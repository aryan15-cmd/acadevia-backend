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

# 🔥 NEW IMPORTS
from app.utils.dataset import load_dataset, DATA
from app.utils.search import search_data

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ✅ SAFER DATASET LOAD
try:
    if not DATA:
        load_dataset()
except Exception as e:
    print("Dataset load failed:", e)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/ai-plan")
async def ai_plan(
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        # ✅ SAFE INPUT HANDLING
        exam = str(data.get("exam", "")).strip()
        topics = str(data.get("topics", "")).strip()
        days = int(data.get("days", 1))
        hours = int(data.get("hours", 2))

        if not exam:
            raise HTTPException(status_code=400, detail="Exam is required")

        # 🔥 STEP 1: CREATE QUERY
        query = f"{exam} {topics}".strip()

        # 🔥 STEP 2: GET RELEVANT DATA
        relevant_rows = search_data(query, DATA, top_k=5)

        # ✅ FALLBACK IF NOTHING FOUND
        if not relevant_rows:
            relevant_rows = DATA[:3]  # fallback minimal data

        # 🔥 STEP 3: BUILD CONTEXT
        context = "\n".join(relevant_rows)

        # 🔥 STEP 4: PROMPT
        prompt = f"""
Use ONLY the dataset below to create a study plan.

DATA:
{context}

Exam: {exam}
Days left: {days}
Daily hours: {hours}

Return ONLY JSON:
[
  {{"day":1,"task":"topic","hours":2}}
]
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict AI planner. Use only given data. Return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.2
        )

        text = response.choices[0].message.content.strip()

        # ✅ FIXED JSON REGEX (NON-GREEDY)
        json_match = re.search(r"\[\s*{.*?}\s*\]", text, re.S)

        if not json_match:
            raise HTTPException(status_code=500, detail="AI returned invalid format")

        plan = json.loads(json_match.group())

        # ✅ VALIDATE PLAN STRUCTURE
        if not isinstance(plan, list):
            raise HTTPException(status_code=500, detail="Invalid plan format")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {str(e)}")

    created_tasks = []

    for item in plan:
        try:
            task = Task(
                user_id=user.id,
                subject=exam,
                description=str(item.get("task", "Study session")),
                estimated_hours=int(item.get("hours", 2)),
                difficulty=int(item.get("difficulty", 2)),
                due_date=datetime.utcnow() + timedelta(days=int(item.get("day", 1)))
            )

            db.add(task)
            created_tasks.append(task)

        except Exception:
            # skip bad items instead of crashing
            continue

    db.commit()

    return {
        "message": "AI study plan created (dataset-driven)",
        "tasks_created": len(created_tasks)
    }