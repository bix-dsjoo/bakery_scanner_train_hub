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
const image = { id: "image-1", brand_id: brand.id, kind: "PRODUCT", product_id: currentProduct.id, original_filename: "아주 긴 상품 사진 이름.jpg", mime_type: "image/jpeg", width: 1200, height: 800, byte_size: 100, labeling_status: "COMPLETED", revision: 0, created_at: now, updated_at: now, box_count: 0 }
let imageItems = [image]
const requests: string[] = []

vi.mock("@/features/brands/brand-provider", () => ({
  useCurrentBrand: () => ({ brand, isLoading: false, error: null }),
}))
vi.mock("@/features/uploads/upload-dialog", () => ({
  UploadDialog: (props: { kind: string; productId?: string; children: React.ReactNode }) => (
    <div data-testid="upload-contract" data-kind={props.kind} data-product-id={props.productId}>{props.children}</div>
  ),
}))

const server = setupServer(
  http.get("/api/v1/brands/:brandId/products", () => HttpResponse.json([currentProduct, activeProduct, inactiveProduct])),
  http.get("/api/v1/brands/:brandId/images", ({ request }) => {
    requests.push(request.url)
    return HttpResponse.json({ items: imageItems, next_cursor: null })
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
afterEach(() => { cleanup(); imageItems = [image]; requests.length = 0; server.resetHandlers() })
afterAll(() => server.close())

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><TooltipProvider delay={0}><MemoryRouter initialEntries={["/products/product-1"]}><Routes><Route path="/products/:productId" element={<ProductDetailPage />} /></Routes></MemoryRouter></TooltipProvider></QueryClientProvider>
  )
}

describe("ProductDetailPage", () => {
  it("shows the current product, thumbnail-only list, and fixed product upload context", async () => {
    renderPage()
    expect(await screen.findByRole("heading", { name: "소금빵" })).toBeVisible()
    const contract = screen.getByTestId("upload-contract")
    expect(contract).toHaveAttribute("data-kind", "PRODUCT")
    expect(contract).toHaveAttribute("data-product-id", currentProduct.id)
    expect(screen.getByRole("img", { name: image.original_filename })).toHaveAttribute("src", expect.stringContaining("/thumbnail?brand_id=brand-1"))
    expect(document.body.innerHTML).not.toContain("/original")
  })

  it("reassigns only to active same-brand products and deletes after an explicit count confirmation", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(image.original_filename)

    await user.click(screen.getByRole("combobox", { name: `${image.original_filename} 상품 변경` }))
    expect(await screen.findByRole("option", { name: activeProduct.name })).toBeVisible()
    expect(screen.queryByRole("option", { name: inactiveProduct.name })).not.toBeInTheDocument()
    await user.click(screen.getByRole("option", { name: activeProduct.name }))
    await waitFor(() => expect(requests.some((url) => url.includes("brand_id=brand-1"))).toBe(true))

    await user.click(screen.getByRole("button", { name: `${image.original_filename} 삭제` }))
    const alert = screen.getByRole("alertdialog", { name: "상품 사진 삭제" })
    expect(within(alert).getByText(/사진 1장과 박스 0개/)).toBeVisible()
    await user.click(within(alert).getByRole("button", { name: "삭제" }))
    expect(await screen.findByText("등록된 상품 사진이 없어요")).toBeVisible()
  })
})
