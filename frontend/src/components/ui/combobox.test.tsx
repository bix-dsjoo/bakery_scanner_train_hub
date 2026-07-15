import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  Combobox,
  ComboboxChip,
  ComboboxChipRemove,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxClear,
  ComboboxInput,
} from "@/components/ui/combobox"
import { TooltipProvider } from "@/components/ui/tooltip"

afterEach(cleanup)

describe("Combobox icon-only actions", () => {
  it("gives the automatic clear button a Korean name and tooltip", async () => {
    const user = userEvent.setup()

    render(
      <TooltipProvider delay={0}>
        <Combobox items={["크루아상"]} defaultValue="크루아상">
          <ComboboxInput
            aria-label="상품"
            showClear
            showTrigger={false}
          />
        </Combobox>
      </TooltipProvider>
    )

    const clearButton = screen.getByRole("button", { name: "선택 지우기" })
    await user.hover(clearButton)

    expect(await screen.findByText("선택 지우기")).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )

    await user.click(clearButton)
    expect(screen.getByRole("combobox", { name: "상품" })).toHaveValue("")
  })

  it("keeps a consumer-provided clear name in the button and tooltip", async () => {
    const user = userEvent.setup()

    render(
      <TooltipProvider delay={0}>
        <Combobox items={["크루아상"]} defaultValue="크루아상">
          <ComboboxInput aria-label="상품" showTrigger={false}>
            <ComboboxClear aria-label="상품 선택 초기화" keepMounted />
          </ComboboxInput>
        </Combobox>
      </TooltipProvider>
    )

    const clearButton = screen.getByRole("button", {
      name: "상품 선택 초기화",
    })
    await user.hover(clearButton)

    expect(await screen.findByText("상품 선택 초기화")).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )
  })

  it("gives the automatic chip remove button a Korean name and tooltip", async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()

    render(
      <TooltipProvider delay={0}>
        <Combobox
          items={["크루아상"]}
          defaultValue={["크루아상"]}
          multiple
          onValueChange={onValueChange}
        >
          <ComboboxChips>
            <ComboboxChip>크루아상</ComboboxChip>
            <ComboboxChipsInput aria-label="상품" />
          </ComboboxChips>
        </Combobox>
      </TooltipProvider>
    )

    const removeButton = screen.getByRole("button", {
      name: "선택 항목 삭제",
    })
    await user.hover(removeButton)

    expect(await screen.findByText("선택 항목 삭제")).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )

    await user.click(removeButton)
    expect(onValueChange).toHaveBeenCalledWith([], expect.anything())
  })

  it("keeps a consumer-provided chip remove name in the button and tooltip", async () => {
    const user = userEvent.setup()

    render(
      <TooltipProvider delay={0}>
        <Combobox
          items={["크루아상"]}
          defaultValue={["크루아상"]}
          multiple
        >
          <ComboboxChips>
            <ComboboxChip showRemove={false}>
              크루아상
              <ComboboxChipRemove aria-label="크루아상 선택 삭제" />
            </ComboboxChip>
            <ComboboxChipsInput aria-label="상품" />
          </ComboboxChips>
        </Combobox>
      </TooltipProvider>
    )

    const removeButton = screen.getByRole("button", {
      name: "크루아상 선택 삭제",
    })
    await user.hover(removeButton)

    expect(await screen.findByText("크루아상 선택 삭제")).toHaveAttribute(
      "data-slot",
      "tooltip-content"
    )
  })
})
