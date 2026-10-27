import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError, AxiosHeaders } from "axios"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { getCampaign, getRender, reviewPiece, validateCampaign } from "@/api/services/campaigns"
import type { Campaign, Piece } from "@/contracts/api"
import { CampaignCard } from "@/features/campaigns/CampaignCard"
import { CampaignDetailPage } from "@/pages/CampaignDetailPage"

vi.mock("@/api/services/campaigns", () => ({ getRender: vi.fn(), getPieceImage: vi.fn(), startRender: vi.fn(), getCampaign: vi.fn(), validateCampaign: vi.fn(), reviewPiece: vi.fn() }))

const piece: Piece = {
  id: "piece-1", campaign_id: "campaign-1", channel: "feed", title: "Título completo",
  subtitle: "Subtítulo completo", cta: "Conheça", disclaimer: "Campanha fictícia.",
  product_id: "syn-001", product_name: "Sabonete Brisa", price: "8.90", authorized_offer: "Condição comercial autorizada",
  state: "draft", validations: [], reviews: [],
}
const campaign: Campaign = {
  id: "campaign-1", created_at: "2026-10-25T12:00:00Z",
  briefing: { campaign_name: "Campanha Zyntra", objective: "Apresentar produto", target_audience: "Adultos", product_id: "syn-001", channels: ["feed", "story"], additional_instructions: null },
  pieces: [piece, { ...piece, id: "piece-2", channel: "story" }],
}
function validated(success = true): Campaign {
  return { ...campaign, pieces: campaign.pieces.map((entry) => ({ ...entry, state: success ? "validated" : "draft", validations: [{
    id: `validation-${entry.id}`, created_at: campaign.created_at, fingerprint: "fp", success,
    results: [{ rule_code: "PRICE_MATCH", field: "price", severity: "critical", passed: success, message: success ? "Preço correto" : "Preço divergente" },
      { rule_code: "EXPRESSION", field: "title", severity: "warning", passed: false, message: "Rever expressão" }],
  }] })) }
}
function httpError(status: number, message: string) {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError(message, "ERR_BAD_RESPONSE", config, undefined, { status, statusText: "Error", headers: {}, config, data: { error: { code: "TEST_ERROR", message, details: [] } } })
}
function renderPage(card = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[card ? "/" : "/campaigns/campaign-1"]}><Routes>
    <Route path="/" element={<CampaignCard campaign={campaign} />} />
    <Route path="/campaigns/:campaignId" element={<CampaignDetailPage />} />
  </Routes></MemoryRouter></QueryClientProvider>)
  return client
}
beforeEach(() => {
  vi.mocked(getRender).mockResolvedValue({ piece_id: "piece-1", visual: {
    state: "pending", plan: null, template: null, background: null, product_image: null,
    final_image: null, generation: null, render_request_id: null, plan_id: null,
    image_generation: null, composed_at: null, source_piece_id: null,
    error_code: null, error_message: null, visual_review_required: true,
  } })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

it("abre o cartão por link e mostra briefing e conteúdo completo de todas as peças", async () => {
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  renderPage(true)
  await userEvent.click(screen.getByRole("link"))
  expect(await screen.findByRole("heading", { name: "Campanha Zyntra" })).toBeTruthy()
  expect(getCampaign).toHaveBeenCalledWith("campaign-1")
  expect(screen.getByText("Adultos")).toBeTruthy()
  const feed = within(screen.getByRole("article", { name: "Peça feed" }))
  for (const value of ["Título completo", "Subtítulo completo", "Conheça", "Campanha fictícia.", "R$ 8,90", "Condição comercial autorizada"]) expect(feed.getByText(value)).toBeTruthy()
  expect(screen.getAllByRole("button", { name: "Aprovar" }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true)
})

it("valida, apresenta avisos, aprova uma peça e atualiza o cache sem afetar a outra", async () => {
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  vi.mocked(validateCampaign).mockResolvedValue(validated())
  vi.mocked(reviewPiece).mockResolvedValue({ ...validated().pieces[0], state: "approved", reviews: [{ id: "review", created_at: campaign.created_at, fingerprint: "fp", decision: "approved", reviewer_id: "Paulo", comment: "Conferido" }] })
  const client = renderPage()
  const user = userEvent.setup()
  await user.click(await screen.findByRole("button", { name: "Validar campanha" }))
  expect(await screen.findAllByText("Sem violações críticas")).toHaveLength(2)
  expect(screen.getAllByText("Violação · Aviso")).toHaveLength(2)
  const feed = within(screen.getByRole("article", { name: "Peça feed" }))
  await user.type(feed.getByLabelText("Identificação do revisor"), "Paulo")
  await user.type(feed.getByLabelText("Comentário da revisão (opcional)"), "Conferido")
  await user.click(feed.getByRole("button", { name: "Aprovar" }))
  expect(reviewPiece).not.toHaveBeenCalled()
  await user.click(feed.getByRole("button", { name: "Confirmar aprovação" }))
  expect(await feed.findByText("Aprovada · Paulo")).toBeTruthy()
  expect(reviewPiece).toHaveBeenCalledWith("piece-1", { decision: "approved", reviewer_id: "Paulo", comment: "Conferido" })
  expect((client.getQueryData<Campaign>(["campaign", "campaign-1"]))?.pieces.map((entry) => entry.state)).toEqual(["approved", "validated"])
  expect((feed.getByRole("button", { name: "Aprovar" }) as HTMLButtonElement).disabled).toBe(true)
})

it("trata falha crítica em HTTP 200 e permite rejeição de rascunho com identificação obrigatória", async () => {
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  vi.mocked(validateCampaign).mockResolvedValue(validated(false))
  vi.mocked(reviewPiece).mockResolvedValue({ ...piece, state: "rejected" })
  renderPage()
  const user = userEvent.setup()
  await user.click(await screen.findByRole("button", { name: "Validar campanha" }))
  expect(await screen.findAllByText("Validação com bloqueios críticos")).toHaveLength(2)
  expect(screen.getAllByText("Violação · Crítica")).toHaveLength(2)
  const feed = within(screen.getByRole("article", { name: "Peça feed" }))
  await user.click(feed.getByRole("button", { name: "Rejeitar" }))
  expect(await feed.findByText("Informe o revisor.")).toBeTruthy()
  expect(reviewPiece).not.toHaveBeenCalled()
  await user.type(feed.getByLabelText("Identificação do revisor"), "Revisor")
  await user.click(feed.getByRole("button", { name: "Rejeitar" }))
  await user.click(feed.getByRole("button", { name: "Cancelar" }))
  expect(reviewPiece).not.toHaveBeenCalled()
  await user.click(feed.getByRole("button", { name: "Rejeitar" }))
  await user.click(feed.getByRole("button", { name: "Confirmar rejeição" }))
  expect(await feed.findByText("Rejeitada")).toBeTruthy()
  expect(reviewPiece).toHaveBeenCalledWith("piece-1", { decision: "rejected", reviewer_id: "Revisor", comment: null })
})

it("reconsulta o estado em 409 e não repete a revisão automaticamente", async () => {
  vi.mocked(getCampaign).mockResolvedValueOnce(validated()).mockResolvedValue(campaign)
  vi.mocked(reviewPiece).mockRejectedValue(httpError(409, "Aprovação bloqueada"))
  renderPage()
  const user = userEvent.setup()
  const feed = within(await screen.findByRole("article", { name: "Peça feed" }))
  await user.type(feed.getByLabelText("Identificação do revisor"), "Paulo")
  await user.click(feed.getByRole("button", { name: "Aprovar" }))
  await user.click(feed.getByRole("button", { name: "Confirmar aprovação" }))
  expect(await screen.findByText("Aprovação bloqueada")).toBeTruthy()
  await waitFor(() => expect(getCampaign).toHaveBeenCalledTimes(2))
  expect(reviewPiece).toHaveBeenCalledTimes(1)
  expect((feed.getByRole("button", { name: "Aprovar" }) as HTMLButtonElement).disabled).toBe(true)
})

it("bloqueia envios duplicados durante validação", async () => {
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  let resolve!: (value: Campaign) => void
  vi.mocked(validateCampaign).mockImplementation(() => new Promise((done) => { resolve = done }))
  renderPage()
  const user = userEvent.setup()
  await user.dblClick(await screen.findByRole("button", { name: "Validar campanha" }))
  expect(validateCampaign).toHaveBeenCalledTimes(1)
  expect((screen.getByRole("button", { name: "Processando…" }) as HTMLButtonElement).disabled).toBe(true)
  resolve(validated())
  expect(await screen.findAllByText("Sem violações críticas")).toHaveLength(2)
})

it.each([404, 422, 502])("mostra erro HTTP %s e oferece nova consulta explícita", async (status) => {
  vi.mocked(getCampaign).mockRejectedValueOnce(httpError(status, `Falha ${status}`)).mockResolvedValue(campaign)
  renderPage()
  expect(await screen.findByText(`Falha ${status}`)).toBeTruthy()
  await userEvent.click(screen.getByRole("button", { name: "Tentar novamente" }))
  expect(await screen.findByRole("heading", { name: "Campanha Zyntra" })).toBeTruthy()
})

it("informa resposta não confirmada em falha de rede, sem repetir a mutação", async () => {
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  vi.mocked(validateCampaign).mockRejectedValue(new AxiosError("offline", "ERR_NETWORK"))
  renderPage()
  await userEvent.click(await screen.findByRole("button", { name: "Validar campanha" }))
  expect(await screen.findByText(/A resposta não foi confirmada/)).toBeTruthy()
  expect(validateCampaign).toHaveBeenCalledTimes(1)
})
