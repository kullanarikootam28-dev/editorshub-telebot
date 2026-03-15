# AURA Reputation System Logic

# Minimum points required to reach the tier
AURA_LEVELS = [
    (0, "Rookie"),
    (100, "Skilled"),
    (250, "Pro"),
    (500, "Elite"),
    (1000, "Legend")
]

def get_aura_level(points: int) -> str:
    """Returns the AURA level name based on points."""
    level_name = "Rookie"
    for threshold, name in AURA_LEVELS:
        if points >= threshold:
            level_name = name
        else:
            break
    return level_name

def calculate_review_points(action: str) -> int:
    """
    Returns points change based on the action.
    Options: 'completed', '5_star', 'revision', 'late'
    """
    points_map = {
        'completed': 20,
        '5_star': 10,
        'revision': -5,
        'late': -10
    }
    return points_map.get(action, 0)
