# OncoLens — Project Status

**As of 2026-08-22.** Built, deployed, and serving live data.

| | |
|---|---|
| Live | https://oncolens.avlokai.com · http://203.57.85.191:8891 |
| Repo | `git@github.com:Linuxboii/SPIH062.git` — branch `main` |
| Health | https://oncolens.avlokai.com/api/health |

---

## What is done

All ten build phases from the PRD are complete.

| Phase | Status | Evidence |
|---|---|---|
| 0 Scaffold | done | pgvector container, 10 tables, indexes |
| 1 Ingest | done | 4 sources, counts below |
| 2 Embed | done | 26,975 chunks, HNSW cosine index |
| 3 Retrieval | done | entity resolver + hybrid BM25/vector + RRF |
| 4 Generation | done | claim contract + citation validator + confidence |
| 5 API | done | 8 endpoints, all responding |
| 6 Frontend | done | 3 surfaces, live data |
| 7 DTI | done | 15 targets, scaffold split |
| 8 Deploy | done | VPS, domain, TLS via Cloudflare edge |
| 9 Demo prep | partial | queries verified; see *Known gaps* |

## Corpus (live counts)

| | |
|---|---|
| PubMed abstracts | 10,812 |
| Embedded chunks | 26,975 |
| Compounds | 12,111 (66 approved) |
| Measured activities | 20,201 |
| Clinical trials | 5,910 (6,321 compound links) |
| Synonyms | 1,523 |
| DTI predictions | 10,905 |
| Targets | 15 |

**DTI model** — ECFP4 fingerprints, gradient-boosted trees, isotonic calibration,
**scaffold split**. Mean held-out ROC-AUC **0.952**, range 0.823 (ROS1) – 0.993.

## Verified behaviour

- *"What resistance mechanisms are reported for osimertinib in EGFR-mutant NSCLC?"* →
  10 citations offered, 10 verified, ~9 s, top sources are papers titled exactly that.
- *"What is Tagrisso?"* → resolves to CHEMBL3353410 (Osimertinib), 4 grounded claims.
- *"What is the recommended insulin dose for type 2 diabetes?"* → abstains, confidence
  0.39, names the gap.
- **Validator catches real fabrications**: observed 8 offered / 7 verified / 1 rejected
  on a live query — a PMID retrieval never returned.
- Osimertinib compound page shows real EGFR IC₅₀ 0.02 nM (pChEMBL 10.7) from ChEMBL.

---

## Deployment map

| Component | Location | Port |
|---|---|---|
| Frontend (static) | `/var/www/oncolens` | via nginx 8891 |
| nginx vhost | `/etc/nginx/sites-available/oncolens` | 8891 |
| API | systemd `oncolens-api`, `/opt/oncolens` | 127.0.0.1:8892 |
| Database | Docker `oncolens-pg` (pgvector:pg16) | 127.0.0.1:5434 |
| Tunnel | `cloudflared-oncolens.service` | tunnel `6238d2e7-…` |
| Source on VPS | `/opt/oncolens` (a real git clone) | — |

The API runs under `MemoryMax=400M`. Actual footprint ~82 MB — no PyTorch, no RDKit on
the server; fingerprints and the trained model are precomputed locally and shipped.

### Rebuild / redeploy

```bash
# frontend
cd frontend && npm run build
tar czf /tmp/d.tgz -C dist . && scp /tmp/d.tgz root@203.57.85.191:/tmp/
ssh root@203.57.85.191 'rm -rf /var/www/oncolens/* && tar xzf /tmp/d.tgz -C /var/www/oncolens'

# backend
tar czf /tmp/b.tgz backend && scp /tmp/b.tgz root@203.57.85.191:/tmp/
ssh root@203.57.85.191 'cd /opt/oncolens && tar xzf /tmp/b.tgz && systemctl restart oncolens-api'
```

### Teardown

```bash
systemctl disable --now oncolens-api cloudflared-oncolens
docker rm -f oncolens-pg
rm -f /etc/nginx/sites-enabled/oncolens && systemctl reload nginx
```

Nothing OncoLens installs is shared with another service, so teardown cannot affect
anything else on the host.

---

## Constraints this project runs under

The host runs 20+ services on 3.7 GB RAM, including **Venkateswara Polymers**, a live
production ERP. See PRD §9.2 for the full protection rules. In short: never touch
`/etc/cloudflared/config.yml` (shared by four hostnames including `vp-api`), never use
host Postgres on 5432, never bind port 3000, and health-check VP before and after any
server-side change.

## Gotchas discovered during the build

- **`cloudflared tunnel route dns` silently prefers the default tunnel** declared in
  `/root/.cloudflared/config.yml` over the one you name. Always pass `--config <app.yml>`
  and `--overwrite-dns`, then verify the tunnel id in the output.
- **Pushing from this workstation fails.** `~/.ssh/id_ed25519` is passphrase-protected
  with no agent running. Push from the VPS via `git bundle` — its key authenticates as
  `Linuxboii`.
- **Dump from inside the PG16 container.** The workstation's `pg_dump` is newer and
  produces archives `pg_restore` 16 rejects.
- **Workstation Python is 3.14**, ahead of numpy/RDKit wheels — use the `uv`-managed
  3.12 venv at `.venv`.
- **podman's 64 MB `/dev/shm`** breaks parallel HNSW builds; set
  `max_parallel_maintenance_workers = 0`.
- **gpt-5-nano shares its token budget between reasoning and output** — it returns
  empty content unless `reasoning_effort=low` and `max_completion_tokens` is generous.

---

## Known gaps

1. **Single uvicorn worker.** Fine for a demo, not for concurrent load.
2. **Five biologics have no structure.** trastuzumab, pertuzumab, atezolizumab,
   pembrolizumab, nivolumab and similar are antibodies with no SMILES in ChEMBL, so
   their compound pages render no diagram. Correct, but looks empty.
3. **Rejected-citation panel only appears when the model actually fabricates** —
   roughly one query in three. A "show validator internals" toggle would make the check
   visible on clean answers too. Not built.
4. **No streaming.** `/api/chat` returns a complete response; the PRD specified SSE.
   Answers take 8–15 s with no token-level feedback, only a pending indicator.
5. **Demo slide 12 needs the real AUC numbers** filled in from this document.

## Next steps, in priority order

1. Fill the real metrics into `docs/DECK_CONTEXT.md` slide 12.
2. Rehearse the four demo moments in PRD §17.
3. Optional: validator-internals toggle (gap 3) — most valuable for the live demo.
4. Optional: SSE streaming (gap 4) — biggest perceived-speed win.
