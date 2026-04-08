def log_event(action: str, entity_type: str, entity_id: str | None = None) -> None:
    print(f"AUDIT {action} {entity_type} {entity_id}")
