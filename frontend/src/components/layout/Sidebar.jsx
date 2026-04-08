
import { Link } from 'react-router-dom'

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <h2>Навигация</h2>
      <nav className="nav-list">
        <Link to="/">Каталог</Link>
        <Link to="/profile">Профиль</Link>
        <Link to="/my-items">Мои объявления</Link>
        <Link to="/admin/moderation">Модерация</Link>
      </nav>
    </aside>
  )
}
