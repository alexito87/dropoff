import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "../components/layout/AppLayout";
import AdminModerationPage from "../pages/AdminModerationPage";
import CatalogPage from "../pages/CatalogPage";
import HomePage from "../pages/HomePage";
import ItemDetailsPage from "../pages/ItemDetailsPage";
import LoginPage from "../pages/LoginPage";
import MyItemsPage from "../pages/MyItemsPage";
import ProfilePage from "../pages/ProfilePage";
import SignupPage from "../pages/SignupPage";

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/my-items" element={<MyItemsPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/items/:id" element={<ItemDetailsPage />} />
        <Route path="/admin/moderation" element={<AdminModerationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
