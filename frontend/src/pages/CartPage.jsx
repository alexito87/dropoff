import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import { clearCart, getActiveCart, removeCartItem } from '../api/cart'

function money(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

export default function CartPage() {
  const navigate = useNavigate()
  const [cart, setCart] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

  useEffect(() => {
    loadCart()
  }, [])

  async function handleRemove(cartItemId) {
    try {
      setSubmitting(true)
      setError('')
      const response = await removeCartItem(cartItemId)
      setCart(response)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleClear() {
    try {
      setSubmitting(true)
      setError('')
      const response = await clearCart()
      setCart(response)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="card">Загрузка корзины...</div>
      </div>
    )
  }

  const items = cart?.items || []

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Корзина</h1>
          <p className="page-subtitle">Проверь вещи, даты аренды, депозит и итоговую сумму.</p>
        </div>
        <Link className="button secondary" to="/catalog">Вернуться в каталог</Link>
      </div>

      {error && <div className="alert error">{error}</div>}

      {items.length === 0 ? (
        <EmptyState
          title="Корзина пустая"
          description="Открой каталог, выбери вещь и даты аренды."
        />
      ) : (
        <div className="cart-layout">
          <div className="cart-items-list">
            {items.map((item) => (
              <div className="card cart-item-card" key={item.id}>
                <div className="cart-item-image-wrap">
                  {item.image_url ? (
                    <img className="cart-item-image" src={item.image_url} alt={item.item_title} />
                  ) : (
                    <div className="cart-item-image-placeholder">Нет фото</div>
                  )}
                </div>

                <div className="cart-item-body">
                  <h3>{item.item_title}</h3>
                  <p className="muted">
                    {item.rent_start} — {item.rent_end}, {item.days_count} дн.
                  </p>
                  <p className="muted">Владелец: {item.owner_name || 'не указан'}</p>

                  <div className="cart-item-prices">
                    <span>Аренда: <strong>{money(item.rent_total_cents)}</strong></span>
                    <span>Депозит: <strong>{money(item.total_deposit_cents)}</strong></span>
                    <span>Итого по позиции: <strong>{money(item.line_total_cents)}</strong></span>
                  </div>
                </div>

                <button
                  className="button danger"
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRemove(item.id)}
                >
                  Удалить
                </button>
              </div>
            ))}
          </div>

          <aside className="card cart-summary-card">
            <h2>Итого</h2>
            <div className="summary-row">
              <span>Количество вещей</span>
              <strong>{cart.items_count}</strong>
            </div>
            <div className="summary-row">
              <span>Аренда</span>
              <strong>{money(cart.items_total_cents)}</strong>
            </div>
            <div className="summary-row">
              <span>Депозит</span>
              <strong>{money(cart.deposit_total_cents)}</strong>
            </div>
            <div className="summary-row total">
              <span>К оплате без доставки</span>
              <strong>{money(cart.payable_total_cents)}</strong>
            </div>

            <button className="button" type="button" onClick={() => navigate('/checkout')}>
              Оформить заказ
            </button>
            <button
              className="button secondary"
              type="button"
              disabled={submitting}
              onClick={handleClear}
            >
              Очистить корзину
            </button>
          </aside>
        </div>
      )}
    </div>
  )
}
