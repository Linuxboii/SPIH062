/**
 * Interface fixtures — used ONLY when the backend is unreachable.
 *
 * These are illustrative, not retrieved. Anything served from here is tagged
 * `demo: true` and the UI renders a standing banner saying so. A tool whose
 * entire premise is provenance must not let placeholder content pass for real
 * evidence, so the fixtures are deliberately labelled as illustrative rather
 * than dressed up with real-looking identifiers.
 */

export const DEMO_STATS = {
  papers: 0,
  chunks: 0,
  compounds: 0,
  activities: 0,
  trials: 0,
  targets: 15,
}

const ILLUSTRATIVE_SOURCES = [
  {
    id: 'DEMO:1',
    type: 'pubmed',
    title: 'Illustrative record — corpus not yet ingested',
    journal: 'Placeholder',
    year: null,
    snippet:
      'This panel shows how a retrieved abstract will be presented: the passage that matched, its metadata, and its retrieval score. Real records appear here once the corpus is ingested.',
    url: null,
    retrieval_score: null,
  },
]

export const DEMO_ANSWER = (query) => ({
  query,
  resolved_entities: [],
  route: 'unavailable',
  confidence: { score: 0, band: 'none' },
  abstained: true,
  claims: [],
  structured: { compounds: [], activities: [] },
  sources: ILLUSTRATIVE_SOURCES,
  gaps: [
    'The retrieval backend is not reachable, so no biomedical data was searched.',
    'No answer is generated without retrieved evidence — this is the same abstention path used when the corpus lacks support for a question.',
  ],
})

export const DEMO_COMPOUND = {
  chembl_id: 'CHEMBL3353410',
  pref_name: 'Osimertinib',
  smiles:
    'COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc1nccc(-c2cn(C)c3ccccc23)n1',
  inchikey: 'DUYJMQONPNNFPI-UHFFFAOYSA-N',
  mol_formula: 'C28H33N7O2',
  mol_weight: 499.6,
  xlogp: 3.7,
  hbd: 2,
  hba: 6,
  tpsa: 87.6,
  ro5_violations: 0,
  max_phase: 4,
  first_approval: 2015,
  pubchem_cid: '71496458',
  synonyms: ['Tagrisso', 'AZD9291', 'Osimertinib mesylate'],
  activities: [],
  predictions: [],
  trials: [],
  papers: [],
  demo_notice:
    'Structural and physicochemical values shown here are from PubChem CID 71496458 and are real. Activity, trial and literature panels are empty because the corpus has not been ingested yet.',
}
