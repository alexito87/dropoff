import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiGet('/api/v1/notifications/me', true)
      .then(setNotifications)
      .catch((e) => setError(e.message))
  }, [])

  async function markAsRead(notificationId) {
    try {
      const updated = await apiPost(`/api/v1/notifications/${notificationId}/read`, {}, true)
      setNotifications((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      )
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <h1>Уведомления</h1>

      {error && <div className="alert error">{error}</div>}

      {!notifications.length && <div className="card">Уведомлений пока нет</div>}

      <div className="item-list">
        {notifications.map((notification) => (
          <div className="card" key={notification.id}>
            <p><strong>Тип:</strong> {notification.type}</p>
            <p className="muted">
              Создано: {new Date(notification.created_at).toLocaleString()}
            </p>

            {notification.payload?.title && (
              <p><strong>Объявление:</strong> {notification.payload.title}</p>
            )}

            {notification.payload?.status && (
              <p><strong>Статус:</strong> {notification.payload.status}</p>
            )}

            {notification.payload?.comment && (
              <p><strong>Комментарий:</strong> {notification.payload.comment}</p>
            )}

            {!notification.is_read && (
              <button className="button" type="button" onClick={() => markAsRead(notification.id)}>
                Отметить как прочитанное
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}