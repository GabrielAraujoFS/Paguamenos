import { Link } from "react-router"
import { EmptyState } from "@/components/shared/RequestState"

export function NotFoundPage() {
  return (
    <EmptyState title="Página não encontrada">
      <p>Esta rota não está disponível nesta etapa.</p>
      <Link to="/" className="mt-3 inline-block font-medium text-blue-700 underline underline-offset-2">Voltar ao início</Link>
    </EmptyState>
  )
}
