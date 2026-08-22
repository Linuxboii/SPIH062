import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import MoleculeField from '../components/MoleculeField'
import { useReveal, useRevealGroup } from '../lib/useReveal'
import { getStats } from '../lib/api'
import '../styles/landing.css'

const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '—')

/* ── content ─────────────────────────────────────────────── */

const CONTRASTS = [
  {
    concern: 'Accuracy',
    chatbot: 'Generates plausible pharmacology from memory',
    lens: 'Answers assembled only from retrieved passages',
  },
  {
    concern: 'Structured data',
    chatbot: 'Flattens IC₅₀ = 0.02 nM into prose it may corrupt',
    lens: 'Numbers stay in SQL tables — never paraphrased',
  },
  {
    concern: 'Uncertainty',
    chatbot: 'Uniformly confident',
    lens: 'Scored before generating; abstains below threshold',
  },
  {
    concern: 'Provenance',
    chatbot: '“Studies show…”',
    lens: 'Every claim carries validated source IDs',
  },
]

const PIPELINE = [
  {
    n: '01',
    title: 'Resolve',
    body: 'Tagrisso, AZD9291 and osimertinib are one molecule. The query is normalised to a ChEMBL identifier before anything is retrieved.',
    aside: 'Tagrisso → CHEMBL3353410',
  },
  {
    n: '02',
    title: 'Retrieve',
    body: 'Two lanes run in parallel. Literature through hybrid lexical and semantic search; structured facts through SQL, never through a vector index.',
    aside: 'BM25 + vector → RRF',
  },
  {
    n: '03',
    title: 'Generate',
    body: 'The model receives only what was retrieved, and must return claims in a strict schema — each one carrying the sources it relies on.',
    aside: 'strict JSON contract',
  },
  {
    n: '04',
    title: 'Validate',
    body: 'Every cited identifier is checked against what retrieval actually returned. Anything else is stripped before it reaches you.',
    aside: 'fabrications removed',
  },
]

const SOURCE_META = [
  { name: 'PubMed', detail: 'Abstracts, MeSH terms, metadata', key: 'papers', unit: 'abstracts' },
  { name: 'ChEMBL', detail: 'Measured bioactivity across 15 targets', key: 'activities', unit: 'activities' },
  { name: 'PubChem', detail: 'Formula, weight, SMILES, XLogP', key: 'compounds', unit: 'compounds' },
  { name: 'ClinicalTrials.gov', detail: 'Phase, status, conditions', key: 'trials', unit: 'studies' },
]

const COMMITMENTS = [
  {
    title: 'Sources on every claim',
    body: 'Click any citation to read the passage it came from, with the matched text highlighted and a link to the original record.',
  },
  {
    title: 'Uncertainty made visible',
    body: 'Retrieval confidence is scored before an answer is written. Below threshold, the assistant declines and names what it could not find.',
  },
  {
    title: 'Predictions never dressed as facts',
    body: 'Machine-learned interaction predictions are labelled as predictions, shown with calibrated probabilities and held-out performance.',
  },
  {
    title: 'Research, not medical advice',
    body: 'The tool accepts no patient-specific input and makes no clinical recommendation. It exists to help researchers read faster.',
  },
]

/* ── page ────────────────────────────────────────────────── */

export default function Landing() {
  const [stats, setStats] = useState(null)
  useEffect(() => { getStats().then(setStats) }, [])

  const heroRef = useReveal()
  const contrastRef = useRevealGroup(60)
  const pipelineRef = useRevealGroup(90)
  const sourcesRef = useRevealGroup(55)
  const commitRef = useRevealGroup(70)
  const provenanceRef = useReveal()
  const compoundRef = useReveal()
  const closeRef = useReveal()

  return (
    <div className="landing">
      {/* ── hero ─────────────────────────────────────────── */}
      <header className="hero">
        <MoleculeField />
        <div className="hero-veil" />
        <div className="shell hero-inner reveal" ref={heroRef}>
          <p className="eyebrow hero-eyebrow">Oncology · Drug Discovery</p>
          <h1 className="display h1 hero-title">
            Evidence you can<br />follow back to source.
          </h1>
          <p className="lede hero-lede">
            A research assistant for oncology drug discovery that retrieves from real
            biomedical data — and binds every claim it makes to the record it came from.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/app">
              Open the assistant
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.4"
                  strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
            <Link className="btn btn-quiet" to="/compound/CHEMBL3353410">
              Explore a compound
            </Link>
          </div>
          <p className="hero-foot mono">
            Grounded in PubMed · ChEMBL · PubChem · ClinicalTrials.gov
          </p>
        </div>
      </header>

      {/* ── premise ──────────────────────────────────────── */}
      <section className="section section-premise">
        <div className="shell shell-narrow">
          <p className="premise display">
            PubMed indexes more than a million new records a year. The facts a researcher
            needs are split across prose, numbers and protocols — and
            <em> connecting them is still manual work.</em>
          </p>
        </div>
      </section>

      {/* ── contrast ─────────────────────────────────────── */}
      <section className="section" id="why">
        <div className="shell">
          <div className="sec-head">
            <p className="eyebrow">The distinction</p>
            <h2 className="display h2">A wrong answer here is not annoying.</h2>
            <p className="prose sec-dek">
              Grounding is an architectural decision, not a line in a prompt. Four places
              where the difference shows.
            </p>
          </div>

          <div className="contrast" ref={contrastRef}>
            <div className="contrast-head">
              <span className="label">Concern</span>
              <span className="label">A general chatbot</span>
              <span className="label label-sage">OncoLens</span>
            </div>
            {CONTRASTS.map((c) => (
              <div className="contrast-row reveal" data-reveal key={c.concern}>
                <div className="contrast-concern">{c.concern}</div>
                <div className="contrast-was">{c.chatbot}</div>
                <div className="contrast-is">{c.lens}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── provenance demo ──────────────────────────────── */}
      <section className="section section-tint">
        <div className="shell">
          <div className="prov-grid">
            <div className="prov-copy reveal" ref={provenanceRef}>
              <p className="eyebrow">Provenance</p>
              <h2 className="display h2">Two kinds of text.<br />Never confusable.</h2>
              <p className="prose sec-dek">
                Retrieved evidence and model inference are rendered differently, always.
                Unsourced statements are not discarded — a synthesis can be useful — but
                they are marked so plainly that they cannot be mistaken for evidence.
              </p>
              <p className="prose sec-dek">
                The backend validates each cited identifier against what retrieval actually
                returned. A citation the model invented does not survive the check.
              </p>
            </div>

            <div className="prov-demo">
              <div className="claim claim-grounded">
                <span className="claim-tag">
                  <span className="dot dot-sage" />
                  Grounded in retrieved data
                </span>
                <p>
                  Osimertinib is a third-generation EGFR tyrosine kinase inhibitor with
                  activity against the T790M resistance mutation.
                  <a className="cite" href="#src">PMID 31825714</a>
                </p>
              </div>

              <div className="claim claim-inferred">
                <span className="claim-tag">
                  <span className="dot dot-ochre" />
                  AI inference — not from retrieved data
                </span>
                <p>
                  This mechanism may generalise to other third-generation inhibitors in
                  the same structural class.
                </p>
              </div>

              <div className="claim claim-stripped">
                <span className="claim-tag">
                  <span className="dot dot-alert" />
                  Citation removed by validator
                </span>
                <p>
                  <s>PMID 99999999</s> — not present in the retrieved set for this query.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── pipeline ─────────────────────────────────────── */}
      <section className="section" id="how">
        <div className="shell">
          <div className="sec-head">
            <p className="eyebrow">How it works</p>
            <h2 className="display h2">Four steps, in order.</h2>
          </div>

          <ol className="pipeline" ref={pipelineRef}>
            {PIPELINE.map((s) => (
              <li className="pipe-step reveal" data-reveal key={s.n}>
                <span className="pipe-n mono">{s.n}</span>
                <div className="pipe-body">
                  <h3 className="h3 display pipe-title">{s.title}</h3>
                  <p className="pipe-text">{s.body}</p>
                  <span className="pipe-aside mono">{s.aside}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── compound intelligence ────────────────────────── */}
      <section className="section section-tint">
        <div className="shell">
          <div className="cmp-grid">
            <div className="cmp-copy reveal" ref={compoundRef}>
              <p className="eyebrow">Compound intelligence</p>
              <h2 className="display h2">Molecules as entities,<br />not as strings.</h2>
              <p className="prose sec-dek">
                Structure, physicochemical properties, Lipinski compliance, measured
                potencies against known targets, and active trials — read from the
                databases directly, never paraphrased.
              </p>
              <Link className="btn btn-quiet cmp-cta" to="/compound/CHEMBL3353410">
                Open osimertinib
              </Link>
            </div>

            <div className="cmp-card card">
              <div className="cmp-card-head">
                <div>
                  <h3 className="cmp-name display">Osimertinib</h3>
                  <p className="cmp-ids mono">CHEMBL3353410 · CID 71496458</p>
                </div>
                <span className="chip chip-sage">Approved</span>
              </div>
              <dl className="cmp-props">
                <div><dt className="label">Formula</dt><dd className="mono">C₂₈H₃₃N₇O₂</dd></div>
                <div><dt className="label">Weight</dt><dd className="mono">499.62</dd></div>
                <div><dt className="label">XLogP</dt><dd className="mono">4.51</dd></div>
                <div><dt className="label">Ro5</dt><dd className="mono cmp-pass">0 violations</dd></div>
              </dl>
              <div className="cmp-targets">
                <span className="label">Measured potency · from ChEMBL</span>
                <div className="cmp-target-row">
                  <span>EGFR</span>
                  <span className="mono">IC₅₀ 0.02 nM · pChEMBL 10.7</span>
                </div>
                <div className="cmp-target-row">
                  <span>EGFR</span>
                  <span className="mono">IC₅₀ 0.06 nM · pChEMBL 10.22</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── sources ──────────────────────────────────────── */}
      <section className="section" id="data">
        <div className="shell">
          <div className="sec-head">
            <p className="eyebrow">The corpus</p>
            <h2 className="display h2">Four public databases.</h2>
            <p className="prose sec-dek">
              Fifteen oncology targets, chosen so retrieval is genuinely good rather than
              broadly mediocre. Depth on a narrow field beats coverage of all of biomedicine.
            </p>
          </div>

          <div className="sources" ref={sourcesRef}>
            {SOURCE_META.map((s) => (
              <div className="source card card-hover reveal" data-reveal key={s.name}>
                <div className="source-count mono">{fmt(stats?.[s.key])}</div>
                <div className="source-unit label">{s.unit}</div>
                <h3 className="source-name">{s.name}</h3>
                <p className="source-detail">{s.detail}</p>
              </div>
            ))}
          </div>

          <p className="corpus-note">
            Live counts, read from the running index — not a target figure.
            {stats?.chunks ? ` ${fmt(stats.chunks)} embedded passages` : ''}
            {stats?.approved_compounds ? `, ${stats.approved_compounds} approved drugs` : ''}.
          </p>

          <p className="targets-line">
            <span className="label">Targets</span>
            <span className="targets-list mono">
              EGFR · ALK · BRAF · KRAS · HER2 · PD-L1 · VEGFR2 · CDK4 · CDK6 · PARP1 ·
              BCR-ABL · ROS1 · BTK · MEK1 · mTOR
            </span>
          </p>
        </div>
      </section>

      {/* ── model performance ────────────────────────────── */}
      <section className="section" id="model">
        <div className="shell">
          <div className="sec-head">
            <p className="eyebrow">Drug–target prediction</p>
            <h2 className="display h2">A real model, reported honestly.</h2>
            <p className="prose sec-dek">
              ECFP4 molecular fingerprints and gradient-boosted trees, trained on measured
              ChEMBL bioactivity. Validated with a <strong>scaffold split</strong> rather
              than a random one — random splits leak close analogues between train and test
              and inflate the score into meaninglessness.
            </p>
          </div>

          <div className="model-strip">
            <div className="model-cell">
              <span className="model-v">{stats?.dti_model?.mean_roc_auc ?? '—'}</span>
              <span className="model-l">Mean ROC-AUC</span>
            </div>
            <div className="model-cell">
              <span className="model-v">
                {stats?.dti_model?.min_roc_auc ?? '—'}–{stats?.dti_model?.max_roc_auc ?? '—'}
              </span>
              <span className="model-l">Range across targets</span>
            </div>
            <div className="model-cell">
              <span className="model-v">{stats?.dti_model?.targets_modelled ?? '—'}</span>
              <span className="model-l">Targets modelled</span>
            </div>
            <div className="model-cell">
              <span className="model-v">{fmt(stats?.predictions)}</span>
              <span className="model-l">Predictions</span>
            </div>
          </div>

          <p className="model-caption">
            Held-out performance on a scaffold split, measured on this corpus. Every
            prediction in the interface is labelled <em>predicted — not experimental</em>,
            carries a calibrated probability, and shows the per-target AUC beside it.
            Predictions that reproduce a measured activity are marked as such rather than
            presented as discoveries.
          </p>
        </div>
      </section>

      {/* ── commitments ──────────────────────────────────── */}
      <section className="section section-tint" id="responsible">
        <div className="shell">
          <div className="sec-head">
            <p className="eyebrow">Responsible by construction</p>
            <h2 className="display h2">Four commitments,<br />enforced in code.</h2>
          </div>

          <div className="commitments" ref={commitRef}>
            {COMMITMENTS.map((c, i) => (
              <div className="commitment reveal" data-reveal key={c.title}>
                <span className="commitment-n mono">{String(i + 1).padStart(2, '0')}</span>
                <h3 className="commitment-title">{c.title}</h3>
                <p className="commitment-body">{c.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── close ────────────────────────────────────────── */}
      <section className="section section-close">
        <div className="shell shell-narrow reveal" ref={closeRef}>
          <h2 className="display h2 close-title">
            Not a chatbot that talks about biomedicine.
          </h2>
          <p className="close-sub display">A retrieval system that happens to speak.</p>
          <div className="hero-actions close-actions">
            <Link className="btn btn-primary" to="/app">
              Open the assistant
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.4"
                  strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
