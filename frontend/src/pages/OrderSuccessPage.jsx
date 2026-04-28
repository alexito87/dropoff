import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { confirmStripePayment, getOrder } from '../api/orders'

function money(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

export default function OrderSuccessPage() {
  const { orderId } = useParams()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')

  const [order, setOrder] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    async function loadAndConfirmOrder() {
      try {
        setLoading(true)
        setError('')

        let response
        if (sessionId) {
          setSyncing(true)
          response = await confirmStripePayment(orderId, sessionId)
        } else {
          response = await getOrder(orderId)
        }

        setOrder(response)
      } catch (e) {
        setError(e.message)
        try {
          const fallback = await getOrder(orderId)
          setOrder(fallback)
        } catch (_) {
          // keep the original error
        }
      } finally {
        setSyncing(false)
        setLoading(false)
      }
    }

    loadAndConfirmOrder()
  }, [orderId, sessionId])

  if (loading) {
    return (
      <div className="page">
        <div className="card">
          {syncing ? 'Проверяем оплату в Stripe и обновляем заказ...' : 'Загрузка заказа...'}
        </div>
      </div>
    )
  }

  const isPaid = order?.status === 'paid'

  return (
    <div className="page">
      {error && <div className="alert error">{error}</div>}

      {order && (
        <div className="card order-success-card">
          <h1 className="page-title">{isPaid ? 'Заказ оплачен' : 'Заказ ожидает подтверждения оплаты'}</h1>
          <p className="page-subtitle">
            {isPaid
              ? 'Stripe подтвердил оплату. Заказ, платёж и позиции заказа переведены в финальный статус.'
              : 'Оплата ещё не подтверждена. Обнови страницу через несколько секунд или проверь Stripe Dashboard.'}
          </p>

          <div className="summary-row">
            <span>Статус заказа</span>
            <strong>{order.status}</strong>
          </div>
          <div className="summary-row">
            <span>Статус платежа</span>
            <strong>{order.payment?.status || 'нет payment'}</strong>
          </div>
          <div className="summary-row">
            <span>Stripe Checkout Session</span>
            <strong>{order.payment?.stripe_checkout_session_id || order.stripe_checkout_session_id || '—'}</strong>
          </div>
          <div className="summary-row">
            <span>Stripe PaymentIntent</span>
            <strong>{order.payment?.stripe_payment_intent_id || order.stripe_payment_intent_id || '—'}</strong>
          </div>
          <div className="summary-row">
            <span>Итого</span>
            <strong>{money(order.total_amount_cents)}</strong>
          </div>

          <h2>Вещи</h2>
          <div className="checkout-items">
            {order.items.map((item) => (
              <div className="checkout-item-row" key={item.id}>
                <div>
                  <strong>{item.item_title}</strong>
                  <p className="muted">{item.rent_start} — {item.rent_end}</p>
                  <p className="muted">Статус позиции: {item.status}</p>
                </div>
                <strong>{money(item.line_total_cents)}</strong>
              </div>
            ))}
          </div>

          <div className="item-details-actions">
            <Link className="button" to="/catalog">Вернуться в каталог</Link>
          </div>
        </div>
      )}
    </div>
  )
}
