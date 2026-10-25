import { ArrowRight, Layers3, ShieldCheck } from "lucide-react"
import { Link } from "react-router"
import { Button } from "@/components/ui/button"

export function HomePage() {
  return (
    <div className="space-y-8">
      <section className="relative isolate overflow-hidden rounded-2xl bg-[var(--brand-navy)] px-6 py-10 text-white shadow-xl shadow-blue-950/10 sm:px-10 sm:py-14">
        <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-28 -z-10 size-80 rotate-45 border-[34px] border-[var(--brand-blue)]/35" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-2 -top-14 -z-10 size-52 rotate-45 border-[24px] border-[var(--brand-orange)]/80" />
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--brand-orange)]">Campanhas</p>
        <h1 className="mt-4 max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">Comece pelo catálogo e crie seu briefing.</h1>
        <p className="mt-5 max-w-2xl leading-relaxed text-blue-50/85">
          Escolha um produto disponível, defina os canais e envie as informações da campanha para geração. As peças criadas começam como rascunhos.
        </p>
        <Button asChild size="lg" className="mt-8 bg-[var(--brand-orange)] text-[var(--brand-navy)] hover:bg-amber-300">
          <Link to="/campaigns/new">Criar briefing <ArrowRight className="size-4" aria-hidden="true" /></Link>
        </Button>
      </section>
      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <Layers3 className="size-6 text-blue-700" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold">Catálogo conectado</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">Produtos, preços e ofertas são consultados diretamente na API.</p>
        </section>
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <ShieldCheck className="size-6 text-blue-700" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold">Briefing documentado</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">O formulário usa os campos aceitos pelo backend e apresenta erros de validação.</p>
        </section>
      </div>
    </div>
  )
}
