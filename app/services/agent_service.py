def agent_decision(user):
    """
    Decides system adjustments based on stress & burnout
    """

    actions = []

    if user.burnout_flag:
        actions.append("recommend_rest_day")
        actions.append("reduce_daily_goal")

    elif user.stress_score >= 70:
        actions.append("reduce_daily_goal")

    elif user.stress_score <= 30:
        actions.append("increase_daily_goal")

    return actions