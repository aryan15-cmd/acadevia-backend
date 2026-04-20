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
from app.utils.dataset import load_dataset, DATA
from app.utils.search import search_data

router = APIRouter()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ---------------- DATASET LOAD ----------------
try:
    if not DATA:
        load_dataset()
except Exception as e:
    print("Dataset load failed:", e)


# ---------------- DATABASE ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- CONTEXT COMPRESS ----------------
def compress_context(rows):
    return "\n".join(r[:100] for r in rows)


# ---------------- STRONG JSON PARSER ----------------
def extract_json(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\[[\s\S]*\]", text)  # more robust
        if match:
            try:
                return json.loads(match.group())
            except:
                return None
        return None


# ---------------- CLEAN TASK ----------------
def clean_task(text):
    if not text:
        return ""

    text = text.lower()

    remove_words = [
        "study", "learn", "practice",
        "understand", "topic", "concept"
    ]

    for word in remove_words:
        text = text.replace(word, "")

    return text.strip().title()


# ==============================
# MAIN AI PLAN ENDPOINT
# ==============================
@router.post("/ai-plan")
async def ai_plan(
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        # ---------------- INPUT ----------------
        exam = str(data.get("exam", "")).strip()
        topics = str(data.get("topics", "")).strip()
        days = max(1, int(data.get("days", 1)))
        hours = max(1, int(data.get("hours", 2)))

        if not exam:
            raise HTTPException(status_code=400, detail="Exam is required")

        # ---------------- QUERY ----------------
        query = f"{exam} {topics}".strip()

        # ---------------- SEARCH ----------------
        relevant_rows = search_data(query, DATA, top_k=5)

        # ---------------- CONTEXT ----------------
        if relevant_rows:
            context = compress_context(relevant_rows)
        else:
            context = query  # fallback

        print("QUERY:", query)
        print("CONTEXT:", context)

        # ---------------- STRONG PROMPT ----------------
        prompt = f"""
Create a {days}-day study plan.

Context:
{context}

Exam: {exam}
Daily hours: {hours}

Rules:
- One task per day
- Max 5 words per task
- Use clear academic topic names
- Do NOT include explanations
- Output ONLY pure JSON (no text before or after)

Format:
[{{"day":1,"task":"CPU Scheduling","hours":2}}]
"""

        # ---------------- AI CALL ----------------
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Return ONLY valid JSON array. No explanation."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
            temperature=0.3,
            timeout=8
        )

        text = response.choices[0].message.content.strip()
        print("AI RAW:", text)

        # ---------------- PARSE ----------------
        plan = extract_json(text)

        if not plan or not isinstance(plan, list):
            raise HTTPException(status_code=500, detail="Invalid AI output")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI failed: {str(e)}")

    # ---------------- SAVE TASKS ----------------
    created_tasks = []

    for i, item in enumerate(plan[:days]):
        try:
            task_text = clean_task(item.get("task", ""))

            if len(task_text) < 3:
                task_text = f"{exam} Topic {i+1}"

            task = Task(
                user_id=user.id,
                subject=exam,
                description=task_text,
                estimated_hours=int(item.get("hours", hours)),
                difficulty=2,
                due_date=datetime.utcnow() + timedelta(days=i + 1)
            )

            db.add(task)
            created_tasks.append(task)

        except Exception:
            continue

    db.commit()

    # ---------------- RESPONSE ----------------
    return {
        "message": "AI study plan created successfully 📚",
        "tasks_created": len(created_tasks),
        "preview": plan[:days]
    }