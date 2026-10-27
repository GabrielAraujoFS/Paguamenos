import type { GenerationMetadata } from "@/contracts/api"

export function contentOrigin(generation?: GenerationMetadata | null): string {
  if (!generation) return "Origem do texto não registrada"
  if (generation.provider === "mock") return "Conteúdo demonstrativo · gerador mock, sem IA real"
  if (generation.provider === "gemini") return "Texto gerado com IA · Gemini"
  return "Texto produzido por provedor personalizado"
}
