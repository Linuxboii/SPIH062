import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import MoleculeThumb from '../components/MoleculeThumb'
import { listCompounds, getTargets } from '../lib/api'
import '../styles/compounds.css'

const PAGE = 24
const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '—')

const PHASES = [
  { key: 'approved',    label: 'Approved' },
  { key: 'trials',      label: 'In trials' },
  { key: 'preclinical', label: 'Preclinical' },
  { key: 'all',         label: 'All' },
]

const SORTS = [
  { key: 'evidence', label: 'Most measured activity' },
  { key: 'potency',  label: 'Highest potency' },
  { key: 'weight',   label: 'Lowest molecular weight' },
  { key: 'name',     label: 'Name (A–Z)' },
]

function phaseChip(c) {
  if (c.max_phase >= 4) {
    return (
      <span className="chip chip-sage">
        Approved{c.first_approval ? ` ${c.first_approval}` : ''}
      </span>
    )
  }
  if (c.max_phase > 0) return <span className="chip chip-quiet">Phase {c.max_phase}</span>
  return <span className="chip chip-quiet">Preclinical</span>
}

function Skeletons() {
  return (
    <div className="cgrid" aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => (
        <div className="ccard card is-skeleton" key={i}>
          <div className="sk sk-thumb" />
          <div className="sk sk-line" />
          <div className="sk sk-line sk-short" />
        </div>
      ))}
    </div>
  )
}

export default function Compounds() {
  const [params, setParams] = useSearchParams()

  const q       = params.get('q') ?? ''
  const phase   = params.get('phase') ?? 'approved'
  const target  = params.get('target') ?? ''
  const sort    = params.get('sort') ?? 'evidence'
  const offset  = Number(params.get('offset') ?? 0)

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [targets, setTargets] = useState([])
  /* the input is uncontrolled by the URL while you type — the URL catches up
     after the debounce, so a slow request never yanks characters back */
  const [draft, setDraft] = useState(q)
  const firstRun = useRef(true)

  useEffect(() => { getTargets().then((r) => setTargets(r.items ?? [])) }, [])

  // keep the box in step when the URL changes from somewhere else (back button)
  useEffect(() => { setDraft(q) }, [q])

  useEffect(() => {
    if (firstRun.current) { firstRun.current = false; return }
    const t = setTimeout(() => {
      if (draft !== q) patch({ q: draft, offset: 0 })
    }, 260)
    return () => clearTimeout(t)
  }, [draft])            // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let live = true
    setLoading(true)
    listCompounds({ q, phase, target, sort, limit: PAGE, offset }).then((d) => {
      if (live) { setData(d); setLoading(false) }
    })
    return () => { live = false }
  }, [q, phase, target, sort, offset])

  function patch(next) {
    const merged = { q, phase, target, sort, offset: 0, ...next }
    const clean = Object.fromEntries(
      Object.entries(merged).filter(([k, v]) =>
        v !== '' && v != null && !(k === 'offset' && !v) &&
        !(k === 'phase' && v === 'approved') && !(k === 'sort' && v === 'evidence'))
    )
    setParams(clean, { replace: true })
  }

  const items  = data?.items ?? []
  const total  = data?.total ?? 0
  const facets = data?.facets ?? {}
  const from   = total ? offset + 1 : 0
  const to     = Math.min(offset + PAGE, total)
  const filtered = Boolean(q || target || phase !== 'approved')

  const facetFor = useMemo(
    () => (k) => (k === 'all' ? facets.all : facets[k]),
    [facets]
  )

  return (
    <div className="compounds">
      {data?.demo && (
        <div className="demo-banner">
          <div className="shell demo-banner-inner">
            <span className="dot dot-ochre" />
            <p><strong>Backend not connected.</strong> The compound index needs the API.</p>
          </div>
        </div>
      )}

      <div className="shell">
        <header className="cx-head">
          <div>
            <p className="eyebrow">Compound explorer</p>
            <h1 className="display cx-h1">Every molecule in the corpus.</h1>
            <p className="prose cx-dek">
              {fmt(facets.all ?? 12111)} compounds drawn from ChEMBL and PubChem, each one
              linked to the measured activity, trials and literature behind it. Structures
              are drawn from the stored SMILES, not from stored images.
            </p>
          </div>
        </header>

        {/* ── controls ─────────────────────────────────────── */}
        <div className="cx-controls">
          <div className="cx-search">
            <svg className="cx-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
            </svg>
            <label className="sr-only" htmlFor="cx-q">Search compounds</label>
            <input
              id="cx-q"
              type="search"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search a name, brand name or ChEMBL ID…"
              autoComplete="off"
            />
            {draft && (
              <button className="cx-clear" onClick={() => setDraft('')} aria-label="Clear search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                  strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
              </button>
            )}
          </div>

          <div className="cx-selects">
            <label className="cx-field">
              <span className="label">Target</span>
              <select value={target} onChange={(e) => patch({ target: e.target.value })}>
                <option value="">Any target</option>
                {targets.map((t) => (
                  <option key={t.gene_symbol} value={t.gene_symbol}>
                    {t.gene_symbol} ({fmt(t.compound_count)})
                  </option>
                ))}
              </select>
            </label>

            <label className="cx-field">
              <span className="label">Sort</span>
              <select value={sort} onChange={(e) => patch({ sort: e.target.value })}>
                {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        <div className="cx-phases" role="group" aria-label="Filter by development stage">
          {PHASES.map((p) => {
            const n = facetFor(p.key)
            return (
              <button
                key={p.key}
                className={`cx-phase${phase === p.key ? ' is-on' : ''}`}
                aria-pressed={phase === p.key}
                onClick={() => patch({ phase: p.key })}
              >
                {p.label}
                {n != null && <span className="cx-phase-n mono">{fmt(n)}</span>}
              </button>
            )
          })}
        </div>

        {/* ── results ──────────────────────────────────────── */}
        <div className="cx-meta" aria-live="polite">
          {loading ? (
            <span className="mono">Searching…</span>
          ) : total ? (
            <span className="mono">
              {fmt(from)}–{fmt(to)} of {fmt(total)}
              {target && <> · measured against <strong>{target}</strong></>}
              {q && <> · matching “{q}”</>}
            </span>
          ) : null}
          {filtered && (
            <button className="cx-reset" onClick={() => setParams({}, { replace: true })}>
              Reset filters
            </button>
          )}
        </div>

        {loading && !data ? (
          <Skeletons />
        ) : total === 0 ? (
          <div className="cx-empty">
            <h2 className="h3 display">Nothing matches that.</h2>
            <p>
              {q
                ? <>No compound named, branded or identified as “{q}”{target && <> with measured activity against {target}</>} in this corpus.</>
                : <>No compound in this corpus matches those filters.</>}
            </p>
            <button className="btn btn-quiet" onClick={() => setParams({}, { replace: true })}>
              Clear filters
            </button>
          </div>
        ) : (
          <div className={`cgrid${loading ? ' is-stale' : ''}`}>
            {items.map((c) => (
              <Link className="ccard card card-hover" to={`/compound/${c.chembl_id}`} key={c.chembl_id}>
                <MoleculeThumb smiles={c.smiles} />

                <div className="ccard-body">
                  <div className="ccard-top">
                    <h2 className="ccard-name">{c.pref_name || c.chembl_id}</h2>
                    {phaseChip(c)}
                  </div>
                  <p className="ccard-id mono">{c.chembl_id}</p>

                  <dl className="ccard-facts">
                    <div>
                      <dt className="label">Weight</dt>
                      <dd className="mono">{c.mol_weight != null ? c.mol_weight.toFixed(1) : '—'}</dd>
                    </div>
                    <div>
                      <dt className="label">Ro5</dt>
                      <dd className={`mono${c.ro5_violations === 0 ? ' is-pass' : ''}`}>
                        {c.ro5_violations != null ? `${c.ro5_violations} viol.` : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="label">Best pChEMBL</dt>
                      <dd className="mono">{c.best_pchembl != null ? c.best_pchembl.toFixed(2) : '—'}</dd>
                    </div>
                  </dl>

                  <p className="ccard-acts">
                    <span className="dot dot-sage" />
                    {fmt(c.activity_count)} measured {c.activity_count === 1 ? 'activity' : 'activities'}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}

        {total > PAGE && (
          <nav className="cx-pager" aria-label="Pagination">
            <button
              className="btn btn-quiet"
              disabled={offset === 0}
              onClick={() => patch({ offset: Math.max(0, offset - PAGE) })}
            >
              ← Previous
            </button>
            <span className="mono cx-pager-at">
              Page {Math.floor(offset / PAGE) + 1} of {Math.ceil(total / PAGE)}
            </span>
            <button
              className="btn btn-quiet"
              disabled={to >= total}
              onClick={() => patch({ offset: offset + PAGE })}
            >
              Next →
            </button>
          </nav>
        )}
      </div>
    </div>
  )
}
