import { useEffect, useState } from 'react'
import { api, getApiBase, ProviderCatalog, setApiBase } from '../api'

export function SettingsPage() {
  const [catalog, setCatalog] = useState<ProviderCatalog[]>([])
  const [configured, setConfigured] = useState<any[]>([])
  const [prefs, setPrefs] = useState<Record<string, string>>({})
  const [base, setBase] = useState(getApiBase())
  const [editing, setEditing] = useState<string | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [baseUrlInput, setBaseUrlInput] = useState('')
  const [modelOverride, setModelOverride] = useState<Record<string, string>>({})
  const [testResult, setTestResult] = useState<Record<string, any>>({})

  async function refresh() {
    const c = await api.get<{ providers: ProviderCatalog[] }>('/api/settings/providers/catalog')
    setCatalog(c.providers)
    const cur = await api.get<{ configured: any[]; preferences: Record<string, string> }>('/api/settings/providers')
    setConfigured(cur.configured)
    setPrefs(cur.preferences)
  }
  useEffect(() => { refresh().catch(() => {}) }, [])

  async function save(p: ProviderCatalog) {
    await api.post('/api/settings/providers', {
      id: p.id,
      api_key: keyInput,
      base_url: baseUrlInput || null,
      models: { ...p.default_models, ...modelOverride },
      enabled: true,
    })
    setEditing(null); setKeyInput(''); setBaseUrlInput(''); setModelOverride({})
    refresh()
  }
  async function del(id: string) { await api.del('/api/settings/providers/' + id); refresh() }
  async function test(id: string) {
    const r = await api.post('/api/settings/providers/' + id + '/test')
    setTestResult({ ...testResult, [id]: r })
  }
  async function setPref(task: string, providerId: string) {
    await api.post('/api/settings/providers/preference', { task, provider_id: providerId })
    refresh()
  }

  function isConfigured(id: string) { return configured.find(c => c.id === id) }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Ajustes</h1>
        <p className="text-slate-600 text-sm">Conecta proveedores de IA y MCP. Las claves se guardan en el backend.</p>
      </header>

      <section className="card">
        <h2 className="font-semibold mb-2">Backend API</h2>
        <div className="flex gap-2">
          <input className="input" value={base} onChange={e => setBase(e.target.value)} />
          <button className="btn-primary" onClick={() => { setApiBase(base.trim()); window.location.reload() }}>Guardar y recargar</button>
        </div>
        <p className="text-xs text-slate-500 mt-1">URL pública de tu FastAPI (ej. https://vibe-marketing-backend.fly.dev).</p>
      </section>

      <section className="card">
        <h2 className="font-semibold mb-2">Preferencias por tarea</h2>
        <div className="grid md:grid-cols-3 gap-2 text-sm">
          {['text', 'image', 'grounded', 'video', 'audio'].map(task => (
            <div key={task} className="flex items-center gap-2">
              <span className="label w-20">{task}</span>
              <select className="input" value={prefs[task] || ''} onChange={e => setPref(task, e.target.value)}>
                <option value="">— elegir —</option>
                {configured.filter(c => c.tasks.includes(task)).map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-semibold mb-2">Proveedores de IA</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {catalog.map(p => {
            const cfg = isConfigured(p.id)
            const tr = testResult[p.id]
            return (
              <div key={p.id} className="card">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="font-semibold">{p.name}</h3>
                  {cfg ? (
                    <span className="chip chip-ok">Configurado</span>
                  ) : (
                    <span className="chip">Sin configurar</span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mb-2">Tareas: {p.tasks.join(', ')}</p>
                <a href={p.docs} target="_blank" rel="noreferrer" className="text-xs text-brand-700 hover:underline">Conseguir API key →</a>

                {editing === p.id ? (
                  <div className="mt-3 space-y-2">
                    <input className="input" placeholder="API key" value={keyInput} onChange={e => setKeyInput(e.target.value)} />
                    {p.needs_base_url && <input className="input" placeholder="Base URL (ej. http://localhost:11434/v1)" value={baseUrlInput} onChange={e => setBaseUrlInput(e.target.value)} />}
                    {Object.entries(p.default_models).map(([task, def]) => (
                      <div key={task} className="grid grid-cols-3 gap-2 items-center">
                        <span className="label">{task}</span>
                        <select className="input col-span-2" value={modelOverride[task] || def} onChange={e => setModelOverride({ ...modelOverride, [task]: e.target.value })}>
                          {(p.models.length ? p.models : [def]).concat([def]).filter((v, i, a) => a.indexOf(v) === i).map(m => <option key={m}>{m}</option>)}
                        </select>
                      </div>
                    ))}
                    <div className="flex gap-2">
                      <button className="btn-primary" onClick={() => save(p)}>Guardar</button>
                      <button className="btn-ghost" onClick={() => setEditing(null)}>Cancelar</button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button className="btn-secondary" onClick={() => { setEditing(p.id); setKeyInput(''); setBaseUrlInput(cfg?.base_url || '') }}>{cfg ? 'Editar' : 'Configurar'}</button>
                    {cfg && <button className="btn-ghost" onClick={() => test(p.id)}>Probar</button>}
                    {cfg && <button className="btn-danger" onClick={() => del(p.id)}>Eliminar</button>}
                  </div>
                )}
                {tr && (
                  <div className={`mt-2 text-xs ${tr.ok ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {tr.ok ? `OK (${tr.model})` : `Error: ${tr.error || ''}`}
                    {tr.sample && <div className="text-slate-500">→ {tr.sample}</div>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="card">
        <h2 className="font-semibold mb-2">Conexión MCP</h2>
        <p className="text-sm text-slate-600 mb-2">El backend expone un servidor MCP HTTP minimalista. Apunta tu cliente (Claude Desktop, ChatGPT, Cursor, Devin) a:</p>
        <pre className="bg-slate-50 rounded p-3 text-sm">{getApiBase()}/api/mcp</pre>
        <p className="text-xs text-slate-500 mt-2">Tools expuestos: list_projects, get_project, list_leads, list_campaigns, generate_text, generate_image.</p>
      </section>
    </div>
  )
}
