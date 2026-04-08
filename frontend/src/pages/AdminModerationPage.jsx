import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'

export default function AdminModerationPage() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [comments, setComments] = useState({})

  useEffect(() => {
    apiGet('/api/v1/admin/moderation/items', true)
      .then(setItems)
      .catch((e) => setError(e.message))
  }, [])

  function updateComment(itemId, value) {
    setComments((prev) => ({ ...prev, [itemId]: value }))
  }

  async function moderate(itemId, action) {
    try {
      const payload = {
        comment: comments[itemId] || null,
      }

      const updated = await apiPost(`/api/v1/admin/moderation/items/${itemId}/${action}`, payload, true)

      setItems((prev) => prev.filter((item) => item.id !== updated.id))
      setComments((prev) => {
        const next = { ...prev }
        delete next[itemId]
        return next
      })
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <h1>Модерация объявлений</h1>

      {error && <div className="alert error">{error}</div>}

      {!items.length && <div className="card">Нет объявлений на модерации</div>}

      <div className="item-list">
        {items.map((item) => (
          <div className="card" key={item.id}>
            <h3>{item.title}</h3>
            <p className="muted">{item.description}</p>
            <p className="muted">Город: {item.city}</p>
            <p className="muted">Цена/день: {item.daily_price_cents}</p>
            <p className="muted">Депозит: {item.deposit_cents}</p>

            <div className="image-grid">
              {(item.images || []).map((image) => (
                <div className="image-card" key={image.id}>
                  <img src={image.url} alt="Изображение объявления" />
                </div>
              ))}
            </div>

            <label>
              Комментарий модератора
              <textarea
                rows={4}
                value={comments[item.id] || ''}
                onChange={(e) => updateComment(item.id, e.target.value)}
              />
            </label>

            <div className="item-row-actions">
              <button className="button" type="button" onClick={() => moderate(item.id, 'approve')}>
                Одобрить
              </button>
              <button className="button ghost" type="button" onClick={() => moderate(item.id, 'needs-changes')}>
                На доработку
              </button>
              <button className="button danger" type="button" onClick={() => moderate(item.id, 'reject')}>
                Отклонить
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}