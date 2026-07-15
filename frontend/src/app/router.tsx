import { BrowserRouter, Route, Routes } from "react-router-dom"

import { AppShell } from "@/app/app-shell"
import { AppProviders } from "@/app/providers"
import { BrandProvider } from "@/features/brands/brand-provider"
import { ProductsPage } from "@/pages/products-page"

function PageFrame({ title }: { title: string }) {
  return (
    <div className="px-5 py-8 sm:px-8 sm:py-10">
      <h1 className="text-2xl leading-8 font-bold tracking-[-0.02em]">
        {title}
      </h1>
    </div>
  )
}

export function AppRouter() {
  return (
    <AppProviders>
      <BrowserRouter>
        <BrandProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<PageFrame title="오늘의 작업" />} />
              <Route path="products" element={<ProductsPage />} />
              <Route
                path="tray-images"
                element={<PageFrame title="트레이 사진" />}
              />
            </Route>
          </Routes>
        </BrandProvider>
      </BrowserRouter>
    </AppProviders>
  )
}
