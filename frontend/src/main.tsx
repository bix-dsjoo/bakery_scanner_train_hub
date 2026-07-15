import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "pretendard/dist/web/variable/pretendardvariable.css"
import "@/index.css"

import { AppRouter } from "@/app/router"

const root = document.getElementById("root")

if (!root) {
  throw new Error("애플리케이션을 표시할 root 요소가 없어요.")
}

createRoot(root).render(
  <StrictMode>
    <AppRouter />
  </StrictMode>
)
