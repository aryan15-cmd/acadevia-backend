from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    # ---------------- PRIMARY KEY ----------------
    id = Column(Integer, primary_key=True, index=True)

    # ---------------- USER RELATION ----------------
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False   # ✅ Important
    )

    # ---------------- TASK DETAILS ----------------
    subject = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    due_date = Column(DateTime, nullable=True)

    # ---------------- TIME TRACKING ----------------
    estimated_hours = Column(Float, default=0.0)
    actual_hours_spent = Column(Float, default=0.0)

    # ---------------- STATUS ----------------
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # ---------------- PERFORMANCE METRICS ----------------
    difficulty = Column(Integer, default=1)
    times_failed = Column(Integer, default=0)
    priority_score = Column(Float, default=0.0)

    # ---------------- TIMESTAMP ----------------
    created_at = Column(DateTime, default=datetime.utcnow)

    # ---------------- RELATIONSHIPS ----------------
    user = relationship("User", back_populates="tasks")

    focus_sessions = relationship(
        "FocusSession",
        back_populates="task",
        cascade="all, delete-orphan"
    )