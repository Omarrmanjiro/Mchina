from pydantic import BaseModel

class City(BaseModel):
    name: str
    lat: float
    lon: float


# 1. Ce que le frontend nous envoie (La Requête)
class PathRequest(BaseModel):
    start: str
    goal: str

# 2. Ce que l'API renvoie au frontend (La Réponse)
class PathResponse(BaseModel):
    start: str
    goal: str
    path: List[str]
    distance: float
    visited: List[str]