import { afterEach, expect, it, vi } from "vitest"
import { apiClient } from "@/api/client"
import { getCampaign, reviewPiece, validateCampaign } from "@/api/services/campaigns"

afterEach(() => vi.restoreAllMocks())

it("usa as rotas reais, codifica IDs e envia validação sem body", async () => {
  const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: { id: "campaign" } })
  const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { id: "piece" } })
  await getCampaign("opaque/id")
  expect(get).toHaveBeenCalledWith("/campaigns/opaque%2Fid")
  await validateCampaign("opaque/id")
  expect(post).toHaveBeenCalledWith("/campaigns/opaque%2Fid/validate")
  const review = { decision: "rejected" as const, reviewer_id: "Revisor", comment: null }
  await reviewPiece("piece/id", review)
  expect(post).toHaveBeenCalledWith("/pieces/piece%2Fid/review", review)
})
