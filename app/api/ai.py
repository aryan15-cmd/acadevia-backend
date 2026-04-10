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

# ✅ CSV IMPORTS
from app.utils.dataset import load_dataset
from app.utils.search import search_data

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ✅ LOAD DATASET ONCE
DATA = load_dataset()


# ---------------- DATABASE ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🔥 CLEAN TASK FUNCTION (NEW)
def clean_task(text):
    text = text.lower()

    remove_words = [
        "watch video lectures on",
        "introduction to",
        "practice",
        "learn",
        "study"
    ]

    for word in remove_words:
        text = text.replace(word, "")

    return text.strip().capitalize()


# ==============================
# MAIN AI CHAT ENDPOINT
# ==============================

@router.post("/ai-chat")
async def ai_chat(
    data: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    message = data.get("message", "").strip().lower()

    # ==============================
    # 🔍 SEARCH CSV DATASET
    # ==============================

    results = search_data(message, DATA)
    context = "\n\n".join(results)

    print("USER:", message)
    print("SEARCH RESULTS:", results)

    if not results:
        return {"reply": "Not in dataset"}

    # ==============================
    # 📊 USER ANALYTICS
    # ==============================

    today = datetime.utcnow()
    week_ago = today - timedelta(days=7)

    sessions = db.query(FocusSession).filter(
        FocusSession.user_id == user.id,
        FocusSession.started_at >= week_ago,
        FocusSession.completed_at != None
    ).all()

    total_minutes = sum(
        (s.completed_at - s.started_at).total_seconds() / 60
        for s in sessions
    )

    weekly_hours = round(total_minutes / 60, 2)

    tasks = db.query(Task).filter(Task.user_id == user.id).all()
    completed_tasks = len([t for t in tasks if t.is_completed])

    completion_rate = (
        round((completed_tasks / len(tasks)) * 100, 2)
        if tasks else 0
    )

    stress_score = user.stress_score or 0

    # ==============================
    # 📅 PLAN / SCHEDULE GENERATION
    # ==============================

    if "schedule" in message or "plan" in message:

        prompt = f"""
You are a STRICT study planner.

ABSOLUTE RULES:
- Use ONLY the DATA provided
- DO NOT add any new information
- If not found, say EXACTLY: Not in dataset

DATA:
{context}

User request:
{message}

TASK RULES:
- Tasks must be SHORT (max 10 words)
- Use words from DATA only
- No explanation

Return ONLY JSON:

[
{{"day":1,"task":"...","hours":1,"difficulty":"easy"}},
{{"day":2,"task":"...","hours":2,"difficulty":"medium"}},
{{"day":3,"task":"...","hours":3,"difficulty":"hard"}}
]
"""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a strict planner."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250
            )

            text = response.choices[0].message.content.strip()
            print("AI RAW RESPONSE:", text)

            json_match = re.search(r"\[.*?\]", text, re.S)

            if not json_match:
                return {"reply": "I couldn't generate a schedule."}

            plan = json.loads(json_match.group())

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        created_tasks = []

        subject = (
            message.split("for")[-1].strip()
            if "for" in message else "Study"
        )

        for item in plan:

            difficulty_map = {
                "easy": 1,
                "medium": 2,
                "hard": 3
            }

            difficulty_text = item.get("difficulty", "medium").lower()
            difficulty = difficulty_map.get(difficulty_text, 2)

            task = Task(
                user_id=user.id,
                subject=subject,
                description=clean_task(item.get("task", "Study")),
                estimated_hours=item.get("hours", 2),
                difficulty=difficulty,
                due_date=datetime.utcnow() + timedelta(days=item.get("day", 1))
            )

            db.add(task)
            created_tasks.append(task)

        db.commit()

        return {
            "reply": "Your personalized study plan is ready 📚",
            "tasks": [
                {
                    "day": item.get("day"),
                    "task": clean_task(item.get("task")),
                    "hours": item.get("hours"),
                    "difficulty": item.get("difficulty")
                }
                for item in plan
            ]
        }

    # ==============================
    # 💡 NORMAL STUDY ADVICE
    # ==============================

    prompt = f"""
You are a study coach.

STRICT RULES:
- Answer ONLY using DATA
- If not found, say: Not in dataset

DATA:
{context}

User message:
{message}

User stats:
Weekly hours: {weekly_hours}
Completion rate: {completion_rate}
Stress: {stress_score}

Give short answer (1–2 sentences).
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a study assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60
        )

        reply = response.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"reply": reply}