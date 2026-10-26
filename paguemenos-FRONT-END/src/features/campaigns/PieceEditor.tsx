import { useEffect, useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { editPiece, uploadPieceBackground } from "@/api/services/campaigns"
import { normalizeHttpError } from "@/api/errors"
import { queryKeys } from "@/api/query-keys"
import type { Campaign, Piece, PieceEditRequest, RenderStatus } from "@/contracts/api"
import { styleOptions } from "@/features/campaigns/briefing-schema"
import { Button } from "@/components/ui/button"

const schema = z.object({
  editor_id: z.string().trim().min(1, "Informe sua identificação.").max(100),
  title: z.string().trim().min(1, "Informe o título.").max(2000),
  subtitle: z.string().trim().min(1, "Informe o subtítulo.").max(2000),
  cta: z.string().trim().min(1, "Informe o CTA.").max(2000),
  template: z.enum(["", "produto_centro", "produto_direita"]),
  visual_style: z.enum(["", ...styleOptions]),
  show_price: z.boolean(),
})
const editLabels: Record<string, string> = { title: "Título", subtitle: "Subtítulo", cta: "CTA", show_price: "Exibir preço", visual_style: "Estilo visual", template: "Posicionamento", selected_background: "Fundo selecionado" }
function historyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Não informado"
  if (typeof value === "boolean") return value ? "Sim" : "Não"
  if (value === "produto_centro") return "Produto ao centro"
  if (value === "produto_direita") return "Produto à direita"
  if (typeof value === "object") {
    const asset = value as Record<string, unknown>
    return typeof asset.file_id === "string" ? `Imagem registrada · ${asset.file_id.slice(0, 12)}` : "Imagem registrada"
  }
  return String(value)
}
type Values = z.infer<typeof schema>
type Operation = { kind: "edit"; request: PieceEditRequest } | { kind: "upload"; file: File; editor: string; version: number }
const fieldClass = "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus-visible:outline-blue-700"

export function PieceEditor({ piece, campaignId, disabled, onBusyChange }: { piece: Piece; campaignId: string; disabled: boolean; onBusyChange: (id: string, active: boolean) => void }) {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [version, setVersion] = useState(piece.edit_version ?? 0)
  const [rights, setRights] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState("")
  const [localError, setLocalError] = useState("")
  const lock = useRef(false)
  const { register, reset, getValues, handleSubmit, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema) })
  const mutation = useMutation({ retry: false, mutationFn: async (operation: Operation) => {
    if (operation.kind === "edit") return editPiece(piece.id, operation.request)
    return uploadPieceBackground(piece.id, operation.file, operation.editor, operation.version)
  } })
  useEffect(() => {
    onBusyChange(`edit-${piece.id}`, mutation.isPending)
    return () => onBusyChange(`edit-${piece.id}`, false)
  }, [piece.id, mutation.isPending, onBusyChange])

  function begin() {
    const status = client.getQueryData<RenderStatus>(queryKeys.render(piece.id))
    const template = status?.visual.plan?.layout
    reset({ editor_id: "", title: piece.title, subtitle: piece.subtitle, cta: piece.cta,
      template: template === "produto_centro" || template === "produto_direita" ? template : "",
      visual_style: piece.visual_style ?? "", show_price: piece.show_price ?? true })
    setVersion(piece.edit_version ?? 0)
    setOpen(true); setNotice(""); setLocalError(""); mutation.reset(); setFile(null); setRights(false)
  }
  async function run(operation: Operation) {
    if (lock.current || disabled || mutation.isPending) return
    lock.current = true; setNotice(""); setLocalError("")
    try {
      await client.cancelQueries({ queryKey: queryKeys.campaign(campaignId) })
      const updated = await mutation.mutateAsync(operation)
      client.setQueryData<Campaign>(queryKeys.campaign(campaignId), (current) => current && ({ ...current, pieces: current.pieces.map((entry) => entry.id === updated.id ? updated : entry) }))
      setVersion(updated.edit_version ?? 0)
      void client.invalidateQueries({ queryKey: queryKeys.render(piece.id) })
      void client.invalidateQueries({ queryKey: ["campaigns"] })
      setNotice(operation.kind === "edit" && (updated.edit_version ?? 0) === operation.request.expected_version ? "Nenhuma alteração de conteúdo foi necessária; o estado anterior foi preservado." : operation.kind === "edit" ? "Alterações salvas. Valide novamente e solicite nova aprovação. Se houver imagem anterior, recomponha primeiro." : "Fundo recebido e selecionado. Clique em Recompor com fundo existente para aplicar; a imagem anterior foi preservada.")
      if (operation.kind === "edit") setOpen(false)
      else { setFile(null); setRights(false) }
    } catch (error) {
      if (normalizeHttpError(error).status === 409) {
        void client.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
        void client.invalidateQueries({ queryKey: queryKeys.render(piece.id) })
      }
    } finally { lock.current = false }
  }
  async function save(values: Values) {
    const { template, visual_style, ...fields } = values
    await run({ kind: "edit", request: { ...fields, expected_version: version, visual_style: visual_style || null, ...(template ? { template } : {}) } })
  }
  async function upload() {
    const editor = getValues("editor_id")?.trim() ?? ""
    if (!editor || editor.length > 100) { setLocalError("Informe sua identificação antes de enviar a imagem."); return }
    if (!file || !rights) { setLocalError("Selecione uma imagem e confirme a autorização de uso."); return }
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size > 5 * 1024 * 1024) { setLocalError("Envie PNG ou JPEG de até 5 MiB."); return }
    await run({ kind: "upload", file, editor, version })
  }
  return <section className="space-y-4 border-t border-slate-200 pt-5" aria-label="Edição da peça">
    <h3 className="text-lg font-bold text-blue-950">Ajustar conteúdo e composição</h3>
    {!open && <Button type="button" variant="outline" disabled={disabled} onClick={begin}>Editar peça</Button>}
    {open && <form onSubmit={(event) => { void handleSubmit(save)(event) }} noValidate className="space-y-4 rounded-xl bg-slate-50 p-4">
      <p className="text-sm text-slate-700">Salvar invalida a validação e aprovação atuais. A imagem anterior permanece disponível até você recompor; produto, preço do catálogo e oferta não são editáveis.</p>
      <fieldset disabled={disabled || mutation.isPending} className="space-y-4 disabled:opacity-60">
        {([['editor_id', 'Identificação do editor'], ['title', 'Editar título'], ['subtitle', 'Editar subtítulo'], ['cta', 'Editar CTA']] as const).map(([name, label]) => <div key={name}>
          <label htmlFor={`${name}-${piece.id}`} className="text-sm font-semibold text-blue-950">{label}</label>
          <textarea id={`${name}-${piece.id}`} rows={name === 'subtitle' ? 3 : 1} maxLength={name === 'editor_id' ? 100 : 2000} className={fieldClass} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `${name}-error-${piece.id}` : undefined} {...register(name)} />
          {errors[name] && <p id={`${name}-error-${piece.id}`} role="alert" className="text-sm text-red-700">{errors[name].message}</p>}
        </div>)}
        {piece.channel !== "banner" && <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold text-blue-950">Posicionamento autorizado do produto
            <select className={fieldClass} {...register("template")}><option value="">Manter / padrão autorizado</option><option value="produto_centro">Produto ao centro</option><option value="produto_direita">Produto à direita</option></select>
          </label>
          <label className="text-sm font-semibold text-blue-950">Estilo visual da peça
            <select className={fieldClass} {...register("visual_style")}><option value="">Original</option>{styleOptions.map((style) => <option key={style}>{style}</option>)}</select>
          </label>
        </div>}
        <label className="flex items-center gap-2 text-sm font-semibold text-blue-950"><input type="checkbox" {...register("show_price")} />Exibir preço autorizado na publicidade</label>
        <div className="flex flex-wrap gap-3"><Button type="submit">Salvar alterações</Button><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar edição</Button></div>
        {piece.channel !== "banner" && <section className="space-y-3 border-t border-slate-200 pt-4" aria-label="Enviar fundo">
          <h4 className="font-semibold text-blue-950">Utilizar imagem enviada como fundo</h4>
          <p className="text-sm text-slate-600">PNG/JPEG, até 5 MiB; 256–4096 pixels por lado e até 12 milhões de pixels. O fundo pode ser recortado para caber no formato. Não substitui logo nem fotografia do produto e não é enviado à IA.</p>
          <label className="block text-sm font-semibold text-blue-950">Imagem de fundo<input type="file" accept="image/png,image/jpeg" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setLocalError("") }} className={fieldClass} /></label>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={rights} onChange={(event) => setRights(event.target.checked)} />Confirmo que possuo autorização para utilizar esta imagem.</label>
          <Button type="button" variant="outline" disabled={!file || !rights} onClick={() => void upload()}>Enviar e selecionar fundo</Button>
        </section>}
      </fieldset>
    </form>}
    {mutation.isPending && <p role="status">Salvando alterações…</p>}
    {notice && <p role="status" className="rounded-lg bg-blue-50 p-3 text-sm text-blue-950">{notice}</p>}
    {(mutation.isError || localError) && <p role="alert" className="text-sm text-red-800">{localError || normalizeHttpError(mutation.error).message} Seus campos foram preservados. Em conflito, atualize e reabra o editor; em falha de rede, confira o histórico antes de repetir.</p>}
    {(piece.edit_history?.length ?? 0) > 0 && <details><summary className="cursor-pointer text-sm font-semibold text-blue-900">Histórico de edições ({piece.edit_history?.length})</summary>
      <ul className="mt-3 space-y-3">{piece.edit_history?.map((record) => <li key={record.id} className="rounded-lg bg-slate-50 p-3 text-sm">
        <p className="font-semibold">{record.kind === "background" ? "Fundo selecionado" : "Conteúdo ajustado"} · {record.editor_id}</p>
        <p className="text-xs text-slate-500">{new Date(record.created_at).toLocaleString("pt-BR")}</p>
        <details className="mt-2"><summary className="cursor-pointer text-blue-900">Consultar alterações</summary><dl className="mt-2 space-y-3">{Object.keys(editLabels).filter((key) => key in record.before || key in record.after).map((key) => <div key={key}>
          <dt className="font-semibold">{editLabels[key]}</dt><dd className="whitespace-pre-wrap break-words"><span className="font-semibold">Antes:</span> {historyValue(record.before[key])}<br /><span className="font-semibold">Depois:</span> {historyValue(record.after[key])}</dd>
        </div>)}</dl></details>
      </li>)}</ul>
    </details>}
  </section>
}
