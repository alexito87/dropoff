import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiPost } from '../api/client'

export default function SignupPage() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setMessage('')
    setError('')
    setLoading(true)

    try {
      const data = await apiPost('/api/v1/auth/signup', form)
      setMessage(`${data.message} Открой Mailpit на localhost:8025.`)
      setForm({ email: '', password: '' })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <h1>Регистрация</h1>
        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
            required
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            minLength={8}
            value={form.password}
            onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
            required
          />
        </label>
        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}
        <button className="button" disabled={loading}>{loading ? 'Создаём...' : 'Создать аккаунт'}</button>
        <p>Уже есть аккаунт? <Link to="/login">Войти</Link></p>
      </form>
    </div>
  )
}
