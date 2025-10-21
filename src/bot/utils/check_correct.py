def is_valid_time(time : str) -> bool:
    try:
        float(time)
        return True
    except ValueError:
        return False

def is_valid_location(location : str) -> bool:
    try:
        # Пока не придумал
        return True
    except ValueError:
        return False