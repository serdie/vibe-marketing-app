import { useEffect, useState } from 'react'
import { api, Project } from '../api'

export function HistoryPage({ project }: { project: Project }) {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [leads, setLeads] = useState<any[]>([])
  useEffect(() => {
    api.get(`/api/projects/${project.id}/campaigns`).then(setCampaigns)
    api.get(`/api/projects/${project.id}/leads`).then(setLeads)
  }, [project.id])

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Histórico (BD)</h1>
        <p className="text-slate-600 text-sm">Todo lo creado se guarda y se puede reutilizar.</p>
      </header>

      <section className="card">
        <h3 className="font-semibold mb-2">Campañas pasadas</h3>
        <ul className="text-sm">
          {campaigns.map((c: any) => (
            <li key={c.id} className="border-t border-slate-100 py-1.5 flex items-center justify-between">
              <div><b>{c.name}</b> <span className="text-xs text-slate-500">{c.created_at?.slice(0, 10)} · {c.status}</span></div>
              {c.roi && <span className="chip">ROI {c.roi.roi_pct}%</span>}
            </li>
          ))}
          {campaigns.length === 0 && <li className="text-slate-500">Sin campañas.</li>}
        </ul>
      </section>

      <section className="card">
        <h3 className="font-semibold mb-2">Leads acumulados</h3>
        <div className="text-sm">{leads.length} leads en la base de datos.</div>
      </section>
    </div>
  )
}
