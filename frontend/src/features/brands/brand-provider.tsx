import { createContext, useContext, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  brandsQueryKey,
  listBrands,
  type Brand,
} from "@/features/brands/api"

const storageKey = "bakery.currentBrandId"

type BrandContextValue = {
  brand: Brand | null
  brands: Brand[]
  activeBrands: Brand[]
  setBrandId: (brandId: string) => void
  isLoading: boolean
  error: Error | null
}

const BrandContext = createContext<BrandContextValue | null>(null)

function readStoredBrandId() {
  return localStorage.getItem(storageKey)
}

export function BrandProvider({ children }: { children: ReactNode }) {
  const [brandId, setBrandIdState] = useState<string | null>(readStoredBrandId)
  const query = useQuery({ queryKey: brandsQueryKey, queryFn: listBrands })
  const brands = query.data ?? []
  const activeBrands = useMemo(
    () => brands.filter((brand) => brand.status === "ACTIVE"),
    [brands]
  )
  const brand = activeBrands.find((item) => item.id === brandId) ?? null

  useEffect(() => {
    if (!query.data) return
    const nextBrandId = brand?.id ?? activeBrands[0]?.id ?? null
    if (nextBrandId !== brandId) setBrandIdState(nextBrandId)
    if (nextBrandId) localStorage.setItem(storageKey, nextBrandId)
    else localStorage.removeItem(storageKey)
  }, [activeBrands, brand?.id, brandId, query.data])

  function setBrandId(nextBrandId: string) {
    if (!activeBrands.some((item) => item.id === nextBrandId)) return
    setBrandIdState(nextBrandId)
    localStorage.setItem(storageKey, nextBrandId)
  }

  return (
    <BrandContext.Provider
      value={{
        brand,
        brands,
        activeBrands,
        setBrandId,
        isLoading: query.isLoading,
        error: query.error,
      }}
    >
      {children}
    </BrandContext.Provider>
  )
}

export function useCurrentBrand() {
  const context = useContext(BrandContext)
  if (!context) throw new Error("useCurrentBrand는 BrandProvider 안에서 사용해야 합니다.")
  return context
}
