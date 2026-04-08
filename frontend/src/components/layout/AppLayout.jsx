import Header from './Header'
import Sidebar from './Sidebar'

export default function AppLayout({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-shell">
        <Header />
        <main className="page-content">{children}</main>
      </div>
    </div>
  )
}
