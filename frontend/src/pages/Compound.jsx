import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getCompound } from '../lib/api'
import MoleculeCanvas from '../components/MoleculeCanvas'
import '../styles/compound.css'

/* Lipinski's Rule of Five, evaluated client-side from stored properties so the
   pass/fail reasoning is visible rather than asserted. */
function lipinski(c) {
  return [
    { rule: 'Molecular weight ≤ 500', value: c.mol_weight, ok: c.mol_weight != null && c.mol_weight <= 500, fmt: (v) => v?.toFixed(1) },
    { rule: 'XLogP ≤ 5',              value: c.xlogp,      ok: c.xlogp != null && c.xlogp <= 5,            fmt: (v) => v?.toFixed(1) },
    { rule: 'H-bond donors ≤ 5',      value: c.hbd,        ok: c.hbd != null && c.hbd <= 5,                fmt: (v) => v },
    { rule: 'H-bond acceptors ≤ 10',  value: c.hba,        ok: c.hba != null && c.hba <= 10,               fmt: (v) => v },
  ]
}

function Panel({ title, chip, children, note }) {
  return (
    <section className="panel card">
      <header className="panel-head">
        <h2 className="panel-title">{title}</h2>
        {chip}
      </header>
      {note && <p className="panel-note">{note}</p>}
      <div className="panel-body">{children}</div>
    </section>
  )
}

function Empty({ children }) {
  return <p className="panel-empty">{children}</p>
}

export default function Compound() {
  const { id } = useParams()
  const [c, setC] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let live = true
    setLoading(true)
    getCompound(id).then((d) => {
      if (live) { setC(d); setLoading(false) }
    })
    return () => { live = false }
  }, [id])

  if (loading) {
    return (
      <div className="shell cmp-loading">
        <div className="thinking">
          <span className="pulse" /><span className="pulse" /><span className="pulse" />
          <span className="thinking-text">Loading compound…</span>
        </div>
      </div>
    )
  }

  if (!c) return <div className="shell cmp-loading">Not found.</div>

  const rules = lipinski(c)
  const violations = rules.filter((r) => !r.ok).length

  return (
    <div className="compound">
      {c.demo && (
        <div className="demo-banner">
          <div className="shell demo-banner-inner">
            <span className="dot dot-ochre" />
            <p>
              <strong>Backend not connected.</strong>{' '}
              {c.demo_notice ?? 'Showing illustrative values.'}
            </p>
          </div>
        </div>
      )}

      <div className="shell">
        {/* ── header ─────────────────────────────────────── */}
        <header className="cmp-header">
          <div>
            <p className="eyebrow">Compound</p>
            <h1 className="display cmp-h1">{c.pref_name ?? c.chembl_id}</h1>
            <p className="cmp-idline mono">
              {c.chembl_id}
              {c.pubchem_cid && <> · CID {c.pubchem_cid}</>}
              {c.inchikey && <> · {c.inchikey}</>}
            </p>
            {c.synonyms?.length > 0 && (
              <div className="cmp-syns">
                <span className="label">Also known as</span>
                {c.synonyms.map((s) => (
                  <span className="chip chip-quiet" key={s}>{s}</span>
                ))}
              </div>
            )}
          </div>
          <div className="cmp-badges">
            {c.max_phase >= 4 && <span className="chip chip-sage">Approved</span>}
            {c.max_phase > 0 && c.max_phase < 4 && (
              <span className="chip chip-quiet">Phase {c.max_phase}</span>
            )}
            {c.first_approval && (
              <span className="chip chip-quiet">{c.first_approval}</span>
            )}
          </div>
        </header>

        <div className="cmp-layout">
          {/* ── left column ──────────────────────────────── */}
          <div className="cmp-col">
            <Panel
              title="Structure"
              chip={<span className="chip chip-sage">PubChem</span>}
            >
              <MoleculeCanvas smiles={c.smiles} />
              {c.smiles && (
                <div className="smiles">
                  <span className="label">SMILES</span>
                  <code>{c.smiles}</code>
                </div>
              )}
            </Panel>

            <Panel
              title="Physicochemical properties"
              chip={<span className="chip chip-sage">Database values</span>}
              note="Read directly from the source database. These figures are never passed through a language model."
            >
              <dl className="props">
                <div><dt className="label">Formula</dt><dd className="mono">{c.mol_formula ?? '—'}</dd></div>
                <div><dt className="label">Mol. weight</dt><dd className="mono">{c.mol_weight?.toFixed(2) ?? '—'}</dd></div>
                <div><dt className="label">XLogP</dt><dd className="mono">{c.xlogp ?? '—'}</dd></div>
                <div><dt className="label">TPSA</dt><dd className="mono">{c.tpsa ?? '—'}</dd></div>
                <div><dt className="label">H-bond donors</dt><dd className="mono">{c.hbd ?? '—'}</dd></div>
                <div><dt className="label">H-bond acceptors</dt><dd className="mono">{c.hba ?? '—'}</dd></div>
              </dl>
            </Panel>

            <Panel
              title="Lipinski Rule of Five"
              chip={
                <span className={`chip ${violations === 0 ? 'chip-sage' : 'chip-ochre'}`}>
                  {violations} violation{violations === 1 ? '' : 's'}
                </span>
              }
            >
              <ul className="ro5" role="list">
                {rules.map((r) => (
                  <li key={r.rule} className={r.ok ? 'is-pass' : 'is-fail'}>
                    <span className="ro5-mark" aria-hidden="true">
                      {r.ok ? '✓' : '✕'}
                    </span>
                    <span className="ro5-rule">{r.rule}</span>
                    <span className="mono ro5-val">
                      {r.value != null ? r.fmt(r.value) : '—'}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          {/* ── right column ─────────────────────────────── */}
          <div className="cmp-col">
            <Panel
              title="Measured targets"
              chip={<span className="chip chip-sage">Experimental</span>}
              note="Bioactivities measured in assays and reported in ChEMBL."
            >
              {c.activities?.length ? (
                <div className="tscroll">
                  <table className="dtable">
                    <thead>
                      <tr>
                        <th>Target</th><th>Type</th>
                        <th className="num">Value</th><th className="num">pChEMBL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.activities.map((a, i) => (
                        <tr key={i}>
                          <td>{a.gene_symbol ?? a.target_name ?? a.target_id}</td>
                          <td className="mono">{a.standard_type}</td>
                          <td className="num mono">
                            {a.standard_value} {a.standard_units}
                          </td>
                          <td className="num mono">{a.pchembl_value?.toFixed(2) ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>No measured activities in the corpus for this compound.</Empty>
              )}
            </Panel>

            <Panel
              title="Predicted targets"
              chip={<span className="chip chip-ochre">Predicted — not experimental</span>}
              note="Model output, not measurement. Probabilities are calibrated on a held-out scaffold split; per-target performance is shown alongside each prediction."
            >
              {c.predictions?.length ? (
                <ul className="preds" role="list">
                  {c.predictions.map((p, i) => (
                    <li key={i} className="pred">
                      <div className="pred-top">
                        <span className="pred-target">{p.gene_symbol ?? p.target_id}</span>
                        <span className="mono pred-p">
                          {(p.probability * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="pred-track">
                        <div className="pred-fill" style={{ width: `${p.probability * 100}%` }} />
                      </div>
                      <div className="pred-meta">
                        {p.is_known && <span className="chip chip-quiet">Reproduces known activity</span>}
                        {p.roc_auc != null && (
                          <span className="mono pred-auc">held-out AUC {p.roc_auc.toFixed(2)}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No predictions available — the model has not been trained yet.</Empty>
              )}
            </Panel>

            <Panel title="Clinical trials" chip={<span className="chip chip-sage">ClinicalTrials.gov</span>}>
              {c.trials?.length ? (
                <ul className="trials" role="list">
                  {c.trials.map((t) => (
                    <li key={t.nct_id} className="trial">
                      <div className="trial-top">
                        <a href={t.url} target="_blank" rel="noreferrer" className="mono trial-id">
                          {t.nct_id}
                        </a>
                        <span className="chip chip-quiet">{t.phase ?? 'N/A'}</span>
                      </div>
                      <p className="trial-title">{t.title}</p>
                      <p className="trial-meta mono">
                        {[t.status, t.conditions?.[0]].filter(Boolean).join(' · ')}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No trials linked to this compound in the corpus.</Empty>
              )}
            </Panel>

            <Panel title="Recent literature" chip={<span className="chip chip-sage">PubMed</span>}>
              {c.papers?.length ? (
                <ul className="papers" role="list">
                  {c.papers.map((p) => (
                    <li key={p.pmid} className="paper">
                      <a href={p.url} target="_blank" rel="noreferrer" className="paper-title">
                        {p.title}
                      </a>
                      <p className="paper-meta mono">
                        {[p.journal, p.year].filter(Boolean).join(' · ')} · PMID {p.pmid}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No abstracts retrieved for this compound yet.</Empty>
              )}
            </Panel>
          </div>
        </div>
      </div>
    </div>
  )
}
