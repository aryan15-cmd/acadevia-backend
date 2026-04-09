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

    # ❗ If nothing found
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
You are a study planner AI.

STRICT RULES:
- Use ONLY the dataset provided
- Do NOT use outside knowledge
- If data is insufficient, respond: "Not in dataset"

DATA:
{context}

User request:
{message}

Create a 3-day study plan.

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
                    {"role": "system", "content": "You are a strict study planner."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )

            text = response.choices[0].message.content.strip()
            print("AI RAW RESPONSE:", text)

            json_match = re.search(r"\[.*?\]", text, re.S)

            if not json_match:
                return {"reply": "I couldn't generate a schedule."}

            plan = json.loads(json_match.group())

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")

        if not plan:
            return {"reply": "No tasks generated."}

        created_tasks = []

        subject = (
            message.split("for")[-1].strip()
            if "for" in message else "Study"
        )

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
            "reply": f"I created {len(created_tasks)} tasks using your dataset!"
        }

    # ==============================
    # 💡 NORMAL STUDY ADVICE
    # ==============================

    prompt = f"""
You are a study coach AI.

STRICT RULES:
- Answer ONLY using the dataset
- If answer not found, say: "Not in dataset"

DATA:
{context}

User message:
{message}

User stats:
- Weekly focus hours: {weekly_hours}
- Completion rate: {completion_rate}
- Stress score: {stress_score}

Give a short helpful answer (1–2 sentences).
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful study assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,
            temperature=0.7
        )

        reply = response.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"reply": reply}