import api from './api'

export function listProducts(params = {}) {
  return api.get('/v1/products', { params })
}

export function createProduct(data) {
  return api.post('/v1/products', data)
}

export function updateProduct(productId, data) {
  return api.put(`/v1/products/${productId}`, data)
}

export function deleteProduct(productId) {
  return api.delete(`/v1/products/${productId}`)
}
