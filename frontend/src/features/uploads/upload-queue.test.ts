import { afterEach, describe, expect, it, vi } from "vitest"

import { uploadFiles } from "@/features/uploads/upload-queue"
import type { UploadRequest } from "@/features/uploads/types"

afterEach(() => vi.restoreAllMocks())

function file(name: string) {
  return new File([name], name, { type: "image/jpeg" })
}

describe("uploadFiles", () => {
  it("keeps at most two genuinely asynchronous uploads running across 100 files", async () => {
    const files = Array.from({ length: 100 }, (_, index) => file(`${index}.jpg`))
    let active = 0
    let maximumActive = 0

    const request: UploadRequest = async (_input) => {
      active += 1
      maximumActive = Math.max(maximumActive, active)
      await new Promise<void>((resolve) => queueMicrotask(resolve))
      active -= 1
      return { id: "uploaded" }
    }

    const results = await uploadFiles({
      files,
      brandId: "brand-1",
      kind: "TRAY",
      concurrency: 2,
      request,
    })

    expect(maximumActive).toBe(2)
    expect(results).toHaveLength(100)
    expect(results.every((result) => result.status === "success")).toBe(true)
  })

  it("preserves file order and isolates duplicate, corrupt, and oversized failures", async () => {
    const files = [
      file("success.jpg"),
      file("duplicate.jpg"),
      file("corrupt.jpg"),
      file("too-large.jpg"),
      file("after-errors.jpg"),
    ]
    const codes: Record<string, string> = {
      "duplicate.jpg": "IMAGE_DUPLICATE",
      "corrupt.jpg": "IMAGE_CORRUPT",
      "too-large.jpg": "IMAGE_TOO_LARGE",
    }
    const transitions: string[][] = []

    const results = await uploadFiles({
      files,
      brandId: "brand-1",
      kind: "TRAY",
      concurrency: 2,
      onChange: (items) => transitions.push(items.map((item) => item.status)),
      request: async ({ file: currentFile }) => {
        await new Promise<void>((resolve) => queueMicrotask(resolve))
        const code = codes[currentFile.name]
        if (code) {
          throw {
            body: {
              code,
              message: `${currentFile.name} 실패`,
              action: "파일을 확인해 주세요.",
            },
          }
        }
        return { id: currentFile.name }
      },
    })

    expect(results.map((result) => result.file.name)).toEqual(files.map(({ name }) => name))
    expect(results.map((result) => result.status)).toEqual([
      "success",
      "failure",
      "failure",
      "failure",
      "success",
    ])
    expect(results.slice(1, 4).map((result) => result.error?.code)).toEqual([
      "IMAGE_DUPLICATE",
      "IMAGE_CORRUPT",
      "IMAGE_TOO_LARGE",
    ])
    expect(transitions[0]).toEqual(["waiting", "waiting", "waiting", "waiting", "waiting"])
    expect(transitions.some((items) => items.includes("uploading"))).toBe(true)
    expect(transitions.at(-1)).toEqual(results.map((result) => result.status))
  })

  it("posts one multipart request per file with the fixed product context", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ id: "image-1" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    )

    await uploadFiles({
      files: [file("salt-bread.jpg"), file("croissant.jpg")],
      brandId: "brand with/slash",
      kind: "PRODUCT",
      productId: "product-7",
      concurrency: 2,
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/brands/brand%20with%2Fslash/images",
      "/api/v1/brands/brand%20with%2Fslash/images",
    ])
    const forms = fetchMock.mock.calls.map(([, init]) => init?.body as FormData)
    expect(forms.every((form) => form instanceof FormData)).toBe(true)
    expect(forms.map((form) => (form.get("file") as File).name)).toEqual([
      "salt-bread.jpg",
      "croissant.jpg",
    ])
    expect(forms.map((form) => form.get("kind"))).toEqual(["PRODUCT", "PRODUCT"])
    expect(forms.map((form) => form.get("product_id"))).toEqual(["product-7", "product-7"])
  })

  it("omits product_id for tray uploads", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ id: "image-1" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    )

    await uploadFiles({
      files: [file("tray.webp")],
      brandId: "brand-2",
      kind: "TRAY",
      concurrency: 2,
    })

    const [path, init] = fetchMock.mock.calls[0]
    const form = init?.body as FormData
    expect(path).toBe("/api/v1/brands/brand-2/images")
    expect((form.get("file") as File).name).toBe("tray.webp")
    expect(form.get("kind")).toBe("TRAY")
    expect(form.has("product_id")).toBe(false)
  })
})
