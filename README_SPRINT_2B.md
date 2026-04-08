# dropoff — Sprint 2B (Supabase Storage image upload)

Этот пакет содержит **новые и изменённые файлы** для спринта 2B.

## Что реализовано
- загрузка изображений объявления в Supabase Storage
- хранение метаданных в `item_images`
- удаление изображения и из Supabase, и из БД
- backend-валидация типа/размера
- frontend-блок загрузки изображений на странице редактирования объявления
- отображение списка загруженных изображений

## Что нужно у тебя перед запуском
В корневом `.env` уже должны быть:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<secret>
SUPABASE_STORAGE_BUCKET=item-images
SUPABASE_STORAGE_PUBLIC_BASE_URL=https://<project-ref>.supabase.co/storage/v1/object/public
```

Bucket `item-images` должен быть public, limit 5 MB, MIME types: jpeg/png/webp.

## Важные замечания
1. Этот пакет предполагает, что в текущем проекте уже есть:
   - `User`, `Item`, `ItemImage` SQLAlchemy models
   - JWT auth и `get_current_user`
   - рабочий CRUD для items из Sprint 2A
2. Если у тебя в проекте уже есть часть этих файлов, **используй этот пакет как overlay** и замени/смерджи только нужные файлы.
3. После замены файлов перезапусти backend и frontend:

```bash
docker compose up --build -d
```

4. Прогони миграцию:

```bash
docker compose exec backend alembic upgrade head
```

## Что проверить
1. Логин
2. Создание объявления
3. Переход в редактирование объявления
4. Загрузка JPEG/PNG/WebP <= 5 MB
5. Отображение картинок в форме
6. Удаление картинки
7. Ошибка при файле > 5 MB
8. Ошибка при неподдерживаемом формате
