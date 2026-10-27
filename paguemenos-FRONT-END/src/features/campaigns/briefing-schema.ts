import { z } from "zod"
import type { GenerateRequest } from "@/contracts/api"

const requiredText = z.string().trim().min(1, "Campo obrigatório.").max(2000, "Use no máximo 2000 caracteres.")

export const themeOptions = ["Autocuidado", "Saúde e prevenção", "Beleza", "Dia das Mães", "Dia dos Pais", "Verão", "Volta às aulas", "Personalizado"] as const
export const styleOptions = ["Minimalista", "Moderno", "Acolhedor", "Vibrante", "Elegante"] as const

export const briefingSchema = z.object({
  theme: z.enum(["", ...themeOptions]),
  custom_theme: z.string().trim().max(120, "Use no máximo 120 caracteres."),
  visual_style: z.enum(styleOptions),
  show_price: z.enum(["yes", "no"]),
  campaign_name: requiredText,
  product_id: requiredText,
  objective: requiredText,
  target_audience: requiredText,
  channels: z.array(z.enum(["feed", "story", "banner"]))
    .min(1, "Selecione pelo menos um canal.")
    .max(3, "Selecione no máximo três canais.")
    .refine((channels) => new Set(channels).size === channels.length, "Os canais não podem se repetir."),
  additional_instructions: z.string().trim().max(4000, "Use no máximo 4000 caracteres."),
}).superRefine((values, context) => {
  if (values.theme === "Personalizado" && !values.custom_theme) {
    context.addIssue({ code: "custom", path: ["custom_theme"], message: "Informe o tema personalizado." })
  }
})

export type BriefingFormValues = z.infer<typeof briefingSchema>

export function toGenerateRequest(values: BriefingFormValues): GenerateRequest {
  return {
    theme: values.theme === "Personalizado" ? values.custom_theme : values.theme || null,
    visual_style: values.visual_style,
    show_price: values.show_price === "yes",
    campaign_name: values.campaign_name,
    product_id: values.product_id,
    objective: values.objective,
    target_audience: values.target_audience,
    channels: values.channels,
    additional_instructions: values.additional_instructions || null,
  }
}
