import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { getCampaign, getPieceImage, getRender, reviewPiece, startRender, validateCampaign } from "@/api/services/campaigns"
import type { Campaign, RenderStatus, VisualProcessingState } from "@/contracts/api"
import { CampaignDetailPage } from "@/pages/CampaignDetailPage"

vi.mock("@/api/services/campaigns", () => ({
  getCampaign: vi.fn(), getPieceImage: vi.fn(), getRender: vi.fn(),
  reviewPiece: vi.fn(), startRender: vi.fn(), validateCampaign: vi.fn(),
}))

const campaign: Campaign = {
  id: "campaign-id", created_at: "2026-10-24T19:07:30Z",
  briefing: { campaign_name: "Campanha", product_id: "syn-005", objective: "Divulgar", target_audience: "Famílias", channels: ["feed"], additional_instructions: null },
  pieces: [{ id: "piece-id", campaign_id: "campaign-id", channel: "feed", title: "Título", subtitle: "Texto", cta: "Conheça", disclaimer: "Demo", product_id: "syn-005", product_name: "Produto", price: "6.75", authorized_offer: "Oferta", state: "draft", validations: [], reviews: [] }],
}

function renderStatus(state: VisualProcessingState): RenderStatus {
  return { piece_id: "piece-id", visual: {
    state, plan: { channel: "feed", art_direction: "Luz natural", background_prompt: "Fundo sem texto", layout: "produto_centro", palette: ["#112233"], concept: "Verão", visual_style: "Leve", scenario: "Praia", lighting: "Natural", decorative_elements: ["Folhas"] },
    template: null, background: null, product_image: null,
    final_image: state === "composed" ? { file_id: "a".repeat(32), media_type: "image/png", width: 1080, height: 1350, sha256: "b".repeat(64) } : null,
    generation: null, render_request_id: null, plan_id: null, image_generation: null, composed_at: null,
    source_piece_id: null, error_code: state === "blocked" ? "PRODUCT_ASSET_MISSING" : null,
    error_message: state === "blocked" ? "Fotografia do produto ausente." : null, visual_review_required: true,
  } }
}

function showPage() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/campanhas/campaign-id"]}><Routes><Route path="/campanhas/:campaignId" element={<CampaignDetailPage />} /></Routes></MemoryRouter>
  </QueryClientProvider>)
}

beforeEach(() => {
  vi.mocked(getCampaign).mockResolvedValue(structuredClone(campaign))
  vi.mocked(getRender).mockResolvedValue(renderStatus("pending"))
  vi.mocked(startRender).mockResolvedValue(renderStatus("processing"))
  vi.mocked(validateCampaign).mockResolvedValue(structuredClone(campaign))
  vi.mocked(reviewPiece).mockResolvedValue(campaign.pieces[0])
  vi.mocked(getPieceImage).mockResolvedValue(new Blob(["png"], { type: "image/png" }))
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:preview"), revokeObjectURL: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.clearAllMocks() })

describe("detalhe da campanha", () => {
  it("inicia renderização uma vez, com request_id, e impede clique duplo", async () => {
    const user = userEvent.setup()
    showPage()
    await screen.findByText("Imagem ainda não gerada")
    const button = screen.getByRole("button", { name: "Gerar imagem" })
    await user.dblClick(button)
    await waitFor(() => expect(startRender).toHaveBeenCalledTimes(1))
    expect(vi.mocked(startRender).mock.calls[0][1]).toMatchObject({ request_id: expect.any(String) })
    expect(await screen.findByText("Gerando fundo e compondo…")).toBeTruthy()
  })

  it("mostra falha recuperável da API e bloqueio de assets", async () => {
    vi.mocked(startRender).mockRejectedValueOnce(new Error("offline"))
    const user = userEvent.setup()
    showPage()
    await screen.findByText("Imagem ainda não gerada")
    await user.click(screen.getByRole("button", { name: "Gerar imagem" }))
    expect(await screen.findByRole("alert")).toBeTruthy()
    vi.mocked(startRender).mockResolvedValueOnce(renderStatus("blocked"))
    await user.click(screen.getByRole("button", { name: "Gerar imagem" }))
    expect(await screen.findByText("Geração bloqueada")).toBeTruthy()
    expect(screen.getByText(/Fotografia do produto ausente/)).toBeTruthy()
  })

  it("exibe prévia e baixa PNG sem expor caminho local", async () => {
    vi.mocked(getRender).mockResolvedValue(renderStatus("composed"))
    const user = userEvent.setup()
    showPage()
    expect(await screen.findByAltText("Prévia de Título")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Baixar PNG" }))
    expect(getPieceImage).toHaveBeenCalledWith("piece-id")
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it("valida e só permite aprovação depois de validação positiva", async () => {
    vi.mocked(getRender).mockResolvedValue(renderStatus("composed"))
    const validated = structuredClone(campaign)
    validated.pieces[0].state = "validated"
    validated.pieces[0].validations = [{ id: "validation", created_at: "2026-10-24T19:07:30Z", fingerprint: "hash", success: true, results: [] }]
    vi.mocked(validateCampaign).mockResolvedValue(validated)
    const user = userEvent.setup()
    showPage()
    await screen.findByText("Composição concluída")
    expect((screen.getByRole("button", { name: "Aprovar peça" }) as HTMLButtonElement).disabled).toBe(true)
    await user.click(screen.getByRole("button", { name: "Validar campanha" }))
    await screen.findByText(/Última validação: Conforme/)
    await user.type(screen.getByLabelText(/Identificação do revisor/), "Revisor")
    await user.click(screen.getByRole("button", { name: "Aprovar peça" }))
    await waitFor(() => expect(reviewPiece).toHaveBeenCalledWith("piece-id", { decision: "approved", reviewer_id: "Revisor", comment: null }))
    expect(validateCampaign).toHaveBeenCalledTimes(1)
  })

  it("acompanha processamento até concluir e para de consultar após o estado terminal", async () => {
    vi.mocked(getRender).mockResolvedValueOnce(renderStatus("processing")).mockResolvedValue(renderStatus("composed"))
    showPage()
    await screen.findByText("Gerando fundo e compondo…")
    expect(await screen.findByText("Composição concluída", {}, { timeout: 3000 })).toBeTruthy()
    const callsAtCompletion = vi.mocked(getRender).mock.calls.length
    await new Promise((resolve) => setTimeout(resolve, 1700))
    expect(getRender).toHaveBeenCalledTimes(callsAtCompletion)
  })

  it("evita validação duplicada e mantém aprovação bloqueada quando BrandGuard falha", async () => {
    const failed = structuredClone(campaign)
    failed.pieces[0].validations = [{ id: "failed", created_at: "2026-10-24T19:07:30Z", fingerprint: "hash", success: false, results: [{ rule_code: "PRICE", severity: "critical", message: "Preço incorreto", field: "price", passed: false }] }]
    vi.mocked(validateCampaign).mockResolvedValue(failed)
    const user = userEvent.setup()
    showPage()
    await screen.findByText("Imagem ainda não gerada")
    await user.dblClick(screen.getByRole("button", { name: "Validar campanha" }))
    await screen.findByText(/Última validação: Não conforme/)
    expect(validateCampaign).toHaveBeenCalledTimes(1)
    await user.type(screen.getByLabelText(/Identificação do revisor/), "Revisor")
    expect((screen.getByRole("button", { name: "Aprovar peça" }) as HTMLButtonElement).disabled).toBe(true)
    expect(reviewPiece).not.toHaveBeenCalled()
  })

  it("evita duas revisões no mesmo clique duplo", async () => {
    vi.mocked(getRender).mockResolvedValue(renderStatus("composed"))
    const validated = structuredClone(campaign)
    validated.pieces[0].state = "validated"
    validated.pieces[0].validations = [{ id: "validation", created_at: "2026-10-24T19:07:30Z", fingerprint: "hash", success: true, results: [] }]
    vi.mocked(getCampaign).mockResolvedValue(validated)
    const user = userEvent.setup()
    showPage()
    await screen.findByText("Composição concluída")
    await user.type(screen.getByLabelText(/Identificação do revisor/), "Revisor")
    await user.dblClick(screen.getByRole("button", { name: "Aprovar peça" }))
    await waitFor(() => expect(reviewPiece).toHaveBeenCalledTimes(1))
  })

  it("exibe falhas visuais e alertas no relatório existente", async () => {
    const report = structuredClone(campaign)
    report.pieces[0].validations = [{ id: "visual-check", created_at: "2026-10-24T19:07:30Z", fingerprint: "hash", success: false, results: [
      { rule_code: "VISUAL_DIMENSIONS", severity: "critical", field: "visual.final_image", passed: false, message: "Falha: dimensões incorretas" },
      { rule_code: "HEALTH_CLAIM_REVIEW", severity: "warning", field: "subtitle", passed: false, message: "Falha: revisão humana necessária" },
    ] }]
    vi.mocked(getCampaign).mockResolvedValue(report)
    showPage()
    expect(await screen.findByText(/Última validação: Não conforme/)).toBeTruthy()
    expect(screen.getByText(/dimensões incorretas/)).toBeTruthy()
    expect(screen.getByText(/revisão humana necessária/)).toBeTruthy()
  })
})
