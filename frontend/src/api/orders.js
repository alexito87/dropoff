import { apiGet, apiPost } from './client'

export function createOrder(payload) {
  return apiPost('/api/v1/orders', payload, true)
}

export function getOrder(orderId) {
  return apiGet(`/api/v1/orders/${orderId}`, true)
}

export function createCheckoutSession(orderId) {
  return apiPost(`/api/v1/orders/${orderId}/checkout-session`, {}, true)
}

export function confirmStripePayment(orderId, stripeCheckoutSessionId) {
  return apiPost(
    `/api/v1/orders/${orderId}/stripe/confirm`,
    { stripe_checkout_session_id: stripeCheckoutSessionId },
    true,
  )
}

export function sandboxPayOrder(orderId) {
  return apiPost(`/api/v1/orders/${orderId}/sandbox-pay`, {}, true)
}
