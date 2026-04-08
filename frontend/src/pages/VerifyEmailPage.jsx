import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiGet } from '../api/client'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function verify() {
      const token = searchParams.get('token')
      if (!token) {
        setStatus('error')
        setMessage('Токен подтверждения не найден')
        return
      }

      try {
        const data = await apiGet(`/api/v1/auth/verify-email?token=${token}`)
        setStatus('success')
        setMessage(data.message)
      } catch (e) {
        setStatus('error')
        setMessage(e.message)
      }
    }

    verify()
  }, [searchParams])

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <h1>Подтверждение email</h1>
        {status === 'loading' && <p>Проверяем токен...</p>}
        {status !== 'loading' && (
          <>
            <div className={`alert ${status === 'success' ? 'success' : 'error'}`}>{message}</div>
            <Link className="button" to="/login">Перейти ко входу</Link>
          </>
        )}
      </div>
    </div>
  )
}
