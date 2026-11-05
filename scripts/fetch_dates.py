"""Fetch manuscript dates from the Biblissima portal (CubicWeb `ejsonexport` view).

Biblissima Wikibase items carry the portal ARK in P129; the portal exposes start_year / stop_year.
Usage: .venv/bin/python scripts/fetch_dates.py     -> cache/dates.json (resumable)
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cache" / "dates.json"
UA = {"User-Agent": "DH2027-lives-browser/0.1"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def arks(qids):
    out = {}
    for i in range(0, len(qids), 50):
        q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                                    "props": "claims", "format": "json"})
        for k, e in get("https://data.biblissima.fr/w/api.php?" + q)["entities"].items():
            v = [c["mainsnak"]["datavalue"]["value"] for c in e.get("claims", {}).get("P129", [])]
            out[k] = v[0] if v else None
        time.sleep(0.5)
    return out


def main():
    qids = sorted({json.loads(l)["book"].rsplit("/", 1)[1] for l in open(ROOT / "mss.json")})
    cache = json.load(open(OUT)) if OUT.exists() else {}
    todo = [q for q in qids if q not in cache]
    ids = arks(todo)
    for n, q in enumerate(todo, 1):
        rec = {"portal_id": ids.get(q), "start_year": None, "stop_year": None}
        if rec["portal_id"]:
            try:
                d = get(f"https://portail.biblissima.fr/ark:/43093/{rec['portal_id']}?vid=ejsonexport")
                m = next((x for x in d if x.get("cw_etype") == "Manuscript"), {})
                rec["start_year"], rec["stop_year"] = m.get("start_year"), m.get("stop_year")
            except Exception as e:  # keep going; rerun to retry
                rec["error"] = str(e)
                time.sleep(2)
        cache[q] = rec
        if n % 25 == 0:
            OUT.write_text(json.dumps(cache, indent=1))
            print(n, "/", len(todo), flush=True)
        time.sleep(0.3)
    OUT.write_text(json.dumps(cache, indent=1))
    ok = sum(1 for v in cache.values() if v["start_year"])
    print(f"{len(cache)} manuscripts; with dates: {ok}; errors: {sum('error' in v for v in cache.values())}")


if __name__ == "__main__":
    main()
