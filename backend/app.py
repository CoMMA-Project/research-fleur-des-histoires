from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import network, wits
from .data import alignments, by_date, ms_info

app = FastAPI(title="Lives network browser")
FRONT = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/lives")
def lives(q: str = "", min_hits: int = 0, date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    df = by_date(alignments(), date_from, date_to, undated)
    df = df[df.hits >= min_hits]
    g = df.groupby(["id", "life_title"]).agg(nlines=("nlines", "first"), n_mss=("qid", "nunique"),
                                              best_cover=("cover", "max")).reset_index()
    if q:
        g = g[g.life_title.str.contains(q, case=False)]
    return g.sort_values("id").to_dict("records")


@app.get("/api/manuscripts")
def manuscripts(q: str = "", min_cover: float = 0.0, min_hits: int = 0, date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    df = by_date(alignments(), date_from, date_to, undated)
    df = df[(df.cover >= min_cover) & (df.hits >= min_hits)]
    g = df.groupby("qid").agg(n_lives=("id", "nunique"), best_cover=("cover", "max"), hits=("hits", "sum")).reset_index()
    rows = []
    for r in g.to_dict("records"):
        info = ms_info(r["qid"])
        rows.append({**r, "shelfmark": info["short"], "label": info["label"], "page": info["page"],
                     "date_label": info["date_label"], "date_mid": info["date_mid"], "century": info["century"]})
    if q:
        rows = [r for r in rows if q.lower() in (r["label"] + r["qid"]).lower()]
    return sorted(rows, key=lambda r: r["shelfmark"])


@app.get("/api/life/{lid:path}")
def life(lid: str, min_cover: float = 0.0, min_hits: int = 0, date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    df = alignments()
    d = by_date(df[df.id == lid], date_from, date_to, undated)
    d = d[(d.cover >= min_cover) & (d.hits >= min_hits)].sort_values(["cover", "hits"], ascending=False)
    if d.empty and not (df.id == lid).any():
        raise HTTPException(404)
    out = []
    for r in d.itertuples():
        info = ms_info(r.qid)
        out.append(dict(qid=r.qid, shelfmark=info["short"], label=info["label"], page=info["page"],
                        date_label=info["date_label"], date_mid=info["date_mid"],
                        hits=r.hits, cover=r.cover, minp=r.minp, maxp=r.maxp, span=int(r.span),
                        density=round(r.density, 3), iiif=info.get("iiif", [])[:1],
                        likely=bool(r.cover >= 0.2 and r.density >= 0.2)))
    return {"id": lid, "title": df[df.id == lid].life_title.iloc[0], "sources": out}


@app.get("/api/manuscript/{qid}")
def manuscript(qid: str, min_cover: float = 0.0, min_hits: int = 0):
    df = alignments()
    d = df[(df.qid == qid) & (df.cover >= min_cover) & (df.hits >= min_hits)].sort_values("min_idx")
    if not (df.qid == qid).any():
        raise HTTPException(404)
    return {**ms_info(qid), "lives": [dict(id=r.id, title=r.life_title, hits=r.hits, cover=r.cover,
                                           minp=r.minp, maxp=r.maxp, span=int(r.span)) for r in d.itertuples()]}


@app.get("/api/graph")
def graph(kind: str = Query("lives", pattern="^(lives|mss|bipartite)$"), min_cover: float = 0.2,
          min_hits: int = 5, resolution: float = 1.0, min_weight: float = 0.0, max_lives: int = 0, max_mss: int = 0, exclude: str = "", date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    return network.build(kind, min_cover, min_hits, resolution, min_weight, max_lives=max_lives, max_mss=max_mss,
                         exclude_mss=[x for x in exclude.split(",") if x], dates=(date_from, date_to, undated))


@app.get("/api/ms_rank")
def ms_rank(min_cover: float = 0.2, min_hits: int = 5, date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    """Manuscripts ranked by number of lives above the thresholds (then total hits)."""
    d = network.filtered(min_cover, min_hits, dates=(date_from, date_to, undated))
    g = d.groupby("qid").agg(n_lives=("id", "nunique"), hits=("hits", "sum"), best_cover=("cover", "max")).reset_index()
    g = g.sort_values(["n_lives", "hits"], ascending=False)
    return [{**r, "rank": i + 1, "shelfmark": ms_info(r["qid"])["short"], "date_label": ms_info(r["qid"])["date_label"]}
            for i, r in enumerate(g.to_dict("records"))]


@app.get("/api/chunks")
def chunks(life: str, ms: str = "", require_all: bool = False, min_ident: float = 0.0, offset: int = 0, date_from: int | None = None, date_to: int | None = None, undated: bool = True):
    """Aligned passages of a life against the chosen manuscripts (all witnesses if ms is empty)."""
    return wits.chunks(life, [m for m in ms.split(",") if m], require_all, min_ident, offset, dates=(date_from, date_to, undated))


@app.get("/api/pair")
def pair(a: str, b: str):
    """Lives where manuscripts a and b are both aligned, with agreement statistics."""
    return {"a": ms_info(a)["short"], "b": ms_info(b)["short"], "lives": wits.pair(a, b)}


@app.get("/api/date_range")
def date_range():
    """Overall range of manuscript dates, and how many manuscripts per century (for the filter bar)."""
    from collections import Counter
    from .data import dates
    d = [v for v in dates().values() if v["date_from"]]
    return {"min": min(v["date_from"] for v in d), "max": max(v["date_to"] for v in d),
            "centuries": sorted(Counter(v["century"] for v in d).items()), "undated": len(dates()) - len(d)}


@app.get("/api/cover_hist")
def cover_hist():
    import numpy as np
    h, edges = np.histogram(alignments().cover, bins=20, range=(0, 1))
    return {"counts": h.tolist(), "edges": edges.tolist()}


@app.get("/")
def index():
    return FileResponse(FRONT / "index.html")


app.mount("/static", StaticFiles(directory=FRONT), name="static")
