import { Project } from '../api'
import type { SectionId } from '../App'

type ProgressKey = 'owner' | 'gaps' | 'product' | 'leads' | 'campaigns'

const SECTIONS: { id: SectionId; label: string; emoji: string; group: string; progressKey?: ProgressKey }[] = [
  { id: 'dashboard', label: 'Dashboard', emoji: '📊', group: 'general' },
  { id: 'owner', label: '1. Propietario', emoji: '👤', group: 'analisis', progressKey: 'owner' },
  { id: 'gaps', label: '2. Carencias y competencia', emoji: '🔍', group: 'analisis', progressKey: 'gaps' },
  { id: 'product', label: '3. Productos e ICP', emoji: '🛍️', group: 'analisis', progressKey: 'product' },
  { id: 'leads', label: '4. Leads y scraping', emoji: '🎯', group: 'accion' },
  { id: 'campaigns', label: '5. Creatividad', emoji: '🎨', group: 'accion' },
  { id: 'calendar', label: 'Calendario editorial', emoji: '📅', group: 'accion' },
  { id: 'automations', label: '6. Automatizaciones', emoji: '⚙️', group: 'accion' },
  { id: 'tracking', label: '9. Tracking mailing', emoji: '📬', group: 'medicion' },
  { id: 'history', label: 'Histórico (BD)', emoji: '🗄️', group: 'medicion' },
  { id: 'settings', label: 'Ajustes (proveedores IA + MCP)', emoji: '🔌', group: 'config' },
]

export function Sidebar(props: {
  section: SectionId
  onSection: (s: SectionId) => void
  projects: Project[]
  currentProjectId?: string
  onSelectProject: (id: string) => void
  onNewProject: () => void
  onDeleteProject?: (id: string) => void
  apiOk: boolean | null
  onConfigApi: () => void
  progress?: Partial<Record<ProgressKey, boolean>>
}) {
  const prog = props.progress || {}
  return (
    <aside className="w-72 shrink-0 border-r border-slate-200 bg-white/80 backdrop-blur p-4 sticky top-0 h-screen overflow-y-auto scroll-thin">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-brand-600 text-white flex items-center justify-center font-bold">V</div>
        <div>
          <div className="font-bold leading-tight">Vibe Marketing</div>
          <div className="text-[11px] text-slate-500 leading-tight">App de IA para marketing — demo clase</div>
        </div>
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="label">Proyecto</span>
          <button className="text-xs text-brand-700 hover:underline" onClick={props.onNewProject}>+ Nuevo</button>
        </div>
        <select
          className="input"
          value={props.currentProjectId || ''}
          onChange={e => props.onSelectProject(e.target.value)}
        >
          <option value="" disabled>Selecciona un proyecto…</option>
          {props.projects.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        {props.currentProjectId && props.onDeleteProject && (
          <button
            className="text-[11px] text-rose-600 hover:underline mt-1"
            onClick={() => props.onDeleteProject!(props.currentProjectId!)}
          >Eliminar este proyecto</button>
        )}
      </div>

      <nav className="space-y-0.5 text-sm">
        {SECTIONS.map(s => {
          const done = s.progressKey ? !!prog[s.progressKey] : false
          return (
            <button
              key={s.id}
              onClick={() => props.onSection(s.id)}
              className={`w-full text-left px-2.5 py-1.5 rounded-md flex items-center gap-2 ${
                props.section === s.id ? 'bg-brand-50 text-brand-800 font-semibold' : 'hover:bg-slate-100 text-slate-700'
              }`}
            >
              <span>{s.emoji}</span>
              <span className="flex-1">{s.label}</span>
              {done && <span className="text-emerald-600 text-xs" title="Hecho">●</span>}
            </button>
          )
        })}
      </nav>

      <div className="mt-6 pt-4 border-t border-slate-200 text-xs text-slate-600">
        <div className="flex items-center gap-2 mb-2">
          <span className={`inline-block w-2 h-2 rounded-full ${props.apiOk ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
          <span>{props.apiOk ? 'Backend conectado' : 'Backend no responde'}</span>
        </div>
        <button className="text-brand-700 hover:underline" onClick={props.onConfigApi}>Configurar URL backend</button>
      </div>
    </aside>
  )
}
