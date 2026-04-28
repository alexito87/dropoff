import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import { getActiveCart } from '../api/cart'
import { createCheckoutSession, createOrder } from '../api/orders'

function money(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

const DELIVERY_OPTIONS = [
  { code: 'pickup', title: 'Самовывоз', description: 'Забрать вещь у владельца', fee: 0 },
  { code: 'courier_standard', title: 'Стандартная доставка', description: 'Учебный тариф доставки для MVP', fee: 1200 },
]

export default function CheckoutPage() {
  const navigate = useNavigate()
  const [cart, setCart] = useState(null)
  const [deliveryMethod, setDeliveryMethod] = useState('pickup')
  const [paymentMethod, setPaymentMethod] = useState('stripe_checkout')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadCart() {
      try {
        setLoading(true)
        setError('')
        const response = await getActiveCart()
        setCart(response)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }

    loadCart()
  }, [])

  const deliveryFee = useMemo(() => {
    return DELIVERY_OPTIONS.find((option) => option.code === deliveryMethod)?.fee || 0
  }, [deliveryMethod])

  const total = (cart?.payable_total_cents || 0) + deliveryFee

  async function handleConfirmOrder(event) {
    event.preventDefault()

    try {
      setSubmitting(true)
      setError('')

      const order = await createOrder({
        delivery_method: deliveryMethod,
        payment_method: paymentMethod,
      })

      const checkout = await createCheckoutSession(order.id)
      window.location.href = checkout.checkout_url
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="card">Загрузка заказа...</div>
      </div>
    )
  }

  const items = cart?.items || []

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Оформление заказа</h1>
          <p className="page-subtitle">Выбери доставку и способ оплаты.</p>
        </div>
        <Link className="button secondary" to="/cart">Вернуться в корзину</Link>
      </div>

      {error && <div className="alert error">{error}</div>}

      {items.length === 0 ? (
        <EmptyState
          title="Корзина пустая"
          description="Добавь вещи в корзину перед оформлением заказа."
        />
      ) : (
        <form className="checkout-layout" onSubmit={handleConfirmOrder}>
          <div className="checkout-main">
            <section className="card">
              <h2>Итоговый платёж</h2>
              <div className="checkout-items">
                {items.map((item) => (
                  <div className="checkout-item-row" key={item.id}>
                    <div>
                      <strong>{item.item_title}</strong>
                      <p className="muted">{item.rent_start} — {item.rent_end}, {item.days_count} дн.</p>
                    </div>
                    <strong>{money(item.line_total_cents)}</strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="card">
              <h2>Метод доставки</h2>
              <div className="choice-stack">
                {DELIVERY_OPTIONS.map((option) => (
                  <label className="choice-card" key={option.code}>
                    <input
                      type="radio"
                      name="delivery_method"
                      value={option.code}
                      checked={deliveryMethod === option.code}
                      onChange={(event) => setDeliveryMethod(event.target.value)}
                    />
                    <span>
                      <strong>{option.title}</strong>
                      <small>{option.description}</small>
                    </span>
                    <strong>{money(option.fee)}</strong>
                  </label>
                ))}
              </div>
            </section>

            <section className="card">
              <h2>Платёж</h2>
              <label className="choice-card">
                <input
                  type="radio"
                  name="payment_method"
                  value="stripe_checkout"
                  checked={paymentMethod === 'stripe_checkout'}
                  onChange={(event) => setPaymentMethod(event.target.value)}
                />
                <span>
                  <strong>Stripe Checkout</strong>
                  <small>Тестовая оплата через Stripe Sandbox</small>
                </span>
              </label>
            </section>
          </div>

          <aside className="card checkout-summary-card">
            <h2>Сумма</h2>
            <div className="summary-row">
              <span>Аренда</span>
              <strong>{money(cart.items_total_cents)}</strong>
            </div>
            <div className="summary-row">
              <span>Депозит</span>
              <strong>{money(cart.deposit_total_cents)}</strong>
            </div>
            <div className="summary-row">
              <span>Доставка</span>
              <strong>{money(deliveryFee)}</strong>
            </div>
            <div className="summary-row total">
              <span>Итого к оплате</span>
              <strong>{money(total)}</strong>
            </div>

            <button className="button" type="submit" disabled={submitting}>
              {submitting ? 'Создаём заказ...' : 'Подтвердить заказ'}
            </button>
          </aside>
        </form>
      )}
    </div>
  )
}
