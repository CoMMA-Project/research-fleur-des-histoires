"""Network construction and community detection."""
import networkx as nx
import numpy as np

from .data import alignments, by_date, life_title, ms_info


def filtered(min_cover, min_hits, exclude_mss=(), dates=(None, None, True)):
    df = by_date(alignments(), *dates)
    return df[(df.cover >= min_cover) & (df.hits >= min_hits) & ~df.qid.isin(exclude_mss)]


def build(kind, min_cover=0.2, min_hits=5, resolution=1.0, min_weight=0.0, exclude_mss=(), max_lives=0, max_mss=0, dates=(None, None, True)):
    df = filtered(min_cover, min_hits, exclude_mss, dates)
    hubs, hub_n = [], None
    life_hubs, life_n = [], None
    if max_lives:  # ignore hub manuscripts: more than max_lives lives above the thresholds
        hub_n = df.groupby("qid").id.nunique()
        hubs = list(hub_n[hub_n > max_lives].sort_values(ascending=False).index)
        df = df[~df.qid.isin(hubs)]
    if max_mss:  # ignore hub lives: aligned to more than max_mss manuscripts above the thresholds
        life_n = df.groupby("id").qid.nunique()
        life_hubs = list(life_n[life_n > max_mss].sort_values(ascending=False).index)
        df = df[~df.id.isin(life_hubs)]
    B = nx.Graph()
    for r in df.itertuples():
        B.add_node(r.id, kind="life", label=r.life_title)
        B.add_node(r.qid, kind="ms", label=ms_info(r.qid)["short"])
        B.add_edge(r.id, r.qid, weight=float(r.cover), hits=int(r.hits))
    lives = [n for n, d in B.nodes(data=True) if d["kind"] == "life"]
    mss = [n for n, d in B.nodes(data=True) if d["kind"] == "ms"]
    if kind == "bipartite":
        G = B
    else:
        side = lives if kind == "lives" else mss
        G = nx.Graph()
        for n in side:
            G.add_node(n, **B.nodes[n])
        # weighted Jaccard over shared neighbours (weights = cover)
        nbrs = {n: {m: B[n][m]["weight"] for m in B[n]} for n in side}
        shared = {}
        for other in (mss if kind == "lives" else lives):
            ns = list(B[other])
            for i, a in enumerate(ns):
                for b in ns[i + 1:]:
                    shared.setdefault((a, b), []).append(other)
        for (a, b), common in shared.items():
            keys = set(nbrs[a]) | set(nbrs[b])
            num = sum(min(nbrs[a].get(k, 0), nbrs[b].get(k, 0)) for k in keys)
            den = sum(max(nbrs[a].get(k, 0), nbrs[b].get(k, 0)) for k in keys)
            w = num / den if den else 0
            if w > min_weight:
                G.add_edge(a, b, weight=w, shared=[ms_info(c)["short"] if kind == "lives" else c for c in common][:8])
    comms = nx.community.louvain_communities(G, weight="weight", resolution=resolution, seed=1) if G.number_of_nodes() else []
    comms = sorted(comms, key=len, reverse=True)
    cid = {n: i for i, c in enumerate(comms) for n in c}
    deg = dict(G.degree(weight="weight"))
    nodes = [{"id": n, "label": d.get("label", n), "kind": d.get("kind"), "community": cid.get(n, -1),
              "degree": round(deg.get(n, 0), 3)} for n, d in G.nodes(data=True)]
    edges = [{"source": a, "target": b, "weight": round(d["weight"], 3), **({"shared": d["shared"]} if "shared" in d else {})}
             for a, b, d in G.edges(data=True)]
    summary = []
    for i, c in enumerate(comms):
        members = [n for n in c]
        top = sorted(members, key=lambda n: -deg.get(n, 0))[:5]
        summary.append({"id": i, "size": len(c), "top": [G.nodes[n].get("label", n) for n in top],
                        "members": members})
    return {"nodes": nodes, "edges": edges, "communities": summary,
            "ignored": [{"qid": q, "shelfmark": ms_info(q)["short"], "n": int(hub_n[q])} for q in hubs],
            "ignored_lives": [{"id": i, "title": life_title(i), "n": int(life_n[i])} for i in life_hubs]}
