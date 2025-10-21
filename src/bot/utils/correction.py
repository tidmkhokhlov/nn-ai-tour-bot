def correction_location(location : str) -> str:
    if location.startswith("Нижний Новгород"):
        pass
    elif location.startswith("Нижний"):
        location = location.replace("Нижний", "Нижний Новгород")
    elif location.startswith("НН"):
        location = location.replace("НН", "Нижний Новгород")
    elif location.startswith("НиНо"):
        location = location.replace("НиНо", "Нижний Новгород")
    else:
        location = "Нижний Новгород, " + location
    return location