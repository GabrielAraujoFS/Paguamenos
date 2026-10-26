import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getPieceImage } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"
import { normalizeHttpError } from "@/api/errors"

export function PiecePreview({ pieceId, fileId, title }: { pieceId: string; fileId: string; title: string }) {
  const [expanded, setExpanded] = useState(false)
  const image = useQuery({
    queryKey: queryKeys.pieceImage(pieceId, fileId),
    queryFn: async () => URL.createObjectURL(await getPieceImage(pieceId)),
    retry: false, staleTime: Infinity, gcTime: 0,
  })

  useEffect(() => {
    if (!image.data) return
    const objectUrl = image.data
    return () => URL.revokeObjectURL(objectUrl)
  }, [image.data])

  if (image.isPending) return <p role="status">Carregando prévia…</p>
  if (image.isError) return <div role="alert" className="text-sm text-red-800">Imagem indisponível: {normalizeHttpError(image.error).message} <button type="button" onClick={() => void image.refetch()} className="underline">Tentar novamente</button></div>
  const url = image.data

  function download() {
    if (!url) return
    const link = document.createElement("a")
    link.href = url
    link.download = `criativo-${pieceId}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return <div className="space-y-3">
    <img src={url} alt={`Prévia de ${title}`} className="max-h-[560px] w-full rounded-lg border border-slate-200 object-contain" />
    <p className="text-xs text-slate-600">Prévia interna. O arquivo só deve ser usado para publicação após aprovação humana.</p>
    <div className="flex flex-wrap gap-3">
      <button type="button" onClick={() => setExpanded(true)} className="rounded-lg border px-3 py-2 text-sm">Ver em tamanho maior</button>
      <button type="button" onClick={download} className="rounded-lg border px-3 py-2 text-sm">Baixar PNG</button>
    </div>
    {expanded && <div role="dialog" aria-modal="true" aria-label={`Prévia ampliada de ${title}`} className="fixed inset-0 z-50 overflow-auto bg-slate-950/90 p-5 text-center">
      <button type="button" onClick={() => setExpanded(false)} className="mb-4 rounded-lg bg-white px-4 py-2 text-blue-950">Fechar</button>
      <img src={url} alt={`Prévia ampliada de ${title}`} className="mx-auto max-h-[85vh] max-w-full object-contain" />
    </div>}
  </div>
}
