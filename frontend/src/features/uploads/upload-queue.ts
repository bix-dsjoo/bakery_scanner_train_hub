import { apiClient, ApiClientError, type ApiErrorBody } from "@/shared/api/client"
import type {
  UploadFilesOptions,
  UploadRequest,
  UploadRequestInput,
  UploadResult,
} from "@/features/uploads/types"

const unknownUploadError: ApiErrorBody = {
  code: "UPLOAD_FAILED",
  message: "사진을 올리지 못했어요.",
  action: "네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
}

const defaultUploadRequest: UploadRequest = ({
  file,
  brandId,
  kind,
  productId,
}: UploadRequestInput) => {
  const form = new FormData()
  form.append("file", file)
  form.append("kind", kind)
  if (productId) form.append("product_id", productId)

  return apiClient(`/api/v1/brands/${encodeURIComponent(brandId)}/images`, {
    method: "POST",
    body: form,
  })
}

function errorBody(error: unknown): ApiErrorBody {
  if (error instanceof ApiClientError) return error.body

  if (
    typeof error === "object" &&
    error !== null &&
    "body" in error &&
    typeof error.body === "object" &&
    error.body !== null &&
    "code" in error.body &&
    "message" in error.body
  ) {
    return error.body as ApiErrorBody
  }

  return unknownUploadError
}

export async function uploadFiles(options: UploadFilesOptions): Promise<UploadResult[]> {
  const results: UploadResult[] = options.files.map((file) => ({
    file,
    status: "waiting",
  }))
  const requestedConcurrency = options.concurrency ?? 2
  const concurrency = Number.isFinite(requestedConcurrency)
    ? Math.min(2, Math.max(1, Math.floor(requestedConcurrency)))
    : 2
  const request = options.request ?? defaultUploadRequest
  let nextIndex = 0

  const notify = () => options.onChange?.(results.map((result) => ({ ...result })))
  notify()

  async function worker() {
    while (nextIndex < results.length) {
      const index = nextIndex
      nextIndex += 1
      const result = results[index]
      result.status = "uploading"
      notify()

      try {
        result.image = await request({
          file: result.file,
          brandId: options.brandId,
          kind: options.kind,
          ...(options.kind === "PRODUCT" ? { productId: options.productId } : {}),
        })
        result.status = "success"
      } catch (error) {
        result.status = "failure"
        result.error = errorBody(error)
      }
      notify()
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrency, results.length) }, () => worker())
  )
  return results
}
