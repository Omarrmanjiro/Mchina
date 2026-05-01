# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# The connection string format is: postgresql://username:password@server:port/database_name
# IMPORTANT: Replace 'your_postgres_password' with the password you use to log into pgAdmin!
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/mchina_db"

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models to inherit from
Base = declarative_base()

# Dependency function to get a database session for our API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()