/**
 * API client.
 *
 * The backend is the source of truth. Until it is running, calls fall back to
 * a small bundled fixture so the interface can be developed and demonstrated
 * standalone. Every fallback response carries `demo: true`, and the UI shows a
 * banner when it is served — a grounding tool must never quietly present
 * placeholder data as real.
 */

import { DEMO_ANSWER, DEMO_COMPOUND, DEMO_STATS } from './demoData'

const TIMEOUT_MS = 20000

async function req(path, init = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl.signal,
      ...init,
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

export async function ask(query) {
  try {
    return await req('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ query }),
    })
  } catch {
    return { ...DEMO_ANSWER(query), demo: true }
  }
}

export async function getCompound(idOrName) {
  try {
    return await req(`/api/compound/${encodeURIComponent(idOrName)}`)
  } catch {
    return { ...DEMO_COMPOUND, demo: true }
  }
}

export async function listCompounds(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v != null)
  )
  try {
    return await req(`/api/compounds?${qs}`)
  } catch {
    return { items: [], total: 0, facets: {}, demo: true }
  }
}

export async function getTargets() {
  try {
    return await req('/api/targets')
  } catch {
    return { items: [], demo: true }
  }
}

export async function getStats() {
  try {
    return await req('/api/stats')
  } catch {
    return { ...DEMO_STATS, demo: true }
  }
}

export async function suggest(q) {
  if (!q || q.length < 2) return { results: [] }
  try {
    return await req(`/api/search/suggest?q=${encodeURIComponent(q)}`)
  } catch {
    const pool = [
      { label: 'Osimertinib', id: 'CHEMBL3353410', kind: 'compound', note: 'Tagrisso · AZD9291' },
      { label: 'Erlotinib', id: 'CHEMBL553', kind: 'compound', note: 'Tarceva' },
      { label: 'Imatinib', id: 'CHEMBL941', kind: 'compound', note: 'Gleevec' },
      { label: 'Sotorasib', id: 'CHEMBL4535757', kind: 'compound', note: 'Lumakras' },
      { label: 'EGFR', id: 'CHEMBL203', kind: 'target', note: 'ERBB1 · HER1' },
      { label: 'KRAS', id: 'CHEMBL2189121', kind: 'target', note: 'G12C' },
    ]
    const n = q.toLowerCase()
    return {
      results: pool.filter(
        (p) => p.label.toLowerCase().includes(n) || p.note.toLowerCase().includes(n)
      ),
      demo: true,
    }
  }
}

export async function health() {
  try {
    const r = await req('/api/health')
    return { ok: true, ...r }
  } catch {
    return { ok: false }
  }
}
