from pathlib import Path

ROOT = Path(__file__).resolve().parent

TARGETS = [
    "backend/app/modules/items/routes/items_routes.py",
    "backend/app/modules/deliveries/routes/deliveries_routes.py",
    "backend/app/modules/rentals/routes/rentals_routes.py",
    "backend/app/modules/orders/routes/orders_routes.py",
]

def ensure_import(text: str) -> str:
    if "from app.core.admin import is_admin" in text:
        return text

    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1

    lines.insert(insert_at, "from app.core.admin import is_admin")
    return "\n".join(lines) + "\n"

def remove_local_is_admin(text: str) -> str:
    text = text.replace(
        '\n\ndef _is_admin(user: User) -> bool:\n    return bool(getattr(user, "is_superuser", False))\n',
        '\n',
    )
    text = text.replace(
        '\n\ndef _is_admin(user) -> bool:\n    return bool(getattr(user, "is_superuser", False))\n',
        '\n',
    )
    return text

def main() -> None:
    for rel_path in TARGETS:
        path = ROOT / rel_path
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        text = path.read_text(encoding="utf-8")
        text = ensure_import(text)
        text = remove_local_is_admin(text)
        text = text.replace("_is_admin(", "is_admin(")
        path.write_text(text, encoding="utf-8")
        print(f"updated: {rel_path}")

if __name__ == "__main__":
    main()
