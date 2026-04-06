from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from groq import Groq
import os
import json
import re

from app.db.database import SessionLocal
from app.api.auth import get_current_user
from app.models.focus_session import FocusSession
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


@router.post("/ai-chat")
async def ai_chat(
    data: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    message = data.get("message", "").strip().lower()

    # ---------------- WEEKLY FOCUS ----------------

    today = datetime.utcnow()
    week_ago = today - timedelta(days=7)

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.started_at >= week_ago,
        FocusSession.completed_at != None
    ).all()

    total_minutes = 0

    for s in sessions:
        duration = (s.completed_at - s.started_at).total_seconds() / 60
        total_minutes += duration

    weekly_hours = round(total_minutes / 60, 2)

    # ---------------- TASK COMPLETION ----------------

    tasks = db.query(Task).filter(Task.user_id == user.id).all()

    completed_tasks = len([t for t in tasks if t.is_completed])

    completion_rate = (
        round((completed_tasks / len(tasks)) * 100, 2)
        if tasks else 0
    )

    stress_score = user.stress_score or 0


    # ==============================
    # SCHEDULE / PLAN REQUEST
    # ==============================

    if "schedule" in message or "plan" in message:

        prompt = f"""
Create a study schedule based on the user's request.

User request:
{message}

Rules:
- Detect the subject from the request.
- Create tasks ONLY related to that subject.
- Do NOT always use math examples.
- Each day must have a different task.

Return ONLY JSON:

[
{{"day":1,"task":"...","hours":2}},
{{"day":2,"task":"...","hours":2}},
{{"day":3,"task":"...","hours":2}}
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

            print("AI RAW RESPONSE:", text)

            json_match = re.search(r"\[.*?\]", text, re.S)

            if not json_match:
                return {"reply": "I couldn't generate a schedule. Please try again."}

            plan = json.loads(json_match.group())

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI parsing failed: {str(e)}")

        if not plan:
            return {"reply": "AI did not generate any tasks."}

        created_tasks = []
        subject = message.split("for")[-1].strip() if "for" in message else "General Study"

        for item in plan:

            task = Task(
                user_id=user.id,
                subject=subject,
                description=item.get("task"),
                estimated_hours=item.get("hours", 2),
                difficulty=2,
                due_date=datetime.utcnow() + timedelta(days=item.get("day", 1))
            )

            db.add(task)
            created_tasks.append(task)

        db.commit()

        return {
            "reply": f"I created {len(created_tasks)} study tasks for you!"
        }


    # ==============================
    # NORMAL STUDY ADVICE
    # ==============================

    prompt = f"""
User message: {message}

User study data:
Weekly focus hours: {weekly_hours}
Completion rate: {completion_rate}
Stress score: {stress_score}

Give short study advice (1–2 sentences).
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are an AI study coach in a productivity app."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=60,
        temperature=0.7
    )

    reply = response.choices[0].message.content.strip()

    return {"reply": reply}