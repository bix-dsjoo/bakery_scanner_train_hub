import { HttpResponse, http } from "msw"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest"

import {
  changeImageProduct,
  deleteImage,
  getImage,
  imageThumbnailUrl,
  listImages,
} from "@/features/images/api"

const requests: string[] = []
const server = setupServer(
  http.get("/api/v1/brands/:brandId/images", ({ request }) => {
    requests.push(request.url)
    return HttpResponse.json({ items: [], next_cursor: null })
  }),
  http.get("/api/v1/images/:imageId", ({ request }) => {
    requests.push(request.url)
    return HttpResponse.json({ id: "image/1" })
  }),
  http.patch("/api/v1/images/:imageId/product", async ({ request }) => {
    requests.push(`${request.url} ${(await request.json() as { product_id: string }).product_id}`)
    return HttpResponse.json({ id: "image/1" })
  }),
  http.delete("/api/v1/images/:imageId", ({ request }) => {
    requests.push(request.url)
    return new HttpResponse(null, { status: 204 })
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => {
  requests.length = 0
  server.resetHandlers()
})
afterAll(() => server.close())

describe("image api", () => {
  it("encodes list filters and scopes every global endpoint to the current brand", async () => {
    await listImages("brand/one", {
      kind: "TRAY",
      status: "UNLABELED",
      productId: "product & one",
      filename: "소금 빵",
      cursor: "next+/=",
      limit: 100,
    })
    await getImage("brand/one", "image/1")
    await changeImageProduct("brand/one", "image/1", "product & one")
    await deleteImage("brand/one", "image/1")

    const listUrl = new URL(requests[0])
    expect(listUrl.pathname).toBe("/api/v1/brands/brand%2Fone/images")
    expect(Object.fromEntries(listUrl.searchParams)).toEqual({
      kind: "TRAY",
      status: "UNLABELED",
      product_id: "product & one",
      filename: "소금 빵",
      cursor: "next+/=",
      limit: "100",
    })
    for (const request of requests.slice(1)) {
      expect(new URL(request.split(" ")[0]).searchParams.get("brand_id")).toBe("brand/one")
    }
    expect(requests[2]).toContain("product & one")
    expect(imageThumbnailUrl("brand/one", "image/1")).toBe(
      "/api/v1/images/image%2F1/thumbnail?brand_id=brand%2Fone"
    )
  })
})
