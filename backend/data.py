"""Load mss.json (lives <-> manuscripts alignments) and Biblissima metadata."""
import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LIFE_RE = re.compile(r"lives/text-(\d+)-f(\d+)-(.+)\.txt$")
FOLIO_RE = re.compile(r"f(\d+)-(.+)\.xml$")


def parse_folio(s):
    m = FOLIO_RE.match(s)
    return (int(m[1]), m[2]) if m else (None, s)


def life_title(lid):
    m = LIFE_RE.search(lid)
    return m[3].replace("-", " ") if m else lid


@lru_cache
def manuscripts():
    p = ROOT / "cache" / "manuscripts.json"
    return json.load(open(p)) if p.exists() else {}


@lru_cache
def alignments() -> pd.DataFrame:
    df = pd.read_json(ROOT / "mss.json", lines=True)
    df["qid"] = df["book"].str.rsplit("/", n=1).str[-1]
    df["life_title"] = df["id"].map(life_title)
    df[["min_idx", "min_label"]] = df["minp"].apply(lambda s: pd.Series(parse_folio(s)))
    df[["max_idx", "max_label"]] = df["maxp"].apply(lambda s: pd.Series(parse_folio(s)))
    # folio-index span (+1): small span relative to hits = contiguous alignment
    df["span"] = (df["max_idx"] - df["min_idx"]).abs() + 1
    df["density"] = df["hits"] / df["span"]
    ms = manuscripts()
    df["shelfmark"] = df["qid"].map(lambda q: ms.get(q, {}).get("short") or q)
    return df


ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII"]


def normalize_dates(start, stop):
    """Biblissima start_year/stop_year (strings, possibly missing) -> normalized date fields.
    date_from <= date_to (ints), date_mid, century (1-based int) and a readable label."""
    def num(v):
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return None
    a, b = num(start), num(stop)
    if a is None and b is None:
        return {"date_from": None, "date_to": None, "date_mid": None, "century": None, "date_label": None}
    a, b = (a if a is not None else b), (b if b is not None else a)
    a, b = min(a, b), max(a, b)
    mid = (a + b) // 2
    cent = (mid - 1) // 100 + 1
    rom = ROMAN[cent] if 0 < cent < len(ROMAN) else str(cent)
    label = f"{a}" if a == b else f"{a}–{b}"
    return {"date_from": a, "date_to": b, "date_mid": mid, "century": cent,
            "date_label": f"{label} (s. {rom})"}


@lru_cache
def dates():
    p = ROOT / "cache" / "dates.json"
    raw = json.load(open(p)) if p.exists() else {}
    return {q: normalize_dates(v.get("start_year"), v.get("stop_year")) for q, v in raw.items()}


NO_DATE = normalize_dates(None, None)


def ms_info(qid):
    base = manuscripts().get(qid, {"qid": qid, "label": qid, "short": qid, "shelfmark": None,
                                   "page": f"https://data.biblissima.fr/w/Item:{qid}"})
    return {**base, **dates().get(qid, NO_DATE)}


def date_ok(qid, lo=None, hi=None, undated=True):
    """Does the manuscript's date range overlap [lo, hi]? Undated manuscripts follow `undated`."""
    d = dates().get(qid, NO_DATE)
    if d["date_from"] is None:
        return undated
    return (hi is None or d["date_from"] <= hi) and (lo is None or d["date_to"] >= lo)


def by_date(df, lo=None, hi=None, undated=True):
    """Restrict an alignments frame to manuscripts overlapping the date window."""
    if lo is None and hi is None and undated:
        return df
    ok = {q: date_ok(q, lo, hi, undated) for q in df.qid.unique()}
    return df[df.qid.map(ok)]
