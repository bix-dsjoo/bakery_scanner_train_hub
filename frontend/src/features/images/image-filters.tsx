import { SearchIcon } from "lucide-react"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Product } from "@/features/products/api"

export function ImageFilters({
  filename,
  onFilenameChange,
  productId,
  onProductChange,
  products,
  productDisabled = false,
  productError,
}: {
  filename: string
  onFilenameChange: (value: string) => void
  productId: string
  onProductChange: (value: string) => void
  products: Product[]
  productDisabled?: boolean
  productError?: string
}) {
  const selected = products.find((product) => product.id === productId)
  return (
    <section aria-label="사진 검색과 필터" className="flex flex-col gap-3 border-b py-4 sm:flex-row sm:flex-wrap">
      <label className="relative block min-w-0 flex-1 sm:max-w-sm">
        <span className="sr-only">파일명 검색</span>
        <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="파일명 검색"
          value={filename}
          onChange={(event) => onFilenameChange(event.target.value)}
          placeholder="파일명 검색"
          className="bg-white pl-9"
        />
      </label>
      <Select disabled={productDisabled} value={productId} onValueChange={(value) => value && onProductChange(value)}>
        <SelectTrigger aria-label="상품 필터" className="w-full bg-white sm:w-48">
          <SelectValue>{selected?.name ?? "모든 상품"}</SelectValue>
        </SelectTrigger>
        <SelectContent align="start">
          <SelectItem value="ALL">모든 상품</SelectItem>
          {products.map((product) => <SelectItem key={product.id} value={product.id}>{product.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {productError && <p role="alert" className="text-sm text-destructive sm:basis-full">{productError}</p>}
    </section>
  )
}
