export type ApiErrorBody = {
  code: string
  message: string
  action?: string | null
  field_errors?: Record<string, string> | null
}

const fallbackError: ApiErrorBody = {
  code: "HTTP_ERROR",
  message: "요청을 처리하지 못했어요.",
  action: "잠시 후 다시 시도해 주세요.",
}

export class ApiClientError extends Error {
  readonly status: number
  readonly body: ApiErrorBody

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = "ApiClientError"
    this.status = status
    this.body = body
  }
}

function readErrorBody(responseText: string): ApiErrorBody {
  try {
    return JSON.parse(responseText) as ApiErrorBody
  } catch {
    return fallbackError
  }
}

export async function apiClient<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(path, init)
  const responseText = await response.text()

  if (!response.ok) {
    throw new ApiClientError(response.status, readErrorBody(responseText))
  }

  if (responseText.trim().length === 0) {
    return undefined as T
  }

  return JSON.parse(responseText) as T
}
