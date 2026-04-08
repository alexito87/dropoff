import { useState } from 'react'
import { apiPatch, apiPost } from '../api/client'
import { useAuth } from '../state/AuthContext'

export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    phone: user?.phone || '',
    city: user?.city || ''
  })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function handleSave(event) {
    event.preventDefault()
    setMessage('')
    setError('')
    try {
      await apiPatch('/api/v1/users/me', form, true)
      await refreshUser()
      setMessage('Профиль сохранён')
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleResendVerification() {
    setMessage('')
    setError('')
    try {
      const data = await apiPost('/api/v1/auth/resend-verification', {}, true)
      setMessage(`${data.message}. Проверь Mailpit на localhost:8025.`)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <h1>Профиль</h1>
      <div className="card">
        <p><strong>Email:</strong> {user?.email}</p>
        <p>
          <strong>Email подтверждён:</strong>{' '}
          {user?.email_verified ? 'Да' : 'Нет'}
        </p>
        {!user?.email_verified && (
          <button className="button ghost" onClick={handleResendVerification}>
            Отправить письмо повторно
          </button>
        )}
      </div>

      <form className="card form-card" onSubmit={handleSave}>
        <label>
          Полное имя
          <input
            value={form.full_name}
            onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))}
          />
        </label>
        <label>
          Телефон
          <input
            value={form.phone}
            onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))}
          />
        </label>
        <label>
          Город
          <input
            value={form.city}
            onChange={(e) => setForm((prev) => ({ ...prev, city: e.target.value }))}
          />
        </label>
        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}
        <button className="button">Сохранить профиль</button>
      </form>
    </div>
  )
}
