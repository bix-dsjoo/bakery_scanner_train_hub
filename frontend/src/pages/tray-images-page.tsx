import { useEffect, useRef, useState } from "react"
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PlusIcon, Trash2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentBrand } from "@/features/brands/brand-provider"
import { deleteImage, imagesQueryKey, listImages, type ImageRecord, type LabelingStatus } from "@/features/images/api"
import { ImageFilters } from "@/features/images/image-filters"
import { ImageList } from "@/features/images/image-list"
import { listProducts, productsQueryKey } from "@/features/products/api"
import { UploadDialog } from "@/features/uploads/upload-dialog"
import type { UploadResult } from "@/features/uploads/types"
import { ApiClientError } from "@/shared/api/client"

export function TrayImagesPage() {
  const { brand, isLoading: brandLoading, error: brandError } = useCurrentBrand()
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<LabelingStatus>("UNLABELED")
  const [filename, setFilename] = useState("")
  const [productFilter, setProductFilter] = useState({ brandId: brand?.id ?? null, value: "ALL" })
  const [uploadedImageId, setUploadedImageId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<ImageRecord | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const currentBrandIdRef = useRef(brand?.id)
  currentBrandIdRef.current = brand?.id
  const productId = productFilter.brandId === brand?.id ? productFilter.value : "ALL"
  useEffect(() => {
    setProductFilter({ brandId: brand?.id ?? null, value: "ALL" })
    setUploadedImageId(null)
    setDeleting(null)
    setDeleteError(null)
  }, [brand?.id])
  const filters = {
    kind: "TRAY" as const,
    status,
    filename: filename.trim() || undefined,
    productId: productId === "ALL" ? undefined : productId,
    limit: 50,
  }
  const productsQuery = useQuery({
    queryKey: productsQueryKey(brand?.id ?? "", { status: "ACTIVE" }),
    queryFn: () => listProducts(brand!.id, { status: "ACTIVE" }),
    enabled: Boolean(brand),
  })
  const imagesQuery = useInfiniteQuery({
    queryKey: imagesQueryKey(brand?.id ?? "", filters),
    queryFn: ({ pageParam }) => listImages(brand!.id, { ...filters, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: Boolean(brand),
  })
  const images = imagesQuery.data?.pages.flatMap((page) => page.items) ?? []
  const filtered = Boolean(filename.trim() || productId !== "ALL")
  const productFilterError = productsQuery.error instanceof ApiClientError
    ? `${productsQuery.error.body.message} ${productsQuery.error.body.action ?? "잠시 후 다시 시도해 주세요."}`
    : productsQuery.error
      ? "상품을 불러오지 못했어요. 서버 연결을 확인한 뒤 다시 시도해 주세요."
      : undefined
  const remove = useMutation({
    mutationFn: ({ brandId, imageId }: { brandId: string; imageId: string }) => deleteImage(brandId, imageId),
    onSuccess: async (_, variables) => {
      if (currentBrandIdRef.current !== variables.brandId) return
      setDeleting(null)
      setDeleteError(null)
      await queryClient.invalidateQueries({ queryKey: ["images", variables.brandId] })
    },
    onError: (error, variables) => {
      if (currentBrandIdRef.current !== variables.brandId) return
      setDeleteError(error instanceof ApiClientError
        ? `${error.body.message} ${error.body.action ?? "잠시 후 다시 시도해 주세요."}`
        : "트레이 사진을 삭제하지 못했어요. 서버 연결을 확인한 뒤 다시 시도해 주세요.")
    },
  })

  async function handleUploadComplete(uploadBrandId: string, results: readonly UploadResult[]) {
    if (currentBrandIdRef.current !== uploadBrandId) return
    const firstSuccess = results.find((result) => result.status === "success" && result.image)
    setUploadedImageId(firstSuccess?.image?.id ?? null)
    await queryClient.invalidateQueries({ queryKey: ["images", uploadBrandId] })
  }

  if (brandLoading) return <PageState title="브랜드를 불러오는 중이에요" />
  if (brandError) return <PageState title="브랜드를 불러오지 못했어요" description="서버 연결을 확인한 뒤 페이지를 새로고침해 주세요." />
  if (!brand) return <PageState title="활성 브랜드가 없어요" description="브랜드를 만든 뒤 트레이 사진을 올려 주세요." />

  return (
    <div className="px-5 py-8 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-5 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0"><p className="mb-1 truncate text-xs font-medium text-muted-foreground">{brand.name}</p><h1 className="text-2xl leading-8 font-bold tracking-[-0.02em]">트레이 사진</h1><p className="mt-1 text-sm text-muted-foreground">라벨이 필요한 사진을 찾아 작업을 시작합니다.</p></div>
          <UploadDialog key={brand.id} brandId={brand.id} kind="TRAY" onComplete={(results) => handleUploadComplete(brand.id, results)}>
            <Button size="lg" variant={uploadedImageId ? "outline" : "default"}><PlusIcon /> 트레이 사진 올리기</Button>
          </UploadDialog>
        </header>

        {uploadedImageId && (
          <div className="flex items-center justify-between gap-4 border-b bg-accent px-4 py-3">
            <p className="text-sm">사진을 올렸어요. 라벨링 편집기는 다음 단계에서 사용할 수 있어요.</p>
            <Button disabled>첫 사진 라벨링하기</Button>
          </div>
        )}

        <Tabs value={status} onValueChange={(value) => setStatus(value as LabelingStatus)} className="pt-4">
          <TabsList variant="line" aria-label="트레이 사진 상태">
            <TabsTrigger value="UNLABELED">라벨 필요</TabsTrigger>
            <TabsTrigger value="COMPLETED">완료</TabsTrigger>
          </TabsList>
        </Tabs>
        <ImageFilters filename={filename} onFilenameChange={setFilename} productId={productId} onProductChange={(value) => setProductFilter({ brandId: brand.id, value })} products={(productsQuery.data ?? []).filter((product) => product.brand_id === brand.id && product.status === "ACTIVE")} productDisabled={productsQuery.isLoading || Boolean(productsQuery.error)} productError={productFilterError} />

        <section aria-labelledby="tray-images-heading">
          <div className="flex h-11 items-center justify-between border-b text-xs font-medium text-muted-foreground"><h2 id="tray-images-heading">사진 목록</h2><span className="tabular-nums">{images.length}장</span></div>
          {imagesQuery.error ? (
            <PageState title="트레이 사진을 불러오지 못했어요" description="서버 연결을 확인한 뒤 다시 시도해 주세요." compact />
          ) : (
            <ImageList
              brandId={brand.id}
              images={images}
              loading={imagesQuery.isLoading}
              empty={filtered
                ? <PageState title="조건에 맞는 사진이 없어요" description="검색어나 상품 조건을 바꿔 주세요." compact action={<Button variant="outline" onClick={() => { setFilename(""); setProductFilter({ brandId: brand.id, value: "ALL" }) }}>필터 초기화</Button>} />
                : <PageState title={status === "UNLABELED" ? "라벨링할 트레이 사진이 없어요" : "완료한 트레이 사진이 없어요"} description="트레이 사진을 올리면 이곳에서 찾을 수 있어요." compact />}
              renderMetadata={(image) => <span>박스 {image.box_count}개</span>}
              renderActions={(image) => <Button variant="destructive" size="icon-sm" aria-label={`${image.original_filename} 삭제`} onClick={() => { setDeleteError(null); setDeleting(image) }}><Trash2Icon /></Button>}
            />
          )}
          {imagesQuery.hasNextPage && <div className="flex justify-center border-t py-5"><Button variant="outline" onClick={() => imagesQuery.fetchNextPage()} disabled={imagesQuery.isFetchingNextPage}>{imagesQuery.isFetchingNextPage ? "불러오는 중" : "다음 사진 불러오기"}</Button></div>}
        </section>
      </div>
      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open && !remove.isPending) setDeleting(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>트레이 사진 삭제</AlertDialogTitle><AlertDialogDescription>사진 1장과 박스 {deleting?.box_count ?? 0}개가 함께 삭제돼요. 삭제한 사진은 되돌릴 수 없어요.</AlertDialogDescription></AlertDialogHeader>
          {deleteError && <p role="alert" className="text-sm text-destructive">{deleteError}</p>}
          <AlertDialogFooter><AlertDialogCancel disabled={remove.isPending}>취소</AlertDialogCancel><AlertDialogAction variant="destructive" disabled={remove.isPending} onClick={() => deleting && !remove.isPending && remove.mutate({ brandId: brand.id, imageId: deleting.id })}>{remove.isPending ? "삭제 중" : "삭제"}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function PageState({ title, description, compact = false, action }: { title: string; description?: string; compact?: boolean; action?: React.ReactNode }) {
  return <div className={compact ? "py-14 text-center" : "px-5 py-16 text-center"}><p className="font-medium">{title}</p>{description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}{action && <div className="mt-4">{action}</div>}</div>
}
