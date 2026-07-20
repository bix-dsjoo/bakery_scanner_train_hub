import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { StrictMode } from "react"

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
    expect(live).toHaveTextContent("2장 중 1장 처리됨")
    expect(within(dialog).getByText("실패")).toBeInTheDocument()
    expect(within(dialog).getByText("업로드 중")).toBeInTheDocument()
    expect(within(dialog).getByText("이미 등록된 사진이에요.")).toBeInTheDocument()
    expect(within(dialog).getByText("다른 사진을 선택해 주세요.")).toBeInTheDocument()

    finishSecond?.()
    await waitFor(() => expect(within(dialog).getByText("성공")).toBeInTheDocument())
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

  it("keeps the dialog open and prevents a second batch while an upload is active", async () => {
    const user = userEvent.setup()
    const finishes: Array<() => void> = []
    let active = 0
    let maximumActive = 0
    const request: UploadRequest = async ({ file }) => {
      active += 1
      maximumActive = Math.max(maximumActive, active)
      await new Promise<void>((resolve) => finishes.push(resolve))
      active -= 1
      return { id: file.name }
    }

    const view = render(
      <UploadDialog open brandId="brand-1" kind="TRAY" request={request} />
    )
    let dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    await user.upload(within(dialog).getByLabelText("사진 선택"), [
      imageFile("first.jpg"),
      imageFile("second.jpg"),
    ])
    await user.click(within(dialog).getByRole("button", { name: "사진 2장 올리기" }))
    await waitFor(() => expect(finishes).toHaveLength(2))

    await user.keyboard("{Escape}")
    expect(screen.getByRole("dialog", { name: "트레이 사진 올리기" })).toBeInTheDocument()
    expect(
      within(dialog).getAllByRole("button", { name: "닫기" }).every((button) => button.hasAttribute("disabled"))
    ).toBe(true)

    view.rerender(<UploadDialog open={false} brandId="brand-1" kind="TRAY" request={request} />)
    view.rerender(<UploadDialog open brandId="brand-1" kind="TRAY" request={request} />)
    dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    expect(within(dialog).getByLabelText("사진 선택")).toBeDisabled()
    expect(maximumActive).toBe(2)

    finishes.splice(0).forEach((finish) => finish())
    await waitFor(() => expect(within(dialog).getAllByText("성공")).toHaveLength(2))
  })

  it("does not publish stale state or completion after unmount", async () => {
    const user = userEvent.setup()
    const onComplete = vi.fn()
    let finish: (() => void) | undefined
    const request: UploadRequest = async () => {
      await new Promise<void>((resolve) => {
        finish = resolve
      })
      return { id: "late-image" }
    }
    const view = render(
      <UploadDialog
        open
        brandId="brand-1"
        kind="TRAY"
        request={request}
        onComplete={onComplete}
      />
    )
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    await user.upload(within(dialog).getByLabelText("사진 선택"), imageFile("late.jpg"))
    await user.click(within(dialog).getByRole("button", { name: "사진 1장 올리기" }))
    await waitFor(() => expect(finish).toBeTypeOf("function"))

    view.unmount()
    finish?.()
    await new Promise<void>((resolve) => setTimeout(resolve, 0))

    expect(onComplete).not.toHaveBeenCalled()
  })

  it("keeps the mounted guard active after the StrictMode effect replay", async () => {
    const user = userEvent.setup()
    const onComplete = vi.fn()
    render(
      <StrictMode>
        <UploadDialog
          open
          brandId="brand-1"
          kind="TRAY"
          request={async ({ file }) => ({ id: file.name })}
          onComplete={onComplete}
        />
      </StrictMode>
    )
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    await user.upload(within(dialog).getByLabelText("사진 선택"), imageFile("strict.jpg"))
    await user.click(within(dialog).getByRole("button", { name: "사진 1장 올리기" }))

    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1))
  })

  it("rejects unsupported and mismatched files locally while keeping valid files uploadable", async () => {
    const user = userEvent.setup()
    const calls: string[] = []
    const request: UploadRequest = async ({ file }) => {
      calls.push(file.name)
      return { id: file.name }
    }
    render(
      <UploadDialog open brandId="brand-1" kind="TRAY" request={request} />
    )
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    const input = within(dialog).getByLabelText("사진 선택")
    fireEvent.change(input, {
      target: {
        files: [
          imageFile("valid.jpg"),
          imageFile("camera.webp", ""),
          imageFile("mismatch.jpg", "image/png"),
          imageFile("notes.pdf", "application/pdf"),
        ],
      },
    })

    expect(within(dialog).getAllByText("대기")).toHaveLength(2)
    expect(within(dialog).getAllByText("실패")).toHaveLength(2)
    expect(within(dialog).getAllByText("지원하지 않는 파일 형식이에요.")).toHaveLength(2)
    expect(within(dialog).getAllByText("JPEG, PNG, WebP 파일을 선택해 주세요.")).toHaveLength(2)
    expect(within(dialog).getByRole("button", { name: "사진 2장 올리기" })).toBeEnabled()

    await user.click(within(dialog).getByRole("button", { name: "사진 2장 올리기" }))
    await waitFor(() => expect(calls).toEqual(["valid.jpg", "camera.webp"]))
    expect(calls).not.toContain("mismatch.jpg")
    expect(calls).not.toContain("notes.pdf")
  })

  it("announces only a short progress summary outside the file list", async () => {
    const user = userEvent.setup()
    render(<UploadDialog open brandId="brand-1" kind="TRAY" />)
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    await user.upload(within(dialog).getByLabelText("사진 선택"), imageFile("private-name.jpg"))

    const live = within(dialog).getByRole("status")
    expect(live).toHaveTextContent("1장 중 0장 처리됨")
    expect(live).not.toHaveTextContent("private-name.jpg")
    expect(within(dialog).getByRole("list")).not.toHaveAttribute("role", "status")
  })

  it("clears the file input so the same file can be selected again after success", async () => {
    const user = userEvent.setup()
    const request: UploadRequest = async ({ file }) => ({ id: file.name })
    render(<UploadDialog open brandId="brand-1" kind="TRAY" request={request} />)
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    const input = within(dialog).getByLabelText("사진 선택")
    const sameFile = imageFile("same.jpg")

    expect(within(dialog).getByRole("button", { name: "사진 0장 올리기" })).toBeDisabled()
    await user.upload(input, sameFile)
    expect(input).toHaveValue("")
    await user.click(within(dialog).getByRole("button", { name: "사진 1장 올리기" }))
    await waitFor(() => expect(within(dialog).getByText("1장 중 1장을 올렸어요.")).toBeInTheDocument())

    await user.upload(input, sameFile)
    expect(within(dialog).getByText("대기")).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "사진 1장 올리기" })).toBeEnabled()
  })

  it("shows a complete failure summary and disables another upload until files are reselected", async () => {
    const user = userEvent.setup()
    const request: UploadRequest = async () => {
      throw {
        body: {
          code: "IMAGE_CORRUPT",
          message: "손상된 사진이에요.",
          action: "다른 사진을 선택해 주세요.",
        },
      }
    }
    render(<UploadDialog open brandId="brand-1" kind="TRAY" request={request} />)
    const dialog = screen.getByRole("dialog", { name: "트레이 사진 올리기" })
    await user.upload(within(dialog).getByLabelText("사진 선택"), imageFile("bad.jpg"))
    const uploadButton = within(dialog).getByRole("button", { name: "사진 1장 올리기" })
    await user.click(uploadButton)

    await waitFor(() => expect(within(dialog).getByText("1장 중 0장을 올렸어요. 1장은 올리지 못했어요.")).toBeInTheDocument())
    expect(uploadButton).toBeDisabled()
  })
})
