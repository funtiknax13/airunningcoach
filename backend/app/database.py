from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

_is_sqlite = "sqlite" in settings.DATABASE_URL

# Пул ограничен так, чтобы 2 воркера uvicorn вместе укладывались в
# postgres max_connections=20: 7+2=9 на воркер × 2 = 18, +1 на лок планировщика.
# pool_pre_ping убирает «висящие» мёртвые соединения после рестарта postgres.
_engine_kwargs = dict(
    pool_pre_ping=True,
    pool_recycle=1800,
)
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(pool_size=7, max_overflow=2)

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()