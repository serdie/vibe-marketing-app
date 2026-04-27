import { useState } from 'react'
import { api, Project } from '../api'
import ProgressBar, { ESTIMATED } from '../components/ProgressBar'

export function GapsPage({ project, onUpdate, onNext }: { project: Project; onUpdate: () => void; onNext?: () => void }) {
  const [extra, setExtra] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState('')
  const g: any = project.gaps || {}
  const hasResearch = !!(project.research as any)?.profile && Object.keys((project.research as any).profile).length > 0
  const hasGaps = Object.keys(g).length > 0

  async function analyze() {
    setBusy(true); setError(null); setProgress('Buscando 5 competidores reales y comparando 10 ejes… (~45-90s)')
    try {
      await api.post(`/api/projects/${project.id}/gaps`, { extra_context: extra || undefined })
      setProgress('')
      onUpdate()
    } catch (e: any) { setError(e.message); setProgress('') }
    finally { setBusy(false) }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">2. Carencias y competencia</h1>
        <p className="text-slate-600 text-sm">Toma todo el research del paso 1, busca 5 competidores reales, compara 10 ejes, genera SWOT y plan de 8 acciones.</p>
      </header>

      <section className="card">
        {!hasResearch && <div className="chip chip-warn mb-2">Aún no has hecho la investigación del paso 1; el análisis será limitado. Vuelve a la pestaña "1. Propietario".</div>}
        <label className="label">Contexto adicional (opcional)</label>
        <textarea className="input min-h-[80px]" value={extra} onChange={e => setExtra(e.target.value)}
          placeholder="Notas sobre el negocio, prioridades, presupuesto, dolencias específicas que quieras destacar…" />
        <div className="mt-3 flex gap-2 items-center">
          <button className="btn-primary" onClick={analyze} disabled={busy}>
            {busy ? '🔄 Analizando…' : '🧠 Analizar carencias y competencia (3 pasadas IA)'}
          </button>
          {hasGaps && onNext && <button className="btn-secondary ml-auto" onClick={onNext}>▶ Siguiente: Productos e ICP</button>}
        </div>
        <ProgressBar active={busy} estimatedSeconds={ESTIMATED.gaps.seconds} steps={ESTIMATED.gaps.steps} title="Análisis de carencias y competencia" />
        {error && <div className="text-rose-600 text-sm mt-2">{error}</div>}
        {g.degraded && <div className="chip chip-warn mt-2">Modo demo (sin IA real)</div>}
      </section>

      {g.tesis_estrategica && (
        <section className="card">
          <h2 className="font-semibold mb-2">Tesis estratégica</h2>
          <p className="text-sm text-slate-800">{g.tesis_estrategica}</p>
        </section>
      )}

      {g.swot_propietario && (
        <section className="grid md:grid-cols-4 gap-3">
          <SWOTCard title="Fortalezas" items={g.swot_propietario.fortalezas} cls="text-emerald-700" />
          <SWOTCard title="Debilidades" items={g.swot_propietario.debilidades} cls="text-amber-700" />
          <SWOTCard title="Oportunidades" items={g.swot_propietario.oportunidades} cls="text-brand-700" />
          <SWOTCard title="Amenazas" items={g.swot_propietario.amenazas} cls="text-rose-700" />
        </section>
      )}

      {Array.isArray(g.competidores) && g.competidores.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-3">Competidores principales (búsqueda real)</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {g.competidores.map((c: any, i: number) => (
              <div key={i} className="border border-slate-200 rounded-lg p-3 text-sm">
                <div className="font-semibold">{c.nombre}</div>
                {c.web && <a className="text-xs text-brand-700 hover:underline" href={c.web} target="_blank" rel="noreferrer">{c.web}</a>}
                {c.ubicacion && <div className="text-xs text-slate-500">{c.ubicacion}</div>}
                {c.ventaja_diferencial && <p className="mt-1 text-slate-700"><b>Ventaja:</b> {c.ventaja_diferencial}</p>}
                {c.por_que_compite && <p className="mt-1 text-xs text-slate-500">{c.por_que_compite}</p>}
                {Array.isArray(c.productos) && c.productos.length > 0 && (
                  <div className="mt-2 text-xs"><span className="label">Productos:</span> {c.productos.join(' · ')}</div>
                )}
                {Array.isArray(c.canales) && c.canales.length > 0 && (
                  <div className="mt-1 text-xs"><span className="label">Canales:</span> {c.canales.join(' · ')}</div>
                )}
                {c.resenas && <div className="mt-1 text-xs"><span className="label">Reseñas:</span> {c.resenas}</div>}
                {c.precio_aprox && <div className="mt-1 text-xs"><span className="label">Precio:</span> {c.precio_aprox}</div>}
                {Array.isArray(c.fortalezas) && c.fortalezas.length > 0 && (
                  <div className="mt-2 text-emerald-700 text-xs">+ {c.fortalezas.join(' · ')}</div>
                )}
                {Array.isArray(c.debilidades) && c.debilidades.length > 0 && (
                  <div className="mt-1 text-rose-700 text-xs">– {c.debilidades.join(' · ')}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {Array.isArray(g.comparativa) && g.comparativa.length > 0 && (
        <section className="card overflow-x-auto">
          <h2 className="font-semibold mb-2">Comparativa propietario vs líder competencia (10 ejes)</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr><th>Eje</th><th>Tú</th><th>Líder</th><th>Brecha</th><th>Comentario</th></tr>
            </thead>
            <tbody>
              {g.comparativa.map((c: any, i: number) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-1.5 font-semibold">{c.eje}</td>
                  <td>{c.nota_propietario ?? c.propietario}</td>
                  <td>{c.nota_lider ?? c.lider_competencia}</td>
                  <td>
                    <span className={`chip ${(c.brecha ?? 0) > 0 ? 'chip-ok' : (c.brecha ?? 0) < 0 ? 'chip-err' : 'chip-warn'}`}>
                      {c.brecha ?? '-'}
                    </span>
                  </td>
                  <td className="text-slate-700 text-xs">{c.comentario}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {Array.isArray(g.carencias) && g.carencias.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Carencias detectadas (clasificadas)</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500"><tr><th>Área</th><th>Descripción</th><th>Evidencia</th><th>Prioridad</th><th>Impacto</th><th>Esfuerzo</th></tr></thead>
            <tbody>
              {g.carencias.map((c: any, i: number) => (
                <tr key={i} className="border-t border-slate-100 align-top">
                  <td className="py-1.5 font-semibold">{c.area}</td>
                  <td className="text-slate-700">{c.descripcion}</td>
                  <td className="text-xs text-slate-500">{c.evidencia}</td>
                  <td><span className={`chip ${c.prioridad === 'alta' ? 'chip-err' : c.prioridad === 'media' ? 'chip-warn' : ''}`}>{c.prioridad}</span></td>
                  <td>{c.impacto}</td>
                  <td>{c.esfuerzo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {Array.isArray(g.plan_accion) && g.plan_accion.length > 0 && (
        <section className="card overflow-x-auto">
          <h2 className="font-semibold mb-2">Plan de acción (8 prioridades)</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr><th>#</th><th>Tarea</th><th>Objetivo</th><th>KPI</th><th>Esfuerzo</th><th>Impacto</th><th>Coste €</th><th>Plazo (días)</th></tr>
            </thead>
            <tbody>
              {g.plan_accion.map((c: any, i: number) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-1.5">{i + 1}</td>
                  <td className="font-semibold">{c.tarea}</td>
                  <td className="text-xs">{c.objetivo}</td>
                  <td className="text-xs">{c.kpi}</td>
                  <td>{c.esfuerzo}</td>
                  <td>{c.impacto}</td>
                  <td>{c.coste_estimado_eur}</td>
                  <td>{c.plazo_dias}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {Array.isArray(g.redes_recomendadas) && g.redes_recomendadas.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Redes sociales recomendadas</h2>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            {g.redes_recomendadas.map((r: any, i: number) => (
              <div key={i} className="border border-slate-200 rounded-lg p-3">
                <div className="font-semibold">{r.plataforma}</div>
                <div className="text-slate-700">{r.razon}</div>
                {r.primer_post_idea && <div className="mt-1 text-xs text-slate-500"><span className="label">Idea de primer post:</span> {r.primer_post_idea}</div>}
              </div>
            ))}
          </div>
        </section>
      )}

      {Array.isArray(g.quick_wins_30_dias) && g.quick_wins_30_dias.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Quick wins (próximos 30 días)</h2>
          <ul className="list-disc list-inside text-sm space-y-1">{g.quick_wins_30_dias.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
        </section>
      )}

      {Array.isArray(g.sources) && g.sources.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Fuentes consultadas</h2>
          <ul className="space-y-1 text-xs list-disc list-inside">
            {g.sources.map((s: any, i: number) => (
              <li key={i}><a className="text-brand-700 hover:underline" href={s.uri} target="_blank" rel="noreferrer">{s.title || s.uri}</a></li>
            ))}
          </ul>
        </section>
      )}

      {hasGaps && onNext && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={onNext}>▶ Siguiente paso: Productos e ICP</button>
        </div>
      )}
    </div>
  )
}

function SWOTCard({ title, items, cls }: { title: string; items?: any[]; cls?: string }) {
  return (
    <div className="card">
      <h3 className={`font-semibold mb-2 ${cls || ''}`}>{title}</h3>
      <ul className="text-sm list-disc list-inside space-y-1">
        {(items || []).map((x: any, i: number) => <li key={i}>{x}</li>)}
        {(!items || items.length === 0) && <li className="text-slate-400">—</li>}
      </ul>
    </div>
  )
}
