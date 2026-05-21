import { apiDelete, apiGet, apiPost } from './client'

export function getActiveCart() {
  return apiGet('/api/v1/cart', true)
}

export function addCartItem(payload) {
  return apiPost('/api/v1/cart/items', payload, true)
}

export function removeCartItem(cartItemId) {
  return apiDelete(`/api/v1/cart/items/${cartItemId}`, true)
}

export function clearCart() {
  return apiDelete('/api/v1/cart', true)
}

export function requestCartCheckout(payload) {
  return apiPost('/api/v1/cart/checkout-request', payload, true)
}

export function getCartCheckoutStatus(cartId) {
  return apiGet(`/api/v1/cart/checkout-status?cart_id=${encodeURIComponent(cartId)}`, true)
}