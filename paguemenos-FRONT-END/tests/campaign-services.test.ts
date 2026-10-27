import { afterEach, expect, it, vi } from "vitest"
import { apiClient } from "@/api/client"
import { editPiece, getCampaign, getPieceImage, reviewPiece, uploadPieceBackground, validateCampaign } from "@/api/services/campaigns"

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


it("envia edição restrita, upload binário com autorização e consulta versão vinculada à peça", async () => {
  const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { id: "piece" } })
  const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: new Blob() })
  const edit = { expected_version: 3, editor_id: "Marketing", title: "Título", subtitle: "Subtítulo", cta: "Confira", visual_style: "Moderno" as const, show_price: false }
  await editPiece("piece/id", edit)
  expect(post).toHaveBeenCalledWith("/pieces/piece%2Fid/edit", edit)
  const file = new File(["synthetic fixture"], "team.jpg", { type: "image/jpeg" })
  await uploadPieceBackground("piece/id", file, "Marketing", 4)
  expect(post).toHaveBeenCalledWith("/pieces/piece%2Fid/background", file, { params: { editor_id: "Marketing", expected_version: 4, rights_confirmed: true }, headers: { "Content-Type": "image/jpeg" } })
  await getPieceImage("piece/id", "a".repeat(32))
  expect(get).toHaveBeenCalledWith("/pieces/piece%2Fid/image", { params: { version_id: "a".repeat(32) }, responseType: "blob", headers: { Accept: "image/png" } })
})
