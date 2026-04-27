import { useEffect, useState } from 'react'
import { api, getApiBase, Project } from '../api'

type Lead = {
  id: string; name: string; website?: string; email?: string; phone?: string
  address?: string; city?: string; country?: string; sector?: string
  score: number; notes?: string; extra?: any
}

export function LeadsPage({ project, onNext }: { project: Project; onNext?: () => void }) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [location, setLocation] = useState('')
  const [limit, setLimit] = useState(8)
  const [error, setError] = useState<string | null>(null)
  const [enrich, setEnrich] = useState(true)

  async function refresh() {
    const r = await api.get<Lead[]>(`/api/projects/${project.id}/leads`)
    setLeads(r)
  }
  useEffect(() => { refresh() }, [project.id])

  async function search() {
    setBusy(true); setError(null)
    try {
      const r: any = await api.post(`/api/projects/${project.id}/leads/search`, {
        query: query || undefined,
        location: location || undefined,
        limit,
        enrich_with_scrape: enrich,
      })
      if (r?.degraded && r?.error) setError(r.error)
      await refresh()
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  async function del(id: string) {
    await api.del(`/api/projects/${project.id}/leads/${id}`)
    refresh()
  }

  const csvHref = `${getApiBase()}/api/projects/${project.id}/leads/export.csv`

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">4. Leads y scraping</h1>
        <p className="text-slate-600 text-sm">Busca clientes potenciales reales (IA con búsqueda web), enriquece sus datos y exporta a CSV.</p>
      </header>

      <section className="card">
        <div className="grid md:grid-cols-12 gap-2">
          <input className="input md:col-span-6" placeholder="Búsqueda libre (opcional, p.ej. 'restaurantes veganos en Madrid')" value={query} onChange={e => setQuery(e.target.value)} />
          <input className="input md:col-span-3" placeholder="Ciudad / país (opcional)" value={location} onChange={e => setLocation(e.target.value)} />
          <input className="input md:col-span-1" type="number" min={1} max={30} value={limit} onChange={e => setLimit(parseInt(e.target.value || '8', 10))} />
          <label className="md:col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={enrich} onChange={e => setEnrich(e.target.checked)} /> Enriquecer con scrape</label>
        </div>
        <div className="mt-3 flex gap-2 items-center">
          <button className="btn-primary" onClick={search} disabled={busy}>{busy ? 'Buscando…' : '🔎 Buscar leads'}</button>
          <a className="btn-secondary" href={csvHref} target="_blank" rel="noreferrer">⬇ Exportar CSV</a>
          <span className="text-xs text-slate-500">{leads.length} leads guardados</span>
        </div>
        {error && <div className="text-rose-600 text-sm mt-2">{error}</div>}
      </section>

      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th>Score</th><th>Nombre</th><th>Web</th><th>Email</th><th>Tel.</th><th>Ciudad</th><th>Sector</th><th>Notas</th><th></th>
            </tr>
          </thead>
          <tbody>
            {leads.map(l => (
              <tr key={l.id} className="border-t border-slate-100 align-top">
                <td className="py-1.5"><span className={`chip ${l.score >= 70 ? 'chip-ok' : l.score >= 40 ? 'chip-warn' : 'chip-err'}`}>{Math.round(l.score)}</span></td>
                <td className="py-1.5"><b>{l.name}</b></td>
                <td>{l.website && <a className="text-brand-700 hover:underline" href={l.website} target="_blank" rel="noreferrer">{l.website.replace(/^https?:\/\//, '').slice(0, 30)}</a>}</td>
                <td>{l.email}</td>
                <td>{l.phone}</td>
                <td>{l.city}</td>
                <td>{l.sector}</td>
                <td className="max-w-[300px] text-slate-600 text-xs">{l.notes}</td>
                <td><button className="btn-ghost" onClick={() => del(l.id)}>✕</button></td>
              </tr>
            ))}
            {leads.length === 0 && <tr><td colSpan={9} className="text-slate-500 text-center py-4">No hay leads aún. Usa el buscador.</td></tr>}
          </tbody>
        </table>
      </section>

      {leads.length > 0 && onNext && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={onNext}>▶ Siguiente paso: crear campaña creativa</button>
        </div>
      )}
    </div>
  )
}
