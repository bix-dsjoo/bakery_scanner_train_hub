import { useEffect, useState, type ReactElement } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { uploadFiles } from "@/features/uploads/upload-queue"
import type {
  ImageKind,
  UploadRequest,
  UploadResult,
} from "@/features/uploads/types"

const acceptedImages = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"

type SharedProps = {
  brandId: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children?: ReactElement
  request?: UploadRequest
  onComplete?: (results: readonly UploadResult[]) => void
}

export type UploadDialogProps = SharedProps &
  (
    | { kind: "PRODUCT"; productId: string }
    | { kind: "TRAY"; productId?: never }
  )

const labels: Record<UploadResult["status"], string> = {
  waiting: "대기",
  uploading: "업로드 중",
  success: "성공",
  failure: "실패",
}

export function UploadDialog(props: UploadDialogProps) {
  const [results, setResults] = useState<UploadResult[]>([])
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (props.open) {
      setResults([])
      setUploading(false)
    }
  }, [props.open])

  const completed = results.filter(({ status }) =>
    status === "success" || status === "failure"
  ).length
  const succeeded = results.filter(({ status }) => status === "success").length
  const failed = results.filter(({ status }) => status === "failure").length
  const progress = results.length ? Math.round((completed / results.length) * 100) : 0
  const title = props.kind === "PRODUCT" ? "상품 사진 올리기" : "트레이 사진 올리기"

  function selectFiles(files: FileList | null) {
    setResults(
      Array.from(files ?? []).map((file) => ({ file, status: "waiting" }))
    )
  }

  async function startUpload() {
    const files = results.map(({ file }) => file)
    if (!files.length || uploading) return

    setUploading(true)
    const common = {
      files,
      brandId: props.brandId,
      concurrency: 2,
      request: props.request,
      onChange: (next: readonly UploadResult[]) => setResults([...next]),
    }
    const next = props.kind === "PRODUCT"
      ? await uploadFiles({ ...common, kind: "PRODUCT", productId: props.productId })
      : await uploadFiles({ ...common, kind: "TRAY" })
    setUploading(false)
    props.onComplete?.(next)
  }

  function handleOpenChange(open: boolean) {
    if (open) {
      setResults([])
      setUploading(false)
    }
    props.onOpenChange?.(open)
  }

  return (
    <Dialog open={props.open} onOpenChange={handleOpenChange}>
      {props.children && <DialogTrigger render={props.children} />}
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            JPEG, PNG, WebP 사진을 선택해 주세요. 파일별 결과는 따로 표시돼요.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <Input
            type="file"
            aria-label="사진 선택"
            accept={acceptedImages}
            multiple
            autoFocus
            disabled={uploading}
            onChange={(event) => selectFiles(event.target.files)}
          />

          {results.length > 0 && (
            <>
              <div className="grid gap-2">
                <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
                  <span>전체 진행</span>
                  <span>{completed} / {results.length}</span>
                </div>
                <Progress value={progress} aria-label="전체 업로드 진행률" />
              </div>

              <div
                role="status"
                aria-live="polite"
                className="max-h-72 overflow-y-auto border-y border-border"
              >
                <ul className="divide-y divide-border">
                  {results.map((result, index) => (
                    <li key={`${result.file.name}-${index}`} className="grid gap-1 py-3">
                      <div className="flex min-w-0 items-center justify-between gap-3">
                        <span className="truncate text-sm" title={result.file.name}>
                          {result.file.name}
                        </span>
                        <span className="shrink-0 text-xs font-medium">
                          {labels[result.status]}
                        </span>
                      </div>
                      {result.error && (
                        <div className="grid gap-0.5 text-xs text-destructive">
                          <p>{result.error.message}</p>
                          {result.error.action && <p>{result.error.action}</p>}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>

              {completed === results.length && (
                <p className="text-sm tabular-nums">
                  {results.length}장 중 {succeeded}장을 올렸어요.
                  {failed > 0 && ` ${failed}장은 올리지 못했어요.`}
                </p>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <DialogClose render={<Button type="button" variant="outline" />}>
            닫기
          </DialogClose>
          <Button
            type="button"
            onClick={startUpload}
            disabled={!results.length || uploading || completed > 0}
          >
            {uploading ? "올리는 중" : `사진 ${results.length}장 올리기`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export type { ImageKind }
