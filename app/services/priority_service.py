from datetime import datetime, timezone

def calculate_priority(task, user):
    now = datetime.now(timezone.utc)

    if task.due_date.tzinfo is None:
        due_date = task.due_date.replace(tzinfo=timezone.utc)
    else:
        due_date = task.due_date.astimezone(timezone.utc)

    delta = due_date - now
    days_left = max(0, delta.days)

    urgency = 10 / (days_left + 1)

    difficulty_weight = (task.difficulty or 0) * 1.5
    failure_weight = (task.times_failed or 0) * 2
    stress_weight = (user.stress_score or 0) * 0.05
    burnout_penalty = 5 if user.burnout_flag else 0

    priority = (
        urgency
        + difficulty_weight
        + failure_weight
        + stress_weight
        - burnout_penalty
    )

    return round(priority, 2)