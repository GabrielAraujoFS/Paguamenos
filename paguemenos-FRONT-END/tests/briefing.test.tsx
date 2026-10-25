import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router"
import type { Campaign, Product } from "@/contracts/api"
import { generateCampaign } from "@/api/services/campaigns"
import { BriefingForm } from "@/features/campaigns/BriefingForm"
import { briefingSchema } from "@/features/campaigns/briefing-schema"
import { applyBriefingServerErrors } from "@/features/campaigns/briefing-errors"

vi.mock("@/api/services/campaigns", () => ({ generateCampaign: vi.fn() }))

const product: Product = {
  id: "syn-001",
  name: "Sabonete Brisa",
  description: "Produto sintético.",
  category: "higiene",
  price: "8.90",
  authorized_offer: "Oferta autorizada pelo catálogo.",
}

const generated: Campaign = {
  id: "campaign-id",
  created_at: "2026-10-20T04:14:41Z",
  briefing: {
    campaign_name: "Campanha teste",
    product_id: product.id,
    objective: "Divulgar",
    target_audience: "Adultos",
    channels: ["feed"],
    additional_instructions: null,
  },
  pieces: [{
    id: "piece-id",
    campaign_id: "campaign-id",
    channel: "feed",
    title: "Título gerado",
    subtitle: "Legenda gerada",
    cta: "Conheça",
    disclaimer: "Campanha fictícia. Dados sintéticos.",
    product_id: product.id,
    product_name: product.name,
    price: product.price,
    authorized_offer: product.authorized_offer,
    state: "draft",
    validations: [],
    reviews: [],
  }],
}

function renderForm() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <MemoryRouter><BriefingForm products={[product]} /></MemoryRouter>
    </QueryClientProvider>,
  )
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nome da campanha"), "Campanha teste")
  await user.selectOptions(screen.getByLabelText("Produto"), product.id)
  await user.type(screen.getByLabelText("Objetivo"), "Divulgar")
  await user.type(screen.getByLabelText("Público-alvo"), "Adultos")
  await user.click(screen.getByRole("checkbox", { name: "Feed" }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("briefing", () => {
  it("rejeita texto vazio após trim e canais duplicados", () => {
    const result = briefingSchema.safeParse({
      campaign_name: "   ", product_id: product.id, objective: "Divulgar",
      target_audience: "Adultos", channels: ["feed", "feed"], additional_instructions: "",
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.path.join("."))).toEqual(expect.arrayContaining(["campaign_name", "channels"]))
    }
  })

  it("bloqueia envio inválido e envia somente os seis campos documentados", async () => {
    const user = userEvent.setup()
    vi.mocked(generateCampaign).mockResolvedValue(generated)
    renderForm()

    await user.click(screen.getByRole("button", { name: "Gerar campanha" }))
    expect(generateCampaign).not.toHaveBeenCalled()
    expect(screen.getByText("Selecione pelo menos um canal.")).toBeTruthy()

    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: "Gerar campanha" }))

    await waitFor(() => expect(generateCampaign).toHaveBeenCalledWith({
      campaign_name: "Campanha teste",
      product_id: product.id,
      objective: "Divulgar",
      target_audience: "Adultos",
      channels: ["feed"],
      additional_instructions: null,
    }, expect.anything()))
    expect(generateCampaign).toHaveBeenCalledTimes(1)
    expect(await screen.findByText("campaign-id")).toBeTruthy()
  })

  it("direciona detalhes 422 para o campo documentado", () => {
    const setError = vi.fn()
    applyBriefingServerErrors({
      kind: "http", status: 422, code: "INVALID_REQUEST", message: "Dados de entrada inválidos.",
      details: [{ field: "body.channels.0", message: "Canal inválido.", type: "enum" }],
    }, setError)
    expect(setError).toHaveBeenCalledWith("channels", { type: "server", message: "Canal inválido." })
  })

  it("preserva o briefing após 502 e permite nova tentativa explícita", async () => {
    const user = userEvent.setup()
    vi.mocked(generateCampaign)
      .mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 502, data: { error: { code: "GENERATION_UNAVAILABLE", message: "Provedor indisponível.", details: [] } } },
      })
      .mockResolvedValueOnce(generated)
    renderForm()
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: "Gerar campanha" }))

    expect(await screen.findByText("Provedor indisponível.")).toBeTruthy()
    expect((screen.getByLabelText("Nome da campanha") as HTMLInputElement).value).toBe("Campanha teste")
    expect(generateCampaign).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole("button", { name: "Gerar campanha" }))
    expect(await screen.findByText("campaign-id")).toBeTruthy()
    expect(generateCampaign).toHaveBeenCalledTimes(2)
  })
})
