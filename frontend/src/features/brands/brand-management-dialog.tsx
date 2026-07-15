import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { BanIcon, PencilIcon, PlusIcon } from "lucide-react"

import {
  brandsQueryKey,
  deactivateBrand,
  type Brand,
} from "@/features/brands/api"
import { BrandFormDialog } from "@/features/brands/brand-form-dialog"
import { useCurrentBrand } from "@/features/brands/brand-provider"
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ApiClientError } from "@/shared/api/client"

export function BrandManagementDialog() {
  const { brand: currentBrand, brands } = useCurrentBrand()
  const queryClient = useQueryClient()
  const [managementOpen, setManagementOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingBrand, setEditingBrand] = useState<Brand | null>(null)
  const [deactivatingBrand, setDeactivatingBrand] = useState<Brand | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (brandId: string) => deactivateBrand(brandId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: brandsQueryKey })
      setDeactivatingBrand(null)
      setManagementOpen(false)
    },
    onError: (mutationError) => {
      setError(
        mutationError instanceof ApiClientError
          ? mutationError.body.message
          : "브랜드를 비활성화하지 못했어요. 잠시 후 다시 시도해 주세요."
      )
    },
  })

  return (
    <>
      <Dialog open={managementOpen} onOpenChange={setManagementOpen}>
        <DialogTrigger render={<Button variant="outline" className="w-full" />}>
          브랜드 관리
        </DialogTrigger>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>브랜드 관리</DialogTitle>
            <DialogDescription>
              브랜드 이름을 바꾸거나 더 이상 사용하지 않는 브랜드를 비활성화합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={() => setCreateOpen(true)}>
              <PlusIcon /> 브랜드 추가
            </Button>
          </div>
          <ul className="max-h-80 divide-y overflow-y-auto border-y" aria-label="브랜드 목록">
            {brands.map((brand) => (
              <li key={brand.id} className="flex min-h-14 items-center gap-3 py-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{brand.name}</span>
                    {brand.id === currentBrand?.id && <Badge variant="outline">현재</Badge>}
                    {brand.status === "INACTIVE" && <Badge variant="secondary">비활성</Badge>}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`${brand.name} 수정`}
                  onClick={() => setEditingBrand(brand)}
                >
                  <PencilIcon /> 수정
                </Button>
                {brand.status === "ACTIVE" && (
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    aria-label={`${brand.name} 비활성화`}
                    onClick={() => {
                      setError(null)
                      setDeactivatingBrand(brand)
                    }}
                  >
                    <BanIcon /> 비활성화
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>

      <BrandFormDialog open={createOpen} onOpenChange={setCreateOpen} />
      <BrandFormDialog
        open={Boolean(editingBrand)}
        onOpenChange={(open) => !open && setEditingBrand(null)}
        brand={editingBrand}
      />

      <AlertDialog
        open={Boolean(deactivatingBrand)}
        onOpenChange={(open) => !open && setDeactivatingBrand(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>브랜드 비활성화</AlertDialogTitle>
            <AlertDialogDescription>
              {deactivatingBrand?.name}의 기존 데이터는 유지됩니다. 비활성화 후에는 새 작업에 이 브랜드를 선택할 수 없습니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={mutation.isPending}
              onClick={() => deactivatingBrand && mutation.mutate(deactivatingBrand.id)}
            >
              {mutation.isPending ? "처리 중" : "비활성화"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
