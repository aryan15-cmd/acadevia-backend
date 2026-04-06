from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from groq import Groq
import os

from app.db.database import SessionLocal
from app.api.auth import get_current_user
from app.models.focus_session import FocusSession
from app.models.task import Task

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/daily-report")
def daily_report(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    today = datetime.utcnow().date()

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id
    ).all()

    today_minutes = 0
    session_count = 0

    for s in sessions:

        if s.completed_at and s.started_at.date() == today:

            duration = (s.completed_at - s.started_at).total_seconds()/60
            today_minutes += duration
            session_count += 1

    focus_hours = round(today_minutes/60,2)

    tasks = db.query(Task).filter(
        Task.user_id == user.id,
        Task.is_completed == True
    ).all()

    completed_tasks = len(tasks)

    prompt = f"""
Daily productivity stats:

Focus hours: {focus_hours}
Sessions completed: {session_count}
Tasks completed: {completed_tasks}

Give short study advice.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":"You are an AI productivity coach."},
            {"role":"user","content":prompt}
        ],
        max_tokens=60
    )

    advice = response.choices[0].message.content.strip()

    return {
        "focus_hours": focus_hours,
        "sessions": session_count,
        "tasks_completed": completed_tasks,
        "ai_advice": advice
    }