import { apiClient } from "@/shared/api/client"

export type CatalogStatus = "ACTIVE" | "INACTIVE"

export type Brand = {
  id: string
  name: string
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export const brandsQueryKey = ["brands"] as const

export function listBrands(): Promise<Brand[]> {
  return apiClient<Brand[]>("/api/v1/brands")
}

export function createBrand(input: { name: string }): Promise<Brand> {
  return apiClient<Brand>("/api/v1/brands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
}

export function updateBrand(
  brandId: string,
  input: { name: string }
): Promise<Brand> {
  return apiClient<Brand>(`/api/v1/brands/${brandId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
}

export function deactivateBrand(brandId: string): Promise<Brand> {
  return apiClient<Brand>(`/api/v1/brands/${brandId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "INACTIVE" }),
  })
}
