export function normalizeProductPayload(form) {
  const name = (form.name || '').trim()
  const brand = (form.brand || '').trim()
  const priceText = (form.price || '').trim()
  const mainImageUrl = (form.main_image_url || '').trim()
  const description = (form.description || '').trim()

  return {
    name,
    brand: brand || null,
    price: priceText ? Number(priceText) : null,
    main_image_url: mainImageUrl || null,
    description: description || null,
  }
}

export function filterOwnedProducts(products = []) {
  return products.filter((product) => product?.is_public !== true)
}
