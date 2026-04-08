import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './router/ProtectedRoute'
import CatalogPage from './pages/CatalogPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import ProfilePage from './pages/ProfilePage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import PlaceholderPage from './pages/PlaceholderPage'
import MyItemsPage from './pages/MyItemsPage'
import ItemFormPage from './pages/ItemFormPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />

      <Route
        path="/"
        element={
          <AppLayout>
            <CatalogPage />
          </AppLayout>
        }
      />

      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <AppLayout>
              <ProfilePage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/my-items"
        element={
          <ProtectedRoute>
            <AppLayout>
              <MyItemsPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/my-items/new"
        element={
          <ProtectedRoute>
            <AppLayout>
              <ItemFormPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/my-items/:itemId/edit"
        element={
          <ProtectedRoute>
            <AppLayout>
              <ItemFormPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/moderation"
        element={
          <ProtectedRoute>
            <AppLayout>
              <PlaceholderPage title="Модерация" />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
