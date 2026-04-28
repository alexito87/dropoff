import { apiGet } from './client'

export function getMyPaidRentals() {
  return apiGet('/api/v1/orders/paid-rentals/me', true)
}

export function getOwnerPaidRentals() {
  return apiGet('/api/v1/orders/paid-rentals/owner', true)
}
