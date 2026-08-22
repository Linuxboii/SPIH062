# SPIH062

**OncoLens** — a grounded biomedical research assistant for oncology drug discovery.

Every claim the assistant makes is bound to a record it actually retrieved, or is
visibly marked as model inference. Fabricated citations are stripped server-side
before they can reach the user.

---

## Why this is not just a chatbot

| Concern | A general chatbot | OncoLens |
|---|---|---|
| Accuracy | Generates plausible pharmacology from memory | Answers assembled only from retrieved passages |
| Structured data | Flattens `IC50 = 12 nM` into prose it may corrupt | Numbers stay in SQL tables — never paraphrased |
| Uncertainty | Uniformly confident | Scored before generating; abstains below threshold |
| Provenance | "Studies show…" | Every claim carries validated source IDs |

## Architecture

```
Query
  ↓
Entity Resolver        Tagrisso · AZD9291 → CHEMBL3353410
  ↓
Query Router
  ├── Lane A · literature    BM25 + pgvector → RRF fusion
  └── Lane B · structured    SQL over typed facts (never embedded)
  ↓
Context Assembler → Generator (strict JSON claim contract)
  ↓
Citation Validator     strips any source ID not actually retrieved
  ↓
Answer + evidence
```

The validator is the load-bearing component: the model must return claims in a
strict schema listing the sources each one relies on, and the backend checks every
identifier against what retrieval actually returned. Anything else is removed and
the claim is downgraded to unsourced.

## Data sources

All public, all free, no API key required.

| Source | Content |
|---|---|
| PubMed (NCBI E-utilities) | Abstracts, MeSH terms, metadata |
| ChEMBL | Molecules and measured bioactivity |
| PubChem | Formula, weight, SMILES, XLogP |
| ClinicalTrials.gov | Phase, status, conditions |

Scope is 15 oncology targets — EGFR, ALK, BRAF, KRAS, HER2, PD-L1, VEGFR2, CDK4,
CDK6, PARP1, BCR-ABL, ROS1, BTK, MEK1, mTOR.

## Stack

- **Frontend** — React 18, Vite, React Router
- **Backend** — FastAPI, Postgres 16 + pgvector
- **Retrieval** — hybrid BM25 (`tsvector`) + dense vectors, Reciprocal Rank Fusion
- **Embeddings** — OpenAI `text-embedding-3-small`
- **Generation** — `gpt-5-nano`, temperature 0, strict JSON schema
- **Chemistry / ML** — RDKit fingerprints, scikit-learn with isotonic calibration

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`. The interface runs standalone before the backend
exists — when the API is unreachable it shows a standing banner saying so rather
than presenting placeholder content as real evidence.

## Documentation

- [`docs/PRD.md`](docs/PRD.md) — full product requirements
- [`docs/DECK_CONTEXT.md`](docs/DECK_CONTEXT.md) — presentation source

---

## Disclaimer

OncoLens is a research and information tool. It does not provide medical advice,
diagnosis, or treatment, and accepts no patient-specific information. Retrieved
content belongs to its original publishers and databases.
