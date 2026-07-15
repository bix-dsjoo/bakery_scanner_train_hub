import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BanIcon, PencilIcon, PlusIcon, SearchIcon } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { BrandFormDialog } from "@/features/brands/brand-form-dialog"
import { useCurrentBrand } from "@/features/brands/brand-provider"
import {
  deactivateProduct,
  listProducts,
  productsQueryKey,
  type Product,
} from "@/features/products/api"
import { ProductFormDialog } from "@/features/products/product-form-dialog"
import { ApiClientError } from "@/shared/api/client"

type StatusFilter = "ALL" | "ACTIVE" | "INACTIVE"

export function ProductsPage() {
  const { brand, isLoading: brandsLoading, error: brandsError } = useCurrentBrand()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState<StatusFilter>("ALL")
  const [createOpen, setCreateOpen] = useState(false)
  const [createBrandOpen, setCreateBrandOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [deactivatingProduct, setDeactivatingProduct] = useState<Product | null>(null)
  const [deactivateError, setDeactivateError] = useState<string | null>(null)

  const filters = {
    query: search.trim() || undefined,
    status: status === "ALL" ? undefined : status,
  }
  const productsQuery = useQuery({
    queryKey: productsQueryKey(brand?.id ?? "", filters),
    queryFn: () => listProducts(brand!.id, filters),
    enabled: Boolean(brand),
  })

  const deactivateMutation = useMutation({
    mutationFn: (product: Product) => deactivateProduct(product),
    onSuccess: async (_, product) => {
      await queryClient.invalidateQueries({ queryKey: ["products", product.brand_id] })
      setDeactivatingProduct(null)
    },
    onError: (error) => {
      setDeactivateError(
        error instanceof ApiClientError
          ? error.body.message
          : "상품을 비활성화하지 못했어요. 잠시 후 다시 시도해 주세요."
      )
    },
  })

  if (brandsLoading) {
    return <PageMessage title="브랜드를 불러오는 중이에요" />
  }

  if (brandsError) {
    return (
      <PageMessage
        title="브랜드를 불러오지 못했어요"
        description="서버 연결을 확인한 뒤 페이지를 새로고침해 주세요."
      />
    )
  }

  if (!brand) {
    return (
      <div className="mx-auto flex min-h-svh max-w-xl flex-col justify-center px-5 py-12 text-center sm:px-8">
        <div aria-hidden="true" className="mx-auto mb-5 flex size-10 items-center justify-center">
          <span className="h-8 w-1 rotate-[28deg] rounded-full bg-ring" />
          <span className="-ml-1 h-8 w-1 -rotate-[28deg] rounded-full bg-black" />
        </div>
        <h1 className="text-2xl leading-8 font-bold tracking-[-0.02em]">
          활성 브랜드가 없어요
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          상품을 관리하려면 먼저 사용할 브랜드를 만들어 주세요.
        </p>
        <div className="mt-6">
          <Button size="lg" onClick={() => setCreateBrandOpen(true)}>
            <PlusIcon /> 브랜드 만들기
          </Button>
        </div>
        <BrandFormDialog
          open={createBrandOpen}
          onOpenChange={setCreateBrandOpen}
          createTitle="브랜드 만들기"
        />
      </div>
    )
  }

  const products = productsQuery.data ?? []

  return (
    <div className="px-5 py-8 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-5 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="mb-1 truncate text-xs font-medium text-muted-foreground">
              {brand.name}
            </p>
            <h1 className="text-2xl leading-8 font-bold tracking-[-0.02em]">
              상품 관리
            </h1>
          </div>
          <Button size="lg" onClick={() => setCreateOpen(true)}>
            <PlusIcon /> 상품 추가
          </Button>
        </header>

        <section aria-label="상품 검색과 필터" className="flex flex-col gap-3 border-b py-4 sm:flex-row">
          <label className="relative block min-w-0 flex-1 sm:max-w-sm">
            <span className="sr-only">상품 검색</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="bg-white pl-9"
              aria-label="상품 검색"
              placeholder="상품 코드 또는 상품명 검색"
            />
          </label>
          <Select value={status} onValueChange={(value) => setStatus(value as StatusFilter)}>
            <SelectTrigger aria-label="상품 상태" className="w-full bg-white sm:w-36">
              <SelectValue>
                {status === "ALL" ? "모든 상태" : status === "ACTIVE" ? "활성" : "비활성"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="ALL">모든 상태</SelectItem>
              <SelectItem value="ACTIVE">활성</SelectItem>
              <SelectItem value="INACTIVE">비활성</SelectItem>
            </SelectContent>
          </Select>
        </section>

        <section aria-labelledby="products-heading">
          <div className="flex h-11 items-center justify-between border-b text-xs font-medium text-muted-foreground">
            <h2 id="products-heading">상품 목록</h2>
            <span className="tabular-nums">{products.length}개</span>
          </div>
          {productsQuery.isLoading ? (
            <PageMessage title="상품을 불러오는 중이에요" compact />
          ) : productsQuery.error ? (
            <PageMessage
              title="상품을 불러오지 못했어요"
              description="서버 연결을 확인한 뒤 다시 시도해 주세요."
              compact
            />
          ) : products.length === 0 ? (
            <PageMessage
              title={search || status !== "ALL" ? "조건에 맞는 상품이 없어요" : "첫 상품을 등록해 주세요"}
              description={search || status !== "ALL" ? "검색어나 상태 조건을 바꿔 주세요." : undefined}
              compact
            />
          ) : (
            <ul className="divide-y" aria-label="상품 목록">
              {products.map((product) => (
                <li key={product.id} className="flex min-h-15 items-center gap-4 py-2">
                  <div className="min-w-0 flex-1 sm:grid sm:grid-cols-[minmax(0,1.5fr)_minmax(8rem,0.8fr)] sm:items-center sm:gap-6">
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate font-medium">{product.name}</span>
                        {product.status === "INACTIVE" && (
                          <Badge variant="secondary">비활성</Badge>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground sm:hidden">
                        {product.code}
                      </p>
                    </div>
                    <span className="hidden truncate text-sm text-muted-foreground sm:block">
                      {product.code}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`${product.name} 수정`}
                      onClick={() => setEditingProduct(product)}
                    >
                      <PencilIcon /> <span className="hidden sm:inline">수정</span>
                    </Button>
                    {product.status === "ACTIVE" && (
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        aria-label={`${product.name} 비활성화`}
                        onClick={() => {
                          setDeactivateError(null)
                          setDeactivatingProduct(product)
                        }}
                      >
                        <BanIcon /> <span className="hidden sm:inline">비활성화</span>
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <ProductFormDialog open={createOpen} onOpenChange={setCreateOpen} brandId={brand.id} />
      <ProductFormDialog
        open={Boolean(editingProduct)}
        onOpenChange={(open) => !open && setEditingProduct(null)}
        brandId={brand.id}
        product={editingProduct}
      />

      <AlertDialog
        open={Boolean(deactivatingProduct)}
        onOpenChange={(open) => !open && setDeactivatingProduct(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>상품 비활성화</AlertDialogTitle>
            <AlertDialogDescription>
              {deactivatingProduct?.name}은 기존 라벨에 유지되지만 새 박스에는 지정할 수 없습니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deactivateError && <p className="text-xs text-destructive">{deactivateError}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deactivateMutation.isPending}
              onClick={() => deactivatingProduct && deactivateMutation.mutate(deactivatingProduct)}
            >
              {deactivateMutation.isPending ? "처리 중" : "비활성화"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function PageMessage({
  title,
  description,
  compact = false,
}: {
  title: string
  description?: string
  compact?: boolean
}) {
  return (
    <div className={compact ? "py-16 text-center" : "px-5 py-12 text-center"}>
      <p className="font-medium">{title}</p>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
    </div>
  )
}
