import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query"
import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { HttpResponse, http } from "msw"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest"

import { brandsQueryKey } from "@/features/brands/api"
import { BrandProvider, useCurrentBrand } from "@/features/brands/brand-provider"

const now = "2026-07-15T08:00:00Z"
const activeFirst = {
  id: "brand-1",
  name: "첫 번째 베이커리",
  status: "ACTIVE" as const,
  created_at: now,
  updated_at: now,
}
const activeSecond = {
  ...activeFirst,
  id: "brand-2",
  name: "두 번째 베이커리",
}
const activeThird = {
  ...activeFirst,
  id: "brand-3",
  name: "세 번째 베이커리",
}
const inactive = {
  ...activeFirst,
  id: "brand-old",
  name: "예전 베이커리",
  status: "INACTIVE" as const,
}

let brands = [activeFirst, activeSecond, activeThird, inactive]
const server = setupServer(
  http.get("/api/v1/brands", () => HttpResponse.json(brands))
)

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => {
  cleanup()
  localStorage.clear()
  brands = [activeFirst, activeSecond, activeThird, inactive]
  server.resetHandlers()
})
afterAll(() => server.close())

function CurrentBrandHarness() {
  const { brand, setBrandId, isLoading } = useCurrentBrand()
  const queryClient = useQueryClient()

  return (
    <div>
      <output>{isLoading ? "불러오는 중" : (brand?.name ?? "선택 없음")}</output>
      <button type="button" onClick={() => setBrandId(activeSecond.id)}>
        두 번째 선택
      </button>
      <button
        type="button"
        onClick={() => void queryClient.invalidateQueries({ queryKey: brandsQueryKey })}
      >
        브랜드 새로고침
      </button>
    </div>
  )
}

function renderProvider(children: ReactNode = <CurrentBrandHarness />) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrandProvider>{children}</BrandProvider>
    </QueryClientProvider>
  )
}

describe("BrandProvider", () => {
  it("automatically selects the first active brand and persists it", async () => {
    renderProvider()

    expect(await screen.findByText(activeFirst.name)).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBe(activeFirst.id)
  })

  it("restores a valid active brand from localStorage", async () => {
    localStorage.setItem("bakery.currentBrandId", activeSecond.id)

    renderProvider()

    expect(await screen.findByText(activeSecond.name)).toBeVisible()
  })

  it("never restores or persists an inactive brand id", async () => {
    localStorage.setItem("bakery.currentBrandId", inactive.id)

    renderProvider()

    expect(await screen.findByText(activeFirst.name)).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBe(activeFirst.id)
  })

  it("moves to the next active brand when the current brand becomes inactive", async () => {
    const user = userEvent.setup()
    renderProvider()
    expect(await screen.findByText(activeFirst.name)).toBeVisible()

    brands = [{ ...activeFirst, status: "INACTIVE" }, activeSecond, inactive]
    await user.click(screen.getByRole("button", { name: "브랜드 새로고침" }))

    expect(await screen.findByText(activeSecond.name)).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBe(activeSecond.id)
  })

  it("preserves list order when a middle current brand becomes inactive", async () => {
    localStorage.setItem("bakery.currentBrandId", activeSecond.id)
    const user = userEvent.setup()
    renderProvider()
    expect(await screen.findByText(activeSecond.name)).toBeVisible()

    brands = [
      activeFirst,
      { ...activeSecond, status: "INACTIVE" },
      activeThird,
      inactive,
    ]
    await user.click(screen.getByRole("button", { name: "브랜드 새로고침" }))

    expect(await screen.findByText(activeThird.name)).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBe(activeThird.id)
  })

  it("clears persisted state when no active brand remains", async () => {
    renderProvider()
    expect(await screen.findByText(activeFirst.name)).toBeVisible()

    brands = [{ ...activeFirst, status: "INACTIVE" }, inactive]
    await act(async () => {
      screen.getByRole("button", { name: "브랜드 새로고침" }).click()
    })

    expect(await screen.findByText("선택 없음")).toBeVisible()
    expect(localStorage.getItem("bakery.currentBrandId")).toBeNull()
  })
})
