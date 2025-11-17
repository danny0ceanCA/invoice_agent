from sqlalchemy import create_engine
from app.backend.src.core.config import get_settings
from app.backend.src.models import *  # noqa
from app.backend.src.db.base import Base

def init_db():
    engine = create_engine(get_settings().database_url, future=True)
    print(f"🚀 Connecting to {get_settings().database_url}")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")

if __name__ == "__main__":
    init_db()
