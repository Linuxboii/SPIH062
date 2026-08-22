import { useEffect, useRef, useState } from 'react'
import { ask, getStats } from '../lib/api'
import SourceDrawer from '../components/SourceDrawer'
import '../styles/chat.css'

const EXAMPLES = [
  'What resistance mechanisms are reported for osimertinib in EGFR-mutant NSCLC?',
  'Which compounds in the corpus inhibit KRAS G12C, and how potent are they?',
  'Summarise recent findings on PARP1 inhibitor resistance in ovarian cancer.',
  'What is Tagrisso?',
]

function ConfidenceBadge({ confidence, abstained }) {
  if (abstained) return <span className="chip chip-alert">Abstained</span>
  const band = confidence?.band ?? 'none'
  const pct = confidence?.score != null ? Math.round(confidence.score * 100) : null
  const map = {
    high: ['chip-sage', 'High confidence'],
    low: ['chip-ochre', 'Low confidence'],
    none: ['chip-quiet', 'Unscored'],
  }
  const [cls, text] = map[band] ?? map.none
  return (
    <span className={`chip ${cls}`}>
      {text}
      {pct != null && <span className="mono conf-pct">{pct}</span>}
    </span>
  )
}

function Claim({ claim, onCite }) {
  const unsourced = claim.unsourced || !claim.sources?.length
  return (
    <div className={`ans-claim${unsourced ? ' is-inferred' : ''}`}>
      {unsourced && (
        <span className="ans-claim-tag">
          <span className="dot dot-ochre" />
          AI inference — not from retrieved data
        </span>
      )}
      <p>
        {claim.text}
        {!unsourced &&
          claim.sources.map((s) => (
            <button
              key={s.id}
              className="cite cite-btn"
              onClick={() => onCite(s.id)}
              title={s.title || s.id}
            >
              {s.id}
            </button>
          ))}
      </p>
    </div>
  )
}

function AbstentionCard({ answer }) {
  return (
    <div className="abstain">
      <div className="abstain-head">
        <span className="dot dot-alert" />
        <h3>Not enough grounded evidence to answer</h3>
      </div>
      <p className="abstain-lede">
        No answer was generated. The assistant does not produce prose when retrieval
        cannot support it.
      </p>
      {answer.gaps?.length > 0 && (
        <>
          <span className="label">What is missing</span>
          <ul className="abstain-gaps">
            {answer.gaps.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </>
      )}
    </div>
  )
}

function StructuredTable({ structured }) {
  const acts = structured?.activities ?? []
  if (!acts.length) return null
  return (
    <div className="struct">
      <div className="struct-head">
        <span className="label">From structured records</span>
        <span className="chip chip-sage">SQL · not paraphrased</span>
      </div>
      <div className="struct-scroll">
        <table>
          <thead>
            <tr>
              <th>Compound</th><th>Target</th><th>Type</th>
              <th className="num">Value</th><th className="num">pChEMBL</th>
            </tr>
          </thead>
          <tbody>
            {acts.map((a, i) => (
              <tr key={i}>
                <td>{a.compound_name ?? a.compound_id}</td>
                <td>{a.target_name ?? a.target_id}</td>
                <td className="mono">{a.standard_type}</td>
                <td className="num mono">
                  {a.standard_value} {a.standard_units}
                </td>
                <td className="num mono">{a.pchembl_value ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EvidencePanel({ answer, onOpen, activeId }) {
  const sources = answer?.sources ?? []
  return (
    <aside className="evidence">
      <div className="evidence-head">
        <span className="label">Evidence</span>
        {sources.length > 0 && (
          <span className="mono evidence-count">{sources.length}</span>
        )}
      </div>

      {sources.length === 0 ? (
        <p className="evidence-empty">
          Retrieved sources appear here. Every claim in an answer links to one.
        </p>
      ) : (
        <div className="evidence-list">
          {sources.map((s) => (
            <button
              key={s.id}
              className={`src-card${activeId === s.id ? ' is-active' : ''}`}
              onClick={() => onOpen(s)}
            >
              <div className="src-top">
                <span className="mono src-id">{s.id}</span>
                {s.retrieval_score != null && (
                  <span className="mono src-score">{s.retrieval_score.toFixed(2)}</span>
                )}
              </div>
              <div className="src-title">{s.title}</div>
              <div className="src-meta mono">
                {[s.journal, s.year].filter(Boolean).join(' · ') || s.type}
              </div>
              {s.snippet && <p className="src-snip">{s.snippet}</p>}
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}

export default function Chat() {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  const [drawer, setDrawer] = useState(null)
  const [stats, setStats] = useState(null)
  const endRef = useRef(null)

  useEffect(() => { getStats().then(setStats) }, [])
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns, busy])

  const latest = turns.length ? turns[turns.length - 1].answer : null
  const isDemo = latest?.demo || stats?.demo

  async function submit(e, preset) {
    e?.preventDefault()
    const q = (preset ?? input).trim()
    if (!q || busy) return
    setInput('')
    setBusy(true)
    setTurns((t) => [...t, { q, answer: null }])
    const answer = await ask(q)
    setTurns((t) => {
      const next = [...t]
      next[next.length - 1] = { q, answer }
      return next
    })
    setBusy(false)
  }

  function openSourceById(id) {
    const s = latest?.sources?.find((x) => x.id === id)
    if (s) setDrawer(s)
  }

  return (
    <div className="chat">
      {isDemo && (
        <div className="demo-banner">
          <div className="shell demo-banner-inner">
            <span className="dot dot-ochre" />
            <p>
              <strong>Backend not connected.</strong> The corpus has not been ingested, so
              nothing is being retrieved. The interface is shown with illustrative
              placeholders — no content here is real evidence.
            </p>
          </div>
        </div>
      )}

      <div className="chat-grid shell">
        <section className="convo">
          {turns.length === 0 && (
            <div className="opening">
              <p className="eyebrow">Assistant</p>
              <h1 className="display h2 opening-title">
                Ask about a compound, a target,<br />or a body of research.
              </h1>
              <p className="prose opening-dek">
                Answers are assembled from retrieved records. Each claim shows where it
                came from, and the assistant declines when the evidence is thin.
              </p>

              <div className="examples">
                <span className="label">Try</span>
                {EXAMPLES.map((ex) => (
                  <button key={ex} className="example" onClick={(e) => submit(e, ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) => (
            <article className="turn" key={i}>
              <div className="turn-q">
                <span className="label">Question</span>
                <p>{t.q}</p>
              </div>

              {t.answer === null ? (
                <div className="thinking">
                  <span className="pulse" /><span className="pulse" /><span className="pulse" />
                  <span className="thinking-text">Retrieving…</span>
                </div>
              ) : (
                <div className="turn-a">
                  <div className="turn-a-head">
                    <ConfidenceBadge
                      confidence={t.answer.confidence}
                      abstained={t.answer.abstained}
                    />
                    {t.answer.resolved_entities?.length > 0 && (
                      <div className="resolved">
                        <span className="label">Resolved</span>
                        {t.answer.resolved_entities.map((en) => (
                          <span className="chip chip-quiet" key={en.id}>
                            {en.text} → {en.id}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {t.answer.abstained ? (
                    <AbstentionCard answer={t.answer} />
                  ) : (
                    <>
                      {t.answer.claims.map((c, ci) => (
                        <Claim key={ci} claim={c} onCite={openSourceById} />
                      ))}
                      <StructuredTable structured={t.answer.structured} />
                    </>
                  )}
                </div>
              )}
            </article>
          ))}

          <div ref={endRef} />

          <form className="composer" onSubmit={submit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a compound, target, or mechanism…"
              aria-label="Your question"
              disabled={busy}
            />
            <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
              {busy ? 'Retrieving…' : 'Ask'}
            </button>
          </form>
          <p className="composer-note">
            Research use only. Answers are grounded in retrieved records and may be incomplete.
          </p>
        </section>

        <EvidencePanel
          answer={latest}
          onOpen={setDrawer}
          activeId={drawer?.id}
        />
      </div>

      <SourceDrawer source={drawer} onClose={() => setDrawer(null)} />
    </div>
  )
}
