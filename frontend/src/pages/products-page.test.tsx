import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { HttpResponse, http } from "msw"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { BrandProvider } from "@/features/brands/brand-provider"
import { BrandSelector } from "@/features/brands/brand-selector"
import type { Brand } from "@/features/brands/api"
import { ProductsPage } from "@/pages/products-page"
import { TooltipProvider } from "@/components/ui/tooltip"

const now = "2026-07-15T08:00:00Z"
const firstBrand = {
  id: "brand-1",
  name: "비솔론 베이커리",
  status: "ACTIVE" as const,
  created_at: now,
  updated_at: now,
}
const secondBrand = {
  ...firstBrand,
  id: "brand-2",
  name: "두 번째 베이커리",
}
const activeProduct = {
  id: "product-1",
  brand_id: firstBrand.id,
  code: "BREAD-001",
  name: "소금빵",
  status: "ACTIVE" as const,
  created_at: now,
  updated_at: now,
}
const inactiveProduct = {
  ...activeProduct,
  id: "product-2",
  code: "BREAD-002",
  name: "단팥빵",
  status: "INACTIVE" as const,
}
const otherBrandProduct = {
  ...activeProduct,
  id: "product-3",
  brand_id: secondBrand.id,
  code: "SECOND-001",
  name: "두 번째 브랜드 상품",
}

let brands: Brand[] = [firstBrand, secondBrand]
let products = [activeProduct, inactiveProduct, otherBrandProduct]
const productRequests: string[] = []

const server = setupServer(
  http.get("/api/v1/brands", () => HttpResponse.json(brands)),
  http.post("/api/v1/brands", async ({ request }) => {
    const body = (await request.json()) as { name: string }
    const created = { ...firstBrand, id: `brand-${brands.length + 1}`, name: body.name }
    brands = [...brands, created]
    return HttpResponse.json(created, { status: 201 })
  }),
  http.patch("/api/v1/brands/:brandId", async ({ params, request }) => {
    const body = (await request.json()) as { name?: string; status?: "INACTIVE" }
    const target = brands.find((brand) => brand.id === params.brandId)!
    const updated = { ...target, ...body }
    brands = brands.map((brand) => (brand.id === target.id ? updated : brand))
    return HttpResponse.json(updated)
  }),
  http.get("/api/v1/brands/:brandId/products", ({ params, request }) => {
    productRequests.push(String(params.brandId))
    const url = new URL(request.url)
    const query = (url.searchParams.get("query") ?? "").toLowerCase()
    const status = url.searchParams.get("status")
    return HttpResponse.json(
      products.filter(
        (product) =>
          product.brand_id === params.brandId &&
          (!status || product.status === status) &&
          (!query ||
            product.name.toLowerCase().includes(query) ||
            product.code.toLowerCase().includes(query))
      )
    )
  }),
  http.post("/api/v1/brands/:brandId/products", async ({ params, request }) => {
    const body = (await request.json()) as { code: string; name: string }
    if (body.code === "BREAD-001") {
      return HttpResponse.json(
        {
          code: "PRODUCT_CODE_DUPLICATE",
          message: "같은 브랜드에 이미 등록된 상품 코드예요.",
          action: "다른 상품 코드를 입력해 주세요.",
          field_errors: { code: "이미 사용 중인 코드예요." },
        },
        { status: 409 }
      )
    }
    const created = {
      ...activeProduct,
      id: `product-${products.length + 1}`,
      brand_id: String(params.brandId),
      ...body,
    }
    products = [...products, created]
    return HttpResponse.json(created, { status: 201 })
  }),
  http.patch(
    "/api/v1/brands/:brandId/products/:productId",
    async ({ params, request }) => {
      const body = (await request.json()) as {
        code?: string
        name?: string
        status?: "INACTIVE"
      }
      const target = products.find(
        (product) =>
          product.id === params.productId && product.brand_id === params.brandId
      )!
      const updated = { ...target, ...body }
      products = products.map((product) =>
        product.id === target.id ? updated : product
      )
      return HttpResponse.json(updated)
    }
  )
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => {
  cleanup()
  localStorage.clear()
  brands = [firstBrand, secondBrand]
  products = [activeProduct, inactiveProduct, otherBrandProduct]
  productRequests.length = 0
  server.resetHandlers()
})
afterAll(() => server.close())

function renderCatalog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrandProvider>
        <TooltipProvider delay={0}>
          <MemoryRouter>
            <BrandSelector />
            <ProductsPage />
          </MemoryRouter>
        </TooltipProvider>
      </BrandProvider>
    </QueryClientProvider>
  )
}

describe("ProductsPage", () => {
  it("lists only the current brand products and marks inactive products", async () => {
    renderCatalog()

    expect(await screen.findByText(activeProduct.name)).toBeVisible()
    expect(screen.getByText(inactiveProduct.name)).toBeVisible()
    expect(screen.getByText("비활성")).toBeVisible()
    expect(screen.queryByText(otherBrandProduct.name)).not.toBeInTheDocument()
  })

  it("refetches products when the current brand changes", async () => {
    const user = userEvent.setup()
    renderCatalog()
    expect(await screen.findByText(activeProduct.name)).toBeVisible()

    await user.click(screen.getByRole("combobox", { name: "현재 브랜드" }))
    await user.click(await screen.findByRole("option", { name: secondBrand.name }))

    expect(await screen.findByText(otherBrandProduct.name)).toBeVisible()
    expect(screen.queryByText(activeProduct.name)).not.toBeInTheDocument()
    expect(productRequests).toContain(firstBrand.id)
    expect(productRequests).toContain(secondBrand.id)
  })

  it("opens an accessibly named product dialog and shows duplicate errors below code", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    await user.click(screen.getByRole("button", { name: "상품 추가" }))
    const dialog = screen.getByRole("dialog", { name: "상품 추가" })
    const code = within(dialog).getByLabelText("상품 코드")
    await user.type(code, activeProduct.code)
    await user.type(within(dialog).getByLabelText("상품명"), "다른 소금빵")
    await user.click(within(dialog).getByRole("button", { name: "상품 추가" }))

    const fieldError = await within(dialog).findByText("이미 사용 중인 코드예요.")
    expect(fieldError).toBeVisible()
    expect(code).toHaveAccessibleDescription("이미 사용 중인 코드예요.")
  })

  it("creates and edits products, then requires confirmation before deactivation", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    await user.click(screen.getByRole("button", { name: "상품 추가" }))
    let dialog = screen.getByRole("dialog", { name: "상품 추가" })
    await user.type(within(dialog).getByLabelText("상품 코드"), "BREAD-003")
    await user.type(within(dialog).getByLabelText("상품명"), "크루아상")
    await user.click(within(dialog).getByRole("button", { name: "상품 추가" }))
    expect(await screen.findByText("크루아상")).toBeVisible()

    await user.click(screen.getByRole("button", { name: "크루아상 수정" }))
    dialog = screen.getByRole("dialog", { name: "상품 수정" })
    const nameInput = within(dialog).getByLabelText("상품명")
    await user.clear(nameInput)
    await user.type(nameInput, "버터 크루아상")
    await user.click(within(dialog).getByRole("button", { name: "변경 저장" }))
    expect(await screen.findByText("버터 크루아상")).toBeVisible()

    await user.click(
      screen.getByRole("button", { name: "버터 크루아상 비활성화" })
    )
    const alert = screen.getByRole("alertdialog", { name: "상품 비활성화" })
    expect(within(alert).getByText(/새 박스에는 지정할 수 없습니다/)).toBeVisible()
    await user.click(within(alert).getByRole("button", { name: "비활성화" }))

    const row = (await screen.findByText("버터 크루아상")).closest("li")!
    expect(within(row).getByText("비활성")).toBeVisible()
  })

  it("shows product action names in tooltips on keyboard focus", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    const editAction = screen.getByRole("button", { name: `${activeProduct.name} 수정` })
    for (let index = 0; index < 10 && document.activeElement !== editAction; index += 1) {
      await user.tab()
    }
    expect(editAction).toHaveFocus()
    expect(await screen.findByText(`${activeProduct.name} 수정`)).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )

    const deactivateAction = screen.getByRole("button", {
      name: `${activeProduct.name} 비활성화`,
    })
    await user.tab()
    expect(deactivateAction).toHaveFocus()
    expect(
      await screen.findByText(`${activeProduct.name} 비활성화`)
    ).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )
  })

  it("applies search and status filters to the current brand request", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    await user.type(screen.getByRole("searchbox", { name: "상품 검색" }), "단팥")
    expect(await screen.findByText(inactiveProduct.name)).toBeVisible()
    expect(screen.queryByText(activeProduct.name)).not.toBeInTheDocument()

    await user.click(screen.getByRole("combobox", { name: "상품 상태" }))
    await user.click(await screen.findByRole("option", { name: "활성" }))
    await waitFor(() => expect(screen.queryByText(inactiveProduct.name)).not.toBeInTheDocument())
  })

  it("edits a brand and moves to the next active brand after current deactivation", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    await user.click(screen.getByRole("button", { name: "브랜드 관리" }))
    let management = screen.getByRole("dialog", { name: "브랜드 관리" })
    await user.click(within(management).getByRole("button", { name: `${firstBrand.name} 수정` }))
    const editDialog = screen.getByRole("dialog", { name: "브랜드 수정" })
    const nameInput = within(editDialog).getByLabelText("브랜드 이름")
    await user.clear(nameInput)
    await user.type(nameInput, "비솔론 베이크 랩")
    await user.click(within(editDialog).getByRole("button", { name: "변경 저장" }))
    management = screen.getByRole("dialog", { name: "브랜드 관리" })
    expect(await within(management).findByText("비솔론 베이크 랩")).toBeVisible()
    await user.click(
      within(management).getByRole("button", { name: "비솔론 베이크 랩 비활성화" })
    )
    const alert = screen.getByRole("alertdialog", { name: "브랜드 비활성화" })
    await user.click(within(alert).getByRole("button", { name: "비활성화" }))

    expect(await screen.findByText(otherBrandProduct.name)).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBe(secondBrand.id)
  })

  it("shows one brand creation action when no active brand remains", async () => {
    brands = [{ ...firstBrand, status: "INACTIVE" as const }]
    const user = userEvent.setup()
    renderCatalog()

    expect(await screen.findByText("활성 브랜드가 없어요")).toBeVisible()
    const action = screen.getByRole("button", { name: "브랜드 만들기" })
    expect(action).toBeVisible()
    await user.click(action)
    expect(screen.getByRole("dialog", { name: "브랜드 만들기" })).toBeVisible()
  })

  it("moves from last-brand deactivation to the empty-state creation flow", async () => {
    brands = [firstBrand]
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText(activeProduct.name)

    await user.click(screen.getByRole("button", { name: "브랜드 관리" }))
    const management = screen.getByRole("dialog", { name: "브랜드 관리" })
    await user.click(
      within(management).getByRole("button", { name: `${firstBrand.name} 비활성화` })
    )
    const alert = screen.getByRole("alertdialog", { name: "브랜드 비활성화" })
    await user.click(within(alert).getByRole("button", { name: "비활성화" }))

    const createAction = await screen.findByRole("button", { name: "브랜드 만들기" })
    expect(screen.getByText("활성 브랜드가 없어요")).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBeNull()

    await user.click(createAction)
    const createDialog = screen.getByRole("dialog", { name: "브랜드 만들기" })
    await user.type(within(createDialog).getByLabelText("브랜드 이름"), "새 베이커리")
    await user.click(within(createDialog).getByRole("button", { name: "브랜드 만들기" }))

    await waitFor(() =>
      expect(localStorage.getItem("bakery.currentBrandId")).toBe("brand-2")
    )
    expect(screen.getAllByText("새 베이커리").length).toBeGreaterThan(0)
  })
})
