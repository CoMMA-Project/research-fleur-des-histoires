"""Life length (nb of lines in lives/text-*.txt) vs nb of matches (mss.json).

A match = a (life, manuscript) row of mss.json; its quality is `cover` (share of the life covered)
and `hits`. Only rows with cover >= --min-cover and hits >= --min-hits are counted (defaults = the
app's network view). Lives left with no match are still plotted, at 0."""
import argparse, glob, json
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.colors as mc
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("out", nargs="?", help="output path; default: parameters are encoded in the file name")
ap.add_argument("--format", choices=["png", "pdf", "svg"], default="png")
ap.add_argument("--kind", choices=["heatmap", "scatter"], default="heatmap")
ap.add_argument("--no-caption", action="store_true", help="omit the title/caption from the figure and print it instead")
ap.add_argument("--min-cover", type=float, default=0.2)
ap.add_argument("--min-hits", type=int, default=5)
a = ap.parse_args()
kind = a.kind
out = a.out or f"length_vs_matches_{kind}_cover{a.min_cover:g}_hits{a.min_hits}{'_nocaption' if a.no_caption else ''}.{a.format}"
nlines = {f: sum(1 for _ in open(f, encoding="utf8")) for f in sorted(glob.glob("lives/text-*.txt"))}
def mid_date(q):
    """Mid-year of the manuscript's date range (cache/dates.json), or None."""
    v = dates.get(q, {})
    try:
        a, b = int(v["start_year"]), int(v["stop_year"])
    except (KeyError, TypeError, ValueError):
        return None
    return (a + b) / 2


dates = json.load(open("cache/dates.json"))
n_ms, hits, mss_dates = defaultdict(int), defaultdict(int), defaultdict(list)
for l in open("mss.json"):
    r = json.loads(l)
    if r["cover"] < a.min_cover or r["hits"] < a.min_hits:
        continue
    f = r["id"]
    n_ms[f] += 1
    if (d := mid_date(r["book"].rsplit("/", 1)[1])) is not None:
        mss_dates[f].append(d)
    hits[f] += r["hits"]
L = np.array([nlines[f] for f in nlines])
# colour = median mid-date of the life's matching manuscripts (NaN -> grey)
D = np.array([np.median(mss_dates[f]) if mss_dates[f] else np.nan for f in nlines])
# continuous date scale (years) read in centuries: s. XIV = 1301-1400, ... (as in backend/data.py)
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII"]
c0, c1 = int((np.nanmin(D) - 1) // 100 + 1), int((np.nanmax(D) - 1) // 100 + 1)
lo, hi = (c0 - 1) * 100, c1 * 100  # edges of the first and last century
cmap = mc.LinearSegmentedColormap.from_list("dates", plt.get_cmap("YlGnBu")(np.linspace(0.12, 0.95, 256)))
norm = mc.Normalize(lo, hi)
panels = [
    ("Number of manuscripts containing the Life", np.array([n_ms[f] for f in nlines])),
    ("Lines of the Life found in the manuscripts\n(all manuscripts together)", np.array([hits[f] for f in nlines])),
]

titles = ["How many manuscripts transmit each Life?", "How much of each Life is found in the manuscripts?"]
fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), constrained_layout=True)
fig.get_layout_engine().set(w_pad=0.1, h_pad=0.12, wspace=0.14, hspace=0.1)
xb = np.logspace(np.log10(max(L.min(), 1)), np.log10(L.max()), 20)
for ax, (ylab, y), ylog in zip(axes, panels, (False, True)):
    off = 1 if ylog else 0  # +1 only where the y axis is log (to show 0 matches)
    # y+1 so that lives with 0 matches fit on the log axis
    if kind == "scatter":
        rng = np.random.default_rng(0)
        jit = lambda v: v * rng.uniform(0.93, 1.07, len(v))  # de-overlap integer counts
        yj = y + rng.uniform(-0.15, 0.15, len(y)) if not ylog else np.where(y == 0, 0, jit(y))
        nd = np.isnan(D)
        ax.scatter(jit(L)[nd], yj[nd], s=24, color="#9a9a9a", alpha=0.7, edgecolor="white", linewidth=0.4)
        sc = ax.scatter(jit(L)[~nd], yj[~nd], s=30, c=D[~nd], cmap=cmap, norm=norm, alpha=0.75, edgecolor="#444", linewidth=0.3)
    else:
        yb = np.logspace(0, np.log10(y.max() + 1), 20) if ylog else np.arange(-0.5, y.max() + 1.5)
        h = ax.hist2d(L, y + off, bins=[xb, yb], cmap="viridis", norm=mc.LogNorm(), cmin=1)
        fig.colorbar(h[3], ax=ax, label="nb of lives")
    ax.set_xscale("log")
    if ylog:
        if kind == "scatter":
            ax.set_yscale("symlog", linthresh=1, linscale=0.4)
            ax.set_ylim(-0.5, y.max() * 2)
            ax.set_yticks([0, 1, 10, 100, 1000])
            ax.set_yticklabels(["0", "1", "10", "100", "1000"])
            ax.yaxis.set_minor_locator(plt.NullLocator())
        else:
            ax.set_yscale("log")
    ax.set_xlabel("Length of the Life (number of lines, log scale)", labelpad=10)
    ax.set_ylabel(labelpad=10, ylabel=ylab + ("\n(log scale" + ("" if kind == "scatter" else ", +1") + ")" if ylog else ""))
    ax.set_title(titles[ax is axes[1]], fontsize=11, pad=14)
    m = y > 0
    print(ylab, "log-log r =", round(np.corrcoef(np.log(L[m]), np.log(y[m]))[0, 1], 2))
caption = (f"Length of the Lives and their manuscript tradition ({len(L)} Lives, {(panels[0][1] == 0).sum()} found in no manuscript). "
           f"A Life counts as present in a manuscript when at least {a.min_hits} of its lines and {a.min_cover:.0%} of its text are found there.")
if a.no_caption:
    print("CAPTION:", caption)
else:
    fig.suptitle(caption.replace(". A Life", "\nA Life").rstrip("."), fontsize=12, linespacing=1.6)
if kind == "scatter":  # one scale shared by both panels
    from matplotlib.lines import Line2D
    cents = np.arange(c0, c1 + 1)
    cb = fig.colorbar(sc, ax=axes, shrink=0.7, pad=0.04, label="Date of the manuscripts containing the Life\n(median, by century)")
    cb.set_ticks([(c - 0.5) * 100 for c in cents])  # label each century at its centre
    cb.set_ticklabels([f"s. {ROMAN[c]}" for c in cents])
    cb.ax.tick_params(length=0)
    for c in cents[:-1]:  # century boundaries
        cb.ax.axhline(c * 100, color="white", lw=1.5)
    cb.ax.invert_yaxis()  # oldest at the top, reading down through time
    grey = Line2D([], [], marker="o", ls="", color="#9a9a9a", alpha=0.7, markersize=6, label="Life found in\nno manuscript")
    cb.ax.legend(handles=[grey], loc="upper center", bbox_to_anchor=(0.5, -0.06), frameon=False, fontsize=9, borderaxespad=0)
plt.rcParams["pdf.fonttype"] = 42  # keep text as real text in PDFs
fig.savefig(out, dpi=150)
print(out)
