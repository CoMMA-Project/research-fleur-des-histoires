"""Fetch shelfmarks/labels for every manuscript in mss.json from Biblissima's Wikibase.

Usage: .venv/bin/python scripts/fetch_labels.py
Writes cache/manuscripts.json (qid -> metadata).
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://data.biblissima.fr/w/api.php"
OUT = ROOT / "cache" / "manuscripts.json"


def call(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "DH2027-lives-browser/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def claim_values(ent, prop):
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        v = c["mainsnak"].get("datavalue", {}).get("value")
        if v is not None:
            out.append(v["id"] if isinstance(v, dict) else v)
    return out


def main():
    qids = sorted({json.loads(l)["book"].rsplit("/", 1)[1] for l in open(ROOT / "mss.json")})
    cache = json.load(open(OUT)) if OUT.exists() else {}
    todo = [q for q in qids if q not in cache]
    ents = {}
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        d = call({"action": "wbgetentities", "ids": "|".join(chunk), "format": "json",
                  "props": "labels|aliases|claims", "languages": "fr|en"})
        ents.update(d.get("entities", {}))
        time.sleep(0.5)
    for q, e in ents.items():
        lab = e.get("labels", {})
        label = (lab.get("fr") or lab.get("en") or {}).get("value", q)
        aliases = [a["value"] for a in e.get("aliases", {}).get("fr", [])]
        shelf = claim_values(e, "P195")
        cache[q] = {
            "qid": q,
            "label": label,
            "short": aliases[0] if aliases else label,
            "shelfmark": shelf[0] if shelf else None,
            "institution": label.rsplit(",", 1)[0] if "," in label else None,
            "iiif": claim_values(e, "P196"),
            "viewer": claim_values(e, "P197"),
            "page": f"https://data.biblissima.fr/w/Item:{q}",
        }
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    print(f"{len(cache)} manuscripts cached; missing shelfmark: "
          f"{sum(1 for v in cache.values() if not v['shelfmark'])}")


if __name__ == "__main__":
    main()
