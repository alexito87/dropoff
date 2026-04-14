import { useEffect, useState } from 'react'
import EmptyState from '../components/common/EmptyState'
import { cancelRental, getMyRentals } from '../api/rentals'

export default function MyRentalRequestsPage() {
  const [rentals, setRentals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoadingId, setActionLoadingId] = useState('')

  async function loadRentals() {
    try {
      setLoading(true)
      setError('')
      const data = await getMyRentals()
      setRentals(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRentals()
  }, [])

  async function handleCancel(rentalId) {
    try {
      setActionLoadingId(rentalId)
      await cancelRental(rentalId)
      await loadRentals()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionLoadingId('')
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Мои заявки</h1>
      <p className="page-subtitle">Здесь отображаются заявки, которые ты отправил как арендатор.</p>

      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <div className="card">Загрузка заявок...</div>
      ) : rentals.length === 0 ? (
        <EmptyState
          title="Пока нет заявок"
          description="Открой карточку вещи в каталоге и отправь первую заявку на аренду."
        />
      ) : (
        <div className="items-list">
          {rentals.map((rental) => (
            <div className="card rental-card" key={rental.id}>
              <div className="rental-card-header">
                <div>
                  <h3>{rental.item_title}</h3>
                  <p className="muted">
                    {rental.start_date} — {rental.end_date}
                  </p>
                </div>
                <span className={`status-badge status-${rental.status}`}>{rental.status}</span>
              </div>

              <div className="rental-card-grid">
                <div>
                  <span className="muted">Владелец</span>
                  <div>{rental.owner_name || 'Не указано'}</div>
                </div>
                <div>
                  <span className="muted">Сумма аренды</span>
                  <div>{rental.total_estimate_cents} центов</div>
                </div>
                <div>
                  <span className="muted">Депозит</span>
                  <div>{rental.deposit_cents} центов</div>
                </div>
              </div>

              {rental.owner_comment && (
                <div className="rental-owner-comment">
                  <span className="muted">Комментарий владельца</span>
                  <p>{rental.owner_comment}</p>
                </div>
              )}

              {rental.status === 'pending' && (
                <div className="rental-actions">
                  <button
                    className="button danger"
                    type="button"
                    disabled={actionLoadingId === rental.id}
                    onClick={() => handleCancel(rental.id)}
                  >
                    {actionLoadingId === rental.id ? 'Отмена...' : 'Отменить заявку'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}