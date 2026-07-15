import { useEffect, useId, useState } from "react"
import type { FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  createProduct,
  updateProduct,
  type Product,
} from "@/features/products/api"
import { ApiClientError } from "@/shared/api/client"

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  brandId: string
  product?: Product | null
}

export function ProductFormDialog({
  open,
  onOpenChange,
  brandId,
  product,
}: Props) {
  const queryClient = useQueryClient()
  const [code, setCode] = useState(product?.code ?? "")
  const [name, setName] = useState(product?.name ?? "")
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const codeId = useId()
  const nameId = useId()
  const codeErrorId = useId()
  const nameErrorId = useId()

  useEffect(() => {
    if (!open) return
    setCode(product?.code ?? "")
    setName(product?.name ?? "")
    setFieldErrors({})
    setFormError(null)
  }, [open, product])

  const mutation = useMutation({
    mutationFn: () => {
      const input = { code: code.trim(), name: name.trim() }
      return product
        ? updateProduct(product, input)
        : createProduct(brandId, input)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["products", brandId] })
      onOpenChange(false)
    },
    onError: (error) => {
      if (error instanceof ApiClientError) {
        const errors = error.body.field_errors ?? {}
        setFieldErrors(errors)
        setFormError(Object.keys(errors).length ? null : error.body.message)
      } else {
        setFormError("상품 정보를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.")
      }
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFieldErrors({})
    setFormError(null)
    mutation.mutate()
  }

  const title = product ? "상품 수정" : "상품 추가"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="contents">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              현재 브랜드에서 사용할 상품 코드와 이름을 입력해 주세요.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor={codeId}>상품 코드</Label>
              <Input
                id={codeId}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                maxLength={50}
                autoFocus
                required
                aria-invalid={Boolean(fieldErrors.code)}
                aria-describedby={fieldErrors.code ? codeErrorId : undefined}
              />
              {fieldErrors.code && (
                <p id={codeErrorId} className="text-xs text-destructive">
                  {fieldErrors.code}
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor={nameId}>상품명</Label>
              <Input
                id={nameId}
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={100}
                required
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? nameErrorId : undefined}
              />
              {fieldErrors.name && (
                <p id={nameErrorId} className="text-xs text-destructive">
                  {fieldErrors.name}
                </p>
              )}
            </div>
            {formError && <p className="text-xs text-destructive">{formError}</p>}
          </div>
          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>
              취소
            </DialogClose>
            <Button
              type="submit"
              disabled={!code.trim() || !name.trim() || mutation.isPending}
            >
              {mutation.isPending ? "저장 중" : product ? "변경 저장" : "상품 추가"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
