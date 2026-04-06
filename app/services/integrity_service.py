def calculate_integrity(duration_minutes):
    if duration_minutes >= 25:
        return 100
    elif duration_minutes >= 15:
        return 80
    elif duration_minutes >= 5:
        return 50
    else:
        return 20