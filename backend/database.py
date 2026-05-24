# database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# The connection string format is: postgresql://username:password@server:port/database_name
# IMPORTANT: Replace 'your_postgres_password' with the password you use to log into pgAdmin!
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:Omarr.2002@localhost:5432/mchina_db"

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models to inherit from
Base = declarative_base()

def ensure_schema():
    """
    Lightweight safety migration for dev environments (no Alembic).
    Adds new columns if they don't exist yet.
    """
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS first_name VARCHAR"))
        conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS last_name VARCHAR"))
        conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS is_pro BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(
            text("ALTER TABLE IF EXISTS searches ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE")
        )
        conn.execute(
            text("ALTER TABLE IF EXISTS searches ADD COLUMN IF NOT EXISTS comment VARCHAR")
        )

# Dependency function to get a database session for our API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()