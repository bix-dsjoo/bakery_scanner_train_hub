import type { ApiErrorBody } from "@/shared/api/client"

export type ImageKind = "PRODUCT" | "TRAY"

export type UploadStatus = "waiting" | "uploading" | "success" | "failure"

export type UploadedImage = {
  id: string
  [key: string]: unknown
}

export type UploadResult = {
  file: File
  status: UploadStatus
  image?: UploadedImage
  error?: ApiErrorBody
}

export type UploadRequestInput = {
  file: File
  brandId: string
  kind: ImageKind
  productId?: string
}

export type UploadRequest = (input: UploadRequestInput) => Promise<UploadedImage>

type SharedUploadOptions = {
  files: readonly File[]
  brandId: string
  concurrency?: number
  onChange?: (results: readonly UploadResult[]) => void
  request?: UploadRequest
}

export type UploadFilesOptions = SharedUploadOptions &
  (
    | { kind: "PRODUCT"; productId: string }
    | { kind: "TRAY"; productId?: never }
  )
