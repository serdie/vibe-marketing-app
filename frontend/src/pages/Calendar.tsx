import { useEffect, useState } from 'react'
import { api, Project } from '../api'

type Item = {
  campaign_id: string; campaign_name: string;
  asset_id: string; kind: string; title?: string;
  approved: boolean; scheduled_at?: string; published_at?: string;
}

export function CalendarPage({ project }: { project: Project }) {
  const [items, setItems] = useState<Item[]>([])
  async function refresh() {
    const r = await api.get<Item[]>(`/api/projects/${project.id}/calendar`)
    setItems(r)
  }
  useEffect(() => { refresh() }, [project.id])

  async function schedule(asset_id: string) {
    const when = prompt('Fecha/hora ISO (ej: 2025-12-01T10:00:00):')
    if (!when) return
    await api.post(`/api/projects/${project.id}/calendar/schedule`, { asset_id, when })
    refresh()
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Calendario editorial</h1>
        <p className="text-slate-600 text-sm">Todos los assets generados, su estado y fecha programada.</p>
      </header>
      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500"><tr><th>Campaña</th><th>Tipo</th><th>Título</th><th>Estado</th><th>Programado</th><th>Publicado</th><th></th></tr></thead>
          <tbody>
            {items.map(it => (
              <tr key={it.asset_id} className="border-t border-slate-100">
                <td className="py-1.5">{it.campaign_name}</td>
                <td><span className="chip">{it.kind}</span></td>
                <td>{it.title}</td>
                <td>{it.approved ? <span className="chip chip-ok">aprobado</span> : <span className="chip chip-warn">pendiente</span>}</td>
                <td>{it.scheduled_at?.replace('T', ' ').slice(0, 16) || '-'}</td>
                <td>{it.published_at?.replace('T', ' ').slice(0, 16) || '-'}</td>
                <td><button className="btn-ghost" onClick={() => schedule(it.asset_id)}>Programar</button></td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="text-center text-slate-500 py-3">No hay assets aún.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  )
}
