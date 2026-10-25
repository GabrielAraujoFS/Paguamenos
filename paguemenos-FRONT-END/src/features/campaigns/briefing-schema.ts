import { z } from "zod"
import type { GenerateRequest } from "@/contracts/api"

const requiredText = z.string().trim().min(1, "Campo obrigatório.").max(2000, "Use no máximo 2000 caracteres.")

export const briefingSchema = z.object({
  campaign_name: requiredText,
  product_id: requiredText,
  objective: requiredText,
  target_audience: requiredText,
  channels: z.array(z.enum(["feed", "story", "banner"]))
    .min(1, "Selecione pelo menos um canal.")
    .max(3, "Selecione no máximo três canais.")
    .refine((channels) => new Set(channels).size === channels.length, "Os canais não podem se repetir."),
  additional_instructions: z.string().trim().max(4000, "Use no máximo 4000 caracteres."),
})

export type BriefingFormValues = z.infer<typeof briefingSchema>

export function toGenerateRequest(values: BriefingFormValues): GenerateRequest {
  return {
    campaign_name: values.campaign_name,
    product_id: values.product_id,
    objective: values.objective,
    target_audience: values.target_audience,
    channels: values.channels,
    additional_instructions: values.additional_instructions || null,
  }
}
