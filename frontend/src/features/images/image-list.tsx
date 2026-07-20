import { useEffect, useState, type ReactNode } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { imageThumbnailUrl, type ImageRecord } from "@/features/images/api"

export function useDelayedLoading(loading: boolean, delay = 200) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!loading) {
      setVisible(false)
      return
    }
    const timer = window.setTimeout(() => setVisible(true), delay)
    return () => window.clearTimeout(timer)
  }, [delay, loading])
  return visible
}

export function ImageList({
  brandId,
  images,
  loading,
  empty,
  renderActions,
}: {
  brandId: string
  images: ImageRecord[]
  loading: boolean
  empty: ReactNode
  renderActions?: (image: ImageRecord) => ReactNode
}) {
  const showSkeleton = useDelayedLoading(loading)
  if (showSkeleton) {
    return <div aria-label="사진 목록 불러오는 중" className="grid gap-1 py-3">{Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-16 w-full" />)}</div>
  }
  if (loading) return null
  if (images.length === 0) return <>{empty}</>
  return (
    <ul aria-label="사진 목록" className="divide-y">
      {images.map((image) => (
        <li key={image.id} className="flex min-h-16 min-w-0 items-center gap-3 py-2">
          <img
            src={imageThumbnailUrl(brandId, image.id)}
            alt={image.original_filename}
            className="size-14 shrink-0 rounded-md border object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium" title={image.original_filename}>{image.original_filename}</p>
            <p className="mt-1 text-xs text-muted-foreground tabular-nums">{new Date(image.created_at).toLocaleString("ko-KR")}</p>
          </div>
          {renderActions?.(image)}
        </li>
      ))}
    </ul>
  )
}
