import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { HttpResponse, http } from "msw"
import { setupServer } from "msw/node"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { ProductDetailPage } from "@/pages/product-detail-page"

const now = "2026-07-20T08:00:00Z"
const brand = { id: "brand-1", name: "비솔론 베이커리" }
const currentProduct = { id: "product-1", brand_id: brand.id, code: "P-1", name: "소금빵", status: "ACTIVE", created_at: now, updated_at: now }
const activeProduct = { ...currentProduct, id: "product-2", code: "P-2", name: "크루아상" }
const inactiveProduct = { ...currentProduct, id: "product-3", code: "P-3", name: "단팥빵", status: "INACTIVE" }
const otherBrandProduct = { ...currentProduct, id: "product-4", brand_id: "brand-2", code: "P-4", name: "다른 브랜드 빵" }
const makeImage = (index: number) => ({ id: `image-${index}`, brand_id: brand.id, kind: "PRODUCT", product_id: currentProduct.id, original_filename: index === 1 ? "아주 긴 상품 사진 이름.jpg" : `product-${index}.jpg`, mime_type: "image/jpeg", width: 1200, height: 800, byte_size: 100, labeling_status: "COMPLETED", revision: 0, created_at: now, updated_at: now, box_count: 0 })
const image = makeImage(1)
let imageItems = [image]
let nextCursor: string | null = null
let currentProductStatus: "ACTIVE" | "INACTIVE" = "ACTIVE"
const requests: string[] = []

vi.mock("@/features/brands/brand-provider", () => ({ useCurrentBrand: () => ({ brand, isLoading: false, error: null }) }))
vi.mock("@/features/uploads/upload-dialog", () => ({
  UploadDialog: (props: { kind: string; productId?: string; children: React.ReactNode }) => <div data-testid="upload-contract" data-kind={props.kind} data-product-id={props.productId}>{props.children}</div>,
}))

const server = setupServer(
  http.get("/api/v1/brands/:brandId/products", () => HttpResponse.json([{ ...currentProduct, status: currentProductStatus }, activeProduct, inactiveProduct, otherBrandProduct])),
  http.get("/api/v1/brands/:brandId/images", ({ request }) => {
    requests.push(request.url)
    return HttpResponse.json({ items: imageItems, next_cursor: nextCursor })
  }),
  http.patch("/api/v1/images/:imageId/product", async ({ request }) => {
    requests.push(request.url)
    const body = await request.json() as { product_id: string }
    imageItems = imageItems.map((item) => ({ ...item, product_id: body.product_id }))
    return HttpResponse.json(imageItems[0])
  }),
  http.delete("/api/v1/images/:imageId", ({ request }) => {
    requests.push(request.url)
    imageItems = []
    return new HttpResponse(null, { status: 204 })
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => { cleanup(); imageItems = [image]; nextCursor = null; currentProductStatus = "ACTIVE"; requests.length = 0; server.resetHandlers() })
afterAll(() => server.close())

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><TooltipProvider delay={0}><MemoryRouter initialEntries={["/products/product-1"]}><Routes><Route path="/products/:productId" element={<ProductDetailPage />} /></Routes></MemoryRouter></TooltipProvider></QueryClientProvider>)
}

describe("ProductDetailPage", () => {
  it("shows the current product, thumbnail-only list, and fixed product upload context", async () => {
    renderPage()
    expect(await screen.findByRole("heading", { name: "소금빵" })).toBeVisible()
    const contract = screen.getByTestId("upload-contract")
    expect(contract).toHaveAttribute("data-kind", "PRODUCT")
    expect(contract).toHaveAttribute("data-product-id", currentProduct.id)
    const thumbnail = screen.getByText(image.original_filename).closest("li")!.querySelector("img")!
    expect(thumbnail).toHaveAttribute("src", expect.stringContaining("/thumbnail?brand_id=brand-1"))
    expect(thumbnail).toHaveAttribute("alt", "")
    expect(document.body.innerHTML).not.toContain("/original")
  })

  it("blocks uploads for an inactive product with a cause and next action", async () => {
    currentProductStatus = "INACTIVE"
    renderPage()
    expect(await screen.findByRole("heading", { name: currentProduct.name })).toBeVisible()
    expect(screen.queryByTestId("upload-contract")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "상품 사진 추가" })).not.toBeInTheDocument()
    expect(screen.getByRole("alert")).toHaveTextContent("비활성 상품에는 사진을 추가할 수 없어요")
    expect(screen.getByRole("alert")).toHaveTextContent("상품을 활성화한 뒤 다시 시도해 주세요")
  })

  it("keeps reassignment available on small layouts and exposes only active same-brand products", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(image.original_filename)
    const trigger = screen.getByRole("combobox", { name: `${image.original_filename} 상품 변경` })
    expect(trigger).not.toHaveClass("hidden")
    await user.click(trigger)
    expect(await screen.findByRole("option", { name: activeProduct.name })).toBeVisible()
    expect(screen.queryByRole("option", { name: inactiveProduct.name })).not.toBeInTheDocument()
    expect(screen.queryByRole("option", { name: otherBrandProduct.name })).not.toBeInTheDocument()
  })

  it("loads a 100-photo first page and its next cursor", async () => {
    imageItems = Array.from({ length: 100 }, (_, index) => makeImage(index + 1))
    nextCursor = "next-product"
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("product-100.jpg")
    expect(document.querySelectorAll("img")).toHaveLength(100)
    expect(new URL(requests[0]).searchParams.get("limit")).toBe("50")
    imageItems = [makeImage(101)]
    nextCursor = null
    await user.click(screen.getByRole("button", { name: "다음 사진 불러오기" }))
    expect(await screen.findByText("product-101.jpg")).toBeVisible()
    expect(new URL(requests.at(-1)!).searchParams.get("cursor")).toBe("next-product")
  })

  it("distinguishes an image request failure from an empty library", async () => {
    server.use(http.get("/api/v1/brands/:brandId/images", () => HttpResponse.json({ code: "HTTP_ERROR", message: "사진을 불러오지 못했어요.", action: "서버 연결을 확인한 뒤 다시 시도해 주세요." }, { status: 500 })))
    renderPage()
    expect(await screen.findByRole("alert")).toHaveTextContent("사진을 불러오지 못했어요")
    expect(screen.getByRole("alert")).toHaveTextContent("서버 연결을 확인한 뒤 다시 시도해 주세요")
    expect(screen.queryByText("등록된 상품 사진이 없어요")).not.toBeInTheDocument()
  })

  it("reassigns and deletes after an explicit count confirmation", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(image.original_filename)
    await user.click(screen.getByRole("combobox", { name: `${image.original_filename} 상품 변경` }))
    await user.click(await screen.findByRole("option", { name: activeProduct.name }))
    await waitFor(() => expect(requests.some((url) => url.includes("brand_id=brand-1"))).toBe(true))
    await user.click(screen.getByRole("button", { name: `${image.original_filename} 삭제` }))
    const alert = screen.getByRole("alertdialog", { name: "상품 사진 삭제" })
    expect(within(alert).getByText(/사진 1장과 박스 0개/)).toBeVisible()
    await user.click(within(alert).getByRole("button", { name: "삭제" }))
    expect(await screen.findByText("등록된 상품 사진이 없어요")).toBeVisible()
  })

  it("keeps deletion failure inside the modal and blocks duplicate delete requests", async () => {
    let release!: () => void
    let deleteCount = 0
    server.use(http.delete("/api/v1/images/:imageId", async () => {
      deleteCount += 1
      await new Promise<void>((resolve) => { release = resolve })
      return HttpResponse.json({ code: "DELETE_FAILED", message: "사진을 삭제하지 못했어요.", action: "서버 연결을 확인한 뒤 다시 시도해 주세요." }, { status: 500 })
    }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(image.original_filename)
    await user.click(screen.getByRole("button", { name: `${image.original_filename} 삭제` }))
    const alert = screen.getByRole("alertdialog", { name: "상품 사진 삭제" })
    const confirm = within(alert).getByRole("button", { name: "삭제" })
    await user.click(confirm)
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    expect(deleteCount).toBe(1)
    release()
    expect(await within(alert).findByRole("alert")).toHaveTextContent("사진을 삭제하지 못했어요. 서버 연결을 확인한 뒤 다시 시도해 주세요.")
    expect(alert).toBeVisible()
  })
})
