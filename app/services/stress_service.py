from datetime import datetime, timedelta

def calculate_stress(user, tasks):
    """
    Calculates stress score between 0 - 100
    """

    now = datetime.utcnow()
    upcoming_days = now + timedelta(days=3)

    # ---------------- WORKLOAD DENSITY ----------------
    total_hours = sum(
    task.estimated_hours - task.actual_hours_spent
    for task in tasks
    if task.due_date and task.due_date <= upcoming_days
)

    workload_score = min(total_hours * 5, 40)

    # ---------------- DEADLINE CLUSTERING ----------------
    deadlines = [
        task.due_date.date()
        for task in tasks
        if task.due_date <= upcoming_days
    ]

    clustering_score = 0
    if len(deadlines) >= 3:
        clustering_score = 20

    # ---------------- FAILURE IMPACT ----------------
    failure_score = sum(task.times_failed for task in tasks) * 3
    failure_score = min(failure_score, 20)

    # ---------------- TOTAL STRESS ----------------
    stress = workload_score + clustering_score + failure_score

    return min(stress, 100)