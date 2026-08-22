-- OncoLens schema
-- Two table families, joined only by resolved entity IDs:
--   literature  -> papers, chunks        (embedded, retrieved by hybrid search)
--   structured  -> compounds, targets, activities, trials  (SQL only, never embedded)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─────────────────────────── literature ───────────────────────────

CREATE TABLE IF NOT EXISTS papers (
    pmid            TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    abstract        TEXT,
    journal         TEXT,
    year            INTEGER,
    authors         TEXT[],
    mesh_terms      TEXT[],
    doi             TEXT,
    url             TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS papers_year_idx ON papers (year DESC);

CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    pmid            TEXT NOT NULL REFERENCES papers(pmid) ON DELETE CASCADE,
    ord             INTEGER NOT NULL,
    text            TEXT NOT NULL,
    -- generated so it can never drift out of sync with `text`
    tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding       vector(1536),
    UNIQUE (pmid, ord)
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx   ON chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS chunks_pmid_idx  ON chunks (pmid);
-- HNSW built after bulk load in ingest/embed.py; cosine to match OpenAI embeddings.

-- ─────────────────────────── structured ───────────────────────────

CREATE TABLE IF NOT EXISTS targets (
    chembl_id       TEXT PRIMARY KEY,
    pref_name       TEXT,
    gene_symbol     TEXT,
    organism        TEXT,
    target_type     TEXT
);

CREATE INDEX IF NOT EXISTS targets_gene_idx ON targets (upper(gene_symbol));

CREATE TABLE IF NOT EXISTS compounds (
    chembl_id       TEXT PRIMARY KEY,
    pref_name       TEXT,
    smiles          TEXT,
    inchikey        TEXT,
    mol_formula     TEXT,
    mol_weight      DOUBLE PRECISION,
    xlogp           DOUBLE PRECISION,
    hbd             INTEGER,
    hba             INTEGER,
    tpsa            DOUBLE PRECISION,
    ro5_violations  INTEGER,
    max_phase       DOUBLE PRECISION,
    first_approval  INTEGER,
    pubchem_cid     TEXT,
    -- ECFP4 Morgan fingerprint, 2048-bit, packed. Precomputed at ingest so the
    -- server never needs RDKit at runtime.
    fingerprint     BYTEA
);

CREATE INDEX IF NOT EXISTS compounds_name_idx ON compounds USING GIN (pref_name gin_trgm_ops);

-- Entity resolution: brand names, research codes, generic names -> one ChEMBL ID.
CREATE TABLE IF NOT EXISTS synonyms (
    id              BIGSERIAL PRIMARY KEY,
    chembl_id       TEXT REFERENCES compounds(chembl_id) ON DELETE CASCADE,
    target_id       TEXT REFERENCES targets(chembl_id) ON DELETE CASCADE,
    synonym         TEXT NOT NULL,
    synonym_norm    TEXT NOT NULL,          -- lowercased, punctuation stripped
    source          TEXT,
    kind            TEXT NOT NULL,          -- 'compound' | 'target'
    CHECK (chembl_id IS NOT NULL OR target_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS synonyms_norm_idx  ON synonyms (synonym_norm);
CREATE INDEX IF NOT EXISTS synonyms_trgm_idx  ON synonyms USING GIN (synonym_norm gin_trgm_ops);

CREATE TABLE IF NOT EXISTS activities (
    id              BIGSERIAL PRIMARY KEY,
    compound_id     TEXT NOT NULL REFERENCES compounds(chembl_id) ON DELETE CASCADE,
    target_id       TEXT NOT NULL REFERENCES targets(chembl_id) ON DELETE CASCADE,
    standard_type   TEXT,
    standard_value  DOUBLE PRECISION,
    standard_units  TEXT,
    pchembl_value   DOUBLE PRECISION,
    assay_chembl_id TEXT,
    source_doc_id   TEXT
);

CREATE INDEX IF NOT EXISTS activities_compound_idx ON activities (compound_id);
CREATE INDEX IF NOT EXISTS activities_target_idx   ON activities (target_id);
CREATE INDEX IF NOT EXISTS activities_pchembl_idx  ON activities (pchembl_value DESC NULLS LAST);

-- ─────────────────────────── trials ───────────────────────────

CREATE TABLE IF NOT EXISTS trials (
    nct_id          TEXT PRIMARY KEY,
    title           TEXT,
    phase           TEXT,
    status          TEXT,
    conditions      TEXT[],
    interventions   TEXT[],
    enrollment      INTEGER,
    start_date      TEXT,
    url             TEXT
);

CREATE TABLE IF NOT EXISTS trial_compounds (
    nct_id          TEXT NOT NULL REFERENCES trials(nct_id) ON DELETE CASCADE,
    chembl_id       TEXT NOT NULL REFERENCES compounds(chembl_id) ON DELETE CASCADE,
    PRIMARY KEY (nct_id, chembl_id)
);

CREATE INDEX IF NOT EXISTS trial_compounds_chembl_idx ON trial_compounds (chembl_id);

-- ─────────────────────────── ML ───────────────────────────

CREATE TABLE IF NOT EXISTS dti_predictions (
    compound_id     TEXT NOT NULL REFERENCES compounds(chembl_id) ON DELETE CASCADE,
    target_id       TEXT NOT NULL REFERENCES targets(chembl_id) ON DELETE CASCADE,
    probability     DOUBLE PRECISION NOT NULL,
    is_known        BOOLEAN NOT NULL DEFAULT FALSE,   -- reproduces a measured activity
    model_version   TEXT NOT NULL,
    PRIMARY KEY (compound_id, target_id, model_version)
);

CREATE INDEX IF NOT EXISTS dti_compound_idx ON dti_predictions (compound_id, probability DESC);

-- Per-target held-out metrics, surfaced in the UI next to predictions so the
-- model's honesty is visible rather than claimed.
CREATE TABLE IF NOT EXISTS dti_metrics (
    target_id       TEXT NOT NULL REFERENCES targets(chembl_id) ON DELETE CASCADE,
    model_version   TEXT NOT NULL,
    roc_auc         DOUBLE PRECISION,
    pr_auc          DOUBLE PRECISION,
    n_train         INTEGER,
    n_test          INTEGER,
    split           TEXT DEFAULT 'scaffold',
    PRIMARY KEY (target_id, model_version)
);
