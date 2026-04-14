import { useEffect, useState } from 'react'
import EmptyState from '../components/common/EmptyState'
import { approveRental, getOwnerRentals, rejectRental } from '../api/rentals'

export default function OwnerRentalRequestsPage() {
  const [rentals, setRentals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoadingId, setActionLoadingId] = useState('')

  async function loadRentals() {
    try {
      setLoading(true)
      setError('')
      const data = await getOwnerRentals()
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

  async function handleApprove(rentalId) {
    try {
      setActionLoadingId(rentalId)
      await approveRental(rentalId)
      await loadRentals()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionLoadingId('')
    }
  }

  async function handleReject(rentalId) {
    const ownerComment = window.prompt('Комментарий владельца (необязательно):') || ''

    try {
      setActionLoadingId(rentalId)
      await rejectRental(rentalId, { owner_comment: ownerComment })
      await loadRentals()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionLoadingId('')
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Заявки на мои вещи</h1>
      <p className="page-subtitle">Здесь отображаются входящие заявки от арендаторов.</p>

      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <div className="card">Загрузка заявок...</div>
      ) : rentals.length === 0 ? (
        <EmptyState
          title="Пока нет входящих заявок"
          description="Когда арендаторы начнут отправлять заявки на твои объявления, они появятся здесь."
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
                  <span className="muted">Арендатор</span>
                  <div>{rental.renter_name || 'Не указано'}</div>
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
                    className="button"
                    type="button"
                    disabled={actionLoadingId === rental.id}
                    onClick={() => handleApprove(rental.id)}
                  >
                    {actionLoadingId === rental.id ? 'Подтверждение...' : 'Подтвердить'}
                  </button>

                  <button
                    className="button secondary"
                    type="button"
                    disabled={actionLoadingId === rental.id}
                    onClick={() => handleReject(rental.id)}
                  >
                    {actionLoadingId === rental.id ? 'Отклонение...' : 'Отклонить'}
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