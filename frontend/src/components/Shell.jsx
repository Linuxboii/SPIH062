import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import '../styles/shell.css'

/* Non-dismissible. Required by the product's positioning, not a cookie banner. */
export function DisclaimerBar() {
  return (
    <div className="disclaimer" role="note">
      <div className="shell disclaimer-inner">
        <span className="disclaimer-mark" aria-hidden="true" />
        <p>
          <strong>Research tool.</strong> Grounded in public biomedical data. Not medical
          advice — not for diagnosis or treatment.
        </p>
      </div>
    </div>
  )
}

function Wordmark() {
  return (
    <Link to="/" className="wordmark" aria-label="OncoLens home">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="7.1" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="12" cy="4.9" r="1.9" fill="currentColor" />
        <circle cx="18.2" cy="15.5" r="1.9" fill="currentColor" />
        <circle cx="5.8" cy="15.5" r="1.9" fill="currentColor" />
      </svg>
      <span>OncoLens</span>
    </Link>
  )
}

export function Nav() {
  const [lifted, setLifted] = useState(false)
  const { pathname } = useLocation()
  const onLanding = pathname === '/'

  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav className={`nav${lifted ? ' is-lifted' : ''}`}>
      <div className="shell nav-inner">
        <Wordmark />

        {onLanding ? (
          <div className="nav-links">
            <a href="#why">Why</a>
            <a href="#how">How it works</a>
            <a href="#data">Data</a>
            <a href="#responsible">Responsible AI</a>
          </div>
        ) : (
          <div className="nav-links">
            <NavLink to="/app">Assistant</NavLink>
            <NavLink to="/compound/CHEMBL3353410">Compounds</NavLink>
          </div>
        )}

        <div className="nav-actions">
          {onLanding ? (
            <Link className="btn btn-primary nav-cta" to="/app">Open assistant</Link>
          ) : (
            <Link className="btn btn-quiet nav-cta" to="/">Overview</Link>
          )}
        </div>
      </div>
    </nav>
  )
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="shell foot-inner">
        <div className="foot-brand">
          <Wordmark />
          <p className="foot-tag">
            A grounded biomedical research assistant for oncology drug discovery.
          </p>
        </div>

        <div className="foot-cols">
          <div>
            <span className="label">Data sources</span>
            <ul role="list">
              <li><a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noreferrer">PubMed</a></li>
              <li><a href="https://www.ebi.ac.uk/chembl/" target="_blank" rel="noreferrer">ChEMBL</a></li>
              <li><a href="https://pubchem.ncbi.nlm.nih.gov/" target="_blank" rel="noreferrer">PubChem</a></li>
              <li><a href="https://clinicaltrials.gov/" target="_blank" rel="noreferrer">ClinicalTrials.gov</a></li>
            </ul>
          </div>
          <div>
            <span className="label">Product</span>
            <ul role="list">
              <li><Link to="/app">Assistant</Link></li>
              <li><Link to="/compound/CHEMBL3353410">Compound explorer</Link></li>
            </ul>
          </div>
        </div>
      </div>

      <div className="shell foot-legal">
        <p>
          OncoLens is a research and information tool. It does not provide medical advice,
          diagnosis, or treatment, and accepts no patient-specific information. Retrieved
          content belongs to its original publishers and databases.
        </p>
        <p className="mono foot-meta">SPIH062</p>
      </div>
    </footer>
  )
}
