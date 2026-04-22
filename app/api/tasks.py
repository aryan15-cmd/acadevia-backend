from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.task import Task
from app.schemas.task_schema import TaskCreate
from app.api.auth import get_current_user
from app.services.priority_service import calculate_priority
from datetime import datetime

router = APIRouter()


# ---------------- DATABASE DEPENDENCY ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- CREATE TASK ----------------
@router.post("/")
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    new_task = Task(
        user_id=user.id,
        subject=task.subject,
        description=task.description,
        due_date=task.due_date,
        estimated_hours=task.estimated_hours,
        difficulty=task.difficulty
    )

    # Calculate priority
    new_task.priority_score = calculate_priority(new_task, user)

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # Return full created task instead of message
    return new_task


# ---------------- GET TASKS ----------------
@router.get("/")
def get_tasks(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(Task.priority_score.desc())
        .all()
    )

    return tasks


# ---------------- UPDATE TASK ----------------
@router.put("/{task_id}")
def update_task(
    task_id: int,
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.subject = task_data.subject
    task.description = task_data.description
    task.due_date = task_data.due_date
    task.estimated_hours = task_data.estimated_hours
    task.difficulty = task_data.difficulty

    # Recalculate priority
    task.priority_score = calculate_priority(task, user)

    db.commit()
    db.refresh(task)

    return task


# ---------------- DELETE TASK ----------------
@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return {"message": "Task deleted successfully"}



# ---------------- COMPLETE TASK ----------------
@router.put("/{task_id}/complete")
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_completed = True
    task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    return task   