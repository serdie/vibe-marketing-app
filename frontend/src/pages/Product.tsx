import { useState } from 'react'
import { api, Project } from '../api'
import ProgressBar, { ESTIMATED } from '../components/ProgressBar'

type ProductRow = { name: string; description: string; price?: string; category?: string }

export function ProductPage({ project, onUpdate, onNext }: { project: Project; onUpdate: () => void; onNext?: () => void }) {
  const initial: ProductRow[] = (project.products as any) || []
  const [rows, setRows] = useState<ProductRow[]>(initial.length ? initial : [{ name: '', description: '' }])
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [bkBusy, setBkBusy] = useState(false)

  function update(i: number, field: keyof ProductRow, v: string) {
    const next = [...rows]; (next[i] as any)[field] = v; setRows(next)
  }
  function add() { setRows([...rows, { name: '', description: '' }]) }
  function del(i: number) { setRows(rows.filter((_, k) => k !== i)) }

  async function generate() {
    setBusy(true)
    try {
      await api.post(`/api/projects/${project.id}/product`, {
        products: rows.filter(r => r.name.trim()),
        notes: notes || undefined,
      })
      onUpdate()
    } finally { setBusy(false) }
  }

  async function autoBrandKit() {
    setBkBusy(true)
    try {
      await api.post(`/api/projects/${project.id}/brand-kit/auto`)
      onUpdate()
    } finally { setBkBusy(false) }
  }

  const icp = project.icp as any
  const personas = (project.personas as any[]) || []
  const brand = (project.brand_kit as any) || {}

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">3. Productos e ICP</h1>
        <p className="text-slate-600 text-sm">Define qué vendes y la app sugiere el cliente ideal y 3 buyer personas.</p>
      </header>

      <section className="card">
        <h2 className="font-semibold mb-2">Productos / servicios</h2>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="grid md:grid-cols-12 gap-2">
              <input className="input md:col-span-3" placeholder="Nombre" value={r.name} onChange={e => update(i, 'name', e.target.value)} />
              <input className="input md:col-span-5" placeholder="Descripción breve" value={r.description} onChange={e => update(i, 'description', e.target.value)} />
              <input className="input md:col-span-2" placeholder="Precio" value={r.price || ''} onChange={e => update(i, 'price', e.target.value)} />
              <input className="input md:col-span-1" placeholder="Cat." value={r.category || ''} onChange={e => update(i, 'category', e.target.value)} />
              <button className="btn-ghost md:col-span-1" onClick={() => del(i)} title="Eliminar">✕</button>
            </div>
          ))}
        </div>
        <div className="mt-2"><button className="btn-secondary" onClick={add}>+ Añadir producto</button></div>
        <label className="label mt-4 block">Notas / restricciones</label>
        <textarea className="input min-h-[80px]" value={notes} onChange={e => setNotes(e.target.value)} />
        <div className="mt-3 flex gap-2">
          <button className="btn-primary" onClick={generate} disabled={busy}>{busy ? 'Generando…' : '🎯 Generar ICP y buyer personas'}</button>
          <button className="btn-secondary" onClick={autoBrandKit} disabled={bkBusy}>{bkBusy ? 'Sugiriendo…' : '🎨 Sugerir brand kit'}</button>
        </div>
        <ProgressBar active={busy || bkBusy} estimatedSeconds={ESTIMATED.icp.seconds} steps={ESTIMATED.icp.steps} title={bkBusy ? 'Sugiriendo brand kit' : 'Generando ICP + personas'} />
      </section>

      {icp && (
        <section className="card">
          <h2 className="font-semibold mb-2">Cliente ideal (ICP)</h2>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            <div><span className="label">Sector principal</span><div>{icp.sector_principal}</div></div>
            <div><span className="label">Sectores secundarios</span><div>{(icp.sectores_secundarios || []).join(', ')}</div></div>
            <div><span className="label">Tamaño empresa</span><div>{icp.tamano_empresa}</div></div>
            <div><span className="label">Geo</span><div>{typeof icp.geo === 'string' ? icp.geo : [icp.geo?.ciudad, icp.geo?.provincia, icp.geo?.pais].filter(Boolean).join(', ')}</div></div>
            <div><span className="label">Presupuesto compra</span><div>{icp.presupuesto_compra}</div></div>
            <div><span className="label">Momento de compra</span><div>{icp.momento_compra}</div></div>
            <div className="md:col-span-2"><span className="label">Criterios de decisión</span>
              <ul className="list-disc list-inside">{(icp.criterios_decision || []).map((c: string, i: number) => <li key={i}>{c}</li>)}</ul>
            </div>
            <div className="md:col-span-2"><span className="label">Canales donde buscan</span>
              <div className="flex flex-wrap gap-1 mt-1">{(icp.canales_donde_buscan || []).map((c: string, i: number) => <span key={i} className="chip">{c}</span>)}</div>
            </div>
          </div>
        </section>
      )}

      {personas.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-3">Buyer personas</h2>
          <div className="grid md:grid-cols-3 gap-3">
            {personas.map((p, i) => (
              <div key={i} className="border border-slate-200 rounded-lg p-3 text-sm">
                <div className="font-semibold">{p.nombre} <span className="text-slate-500 text-xs">· {p.rol}</span></div>
                {p.edad && <div className="text-xs text-slate-500">{p.edad} años</div>}
                <p className="mt-1 text-slate-700">{p.perfil_personal}</p>
                {Array.isArray(p.jobs_to_be_done) && p.jobs_to_be_done.length > 0 && (
                  <div className="mt-2"><span className="label">Jobs to be done</span><ul className="list-disc list-inside">{p.jobs_to_be_done.map((j: string, k: number) => <li key={k}>{j}</li>)}</ul></div>
                )}
                {Array.isArray(p.dolores) && p.dolores.length > 0 && (
                  <div className="mt-2"><span className="label">Dolores</span><div className="text-slate-700">{p.dolores.join(' · ')}</div></div>
                )}
                {Array.isArray(p.objeciones) && p.objeciones.length > 0 && (
                  <div className="mt-1"><span className="label">Objeciones</span><div className="text-slate-700">{p.objeciones.join(' · ')}</div></div>
                )}
                {Array.isArray(p.canales_preferidos) && p.canales_preferidos.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">{p.canales_preferidos.map((c: string, k: number) => <span key={k} className="chip">{c}</span>)}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {Object.keys(brand).length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-2">Brand kit</h2>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            <div>
              <span className="label">Colores</span>
              <div className="flex gap-1 mt-1">{(brand.colores || []).map((c: string, i: number) => (
                <div key={i} title={c} className="w-8 h-8 rounded border" style={{ background: c }}></div>
              ))}</div>
            </div>
            <div><span className="label">Fuentes</span><div>{(brand.fuentes || []).join(', ')}</div></div>
            <div><span className="label">Tono</span><div>{brand.tono}</div></div>
            <div><span className="label">Claims</span><ul className="list-disc list-inside">{(brand.claims || []).map((c: string, i: number) => <li key={i}>{c}</li>)}</ul></div>
            {brand.palabras_prohibidas?.length > 0 && (
              <div className="md:col-span-2"><span className="label">Palabras prohibidas</span><div>{brand.palabras_prohibidas.join(', ')}</div></div>
            )}
          </div>
        </section>
      )}

      {(icp?.sector_principal || personas.length > 0) && onNext && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={onNext}>▶ Siguiente paso: buscar leads</button>
        </div>
      )}
    </div>
  )
}
