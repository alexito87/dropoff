import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import { getCatalogItemDetails } from '../api/catalog'
import { createRental } from '../api/rentals'
import { useAuth } from '../state/AuthContext'

function formatDateInput(value) {
  return value || ''
}

export default function ItemDetailsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuth()

  const [item, setItem] = useState(null)
  const [selectedImageIndex, setSelectedImageIndex] = useState(0)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadItem() {
      try {
        setLoading(true)
        setError('')
        const response = await getCatalogItemDetails(id)
        setItem(response)
        setSelectedImageIndex(0)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }

    loadItem()
  }, [id])

  const selectedImage = item?.images?.[selectedImageIndex] || null

  const rentalSummary = useMemo(() => {
    if (!startDate || !endDate || !item) {
      return null
    }

    const start = new Date(startDate)
    const end = new Date(endDate)

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
      return null
    }

    const diffMs = end.getTime() - start.getTime()
    const daysCount = Math.floor(diffMs / (1000 * 60 * 60 * 24)) + 1
    const rentalCost = daysCount * item.daily_price_cents

    return {
      daysCount,
      rentalCost,
      depositCents: item.deposit_cents,
      totalEstimateCents: rentalCost,
    }
  }, [startDate, endDate, item])

  async function handleSubmitRental(event) {
    event.preventDefault()

    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    try {
      setSubmitting(true)
      setError('')
      setSuccessMessage('')

      await createRental({
        item_id: item.id,
        start_date: startDate,
        end_date: endDate,
      })

      setSuccessMessage('Заявка на аренду отправлена владельцу.')
      setStartDate('')
      setEndDate('')
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="card">
          <p>Загрузка карточки объявления...</p>
        </div>
      </div>
    )
  }

  if (error && !item) {
    return (
      <div className="page">
        <div className="alert error">{error}</div>
        <div className="details-back-link-wrap">
          <Link className="button secondary" to="/catalog">
            Назад в каталог
          </Link>
        </div>
      </div>
    )
  }

  if (!item) {
    return (
      <div className="page">
        <EmptyState
          title="Объявление не найдено"
          description="Возможно, оно больше недоступно в публичном каталоге."
        />
      </div>
    )
  }

  const isOwnItem = user?.id && item.owner?.id && user.id === item.owner.id

  return (
    <div className="page">
      <div className="details-back-link-wrap">
        <Link className="button secondary" to="/catalog">
          Назад в каталог
        </Link>
      </div>

      {error && <div className="alert error">{error}</div>}
      {successMessage && <div className="alert success">{successMessage}</div>}

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
                  className={`item-details-thumb ${index === selectedImageIndex ? 'active' : ''}`}
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
              {item.owner?.full_name || 'Имя не указано'}
              {item.owner?.city ? `, ${item.owner.city}` : ''}
            </p>
          </div>

          <div className="item-details-section">
            <h2>Заявка на аренду</h2>

            {!isAuthenticated ? (
              <div className="rental-cta-unauth">
                <p className="muted">Чтобы отправить заявку, сначала войди в систему.</p>
                <Link className="button" to="/login">
                  Войти, чтобы арендовать
                </Link>
              </div>
            ) : isOwnItem ? (
              <div className="alert error">
                Нельзя отправить заявку на собственное объявление.
              </div>
            ) : (
              <form className="rental-request-form" onSubmit={handleSubmitRental}>
                <div className="form-grid-two">
                  <label>
                    Дата начала
                    <input
                      type="date"
                      value={formatDateInput(startDate)}
                      onChange={(event) => setStartDate(event.target.value)}
                      required
                    />
                  </label>

                  <label>
                    Дата конца
                    <input
                      type="date"
                      value={formatDateInput(endDate)}
                      onChange={(event) => setEndDate(event.target.value)}
                      required
                    />
                  </label>
                </div>

                <div className="rental-summary card">
                  {rentalSummary ? (
                    <>
                      <div className="rental-summary-row">
                        <span>Дней аренды</span>
                        <strong>{rentalSummary.daysCount}</strong>
                      </div>
                      <div className="rental-summary-row">
                        <span>Аренда</span>
                        <strong>{rentalSummary.rentalCost} центов</strong>
                      </div>
                      <div className="rental-summary-row">
                        <span>Депозит</span>
                        <strong>{rentalSummary.depositCents} центов</strong>
                      </div>
                      <div className="rental-summary-row">
                        <span>Итого без депозита</span>
                        <strong>{rentalSummary.totalEstimateCents} центов</strong>
                      </div>
                    </>
                  ) : (
                    <p className="muted">Выбери корректные даты, чтобы увидеть расчет.</p>
                  )}
                </div>

                <div className="item-details-actions">
                  <button className="button" type="submit" disabled={submitting}>
                    {submitting ? 'Отправка...' : 'Отправить заявку'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}