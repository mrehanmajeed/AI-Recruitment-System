from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from sqlalchemy import inspect, text

from database.connection import engine
from database.models import Base
from scheduler.jobs import start_scheduler
from routers import dashboard, candidates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_db():
    """Add columns missing from older database files."""
    inspector = inspect(engine)
    if "job_descriptions" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("job_descriptions")}
    if "active" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE job_descriptions ADD COLUMN active INTEGER DEFAULT 1")
            )
        logger.info("Added missing 'active' column to job_descriptions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    migrate_db()
    
    # Start Scheduler
    logger.info("Starting scheduler...")
    start_scheduler()
    
    yield
    
    logger.info("Shutting down...")

app = FastAPI(title="TalentFlow — AI Recruitment System", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(dashboard.router)
app.include_router(candidates.router)
