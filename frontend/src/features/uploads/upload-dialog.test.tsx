import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"

import { Button } from "@/components/ui/button"
import { UploadDialog } from "@/features/uploads/upload-dialog"
import type { UploadRequest } from "@/features/uploads/types"

afterEach(cleanup)

function imageFile(name: string, type = "image/jpeg") {
  return new File([name], name, { type })
}

describe("UploadDialog", () => {
  it("fixes PRODUCT and product_id context while showing progress and API guidance", async () => {
    const user = userEvent.setup()
    const calls: Parameters<UploadRequest>[0][] = []
    let finishSecond: (() => void) | undefined
    const request: UploadRequest = async (input) => {
      calls.push(input)
      if (input.file.name === "duplicate.png") {
        throw {
          body: {
            code: "IMAGE_DUPLICATE",
            message: "이미 등록된 사진이에요.",
            action: "다른 사진을 선택해 주세요.",
          },
        }
      }
      await new Promise<void>((resolve) => {
        finishSecond = resolve
      })
      return { id: "image-2" }
    }

    render(
      <UploadDialog
        open
        onOpenChange={() => undefined}
        brandId="brand-1"
        kind="PRODUCT"
        productId="product-1"
        request={request}
      />
    )

    const dialog = screen.getByRole("dialog", { name: "상품 사진 올리기" })
    const input = within(dialog).getByLabelText("사진 선택")
    expect(input).toHaveAttribute(
      "accept",
      "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
    )
    expect(input).toHaveFocus()
    expect(within(dialog).queryByLabelText(/종류|상품/)).not.toBeInTheDocument()

    await user.upload(input, [imageFile("duplicate.png", "image/png"), imageFile("ok.webp", "image/webp")])
    expect(within(dialog).getAllByText("대기")).toHaveLength(2)
    await user.click(within(dialog).getByRole("button", { name: "사진 2장 올리기" }))

    await waitFor(() => expect(calls).toHaveLength(2))
    expect(calls.every((call) => call.kind === "PRODUCT" && call.productId === "product-1")).toBe(true)
    expect(within(dialog).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50")
    const live = within(dialog).getByRole("status")
    expect(live).toHaveAttribute("aria-live", "polite")
    expect(within(live).getByText("실패")).toBeInTheDocument()
    expect(within(live).getByText("업로드 중")).toBeInTheDocument()
    expect(within(live).getByText("이미 등록된 사진이에요.")).toBeInTheDocument()
    expect(within(live).getByText("다른 사진을 선택해 주세요.")).toBeInTheDocument()

    finishSecond?.()
    await waitFor(() => expect(within(live).getByText("성공")).toBeInTheDocument())
    expect(within(dialog).getByText("2장 중 1장을 올렸어요. 1장은 올리지 못했어요.")).toBeInTheDocument()
  })

  it("keeps TRAY context fixed and restores trigger focus after Escape", async () => {
    const user = userEvent.setup()

    function Harness() {
      return (
        <UploadDialog brandId="brand-2" kind="TRAY">
          <Button>트레이 사진 추가</Button>
        </UploadDialog>
      )
    }

    render(<Harness />)
    const trigger = screen.getByRole("button", { name: "트레이 사진 추가" })
    await user.click(trigger)

    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    expect(within(dialog).queryByLabelText(/종류|상품/)).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText("사진 선택")).toHaveFocus()

    await user.keyboard("{Escape}")
    await waitFor(() => expect(dialog).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })
})
