import type { CatalogStatus } from "@/features/brands/api"
import { apiClient } from "@/shared/api/client"

export type Product = {
  id: string
  brand_id: string
  code: string
  name: string
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export type ProductInput = { code: string; name: string }
export type ProductFilters = { query?: string; status?: CatalogStatus }

export const productsQueryKey = (
  brandId: string,
  filters: ProductFilters = {}
) => ["products", brandId, filters] as const

export function listProducts(
  brandId: string,
  filters: ProductFilters = {}
): Promise<Product[]> {
  const search = new URLSearchParams()
  if (filters.query) search.set("query", filters.query)
  if (filters.status) search.set("status", filters.status)
  const suffix = search.size ? `?${search.toString()}` : ""
  return apiClient<Product[]>(`/api/v1/brands/${brandId}/products${suffix}`)
}

export function createProduct(
  brandId: string,
  input: ProductInput
): Promise<Product> {
  return apiClient<Product>(`/api/v1/brands/${brandId}/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
}

export function updateProduct(
  product: Pick<Product, "id" | "brand_id">,
  input: ProductInput
): Promise<Product> {
  return apiClient<Product>(
    `/api/v1/brands/${product.brand_id}/products/${product.id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  )
}

export function deactivateProduct(
  product: Pick<Product, "id" | "brand_id">
): Promise<Product> {
  return apiClient<Product>(
    `/api/v1/brands/${product.brand_id}/products/${product.id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "INACTIVE" }),
    }
  )
}
