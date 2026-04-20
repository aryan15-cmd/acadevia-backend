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


# ---------------- SEARCH (IMPROVED) ----------------

def search_data(query, data, top_k=3):
    query_words = query.lower().split()
    scored = []

    for item in data:
        text = item.lower()
        score = sum(1 for word in query_words if word in text)

        if score > 0:
            scored.append((score, item))

    scored.sort(reverse=True)
    return [item for _, item in scored[:top_k]]


# ---------------- CONTEXT COMPRESS ----------------

def compress_context(results):
    return "\n".join(r[:120] for r in results)


# ---------------- CLEAN TASK ----------------

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

    message = str(data.get("message", "")).strip().lower()

    # 🔍 SEARCH (IMPROVED)
    results = search_data(message, DATA, top_k=3)

    # ✅ Fallback if no dataset match
    if not results:
        context = message
    else:
        context = compress_context(results)

    print("USER:", message)
    print("CONTEXT:", context)

    # ==============================
    # 📅 PLAN GENERATION
    # ==============================

    if "schedule" in message or "plan" in message:

        prompt = f"""
Make a simple 3-day study plan.

Context:
{context}

User: {message}

Return ONLY JSON:
[{{"day":1,"task":"","hours":1,"difficulty":"easy"}}]
"""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You create short study plans."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=120,   # ✅ reduced
                temperature=0.3,
                timeout=8
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

            task = Task(
                user_id=user.id,
                subject=subject,
                description=task_text,
                estimated_hours=int(item.get("hours", 2)),
                difficulty=difficulty_map.get(item.get("difficulty", "medium"), 2),
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
Answer briefly (1-2 lines).

Context:
{context}

User: {message}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Helpful study assistant"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            timeout=8
        )

        reply = response.choices[0].message.content.strip()

    except:
        return {"reply": "AI error"}

    return {"reply": reply}