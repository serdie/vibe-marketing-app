import { useState } from 'react'
import { api, Project } from '../api'

export function OwnerPage({ project, onUpdate, onNext }: { project: Project; onUpdate: () => void; onNext?: () => void }) {
  const [name, setName] = useState(project.full_name || project.name || '')
  const [website, setWebsite] = useState(project.website || '')
  const [ownerType, setOwnerType] = useState(project.owner_type || 'empresa')
  const [cv, setCv] = useState(project.cv_text || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState('')

  async function save() {
    await api.put(`/api/projects/${project.id}`, {
      full_name: name, website, owner_type: ownerType, cv_text: cv,
    })
    onUpdate()
  }

  async function research() {
    setBusy(true); setError(null); setProgress('Investigando con búsqueda en Google… (3 pasadas, ~30-60s)')
    try {
      await save()
      await api.post(`/api/projects/${project.id}/research`)
      setProgress('')
      onUpdate()
    } catch (e: any) { setError(e.message); setProgress('') }
    finally { setBusy(false) }
  }

  const r: any = (project.research as any)?.profile || {}
  const seo: any = (project.research as any)?.seo_audit || {}
  const web: any = (project.research as any)?.web_scrape || {}
  const hasResearch = Object.keys(r).length > 0

  const ubic = r.ubicacion
  const ubicStr = typeof ubic === 'string' ? ubic : ubic ? [ubic.ciudad, ubic.provincia, ubic.pais].filter(Boolean).join(', ') : ''

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">1. Identificar al propietario</h1>
        <p className="text-slate-600 text-sm">URL, nombre y CV/ficha → la app investiga en internet (3 búsquedas grounded en Google) y resume.</p>
      </header>

      <section className="card grid md:grid-cols-2 gap-4">
        <div>
          <label className="label">Tipo</label>
          <select className="input" value={ownerType} onChange={e => setOwnerType(e.target.value)}>
            <option value="empresa">Empresa</option>
            <option value="autonomo">Autónomo</option>
            <option value="particular">Particular</option>
          </select>
        </div>
        <div>
          <label className="label">Nombre completo / Razón social</label>
          <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="ACME S.L." />
        </div>
        <div className="md:col-span-2">
          <label className="label">URL del sitio web</label>
          <input className="input" value={website} onChange={e => setWebsite(e.target.value)} placeholder="https://acme.com" />
        </div>
        <div className="md:col-span-2">
          <label className="label">CV / información extra (recomendado, sobre todo si es particular o autónomo)</label>
          <textarea className="input min-h-[120px]" value={cv} onChange={e => setCv(e.target.value)}
            placeholder="Pega aquí experiencia, sectores, idiomas, certificaciones, productos, hechos diferenciales, etc." />
        </div>
        <div className="md:col-span-2 flex gap-2 items-center">
          <button className="btn-secondary" onClick={save} disabled={busy}>Guardar</button>
          <button className="btn-primary" onClick={research} disabled={busy}>
            {busy ? '🔄 Investigando…' : '🔎 Investigar en profundidad (Google + IA)'}
          </button>
          {hasResearch && onNext && <button className="btn-secondary ml-auto" onClick={onNext}>▶ Siguiente: Carencias</button>}
        </div>
        {progress && <div className="md:col-span-2 text-brand-700 text-sm">{progress}</div>}
        {error && <div className="md:col-span-2 text-rose-600 text-sm">{error}</div>}
      </section>

      {hasResearch && (
        <section className="card">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold">Perfil detectado</h2>
            {r.degraded && <span className="chip chip-warn">Modo demo (sin IA real)</span>}
            {!r.degraded && <span className="chip chip-ok">Investigación con Google {r.model || ''}</span>}
          </div>
          <p className="text-slate-700 text-sm mb-3">{r.summary}</p>

          <div className="grid md:grid-cols-3 gap-3 text-sm">
            <Field k="Sector" v={r.sector} />
            <Field k="Subsectores" v={(r.subsectores || []).join(', ')} />
            <Field k="Actividad principal" v={r.actividad_principal} />
            <Field k="Ubicación" v={ubicStr || (typeof ubic === 'string' ? ubic : '')} />
            <Field k="Ámbito" v={ubic?.ambito} />
            <Field k="Año fundación" v={r.año_fundacion} />
            <Field k="Tamaño" v={r.tamano} />
            <Field k="Tono de marca" v={r.tono_marca} />
            <Field k="Idiomas" v={Array.isArray(r.idiomas) ? r.idiomas.join(', ') : r.idiomas} />
          </div>

          <Block title="Propuesta de valor" content={r.propuesta_valor} />
          <ListBlock title="Ventajas competitivas" items={r.ventajas_competitivas} />
          <ListBlock title="Públicos objetivo" items={r.publicos_objetivo} />
        </section>
      )}

      {Array.isArray(r.productos_servicios) && r.productos_servicios.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Productos / servicios detectados en internet</h2>
          <div className="grid md:grid-cols-2 gap-2 text-sm">
            {r.productos_servicios.map((s: any, i: number) => (
              <div key={i} className="border border-slate-200 rounded-lg p-3">
                <div className="font-semibold">{typeof s === 'string' ? s : s.nombre}</div>
                {typeof s === 'object' && (
                  <>
                    <div className="text-slate-700">{s.descripcion}</div>
                    <div className="text-xs text-slate-500 mt-1">{s.precio_aprox} {s.publico ? `· ${s.publico}` : ''}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {(r.presencia_digital || r.reputacion) && (
        <section className="card">
          <h2 className="font-semibold mb-2">Presencia digital y reputación</h2>
          {r.presencia_digital?.web && (
            <div className="text-sm mb-3">
              <span className="label">Web:</span> {r.presencia_digital.web.url || project.website} ·
              SEO score: <b>{r.presencia_digital.web.puntuacion_seo ?? seo.score}</b> /100
              {r.presencia_digital.web.principales_problemas?.length > 0 && (
                <ul className="list-disc list-inside text-xs mt-1 text-slate-600">
                  {r.presencia_digital.web.principales_problemas.map((x: string, i: number) => <li key={i}>{x}</li>)}
                </ul>
              )}
            </div>
          )}
          {Array.isArray(r.presencia_digital?.redes) && r.presencia_digital.redes.length > 0 && (
            <div className="text-sm mb-3">
              <span className="label">Redes:</span>
              <table className="w-full mt-1">
                <thead className="text-left text-slate-500"><tr><th>Plataforma</th><th>URL</th><th>Seguidores</th><th>Frecuencia</th><th>Calidad</th></tr></thead>
                <tbody>{r.presencia_digital.redes.map((n: any, i: number) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td>{n.plataforma}</td>
                    <td><a className="text-brand-700 hover:underline" href={n.url} target="_blank" rel="noreferrer">{n.url}</a></td>
                    <td>{n.seguidores_aprox}</td>
                    <td>{n.frecuencia}</td>
                    <td>{n.calidad}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {r.reputacion?.google_maps && (
            <div className="text-sm">
              <span className="label">Reseñas:</span> Google Maps {r.reputacion.google_maps.nota || '?'} ({r.reputacion.google_maps['nº_reseñas'] || '?'} reseñas)
              {r.reputacion.google_maps.temas_positivos?.length > 0 && (
                <div className="text-xs text-emerald-700 mt-1">+ {r.reputacion.google_maps.temas_positivos.join(', ')}</div>
              )}
              {r.reputacion.google_maps.temas_negativos?.length > 0 && (
                <div className="text-xs text-rose-700 mt-1">– {r.reputacion.google_maps.temas_negativos.join(', ')}</div>
              )}
            </div>
          )}
        </section>
      )}

      {(r.fortalezas?.length || r.debilidades?.length || r.riesgos?.length) > 0 && (
        <section className="grid md:grid-cols-3 gap-3">
          {r.fortalezas?.length > 0 && <CardList title="Fortalezas" items={r.fortalezas} cls="text-emerald-700" />}
          {r.debilidades?.length > 0 && <CardList title="Debilidades" items={r.debilidades} cls="text-amber-700" />}
          {r.riesgos?.length > 0 && <CardList title="Riesgos" items={r.riesgos} cls="text-rose-700" />}
        </section>
      )}

      {r.oportunidades_inmediatas?.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Oportunidades inmediatas (esta semana)</h2>
          <ul className="list-disc list-inside text-sm space-y-1">{r.oportunidades_inmediatas.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
        </section>
      )}

      {r.keywords_seo_recomendadas?.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Keywords SEO recomendadas</h2>
          <div className="flex flex-wrap gap-1">{r.keywords_seo_recomendadas.map((k: string, i: number) => <span key={i} className="chip">{k}</span>)}</div>
        </section>
      )}

      {r.noticias_recientes?.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Noticias / menciones recientes</h2>
          <ul className="text-sm space-y-1">{r.noticias_recientes.map((n: any, i: number) => (
            <li key={i}>· <a className="text-brand-700 hover:underline" href={n.url} target="_blank" rel="noreferrer">{n.titulo}</a> <span className="text-xs text-slate-500">{n.fecha}</span></li>
          ))}</ul>
        </section>
      )}

      {Array.isArray(r.sources) && r.sources.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Fuentes consultadas en Google</h2>
          <ul className="space-y-1 text-xs list-disc list-inside">
            {r.sources.map((s: any, i: number) => (
              <li key={i}><a className="text-brand-700 hover:underline" href={s.uri} target="_blank" rel="noreferrer">{s.title || s.uri}</a></li>
            ))}
          </ul>
        </section>
      )}

      {seo && Object.keys(seo).length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Mini-audit SEO de la web</h2>
          <div className="flex items-center gap-3 mb-2">
            <div className="text-3xl font-bold">{seo.score}</div>
            <div className="text-sm text-slate-500">/ 100</div>
          </div>
          <ul className="list-disc list-inside text-sm space-y-1 text-slate-700">
            {(seo.issues || []).map((i: string, k: number) => <li key={k}>{i}</li>)}
            {(seo.issues || []).length === 0 && <li>Sin issues detectados.</li>}
          </ul>
        </section>
      )}

      {web && Object.keys(web.socials || {}).length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Redes detectadas en la web</h2>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(web.socials).map(([k, v]) => (
              <a key={k} href={v as string} target="_blank" rel="noreferrer" className="chip chip-ok">{k}</a>
            ))}
          </div>
        </section>
      )}

      {hasResearch && onNext && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={onNext}>▶ Siguiente paso: detectar carencias y competencia</button>
        </div>
      )}
    </div>
  )
}

function Field({ k, v }: { k: string; v: any }) {
  if (v === null || v === undefined || v === '') return null
  return (
    <div>
      <div className="label">{k}</div>
      <div className="text-slate-800">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
    </div>
  )
}
function Block({ title, content }: { title: string; content?: string }) {
  if (!content) return null
  return (
    <div className="mt-3">
      <div className="label">{title}</div>
      <div className="text-slate-800 text-sm">{content}</div>
    </div>
  )
}
function ListBlock({ title, items }: { title: string; items?: any[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-3">
      <div className="label">{title}</div>
      <ul className="list-disc list-inside text-sm space-y-1">
        {items.map((it, i) => <li key={i}>{typeof it === 'object' ? JSON.stringify(it) : String(it)}</li>)}
      </ul>
    </div>
  )
}
function CardList({ title, items, cls }: { title: string; items: any[]; cls?: string }) {
  return (
    <div className="card">
      <h3 className={`font-semibold mb-2 ${cls || ''}`}>{title}</h3>
      <ul className="list-disc list-inside text-sm space-y-1">{items.map((x, i) => <li key={i}>{typeof x === 'object' ? JSON.stringify(x) : x}</li>)}</ul>
    </div>
  )
}
