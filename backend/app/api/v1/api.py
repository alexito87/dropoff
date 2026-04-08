from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, items, users, categories

api_router = APIRouter()
api_router.include_router(health.router, prefix='/health-check', tags=['health'])
api_router.include_router(auth.router, prefix='/auth', tags=['auth'])
api_router.include_router(users.router, prefix='/users', tags=['users'])
api_router.include_router(categories.router, prefix='/categories', tags=['categories'])
api_router.include_router(items.router, prefix='/items', tags=['items'])
