"""Train the drug-target interaction model.

Honest by construction:
  * real ChEMBL bioactivity as labels (active = pChEMBL >= 6, i.e. <= 1 uM)
  * ECFP4 Morgan fingerprints, computed here and stored, so the server never
    needs RDKit at runtime
  * SCAFFOLD split, not random. Random splits leak close analogues between
    train and test and inflate AUC into meaninglessness.
  * isotonic calibration, so the probability shown in the UI is a real
    probability rather than a raw model score
"""
from __future__ import annotations

import pickle
from collections import defaultdict

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from common import connect, log

RDLogger.DisableLog("rdApp.*")

MODEL_VERSION = "dti-v1"
N_BITS = 2048
RADIUS = 2
ACTIVE_PCHEMBL = 6.0
MIN_ACTIVES = 25          # a target with fewer actives cannot be modelled honestly

_gen = rdFingerprintGenerator.GetMorganGenerator(radius=RADIUS, fpSize=N_BITS)


def fingerprint(smiles: str):
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return None
    return np.array(_gen.GetFingerprintAsNumPy(mol), dtype=np.uint8)


def scaffold(smiles: str) -> str:
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(smiles=smiles, includeChirality=False)
    except Exception:
        return ""


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT chembl_id, smiles FROM compounds WHERE smiles IS NOT NULL")
        compounds = cur.fetchall()
        cur.execute(
            """SELECT compound_id, target_id, max(pchembl_value) AS p
               FROM activities WHERE pchembl_value IS NOT NULL
               GROUP BY compound_id, target_id""")
        acts = cur.fetchall()
        cur.execute("SELECT chembl_id, gene_symbol FROM targets")
        targets = dict(cur.fetchall())

    log("dti", f"{len(compounds)} compounds, {len(acts)} measured pairs")

    # ---- fingerprints ----
    fps, smis = {}, {}
    for cid, smi in compounds:
        fp = fingerprint(smi)
        if fp is not None:
            fps[cid] = fp
            smis[cid] = smi
    log("dti", f"{len(fps)} fingerprints computed")

    # persist fingerprints so the API never needs RDKit
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "UPDATE compounds SET fingerprint = %s WHERE chembl_id = %s",
            [(np.packbits(fp).tobytes(), cid) for cid, fp in fps.items()])
        conn.commit()
    log("dti", "fingerprints stored")

    # ---- scaffold groups ----
    scaf = {cid: scaffold(s) for cid, s in smis.items()}
    groups = defaultdict(list)
    for cid, sc in scaf.items():
        groups[sc].append(cid)
    # deterministic split: biggest scaffold families to train
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    train_ids, test_ids = set(), set()
    for i, (_, members) in enumerate(ordered):
        (test_ids if i % 5 == 4 else train_ids).update(members)
    log("dti", f"scaffold split — train {len(train_ids)}, test {len(test_ids)}, "
               f"{len(groups)} scaffold families")

    by_target = defaultdict(dict)
    for cid, tid, p in acts:
        by_target[tid][cid] = float(p)

    rng = np.random.default_rng(20260822)
    models, metrics, all_preds = {}, [], []

    for tid, measured in by_target.items():
        gene = targets.get(tid, tid)
        actives = {c for c, p in measured.items() if p >= ACTIVE_PCHEMBL and c in fps}
        inactives = {c for c, p in measured.items() if p < ACTIVE_PCHEMBL and c in fps}
        if len(actives) < MIN_ACTIVES:
            log("dti", f"{gene:7s} skipped ({len(actives)} actives < {MIN_ACTIVES})")
            continue

        # decoys: compounds measured against OTHER targets but never this one
        unmeasured = [c for c in fps if c not in measured]
        n_decoy = min(len(unmeasured), max(0, len(actives) * 2 - len(inactives)))
        decoys = set(rng.choice(unmeasured, size=n_decoy, replace=False)) if n_decoy else set()
        negatives = inactives | decoys

        def split(ids):
            tr = [c for c in ids if c in train_ids]
            te = [c for c in ids if c in test_ids]
            return tr, te

        pa, ta = split(actives)
        pn, tn = split(negatives)
        if len(pa) < 10 or len(ta) < 3 or len(pn) < 10 or len(tn) < 3:
            log("dti", f"{gene:7s} skipped (split too small)")
            continue

        Xtr = np.array([fps[c] for c in pa + pn], dtype=np.float32)
        ytr = np.array([1] * len(pa) + [0] * len(pn))
        Xte = np.array([fps[c] for c in ta + tn], dtype=np.float32)
        yte = np.array([1] * len(ta) + [0] * len(tn))

        base = HistGradientBoostingClassifier(
            max_iter=180, learning_rate=0.1, max_depth=7,
            min_samples_leaf=8, l2_regularization=1.0, random_state=42)
        clf = CalibratedClassifierCV(base, method="isotonic", cv=3)
        clf.fit(Xtr, ytr)

        prob = clf.predict_proba(Xte)[:, 1]
        try:
            roc = float(roc_auc_score(yte, prob))
            pr = float(average_precision_score(yte, prob))
        except ValueError:
            continue

        models[tid] = clf
        metrics.append({"target_id": tid, "model_version": MODEL_VERSION,
                        "roc_auc": roc, "pr_auc": pr,
                        "n_train": len(ytr), "n_test": len(yte), "split": "scaffold"})
        log("dti", f"{gene:7s} ROC-AUC {roc:.3f}  PR-AUC {pr:.3f}  "
                   f"(train {len(ytr)}, test {len(yte)})")

        # score every compound against this target
        cand = sorted(fps.keys())
        Xall = np.array([fps[c] for c in cand], dtype=np.float32)
        probs = clf.predict_proba(Xall)[:, 1]
        for cid, p in zip(cand, probs):
            if p >= 0.55:
                all_preds.append({
                    "compound_id": cid, "target_id": tid, "probability": float(p),
                    "is_known": cid in measured, "model_version": MODEL_VERSION,
                })

    if not models:
        log("dti", "no target had enough data to train — nothing written")
        return

    with connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dti_predictions WHERE model_version = %s", (MODEL_VERSION,))
        cur.execute("DELETE FROM dti_metrics     WHERE model_version = %s", (MODEL_VERSION,))
        cur.executemany(
            """INSERT INTO dti_metrics (target_id,model_version,roc_auc,pr_auc,n_train,n_test,split)
               VALUES (%(target_id)s,%(model_version)s,%(roc_auc)s,%(pr_auc)s,
                       %(n_train)s,%(n_test)s,%(split)s)""", metrics)
        for i in range(0, len(all_preds), 1000):
            cur.executemany(
                """INSERT INTO dti_predictions (compound_id,target_id,probability,is_known,model_version)
                   VALUES (%(compound_id)s,%(target_id)s,%(probability)s,%(is_known)s,%(model_version)s)
                   ON CONFLICT DO NOTHING""", all_preds[i:i + 1000])
        conn.commit()

    with open("../models/dti_model.pkl", "wb") as f:
        pickle.dump({"version": MODEL_VERSION, "models": models,
                     "n_bits": N_BITS, "radius": RADIUS}, f)

    mean_roc = sum(m["roc_auc"] for m in metrics) / len(metrics)
    log("dti", f"DONE — {len(models)} targets, {len(all_preds)} predictions, "
               f"mean scaffold-split ROC-AUC {mean_roc:.3f}")


if __name__ == "__main__":
    main()
