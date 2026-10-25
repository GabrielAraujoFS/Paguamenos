import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { getCampaigns } from "@/api/services/campaigns"
import type { CampaignPage } from "@/contracts/api"
import { CampaignsPage } from "@/pages/CampaignsPage"

vi.mock("@/api/services/campaigns", () => ({ getCampaigns: vi.fn() }))

const firstPage: CampaignPage = {
  items: [{
    id: "campaign-id",
    created_at: "2026-10-24T19:07:30Z",
    briefing: {
      campaign_name: "Campanha de algodão", product_id: "syn-005", objective: "Divulgar algodão",
      target_audience: "Famílias", channels: ["story"], additional_instructions: null,
    },
    pieces: [{
      id: "piece-id", campaign_id: "campaign-id", channel: "story", title: "Título", subtitle: "Texto",
      cta: "Conheça", disclaimer: "Campanha fictícia. Dados sintéticos.", product_id: "syn-005",
      product_name: "Algodão Sereno", price: "6.75", authorized_offer: "Oferta", state: "draft",
      validations: [], reviews: [],
    }],
  }],
  total: 21, page: 1, page_size: 20, total_pages: 2,
}

function renderPage() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><CampaignsPage /></MemoryRouter>
  </QueryClientProvider>)
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe("listagem de campanhas", () => {
  it("mostra dados da API e envia paginação, busca e estado ao servidor", async () => {
    vi.mocked(getCampaigns).mockImplementation(async (params) => ({ ...firstPage, page: params.page }))
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("Campanha de algodão")).toBeTruthy()
    expect(screen.getByText("story · Rascunho")).toBeTruthy()
    expect(vi.mocked(getCampaigns)).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    await user.click(screen.getByRole("button", { name: "Próxima" }))
    await waitFor(() => expect(vi.mocked(getCampaigns)).toHaveBeenCalledWith({ page: 2, page_size: 20 }))
    await user.type(screen.getByRole("searchbox", { name: "Pesquisar pelo nome" }), "algodão")
    await user.click(screen.getByRole("button", { name: "Pesquisar" }))
    await waitFor(() => expect(vi.mocked(getCampaigns)).toHaveBeenCalledWith({ page: 1, page_size: 20, search: "algodão" }))
    await user.selectOptions(screen.getByLabelText("Estado da peça"), "approved")
    await waitFor(() => expect(vi.mocked(getCampaigns)).toHaveBeenCalledWith({ page: 1, page_size: 20, search: "algodão", status: "approved" }))
  })

  it("distingue lista vazia de pesquisa sem resultados e limpa filtros", async () => {
    vi.mocked(getCampaigns).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("Nenhuma campanha encontrada")).toBeTruthy()
    await user.type(screen.getByRole("searchbox", { name: "Pesquisar pelo nome" }), "inexistente")
    await user.click(screen.getByRole("button", { name: "Pesquisar" }))
    expect(await screen.findByText("Nenhuma campanha corresponde à pesquisa")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Limpar filtros" }))
    expect(await screen.findByText("Nenhuma campanha encontrada")).toBeTruthy()
  })

  it("permite repetir a consulta após falha de conexão", async () => {
    vi.mocked(getCampaigns).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(firstPage)
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("Não foi possível carregar as campanhas")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }))
    expect(await screen.findByText("Campanha de algodão")).toBeTruthy()
  })
})
