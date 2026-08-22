# OncoLens — Deck Context Slip

Source text for building a presentation. Each slide gives **on-slide text** (keep it
short, that's what goes on the slide) and **speaker notes** (what you actually say).

Suggested length: 18 core slides, ~8–10 minutes. Slides marked ⭐ are the ones that
win marks — do not cut them.

---

## SLIDE 1 — Title

**On slide:**

> # OncoLens
> ### A grounded biomedical research assistant for oncology drug discovery
>
> Every claim traceable to real data — or visibly marked as not.
>
> *[Team name] · [Date]*

**Speaker notes:**
Open with the one-liner and nothing else. Don't explain yet. The tagline is the
whole thesis: this system's job isn't to sound smart, it's to be checkable.

---

## SLIDE 2 — The Problem

**On slide:**

> ### Biomedical research produces more information than anyone can read
>
> - PubMed indexes **1M+ new records every year**
> - Drug discovery is slow and expensive partly because **connecting the dots is manual**
> - The facts a researcher needs are split across incompatible shapes:
>   - Prose in abstracts
>   - Numbers in compound databases
>   - Protocols in trial registries
>
> **No single tool reads across all three.**

**Speaker notes:**
Set up the pain before the solution. The key insight to plant here is the *shape*
problem, not just the *volume* problem. Everyone knows there's too much to read.
Fewer people notice that the data isn't all the same kind of thing — and that's what
makes it hard to build for.

---

## SLIDE 3 ⭐ — Why This Is Not Just a Chatbot

**On slide:**

> ### A wrong answer here is not annoying. It's harmful.
>
> | Concern | A chatbot | OncoLens |
> |---|---|---|
> | **Accuracy** | Plausible pharmacology from memory | Answers assembled *only* from retrieved passages |
> | **Structured data** | Flattens `IC50 = 12 nM` into prose | Numbers stay in SQL tables — never paraphrased |
> | **Uncertainty** | Uniformly confident | Confidence scored *before* generating; abstains below threshold |
> | **Provenance** | "Studies show…" | Every claim carries validated source IDs |
>
> **Grounding is an architecture decision, not a prompt.**

**Speaker notes:**
This is the slide that answers "did you understand the problem." Land the last line
hard. Most teams will write "please cite your sources" in a prompt and call it
grounded. We made it structurally impossible to fake — explained on slide 8.

The `IC50` row is worth pausing on: a molecular weight is a number, and a number that
passes through a language model can come out wrong. So ours never does.

---

## SLIDE 4 — What We're Building

**On slide:**

> ### Three surfaces, one grounded engine
>
> **1. Chat** — Ask anything about oncology compounds and targets. Answers arrive
> with inline citations and a live evidence panel.
>
> **2. Compound Explorer** — Look up any compound: structure, properties, known
> targets with measured potencies, active trials.
>
> **3. Source Drawer** — Click any citation. See the actual retrieved passage, the
> matched text highlighted, and a link to the original paper.

**Speaker notes:**
Keep this fast. It's orientation, not the pitch. The audience needs a mental picture
of the app before you go into the architecture, or the next four slides won't land.

---

## SLIDE 5 — Scope: We Went Deep, Not Wide

**On slide:**

> ### Oncology only. 15 targets. On purpose.
>
> EGFR · ALK · BRAF · KRAS · HER2 · PD-L1 · VEGFR2 · CDK4 · CDK6 · PARP1 ·
> BCR-ABL · ROS1 · BTK · MEK1 · mTOR
>
> - **~25,000** PubMed abstracts
> - **~300** compounds with full property + bioactivity data
> - **~10,000** measured compound–target activities
> - **~2,000** clinical trials
>
> **Depth on a narrow topic beats a shallow attempt at all of biomedicine.**

**Speaker notes:**
Frame the narrow scope as a *decision*, not a limitation — because it is one. A
retrieval system over all of biomedicine returns mush. Over 15 well-chosen oncology
targets, it returns the right paper. We can demonstrate that live.

---

## SLIDE 6 — Real Data, Real Sources

**On slide:**

> ### Four public biomedical databases. No API keys. All verified live.
>
> | Source | What we take | Volume |
> |---|---|---|
> | **PubMed** (NCBI E-utilities) | Abstracts, MeSH terms, metadata | ~25,000 |
> | **ChEMBL** | Molecules + bioactivity (IC50 / Ki / Kd) | ~300 / ~10k |
> | **PubChem** | Formula, MW, SMILES, XLogP | ~300 |
> | **ClinicalTrials.gov** | Phase, status, conditions | ~2,000 |
>
> *All four endpoints probed and confirmed working before design was finalised.*

**Speaker notes:**
Mention that we tested every endpoint before committing to the design rather than
assuming they'd work — that's why there are no placeholders in this plan. If asked
about DrugBank: it requires a licence for bulk access, ChEMBL is the open equivalent
and gives us the bioactivity data we actually need.

---

## SLIDE 7 ⭐ — Architecture: Two Retrieval Lanes

**On slide:**

> ### Biomedical data is half prose, half numbers. So we built two paths.
>
> ```
>              User question
>                    ↓
>            Entity Resolver          "Tagrisso" → CHEMBL3353410
>                    ↓
>              Query Router
>              ↙          ↘
>    LANE A                  LANE B
>    Literature              Structured
>    BM25 + vector           SQL over typed facts
>    → RRF fusion            (never embedded)
>              ↘          ↙
>           Context Assembler
>                    ↓
>          Generator (gpt-5-nano)
>                    ↓
>          Citation Validator  ← the load-bearing part
>                    ↓
>             Answer + sources
> ```

**Speaker notes:**
Walk it top to bottom in about 40 seconds. The two things to emphasise:

1. **Lane B never touches the vector database.** Structured facts are read by SQL and
   handed to the UI as raw JSON. The model can describe them but cannot alter them.
2. **The validator sits after the model, not before.** Explain that on slide 8.

---

## SLIDE 8 ⭐⭐ — The Citation Validator (Our Core Idea)

**On slide:**

> ### The model cannot invent a citation that survives.
>
> The generator must return strict JSON:
>
> ```json
> {
>   "claims": [{
>     "text": "Osimertinib is a third-generation EGFR TKI...",
>     "source_ids": ["PMID:31825714"],
>     "confidence": "high"
>   }]
> }
> ```
>
> Then the **backend checks every `source_id` against what was actually retrieved.**
>
> - ID was retrieved → citation stands
> - ID was **not** retrieved → **stripped**, claim downgraded to unsourced
>
> **Fabricated citations cannot reach the user as real.**

**Speaker notes:**
This is the single most important slide in the deck. Slow down.

The standard approach is to ask the model to cite and trust it. Models hallucinate
citations that *look* perfect — right format, plausible PMID, wrong or nonexistent
paper. Asking nicely does not fix this.

Our fix is to treat the model's citations as *claims to be verified*, not as output.
The backend holds the list of what retrieval actually returned. Anything the model
cites that isn't on that list gets stripped before the user sees it.

**Say this line:** "We can demo this live — we can show the model citing something we
never retrieved, and show the system catching it."

---

## SLIDE 9 ⭐ — Retrieved vs. AI-Generated, Made Visible

**On slide:**

> ### Two kinds of text. Never confusable.
>
> **✅ Grounded in retrieved data**
> > Osimertinib is a third-generation EGFR tyrosine kinase inhibitor with activity
> > against the T790M resistance mutation. `[PMID 31825714]`
>
> **⚠️ AI inference — not from retrieved data**
> > *This mechanism may generalise to other third-generation inhibitors in the same class.*
>
> Unsourced claims are **not deleted** — they're quarantined: amber border, italic,
> explicitly labelled.

**Speaker notes:**
Rubric asks for "clear labelling of which parts come from retrieved data versus AI
summary." This is that, done structurally.

Note the design choice: we don't throw unsourced claims away. Sometimes the model's
synthesis is genuinely useful. We just make it impossible to mistake for evidence.
The researcher decides what to trust — but they always know which is which.

---

## SLIDE 10 ⭐ — When We Don't Know, We Say So

**On slide:**

> ### Abstention is a feature, not a failure.
>
> Retrieval confidence is scored **before** the model runs:
>
> - Top-1 retrieval score — *weight 0.4*
> - Number of chunks above the similarity floor — *weight 0.3*
> - Agreement across independent sources — *weight 0.3*
>
> | Score | Behaviour |
> |---|---|
> | `< 0.35` | **Abstain.** Name the gap. Show partial sources. *No generation runs.* |
> | `0.35–0.6` | Generate, banner as low confidence |
> | `> 0.6` | Normal answer |
>
> **Presenting a guess as a fact is worse than saying "I'm not certain."**

**Speaker notes:**
Emphasise "*no generation runs*" — we don't generate then filter, we decline to
generate at all. Cheaper, and it removes the temptation to ship a hedged guess.

The closing line is lifted almost verbatim from the problem statement. Use it.

---

## SLIDE 11 ⭐ — Compound Intelligence, Not Just Text Search

**On slide:**

> ### The app understands molecules as entities, not strings.
>
> **Entity resolution**
> `Tagrisso` · `AZD9291` · `osimertinib` → **CHEMBL3353410**
>
> **Compound Explorer shows:**
> - 2D structure rendered from SMILES
> - Formula, MW, XLogP, TPSA, H-bond donors/acceptors
> - **Lipinski Rule of Five** — pass/fail on each rule
> - Known targets with **measured IC50 / Ki values**, sorted by potency
> - Active clinical trials with phase and status
>
> *Without entity resolution, "What is Tagrisso?" returns nothing — the literature says "osimertinib."*

**Speaker notes:**
This is the 20-mark "domain-specific analysis" slide.

The synonym example is the most concrete way to show we're doing real biomedical work
rather than generic document search. Brand name, research code, and generic name are
three different strings for one molecule. A text-RAG system fails that question. Ours
normalises first, then retrieves.

---

## SLIDE 12 — Bonus: Drug–Target Interaction Prediction

**On slide:**

> ### A real ML model, presented honestly.
>
> - **Trained on** real ChEMBL bioactivity data (active = pChEMBL ≥ 6)
> - **Features:** RDKit ECFP4 molecular fingerprints (2048-bit)
> - **Model:** gradient-boosted trees, calibrated with isotonic regression
> - **Validated with a scaffold split** — not a random split
>
> Every prediction shown as:
> **⚠️ Predicted — not experimental** · with a calibrated probability · and the
> model's held-out AUC displayed next to it.

**Speaker notes:**
Two things a judge with an ML background will notice:

**Scaffold split.** Random splits leak chemical analogues between train and test, so
your AUC looks great and means nothing. Scaffold splitting separates by core
structure — a much harder, much more honest test. Say this out loud; it signals you
know what you're doing.

**Calibration.** The number shown is a real probability, not a raw model score.

And note the framing rule: predictions that just reproduce a known experimental
activity get marked as such, rather than dressed up as discoveries.

---

## SLIDE 13 — Responsible AI, In One Place

**On slide:**

> ### Four commitments, all enforced in code
>
> **1. Persistent disclaimer** — non-dismissible bar on every screen:
> *"Research tool. Grounded in public biomedical data. Not medical advice — do not
> use for diagnosis or treatment."*
>
> **2. Every claim traceable** — click any citation, see the actual source passage
>
> **3. Uncertainty visible** — confidence bands, and genuine abstention
>
> **4. Predictions never dressed as facts** — ML output always labelled and calibrated
>
> **Explicit non-goals:** not diagnostic, not treatment guidance, not general medical Q&A.

**Speaker notes:**
Fifteen marks live here. The phrase to use is "*enforced in code*" — these aren't
promises in a README, they're behaviours the system cannot skip. The disclaimer can't
be dismissed. The validator can't be bypassed. Abstention isn't optional.

---

## SLIDE 14 — Tech Stack

**On slide:**

> | Layer | Choice |
> |---|---|
> | **Frontend** | React 18 + Vite |
> | **Backend** | FastAPI (Python), SSE streaming |
> | **Database** | Postgres 16 + pgvector |
> | **Retrieval** | Hybrid BM25 (`tsvector`) + dense vectors, RRF fusion |
> | **Embeddings** | OpenAI `text-embedding-3-small` (1536-d) |
> | **Generation** | `gpt-5-nano`, temperature 0, strict JSON schema |
> | **Chemistry** | RDKit (fingerprints, descriptors) |
> | **ML** | scikit-learn (gradient boosting + isotonic calibration) |
>
> **Total cost to embed the entire corpus: ~$0.20**

**Speaker notes:**
Keep it brief unless asked. The cost line is a nice throwaway — grounding an entire
25,000-paper corpus costs twenty cents, so there's no excuse for not doing it
properly.

If asked why not a local embedding model: our deployment host runs 20+ production
services on 3.7GB of RAM. Loading PyTorch there risks OOM-killing a live client
system. We measured, then designed around it.

---

## SLIDE 15 — Engineering Discipline

**On slide:**

> ### Built to deploy safely onto a shared production host
>
> - Deployment target already runs **20+ live services on 3.7 GB RAM**
> - We measured the constraints **before** finalising the architecture
> - All heavy compute — embedding, fingerprints, model training — runs **offline on a
>   workstation**; the server receives a prebuilt database
> - Runtime footprint: **~150 MB RAM**
> - Isolated database container — zero contact with any existing service
> - Health checks on neighbouring production apps **before and after every deploy step**
> - Single-command rollback

**Speaker notes:**
Optional slide — include it if the judging rewards engineering maturity, cut it if
you're tight on time.

The point: we didn't design in a vacuum and hope it fit. We surveyed the host, found
it was nearly out of memory, and changed the architecture in response. That's also
*why* we use API embeddings rather than a local model — it's a constraint-driven
decision, not a shortcut.

---

## SLIDE 16 — Build Plan

**On slide:**

> | Phase | Deliverable | Exit gate |
> |---|---|---|
> | 0 | Scaffold + schema | Tables exist |
> | 1 | Ingest 4 data sources | Row counts match |
> | 2 | Embed + index | Vector search sane |
> | 3 | Entity resolver + hybrid retrieval | Fixed queries return correct PMIDs |
> | 4 | Claim contract + **validator** | Fabricated citations provably stripped |
> | 5 | API + streaming | Contract tests green |
> | 6 | Frontend, 3 surfaces | Walkthrough passes |
> | 7 | DTI model | Scaffold-split AUC reported |
> | 8 | Deploy | Neighbour health green |
> | 9 | Demo rehearsal | Full dry run |
>
> **Every phase has an exit gate. No phase starts until the last one is green.**

**Speaker notes:**
Shows this is a plan, not a wish. The gate on phase 4 is the interesting one —
"fabricated citations provably stripped" is a testable condition, and we test it by
deliberately feeding the system a fake citation.

---

## SLIDE 17 ⭐ — Live Demo Script

**On slide:**

> ### Four moments
>
> **1. Grounded answer**
> *"What resistance mechanisms are reported for osimertinib in EGFR-mutant NSCLC?"*
> → cited answer, evidence panel fills, click a citation, see the real passage
>
> **2. Compound intelligence**
> *Search "Tagrisso"* → resolves to osimertinib → structure, properties, Lipinski,
> measured targets, trials
>
> **3. The validator catching a fake citation**
> → show a fabricated source ID being stripped before it reaches the user
>
> **4. Honest refusal**
> *Ask something the corpus can't support* → system abstains, names the gap, still
> shows partial sources

**Speaker notes:**
Moment 4 is the one that wins. **Most teams will hide their system's failure cases.
We're going to demo ours on purpose** — because a system that knows what it doesn't
know is the whole point of the brief.

Rehearse all four. Have the exact queries saved. Know your fallback if the network
drops: retrieval and the Compound Explorer work fully offline, only prose generation
needs the API.

---

## SLIDE 18 — Close

**On slide:**

> ### OncoLens
>
> **Grounded** — every claim validated against real retrieved data
> **Domain-aware** — molecules as entities, structured facts as structured facts
> **Honest** — visible uncertainty, genuine abstention, no medical advice
>
> *Not a chatbot that talks about biomedicine.*
> *A retrieval system that happens to speak.*

**Speaker notes:**
End on the last two lines and stop. Don't trail off into thanks-for-listening. Let
the distinction sit, then take questions.

---

# Appendix — Likely Questions

**"Why not fine-tune a model on biomedical text?"**
Fine-tuning teaches style, not facts, and a fine-tuned model still can't tell you
where an answer came from. Retrieval gives us provenance, and provenance is the whole
requirement. It's also updatable — new papers just get ingested.

**"Why not DrugBank?"**
Bulk access requires a licence. ChEMBL is the open equivalent and carries the
bioactivity data we actually need for both lookup and the DTI model.

**"How do you know retrieval is actually good?"**
Phase 3's exit gate is a fixed set of queries with known-correct PMIDs. Hybrid
retrieval matters specifically for biomedical text because gene variants like `G12C`
are lexical tokens that pure vector search smears — BM25 catches those, vectors catch
paraphrase, RRF fuses both.

**"What if the LLM API goes down mid-demo?"**
Extractive fallback: retrieval still runs and returns cited source passages directly,
just without generated prose. The Compound Explorer is entirely unaffected — it's all
SQL and client-side rendering.

**"Isn't 25,000 abstracts small?"**
Deliberately. Quality of retrieval over 15 well-chosen targets beats coverage. The
ingest pipeline is parameterised — scaling to 250,000 is a config change and about
two dollars, not a rewrite.

**"Could this actually be used clinically?"**
No, and it's built to refuse that framing. It's a literature and compound triage tool
for researchers. The disclaimer isn't decoration — no patient-specific input is
accepted anywhere in the system.
