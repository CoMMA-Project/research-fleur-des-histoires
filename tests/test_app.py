from fastapi.testclient import TestClient
from backend.app import app
from backend.data import alignments, parse_folio

c = TestClient(app)


def test_counts():
    df = alignments()
    assert len(df) == 2262 and df.id.nunique() == 223 and df.qid.nunique() == 501


def test_folio():
    assert parse_folio("f608-295r.xml") == (608, "295r")


def test_shelfmark_and_life():
    r = c.get("/api/life/lives/text-0123-f0220-saint-jerome-lustful-monk-miracle.txt").json()
    assert r["sources"][0]["qid"] == "Q47786" and "Français" in r["sources"][0]["shelfmark"]


def test_graph_partition():
    for kind in ("lives", "mss", "bipartite"):
        g = c.get(f"/api/graph?kind={kind}&min_cover=0.2&min_hits=5").json()
        assert all(n["community"] >= 0 for n in g["nodes"])
        assert sum(x["size"] for x in g["communities"]) == len(g["nodes"])


def test_ignore_hubs():
    g = c.get("/api/graph?kind=bipartite&min_cover=0.05&min_hits=3&max_lives=30").json()
    assert g["ignored"] and all(h["n"] > 30 for h in g["ignored"])
    assert not {n["id"] for n in g["nodes"]} & {h["qid"] for h in g["ignored"]}


def test_ignore_hub_lives():
    g = c.get("/api/graph?kind=lives&min_cover=0&min_hits=1&max_mss=50").json()
    assert g["ignored_lives"] and all(h["n"] > 50 for h in g["ignored_lives"])
    assert not {n["id"] for n in g["nodes"]} & {h["id"] for h in g["ignored_lives"]}


def test_rank_and_exclude():
    r = c.get("/api/ms_rank?min_cover=0.05&min_hits=3").json()
    assert r[0]["rank"] == 1 and r[0]["n_lives"] >= r[-1]["n_lives"]
    top = r[0]["qid"]
    g = c.get(f"/api/graph?kind=bipartite&min_cover=0.05&min_hits=3&exclude={top}").json()
    assert top not in {n["id"] for n in g["nodes"]}


def test_chunks_and_pair():
    from backend import wits
    life = "lives/text-0123-f0220-saint-jerome-lustful-monk-miracle.txt"
    d = c.get(f"/api/chunks?life={life}&ms=Q47786").json()
    assert d["chunks"] and all(len(x["life"]) == len(x["wits"][0]["cells"]) for x in d["chunks"])
    assert all(0 <= w["ident"] <= 1 for x in d["chunks"] for w in x["wits"])
    p = c.get("/api/pair?a=Q50192&b=Q47786").json()
    assert isinstance(p["lives"], list)
    life_chars, cells = wits.project({"alg": "ab-c", "alg2": "a-xc"})
    assert life_chars == ["a", "x", "c"] and cells == [["", "a"], ["b", ""], ["", "c"]]


def test_dates():
    from backend.data import normalize_dates
    assert normalize_dates("1470", "1475")["date_label"] == "1470–1475 (s. XV)"
    assert normalize_dates(None, "1300")["date_from"] == 1300
    assert normalize_dates("1400", "1350")["date_from"] == 1350
    assert normalize_dates(None, None)["date_label"] is None


def test_date_filter():
    allm = c.get("/api/manuscripts").json()
    xv = c.get("/api/manuscripts?date_from=1401&date_to=1500&undated=false").json()
    assert 0 < len(xv) < len(allm)
    assert all(m["date_mid"] and 1350 <= m["date_mid"] <= 1550 for m in xv)
    g = c.get("/api/graph?kind=bipartite&min_cover=0.05&min_hits=3&date_from=1300&date_to=1399&undated=false").json()
    assert g["nodes"]


def test_min_hits_browse():
    a = c.get("/api/manuscripts").json()
    b = c.get("/api/manuscripts?min_hits=10").json()
    assert 0 < len(b) < len(a)
    life = "lives/text-0123-f0220-saint-jerome-lustful-monk-miracle.txt"
    s = c.get(f"/api/life/{life}?min_hits=50").json()["sources"]
    assert s and all(x["hits"] >= 50 for x in s)
    assert all(l["hits"] >= 10 for l in c.get("/api/manuscript/Q47786?min_hits=10").json()["lives"])
