"""Text alignments (wits.json.gz).

Each row is a chunk of a life: `begin` (char offset in the life), `llen`, and for every manuscript
witness a pairwise alignment: `alg` = manuscript reading, `alg2` = life text, same length, '-' = gap.
"""
import gzip
import json
from collections import defaultdict
from functools import lru_cache

from .data import ROOT, date_ok, life_title, ms_info, parse_folio


@lru_cache
def _load():
    rows = [json.loads(l) for l in gzip.open(ROOT / "wits.json.gz", "rt")]
    by_life, by_ms = defaultdict(list), defaultdict(set)
    for i, r in enumerate(rows):
        by_life[r["id"]].append(i)
        for w in r["wits"]:
            w["qid"] = w["book"].rsplit("/", 1)[1]
            by_ms[w["qid"]].add(i)
    for v in by_life.values():
        v.sort(key=lambda i: rows[i]["begin"])
    return rows, by_life, by_ms


def _vis(s):
    return s.replace("\n", "↵")


def project(w):
    """Project a pairwise alignment on the life's coordinates.
    Returns (life_chars, cells); cell = [insertion_before, reading] ('' reading = deletion)."""
    life, cells, ins = [], [], ""
    for a, l in zip(_vis(w["alg"]), _vis(w["alg2"])):
        if l == "-":
            if a != "-":
                ins += a
        else:
            life.append(l)
            cells.append([ins, "" if a == "-" else a])
            ins = ""
    if ins:
        life.append("")
        cells.append([ins, ""])
    return life, cells


def identity(life, cells):
    n = sum(1 for l in life if l)
    m = sum(1 for l, c in zip(life, cells) if l and not c[0] and c[1].lower() == l.lower())
    return round(m / n, 3) if n else 0.0


def chunks(life_id, qids=(), require_all=False, min_ident=0.0, offset=0, limit=100, dates=(None, None, True)):
    rows, by_life, _ = _load()
    out = []
    for i in by_life.get(life_id, []):
        r = rows[i]
        ws = [w for w in r["wits"] if (w["qid"] in qids if qids else date_ok(w["qid"], *dates))]
        if not ws or (require_all and qids and {w["qid"] for w in ws} != set(qids)):
            continue
        life, wl = None, []
        for w in ws:
            life, cells = project(w)
            ident = identity(life, cells)
            if ident < min_ident:
                continue
            idx, lab = parse_folio(w["page"])
            wl.append({"qid": w["qid"], "shelfmark": ms_info(w["qid"])["short"], "folio": lab,
                       "begin": w["begin"], "ident": ident, "cells": cells})
        if wl and (not require_all or len(wl) == len(qids)):
            out.append({"begin": r["begin"], "llen": r["llen"], "life": life, "wits": wl})
    return {"id": life_id, "title": life_title(life_id), "n_total": len(by_life.get(life_id, [])),
            "n_match": len(out), "offset": offset, "chunks": out[offset:offset + limit]}


def pair(a, b):
    """Lives/passages shared by two manuscripts, with agreement statistics."""
    rows, _, by_ms = _load()
    per = defaultdict(lambda: dict(n=0, ia=0.0, ib=0.0, both_var=0, shared_var=0, agree=0, pos=0))
    for i in by_ms.get(a, set()) & by_ms.get(b, set()):
        r = rows[i]
        wa = next(w for w in r["wits"] if w["qid"] == a)
        wb = next(w for w in r["wits"] if w["qid"] == b)
        la, ca = project(wa)
        _, cb = project(wb)
        if len(ca) != len(cb):
            continue
        p = per[r["id"]]
        p["n"] += 1
        p["ia"] += identity(la, ca)
        p["ib"] += identity(la, cb)
        for l, x, y in zip(la, ca, cb):
            if not l:
                continue
            p["pos"] += 1
            p["agree"] += x == y
            if x[1].lower() != l.lower() and y[1].lower() != l.lower():
                p["both_var"] += 1
                p["shared_var"] += x == y
    res = [{"id": k, "title": life_title(k), "chunks": v["n"], "ident_a": round(v["ia"] / v["n"], 3),
            "ident_b": round(v["ib"] / v["n"], 3), "agreement": round(v["agree"] / v["pos"], 3) if v["pos"] else None,
            "shared_variants": v["shared_var"], "both_differ": v["both_var"]} for k, v in per.items() if v["n"]]
    return sorted(res, key=lambda r: -r["chunks"])
