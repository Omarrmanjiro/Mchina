from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
from jose import JWTError, jwt

# --- Imports Base de données & Modèles SQLAlchemy ---
from database import engine, Base, get_db, ensure_schema
from models.users import User
from models.search import Search

# --- Imports Schémas Pydantic (DTOs) ---
from models.schemas import UserCreate, UserUpdate, UserResponse, SearchCreate, MatchResponse, PublicSearchResponse
from models.path import PathRequest, PathResponse 

# --- Imports Logique Métier ---
from data.cities import cities
from algorithms.astar import astar
from utils.auth import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM

# 1. Création des tables dans PostgreSQL
Base.metadata.create_all(bind=engine)
ensure_schema()

# 2. Initialisation de l'API
app = FastAPI(title="Mchina API")

# 3. Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Configuration sécurité
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Dependency to get the current authenticated user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
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
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Vérifie les identifiants dans PostgreSQL et génère un Token JWT.
    """
    # Rechercher l'utilisateur par son email (form_data.username contient l'email)
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email ou mot de passe incorrect"
        )
    
    # Vérifier le mot de passe
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email ou mot de passe incorrect"
        )
    
    # Générer le token de session
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


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
def get_path(request: PathRequest, token: str = Depends(oauth2_scheme)):
    """
    Calcule le trajet optimal avec A*. 
    Nécessite d'être connecté.
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


@app.get("/public-searches", response_model=List[PublicSearchResponse])
def list_public_searches(
    window: str = "1h",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List recent public searches. window: 1h | 6h | 1d.
    Requires Pro subscription.
    """
    if not current_user.is_pro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pro subscription required to view public searches.")

    now = datetime.utcnow()
    if window == "1h":
        since = now - timedelta(hours=1)
    elif window == "6h":
        since = now - timedelta(hours=6)
    elif window == "1d":
        since = now - timedelta(days=1)
    else:
        raise HTTPException(status_code=400, detail="Invalid window. Use 1h, 6h, or 1d.")

    rows = (
        db.query(Search)
        .filter(Search.is_public.is_(True), Search.created_at >= since)
        .order_by(Search.created_at.desc())
        .limit(200)
        .all()
    )

    out: list[dict] = []
    for s in rows:
        out.append(
            {
                "id": s.id,
                "start_city": s.start_city,
                "goal_city": s.goal_city,
                "path": s.path,
                "distance": round(float(s.distance), 2),
                "comment": s.comment,
                "created_at": s.created_at,
                "user_first_name": getattr(s.user, "first_name", None),
                "user_last_name": getattr(s.user, "last_name", None),
                "user_phone": s.user.phone,
            }
        )
    return out