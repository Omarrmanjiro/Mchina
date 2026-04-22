from fastapi import FastAPI
from data.cities import cities
from models.path import PathResponse
from algorithms.astar import astar
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Morocco path api is working!"}

@app.get("/cities")
def get_cities():
    return cities

@app.post("/path")
def get_path(request: PathResponse):
    result = astar(request.start, request.goal)
    if result is None:
        return {"error": "No path found"}

    return {"start": request.start,
            "goal": request.goal,
            "path": result["path"],
            "distance": result["distance"],
            "visited": result["visited"]
           }