from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from groq import Groq
import os
import json
import re
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.api.auth import get_current_user
from app.models.task import Task

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ---------------- DATABASE ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- AI STUDY PLAN ----------------

@router.post("/ai-plan")
async def ai_plan(
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    prompt = f"""
Create a short study plan.

Exam: {data.get("exam")}
Days left: {data.get("days")}
Topics: {data.get("topics")}
Daily study time: {data.get("hours")} hours

Return ONLY JSON like this:

[
  {{"day":1,"task":"Algebra basics","hours":2}},
  {{"day":2,"task":"Algebra practice","hours":2}}
]
"""

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an AI study planner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )

        text = response.choices[0].message.content.strip()

        # Extract JSON safely
        json_match = re.search(r"\[.*\]", text, re.S)

        if not json_match:
            raise HTTPException(status_code=500, detail="AI returned invalid format")

        plan = json.loads(json_match.group())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {str(e)}")

    created_tasks = []

    for item in plan:

        task = Task(
            user_id=user.id,
            subject=data.get("exam"),
            description=item.get("task"),
            estimated_hours=item.get("hours", 2),
            difficulty=item.get("difficulty", 2),
            due_date=datetime.utcnow() + timedelta(days=item.get("day", 1))
        )

        db.add(task)
        created_tasks.append(task)

    db.commit()

    return {
        "message": "AI study plan created",
        "tasks_created": len(created_tasks)
    }