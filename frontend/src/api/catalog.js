import { apiGet } from "./client";

function buildQuery(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export function getCatalogItems(params = {}) {
  const query = buildQuery(params);
  return apiGet(`/api/v1/catalog/items${query}`);
}

export function getCatalogItemDetails(itemId) {
  return apiGet(`/api/v1/catalog/items/${itemId}`);
}