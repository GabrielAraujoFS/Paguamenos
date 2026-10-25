import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { normalizeHttpError } from "@/api/errors"
import { queryKeys } from "@/api/query-keys"
import { generateCampaign } from "@/api/services/campaigns"
import type { Campaign, Channel, Product } from "@/contracts/api"
import { formatPrice } from "@/features/catalog/format-price"
import { applyBriefingServerErrors } from "@/features/campaigns/briefing-errors"
import { briefingSchema, toGenerateRequest, type BriefingFormValues } from "@/features/campaigns/briefing-schema"

const channelOptions: Array<{ value: Channel; label: string }> = [
  { value: "feed", label: "Feed" },
  { value: "story", label: "Story" },
  { value: "banner", label: "Banner" },
]

const inputClass = "mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none focus-visible:border-blue-700 focus-visible:ring-2 focus-visible:ring-blue-700/20 aria-invalid:border-red-500"
const labelClass = "block text-sm font-semibold text-blue-950"

export function BriefingForm({ products, initialProductId }: { products: Product[]; initialProductId?: string }) {
  const queryClient = useQueryClient()
  const [created, setCreated] = useState<Campaign | null>(null)
  const [requestError, setRequestError] = useState<unknown>(null)
  const mutation = useMutation({ mutationFn: generateCampaign })
  const {
    register, handleSubmit, control, setValue, setError, clearErrors, reset,
    formState: { errors },
  } = useForm<BriefingFormValues>({
    resolver: zodResolver(briefingSchema),
    defaultValues: {
      campaign_name: "",
      product_id: products.some((product) => product.id === initialProductId) ? initialProductId : "",
      objective: "",
      target_audience: "",
      channels: [],
      additional_instructions: "",
    },
  })
  const selectedProductId = useWatch({ control, name: "product_id" })
  const selectedChannels = useWatch({ control, name: "channels" }) ?? []
  const selectedProduct = products.find((product) => product.id === selectedProductId)
  const normalizedRequestError = requestError === null ? null : normalizeHttpError(requestError)

  async function onSubmit(values: BriefingFormValues) {
    if (mutation.isPending) return
    clearErrors()
    setRequestError(null)
    try {
      setCreated(await mutation.mutateAsync(toGenerateRequest(values)))
    } catch (error) {
      const normalized = normalizeHttpError(error)
      setRequestError(error)
      applyBriefingServerErrors(normalized, setError)
      if (normalized.code === "PRODUCT_NOT_FOUND") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.products })
      }
    }
  }

  if (created) {
    return (
      <section className="rounded-2xl border border-blue-200 bg-white p-6 shadow-sm sm:p-8" role="status" aria-live="polite">
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Campanha criada</p>
        <h2 className="mt-2 text-2xl font-bold text-blue-950">{created.briefing.campaign_name}</h2>
        <p className="mt-3 text-sm text-slate-600">Guarde o ID para consultar a campanha depois. As peças geradas ainda não foram validadas nem aprovadas.</p>
        <p className="mt-4 break-all rounded-lg bg-slate-50 p-3 font-mono text-sm text-slate-800">{created.id}</p>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {created.pieces.map((piece) => (
            <li key={piece.id} className="rounded-lg border border-slate-200 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">{piece.channel} · {piece.state}</p>
              <p className="mt-1 font-semibold text-blue-950">{piece.title}</p>
            </li>
          ))}
        </ul>
        <div className="mt-7 flex flex-wrap gap-3">
          <Button type="button" onClick={() => { reset(); setCreated(null); setRequestError(null) }}>Criar outro briefing</Button>
          <Button asChild variant="outline"><Link to="/products">Voltar ao catálogo</Link></Button>
        </div>
      </section>
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <label htmlFor="campaign-name" className={labelClass}>Nome da campanha</label>
          <input id="campaign-name" maxLength={2000} aria-invalid={Boolean(errors.campaign_name)} aria-describedby={errors.campaign_name ? "campaign-name-error" : undefined} className={inputClass} {...register("campaign_name")} />
          {errors.campaign_name && <p id="campaign-name-error" className="mt-1 text-sm text-red-700">{errors.campaign_name.message}</p>}
        </div>
        <div>
          <label htmlFor="product-id" className={labelClass}>Produto</label>
          <select id="product-id" aria-invalid={Boolean(errors.product_id)} aria-describedby={errors.product_id ? "product-id-error" : undefined} className={inputClass} {...register("product_id")}>
            <option value="">Selecione um produto</option>
            {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
          </select>
          {errors.product_id && <p id="product-id-error" className="mt-1 text-sm text-red-700">{errors.product_id.message}</p>}
        </div>
      </div>

      {selectedProduct && (
        <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4 text-sm text-slate-700">
          <p className="font-semibold text-blue-950">{selectedProduct.name} · {formatPrice(selectedProduct.price)}</p>
          <p className="mt-1">{selectedProduct.description}</p>
          <p className="mt-2"><span className="font-semibold">Oferta autorizada:</span> {selectedProduct.authorized_offer}</p>
        </div>
      )}

      <div>
        <label htmlFor="objective" className={labelClass}>Objetivo</label>
        <textarea id="objective" rows={3} maxLength={2000} aria-invalid={Boolean(errors.objective)} aria-describedby={errors.objective ? "objective-error" : undefined} className={inputClass} {...register("objective")} />
        {errors.objective && <p id="objective-error" className="mt-1 text-sm text-red-700">{errors.objective.message}</p>}
      </div>
      <div>
        <label htmlFor="target-audience" className={labelClass}>Público-alvo</label>
        <textarea id="target-audience" rows={3} maxLength={2000} aria-invalid={Boolean(errors.target_audience)} aria-describedby={errors.target_audience ? "target-audience-error" : undefined} className={inputClass} {...register("target_audience")} />
        {errors.target_audience && <p id="target-audience-error" className="mt-1 text-sm text-red-700">{errors.target_audience.message}</p>}
      </div>

      <fieldset aria-describedby={errors.channels ? "channels-error" : undefined}>
        <legend className={labelClass}>Canais</legend>
        <p className="mt-1 text-sm text-slate-600">Escolha de um a três canais.</p>
        <div className="mt-3 flex flex-wrap gap-3">
          {channelOptions.map(({ value, label }) => (
            <label key={value} className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-blue-950 has-checked:border-blue-700 has-checked:bg-blue-50">
              <input
                type="checkbox"
                checked={selectedChannels.includes(value)}
                onChange={(event) => setValue("channels", event.target.checked ? [...selectedChannels, value] : selectedChannels.filter((channel) => channel !== value), { shouldValidate: true, shouldDirty: true })}
                className="size-4 accent-blue-800"
              />
              {label}
            </label>
          ))}
        </div>
        {errors.channels && <p id="channels-error" className="mt-2 text-sm text-red-700">{errors.channels.message}</p>}
      </fieldset>

      <div>
        <label htmlFor="additional-instructions" className={labelClass}>Instruções adicionais <span className="font-normal text-slate-500">(opcional)</span></label>
        <textarea id="additional-instructions" rows={4} maxLength={4000} aria-invalid={Boolean(errors.additional_instructions)} aria-describedby={errors.additional_instructions ? "additional-instructions-error" : undefined} className={inputClass} {...register("additional_instructions")} />
        {errors.additional_instructions && <p id="additional-instructions-error" className="mt-1 text-sm text-red-700">{errors.additional_instructions.message}</p>}
      </div>

      {normalizedRequestError && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">
          <p className="font-semibold">Não foi possível gerar a campanha.</p>
          <p className="mt-1">{normalizedRequestError.message}</p>
          {normalizedRequestError.code && <p className="mt-1 text-xs">Código: {normalizedRequestError.code}</p>}
        </div>
      )}
      <div className="flex flex-col gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">A geração cria conteúdo em rascunho; a validação é uma etapa posterior.</p>
        <Button type="submit" size="lg" disabled={mutation.isPending} className="w-full bg-blue-900 text-white hover:bg-blue-800 sm:w-auto">
          {mutation.isPending ? "Gerando campanha…" : "Gerar campanha"}
        </Button>
      </div>
    </form>
  )
}
