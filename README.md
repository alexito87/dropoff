
# dropoff

MVP rental marketplace.

## Local start

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seeds.categories
```

## URLs

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health-check
- Categories: http://localhost:8000/api/v1/categories
- pgAdmin: http://localhost:5050
- Mailpit: http://localhost:8025

## Sprint 1 endpoints

- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/verify-email?token=...`
- `POST /api/v1/auth/resend-verification`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
