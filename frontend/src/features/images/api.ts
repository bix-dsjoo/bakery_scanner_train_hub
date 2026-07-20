import { apiClient } from "@/shared/api/client"

export type ImageKind = "PRODUCT" | "TRAY"
export type LabelingStatus = "UNLABELED" | "COMPLETED"

export type ImageRecord = {
  id: string
  brand_id: string
  kind: ImageKind
  product_id: string | null
  original_filename: string
  mime_type: string
  width: number
  height: number
  byte_size: number
  labeling_status: LabelingStatus
  revision: number
  created_at: string
  updated_at: string
  box_count: number
}

export type ImagePage = { items: ImageRecord[]; next_cursor: string | null }
export type ImageFilters = {
  kind?: ImageKind
  status?: LabelingStatus
  productId?: string
  filename?: string
  cursor?: string
  limit?: number
}

export const imagesQueryKey = (brandId: string, filters: ImageFilters = {}) =>
  ["images", brandId, filters] as const

function imagePath(brandId: string, imageId: string, suffix = "") {
  const search = new URLSearchParams({ brand_id: brandId })
  return `/api/v1/images/${encodeURIComponent(imageId)}${suffix}?${search}`
}

export function listImages(brandId: string, filters: ImageFilters = {}) {
  const search = new URLSearchParams()
  if (filters.kind) search.set("kind", filters.kind)
  if (filters.status) search.set("status", filters.status)
  if (filters.productId) search.set("product_id", filters.productId)
  if (filters.filename) search.set("filename", filters.filename)
  if (filters.cursor) search.set("cursor", filters.cursor)
  if (filters.limit) search.set("limit", String(filters.limit))
  const suffix = search.size ? `?${search}` : ""
  return apiClient<ImagePage>(
    `/api/v1/brands/${encodeURIComponent(brandId)}/images${suffix}`
  )
}

export function getImage(brandId: string, imageId: string) {
  return apiClient<ImageRecord>(imagePath(brandId, imageId))
}

export function changeImageProduct(
  brandId: string,
  imageId: string,
  productId: string
) {
  return apiClient<ImageRecord>(imagePath(brandId, imageId, "/product"), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId }),
  })
}

export function deleteImage(brandId: string, imageId: string) {
  return apiClient<void>(imagePath(brandId, imageId), { method: "DELETE" })
}

export function imageThumbnailUrl(brandId: string, imageId: string) {
  return imagePath(brandId, imageId, "/thumbnail")
}

export function imageOriginalUrl(brandId: string, imageId: string) {
  return imagePath(brandId, imageId, "/original")
}
