import os 
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import json
import time
import redis as redis_lib
from utils.redis_client import get_redis
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from jose import JWTError, jwt

# --- Imports Base de données & Modèles SQLAlchemy ---
from database import engine, Base, get_db, ensure_schema, SessionLocal
from models.users import User
from models.search import Search

# --- Imports Schémas Pydantic (DTOs) ---
from models.schemas import UserCreate, UserUpdate, UserResponse, SearchCreate, MatchResponse, PublicSearchResponse, AdminUserUpdate
from models.path import PathRequest, PathResponse

# --- Imports Logique Métier ---
from data.cities import cities
from algorithms.astar import astar
from utils.auth import verify_password, get_password_hash, create_access_token

from config import settings
# 1. Création des tables dans PostgreSQL
Base.metadata.create_all(bind=engine)
ensure_schema()

# --- Tâches d'arrière-plan & Initialisation ---

async def purge_old_searches_loop():
    while True:
        try:
            db = SessionLocal()
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            deleted_count = db.query(Search).filter(Search.created_at < one_week_ago).delete()
            if deleted_count > 0:
                db.commit()
                print(f"Purged {deleted_count} searches older than 1 week.")
            db.close()
        except Exception as e:
            print(f"Error purging old searches: {e}")
        await asyncio.sleep(86400) # Sleep for 24 hours

def seed_admin():
    db = SessionLocal()
    try:
        admin_email = "admin@mchina.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                hashed_password=get_password_hash("admin2026"),
                full_name="System Admin",
                first_name="System",
                last_name="Admin",
                phone="+212600000000",
                is_pro=True,
                is_admin=True
            )
            db.add(admin)
            db.commit()
            print("Seeded admin account successfully.")
    except Exception as e:
        print(f"Error seeding admin: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    seed_admin()
    purge_task = asyncio.create_task(purge_old_searches_loop())
    yield
    # Shutdown
    purge_task.cancel()

# 2. Initialisation de l'API
app = FastAPI(title="Mchina API", lifespan=lifespan)


# ==========================================
# CONFIGURATION ENVIRONNEMENT
# ==========================================
# ENV doit être "production" une fois déployé en HTTPS.
# En local (dev), laisser ENV=development (ou ne rien définir).
ENV = os.environ.get("ENV", "development")
IS_PRODUCTION = ENV == "production"

# Durée de vie du cookie (en minutes). Doit correspondre à l'expiration du JWT
# définie dans utils/auth.py (create_access_token).
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Origines autorisées pour le frontend. En dev, ajuste le port si besoin
# (ex: http://localhost:5173 pour Vite, http://localhost:3000 pour Next/CRA).
ALLOWED_ORIGINS = settings.ALLOWED_ORIGINS.split(",")

# 3. Configuration CORS
# IMPORTANT: avec allow_credentials=True, on ne peut PAS utiliser "*" comme
# origine. Le navigateur refuse cette combinaison et n'enverra/n'acceptera
# pas le cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ==========================================
# AUTHENTIFICATION (cookie + Bearer)
# ==========================================

class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    """
    Variante de OAuth2PasswordBearer qui lit le token depuis le cookie
    httpOnly 'access_token' en priorité, puis retombe sur le header
    'Authorization: Bearer <token>' si présent (utile pour Swagger/tests).
    """
    async def __call__(self, request: Request) -> Optional[str]:
        token = request.cookies.get("access_token")
        if token:
            return token
        try:
            return await super().__call__(request)
        except HTTPException:
            return None


oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="login")


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    import time
    t0 = time.time()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    t1 = time.time()

    user = db.query(User).filter(User.email == email).first()
    t2 = time.time()
    
    # Log auth timing (only if it took some time, to reduce extreme spam, but here we log if > 1ms)
    if (t2 - t0) * 1000 > 1:
        print(f"[TIMING] Auth -> JWT Decode: {(t1-t0)*1000:.2f}ms | DB Lookup: {(t2-t1)*1000:.2f}ms | Total Auth: {(t2-t0)*1000:.2f}ms")

    if user is None:
        raise credentials_exception
    return user


# ==========================================
# ROUTES AUTHENTIFICATION (Comptes Utilisateurs)
# ==========================================

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Crée un nouvel utilisateur dans la base de données PostgreSQL.
    """
    # Vérifier si l'email existe déjà
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    # Hacher le mot de passe et sauvegarder
    hashed_password = get_password_hash(user.password)
    full_name = user.full_name
    if not full_name:
        full_name = " ".join([x for x in [user.first_name, user.last_name] if x]) or user.email
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=full_name,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Email ou mot de passe incorrect"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=400,
            detail="Email ou mot de passe incorrect"
        )

    access_token = create_access_token(
        data={"sub": user.email}
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=IS_PRODUCTION,          # True en HTTPS/prod, False en dev http://
        samesite="lax",                # protège contre la majorité des CSRF cross-site
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "message": "Login successful"
    }


@app.post("/logout")
def logout(response: Response):
    """
    Supprime le cookie d'authentification.
    """
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out"}


@app.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Retourne le profil de l'utilisateur connecté, incluant son statut Pro.
    """
    return current_user


@app.put("/me", response_model=UserResponse)
def update_me(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Met à jour le profil de l'utilisateur connecté.
    """
    if update_data.first_name is not None:
        current_user.first_name = update_data.first_name
    if update_data.last_name is not None:
        current_user.last_name = update_data.last_name
    if update_data.phone is not None:
        current_user.phone = update_data.phone

    # Recompute full_name
    first = current_user.first_name or ""
    last = current_user.last_name or ""
    computed_full_name = " ".join([x for x in [first, last] if x]).strip()
    current_user.full_name = computed_full_name or current_user.email

    db.commit()
    db.refresh(current_user)
    return current_user


@app.post("/subscribe")
def subscribe(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Simule un paiement et passe l'utilisateur en Pro.
    """
    current_user.is_pro = True
    db.commit()
    return {"message": "Successfully subscribed to Pro", "is_pro": current_user.is_pro}


# ==========================================
# ROUTES MÉTÉO / TRAJETS (Cœur de Mchina)
# ==========================================

@app.get("/")
def root():
    return {"message": "Mchina API is working!"}


@app.get("/cities")
def get_cities():
    """Retourne la liste des villes disponibles."""
    return cities


@app.post("/path")
def get_path(request: PathRequest, current_user: User = Depends(get_current_user)):
    """
    Calcule le trajet optimal avec A*.
    Nécessite d'être connecté (cookie ou Bearer token valide).
    """
    result = astar(request.start, request.goal)

    if result is None:
        raise HTTPException(status_code=404, detail="No path found")

    return {
        "start": request.start,
        "goal": request.goal,
        "path": result["path"],
        "distance": round(float(result["distance"]), 2),
        "visited": result["visited"]
    }


@app.post("/search", response_model=List[MatchResponse])
def save_search_and_match(
    search_data: SearchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Enregistre une recherche d'itinéraire et retourne les autres utilisateurs
    ayant effectué la même recherche pour un éventuel covoiturage.
    """
    if not current_user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro subscription required to save searches."
        )
    # 1. Enregistrer la recherche
    new_search = Search(
        user_id=current_user.id,
        start_city=search_data.start_city,
        goal_city=search_data.goal_city,
        path=search_data.path,
        distance=round(float(search_data.distance), 2),
        is_public=search_data.is_public,
        comment=search_data.comment,
    )
    db.add(new_search)
    db.commit()
    db.refresh(new_search)

    # 2. Trouver les correspondances (Pro only)
    # Les utilisateurs non-Pro sauvegardent leur recherche mais ne voient pas les correspondances
    if not current_user.is_pro:
        return []

    # On cherche d'autres utilisateurs avec les mêmes villes de départ/arrivée
    matches = db.query(Search).filter(
        Search.start_city == search_data.start_city,
        Search.goal_city == search_data.goal_city,
        Search.user_id != current_user.id
    ).all()

    # 3. Formater la réponse
    results = []
    for m in matches:
        results.append({
            "user_full_name": m.user.full_name,
            "user_phone": m.user.phone,
            "start_city": m.start_city,
            "goal_city": m.goal_city,
            "path": m.path,
            "distance": m.distance,
            "comment": m.comment,
            "created_at": m.created_at
        })

    return results


def refresh_public_searches_cache(window: str):
    """Background task to fetch public searches and update Redis."""
    try:
        db = SessionLocal()
        now = datetime.utcnow()
        if window == "1h":
            since = now - timedelta(hours=1)
        elif window == "6h":
            since = now - timedelta(hours=6)
        elif window == "1d":
            since = now - timedelta(days=1)
        else:
            return

        rows = (
            db.query(Search)
            .filter(Search.is_public.is_(True), Search.created_at >= since)
            .order_by(Search.created_at.desc())
            .limit(200)
            .all()
        )

        out = []
        for s in rows:
            out.append(
                {
                    "id": s.id,
                    "start_city": s.start_city,
                    "goal_city": s.goal_city,
                    "path": s.path,
                    "distance": round(float(s.distance), 2),
                    "comment": s.comment,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "user_first_name": getattr(s.user, "first_name", None),
                    "user_last_name": getattr(s.user, "last_name", None),
                    "user_phone": getattr(s.user, "phone", None),
                }
            )
        
        # Cache for 24 hours (86400 seconds)
        cache_data = {
            "timestamp": time.time(),
            "data": out
        }
        redis_client = get_redis()
        redis_client.setex(f"public_searches:{window}", 86400, json.dumps(cache_data))
        redis_client.delete(f"lock:refresh_public_searches:{window}")
    except Exception as e:
        print(f"Error refreshing cache for {window}: {e}")
        # Make sure to clear the lock on error so it can be retried
        try:
            get_redis().delete(f"lock:refresh_public_searches:{window}")
        except:
            pass
    finally:
        db.close()


@app.get("/public-searches", response_model=List[PublicSearchResponse])
def list_public_searches(
    background_tasks: BackgroundTasks,
    window: str = "1h",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List recent public searches. window: 1h | 6h | 1d.
    Requires Pro subscription.
    """
    t_endpoint_start = time.time()
    if not current_user.is_pro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pro subscription required to view public searches.")

    if window not in ["1h", "6h", "1d"]:
        raise HTTPException(status_code=400, detail="Invalid window. Use 1h, 6h, or 1d.")

    # --- Redis path (with graceful fallback if Redis is unavailable) ---
    try:
        
        redis_client = get_redis()
        cache_key = f"public_searches:{window}"
        cached_response = redis_client.get(cache_key)
        t_redis_get = time.time()

        if cached_response:
            try:
                cache_data = json.loads(cached_response)
                data = cache_data.get("data", [])
                cached_time = cache_data.get("timestamp", 0)

                # Logical TTL: 1 minute (60 seconds)
                if time.time() - cached_time > 60:
                    # Data is logically stale, trigger background refresh
                    lock_key = f"lock:refresh_public_searches:{window}"
                    if redis_client.setnx(lock_key, "1"):
                        redis_client.expire(lock_key, 60)  # Protect against zombie locks
                        background_tasks.add_task(refresh_public_searches_cache, window)

                t_end = time.time()
                print(f"[TIMING] Endpoint -> Redis Read: {(t_redis_get-t_endpoint_start)*1000:.2f}ms | Endpoint Total: {(t_end-t_endpoint_start)*1000:.2f}ms")
                return data
            except json.JSONDecodeError:
                # Cache corrupted, fall through to synchronous refresh
                pass

        # Cache miss — synchronous refresh then return from cache
        refresh_public_searches_cache(window)
        new_cached_response = redis_client.get(cache_key)
        if new_cached_response:
            try:
                return json.loads(new_cached_response).get("data", [])
            except json.JSONDecodeError:
                pass

    except redis_lib.RedisError as e:
        # ---------------------------------------------------------------
        # Redis is down (connection refused, timeout, etc.)
        # Gracefully fall back to a direct synchronous DB query so the
        # endpoint keeps serving data instead of returning a 500 error.
        # ---------------------------------------------------------------
        print(f"[WARNING] Redis unavailable, falling back to DB: {e}")
        now = datetime.utcnow()
        if window == "1h":
            since = now - timedelta(hours=1)
        elif window == "6h":
            since = now - timedelta(hours=6)
        else:  # 1d
            since = now - timedelta(days=1)

        rows = (
            db.query(Search)
            .filter(Search.is_public.is_(True), Search.created_at >= since)
            .order_by(Search.created_at.desc())
            .limit(200)
            .all()
        )
        return [
            {
                "id": s.id,
                "start_city": s.start_city,
                "goal_city": s.goal_city,
                "path": s.path,
                "distance": round(float(s.distance), 2),
                "comment": s.comment,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "user_first_name": getattr(s.user, "first_name", None),
                "user_last_name": getattr(s.user, "last_name", None),
                "user_phone": getattr(s.user, "phone", None),
            }
            for s in rows
        ]

    return []


# ==========================================
# ROUTES D'ADMINISTRATION
# ==========================================

def get_current_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )
    return current_user

@app.get("/admin/users", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    return db.query(User).order_by(User.id).all()

@app.put("/admin/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: int,
    update_data: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if update_data.first_name is not None:
        user.first_name = update_data.first_name
    if update_data.last_name is not None:
        user.last_name = update_data.last_name
    if update_data.phone is not None:
        user.phone = update_data.phone
    if update_data.is_pro is not None:
        user.is_pro = update_data.is_pro
    if update_data.is_admin is not None:
        if user.id == current_admin.id and not update_data.is_admin:
            raise HTTPException(status_code=400, detail="You cannot remove your own admin status.")
        user.is_admin = update_data.is_admin

    # Recompute full_name
    first = user.first_name or ""
    last = user.last_name or ""
    computed_full_name = " ".join([x for x in [first, last] if x]).strip()
    user.full_name = computed_full_name or user.email

    db.commit()
    db.refresh(user)
    return user

@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account.")
    
    # Delete user's searches first to avoid foreign key constraints
    db.query(Search).filter(Search.user_id == user.id).delete()
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
