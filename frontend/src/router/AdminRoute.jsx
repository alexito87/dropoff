import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../state/AuthContext'

export default function AdminRoute({ children }) {
  const { isAuthenticated, loading, user } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="page">
        <div className="card">Загрузка...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (!user?.is_superuser) {
    return <Navigate to="/" replace />
  }

  return children
}