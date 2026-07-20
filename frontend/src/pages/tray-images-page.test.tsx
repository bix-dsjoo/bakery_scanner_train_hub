import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { HttpResponse, delay, http } from "msw"
import { setupServer } from "msw/node"
import { MemoryRouter } from "react-router-dom"
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { TrayImagesPage } from "@/pages/tray-images-page"

const now = "2026-07-20T08:00:00Z"
const brand = { id: "brand-1", name: "비솔론 베이커리" }
const product = { id: "product-1", brand_id: brand.id, code: "P-1", name: "소금빵", status: "ACTIVE", created_at: now, updated_at: now }
const makeImage = (index: number) => ({ id: `image-${index}`, brand_id: brand.id, kind: "TRAY", product_id: null, original_filename: index === 1 ? `${"매우긴파일명".repeat(20)}.jpg` : `tray-${index}.jpg`, mime_type: "image/jpeg", width: 1200, height: 800, byte_size: 100, labeling_status: "UNLABELED", revision: 0, created_at: now, updated_at: now, box_count: 0 })
let responseItems = [makeImage(1)]
let currentBrand = brand
let nextCursor: string | null = null
let responseDelay = 0
const requests: string[] = []

vi.mock("@/features/brands/brand-provider", () => ({ useCurrentBrand: () => ({ brand: currentBrand, isLoading: false, error: null }) }))
vi.mock("@/features/uploads/upload-dialog", () => ({
  UploadDialog: (props: { kind: string; productId?: string; onComplete?: (results: unknown[]) => void; children: React.ReactNode }) => (
    <div data-testid="upload-contract" data-kind={props.kind} data-product-id={props.productId ?? ""}>
      {props.children}<button onClick={() => props.onComplete?.([{ status: "success", image: { id: "uploaded-1" } }])}>업로드 성공 시뮬레이션</button>
    </div>
  ),
}))

const server = setupServer(
  http.get("/api/v1/brands/:brandId/products", () => HttpResponse.json([product])),
  http.get("/api/v1/brands/:brandId/images", async ({ request }) => {
    requests.push(request.url)
    if (responseDelay) await delay(responseDelay)
    return HttpResponse.json({ items: responseItems, next_cursor: nextCursor })
  }),
  http.delete("/api/v1/images/:imageId", ({ request }) => {
    requests.push(request.url)
    responseItems = []
    return new HttpResponse(null, { status: 204 })
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => { cleanup(); responseItems = [makeImage(1)]; currentBrand = brand; nextCursor = null; responseDelay = 0; requests.length = 0; server.resetHandlers(); vi.useRealTimers() })
afterAll(() => server.close())

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><TooltipProvider delay={0}><MemoryRouter><TrayImagesPage /></MemoryRouter></TooltipProvider></QueryClientProvider>)
}

describe("TrayImagesPage", () => {
  it("provides status tabs, filename and active-product filters with thumbnail rows", async () => {
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText(responseItems[0].original_filename)).toBeVisible()
    expect(screen.getByRole("tab", { name: "라벨 필요" })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("tab", { name: "완료" })).toBeVisible()
    expect(screen.getByRole("img", { name: responseItems[0].original_filename })).toHaveClass("size-14")
    expect(screen.getByText(responseItems[0].original_filename)).toHaveClass("truncate")
    expect(screen.getByTestId("upload-contract")).toHaveAttribute("data-kind", "TRAY")

    await user.type(screen.getByRole("searchbox", { name: "파일명 검색" }), "tray name")
    await user.click(screen.getByRole("combobox", { name: "상품 필터" }))
    await user.click(await screen.findByRole("option", { name: product.name }))
    await waitFor(() => {
      const url = new URL(requests.at(-1)!)
      expect(url.searchParams.get("filename")).toBe("tray name")
      expect(url.searchParams.get("product_id")).toBe(product.id)
    })
  })

  it("distinguishes an empty library from no search results", async () => {
    responseItems = []
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("라벨링할 트레이 사진이 없어요")).toBeVisible()
    await user.type(screen.getByRole("searchbox", { name: "파일명 검색" }), "없음")
    expect(await screen.findByText("조건에 맞는 사진이 없어요")).toBeVisible()
    expect(screen.getByRole("button", { name: "필터 초기화" })).toBeVisible()
  })

  it("renders 100 rows and loads the next cursor page", async () => {
    responseItems = Array.from({ length: 100 }, (_, index) => makeImage(index + 1))
    nextCursor = "next+/="
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findAllByRole("img")).toHaveLength(100)
    responseItems = [makeImage(101)]
    nextCursor = null
    await user.click(screen.getByRole("button", { name: "다음 사진 불러오기" }))
    expect(await screen.findByText("tray-101.jpg")).toBeVisible()
    expect(new URL(requests.at(-1)!).searchParams.get("cursor")).toBe("next+/=")
  })

  it("does not flash a skeleton for quick requests but shows it after 200ms", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    responseDelay = 500
    renderPage()
    expect(screen.queryByLabelText("사진 목록 불러오는 중")).not.toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(201) })
    expect(screen.getByLabelText("사진 목록 불러오는 중")).toBeVisible()
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(await screen.findByText(responseItems[0].original_filename)).toBeVisible()
  })

  it("offers the first-labeling action after a successful tray upload", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(responseItems[0].original_filename)
    await user.click(screen.getByRole("button", { name: "업로드 성공 시뮬레이션" }))
    const action = await screen.findByRole("link", { name: "첫 사진 라벨링하기" })
    expect(action).toHaveAttribute("href", "/images/uploaded-1/label")
  })

  it("clears an uploaded-photo action when the current brand changes", async () => {
    const user = userEvent.setup()
    const view = renderPage()
    await screen.findByText(responseItems[0].original_filename)
    await user.click(screen.getByRole("button", { name: "업로드 성공 시뮬레이션" }))
    expect(await screen.findByRole("link", { name: "첫 사진 라벨링하기" })).toBeVisible()
    currentBrand = { id: "brand-2", name: "다른 브랜드" }
    view.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><TooltipProvider delay={0}><MemoryRouter><TrayImagesPage /></MemoryRouter></TooltipProvider></QueryClientProvider>)
    await waitFor(() => expect(screen.queryByRole("link", { name: "첫 사진 라벨링하기" })).not.toBeInTheDocument())
  })

  it("deletes a tray photo only after confirming image and box counts", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(responseItems[0].original_filename)
    await user.click(screen.getByRole("button", { name: `${responseItems[0].original_filename} 삭제` }))
    const alert = screen.getByRole("alertdialog", { name: "트레이 사진 삭제" })
    expect(within(alert).getByText(/사진 1장과 박스 0개/)).toBeVisible()
    await user.click(within(alert).getByRole("button", { name: "삭제" }))
    expect(await screen.findByText("라벨링할 트레이 사진이 없어요")).toBeVisible()
    const deleteRequest = requests.find((url) => url.includes("/api/v1/images/"))!
    expect(new URL(deleteRequest).searchParams.get("brand_id")).toBe(brand.id)
  })
})
