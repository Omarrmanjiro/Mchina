# models/schemas.py
from pydantic import BaseModel

# Ce que le frontend nous envoie pour créer un compte
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str

# Ce que nous renvoyons au frontend (On ne renvoie JAMAIS le mot de passe !)
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str

    # Cette configuration permet à Pydantic de lire un objet SQLAlchemy
    class Config:
        from_attributes = True