import { apiGet, apiPost } from './client'

export function createRental(body) {
  return apiPost('/api/v1/rentals', body, true)
}

export function getMyRentals() {
  return apiGet('/api/v1/rentals/me', true)
}

export function getOwnerRentals() {
  return apiGet('/api/v1/rentals/owner', true)
}

export function approveRental(rentalId) {
  return apiPost(`/api/v1/rentals/${rentalId}/approve`, {}, true)
}

export function rejectRental(rentalId, body) {
  return apiPost(`/api/v1/rentals/${rentalId}/reject`, body, true)
}

export function cancelRental(rentalId) {
  return apiPost(`/api/v1/rentals/${rentalId}/cancel`, {}, true)
}