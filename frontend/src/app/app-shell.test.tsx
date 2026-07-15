import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AppRouter } from "@/app/router"

describe("AppRouter", () => {
  it("shows the application name and the three management destinations", () => {
    render(<AppRouter />)

    expect(screen.getByText("Bakery Scanner Train Hub")).toBeVisible()
    expect(screen.getByRole("link", { name: "오늘의 작업" })).toBeVisible()
    expect(screen.getByRole("link", { name: "상품 관리" })).toBeVisible()
    expect(screen.getByRole("link", { name: "트레이 사진" })).toBeVisible()
  })
})
