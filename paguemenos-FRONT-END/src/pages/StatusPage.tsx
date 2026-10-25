import { useHealth } from "@/features/system/use-system-status"
import { useProducts } from "@/features/catalog/use-products"
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/RequestState"

export function StatusPage() {
  const health = useHealth()
  const products = useProducts()

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Diagnóstico</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-950">Conexão com o backend</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">Este painel consulta as rotas reais <code>/health</code> e <code>/products</code>. O provedor informado por <code>/health</code> indica configuração, não sua disponibilidade externa.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-6" aria-labelledby="health-title">
          <h2 id="health-title" className="text-lg font-semibold">Serviço</h2>
          {health.isPending ? <LoadingState label="Consultando /health…" /> : health.isError ? <ErrorState error={health.error} onRetry={() => void health.refetch()} /> : (
            <dl className="grid gap-3 text-sm">
              <div><dt className="text-slate-500">Estado</dt><dd className="font-medium">{health.data.status}</dd></div>
              <div><dt className="text-slate-500">Provedor configurado</dt><dd className="font-medium">{health.data.generation_provider}</dd></div>
            </dl>
          )}
        </section>
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-6" aria-labelledby="products-title">
          <h2 id="products-title" className="text-lg font-semibold">Catálogo</h2>
          {products.isPending ? <LoadingState label="Consultando /products…" /> : products.isError ? <ErrorState error={products.error} onRetry={() => void products.refetch()} /> : products.data.length === 0 ? (
            <EmptyState title="Nenhum produto retornado">O catálogo está vazio no backend atual.</EmptyState>
          ) : (
            <p className="text-sm text-slate-700"><span className="text-2xl font-semibold text-blue-900">{products.data.length}</span> produto(s) retornado(s) pela API.</p>
          )}
        </section>
      </div>
    </div>
  )
}
