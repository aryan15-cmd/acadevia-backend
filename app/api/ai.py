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


# ---------------- SEARCH (UPDATED) ----------------
def search_data(query, data, top_k=3):
    query_words = query.lower().split()
    scored = []

    for row in data:
        text = f"{row.get('subject','')} {row.get('topic','')} {row.get('details','')}".lower()

        score = sum(1 for word in query_words if word in text)

        if score > 0:
            scored.append((row, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [row for row, _ in scored[:top_k]]


# ---------------- CONTEXT COMPRESS ----------------
def compress_context(results):
    return "\n".join(
        f"{r.get('subject','')} - {r.get('topic','')} ({r.get('time',2)}h)"
        for r in results
    )


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

    return text.strip().title()


# ---------------- CSV TOPIC FETCH ----------------
def get_topics_from_csv(query, days):
    query = query.lower()

    filtered = [
        row for row in DATA
        if any(word in row.get("subject", "") for word in query.split())
    ]

    return filtered[:days]


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

    print("USER:", message)

    # ==============================
    # 📅 PLAN GENERATION (CSV FIRST)
    # ==============================
    if "schedule" in message or "plan" in message:

        days = 3  # default
        match = re.search(r"\d+", message)
        if match:
            days = int(match.group())

        # 🔥 CSV FIRST
        csv_topics = get_topics_from_csv(message, days)

        # ==============================
        # ✅ USE CSV DATA
        # ==============================
        if csv_topics:
            print("Using CSV data")

            plan = [
                {
                    "day": i + 1,
                    "task": row["topic"],
                    "hours": row.get("time", 2)
                }
                for i, row in enumerate(csv_topics)
            ]

        # ==============================
        # 🤖 AI FALLBACK
        # ==============================
        else:
            print("Using AI fallback")

            results = search_data(message, DATA, top_k=3)

            if results:
                context = compress_context(results)
            else:
                context = message

            prompt = f"""
Make a {days}-day study plan.

Context:
{context}

User: {message}

Return ONLY JSON:
[{{"day":1,"task":"","hours":2}}]
"""

            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Return only JSON"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=120,
                    temperature=0.3,
                    timeout=8
                )

                text = response.choices[0].message.content.strip()

                json_match = re.search(r"\[.*?\]", text, re.S)

                if not json_match:
                    return {"reply": "AI format error"}

                plan = json.loads(json_match.group())

            except:
                return {"reply": "AI request failed"}

        # ==============================
        # 💾 SAVE TASKS
        # ==============================
        created_tasks = []

        subject = message.split("for")[-1].strip() if "for" in message else "Study"

        for i, item in enumerate(plan[:days]):

            task_text = clean_task(item.get("task", ""))

            if not task_text:
                continue

            hours = int(item.get("hours", 2))

            # 🔥 YOUR REQUIRED FORMAT
            description = f"Study {task_text} for {hours} hour{'s' if hours > 1 else ''} today"

            task = Task(
                user_id=user.id,
                subject=subject,
                description=description,
                estimated_hours=hours,
                difficulty=2,
                due_date=datetime.utcnow() + timedelta(days=i + 1)
            )

            db.add(task)
            created_tasks.append(task)

        db.commit()

        return {
            "reply": "Your study plan is ready 📚",
            "tasks": [
                {
                    "day": item.get("day"),
                    "task": item.get("task"),
                    "hours": item.get("hours")
                }
                for item in plan[:days]
            ]
        }

    # ==============================
    # 💡 NORMAL CHAT
    # ==============================
    results = search_data(message, DATA, top_k=3)

    if results:
        context = compress_context(results)
    else:
        context = message

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