import { useEffect, useRef, useState } from "react"
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeftIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { Link, useParams } from "react-router-dom"

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
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCurrentBrand } from "@/features/brands/brand-provider"
import {
  changeImageProduct,
  deleteImage,
  imagesQueryKey,
  listImages,
  type ImageRecord,
} from "@/features/images/api"
import { ImageList } from "@/features/images/image-list"
import { listProducts, productsQueryKey } from "@/features/products/api"
import { UploadDialog } from "@/features/uploads/upload-dialog"
import { ApiClientError } from "@/shared/api/client"

export function ProductDetailPage() {
  const { productId = "" } = useParams()
  const { brand, isLoading: brandLoading, error: brandError } = useCurrentBrand()
  const queryClient = useQueryClient()
  const [deleting, setDeleting] = useState<ImageRecord | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const currentBrandIdRef = useRef(brand?.id)
  currentBrandIdRef.current = brand?.id
  useEffect(() => {
    setDeleting(null)
    setActionError(null)
    setDeleteError(null)
  }, [brand?.id])
  const imageFilters = { kind: "PRODUCT" as const, productId, limit: 50 }
  const productsQuery = useQuery({
    queryKey: productsQueryKey(brand?.id ?? ""),
    queryFn: () => listProducts(brand!.id),
    enabled: Boolean(brand),
  })
  const imagesQuery = useInfiniteQuery({
    queryKey: imagesQueryKey(brand?.id ?? "", imageFilters),
    queryFn: ({ pageParam }) => listImages(brand!.id, { ...imageFilters, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: Boolean(brand && productId),
  })
  const product = productsQuery.data?.find((item) => item.id === productId)
  const activeProducts = productsQuery.data?.filter((item) => item.brand_id === brand?.id && item.status === "ACTIVE") ?? []

  const reassign = useMutation({
    mutationFn: ({ brandId, imageId, nextProductId }: { brandId: string; imageId: string; nextProductId: string }) =>
      changeImageProduct(brandId, imageId, nextProductId),
    onSuccess: async (_, variables) => {
      if (currentBrandIdRef.current !== variables.brandId) return
      setActionError(null)
      await queryClient.invalidateQueries({ queryKey: ["images", variables.brandId] })
    },
    onError: (error, variables) => {
      if (currentBrandIdRef.current === variables.brandId) showActionError(error)
    },
  })
  const remove = useMutation({
    mutationFn: ({ brandId, imageId }: { brandId: string; imageId: string }) => deleteImage(brandId, imageId),
    onSuccess: async (_, variables) => {
      if (currentBrandIdRef.current !== variables.brandId) return
      setDeleting(null)
      setDeleteError(null)
      await queryClient.invalidateQueries({ queryKey: ["images", variables.brandId] })
    },
    onError: (error, variables) => {
      if (currentBrandIdRef.current === variables.brandId) setDeleteError(toActionError(error, "상품 사진을 삭제하지 못했어요."))
    },
  })

  function showActionError(error: unknown) {
    setActionError(toActionError(error, "사진을 변경하지 못했어요."))
  }

  if (brandLoading || productsQuery.isLoading) return <PageState title="상품을 불러오는 중이에요" />
  if (brandError || productsQuery.error) return <PageState title="상품을 불러오지 못했어요" description="서버 연결을 확인한 뒤 페이지를 새로고침해 주세요." />
  if (!brand || !product) return <PageState title="상품을 찾을 수 없어요" description="현재 브랜드의 상품 목록에서 다시 선택해 주세요." />

  const images = imagesQuery.data?.pages.flatMap((page) => page.items) ?? []
  return (
    <div className="px-5 py-8 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-6xl">
        <Link to="/products" className="mb-5 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
          <ArrowLeftIcon className="size-4" /> 상품 목록
        </Link>
        <header className="flex flex-col gap-5 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="mb-1 truncate text-xs font-medium text-muted-foreground">{brand.name} · {product.code}</p>
            <h1 className="truncate text-2xl leading-8 font-bold tracking-[-0.02em]">{product.name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">분류기 학습에 사용할 상품 사진을 관리합니다.</p>
          </div>
          {product.status === "ACTIVE" ? (
            <UploadDialog
              key={brand.id}
              brandId={brand.id}
              kind="PRODUCT"
              productId={product.id}
              onComplete={() => currentBrandIdRef.current === brand.id && queryClient.invalidateQueries({ queryKey: ["images", brand.id] })}
            >
              <Button size="lg"><PlusIcon /> 상품 사진 추가</Button>
            </UploadDialog>
          ) : (
            <p role="alert" className="max-w-sm text-sm text-destructive">비활성 상품에는 사진을 추가할 수 없어요. 상품을 활성화한 뒤 다시 시도해 주세요.</p>
          )}
        </header>

        {actionError && <p role="alert" className="border-b py-3 text-sm text-destructive">{actionError}</p>}
        <section aria-labelledby="product-images-heading">
          <div className="flex h-11 items-center justify-between border-b text-xs font-medium text-muted-foreground">
            <h2 id="product-images-heading">상품 사진</h2><span className="tabular-nums">{images.length}장</span>
          </div>
          {imagesQuery.error ? (
            <p role="alert" className="py-14 text-center text-sm text-destructive">
              {toActionError(imagesQuery.error, "상품 사진을 불러오지 못했어요.")}
            </p>
          ) : <ImageList
            brandId={brand.id}
            images={images}
            loading={imagesQuery.isLoading}
            empty={<PageState title="등록된 상품 사진이 없어요" description="이 상품을 잘 보여주는 사진을 올려 주세요." compact />}
            renderActions={(image) => (
              <div className="flex min-w-0 shrink items-center gap-1 sm:shrink-0 sm:gap-2">
                <Select
                  value={image.product_id ?? undefined}
                  onValueChange={(nextProductId) => nextProductId && reassign.mutate({ brandId: brand.id, imageId: image.id, nextProductId })}
                >
                  <SelectTrigger aria-label={`${image.original_filename} 상품 변경`} className="w-28 min-w-0 bg-white sm:w-40">
                    <SelectValue>{activeProducts.find((item) => item.id === image.product_id)?.name ?? product.name}</SelectValue>
                  </SelectTrigger>
                  <SelectContent align="end">
                    {activeProducts.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button variant="destructive" size="icon-sm" aria-label={`${image.original_filename} 삭제`} onClick={() => { setDeleteError(null); setDeleting(image) }}><Trash2Icon /></Button>
              </div>
            )}
          />}
          {imagesQuery.hasNextPage && <div className="flex justify-center border-t py-5"><Button variant="outline" onClick={() => imagesQuery.fetchNextPage()} disabled={imagesQuery.isFetchingNextPage}>{imagesQuery.isFetchingNextPage ? "불러오는 중" : "다음 사진 불러오기"}</Button></div>}
        </section>
      </div>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open && !remove.isPending) setDeleting(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>상품 사진 삭제</AlertDialogTitle>
            <AlertDialogDescription>사진 1장과 박스 {deleting?.box_count ?? 0}개가 함께 삭제돼요. 삭제한 사진은 되돌릴 수 없어요.</AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && <p role="alert" className="text-sm text-destructive">{deleteError}</p>}
          <AlertDialogFooter><AlertDialogCancel disabled={remove.isPending}>취소</AlertDialogCancel><AlertDialogAction variant="destructive" disabled={remove.isPending} onClick={() => deleting && !remove.isPending && remove.mutate({ brandId: brand.id, imageId: deleting.id })}>{remove.isPending ? "삭제 중" : "삭제"}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function toActionError(error: unknown, fallback: string) {
  return error instanceof ApiClientError
    ? `${error.body.message} ${error.body.action ?? "잠시 후 다시 시도해 주세요."}`
    : `${fallback} 서버 연결을 확인한 뒤 다시 시도해 주세요.`
}

function PageState({ title, description, compact = false }: { title: string; description?: string; compact?: boolean }) {
  return <div className={compact ? "py-14 text-center" : "px-5 py-16 text-center"}><p className="font-medium">{title}</p>{description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}</div>
}
