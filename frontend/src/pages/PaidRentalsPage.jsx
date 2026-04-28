import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import { getMyPaidRentals, getOwnerPaidRentals } from '../api/paidRentals'

function money(cents) {
  return `$${((cents || 0) / 100).toFixed(2)}`
}

function dateRange(item) {
  return `${item.rent_start} — ${item.rent_end}`
}

function OrderCard({ order, mode }) {
  const payment = order.payment

  return (
    <div className="card rental-card paid-rental-card">
      <div className="rental-card-header">
        <div>
          <h3>Заказ #{String(order.id).slice(0, 8)}</h3>
          <p className="muted">
            {mode === 'owner' ? 'Оплаченная бронь на вашу вещь' : 'Ваша оплаченная аренда'}
          </p>
        </div>
        <span className="status-badge status-approved">{order.status}</span>
      </div>

      <div className="rental-card-grid">
        <div>
          <strong>Итого</strong>
          <p>{money(order.total_amount_cents)}</p>
        </div>
        <div>
          <strong>Аренда</strong>
          <p>{money(order.items_total_cents)}</p>
        </div>
        <div>
          <strong>Депозит</strong>
          <p>{money(order.deposit_total_cents)}</p>
        </div>
      </div>

      {payment && (
        <div className="rental-owner-comment">
          <strong>Платёж</strong>
          <p>
            Статус: <b>{payment.status}</b>
          </p>
          <p className="muted">
            Provider: {payment.provider}, method: {payment.payment_method}
          </p>
          {payment.stripe_checkout_session_id && (
            <p className="muted">Stripe Session: {payment.stripe_checkout_session_id}</p>
          )}
          {payment.stripe_payment_intent_id && (
            <p className="muted">Stripe PaymentIntent: {payment.stripe_payment_intent_id}</p>
          )}
        </div>
      )}

      <div className="items-list">
        {order.items.map((item) => (
          <div className="item-row" key={item.id}>
            <div>
              <strong>{item.item_title}</strong>
              <p className="muted">{dateRange(item)}</p>
              <p className="muted">
                Владелец: {item.owner_name || String(item.owner_id).slice(0, 8)}
              </p>
            </div>
            <div>
              <strong>{money(item.line_total_cents)}</strong>
              <p className="muted">Статус: {item.status}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="rental-actions">
        <Link className="button secondary" to={`/orders/${order.id}/success`}>
          Открыть заказ
        </Link>
      </div>
    </div>
  )
}

function PaidRentalsSection({ title, description, orders, mode }) {
  if (!orders.length) {
    return (
      <section className="paid-rentals-section">
        <h2>{title}</h2>
        <EmptyState title="Пока пусто" description={description} />
      </section>
    )
  }

  return (
    <section className="paid-rentals-section">
      <h2>{title}</h2>
      <p className="page-subtitle">{description}</p>
      <div className="items-list">
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} mode={mode} />
        ))}
      </div>
    </section>
  )
}

export default function PaidRentalsPage() {
  const [myRentals, setMyRentals] = useState([])
  const [ownerRentals, setOwnerRentals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadPaidRentals() {
    try {
      setLoading(true)
      setError('')
      const [myResponse, ownerResponse] = await Promise.all([
        getMyPaidRentals(),
        getOwnerPaidRentals(),
      ])
      setMyRentals(myResponse)
      setOwnerRentals(ownerResponse)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPaidRentals()
  }, [])

  const totalCount = useMemo(
    () => myRentals.length + ownerRentals.length,
    [myRentals.length, ownerRentals.length],
  )

  if (loading) {
    return (
      <div className="page">
        <div className="card">
          <p>Загрузка оплаченных аренд...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Оплаченные аренды</h1>
          <p className="page-subtitle">
            Всего найдено: {totalCount}. Здесь отображаются только заказы со статусом paid.
          </p>
        </div>
        <button className="button secondary" type="button" onClick={loadPaidRentals}>
          Обновить
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      <PaidRentalsSection
        title="Я арендую"
        description="Оплаченные заказы, где вы арендатор."
        orders={myRentals}
        mode="renter"
      />

      <PaidRentalsSection
        title="Мои вещи забронировали"
        description="Оплаченные заказы, где в заказе есть ваши вещи."
        orders={ownerRentals}
        mode="owner"
      />
    </div>
  )
}
