# OncoLens — Product Requirements Document

**A grounded biomedical research assistant for oncology drug discovery.**

| | |
|---|---|
| Version | 1.0 |
| Date | 2026-08-22 |
| Status | Approved for build |
| Owner | sushanth@avlokai.com |
| Target | Hackathon demo, live |

---

## 1. Problem & Position

Biomedical literature grows faster than anyone can read it. PubMed indexes over a
million new records a year. Meanwhile the facts a drug-discovery researcher needs
are split across incompatible shapes: prose in abstracts, numbers in compound
databases, protocols in trial registries. Connecting them is manual, slow work.

OncoLens answers natural-language questions about oncology compounds and targets by
retrieving from real biomedical sources and generating answers where **every claim
is bound to a retrieved source or explicitly marked as unsourced**.

### Why this is not "just a chatbot"

A general chatbot optimises for fluency. This system optimises for **traceability**,
and the difference is architectural, not cosmetic:

| Concern | How a chatbot fails | How OncoLens is built |
|---|---|---|
| **Accuracy** | Generates plausible pharmacology from parametric memory | Answers are assembled only from retrieved passages; the generator never runs without context |
| **Structured data** | Flattens `IC50 = 12 nM` into prose it may corrupt | Numeric/structured facts live in relational tables and are read by SQL, never embedded or paraphrased |
| **Uncertainty** | Uniformly confident | Retrieval confidence is computed before generation; below threshold the system abstains and says what is missing |
| **Provenance** | "Studies show…" | Every claim carries validated source IDs; unsourced claims are visually quarantined in the UI |

### Non-goals

- Not a diagnostic or treatment tool. No patient-specific input, ever.
- Not a general medical Q&A system. Out-of-scope questions are refused, not guessed.
- Not a claim of novel drug discovery. Predictions are ranked hypotheses for triage.

---

## 2. Users & Scenarios

**Primary user:** an early-stage drug-discovery researcher or computational biologist
triaging a target or compound.

| # | Scenario | Surface |
|---|---|---|
| S1 | "What resistance mechanisms are reported for osimertinib in EGFR-mutant NSCLC?" | Chat |
| S2 | "Show me osimertinib — properties, targets, trials." | Compound Explorer |
| S3 | "Which compounds in the corpus hit KRAS G12C, and how potent are they?" | Chat → structured table |
| S4 | "Is this answer real? Where did it come from?" | Source drawer |
| S5 | "What might compound X also bind?" | DTI prediction panel |

---

## 3. Scope: Oncology

Depth over breadth. Narrow scope is what makes retrieval quality demonstrable.

**Targets (15):** EGFR, ALK, BRAF, KRAS, ERBB2/HER2, CD274/PD-L1, KDR/VEGFR2,
CDK4, CDK6, PARP1, ABL1/BCR-ABL, ROS1, BTK, MAP2K1/MEK1, MTOR.

**Corpus:**

| Source | Content | Volume | Access |
|---|---|---|---|
| PubMed (E-utilities) | Abstracts, titles, authors, journal, year, MeSH | ~25,000 | Free, verified |
| ChEMBL REST | Molecules, properties, bioactivity (IC50/Ki/Kd) | ~300 compounds, ~10k activities | Free, verified |
| PubChem PUG REST | Formula, MW, SMILES, XLogP, InChIKey | ~300 compounds | Free, verified |
| ClinicalTrials.gov v2 | Trial phase, status, conditions, interventions | ~2,000 studies | Free, verified |

All four endpoints were probed and confirmed live and key-free on 2026-08-22.

---

## 4. Architecture

```
┌──────────────── FRONTEND (React + Vite) ────────────────┐
│  Chat  ·  Compound Explorer  ·  Source Drawer           │
└───────────────────────┬─────────────────────────────────┘
                        │ REST + SSE
┌───────────────────────▼─────────────────────────────────┐
│                  BACKEND (FastAPI)                       │
│                                                          │
│   Entity Resolver ──► Query Router                       │
│         │                   │                            │
│         │        ┌──────────┴──────────┐                 │
│         │        ▼                     ▼                 │
│         │   LANE A: literature    LANE B: structured     │
│         │   BM25 + vector          SQL over facts        │
│         │   → RRF fusion                                 │
│         │        └──────────┬──────────┘                 │
│         │                   ▼                            │
│         │          Context Assembler                     │
│         │                   ▼                            │
│         │      Grounded Generator (gpt-5-nano)           │
│         │       → strict JSON claim contract             │
│         │                   ▼                            │
│         └────────► Citation Validator ──► Response       │
└───────────────────────┬─────────────────────────────────┘
                        ▼
        Postgres 16 + pgvector  (isolated container)
```

### 4.1 Entity Resolver

The component that makes this domain-specific rather than generic text RAG.

Before retrieval, the query is scanned for biomedical entities and normalised
against a synonym table built at ingest from ChEMBL `molecule_synonyms` and
PubChem synonyms:

```
"Tagrisso" ─┐
"AZD9291"  ─┼─► CHEMBL3353410 (osimertinib)
"osimertinib"┘
```

Gene symbols resolve similarly (`HER2` → `ERBB2`). Resolved entities are attached
to the query and drive both lanes: Lane B filters SQL by entity ID, Lane A boosts
lexical matches on all known synonyms.

**Why it matters:** without this, "What is Tagrisso?" retrieves nothing, because the
corpus overwhelmingly says "osimertinib".

### 4.2 Lane A — Literature retrieval

Hybrid, because pure dense retrieval smears rare lexical tokens like `G12C`.

1. **Lexical:** Postgres `tsvector` BM25 over abstract chunks.
2. **Dense:** cosine over `vector(1536)` via pgvector HNSW.
3. **Fusion:** Reciprocal Rank Fusion, `k = 60`, over both lists.
4. **Top-k = 8** chunks pass to the assembler.

Chunking: abstracts split at ~220 tokens with 40-token overlap, never across
sentence boundaries. Each chunk retains its PMID, so every chunk is independently
citable.

**Embeddings:** OpenAI `text-embedding-3-small` (1536-d) for both corpus and query.
Chosen over local PubMedBERT because the deployment target has ~1GB free RAM and
cannot host PyTorch without risking OOM kills against co-resident production
services. One-time corpus embedding cost: ~$0.20.

### 4.3 Lane B — Structured retrieval

Compound properties, bioactivities, and trials are **relational and queried by SQL**.
They are never embedded and never paraphrased by the model — a molecular weight is a
number, and a number that passes through a language model can come out wrong.

Structured results are injected into the context as a typed block the generator is
instructed to quote verbatim, and are additionally returned to the frontend as raw
JSON so the UI can render them as tables independent of anything the model says.

### 4.4 Grounded generation contract

The generator is constrained to emit a strict JSON schema:

```json
{
  "claims": [
    {
      "text": "Osimertinib is a third-generation EGFR TKI...",
      "source_ids": ["PMID:31825714", "CHEMBL:3353410"],
      "confidence": "high"
    }
  ],
  "abstained": false,
  "gaps": []
}
```

**The backend then validates every `source_id` against the set actually retrieved
for this query.** IDs that were not retrieved are stripped, and the claim is
downgraded to unsourced. This makes citation fabrication structurally impossible
to present as real — the model cannot invent a citation that survives validation.

Claims arriving with zero valid sources are not discarded; they are returned flagged
`unsourced: true` and the UI renders them in a visually distinct style labelled
*AI inference — not from retrieved data*.

Model: `gpt-5-nano`, `reasoning_effort: low`, temperature 0, response format
`json_schema` with `strict: true`.

### 4.5 Uncertainty & abstention

A retrieval confidence score is computed **before** generation:

| Signal | Weight |
|---|---|
| Top-1 fused retrieval score | 0.4 |
| Number of chunks above similarity floor | 0.3 |
| Agreement across independent sources (distinct PMIDs / DBs) | 0.3 |

- `score < 0.35` → **abstain**. Return "Not enough grounded evidence", name the gap,
  and still show whatever partial sources were found. No generation runs.
- `0.35 – 0.6` → generate, banner the answer as low-confidence.
- `> 0.6` → normal.

Abstention is a first-class success state, not an error. It is shown in the demo
deliberately.

---

## 5. Data Model

```sql
-- Literature
papers(pmid PK, title, abstract, journal, year, authors[], mesh_terms[], doi, url)
chunks(id PK, pmid FK, ord, text, tsv tsvector, embedding vector(1536))

-- Structured compounds
compounds(chembl_id PK, pref_name, smiles, inchikey, mol_formula, mol_weight,
          xlogp, hbd, hba, tpsa, ro5_violations, max_phase, first_approval,
          pubchem_cid, fingerprint bytea)
synonyms(id PK, chembl_id FK, synonym, source)      -- entity resolver
targets(chembl_id PK, pref_name, gene_symbol, organism, target_type)
activities(id PK, compound_id FK, target_id FK, standard_type, standard_value,
           standard_units, pchembl_value, assay_chembl_id, source_doc_id)

-- Trials
trials(nct_id PK, title, phase, status, conditions[], interventions[],
       enrollment, start_date, url)
trial_compounds(nct_id FK, chembl_id FK)

-- ML
dti_predictions(compound_id FK, target_id FK, probability, model_version)
```

Indexes: HNSW on `chunks.embedding` (cosine), GIN on `chunks.tsv`, GIN on
`synonyms.synonym` (trigram), btree on all foreign keys.

---

## 6. Drug–Target Interaction Prediction

The creativity feature, built to be *honest* rather than impressive.

- **Training data:** real ChEMBL bioactivities. Positive = `pChEMBL ≥ 6` (≤1 µM).
  Negatives sampled from compound–target pairs measured but inactive, plus random
  unmeasured pairs at a controlled ratio.
- **Features:** RDKit ECFP4 Morgan fingerprints (2048-bit, radius 2), computed at
  ingest and stored, plus a one-hot target identifier.
- **Model:** gradient-boosted trees (scikit-learn), one multi-label model across the
  15 targets. Small enough to ship as a pickle (<10 MB) and to infer in milliseconds.
- **Calibration:** isotonic regression on a held-out split, so the probability shown
  is a real probability.
- **Validation:** scaffold split, not random split — random splits leak analogues
  between train and test and inflate scores. Report ROC-AUC and PR-AUC per target.

**Presentation rules (non-negotiable):**
- Every prediction is labelled **Predicted — not experimental**.
- Calibrated probability shown numerically, never as a bare "yes".
- Predictions that reproduce a known experimental activity already in `activities`
  are marked as such rather than presented as discoveries.
- Held-out performance is displayed in the UI next to the predictions.

---

## 7. Backend — API Surface

FastAPI. All responses Pydantic-typed.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Ask a question. SSE stream. Returns claims + sources + confidence. |
| `GET` | `/api/compound/{query}` | Resolve and return a full compound dossier. |
| `GET` | `/api/compound/{id}/targets` | Known activities + predicted interactions. |
| `GET` | `/api/target/{gene}` | Target dossier: compounds, potencies, trials. |
| `GET` | `/api/source/{type}/{id}` | Full retrieved passage for the source drawer. |
| `GET` | `/api/search/suggest?q=` | Typeahead over the synonym table. |
| `GET` | `/api/stats` | Corpus counts, for the "what's in here" panel. |
| `GET` | `/api/health` | Liveness + DB + embedding-API reachability. |

**`POST /api/chat` response shape:**

```json
{
  "query": "...",
  "resolved_entities": [{"text": "Tagrisso", "type": "compound", "id": "CHEMBL3353410"}],
  "route": "hybrid",
  "confidence": {"score": 0.78, "band": "high"},
  "abstained": false,
  "claims": [
    {"text": "...", "sources": [{"id": "PMID:31825714", "type": "pubmed"}],
     "unsourced": false, "confidence": "high"}
  ],
  "structured": {"compounds": [...], "activities": [...]},
  "sources": [
    {"id": "PMID:31825714", "type": "pubmed", "title": "...", "year": 2019,
     "snippet": "...", "url": "https://pubmed.ncbi.nlm.nih.gov/31825714/",
     "retrieval_score": 0.83}
  ],
  "gaps": []
}
```

### Backend module layout

```
backend/app/
  main.py              FastAPI app, CORS, routers
  config.py            pydantic-settings
  db.py                connection pool
  models.py            SQLAlchemy tables
  schemas.py           Pydantic request/response
  routers/             chat.py  compound.py  target.py  source.py  meta.py
  services/
    entities.py        entity resolution + synonym lookup
    retrieval.py       BM25 + vector + RRF fusion
    structured.py      SQL fact queries
    assembler.py       context building, token budgeting
    generator.py       OpenAI call, strict JSON schema
    validator.py       citation validation, unsourced flagging
    confidence.py      retrieval confidence scoring
    dti.py             model load + inference
ingest/                pubmed.py chembl.py pubchem.py trials.py embed.py
                       fingerprints.py train_dti.py  (run LOCALLY only)
```

**Deployment split:** everything under `ingest/` runs on the local workstation. The
VPS receives only `backend/app/` plus a pre-built database dump. This keeps RDKit,
scikit-learn training, and bulk embedding off the constrained server.

---

## 8. Frontend

React 18 + Vite. No component library — hand-built, so the grounding UI behaves
exactly as specified.

### 8.1 Global

- **Persistent disclaimer bar**, top of viewport, not dismissible:
  *"Research tool. Grounded in public biomedical data. Not medical advice — do not
  use for diagnosis or treatment."*
- Dark/light aware. Responsive to 768px.

### 8.2 Chat (`/`)

Two-column: conversation left, **evidence panel pinned right**.

- **Sourced claim** — normal text, superscript citation chips `[1]`, hover shows
  title + year, click opens the source drawer.
- **Unsourced claim** — amber left border, italic, small header
  *AI inference — not from retrieved data*. Visually impossible to confuse with a
  sourced claim. This is the single most important pixel in the app.
- **Confidence chip** at answer head: green / amber / grey.
- **Abstention state** — dedicated card, not an error toast: what was asked, what
  was found, what was missing, plus the partial sources.
- **Evidence panel** — every retrieved source as a card with title, journal, year,
  retrieval score, matched snippet. Clicking a chip scrolls and highlights.
- **Structured blocks** render as real tables from `structured`, not as model prose.
- Streaming via SSE; claims appear as they validate.

### 8.3 Compound Explorer (`/compound/:id`)

- **Header:** preferred name, ChEMBL + PubChem IDs, max phase badge, approval year.
- **Structure:** 2D depiction rendered client-side from SMILES with SmilesDrawer
  (pure JS canvas, no backend load, no external calls).
- **Properties table:** formula, MW, XLogP, HBD, HBA, TPSA — each cell showing its
  source database.
- **Lipinski Ro5 panel:** four rules, pass/fail each, violation count.
- **Known targets:** table of measured activities with assay type, value, units,
  pChEMBL, sorted by potency, each row linking to its ChEMBL assay.
- **Predicted targets:** separate panel, amber-framed, headed *Predicted — not
  experimental*, with calibrated probabilities and model held-out AUC.
- **Trials:** phase, status, condition, enrolment, link to ClinicalTrials.gov.
- **Recent literature:** newest abstracts mentioning the compound, one-line grounded
  summaries, links to PubMed.

### 8.4 Source Drawer

Slides from right over any surface. Full retrieved passage with the matched span
highlighted, full metadata, retrieval score with a plain-language explanation of why
it was retrieved, and a deep link to the primary source.

### 8.5 Component inventory

```
App · DisclaimerBar · ChatView · MessageList · ClaimBlock · CitationChip
ConfidenceBadge · AbstentionCard · EvidencePanel · SourceCard · SourceDrawer
CompoundView · MoleculeCanvas · PropertyTable · LipinskiPanel · ActivityTable
PredictionPanel · TrialTable · RecentPapers · SearchBar · StatsBar
```

---

## 9. Deployment

### 9.1 Topology

| Component | Placement | Port |
|---|---|---|
| Postgres 16 + pgvector | **New isolated Docker container**, reusing the `pgvector/pgvector:pg16` image already present | 5434 (host) |
| FastAPI backend | systemd service, venv | 8891 (localhost) |
| React build | static, served by nginx | via 8891 |

Corpus is built entirely on the local workstation and shipped as a `pg_dump`,
restored into the new container. The VPS never embeds a corpus, never trains a
model, and never loads PyTorch or RDKit.

Estimated VPS footprint: **~150 MB RAM, ~300 MB disk** excluding the database
(~1.5 GB with vectors).

### 9.2 Host constraints (measured 2026-08-22)

`203.57.85.191` runs 20+ services on 3.7 GB RAM. Post-cleanup: 13 GB disk free,
~1.1 GB RAM available, swap saturated. The inference-light design above is a
direct consequence of these numbers.

### 9.3 Venkateswara Polymers — protected, do not touch

A live production ERP shares this host. The following are **off-limits**:

| Asset | Detail |
|---|---|
| Process | PM2 `vp-api`, uvicorn, **port 3000**, cwd `/root/backend` |
| Public | `https://vp-api.avlokai.com` |
| Routing | cloudflared tunnel `n8n-tunnel`, `/etc/cloudflared/config.yml` |
| Database | `venkateswara_polymers` — **local Postgres 16 on port 5432**, owner `admin` |
| Logs | `/root/.pm2/logs/vp-api-*.log` |

**Hard rules:**
1. Never edit `/etc/cloudflared/config.yml` — it is shared by four hostnames;
   a syntax error or a `cloudflared` restart takes VP offline.
2. Never use the host Postgres on 5432. OncoLens gets its own container on 5434.
3. Never bind port 3000, or 8890 (MetroMind), or any port in the in-use set.
4. Run `pm2 save` only after confirming VP is `online`, so a bad state is not persisted.
5. VP health check — HTTP 200 on both `localhost:3000` and `https://vp-api.avlokai.com`,
   plus a DB row count — **before and after every deployment step**.

### 9.4 Rollback

Single-command teardown: stop the systemd unit, remove the nginx site, stop and
remove the OncoLens container. Nothing OncoLens installs is shared with any other
service, so rollback cannot affect VP or the other twenty.

---

## 10. Build Phases

| # | Phase | Output | Gate |
|---|---|---|---|
| 0 | Scaffold | Repo, compose, schema, migrations | Container up, tables exist |
| 1 | Ingest | PubMed + ChEMBL + PubChem + trials loaded locally | Row counts match targets |
| 2 | Embed | Chunks embedded, HNSW built | Vector search returns sane neighbours |
| 3 | Retrieval | Entity resolver, hybrid search, RRF | Fixed query set returns correct PMIDs |
| 4 | Generation | Claim contract, citation validator, confidence | Fabricated citations provably stripped |
| 5 | API | All endpoints, SSE streaming | Contract tests green |
| 6 | Frontend | Three surfaces, grounding UI | Manual walkthrough |
| 7 | DTI | Fingerprints, training, calibration | Scaffold-split AUC reported |
| 8 | Deploy | Dump shipped, service up, nginx routed | VP health green before *and* after |
| 9 | Demo prep | Scripted queries incl. an abstention case | Full dry run |

---

## 11. Rubric Mapping

| Criterion | Marks | Where earned |
|---|---|---|
| Understanding the problem | 10 | §1 two-lane rationale; structured-vs-text split; abstention as a design goal |
| Data grounding & accuracy | 25 | §4.2–4.4 hybrid retrieval, claim contract, **server-side citation validation** |
| Domain-specific analysis | 20 | §4.1 entity resolution; §4.3 SQL over bioactivity; §6 fingerprints; Compound Explorer |
| Responsible AI | 15 | §4.5 abstention, confidence bands, unsourced quarantine, persistent disclaimer, "predicted not experimental" |
| Ease of use | 10 | §8 typeahead, one-click citations, no jargon in chrome |
| Creativity | 10 | §6 calibrated DTI with scaffold split; live evidence panel; abstention shown deliberately |
| Demo & explanation | 10 | §10 phase 9; the validator can be demonstrated live |

**Demo moment worth rehearsing:** ask something the corpus cannot support and let it
abstain. Most teams will hide that. Showing it — with the gap named and partial
sources still listed — is the clearest possible proof the grounding is real.

---

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Host OOM kills a client service | Severe — production ERP | Inference-light design; no torch; measured 150 MB footprint; isolated container |
| Demo-day network failure | Demo dies | Corpus fully local to the box; only generation needs network. Extractive fallback returns cited passages with no LLM |
| OpenAI rate limit / outage | No generated prose | Same extractive fallback; retrieval and Compound Explorer stay fully functional |
| PubMed throttling during ingest | Slow build | 3 req/s honoured, batches of 200, resumable checkpointing |
| DTI model looks like overclaiming | Credibility, Responsible-AI marks | Scaffold split, calibration, "predicted not experimental" framing, AUC shown |
| Scope creep beyond oncology | Retrieval quality drops | Target list frozen at 15 |

---

## 13. Open Items

- Password auth on the VPS is a shared-credential path; the user has stated they
  will rotate `Parzival@1477` after this work. Key-based access is recommended.
- Swap on the host is saturated and will not clear without a `swapoff/swapon` cycle,
  which needs 2 GB free RAM. Deferred as too risky while client services are live.
