from pydantic import BaseModel

class City(BaseModel):
    name: str
    lat: float
    lon: float

class PathResponse(BaseModel):
    start: str
    goal: str