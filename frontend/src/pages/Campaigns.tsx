import { useEffect, useState } from 'react'
import { api, Project } from '../api'
import ProgressBar, { ESTIMATED } from '../components/ProgressBar'

type Asset = {
  id: string; kind: string; title?: string; text?: string
  image_data?: string; meta?: any; approved: boolean; scheduled_at?: string
}
type Campaign = {
  id: string; name: string; goal?: string; brief?: string
  channels?: string[]; selectors?: any; status: string
  prediction?: any; roi?: any; assets?: Asset[]
}

const PLATFORMS = ['instagram', 'facebook', 'linkedin', 'tiktok', 'twitter', 'youtube']
const POST_KINDS = ['text+image', 'text', 'video', 'infographic']

export function CampaignsPage({ project }: { project: Project }) {
  const [list, setList] = useState<Campaign[]>([])
  const [current, setCurrent] = useState<Campaign | null>(null)
  const [busy, setBusy] = useState(false)
  const [showNew, setShowNew] = useState(false)

  async function refresh() {
    const r = await api.get<Campaign[]>(`/api/projects/${project.id}/campaigns`)
    setList(r)
    if (r.length && !current) selectCampaign(r[0].id)
  }
  async function selectCampaign(id: string) {
    const c = await api.get<Campaign>(`/api/projects/${project.id}/campaigns/${id}`)
    setCurrent(c)
  }
  useEffect(() => { refresh() }, [project.id])

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">5. Creatividad</h1>
          <p className="text-slate-600 text-sm">Selector de qué generar: ideas, eslogan, logo, folleto, newsletter, banner, posts (texto+imagen, vídeo, infografía).</p>
        </div>
        <button className="btn-primary" onClick={() => setShowNew(true)}>+ Nueva campaña</button>
      </header>

      <div className="grid md:grid-cols-12 gap-4">
        <aside className="md:col-span-3 card">
          <h3 className="font-semibold mb-2">Campañas</h3>
          <ul className="text-sm space-y-1">
            {list.map(c => (
              <li key={c.id}>
                <button className={`text-left w-full px-2 py-1 rounded ${current?.id === c.id ? 'bg-brand-50 text-brand-800 font-semibold' : 'hover:bg-slate-100'}`} onClick={() => selectCampaign(c.id)}>{c.name} <span className="text-xs text-slate-400">{c.status}</span></button>
              </li>
            ))}
            {list.length === 0 && <li className="text-slate-500">Aún no hay campañas.</li>}
          </ul>
        </aside>

        <div className="md:col-span-9 space-y-4">
          {!current && <div className="card text-slate-500">Selecciona una campaña o crea una nueva.</div>}
          {current && <CampaignDetail project={project} campaign={current} onChanged={() => { refresh(); selectCampaign(current.id) }} />}
        </div>
      </div>

      {showNew && <NewCampaignModal projectId={project.id} onClose={() => setShowNew(false)} onCreated={(id) => { setShowNew(false); refresh().then(() => selectCampaign(id)) }} setBusy={setBusy} />}
      {busy && (
        <div className="fixed bottom-4 right-4 bg-white border border-slate-200 rounded-lg shadow-xl p-4 text-sm w-[360px]" style={{ zIndex: 60 }}>
          <ProgressBar active={busy} estimatedSeconds={ESTIMATED.campaign.seconds} steps={ESTIMATED.campaign.steps} title="Generando campaña con IA" />
        </div>
      )}
    </div>
  )
}

function NewCampaignModal({ projectId, onClose, onCreated, setBusy }: { projectId: string; onClose: () => void; onCreated: (id: string) => void; setBusy: (b: boolean) => void }) {
  const [name, setName] = useState('Campaña ' + new Date().toLocaleDateString())
  const [goal, setGoal] = useState('Captación de leads')
  const [brief, setBrief] = useState('')
  const [sel, setSel] = useState({
    ideas: true, slogan: true, logo: false, brochure: false,
    newsletter: false, banner: false,
  })
  const [posts, setPosts] = useState<{ platform: string; kind: string; prompt: string }[]>([
    { platform: 'instagram', kind: 'text+image', prompt: '' },
  ])

  function togglePost(i: number, field: 'platform' | 'kind' | 'prompt', v: string) {
    const next = [...posts]; (next[i] as any)[field] = v; setPosts(next)
  }
  function addPost() { setPosts([...posts, { platform: 'instagram', kind: 'text+image', prompt: '' }]) }
  function delPost(i: number) { setPosts(posts.filter((_, k) => k !== i)) }

  async function submit() {
    setBusy(true)
    try {
      const c = await api.post<{ id: string }>(`/api/projects/${projectId}/campaigns`, {
        name, goal, brief,
        selectors: { ...sel, posts },
        channels: posts.map(p => p.platform),
      })
      onCreated(c.id)
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
        <h2 className="text-xl font-semibold mb-3">Nueva campaña</h2>
        <div className="grid md:grid-cols-2 gap-3 mb-3">
          <div><label className="label">Nombre</label><input className="input" value={name} onChange={e => setName(e.target.value)} /></div>
          <div><label className="label">Objetivo</label><input className="input" value={goal} onChange={e => setGoal(e.target.value)} /></div>
        </div>
        <label className="label">Brief / contexto</label>
        <textarea className="input min-h-[80px] mb-3" value={brief} onChange={e => setBrief(e.target.value)} />

        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
          {(['ideas', 'slogan', 'logo', 'brochure', 'newsletter', 'banner'] as const).map(k => (
            <label key={k} className="flex items-center gap-2 text-sm bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
              <input type="checkbox" checked={(sel as any)[k]} onChange={e => setSel({ ...sel, [k]: e.target.checked })} />
              <span className="capitalize">{k}</span>
            </label>
          ))}
        </div>

        <div className="mb-3">
          <div className="label mb-1">Posts redes sociales</div>
          {posts.map((p, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 mb-2">
              <select className="input col-span-3" value={p.platform} onChange={e => togglePost(i, 'platform', e.target.value)}>
                {PLATFORMS.map(x => <option key={x}>{x}</option>)}
              </select>
              <select className="input col-span-3" value={p.kind} onChange={e => togglePost(i, 'kind', e.target.value)}>
                {POST_KINDS.map(x => <option key={x}>{x}</option>)}
              </select>
              <input className="input col-span-5" placeholder="Idea / prompt opcional" value={p.prompt} onChange={e => togglePost(i, 'prompt', e.target.value)} />
              <button className="btn-ghost col-span-1" onClick={() => delPost(i)}>✕</button>
            </div>
          ))}
          <button className="btn-secondary" onClick={addPost}>+ Añadir post</button>
        </div>

        <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-slate-200">
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn-primary" onClick={submit}>Generar campaña con IA</button>
        </div>
      </div>
    </div>
  )
}

function CampaignDetail({ project, campaign, onChanged }: { project: Project; campaign: Campaign; onChanged: () => void }) {
  const [predBudget, setPredBudget] = useState(500)
  const [audienceSize, setAudienceSize] = useState(1000)
  const [duration, setDuration] = useState(30)
  const [pBusy, setPBusy] = useState(false)
  const [rBusy, setRBusy] = useState(false)
  const [eBusy, setEBusy] = useState(false)

  const [costPer, setCostPer] = useState(20)
  const [price, setPrice] = useState(60)
  const [fixed, setFixed] = useState(0)

  async function predict() {
    setPBusy(true)
    try {
      await api.post(`/api/projects/${project.id}/campaigns/${campaign.id}/predict`, {
        audience_size: audienceSize, budget_eur: predBudget, duration_days: duration,
      })
      onChanged()
    } finally { setPBusy(false) }
  }
  async function roi() {
    setRBusy(true)
    try {
      await api.post(`/api/projects/${project.id}/campaigns/${campaign.id}/roi`, {
        cost_per_unit_eur: costPer, selling_price_eur: price, fixed_costs_eur: fixed,
        audience_size: audienceSize, duration_days: duration,
      })
      onChanged()
    } finally { setRBusy(false) }
  }
  async function emailBatch() {
    setEBusy(true)
    try {
      const r = await api.post(`/api/projects/${project.id}/campaigns/${campaign.id}/email-batch`, { use_ai: true, ab_test: true })
      alert(`Preparados ${r.count} emails con tracking real. ${r.note || ''}`)
      onChanged()
    } catch (e: any) { alert(e.message) }
    finally { setEBusy(false) }
  }
  async function approve(aid: string) {
    await api.post(`/api/projects/${project.id}/campaigns/${campaign.id}/assets/${aid}/approve`)
    onChanged()
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-xl font-semibold">{campaign.name}</h2>
            <div className="text-sm text-slate-500">{campaign.goal}</div>
          </div>
          <span className="chip">{campaign.status}</span>
        </div>
        {campaign.brief && <p className="text-sm text-slate-700">{campaign.brief}</p>}
      </div>

      {(campaign.assets || []).length > 0 && (
        <div className="grid md:grid-cols-2 gap-3">
          {(campaign.assets || []).map(a => (
            <AssetCard key={a.id} asset={a} onApprove={() => approve(a.id)} />
          ))}
        </div>
      )}

      <div className="card grid md:grid-cols-2 gap-6">
        <div>
          <h3 className="font-semibold mb-2">7. Predicción de resultados</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div><label className="label">Audiencia</label><input className="input" type="number" value={audienceSize} onChange={e => setAudienceSize(parseInt(e.target.value || '0', 10))} /></div>
            <div><label className="label">Presupuesto €</label><input className="input" type="number" value={predBudget} onChange={e => setPredBudget(parseFloat(e.target.value || '0'))} /></div>
            <div><label className="label">Días</label><input className="input" type="number" value={duration} onChange={e => setDuration(parseInt(e.target.value || '0', 10))} /></div>
          </div>
          <button className="btn-primary mt-3" onClick={predict} disabled={pBusy}>{pBusy ? 'Calculando…' : 'Predecir'}</button>
          <ProgressBar active={pBusy} estimatedSeconds={ESTIMATED.prediction.seconds} steps={ESTIMATED.prediction.steps} />
          {campaign.prediction && (
            <div className="mt-3 text-sm">
              <div className="font-semibold">≈ {campaign.prediction.total_conversiones_estimadas} conversiones</div>
              <table className="w-full mt-2">
                <thead className="text-left text-slate-500"><tr><th>Canal</th><th>CTR%</th><th>Conv%</th><th>Conv.</th></tr></thead>
                <tbody>{(campaign.prediction.channels || []).map((c: any) => (
                  <tr key={c.channel} className="border-t border-slate-100"><td>{c.channel}</td><td>{c.ctr_pct}</td><td>{c.conv_pct}</td><td>{c.conversiones_estimadas}</td></tr>
                ))}</tbody>
              </table>
              {campaign.prediction.ai_refinement?.summary && <p className="mt-2 text-slate-700">{campaign.prediction.ai_refinement.summary}</p>}
            </div>
          )}
        </div>
        <div>
          <h3 className="font-semibold mb-2">8. ROI</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div><label className="label">Coste/ud €</label><input className="input" type="number" value={costPer} onChange={e => setCostPer(parseFloat(e.target.value || '0'))} /></div>
            <div><label className="label">Precio venta €</label><input className="input" type="number" value={price} onChange={e => setPrice(parseFloat(e.target.value || '0'))} /></div>
            <div><label className="label">Costes fijos €</label><input className="input" type="number" value={fixed} onChange={e => setFixed(parseFloat(e.target.value || '0'))} /></div>
          </div>
          <button className="btn-primary mt-3" onClick={roi} disabled={rBusy}>{rBusy ? 'Calculando…' : 'Calcular ROI'}</button>
          <ProgressBar active={rBusy} estimatedSeconds={ESTIMATED.roi.seconds} steps={ESTIMATED.roi.steps} />
          {campaign.roi && (
            <div className="mt-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><div className="label">Ingresos</div><div>€{campaign.roi.revenue_eur}</div></div>
                <div><div className="label">Coste total</div><div>€{campaign.roi.total_cost_eur}</div></div>
                <div><div className="label">Beneficio</div><div className="font-semibold">€{campaign.roi.profit_eur}</div></div>
                <div><div className="label">ROI</div><div className="font-semibold text-brand-700">{campaign.roi.roi_pct}%</div></div>
                <div><div className="label">Punto equilibrio</div><div>{campaign.roi.breakeven_units}</div></div>
                <div><div className="label">CAC</div><div>€{campaign.roi.cac_eur}</div></div>
              </div>
              {campaign.roi.attribution_per_channel?.length > 0 && (
                <div className="mt-2">
                  <div className="label">Atribución por canal</div>
                  <ul className="text-xs">
                    {campaign.roi.attribution_per_channel.map((a: any) => (
                      <li key={a.channel}>{a.channel}: {a.share_pct}% → €{a.estimated_profit_eur}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-2">📬 Email batch a leads (con tracking)</h3>
        <p className="text-sm text-slate-600">Genera emails personalizados (variantes A/B) para todos los leads del proyecto. El backend inserta pixel de apertura y reescribe links para medir clicks.</p>
        <button className="btn-primary mt-2" onClick={emailBatch} disabled={eBusy}>{eBusy ? 'Preparando…' : 'Preparar batch'}</button>
        <ProgressBar active={eBusy} estimatedSeconds={ESTIMATED.email_batch.seconds} steps={ESTIMATED.email_batch.steps} title="Batch de emails" />
      </div>
    </div>
  )
}

function AssetCard({ asset, onApprove }: { asset: Asset; onApprove: () => void }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="chip mr-2">{asset.kind}</span>
          <span className="font-semibold">{asset.title}</span>
        </div>
        {!asset.approved && <button className="btn-secondary" onClick={onApprove}>Aprobar</button>}
        {asset.approved && <span className="chip chip-ok">Aprobado</span>}
      </div>
      {asset.image_data && (
        <img src={`data:image/png;base64,${asset.image_data}`} alt={asset.title} className="rounded-md max-h-64 object-contain bg-slate-50 w-full mb-2" />
      )}
      {asset.text && (
        <pre className="whitespace-pre-wrap text-sm bg-slate-50 rounded p-2 max-h-64 overflow-auto">{asset.text}</pre>
      )}
      {asset.meta?.platform && <div className="text-xs text-slate-500 mt-1">Plataforma: {asset.meta.platform}</div>}
    </div>
  )
}
