from database.sheets import get_latest_order_id, increment_order_id

def generate_new_order_id() -> str:
    """Reads latest ID from DB and returns the next one."""
    latest = get_latest_order_id()
    new_id = increment_order_id(latest)
    return new_id
