import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { sandboxPayOrder } from '../api/orders'

export default function SandboxPaymentPage() {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handlePay() {
    try {
      setSubmitting(true)
      setError('')
      await sandboxPayOrder(orderId)
      navigate(`/orders/${orderId}/success`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="card sandbox-payment-card">
        <h1 className="page-title">Stripe Sandbox</h1>
        <p className="page-subtitle">
          Это временная страница-имитация. В следующем паке заменим её на настоящий Stripe Checkout.
        </p>

        {error && <div className="alert error">{error}</div>}

        <div className="sandbox-box">
          <p>Заказ: <strong>{orderId}</strong></p>
          <p className="muted">Нажатие кнопки переведёт заказ в статус paid.</p>
        </div>

        <div className="item-details-actions">
          <button className="button" type="button" disabled={submitting} onClick={handlePay}>
            {submitting ? 'Оплата...' : 'Оплатить тестово'}
          </button>
          <Link className="button secondary" to="/cart">Вернуться в корзину</Link>
        </div>
      </div>
    </div>
  )
}
