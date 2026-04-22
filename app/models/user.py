from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    
    full_name = Column(String(255), nullable=False)

    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))

    # ---------------- GAMIFICATION ----------------
    coins = Column(Integer, default=0)

    # ---------------- FOCUS & PERFORMANCE ----------------
    daily_goal = Column(Float, default=4.0)
    stress_score = Column(Float, default=0.0)
    burnout_flag = Column(Boolean, default=False)

    suspicion_score = Column(Float, default=0.0)
    strict_mode = Column(Boolean, default=False)

    # ---------------- STREAK SYSTEM ----------------
    last_focus_date = Column(DateTime, nullable=True)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)

    tasks = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )