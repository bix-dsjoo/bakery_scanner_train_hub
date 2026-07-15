import { useEffect, useId, useState } from "react"
import type { FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  brandsQueryKey,
  createBrand,
  updateBrand,
  type Brand,
} from "@/features/brands/api"
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
import { ApiClientError } from "@/shared/api/client"

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  brand?: Brand | null
  createTitle?: string
}

export function BrandFormDialog({
  open,
  onOpenChange,
  brand,
  createTitle = "브랜드 추가",
}: Props) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(brand?.name ?? "")
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const inputId = useId()
  const errorId = useId()
  const title = brand ? "브랜드 수정" : createTitle

  useEffect(() => {
    if (!open) return
    setName(brand?.name ?? "")
    setFieldError(null)
    setFormError(null)
  }, [brand, open])

  const mutation = useMutation({
    mutationFn: () =>
      brand
        ? updateBrand(brand.id, { name: name.trim() })
        : createBrand({ name: name.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: brandsQueryKey })
      onOpenChange(false)
    },
    onError: (error) => {
      if (error instanceof ApiClientError) {
        setFieldError(error.body.field_errors?.name ?? null)
        setFormError(error.body.field_errors?.name ? null : error.body.message)
      } else {
        setFormError("브랜드 정보를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.")
      }
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFieldError(null)
    setFormError(null)
    mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="contents">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              작업 목록에서 구분하기 쉬운 브랜드 이름을 입력해 주세요.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor={inputId}>브랜드 이름</Label>
            <Input
              id={inputId}
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
              maxLength={100}
              aria-invalid={Boolean(fieldError)}
              aria-describedby={fieldError ? errorId : undefined}
              required
            />
            {fieldError && (
              <p id={errorId} className="text-xs text-destructive">
                {fieldError}
              </p>
            )}
            {formError && <p className="text-xs text-destructive">{formError}</p>}
          </div>
          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>
              취소
            </DialogClose>
            <Button type="submit" disabled={!name.trim() || mutation.isPending}>
              {mutation.isPending ? "저장 중" : brand ? "변경 저장" : title}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
