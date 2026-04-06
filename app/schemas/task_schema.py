from pydantic import BaseModel
from datetime import datetime

class TaskCreate(BaseModel):
    subject: str
    description: str
    due_date: datetime
    estimated_hours: float
    difficulty: int

class TaskResponse(BaseModel):
    id: int
    subject: str
    due_date: datetime
    priority_score: float

    class Config:
      from_attributes = True