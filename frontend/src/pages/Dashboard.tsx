import { useEffect, useState } from 'react'
import { api, Project } from '../api'

export function DashboardPage({ project }: { project: Project }) {
  const [k, setK] = useState<any>(null)
  useEffect(() => { api.get(`/api/kpis/${project.id}`).then(setK) }, [project.id])
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-slate-600 text-sm">Visión general del proyecto.</p>
      </header>
      {k && (
        <div className="grid md:grid-cols-4 gap-3">
          <Kpi label="Leads" v={k.leads} />
          <Kpi label="Campañas" v={k.campaigns} />
          <Kpi label="Assets" v={`${k.approved_assets}/${k.assets}`} />
          <Kpi label="Automatizaciones" v={k.automations} />
          <Kpi label="Emails enviados" v={k.emails_sent} />
          <Kpi label="Apertura" v={`${k.open_rate_pct}%`} />
          <Kpi label="Click" v={`${k.click_rate_pct}%`} />
          <Kpi label="Beneficio est." v={`€${k.estimated_profit_eur}`} />
        </div>
      )}
    </div>
  )
}

function Kpi({ label, v }: { label: string; v: any }) {
  return <div className="card"><div className="label">{label}</div><div className="text-2xl font-bold">{v}</div></div>
}
