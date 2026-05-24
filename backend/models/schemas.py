from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# --- User Schemas ---

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_pro: bool

    class Config:
        from_attributes = True

# --- Search & Matching Schemas ---

class SearchCreate(BaseModel):
    start_city: str
    goal_city: str
    path: List[str]
    distance: float
    is_public: bool = False
    comment: Optional[str] = None

class SearchResponse(SearchCreate):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class MatchResponse(BaseModel):
    user_full_name: str
    user_phone: Optional[str]
    start_city: str
    goal_city: str
    path: List[str]
    distance: float
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PublicSearchResponse(BaseModel):
    id: int
    start_city: str
    goal_city: str
    path: List[str]
    distance: float
    comment: Optional[str] = None
    created_at: datetime

    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_phone: Optional[str] = None

    class Config:
        from_attributes = True