import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EmptyState from "../components/common/EmptyState";
import { getCatalogItems } from "../api/catalog";
import { apiGet } from "../api/client";

const DEFAULT_FILTERS = {
  city: "",
  category_id: "",
  price_from: "",
  price_to: "",
  sort: "newest",
};

export default function CatalogPage() {
  const [categories, setCategories] = useState([]);
  const [itemsResponse, setItemsResponse] = useState({
    items: [],
    page: 1,
    page_size: 12,
    total: 0,
    pages: 1,
  });
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [error, setError] = useState("");

  const activePage = itemsResponse.page;

  useEffect(() => {
    async function loadCategories() {
      try {
        setCategoriesLoading(true);
        const data = await apiGet("/api/v1/categories");
        setCategories(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setCategoriesLoading(false);
      }
    }

    loadCategories();
  }, []);

  useEffect(() => {
    async function loadCatalog() {
      try {
        setLoading(true);
        setError("");

        const response = await getCatalogItems({
          ...appliedFilters,
          page: activePage,
          page_size: itemsResponse.page_size,
        });

        setItemsResponse(response);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }

    loadCatalog();
  }, [appliedFilters, activePage, itemsResponse.page_size]);

  function updateFilter(name, value) {
    setFilters((prev) => ({
      ...prev,
      [name]: value,
    }));
  }

  function applyFilters(event) {
    event.preventDefault();
    setItemsResponse((prev) => ({
      ...prev,
      page: 1,
    }));
    setAppliedFilters(filters);
  }

  function resetFilters() {
    setFilters(DEFAULT_FILTERS);
    setAppliedFilters(DEFAULT_FILTERS);
    setItemsResponse((prev) => ({
      ...prev,
      page: 1,
    }));
  }

  function goToPage(page) {
    setItemsResponse((prev) => ({
      ...prev,
      page,
    }));
  }

  const hasItems = itemsResponse.items.length > 0;

  const pageNumbers = useMemo(() => {
    return Array.from({ length: itemsResponse.pages }, (_, index) => index + 1);
  }, [itemsResponse.pages]);

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Каталог</h1>
          <p className="page-subtitle">
            Публичная витрина опубликованных объявлений.
          </p>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="card catalog-filters-card">
        <form className="catalog-filters-form" onSubmit={applyFilters}>
          <div className="catalog-filters-grid">
            <label>
              Город
              <input
                type="text"
                placeholder="Например, Minsk"
                value={filters.city}
                onChange={(event) => updateFilter("city", event.target.value)}
              />
            </label>

            <label>
              Категория
              <select
                value={filters.category_id}
                onChange={(event) => updateFilter("category_id", event.target.value)}
                disabled={categoriesLoading}
              >
                <option value="">Все категории</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Цена от, центов/день
              <input
                type="number"
                min="0"
                placeholder="0"
                value={filters.price_from}
                onChange={(event) => updateFilter("price_from", event.target.value)}
              />
            </label>

            <label>
              Цена до, центов/день
              <input
                type="number"
                min="0"
                placeholder="5000"
                value={filters.price_to}
                onChange={(event) => updateFilter("price_to", event.target.value)}
              />
            </label>

            <label>
              Сортировка
              <select
                value={filters.sort}
                onChange={(event) => updateFilter("sort", event.target.value)}
              >
                <option value="newest">Сначала новые</option>
                <option value="price_asc">Сначала дешевле</option>
                <option value="price_desc">Сначала дороже</option>
              </select>
            </label>
          </div>

          <div className="catalog-filters-actions">
            <button className="button" type="submit">
              Применить
            </button>
            <button className="button secondary" type="button" onClick={resetFilters}>
              Сбросить
            </button>
          </div>
        </form>
      </div>

      <div className="catalog-summary muted">
        {loading
          ? "Загрузка объявлений..."
          : `Найдено объявлений: ${itemsResponse.total}`}
      </div>

      {loading ? (
        <div className="card">
          <p>Загрузка каталога...</p>
        </div>
      ) : hasItems ? (
        <>
          <div className="catalog-grid">
            {itemsResponse.items.map((item) => (
              <article className="catalog-card card" key={item.id}>
                <div className="catalog-card-image-wrap">
                  {item.preview_image_url ? (
                    <img
                      className="catalog-card-image"
                      src={item.preview_image_url}
                      alt={item.title}
                    />
                  ) : (
                    <div className="catalog-card-image catalog-card-image-placeholder">
                      Нет фото
                    </div>
                  )}
                </div>

                <div className="catalog-card-body">
                  <div className="catalog-card-meta muted">
                    <span>{item.category_name}</span>
                    <span>•</span>
                    <span>{item.city}</span>
                  </div>

                  <h2 className="catalog-card-title">
                    <Link to={`/items/${item.id}`}>{item.title}</Link>
                  </h2>

                  <div className="catalog-card-price">
                    {item.daily_price_cents} центов / день
                  </div>

                  <div className="catalog-card-deposit muted">
                    Депозит: {item.deposit_cents} центов
                  </div>

                  <Link className="button secondary catalog-card-link" to={`/items/${item.id}`}>
                    Подробнее
                  </Link>
                </div>
              </article>
            ))}
          </div>

          {itemsResponse.pages > 1 && (
            <div className="pagination">
              <button
                className="button secondary"
                type="button"
                disabled={activePage === 1}
                onClick={() => goToPage(activePage - 1)}
              >
                Назад
              </button>

              <div className="pagination-pages">
                {pageNumbers.map((pageNumber) => (
                  <button
                    key={pageNumber}
                    type="button"
                    className={`pagination-page ${pageNumber === activePage ? "active" : ""}`}
                    onClick={() => goToPage(pageNumber)}
                  >
                    {pageNumber}
                  </button>
                ))}
              </div>

              <button
                className="button secondary"
                type="button"
                disabled={activePage === itemsResponse.pages}
                onClick={() => goToPage(activePage + 1)}
              >
                Вперед
              </button>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          title="Ничего не найдено"
          description="Попробуй изменить фильтры или очистить их."
        />
      )}
    </div>
  );
}