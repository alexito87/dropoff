import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import EmptyState from "../components/common/EmptyState";
import { getCatalogItemDetails } from "../api/catalog";

export default function ItemDetailsPage() {
  const { id } = useParams();

  const [item, setItem] = useState(null);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadItem() {
      try {
        setLoading(true);
        setError("");
        const response = await getCatalogItemDetails(id);
        setItem(response);
        setSelectedImageIndex(0);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }

    loadItem();
  }, [id]);

  if (loading) {
    return (
      <div className="page">
        <div className="card">
          <p>Загрузка карточки объявления...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="alert error">{error}</div>
        <div className="details-back-link-wrap">
          <Link className="button secondary" to="/catalog">
            Назад в каталог
          </Link>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="page">
        <EmptyState
          title="Объявление не найдено"
          description="Возможно, оно больше недоступно в публичном каталоге."
        />
      </div>
    );
  }

  const selectedImage = item.images?.[selectedImageIndex] || null;

  return (
    <div className="page">
      <div className="details-back-link-wrap">
        <Link className="button secondary" to="/catalog">
          Назад в каталог
        </Link>
      </div>

      <div className="item-details-layout">
        <div className="card item-details-gallery-card">
          {selectedImage ? (
            <img
              className="item-details-main-image"
              src={selectedImage.url}
              alt={item.title}
            />
          ) : (
            <div className="item-details-main-image item-details-image-placeholder">
              Нет фото
            </div>
          )}

          {item.images?.length > 1 && (
            <div className="item-details-thumbs">
              {item.images.map((image, index) => (
                <button
                  key={image.id}
                  type="button"
                  className={`item-details-thumb ${index === selectedImageIndex ? "active" : ""}`}
                  onClick={() => setSelectedImageIndex(index)}
                >
                  <img src={image.url} alt={`${item.title} ${index + 1}`} />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card item-details-info-card">
          <div className="item-details-meta muted">
            <span>{item.category_name}</span>
            <span>•</span>
            <span>{item.city}</span>
          </div>

          <h1 className="page-title item-details-title">{item.title}</h1>

          <div className="item-details-pricing">
            <div className="item-details-price-block">
              <span className="muted">Цена аренды</span>
              <strong>{item.daily_price_cents} центов / день</strong>
            </div>
            <div className="item-details-price-block">
              <span className="muted">Депозит</span>
              <strong>{item.deposit_cents} центов</strong>
            </div>
          </div>

          <div className="item-details-section">
            <h2>Описание</h2>
            <p>{item.description}</p>
          </div>

          <div className="item-details-section">
            <h2>Владелец</h2>
            <p>
              {item.owner?.full_name || "Имя не указано"}
              {item.owner?.city ? `, ${item.owner.city}` : ""}
            </p>
          </div>

          <div className="item-details-actions">
            <button className="button" type="button" disabled>
              Запросить аренду — скоро доступно
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}