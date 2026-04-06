from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict

from app.services.stress_service import calculate_stress
from app.db.database import SessionLocal
from app.api.auth import get_current_user
from app.models.focus_session import FocusSession
from app.models.task import Task
from app.core.logger import logger

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================
# WEEKLY REPORT
# ==============================

@router.get("/weekly-report")
def weekly_report(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    today = datetime.utcnow()

    # start from Monday
    start_of_week = today - timedelta(days=today.weekday())

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.started_at >= start_of_week,
        FocusSession.completed_at != None
    ).all()

    total_minutes = 0
    daily_minutes = defaultdict(int)

    for s in sessions:

        duration = (s.completed_at - s.started_at).total_seconds() / 60
        total_minutes += duration

        day_index = s.started_at.weekday()
        daily_minutes[day_index] += duration

    # total weekly hours
    weekly_hours = round(total_minutes / 60, 2)

    # daily focus hours for chart
    daily_focus_hours = [
        round(daily_minutes[i] / 60, 2) for i in range(7)
    ]

    # ---------------- TASK DATA ----------------

    tasks = db.query(Task).filter(
        Task.user_id == user.id
    ).all()

    tasks_total = len(tasks)
    completed_tasks = len([t for t in tasks if t.is_completed])

    completion_rate = round(
        (completed_tasks / tasks_total) * 100, 2
    ) if tasks_total else 0

    # ---------------- ESTIMATION ACCURACY ----------------

    estimated_total = 0
    actual_total = 0

    for t in tasks:

        if getattr(t, "estimated_minutes", None) and getattr(t, "actual_minutes", None):

            estimated_total += t.estimated_minutes
            actual_total += t.actual_minutes

    estimation_accuracy = round(
        (estimated_total / actual_total) * 100, 2
    ) if actual_total else 0

    # ---------------- STRESS SCORE ----------------

    stress_score = calculate_stress(user, tasks)

    return {
        "stress_score": stress_score,
        "estimation_accuracy": estimation_accuracy,
        "completion_rate": completion_rate,
        "weekly_focus_hours": weekly_hours,
        "daily_focus_hours": daily_focus_hours
    }


# ==============================
# STRESS TREND
# ==============================

@router.get("/stress-trend")
def stress_trend(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    today = datetime.utcnow()
    week_ago = today - timedelta(days=7)

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.started_at >= week_ago
    ).all()

    daily_stress = defaultdict(list)

    for s in sessions:
        date = s.started_at.date()
        daily_stress[str(date)].append(user.stress_score)

    trend = {
        day: round(sum(scores) / len(scores), 2)
        for day, scores in daily_stress.items()
    }

    return trend


# ==============================
# FOCUS HEATMAP
# ==============================

@router.get("/focus-heatmap")
def focus_heatmap(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.completed_at != None
    ).all()

    heatmap = defaultdict(int)

    for s in sessions:

        hour = s.started_at.hour

        duration = (s.completed_at - s.started_at).total_seconds() / 60
        heatmap[hour] += duration

    return heatmap


# ==============================
# PRODUCTIVITY SCORE
# ==============================

@router.get("/productivity-score")
def productivity_score(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.completed_at != None
    ).all()

    if not sessions:
        return {"productivity_score": 0}

    total_minutes = 0

    for s in sessions:
        duration = (s.completed_at - s.started_at).total_seconds() / 60
        total_minutes += duration

    avg_focus = total_minutes / len(sessions)

    consistency_bonus = (user.current_streak or 0) * 2
    penalty = (user.suspicion_score or 0) * 0.5

    score = avg_focus + consistency_bonus - penalty

    score = max(min(score, 100), 0)

    return {
        "productivity_score": round(score, 2)
    }