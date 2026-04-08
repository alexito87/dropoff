import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiDelete, apiGet } from '../api/client'

export default function MyItemsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiGet('/api/v1/items/my', true)
      .then(setItems)
      .catch((e) => setError(e.message))
  }, [])

  async function handleDelete(itemId) {
    try {
      await apiDelete(`/api/v1/items/${itemId}`, true)
      setItems((prev) => prev.filter((item) => item.id !== itemId))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <div className="page-header-row">
        <h1>Мои объявления</h1>
        <button className="button" type="button" onClick={() => navigate('/my-items/new')}>
          Создать объявление
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="item-list">
        {items.map((item) => (
          <div className="card item-row" key={item.id}>
            <div>
              <h3>{item.title}</h3>
              <p className="muted">Статус: {item.status}</p>
              <p className="muted">Изображений: {item.images?.length || 0}</p>
              {item.moderation_comment && (
                <p className="muted">Комментарий модератора: {item.moderation_comment}</p>
              )}
            </div>

            <div className="item-row-actions">
              {(item.status === 'draft' || item.status === 'rejected') && (
                <>
                  <Link className="button ghost" to={`/my-items/${item.id}/edit`}>
                    Редактировать
                  </Link>
                  <button
                    className="button danger"
                    type="button"
                    onClick={() => handleDelete(item.id)}
                  >
                    Удалить
                  </button>
                </>
              )}

              {item.status === 'pending_review' && (
                <div className="muted">Объявление на проверке</div>
              )}

              {item.status === 'published' && (
                <div className="muted">Объявление опубликовано</div>
              )}
            </div>
          </div>
        ))}

        {!items.length && <div className="card">У тебя пока нет объявлений</div>}
      </div>
    </div>
  )
}