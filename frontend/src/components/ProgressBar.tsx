import { useEffect, useState } from 'react'

export type Step = { label: string; pctAt: number }

type Props = {
  /** Si null/undefined la barra no se muestra. Si true, la barra está activa. */
  active: boolean
  /** Tiempo estimado total en segundos */
  estimatedSeconds: number
  /** Pasos con su % de progreso (pctAt de 0 a 95). Último paso queda en 95% hasta que termina. */
  steps: Step[]
  /** Título opcional a mostrar encima */
  title?: string
}

/**
 * Barra de progreso "inteligente" sin streaming real:
 * - Arranca al activarse, simula avance por pasos calibrados con estimatedSeconds.
 * - Cuando active pasa a false, completa a 100% rápidamente.
 * - Nunca llega al 100% por sí sola (máx 95%) para no dar falsos positivos.
 */
export default function ProgressBar({ active, estimatedSeconds, steps, title }: Props) {
  const [pct, setPct] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [completing, setCompleting] = useState(false)

  useEffect(() => {
    if (active) {
      setPct(2)
      setElapsed(0)
      setCompleting(false)
      const started = Date.now()
      const interval = setInterval(() => {
        const secs = (Date.now() - started) / 1000
        setElapsed(secs)
        // progresión asintótica hacia 95% calibrada con estimatedSeconds
        const raw = (secs / estimatedSeconds) * 95
        const asymp = 95 * (1 - Math.exp(-secs / estimatedSeconds))
        setPct(Math.min(95, Math.max(raw * 0.3 + asymp * 0.7, 2)))
      }, 200)
      return () => clearInterval(interval)
    } else {
      // cuando acaba, completamos rápido a 100%
      if (pct > 0) {
        setCompleting(true)
        const interval = setInterval(() => {
          setPct((p) => {
            if (p >= 100) {
              clearInterval(interval)
              return 100
            }
            return Math.min(100, p + 5)
          })
        }, 40)
        const reset = setTimeout(() => {
          setPct(0)
          setElapsed(0)
          setCompleting(false)
        }, 1500)
        return () => {
          clearInterval(interval)
          clearTimeout(reset)
        }
      }
    }
  }, [active, estimatedSeconds])

  if (pct <= 0 && !active) return null

  const currentStep = steps.find((s, i) => {
    const next = steps[i + 1]
    return pct >= s.pctAt && (!next || pct < next.pctAt)
  }) || steps[0]

  return (
    <div style={{
      padding: '12px 16px', background: '#0f172a', borderRadius: 8,
      border: '1px solid #1e293b', margin: '12px 0', color: '#e2e8f0',
    }}>
      {title && <div style={{ fontWeight: 600, marginBottom: 8 }}>{title}</div>}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
        <span>{completing ? '✓ Finalizando...' : (currentStep?.label || 'Procesando...')}</span>
        <span style={{ color: '#94a3b8' }}>
          {Math.round(pct)}% · {Math.round(elapsed)}s{active ? ` / ~${estimatedSeconds}s` : ''}
        </span>
      </div>
      <div style={{
        height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden', position: 'relative',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: completing
            ? 'linear-gradient(90deg,#22c55e,#4ade80)'
            : 'linear-gradient(90deg,#3b82f6,#8b5cf6)',
          transition: 'width 0.25s ease-out',
          boxShadow: completing ? '0 0 8px #22c55e' : '0 0 8px #3b82f6',
        }} />
      </div>
      {elapsed > estimatedSeconds * 1.5 && active && (
        <div style={{ fontSize: 12, color: '#fbbf24', marginTop: 6 }}>
          ⏳ Tarda más de lo habitual. La IA está pensando a fondo, aguanta… (puede llegar a {Math.round(estimatedSeconds * 3)}s).
        </div>
      )}
    </div>
  )
}

export const ESTIMATED = {
  research: { seconds: 50, steps: [
    { label: '🔍 Identificando quién es el propietario...', pctAt: 0 },
    { label: '📱 Buscando presencia digital y reseñas...', pctAt: 35 },
    { label: '📝 Sintetizando perfil estructurado...', pctAt: 70 },
  ]},
  gaps: { seconds: 70, steps: [
    { label: '🏢 Identificando 5 competidores reales...', pctAt: 0 },
    { label: '⚖️ Comparativa en 10 ejes vs competencia...', pctAt: 35 },
    { label: '📊 SWOT + plan de 8 acciones...', pctAt: 70 },
  ]},
  icp: { seconds: 30, steps: [
    { label: '🎯 Generando ICP + buyer personas...', pctAt: 0 },
    { label: '🧠 Afinando sector y jobs-to-be-done...', pctAt: 60 },
  ]},
  leads: { seconds: 45, steps: [
    { label: '🔎 Buscando negocios reales en la ubicación...', pctAt: 0 },
    { label: '📇 Extrayendo contactos (email, teléfono, web)...', pctAt: 50 },
    { label: '✨ Enriqueciendo con scraping de cada web...', pctAt: 80 },
  ]},
  campaign: { seconds: 90, steps: [
    { label: '💡 Generando ideas y estrategia...', pctAt: 0 },
    { label: '✏️ Eslóganes, copies, textos...', pctAt: 25 },
    { label: '🎨 Imágenes (logo/banner/posts)...', pctAt: 55 },
    { label: '📧 Newsletter HTML + posts RRSS...', pctAt: 80 },
  ]},
  prediction: { seconds: 25, steps: [
    { label: '📈 Benchmarks por canal + heurísticas...', pctAt: 0 },
    { label: '🤖 Refinamiento IA del forecast...', pctAt: 60 },
  ]},
  roi: { seconds: 20, steps: [
    { label: '💰 Calculando ROI y atribución multicanal...', pctAt: 0 },
  ]},
  email_batch: { seconds: 60, steps: [
    { label: '✉️ Personalizando emails por lead con IA...', pctAt: 0 },
    { label: '📤 Preparando tracking y enviando...', pctAt: 60 },
  ]},
}
