import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

const stylesheet = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8")

describe("design tokens", () => {
  it("maps the approved Information Blue to a semantic Tailwind color", () => {
    expect(stylesheet).toMatch(/--information:\s*#05498D;/)
    expect(stylesheet).toMatch(
      /--color-information:\s*var\(--information\);/
    )
  })
})
