// API helpers
const ENV_BASE = (import.meta as any).env?.VITE_API_BASE as string | undefined
const LS_KEY = 'vibe.api_base'

export function getApiBase(): string {
  return localStorage.getItem(LS_KEY) || ENV_BASE || 'http://localhost:8000'
}

export function setApiBase(url: string) {
  localStorage.setItem(LS_KEY, url)
}

async function req<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(getApiBase() + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${txt || res.statusText}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return (await res.text()) as any
}

export const api = {
  get: <T = any>(p: string) => req<T>(p),
  post: <T = any>(p: string, body?: any) =>
    req<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T = any>(p: string, body?: any) =>
    req<T>(p, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  del: <T = any>(p: string) => req<T>(p, { method: 'DELETE' }),
}

export type Project = {
  id: string
  name: string
  owner_type: string
  website?: string
  full_name?: string
  cv_text?: string
  research?: any
  gaps?: any
  competitors?: any[]
  products?: any[]
  icp?: any
  personas?: any[]
  brand_kit?: any
}

export type Provider = {
  id: string
  name: string
  tasks: string[]
  models: Record<string, string>
  base_url?: string | null
  enabled: boolean
  has_key: boolean
}

export type ProviderCatalog = {
  id: string
  name: string
  env: string | null
  needs_base_url: boolean
  needs_from_email?: boolean
  smtp_hint?: string
  tasks: string[]
  default_models: Record<string, string>
  models: string[]
  docs: string
}
