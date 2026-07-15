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

async function readErrorBody(response: Response): Promise<ApiErrorBody> {
  try {
    return (await response.json()) as ApiErrorBody
  } catch {
    return fallbackError
  }
}

export async function apiClient<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(path, init)

  if (!response.ok) {
    throw new ApiClientError(response.status, await readErrorBody(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
