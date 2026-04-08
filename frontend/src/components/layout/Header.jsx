import { Link } from 'react-router-dom'
import { useAuth } from '../../state/AuthContext'

export default function Header() {
  const { user, isAuthenticated, logout } = useAuth()

  return (
    <header className="topbar">
      <div>
        <strong>dropoff</strong>
      </div>
      <div className="topbar-actions">
        {isAuthenticated ? (
          <>
            <span>{user?.email}</span>
            <Link className="button ghost" to="/profile">Профиль</Link>
            <button className="button" onClick={logout}>Выйти</button>
          </>
        ) : (
          <>
            <Link className="button ghost" to="/login">Войти</Link>
            <Link className="button" to="/signup">Регистрация</Link>
          </>
        )}
      </div>
    </header>
  )
}
