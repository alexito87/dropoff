export default function HomePage() {
  return (
    <section className="stack">
      <div className="card">
        <h2>Спринт 0 готовит каркас проекта</h2>
        <p>
          Здесь пока нет бизнес-функций. Цель этапа — запустить frontend, backend,
          PostgreSQL, миграции и базовый справочник категорий.
        </p>
      </div>

      <div className="card">
        <h3>Что проверить после запуска</h3>
        <ol>
          <li>Открывается frontend на localhost:3000.</li>
          <li>Открывается Swagger на localhost:8000/docs.</li>
          <li>Работает GET /api/v1/health-check.</li>
          <li>После миграции и seed работает GET /api/v1/categories.</li>
        </ol>
      </div>
    </section>
  );
}
