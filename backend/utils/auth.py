# utils/auth.py
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

# Clé secrète pour signer les JWT (À mettre dans un fichier .env plus tard !)
SECRET_KEY = "mchina_super_secret_key_pour_le_developpement"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Configuration de bcrypt pour le hachage
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Vérifie si le mot de passe en clair correspond au hash en base de données."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Génère un hash sécurisé à partir d'un mot de passe en clair."""
    return pwd_context.hash(password)

def create_access_token(data: dict):
    """Génère le token JWT contenant les infos de l'utilisateur."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt