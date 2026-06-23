from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int 
    ALLOWED_ORIGINS: str
    REDIS_URL: str 
    class Config:
        env_file = ".env"

settings = Settings()