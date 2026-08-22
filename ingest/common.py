"""Shared ingest helpers: DB connection, HTTP client, target list."""
from __future__ import annotations

import os
import pathlib

import httpx
import psycopg
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# Fall back to the key already on this workstation.
load_dotenv(pathlib.Path.home() / "langchain" / ".env", override=False)

DSN = os.environ.get(
    "DATABASE_URL", "postgresql://oncolens:oncolens@localhost:5434/oncolens"
).replace("postgresql+psycopg://", "postgresql://")

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# The 15 oncology targets the corpus is scoped to. `chembl` is the ChEMBL target
# id; `queries` drive the PubMed searches.
TARGETS = [
    {"gene": "EGFR",   "chembl": "CHEMBL203",     "name": "Epidermal growth factor receptor erbB1",
     "queries": ["EGFR inhibitor non-small cell lung cancer", "EGFR T790M resistance osimertinib"]},
    {"gene": "ALK",    "chembl": "CHEMBL4247",    "name": "Anaplastic lymphoma kinase",
     "queries": ["ALK rearrangement lung cancer inhibitor", "ALK resistance mutation crizotinib"]},
    {"gene": "BRAF",   "chembl": "CHEMBL5145",    "name": "Serine/threonine-protein kinase B-raf",
     "queries": ["BRAF V600E melanoma inhibitor", "BRAF inhibitor resistance mechanism"]},
    {"gene": "KRAS",   "chembl": "CHEMBL2189121", "name": "GTPase KRas",
     "queries": ["KRAS G12C inhibitor sotorasib", "KRAS mutant cancer targeted therapy"]},
    {"gene": "ERBB2",  "chembl": "CHEMBL1824",    "name": "Receptor protein-tyrosine kinase erbB-2",
     "queries": ["HER2 positive breast cancer trastuzumab", "ERBB2 amplification targeted therapy"]},
    {"gene": "CD274",  "chembl": "CHEMBL3580522", "name": "Programmed cell death 1 ligand 1",
     "queries": ["PD-L1 immune checkpoint inhibitor cancer", "PD-L1 expression biomarker response"]},
    {"gene": "KDR",    "chembl": "CHEMBL279",     "name": "Vascular endothelial growth factor receptor 2",
     "queries": ["VEGFR2 inhibitor angiogenesis tumor", "VEGFR2 antiangiogenic therapy resistance"]},
    {"gene": "CDK4",   "chembl": "CHEMBL331",     "name": "Cyclin-dependent kinase 4",
     "queries": ["CDK4/6 inhibitor palbociclib breast cancer"]},
    {"gene": "CDK6",   "chembl": "CHEMBL3974",    "name": "Cyclin-dependent kinase 6",
     "queries": ["CDK6 inhibitor cell cycle cancer therapy"]},
    {"gene": "PARP1",  "chembl": "CHEMBL3105",    "name": "Poly [ADP-ribose] polymerase-1",
     "queries": ["PARP inhibitor olaparib ovarian cancer", "PARP inhibitor resistance BRCA"]},
    {"gene": "ABL1",   "chembl": "CHEMBL1862",    "name": "Tyrosine-protein kinase ABL",
     "queries": ["BCR-ABL imatinib chronic myeloid leukemia", "ABL kinase domain mutation resistance"]},
    {"gene": "ROS1",   "chembl": "CHEMBL5568",    "name": "Proto-oncogene tyrosine-protein kinase ROS",
     "queries": ["ROS1 fusion lung cancer inhibitor"]},
    {"gene": "BTK",    "chembl": "CHEMBL5251",    "name": "Tyrosine-protein kinase BTK",
     "queries": ["BTK inhibitor ibrutinib lymphoma", "BTK C481S resistance mutation"]},
    {"gene": "MAP2K1", "chembl": "CHEMBL3587",    "name": "Dual specificity mitogen-activated protein kinase kinase 1",
     "queries": ["MEK inhibitor trametinib combination therapy"]},
    {"gene": "MTOR",   "chembl": "CHEMBL2842",    "name": "Serine/threonine-protein kinase mTOR",
     "queries": ["mTOR inhibitor everolimus cancer", "PI3K mTOR pathway inhibitor resistance"]},
]

TARGET_BY_CHEMBL = {t["chembl"]: t for t in TARGETS}


def connect():
    return psycopg.connect(DSN, autocommit=False)


def client(timeout: float = 60.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": "OncoLens/1.0 (research prototype; contact sushanth@avlokai.com)"},
        follow_redirects=True,
    )


def log(stage: str, msg: str) -> None:
    print(f"[{stage}] {msg}", flush=True)
