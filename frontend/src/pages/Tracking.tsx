import { useEffect, useState } from 'react'
import { api, Project } from '../api'

export function TrackingPage({ project }: { project: Project }) {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [cid, setCid] = useState<string>('')
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    api.get(`/api/projects/${project.id}/campaigns`).then((cs: any) => { setCampaigns(cs); if (cs[0]) setCid(cs[0].id) })
  }, [project.id])

  useEffect(() => {
    if (!cid) return
    api.get(`/api/track/dashboard/${cid}`).then(setData)
  }, [cid])

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">9. Tracking de mailing</h1>
        <p className="text-slate-600 text-sm">Aperturas (pixel), clicks (redirect), bajas — agregado y por destinatario, con A/B.</p>
      </header>

      <section className="card">
        <label className="label">Campaña</label>
        <select className="input md:max-w-md" value={cid} onChange={e => setCid(e.target.value)}>
          {campaigns.map((c: any) => <option key={c.id} value={c.id}>{c.name} · {c.status}</option>)}
        </select>
      </section>

      {data && (
        <>
          <section className="grid md:grid-cols-4 gap-3">
            <Kpi label="Enviados" value={data.total_sent} />
            <Kpi label="Apertura" value={`${data.open_rate_pct}%`} />
            <Kpi label="Clicks" value={`${data.click_rate_pct}%`} />
            <Kpi label="Bajas" value={`${data.unsubscribe_rate_pct}%`} />
          </section>

          {Object.keys(data.by_variant || {}).length > 0 && (
            <section className="card">
              <h3 className="font-semibold mb-2">A/B</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500"><tr><th>Variante</th><th>Enviados</th><th>Aperturas</th><th>Clicks</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_variant).map(([v, s]: any) => (
                    <tr key={v} className="border-t border-slate-100">
                      <td>{v}</td><td>{s.sent}</td><td>{s.open}</td><td>{s.click}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section className="card overflow-x-auto">
            <h3 className="font-semibold mb-2">Detalle por destinatario</h3>
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500"><tr><th>Email</th><th>Asunto</th><th>Var.</th><th>Aperturas</th><th>Clicks</th><th>Última apertura</th><th>Último click</th><th>Baja</th></tr></thead>
              <tbody>
                {(data.sends || []).map((s: any) => (
                  <tr key={s.id} className="border-t border-slate-100">
                    <td className="py-1.5">{s.to}</td>
                    <td className="max-w-[260px] truncate" title={s.subject}>{s.subject}</td>
                    <td>{s.variant}</td>
                    <td>{s.opens}</td>
                    <td>{s.clicks}</td>
                    <td className="text-xs">{s.opened_at?.replace('T', ' ').slice(0, 16) || '-'}</td>
                    <td className="text-xs">{s.last_click_at?.replace('T', ' ').slice(0, 16) || '-'}</td>
                    <td>{s.unsubscribed ? '✓' : ''}</td>
                  </tr>
                ))}
                {(data.sends || []).length === 0 && <tr><td colSpan={8} className="text-center text-slate-500 py-3">Sin envíos. Genera un batch desde Creatividad.</td></tr>}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  )
}

function Kpi({ label, value }: { label: string; value: any }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  )
}
