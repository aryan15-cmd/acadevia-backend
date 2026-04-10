from fastapi import APIRouter, Depends
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

from app.utils.dataset import load_dataset
from app.utils.search import search_data

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ✅ Load dataset once
DATA = load_dataset()


# ---------------- DATABASE ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🔥 CLEAN TASK FUNCTION
def clean_task(text):
    if not text:
        return ""

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
    user=Depends(get_current_user)
):

    # ✅ Safe input
    message = str(data.get("message", "")).strip().lower()

    # 🔍 SEARCH CSV
    results = search_data(message, DATA, top_k=3)
    context = "\n\n".join(results)

    print("USER:", message)
    print("RESULTS:", results)

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

    completed_tasks = len([t for t in tasks if t.is_completed]) if tasks else 0

    completion_rate = (
        round((completed_tasks / len(tasks)) * 100, 2)
        if tasks else 0
    )

    stress_score = user.stress_score or 0

    # ==============================
    # 📅 PLAN GENERATION
    # ==============================

    if "schedule" in message or "plan" in message:

        prompt = f"""
You are a STRICT study planner.

RULES:
- Use ONLY the DATA
- No extra knowledge
- If not found: Not in dataset

DATA:
{context}

User:
{message}

TASK RULES:
- Short tasks (max 10 words)
- Use dataset words only

Return JSON:

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
                    {"role": "system", "content": "Strict planner"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.2,
                timeout=10
            )

            text = response.choices[0].message.content.strip()
            print("AI:", text)

            json_match = re.search(r"\[.*?\]", text, re.S)

            if not json_match:
                return {"reply": "AI format error"}

            try:
                plan = json.loads(json_match.group())
            except:
                return {"reply": "AI parsing error"}

        except:
            return {"reply": "AI request failed"}

        # ✅ Limit tasks
        if len(plan) > 10:
            plan = plan[:5]

        created_tasks = []

        subject = message.split("for")[-1].strip() if "for" in message else "Study"

        for item in plan:

            task_text = clean_task(item.get("task", ""))

            if not task_text:
                continue

            difficulty_map = {
                "easy": 1,
                "medium": 2,
                "hard": 3
            }

            difficulty = difficulty_map.get(
                str(item.get("difficulty", "medium")).lower(), 2
            )

            task = Task(
                user_id=user.id,
                subject=subject,
                description=task_text,
                estimated_hours=int(item.get("hours", 2)),
                difficulty=difficulty,
                due_date=datetime.utcnow() + timedelta(days=int(item.get("day", 1)))
            )

            db.add(task)
            created_tasks.append(task)

        db.commit()

        return {
            "reply": "Your study plan is ready 📚",
            "tasks": [
                {
                    "day": item.get("day"),
                    "task": clean_task(item.get("task", "")),
                    "hours": item.get("hours"),
                    "difficulty": item.get("difficulty")
                }
                for item in plan if item.get("task")
            ]
        }

    # ==============================
    # 💡 NORMAL RESPONSE
    # ==============================

    prompt = f"""
Answer using ONLY DATA.

DATA:
{context}

User:
{message}

Short answer (1–2 lines).
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Study assistant"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            timeout=10
        )

        reply = response.choices[0].message.content.strip()

    except:
        return {"reply": "AI error"}

    return {"reply": reply}