import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
  const imageFilters = { kind: "PRODUCT" as const, productId, limit: 100 }
  const productsQuery = useQuery({
    queryKey: productsQueryKey(brand?.id ?? ""),
    queryFn: () => listProducts(brand!.id),
    enabled: Boolean(brand),
  })
  const imagesQuery = useQuery({
    queryKey: imagesQueryKey(brand?.id ?? "", imageFilters),
    queryFn: () => listImages(brand!.id, imageFilters),
    enabled: Boolean(brand && productId),
  })
  const product = productsQuery.data?.find((item) => item.id === productId)
  const activeProducts = productsQuery.data?.filter((item) => item.status === "ACTIVE") ?? []

  const reassign = useMutation({
    mutationFn: ({ imageId, nextProductId }: { imageId: string; nextProductId: string }) =>
      changeImageProduct(brand!.id, imageId, nextProductId),
    onSuccess: async () => {
      setActionError(null)
      await queryClient.invalidateQueries({ queryKey: ["images", brand!.id] })
    },
    onError: showActionError,
  })
  const remove = useMutation({
    mutationFn: (imageId: string) => deleteImage(brand!.id, imageId),
    onSuccess: async () => {
      setDeleting(null)
      setActionError(null)
      await queryClient.invalidateQueries({ queryKey: ["images", brand!.id] })
    },
    onError: showActionError,
  })

  function showActionError(error: unknown) {
    setActionError(error instanceof ApiClientError
      ? `${error.body.message} ${error.body.action ?? "잠시 후 다시 시도해 주세요."}`
      : "사진을 변경하지 못했어요. 서버 연결을 확인한 뒤 다시 시도해 주세요.")
  }

  if (brandLoading || productsQuery.isLoading) return <PageState title="상품을 불러오는 중이에요" />
  if (brandError || productsQuery.error) return <PageState title="상품을 불러오지 못했어요" description="서버 연결을 확인한 뒤 페이지를 새로고침해 주세요." />
  if (!brand || !product) return <PageState title="상품을 찾을 수 없어요" description="현재 브랜드의 상품 목록에서 다시 선택해 주세요." />

  const images = imagesQuery.data?.items ?? []
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
          <UploadDialog
            brandId={brand.id}
            kind="PRODUCT"
            productId={product.id}
            onComplete={() => queryClient.invalidateQueries({ queryKey: ["images", brand.id] })}
          >
            <Button size="lg"><PlusIcon /> 상품 사진 추가</Button>
          </UploadDialog>
        </header>

        {actionError && <p role="alert" className="border-b py-3 text-sm text-destructive">{actionError}</p>}
        <section aria-labelledby="product-images-heading">
          <div className="flex h-11 items-center justify-between border-b text-xs font-medium text-muted-foreground">
            <h2 id="product-images-heading">상품 사진</h2><span className="tabular-nums">{images.length}장</span>
          </div>
          <ImageList
            brandId={brand.id}
            images={images}
            loading={imagesQuery.isLoading}
            empty={<PageState title="등록된 상품 사진이 없어요" description="이 상품을 잘 보여주는 사진을 올려 주세요." compact />}
            renderActions={(image) => (
              <div className="flex shrink-0 items-center gap-2">
                <Select
                  value={image.product_id ?? undefined}
                  onValueChange={(nextProductId) => nextProductId && reassign.mutate({ imageId: image.id, nextProductId })}
                >
                  <SelectTrigger aria-label={`${image.original_filename} 상품 변경`} className="hidden w-40 bg-white sm:flex">
                    <SelectValue>{activeProducts.find((item) => item.id === image.product_id)?.name ?? product.name}</SelectValue>
                  </SelectTrigger>
                  <SelectContent align="end">
                    {activeProducts.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button variant="destructive" size="icon-sm" aria-label={`${image.original_filename} 삭제`} onClick={() => setDeleting(image)}><Trash2Icon /></Button>
              </div>
            )}
          />
        </section>
      </div>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>상품 사진 삭제</AlertDialogTitle>
            <AlertDialogDescription>사진 1장과 박스 {deleting?.box_count ?? 0}개가 함께 삭제돼요. 삭제한 사진은 되돌릴 수 없어요.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>취소</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={() => deleting && remove.mutate(deleting.id)}>삭제</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function PageState({ title, description, compact = false }: { title: string; description?: string; compact?: boolean }) {
  return <div className={compact ? "py-14 text-center" : "px-5 py-16 text-center"}><p className="font-medium">{title}</p>{description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}</div>
}
