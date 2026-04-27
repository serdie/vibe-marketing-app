import { useEffect, useState } from 'react'
import { api, Project, getApiBase, setApiBase } from './api'
import { Sidebar } from './components/Sidebar'
import { OwnerPage } from './pages/Owner'
import { GapsPage } from './pages/Gaps'
import { ProductPage } from './pages/Product'
import { LeadsPage } from './pages/Leads'
import { CampaignsPage } from './pages/Campaigns'
import { AutomationsPage } from './pages/Automations'
import { TrackingPage } from './pages/Tracking'
import { HistoryPage } from './pages/History'
import { SettingsPage } from './pages/Settings'
import { DashboardPage } from './pages/Dashboard'
import { CalendarPage } from './pages/Calendar'

export type SectionId =
  | 'dashboard'
  | 'owner' | 'gaps' | 'product' | 'leads'
  | 'campaigns' | 'calendar' | 'automations'
  | 'tracking' | 'history' | 'settings'

const SECTION_ORDER: SectionId[] = [
  'owner', 'gaps', 'product', 'leads', 'campaigns',
  'calendar', 'automations', 'tracking', 'history',
]

export default function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [project, setProject] = useState<Project | null>(null)
  const [section, setSection] = useState<SectionId>('owner')
  const [loading, setLoading] = useState(true)
  const [showApiBaseModal, setShowApiBaseModal] = useState(false)
  const [apiBaseInput, setApiBaseInput] = useState(getApiBase())
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [showNewProject, setShowNewProject] = useState(false)

  async function checkApi() {
    try { await api.get('/healthz'); setApiOk(true) } catch { setApiOk(false) }
  }

  async function refreshProjects() {
    try {
      const ps = await api.get<Project[]>('/api/projects')
      setProjects(ps)
    } catch (e) { console.warn(e) }
    finally { setLoading(false) }
  }

  async function refreshProject() {
    if (!project) return
    const full = await api.get<Project>('/api/projects/' + project.id)
    setProject(full)
  }

  useEffect(() => { checkApi().then(refreshProjects) }, [])

  async function selectProject(id: string) {
    const full = await api.get<Project>('/api/projects/' + id)
    setProject(full)
    setSection('owner')
  }

  async function deleteProject(id: string) {
    if (!confirm('¿Eliminar este proyecto y todos sus datos?')) return
    await api.del('/api/projects/' + id)
    if (project?.id === id) setProject(null)
    refreshProjects()
  }

  function nextSection() {
    const idx = SECTION_ORDER.indexOf(section)
    if (idx >= 0 && idx < SECTION_ORDER.length - 1) {
      setSection(SECTION_ORDER[idx + 1])
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  // Progress flags for sidebar
  const progress = project ? {
    owner: !!(project.research as any)?.profile && Object.keys((project.research as any).profile).length > 0,
    gaps: !!(project.gaps && Object.keys(project.gaps).length > 0),
    product: Array.isArray(project.products) && project.products.length > 0,
    leads: false, // computed inside the page if needed
    campaigns: false,
  } : {}

  return (
    <div className="min-h-screen flex">
      <Sidebar
        section={section}
        onSection={setSection}
        projects={projects}
        currentProjectId={project?.id}
        onSelectProject={selectProject}
        onNewProject={() => setShowNewProject(true)}
        onDeleteProject={deleteProject}
        apiOk={apiOk}
        onConfigApi={() => setShowApiBaseModal(true)}
        progress={progress as any}
      />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="max-w-6xl mx-auto p-6 lg:p-8">
          {loading && <div className="text-slate-500">Cargando…</div>}
          {!loading && !project && section !== 'settings' && (
            <div className="card max-w-2xl">
              <h2 className="text-xl font-semibold mb-2">Bienvenido a Vibe Marketing</h2>
              <p className="text-slate-600 mb-4">
                Crea un proyecto para empezar. La cadena: identificar al propietario → detectar carencias → definir
                productos e ICP → generar leads → crear campañas con IA → automatizar → predecir/medir ROI →
                trackear emails. Cada paso usa lo del anterior.
              </p>
              <button className="btn-primary" onClick={() => setShowNewProject(true)}>+ Nuevo proyecto</button>
              {projects.length > 0 && (
                <div className="mt-4 text-sm">
                  <div className="label mb-1">Proyectos existentes:</div>
                  <ul className="space-y-1">
                    {projects.map(p => (
                      <li key={p.id} className="flex justify-between items-center">
                        <button className="text-brand-700 hover:underline" onClick={() => selectProject(p.id)}>{p.name}</button>
                        <button className="text-rose-600 text-xs hover:underline" onClick={() => deleteProject(p.id)}>Eliminar</button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          {!loading && project && section === 'dashboard' && <DashboardPage project={project} />}
          {!loading && project && section === 'owner' && <OwnerPage project={project} onUpdate={refreshProject} onNext={nextSection} />}
          {!loading && project && section === 'gaps' && <GapsPage project={project} onUpdate={refreshProject} onNext={nextSection} />}
          {!loading && project && section === 'product' && <ProductPage project={project} onUpdate={refreshProject} onNext={nextSection} />}
          {!loading && project && section === 'leads' && <LeadsPage project={project} onNext={nextSection} />}
          {!loading && project && section === 'campaigns' && <CampaignsPage project={project} />}
          {!loading && project && section === 'calendar' && <CalendarPage project={project} />}
          {!loading && project && section === 'automations' && <AutomationsPage project={project} />}
          {!loading && project && section === 'tracking' && <TrackingPage project={project} />}
          {!loading && project && section === 'history' && <HistoryPage project={project} />}
          {section === 'settings' && <SettingsPage />}
        </div>
      </main>

      {showNewProject && (
        <NewProjectModal
          onClose={() => setShowNewProject(false)}
          onCreated={async (p) => {
            setShowNewProject(false)
            await refreshProjects()
            const full = await api.get<Project>('/api/projects/' + p.id)
            setProject(full)
            setSection('owner')
          }}
        />
      )}

      {showApiBaseModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="card w-[420px]">
            <h3 className="font-semibold mb-3">Backend API base URL</h3>
            <p className="text-sm text-slate-600 mb-3">URL pública del backend FastAPI.</p>
            <input className="input mb-3" value={apiBaseInput} onChange={e => setApiBaseInput(e.target.value)} />
            <div className="flex gap-2 justify-end">
              <button className="btn-ghost" onClick={() => setShowApiBaseModal(false)}>Cancelar</button>
              <button className="btn-primary" onClick={() => {
                setApiBase(apiBaseInput.trim())
                setShowApiBaseModal(false)
                window.location.reload()
              }}>Guardar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function NewProjectModal({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Project) => void }) {
  const [name, setName] = useState('')
  const [ownerType, setOwnerType] = useState('empresa')
  const [website, setWebsite] = useState('')
  const [fullName, setFullName] = useState('')
  const [cv, setCv] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function create() {
    if (!name.trim()) { setErr('El nombre es obligatorio'); return }
    setBusy(true); setErr(null)
    try {
      const p = await api.post<Project>('/api/projects', {
        name: name.trim(),
        owner_type: ownerType,
        website: website.trim() || null,
        full_name: fullName.trim() || null,
        cv_text: cv.trim() || null,
      })
      onCreated(p)
    } catch (e: any) { setErr(e.message); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="card w-[560px] max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold mb-3">Nuevo proyecto / cliente</h3>
        <p className="text-sm text-slate-600 mb-3">Estos datos arrancan la cadena. Después podrás afinarlos en la pestaña "Propietario".</p>
        <div className="space-y-3">
          <div>
            <label className="label">Nombre interno del proyecto *</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="Ej. Cliente Diemy 2026" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
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
              <input className="input" value={fullName} onChange={e => setFullName(e.target.value)} placeholder="ACME S.L." />
            </div>
          </div>
          <div>
            <label className="label">URL del sitio web</label>
            <input className="input" value={website} onChange={e => setWebsite(e.target.value)} placeholder="https://..." />
          </div>
          <div>
            <label className="label">CV / información extra (opcional, pero recomendado)</label>
            <textarea className="input min-h-[100px]" value={cv} onChange={e => setCv(e.target.value)}
              placeholder="Pega aquí experiencia, sectores, certificaciones, productos, hechos diferenciales…" />
          </div>
          {err && <div className="text-rose-600 text-sm">{err}</div>}
          <div className="flex gap-2 justify-end pt-2">
            <button className="btn-ghost" onClick={onClose} disabled={busy}>Cancelar</button>
            <button className="btn-primary" onClick={create} disabled={busy}>{busy ? 'Creando…' : 'Crear y empezar'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
