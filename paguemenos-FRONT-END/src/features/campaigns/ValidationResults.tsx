import type { ValidationResult, ValidationRun } from "@/contracts/api"

const severityLabels = { critical: "Crítica", warning: "Aviso", info: "Informação" }
function category(result: ValidationResult) {
  if (result.rule_code.startsWith("VISUAL_")) return "Composição visual"
  if (/PRICE|OFFER|PRODUCT/.test(result.rule_code)) return "Produto e condições comerciais"
  if (result.rule_code === "CHARACTER_LIMIT") return "Limites de conteúdo"
  return "Identidade e regras de marca"
}

export function ValidationResults({ run }: { run: ValidationRun }) {
  const passed = run.results.filter((result) => result.passed).length
  const critical = run.results.filter((result) => !result.passed && result.severity === "critical").length
  const groups = new Map<string, ValidationResult[]>()
  for (const result of run.results) groups.set(category(result), [...(groups.get(category(result)) ?? []), result])
  return <div className="mt-3 space-y-3">
    <p className={`font-semibold ${critical ? "text-red-900" : "text-blue-950"}`}>{run.success ? "Sem violações críticas" : "Validação com bloqueios críticos"}</p>
    <p className="text-sm text-slate-700">{passed} de {run.results.length} verificações aprovadas · {critical} violações críticas · {run.results.length - passed - critical} outros apontamentos</p>
    <p className="text-xs text-slate-500">{new Date(run.created_at).toLocaleString("pt-BR")}</p>
    <details className="rounded-lg border border-slate-200 p-3">
      <summary className="cursor-pointer font-semibold text-blue-900 focus-visible:outline-2 focus-visible:outline-blue-700">Relatório detalhado ({run.results.length} verificações)</summary>
      {[...groups].map(([name, results]) => <section key={name} className="mt-4 space-y-2" aria-label={name}>
        <h4 className="font-semibold text-blue-950">{name}</h4>
        <ul className="space-y-2">{results.map((result, index) => <li key={`${result.rule_code}-${index}`} className={`rounded-lg border p-3 text-sm ${result.passed ? "border-emerald-200 bg-emerald-50" : result.severity === "critical" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
          <p className="font-semibold">{result.passed ? "Aprovada" : "Violação"} · {severityLabels[result.severity]}</p>
          <p className="mt-1 break-words">{result.message}</p>
          <p className="mt-1 break-words text-xs text-slate-600">{result.rule_code} · {result.field}</p>
        </li>)}</ul>
      </section>)}
    </details>
  </div>
}
