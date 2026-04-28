
import { Link } from 'react-router-dom'
import { useAuth } from '../../state/AuthContext'

export default function Sidebar() {
  const { user, isAuthenticated } = useAuth()

  return (
    <aside className="sidebar">
      <h2>Навигация</h2>

      <nav className="nav-list">
        <Link to="/">Каталог</Link>

        {isAuthenticated && (
          <>
            <Link to="/profile">Профиль</Link>
            <Link to="/my-items">Мои объявления</Link>
            <Link to="/rentals/me">Мои заявки</Link>
            <Link to="/rentals/owner">Заявки на мои вещи</Link>
            <Link to="/paid-rentals">Оплаченные аренды</Link>
            <Link to="/notifications">Уведомления</Link>
          </>
        )}

        {user?.is_superuser && <Link to="/admin/moderation">Модерация</Link>}
      </nav>
    </aside>
  )
}
