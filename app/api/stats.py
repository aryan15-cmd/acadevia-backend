from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.models.task import Task
from app.api.auth import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def get_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    today = date.today()

    daily_completed = db.query(Task).filter(
        Task.user_id == user.id,
        Task.is_completed == True,
        Task.completed_at >= today
    ).count()

    return {
        "daily_completed": daily_completed,
        "streak": 0
    }