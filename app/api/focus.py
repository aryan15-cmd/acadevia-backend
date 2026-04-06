from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.core.logger import logger
from app.db.database import SessionLocal
from app.models.focus_session import FocusSession
from app.models.task import Task
from app.models.user import User
from app.api.auth import get_current_user
from app.services.integrity_service import calculate_integrity
from app.services.stress_service import calculate_stress
from app.services.agent_service import agent_decision
from app.services.priority_service import calculate_priority
from app.services.anti_cheat_service import evaluate_session
import subprocess


router = APIRouter()


# ---------------- DATABASE DEPENDENCY ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- START FOCUS ----------------

@router.post("/start/{task_id}")
def start_focus(
    task_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):

    # ---------------- FIND TASK ----------------
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # ---------------- GET BLOCKED APPS ----------------
    blocked_apps = data.get("blocked_apps", [])

    # ---------------- START BLOCKER ----------------
    if blocked_apps:
        subprocess.Popen(
            ["python", "app/services/blocker.py"] + blocked_apps
        )

    # ---------------- CREATE SESSION ----------------
    session = FocusSession(
        user_id=user.id,
        task_id=task.id,
        started_at=datetime.utcnow()
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"User {user.id} started focus session {session.id}")

    return {
        "message": "Focus session started",
        "session_id": session.id,
        "blocked_apps": blocked_apps
    }

    # ---------------- BLOCKED APPS ----------------
    blocked_apps = data.get("blocked_apps", [])

    if blocked_apps:
        subprocess.Popen(
            ["python", "app/services/blocker.py"] + blocked_apps
        )

    # ---------------- CREATE SESSION ----------------
    session = FocusSession(
        user_id=user.id,
        task_id=task.id,
        started_at=datetime.utcnow()
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"User {user.id} started focus session {session.id}")

    return {
        "message": "Focus session started",
        "session_id": session.id,
        "blocked_apps": blocked_apps
    }


# ---------------- COMPLETE FOCUS ----------------
@router.post("/complete/{session_id}")
def complete_focus(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    session = db.query(FocusSession).filter(
        FocusSession.id == session_id,
        FocusSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.completed_at:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Mark session complete
    session.completed_at = datetime.utcnow()

    duration_minutes = (
        session.completed_at - session.started_at
    ).total_seconds() / 60

    integrity_score = calculate_integrity(duration_minutes)

    # ---------------- UPDATE TASK ----------------
    task = db.query(Task).filter(
        Task.id == session.task_id
    ).first()

    if task:
        hours_spent = duration_minutes / 60

        if task.actual_hours_spent is None:
            task.actual_hours_spent = 0

        if task.estimated_hours is None:
            task.estimated_hours = 0

        task.actual_hours_spent += hours_spent
        task.estimated_hours -= hours_spent

        if task.estimated_hours < 0:
            task.estimated_hours = 0

        if task.estimated_hours == 0:
            task.is_completed = True

    # ---------------- STREAK LOGIC ----------------
    today = datetime.utcnow().date()

    if user.last_focus_date:
        last_date = user.last_focus_date.date()

        if last_date == today:
            pass
        elif last_date == today - timedelta(days=1):
            user.current_streak = (user.current_streak or 0) + 1
        else:
            user.current_streak = 1
    else:
        user.current_streak = 1

    user.last_focus_date = datetime.utcnow()

    if user.longest_streak is None:
        user.longest_streak = 0

    if user.current_streak > user.longest_streak:
        user.longest_streak = user.current_streak

    # ---------------- ANTI CHEAT ----------------
    user.suspicion_score = evaluate_session(
        user,
        session,
        db,
        duration_minutes
    )

    if user.suspicion_score >= 50:
        user.strict_mode = True

    # ---------------- STRESS UPDATE ----------------
    user_tasks = db.query(Task).filter(
        Task.user_id == user.id
    ).all()

    user.stress_score = calculate_stress(user, user_tasks) or 0

    # ---------------- AGENT DECISION ----------------
    actions = agent_decision(user) or []

    if user.daily_goal is None:
        user.daily_goal = 1

    if "reduce_daily_goal" in actions:
        user.daily_goal = max(user.daily_goal - 0.5, 1)

    if "increase_daily_goal" in actions:
        user.daily_goal += 0.5

    if user.strict_mode:
        user.daily_goal = max(user.daily_goal - 1, 1)

    # ---------------- PRIORITY RECALCULATION ----------------
    for t in user_tasks:
        t.priority_score = calculate_priority(t, user)

    db.commit()

    logger.info(
        f"User {user.id} completed session {session.id} "
        f"Duration: {duration_minutes:.2f} min"
    )

    return {
        "message": "Focus session completed",
        "duration_minutes": round(duration_minutes, 2),
        "integrity_score": integrity_score,
        "current_streak": user.current_streak,
        "stress_score": user.stress_score,
        "daily_goal": user.daily_goal,
        "agent_actions": actions
    }


# ---------------- FAIL FOCUS ----------------
@router.post("/fail/{session_id}")
def fail_focus(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    session = db.query(FocusSession).filter(
        FocusSession.id == session_id,
        FocusSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.completed_at:
        session.completed_at = datetime.utcnow()

    task = db.query(Task).filter(
        Task.id == session.task_id
    ).first()

    if task:
        if task.times_failed is None:
            task.times_failed = 0
        task.times_failed += 1

    db.commit()

    return {"message": "Focus session marked as failed"}