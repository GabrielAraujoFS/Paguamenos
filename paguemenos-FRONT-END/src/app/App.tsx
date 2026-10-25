import { QueryClientProvider } from "@tanstack/react-query"
import { lazy, Suspense } from "react"
import { Route, Routes } from "react-router"
import { queryClient } from "@/app/query-client"
import { AppLayout } from "@/layouts/AppLayout"
import { HomePage } from "@/pages/HomePage"
import { StatusPage } from "@/pages/StatusPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { LoadingState } from "@/components/shared/RequestState"

const ProductsPage = lazy(() => import("@/pages/ProductsPage").then((module) => ({ default: module.ProductsPage })))
const ProductDetailPage = lazy(() => import("@/pages/ProductDetailPage").then((module) => ({ default: module.ProductDetailPage })))
const NewCampaignPage = lazy(() => import("@/pages/NewCampaignPage").then((module) => ({ default: module.NewCampaignPage })))
const CampaignsPage = lazy(() => import("@/pages/CampaignsPage").then((module) => ({ default: module.CampaignsPage })))

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="mx-auto max-w-6xl px-5 py-8"><LoadingState label="Abrindo página…" /></div>}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="status" element={<StatusPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="products/:productId" element={<ProductDetailPage />} />
            <Route path="campaigns/new" element={<NewCampaignPage />} />
            <Route path="campanhas" element={<CampaignsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </QueryClientProvider>
  )
}
