import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest"
import { http, HttpResponse } from "msw"
import { setupServer } from "msw/node"

import { apiClient } from "@/shared/api/client"

const server = setupServer(
  http.get("http://localhost/api/v1/health", () =>
    HttpResponse.json({ status: "ready" })
  ),
  http.get("http://localhost/api/v1/empty", () =>
    new HttpResponse(null, { status: 200 })
  ),
  http.post("http://localhost/api/v1/empty", () =>
    new HttpResponse(null, { status: 201 })
  ),
  http.head("http://localhost/api/v1/empty", () =>
    new HttpResponse(null, { status: 200 })
  ),
  http.delete("http://localhost/api/v1/empty", () =>
    new HttpResponse(null, { status: 204 })
  ),
  http.post("http://localhost/api/v1/products", () =>
    HttpResponse.json(
      {
        code: "PRODUCT_CODE_DUPLICATE",
        message: "같은 브랜드에 이미 등록된 상품 코드예요.",
        action: "다른 상품 코드를 입력해 주세요.",
        field_errors: { code: "이미 사용 중인 코드예요." },
      },
      { status: 409 }
    )
  )
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe("apiClient", () => {
  it("returns parsed JSON for a successful response", async () => {
    await expect(
      apiClient<{ status: string }>("http://localhost/api/v1/health")
    ).resolves.toEqual({ status: "ready" })
  })

  it("returns undefined for an empty 200 response", async () => {
    await expect(
      apiClient<void>("http://localhost/api/v1/empty")
    ).resolves.toBeUndefined()
  })

  it("returns undefined for an empty 201 response", async () => {
    await expect(
      apiClient<void>("http://localhost/api/v1/empty", { method: "POST" })
    ).resolves.toBeUndefined()
  })

  it("returns undefined for an empty HEAD response", async () => {
    await expect(
      apiClient<void>("http://localhost/api/v1/empty", { method: "HEAD" })
    ).resolves.toBeUndefined()
  })

  it("returns undefined for a 204 response", async () => {
    await expect(
      apiClient<void>("http://localhost/api/v1/empty", { method: "DELETE" })
    ).resolves.toBeUndefined()
  })

  it("preserves the API error JSON in ApiClientError", async () => {
    const request = apiClient("http://localhost/api/v1/products", {
      method: "POST",
    })

    await expect(request).rejects.toMatchObject({
      name: "ApiClientError",
      status: 409,
      body: {
        code: "PRODUCT_CODE_DUPLICATE",
        message: "같은 브랜드에 이미 등록된 상품 코드예요.",
        action: "다른 상품 코드를 입력해 주세요.",
        field_errors: { code: "이미 사용 중인 코드예요." },
      },
    })
  })
})
