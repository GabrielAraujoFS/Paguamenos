import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError, AxiosHeaders } from "axios"
import { MemoryRouter } from "react-router"
import { afterEach, expect, it, vi } from "vitest"
import { generateCampaign, generateDemonstration, getRender, startRender } from "@/api/services/campaigns"
import type { Campaign, Piece, Product, RenderStatus } from "@/contracts/api"
import { BriefingForm } from "@/features/campaigns/BriefingForm"
import { PieceVisual } from "@/features/campaigns/PieceVisual"

vi.mock("@/api/services/campaigns", () => ({ generateCampaign: vi.fn(), generateDemonstration: vi.fn(), getRender: vi.fn(), startRender: vi.fn() }))
const product: Product = { id: "syn-001", name: "Produto", description: "Sintético", category: "Demo", price: "8.90", authorized_offer: "Sem desconto" }
const piece: Piece = { id: "piece", campaign_id: "campaign", channel: "feed", title: "Título", subtitle: "Texto", cta: "Conheça", disclaimer: "Fictício", product_id: product.id, product_name: product.name, price: product.price, authorized_offer: product.authorized_offer, state: "draft", validations: [], reviews: [] }
const briefing = { campaign_name: "Campanha", product_id: product.id, objective: "Divulgar", target_audience: "Adultos", channels: ["feed" as const], additional_instructions: null }
const campaign: Campaign = { id: "campaign", created_at: "2026-10-26T12:00:00Z", briefing, pieces: [piece], generation: { provider: "mock", model: "deterministic", created_at: "2026-10-26T12:00:00Z", prompt_tokens: null, response_tokens: null, total_tokens: null, attempts: 1 } }
function failure(code: string) {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError("unavailable", "ERR_BAD_RESPONSE", config, undefined, { status: 502, statusText: "Error", headers: {}, config, data: { error: { code, message: "Limite temporário", details: [{ demo_token: "offer-token" }] } } })
}
function show(element: React.ReactNode) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>)
}
async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nome da campanha"), "Campanha")
  await user.selectOptions(screen.getByLabelText("Produto"), product.id)
  await user.type(screen.getByLabelText("Objetivo"), "Divulgar")
  await user.type(screen.getByLabelText("Público-alvo"), "Adultos")
  await user.click(screen.getByRole("checkbox", { name: "Feed" }))
  await user.click(screen.getByRole("button", { name: "Gerar campanha" }))
}
function visual(code: string | null, source: "local_assets" | null = null): RenderStatus {
  return { piece_id: piece.id, visual: { state: source ? "composed" : "failed", error_code: code, error_message: code ? "Limite de imagens" : null, composition_source: source,
    plan: { channel: "feed", art_direction: "Clara", background_prompt: "Fundo neutro", layout: "produto_centro", palette: [], concept: null, visual_style: null, scenario: null, lighting: null, decorative_elements: [] },
    template: null, background: null, product_image: null, final_image: null, generation: null,
    render_request_id: null, plan_id: null, image_generation: null, composed_at: null, source_piece_id: null, visual_review_required: true } }
}
afterEach(() => { cleanup(); vi.resetAllMocks() })

it.each(["GENERATION_RATE_LIMIT", "GENERATION_QUOTA_EXCEEDED", "GENERATION_UNAVAILABLE"])("preserva briefing após %s e só gera mock após confirmação", async (code) => {
  vi.mocked(generateCampaign).mockRejectedValue(failure(code))
  vi.mocked(generateDemonstration).mockResolvedValue(campaign)
  const user = userEvent.setup()
  show(<BriefingForm products={[product]} />)
  await fill(user)
  expect(await screen.findByText(/Seu briefing foi preservado/)).toBeTruthy()
  expect((screen.getByLabelText("Nome da campanha") as HTMLInputElement).value).toBe("Campanha")
  expect(generateDemonstration).not.toHaveBeenCalled()
  expect(screen.queryByRole("button", { name: "Criar peça com imagens disponíveis" })).toBeNull()
  await user.click(screen.getByRole("button", { name: "Continuar com versão demonstrativa" }))
  expect(await screen.findByText(/Conteúdo demonstrativo · gerador mock/)).toBeTruthy()
  expect(generateDemonstration).toHaveBeenCalledWith(briefing, "offer-token")
  expect(generateCampaign).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole("button", { name: "Retomar briefing" }))
  expect((screen.getByLabelText("Nome da campanha") as HTMLInputElement).value).toBe("Campanha")
  expect(generateCampaign).toHaveBeenCalledTimes(1)
})

it.each(["GENERATION_CONTRACT_ERROR", "GENERATION_AUTH_ERROR", "INVALID_REQUEST"])("não oferece mock para %s", async (code) => {
  vi.mocked(generateCampaign).mockRejectedValue(failure(code))
  const user = userEvent.setup()
  show(<BriefingForm products={[product]} />)
  await fill(user)
  await screen.findByText("Limite temporário")
  expect(screen.queryByRole("button", { name: "Continuar com versão demonstrativa" })).toBeNull()
  expect(generateDemonstration).not.toHaveBeenCalled()
})

it("oferece composição local após falha visual e aguarda clique explícito", async () => {
  vi.mocked(getRender).mockResolvedValue(visual("IMAGE_RATE_LIMIT"))
  vi.mocked(startRender).mockResolvedValue(visual(null, "local_assets"))
  const user = userEvent.setup()
  show(<PieceVisual piece={piece} campaignId="campaign" sourcePieces={[]} disabled={false} onBusyChange={() => {}} />)
  const button = await screen.findByRole("button", { name: "Criar peça com imagens disponíveis" })
  expect(startRender).not.toHaveBeenCalled()
  expect(screen.queryByRole("button", { name: "Continuar com versão demonstrativa" })).toBeNull()
  await user.click(button)
  expect(await screen.findByText(/Peça produzida com recursos locais/)).toBeTruthy()
  await waitFor(() => expect(startRender).toHaveBeenCalledWith(piece.id, { use_local_assets: true, request_id: expect.any(String) }))
  expect(startRender).toHaveBeenCalledTimes(1)
})

it("não oferece composição alternativa em bloqueio de imagem inválida", async () => {
  vi.mocked(getRender).mockResolvedValue(visual("IMAGE_EMPTY"))
  show(<PieceVisual piece={piece} campaignId="campaign" sourcePieces={[]} disabled={false} onBusyChange={() => {}} />)
  await screen.findByText(/Limite de imagens/)
  expect(screen.queryByRole("button", { name: "Criar peça com imagens disponíveis" })).toBeNull()
  expect(startRender).not.toHaveBeenCalled()
})
