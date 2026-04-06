from datetime import datetime, timedelta


def evaluate_session(user, session, db, duration_minutes):
    """
    Returns updated suspicion score
    """

    # Safe default
    suspicion = user.suspicion_score or 0

    # 1️⃣ Too short session (< 2 min)
    if duration_minutes < 2:
        suspicion += 10

    # 2️⃣ Rapid consecutive sessions (within last 10 minutes)
    recent_sessions = db.query(type(session)).filter(
        type(session).user_id == user.id,
        type(session).started_at >= datetime.utcnow() - timedelta(minutes=10)
    ).count()

    if recent_sessions >= 3:
        suspicion += 5

    # 3️⃣ Too perfect streak farming
    if duration_minutes < 5 and (user.current_streak or 0) > 3:
        suspicion += 5

    # 4️⃣ Reduce suspicion slowly if clean long session
    if duration_minutes >= 25:
        suspicion = max(suspicion - 3, 0)

    return min(suspicion, 100)