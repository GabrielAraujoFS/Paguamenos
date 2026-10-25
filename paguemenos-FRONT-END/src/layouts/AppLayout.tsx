import { Activity, FolderOpen, Home, Package, SquarePen } from "lucide-react"
import { Link, NavLink, Outlet } from "react-router"
import { cn } from "@/lib/utils"

const navigation = [
  { to: "/", label: "Início", icon: Home, end: true },
  { to: "/products", label: "Catálogo", icon: Package, end: false },
  { to: "/campanhas", label: "Campanhas", icon: FolderOpen, end: false },
  { to: "/campaigns/new", label: "Nova campanha", icon: SquarePen, end: false },
  { to: "/status", label: "Conexão", icon: Activity, end: false },
] as const

export function AppLayout() {
  return (
    <div className="min-h-svh bg-[var(--brand-paper)]">
      <a href="#conteudo" className="sr-only rounded bg-white px-3 py-2 focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50">
        Ir para o conteúdo
      </a>
      <header className="border-b border-white/10 bg-[var(--brand-navy)] shadow-lg shadow-blue-950/10">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <Link to="/" aria-label="Zyntra AI, início" className="block w-fit rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--brand-orange)]">
            <img src="/logos/zyntra-ai-dark.jpeg" alt="Zyntra AI" className="h-auto w-48 sm:w-56" />
          </Link>
          <nav aria-label="Navegação principal" className="flex flex-wrap gap-2">
            {navigation.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) => cn(
                  "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white/85 transition-colors hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-orange)]",
                  isActive ? "bg-white/12 text-white shadow-inner ring-1 ring-white/15" : "hover:bg-white/10",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 sm:py-12">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-5 pb-8 text-xs text-slate-500 sm:px-8">
        Os dados e estados apresentados pela API são a fonte de verdade.
      </footer>
    </div>
  )
}
