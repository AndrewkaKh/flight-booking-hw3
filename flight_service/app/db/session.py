from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.settings import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
