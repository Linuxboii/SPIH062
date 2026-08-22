import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="section">
      <div className="shell shell-narrow" style={{ textAlign: 'center', paddingBlock: '10vh' }}>
        <p className="eyebrow" style={{ marginBottom: 18 }}>404</p>
        <h1 className="display h2" style={{ marginBottom: 14 }}>
          Nothing retrieved for that address.
        </h1>
        <p className="prose" style={{ margin: '0 auto 30px', color: 'var(--muted)' }}>
          The page you asked for does not exist.
        </p>
        <Link className="btn btn-primary" to="/">Back to overview</Link>
      </div>
    </section>
  )
}
