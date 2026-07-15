import { BrandManagementDialog } from "@/features/brands/brand-management-dialog"
import { useCurrentBrand } from "@/features/brands/brand-provider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function BrandSelector() {
  const { brand, activeBrands, setBrandId, isLoading } = useCurrentBrand()

  return (
    <div className="grid gap-2">
      <div className="grid gap-1.5">
        <span className="text-xs font-medium text-muted-foreground">현재 브랜드</span>
        <Select
          value={brand?.id ?? null}
          onValueChange={(value) => typeof value === "string" && setBrandId(value)}
          disabled={isLoading || activeBrands.length === 0}
        >
          <SelectTrigger aria-label="현재 브랜드" className="w-full bg-white">
            <SelectValue>{brand?.name ?? "활성 브랜드 없음"}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            {activeBrands.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <BrandManagementDialog />
    </div>
  )
}
