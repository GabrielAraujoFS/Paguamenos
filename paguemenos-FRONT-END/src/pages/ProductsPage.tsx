import { Link } from "react-router"
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/RequestState"
import { ProductCard } from "@/features/catalog/ProductCard"
import { useProducts } from "@/features/catalog/use-products"

export function ProductsPage() {
  const products = useProducts()

  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Catálogo</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-950">Produtos disponíveis</h1>
          <p className="mt-2 text-sm text-slate-600">Os produtos e as ofertas vêm diretamente do backend.</p>
        </div>
        <Link to="/campaigns/new" className="inline-flex w-fit rounded-lg bg-blue-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Criar briefing</Link>
      </div>
      {products.isPending ? <LoadingState label="Carregando catálogo…" /> : products.isError ? (
        <ErrorState error={products.error} onRetry={() => void products.refetch()} />
      ) : products.data.length === 0 ? (
        <EmptyState title="Nenhum produto disponível">Tente novamente quando o catálogo do backend for atualizado.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {products.data.map((product) => <ProductCard key={product.id} product={product} />)}
        </div>
      )}
    </div>
  )
}
