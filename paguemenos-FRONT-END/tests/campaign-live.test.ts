// @vitest-environment node
import { expect, it } from "vitest"
import { apiClient } from "@/api/client"
import { generateCampaign, getCampaign, getCampaigns, reviewPiece, validateCampaign } from "@/api/services/campaigns"
import type { Health, Product } from "@/contracts/api"

// Opt in only against an isolated backend with a disposable database and mock provider.
it.skipIf(process.env.ZYNTRA_TEST_LIVE_API !== "1")("executa o fluxo HTTP real em backend isolado", async () => {
  const health = (await apiClient.get<Health>("/health")).data
  expect(health.generation_provider).toBe("mock")
  const products = (await apiClient.get<Product[]>("/products")).data
  const created = await generateCampaign({ campaign_name: `Teste frontend ${Date.now()}`, product_id: products[0].id,
    objective: "Apresentar produto sintético", target_audience: "Adultos", channels: ["feed", "story"], additional_instructions: null })
  expect(created.pieces.map((piece) => piece.state)).toEqual(["draft", "draft"])
  await expect(reviewPiece(created.pieces[0].id, { decision: "approved", reviewer_id: "Teste isolado" })).rejects.toMatchObject({ response: { status: 409 } })
  const validated = await validateCampaign(created.id)
  expect(validated.pieces.every((piece) => piece.state === "validated" && piece.validations.at(-1)?.success)).toBe(true)
  expect(validated.pieces[0].price).toBe(products[0].price)
  const approved = await reviewPiece(created.pieces[0].id, { decision: "approved", reviewer_id: "Teste isolado", comment: "Conferido" })
  expect(approved.state).toBe("approved")
  const rejected = await reviewPiece(created.pieces[1].id, { decision: "rejected", reviewer_id: "Teste isolado", comment: null })
  expect(rejected.state).toBe("rejected")
  const detail = await getCampaign(created.id)
  expect(detail.pieces.map((piece) => piece.state)).toEqual(["approved", "rejected"])
  expect(detail.pieces.every((piece) => piece.reviews.length === 1)).toBe(true)
  const listed = await getCampaigns({ page: 1, page_size: 20, search: created.briefing.campaign_name })
  expect(listed.items.some((campaign) => campaign.id === created.id)).toBe(true)
}, 20000)
