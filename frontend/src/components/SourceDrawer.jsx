import { useEffect } from 'react'
import '../styles/drawer.css'

export default function SourceDrawer({ source, onClose }) {
  useEffect(() => {
    if (!source) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [source, onClose])

  return (
    <>
      <div
        className={`drawer-scrim${source ? ' is-open' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`drawer${source ? ' is-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Source detail"
      >
        {source && (
          <>
            <header className="drawer-head">
              <div>
                <span className="mono drawer-id">{source.id}</span>
                <span className="chip chip-quiet drawer-kind">{source.type}</span>
              </div>
              <button className="drawer-close" onClick={onClose} aria-label="Close">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4"
                    strokeLinecap="round" />
                </svg>
              </button>
            </header>

            <div className="drawer-body">
              <h2 className="display drawer-title">{source.title}</h2>

              {(source.journal || source.year) && (
                <p className="drawer-meta mono">
                  {[source.journal, source.year].filter(Boolean).join(' · ')}
                </p>
              )}

              {source.retrieval_score != null && (
                <div className="drawer-score">
                  <div className="drawer-score-row">
                    <span className="label">Retrieval score</span>
                    <span className="mono">{source.retrieval_score.toFixed(3)}</span>
                  </div>
                  <div className="score-track">
                    <div
                      className="score-fill"
                      style={{ width: `${Math.min(100, source.retrieval_score * 100)}%` }}
                    />
                  </div>
                  <p className="drawer-why">
                    Ranked by combined lexical and semantic match against your question,
                    fused across both retrieval lanes.
                  </p>
                </div>
              )}

              {source.snippet && (
                <div className="drawer-passage">
                  <span className="label">Retrieved passage</span>
                  <blockquote>{source.snippet}</blockquote>
                </div>
              )}

              {source.url && (
                <a
                  className="btn btn-quiet drawer-link"
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open original record
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M6 3h7v7M13 3L4 12" stroke="currentColor" strokeWidth="1.4"
                      strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </a>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  )
}
