import type { UseFormSetError } from "react-hook-form"
import type { HttpError } from "@/api/errors"
import type { BriefingFormValues } from "@/features/campaigns/briefing-schema"

const fields = new Set<keyof BriefingFormValues>([
  "theme", "custom_theme", "visual_style", "show_price", "campaign_name", "product_id", "objective", "target_audience", "channels", "additional_instructions",
])

export function applyBriefingServerErrors(
  error: HttpError,
  setError: UseFormSetError<BriefingFormValues>,
): void {
  if (error.code === "PRODUCT_NOT_FOUND") {
    setError("product_id", { type: "server", message: error.message })
  }
  if (error.code !== "INVALID_REQUEST") return

  for (const detail of error.details) {
    const rawField = typeof detail.field === "string" ? detail.field.split(".")[1] : undefined
    const field = rawField === "theme" ? "custom_theme" : rawField
    if (field && fields.has(field as keyof BriefingFormValues)) {
      const message = typeof detail.message === "string" ? detail.message : error.message
      setError(field as keyof BriefingFormValues, { type: "server", message })
    }
  }
}
