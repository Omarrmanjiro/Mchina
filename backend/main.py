from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# --- Imports Base de données & Modèles SQLAlchemy ---
from database import engine, Base, get_db
from models.users import User

# --- Imports Schémas Pydantic (DTOs) ---
from models.schemas import UserCreate, UserResponse
# Assure-toi d'importer PathRequest (pour l'entrée) au lieu de PathResponse
from models.path import PathRequest, PathResponse 

# --- Imports Logique Métier ---
from data.cities import cities
from algorithms.astar import astar
from utils.auth import verify_password, get_password_hash, create_access_token

# 1. Création des tables dans PostgreSQL
Base.metadata.create_all(bind=engine)

# 2. Initialisation de l'API
app = FastAPI(title="Mchina API")

# 3. Configuration CORS (pour autoriser ton futur frontend React/Web à communiquer)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Configuration sécurité (indique à Swagger où envoyer les identifiants)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


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
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
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
    Nécessite d'être connecté (Token JWT valide fourni par Swagger).
    """
    result = astar(request.start, request.goal)
    
    if result is None:
        raise HTTPException(status_code=404, detail="No path found")

    return {
        "start": request.start,
        "goal": request.goal,
        "path": result["path"],
        "distance": result["distance"],
        "visited": result["visited"]
    }