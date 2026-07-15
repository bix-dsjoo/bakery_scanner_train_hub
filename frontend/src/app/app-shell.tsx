import { useState } from "react"
import { MenuIcon } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { BrandSelector } from "@/features/brands/brand-selector"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const navigation = [
  { label: "오늘의 작업", to: "/", end: true },
  { label: "상품 관리", to: "/products", end: false },
  { label: "트레이 사진", to: "/tray-images", end: false },
] as const

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="주요 메뉴" className="flex flex-col gap-1">
      {navigation.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn("app-nav-link", isActive && "app-nav-link-active")
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

function AppIdentity() {
  return (
    <div className="text-sm leading-5 font-semibold tracking-[-0.01em]">
      Bakery Scanner Train Hub
    </div>
  )
}

export function AppShell() {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)

  return (
    <div className="min-h-svh xl:grid xl:grid-cols-[224px_minmax(0,1fr)] xl:grid-rows-[61px_minmax(0,1fr)]">
      <header className="flex h-14 items-center justify-between border-b bg-white px-4 xl:col-start-1 xl:row-start-1 xl:h-auto xl:border-r xl:px-5">
        <AppIdentity />
        <div className="xl:hidden">
          <Sheet
            open={mobileNavigationOpen}
            onOpenChange={setMobileNavigationOpen}
          >
            <SheetTrigger
              render={
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="탐색 메뉴 열기"
                />
              }
            >
              <MenuIcon />
            </SheetTrigger>
            <SheetContent side="left" className="w-56 gap-0 p-0 sm:max-w-56">
              <SheetHeader className="border-b px-5 py-5 text-left">
                <SheetTitle className="text-sm font-semibold">
                  Bakery Scanner Train Hub
                </SheetTitle>
                <SheetDescription className="sr-only">
                  관리 화면으로 이동합니다.
                </SheetDescription>
              </SheetHeader>
              <div className="border-b px-3 py-4">
                <BrandSelector />
              </div>
              <div className="px-3 py-4">
                <NavigationLinks
                  onNavigate={() => setMobileNavigationOpen(false)}
                />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <aside className="hidden border-r bg-sidebar xl:col-start-1 xl:row-start-2 xl:flex xl:flex-col">
        <div className="border-b px-3 py-4">
          <BrandSelector />
        </div>
        <div className="px-3 py-4">
          <NavigationLinks />
        </div>
      </aside>

      <div className="min-w-0 xl:col-start-2 xl:row-span-2 xl:row-start-1">
        <main className="min-h-[calc(100svh-3.5rem)] xl:min-h-svh">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
