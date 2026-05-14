# main.py
from fastapi import FastAPI

# Импорт функций include_module из index.py каждого модуля
from modules.auth.index import include_module as include_auth
from modules.users.index import include_module as include_users
from modules.catalog.index import include_module as include_catalog
from modules.items.index import include_module as include_items
from modules.orders.index import include_module as include_orders
from modules.payments.index import include_module as include_payments
from modules.rentals.index import include_module as include_rentals
from modules.notifications.index import include_module as include_notifications

app = FastAPI(
    title="Dropoff Modular Monolith",
    description="Маркетплейс обмена вещами — модульный монолит",
    version="1.0.0"
)

# Подключаем модули
include_auth(app)
include_users(app)
include_catalog(app)
include_items(app)
include_orders(app)
include_payments(app)
include_rentals(app)
include_notifications(app)

# Опционально: корневой эндпоинт для проверки
@app.get("/")
async def root():
    return {"message": "Dropoff Modular Monolith is running!"}


