import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '../components/layout/AppLayout'
import ProtectedRoute from './ProtectedRoute'
import AdminRoute from './AdminRoute'
import CatalogPage from '../pages/CatalogPage'
import LoginPage from '../pages/LoginPage'
import SignupPage from '../pages/SignupPage'
import ProfilePage from '../pages/ProfilePage'
import VerifyEmailPage from '../pages/VerifyEmailPage'
import MyItemsPage from '../pages/MyItemsPage'
import ItemFormPage from '../pages/ItemFormPage'
import AdminModerationPage from '../pages/AdminModerationPage'
import NotificationsPage from '../pages/NotificationsPage'
import ItemDetailsPage from '../pages/ItemDetailsPage'
import MyRentalRequestsPage from '../pages/MyRentalRequestsPage'
import OwnerRentalRequestsPage from '../pages/OwnerRentalRequestsPage'

export default function AppRouter() {
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
        path="/catalog"
        element={
          <AppLayout>
            <CatalogPage />
          </AppLayout>
        }
      />

      <Route
        path="/items/:id"
        element={
          <AppLayout>
            <ItemDetailsPage />
          </AppLayout>
        }
      />

      <Route
        path="/rentals/me"
        element={
          <ProtectedRoute>
            <AppLayout>
              <MyRentalRequestsPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/rentals/owner"
        element={
          <ProtectedRoute>
            <AppLayout>
              <OwnerRentalRequestsPage />
            </AppLayout>
          </ProtectedRoute>
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
        path="/notifications"
        element={
          <ProtectedRoute>
            <AppLayout>
              <NotificationsPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/moderation"
        element={
          <AdminRoute>
            <AppLayout>
              <AdminModerationPage />
            </AppLayout>
          </AdminRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}