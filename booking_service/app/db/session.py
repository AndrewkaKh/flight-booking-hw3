from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()