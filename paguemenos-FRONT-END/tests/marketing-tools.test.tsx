import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError, AxiosHeaders } from "axios"
import { afterEach, expect, it, vi } from "vitest"
import { editPiece, startRender, uploadPieceBackground } from "@/api/services/campaigns"
import type { Campaign, Piece, ValidationRun } from "@/contracts/api"
import { PieceEditor } from "@/features/campaigns/PieceEditor"
import { ValidationResults } from "@/features/campaigns/ValidationResults"

vi.mock("@/api/services/campaigns", () => ({ editPiece: vi.fn(), uploadPieceBackground: vi.fn(), startRender: vi.fn() }))
const piece: Piece = { id: "piece", campaign_id: "campaign", channel: "feed", title: "Título original", subtitle: "Subtítulo original", cta: "Conheça", disclaimer: "Campanha fictícia", product_id: "syn-001", product_name: "Produto autorizado", price: "8.90", authorized_offer: "Sem desconto", state: "approved", validations: [], reviews: [], edit_version: 2, show_price: false, visual_style: "Minimalista" }
const campaign: Campaign = { id: "campaign", created_at: "2026-10-26T10:00:00Z", briefing: { campaign_name: "Teste", objective: "Apresentar", target_audience: "Adultos", product_id: "syn-001", channels: ["feed"], additional_instructions: null }, pieces: [piece] }
function showEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(["campaign", "campaign"], campaign)
  render(<QueryClientProvider client={client}><PieceEditor piece={piece} campaignId="campaign" disabled={false} onBusyChange={() => {}} /></QueryClientProvider>)
  return client
}
afterEach(() => { cleanup(); vi.resetAllMocks() })

it("resume conformidade e permite expandir/recolher todas as verificações agrupadas", async () => {
  const run: ValidationRun = { id: "v", created_at: campaign.created_at, fingerprint: "fp", success: false, results: [
    { rule_code: "PRICE_MATCH", field: "price", passed: true, severity: "critical", message: "Preço autorizado" },
    { rule_code: "FORBIDDEN_EXPRESSION", field: "title", passed: false, severity: "critical", message: "Expressão proibida" },
    { rule_code: "VISUAL_SAFE_AREA", field: "visual", passed: false, severity: "warning", message: "Conferir margens" },
  ] }
  render(<ValidationResults run={run} />)
  expect(screen.getByText(/1 outros apontamentos/)).toBeTruthy()
  expect(screen.getByText(/1 violações críticas/)).toBeTruthy()
  const summary = screen.getByText("Relatório detalhado (3 verificações)")
  const details = summary.closest("details")!
  expect(details.open).toBe(false)
  expect(details.hasAttribute("open")).toBe(false)
  summary.focus()
  expect(document.activeElement).toBe(summary)
  const user = userEvent.setup()
  await user.click(summary)
  expect(details.open).toBe(true)
  expect(screen.getAllByRole("list")).toHaveLength(3)
  for (const message of ["Preço autorizado", "Expressão proibida", "Conferir margens"]) expect(screen.getByText(message)).toBeTruthy()
  expect(screen.getByText("Aprovada · Crítica")).toBeTruthy()
  expect(screen.getByText("Violação · Aviso")).toBeTruthy()
  await user.click(summary)
  expect(details.open).toBe(false)
})

it("edita somente os campos permitidos e atualiza o cache com o rascunho do servidor", async () => {
  const updated = { ...piece, title: "Novo título", subtitle: "Novo subtítulo", cta: "Confira", state: "draft" as const, edit_version: 3, show_price: true, visual_style: "Elegante" as const, visual_needs_recomposition: true }
  vi.mocked(editPiece).mockResolvedValue(updated)
  const client = showEditor()
  const user = userEvent.setup()
  await user.click(screen.getByRole("button", { name: "Editar peça" }))
  await user.type(screen.getByLabelText("Identificação do editor"), "Marketing")
  for (const [label, value] of [["Editar título", "Novo título"], ["Editar subtítulo", "Novo subtítulo"], ["Editar CTA", "Confira"]]) {
    await user.clear(screen.getByLabelText(label)); await user.type(screen.getByLabelText(label), value)
  }
  await user.selectOptions(screen.getByLabelText("Estilo visual da peça"), "Elegante")
  await user.selectOptions(screen.getByLabelText("Posicionamento autorizado do produto"), "produto_direita")
  await user.click(screen.getByLabelText("Exibir preço autorizado na publicidade"))
  expect(screen.queryByLabelText("Preço do catálogo")).toBeNull()
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }))
  expect(await screen.findByText(/Alterações salvas/)).toBeTruthy()
  expect(editPiece).toHaveBeenCalledExactlyOnceWith("piece", { expected_version: 2, editor_id: "Marketing", title: "Novo título", subtitle: "Novo subtítulo", cta: "Confira", template: "produto_direita", visual_style: "Elegante", show_price: true })
  expect(client.getQueryData<Campaign>(["campaign", "campaign"])?.pieces[0]).toEqual(updated)
  expect(startRender).not.toHaveBeenCalled()
})

it("mantém os campos após erro de validação sem repetir o envio", async () => {
  const config = { headers: new AxiosHeaders() }
  vi.mocked(editPiece).mockRejectedValue(new AxiosError("invalid", "ERR_BAD_RESPONSE", config, undefined, { status: 422, statusText: "Error", headers: {}, config, data: { error: { code: "EDIT_CONTENT_INVALID", message: "Texto comercial não autorizado.", details: [] } } }))
  showEditor()
  const user = userEvent.setup()
  await user.click(screen.getByRole("button", { name: "Editar peça" }))
  await user.type(screen.getByLabelText("Identificação do editor"), "Marketing")
  await user.clear(screen.getByLabelText("Editar título"))
  await user.type(screen.getByLabelText("Editar título"), "Rascunho preservado")
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }))
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Texto comercial não autorizado"))
  expect((screen.getByLabelText("Editar título") as HTMLTextAreaElement).value).toBe("Rascunho preservado")
  expect(editPiece).toHaveBeenCalledTimes(1)
})

it("só envia o fundo após confirmação de autorização, sem recompor ou usar IA automaticamente", async () => {
  vi.mocked(uploadPieceBackground).mockResolvedValue({ ...piece, state: "draft", edit_version: 3, visual_needs_recomposition: true })
  showEditor()
  const user = userEvent.setup()
  await user.click(screen.getByRole("button", { name: "Editar peça" }))
  await user.type(screen.getByLabelText("Identificação do editor"), "Marketing")
  const file = new File(["synthetic fixture"], "background.png", { type: "image/png" })
  await user.upload(screen.getByLabelText("Imagem de fundo"), file)
  const button = screen.getByRole("button", { name: "Enviar e selecionar fundo" })
  expect(button).toHaveProperty("disabled", true)
  expect(uploadPieceBackground).not.toHaveBeenCalled()
  await user.click(screen.getByLabelText("Confirmo que possuo autorização para utilizar esta imagem."))
  await user.click(button)
  expect(await screen.findByText(/Fundo recebido e selecionado/)).toBeTruthy()
  await waitFor(() => expect(uploadPieceBackground).toHaveBeenCalledExactlyOnceWith("piece", file, "Marketing", 2))
  expect(editPiece).not.toHaveBeenCalled()
  expect(startRender).not.toHaveBeenCalled()
})
