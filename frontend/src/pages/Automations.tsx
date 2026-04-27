import { useEffect, useState } from 'react'
import { api, Project } from '../api'

type Auto = {
  id: string; name: string;
  trigger_kind: string; trigger_config: any;
  action_kind: string; action_config: any;
  enabled: boolean; last_run?: string; runs?: any[]
}

export function AutomationsPage({ project }: { project: Project }) {
  const [list, setList] = useState<Auto[]>([])
  const [name, setName] = useState('Programar post diario')
  const [trigger, setTrigger] = useState('schedule')
  const [triggerCfg, setTriggerCfg] = useState('{"cron":"0 9 * * *"}')
  const [action, setAction] = useState('publish_post')
  const [actionCfg, setActionCfg] = useState('{"asset_id":""}')
  const [comments, setComments] = useState('Me encanta vuestro producto!\nNo entiendo el precio.\nMuy malo, no lo recomiendo.')
  const [sentiment, setSentiment] = useState<any[] | null>(null)

  async function refresh() {
    const r = await api.get<Auto[]>(`/api/projects/${project.id}/automations`)
    setList(r)
  }
  useEffect(() => { refresh() }, [project.id])

  async function create() {
    await api.post(`/api/projects/${project.id}/automations`, {
      name, trigger_kind: trigger, trigger_config: parseJson(triggerCfg),
      action_kind: action, action_config: parseJson(actionCfg), enabled: true,
    })
    refresh()
  }
  async function run(id: string) {
    const r = await api.post(`/api/projects/${project.id}/automations/${id}/run`)
    alert(JSON.stringify(r, null, 2))
    refresh()
  }
  async function del(id: string) {
    await api.del(`/api/projects/${project.id}/automations/${id}`); refresh()
  }
  async function runSentiment() {
    const list = comments.split('\n').filter(Boolean)
    const r = await api.post(`/api/projects/${project.id}/automations/_/sentiment`, { comments: list })
    setSentiment(Array.isArray(r) ? r : (r.data || []))
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">6. Automatizaciones</h1>
        <p className="text-slate-600 text-sm">Triggers (horario / comentario / nuevo lead) → acción (publicar, responder, etiquetar). Aprobación humana antes de publicar.</p>
      </header>

      <section className="card">
        <h3 className="font-semibold mb-2">Crear automatización</h3>
        <div className="grid md:grid-cols-12 gap-2 text-sm">
          <input className="input md:col-span-3" placeholder="Nombre" value={name} onChange={e => setName(e.target.value)} />
          <select className="input md:col-span-2" value={trigger} onChange={e => setTrigger(e.target.value)}>
            <option value="schedule">schedule</option><option value="comment">comment</option><option value="like">like</option><option value="new_lead">new_lead</option>
          </select>
          <input className="input md:col-span-3" placeholder='Trigger config JSON' value={triggerCfg} onChange={e => setTriggerCfg(e.target.value)} />
          <select className="input md:col-span-2" value={action} onChange={e => setAction(e.target.value)}>
            <option value="publish_post">publish_post</option><option value="webhook">webhook (Make/n8n/Zapier)</option><option value="reply_comment">reply_comment</option><option value="send_email">send_email</option><option value="tag_lead">tag_lead</option>
          </select>
          <input className="input md:col-span-2" placeholder='Action config JSON' value={actionCfg} onChange={e => setActionCfg(e.target.value)} />
        </div>
        <button className="btn-primary mt-2" onClick={create}>Crear</button>
        <details className="mt-3 text-xs text-slate-600">
          <summary className="cursor-pointer">Ejemplos de configuración</summary>
          <div className="mt-2 space-y-2">
            <div><b>Schedule cron (todos los días a las 9:00):</b><pre className="bg-slate-50 p-2 rounded">{'{ "kind": "cron", "cron": "0 9 * * *" }'}</pre></div>
            <div><b>Schedule una vez:</b><pre className="bg-slate-50 p-2 rounded">{'{ "kind": "once", "at": "2025-05-01T09:00:00Z" }'}</pre></div>
            <div><b>Schedule cada N segundos:</b><pre className="bg-slate-50 p-2 rounded">{'{ "kind": "interval", "seconds": 3600 }'}</pre></div>
            <div><b>Acción webhook (para RRSS vía Make/n8n/Zapier):</b><pre className="bg-slate-50 p-2 rounded">{'{ "url": "https://hook.eu1.make.com/abc", "asset_id": "...", "payload": { "network": "instagram" } }'}</pre></div>
            <div><b>Acción send_email:</b><pre className="bg-slate-50 p-2 rounded">{'{ "to": "cliente@empresa.com", "subject": "Hola", "html": "<p>Hola</p>" }'}</pre></div>
          </div>
        </details>
      </section>

      <section className="card">
        <h3 className="font-semibold mb-2">Automatizaciones activas</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500"><tr><th>Nombre</th><th>Trigger</th><th>Acción</th><th>Última ejecución</th><th></th></tr></thead>
          <tbody>
            {list.map(a => (
              <tr key={a.id} className="border-t border-slate-100">
                <td className="py-1.5">{a.name}</td>
                <td><span className="chip">{a.trigger_kind}</span></td>
                <td><span className="chip">{a.action_kind}</span></td>
                <td className="text-xs">{a.last_run?.replace('T', ' ').slice(0, 16) || '-'}</td>
                <td className="space-x-1">
                  <button className="btn-secondary" onClick={() => run(a.id)}>▶ Ejecutar</button>
                  <button className="btn-ghost" onClick={() => del(a.id)}>✕</button>
                </td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={5} className="text-center text-slate-500 py-3">Sin automatizaciones.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3 className="font-semibold mb-2">Análisis de sentimiento de comentarios</h3>
        <textarea className="input min-h-[100px]" value={comments} onChange={e => setComments(e.target.value)} />
        <button className="btn-primary mt-2" onClick={runSentiment}>Analizar</button>
        {sentiment && (
          <ul className="mt-3 text-sm space-y-1">
            {sentiment.map((s: any, i) => (
              <li key={i} className="border-t border-slate-100 pt-1">
                <span className={`chip ${s.sentimiento === 'positivo' ? 'chip-ok' : s.sentimiento === 'negativo' ? 'chip-err' : 'chip-warn'}`}>{s.sentimiento}</span>{' '}
                <b>{s.texto}</b>
                {s.sugerencia_respuesta && <div className="text-xs text-slate-600 mt-0.5">↪ {s.sugerencia_respuesta}</div>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function parseJson(s: string) { try { return JSON.parse(s) } catch { return {} } }
