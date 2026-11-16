const $ = s => document.querySelector(s);
// ---- global date filter (manuscripts whose date range overlaps [from, to])
const DF = {from: "", to: "", undated: true};
const DATED = /^\/api\/(lives|manuscripts|life|graph|ms_rank|chunks)/;
const BROWSE = /^\/api\/(lives|manuscripts|life|manuscript)\b/;
let minLines = 1;
function withDates(u) {
  if (BROWSE.test(u) && !u.includes("min_hits=")) u += (u.includes("?") ? "&" : "?") + "min_hits=" + minLines;
  if (!DATED.test(u) || (!DF.from && !DF.to && DF.undated)) return u;
  const p = new URLSearchParams();
  if (DF.from) p.set("date_from", DF.from); if (DF.to) p.set("date_to", DF.to); if (!DF.undated) p.set("undated", "false");
  return u + (u.includes("?") ? "&" : "?") + p;
}
const api = (u) => fetch(withDates(u)).then(r => { if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); });
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let mode = "lives";

function showTab(t) {
  document.querySelectorAll("header nav button").forEach(x => x.classList.toggle("on", x.dataset.tab === t));
  ["browse", "network", "align"].forEach(id => $("#" + id).hidden = id !== t);
}
document.querySelectorAll("header nav button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  mode = b.dataset.list; document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b)); loadList();
});
$("#q").oninput = () => loadList();

async function loadList() {
  const q = encodeURIComponent($("#q").value);
  const rows = await api(mode === "lives" ? `/api/lives?q=${q}` : `/api/manuscripts?q=${q}`);
  $("#list").innerHTML = rows.map(r => mode === "lives"
    ? `<li data-id="${esc(r.id)}">${esc(r.life_title)}<small>${r.n_mss} mss · best cover ${r.best_cover.toFixed(2)}</small></li>`
    : `<li data-id="${esc(r.qid)}">${esc(r.shelfmark)}<small>${esc(r.date_label || "undated")} · ${r.n_lives} lives · best cover ${r.best_cover.toFixed(2)}</small></li>`).join("");
  $("#list").querySelectorAll("li").forEach(li => li.onclick = () => mode === "lives" ? showLife(li.dataset.id) : showMs(li.dataset.id));
}
const bar = c => `<span class="bar" style="width:${Math.round(c * 120)}px"></span> ${c.toFixed(2)}`;

let redraw = null;
async function showLife(id) {
  redraw = () => showLife(id);
  const d = await api(`/api/life/${id}`);
  $("#detail").innerHTML = `<h2>${esc(d.title)}</h2><p class="muted">${esc(d.id)} — candidate sources (cover = share of the life aligned; density = hits per folio spanned)</p>
  <table><tr><th>Manuscript</th><th>Date</th><th>Cover</th><th>Hits</th><th>Folios</th><th>Density</th><th></th></tr>
  ${d.sources.map(s => `<tr class="link" data-q="${s.qid}"><td title="${esc(s.label)}">${esc(s.shelfmark)} <a href="${s.page}" target="_blank" rel="noopener">↗</a></td>
  <td>${esc(s.date_label || "–")}</td><td>${bar(s.cover)}</td><td>${s.hits}</td><td>${esc(s.minp.replace(".xml",""))} → ${esc(s.maxp.replace(".xml",""))}</td><td>${s.density}</td>
  <td>${s.likely ? '<span class="tag">likely</span>' : ""} <a href="#" class="al" data-life="${esc(d.id)}" data-q="${s.qid}">text ↔</a></td></tr>`).join("")}</table>`;
  $("#detail").querySelectorAll("tr.link").forEach(tr => tr.onclick = e => { if (e.target.tagName !== "A") showMs(tr.dataset.q); });
  wireAlign();
}
async function showMs(q) {
  redraw = () => showMs(q);
  const d = await api(`/api/manuscript/${q}`);
  $("#detail").innerHTML = `<h2>${esc(d.short)}</h2><p>${esc(d.label)} · <b>${esc(d.date_label || "undated")}</b> · <a href="${d.page}" target="_blank" rel="noopener">Biblissima</a>
  ${(d.viewer || []).map(v => ` · <a href="${esc(v)}" target="_blank" rel="noopener">viewer</a>`).join("")}</p>
  <p class="muted">Lives in folio order</p><table><tr><th>Life</th><th>Cover</th><th>Hits</th><th>Folios</th></tr>
  ${d.lives.map(l => `<tr class="link" data-id="${esc(l.id)}"><td>${esc(l.title)}</td><td>${bar(l.cover)}</td><td>${l.hits}</td><td>${esc(l.minp.replace(".xml",""))} → ${esc(l.maxp.replace(".xml",""))} <a href="#" class="al" data-life="${esc(l.id)}" data-q="${q}">text ↔</a></td></tr>`).join("")}</table>`;
  $("#detail").querySelectorAll("tr.link").forEach(tr => tr.onclick = e => { if (e.target.tagName !== "A") showLife(tr.dataset.id); });
  wireAlign();
}

// ---- network
let cy, comms = [];
const excluded = new Set(); let rank = [];
const rerun = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => $("#go").click(), 250); }; })();
function drawRank() {
  const f = $("#msq").value.toLowerCase();
  $("#msrank").innerHTML = rank.filter(r => r.shelfmark.toLowerCase().includes(f)).map(r =>
    `<li class="${excluded.has(r.qid) ? "x" : ""}"><input type="checkbox" data-q="${r.qid}" ${excluded.has(r.qid) ? "checked" : ""} title="remove from network">
     <span class="r">${r.rank}</span><span title="${esc(r.qid)}">${esc(r.shelfmark)}</span><span class="n">${esc(r.date_label ? r.date_label.split(" ")[0] + " · " : "")}${r.n_lives} lives</span></li>`).join("");
  $("#xinfo").textContent = excluded.size ? `${excluded.size} manuscript(s) removed` : "tick a manuscript to remove it";
  $("#msrank").querySelectorAll("input").forEach(i => i.onchange = () => {
    i.checked ? excluded.add(i.dataset.q) : excluded.delete(i.dataset.q); drawRank(); rerun(); });
}
async function loadRank() {
  rank = await api(`/api/ms_rank?min_cover=${$("#min_cover").value}&min_hits=${$("#min_hits").value}`); drawRank();
}
$("#msq").oninput = drawRank;
$("#clearx").onclick = e => { e.preventDefault(); excluded.clear(); drawRank(); rerun(); };
["min_cover","min_hits"].forEach(id => $("#" + id).onchange = loadRank);
loadRank();
const layoutOpts = () => { const k = +$("#spread").value;
  return {name: "cose", animate: false, randomize: true, nodeRepulsion: 9000 * k * k, idealEdgeLength: 40 * k,
          nodeOverlap: 20 * k, componentSpacing: 80 * k, gravity: 1 / k}; };
$("#spread").oninput = e => { $("#o6").textContent = (+e.target.value).toFixed(1); cy && cy.layout(layoutOpts()).run(); };
const palette = ["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ac"];
["min_cover","min_hits","min_weight","resolution"].forEach((id, i) =>
  $("#" + id).oninput = e => $("#o" + (i + 1)).textContent = (+e.target.value).toFixed(id === "min_hits" ? 0 : 2));
$("#go").onclick = async () => {
  const p = new URLSearchParams({kind: $("#kind").value});
  ["min_cover","min_hits","min_weight","resolution"].forEach(k => p.set(k, $("#" + k).value));
  p.set("exclude", [...excluded].join(","));
  $("#stats").textContent = "computing…";
  const g = await api("/api/graph?" + p);
  comms = g.communities;
  $("#stats").textContent = `${g.nodes.length} nodes · ${g.edges.length} edges · ${g.communities.length} communities`;
  $("#comms").innerHTML = g.communities.slice(0, 40).map(c => `<li data-c="${c.id}"><b style="color:${palette[c.id % 10]}">●</b> ${c.size}: ${c.top.map(esc).join("; ")}</li>`).join("");
  cy && cy.destroy();
  cy = cytoscape({container: $("#cy"), wheelSensitivity: .3,
    elements: [...g.nodes.map(n => ({data: {...n, color: palette[n.community % 10]}})),
               ...g.edges.map(e => ({data: {...e, id: e.source + "|" + e.target}}))],
    style: [{selector: "node", style: {"background-color": "data(color)", label: "data(label)", "font-size": 8, width: "mapData(degree,0,10,6,28)", height: "mapData(degree,0,10,6,28)", color: "#889", "text-opacity": .8}},
            {selector: "node[kind='ms']", style: {shape: "rectangle"}},
            {selector: "edge", style: {width: "mapData(weight,0,1,.5,4)", "line-color": "#8895", opacity: .5}},
            {selector: ".sel", style: {"border-width": 2, "border-color": "#000"}}],
    layout: layoutOpts()});
  $("#export").hidden = false;
  cy.on("tap", "node", e => {
    const n = e.target.data();
    document.querySelector('[data-tab="browse"]').click();
    if (n.kind === "ms") { mode = "mss"; showMs(n.id); } else { mode = "lives"; showLife(n.id); }
  });
};
// ---- export of the network (SVG / TikZ from the current layout, PNG from Cytoscape)
function download(blob, name) {
  const a = Object.assign(document.createElement("a"), {href: URL.createObjectURL(blob), download: name});
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function drawnGraph() {
  return {nodes: cy.nodes().map(n => ({id: n.id(), label: n.data("label") || "", x: n.position("x"), y: n.position("y"),
                                       size: n.width(), color: n.data("color"), shape: n.data("kind") === "ms" ? "rect" : "circle"})),
          edges: cy.edges().map(e => ({source: e.data("source"), target: e.data("target"), width: parseFloat(e.style("width"))}))};
}
const exportName = ext => `network-${$("#kind").value}.${ext}`;
$("#x_svg").onclick = () => cy && download(new Blob([GraphExport.toSVG(drawnGraph(), {labels: $("#x_lab").checked})], {type: "image/svg+xml"}), exportName("svg"));
$("#x_tex").onclick = () => cy && download(new Blob([GraphExport.toTikZ(drawnGraph(), {labels: $("#x_lab").checked})], {type: "text/x-tex"}), exportName("tex"));
$("#x_png").onclick = () => {
  if (!cy) return;
  const noLabels = !$("#x_lab").checked;
  if (noLabels) cy.nodes().style("label", "");
  const blob = cy.png({full: true, scale: 3, bg: "#ffffff", output: "blob"});
  if (noLabels) cy.nodes().removeStyle("label");
  download(blob, exportName("png"));
};
// each detected network on its own: re-laid out in a headless Cytoscape, then exported like the whole graph
function communityGraph(c) {
  const sub = cy.nodes().filter(n => n.data("community") === c.id);
  const h = cytoscape({headless: true, elements: [...sub.map(n => ({data: n.data()})), ...sub.edgesWith(sub).map(e => ({data: e.data()}))]});
  h.layout({...layoutOpts(), randomize: true}).run();
  return {nodes: h.nodes().map(n => ({id: n.id(), label: n.data("label") || "", x: n.position("x"), y: n.position("y"),   // same sizes as the style above
                                      size: 6 + 22 * Math.min((n.data("degree") || 0) / 10, 1), color: palette[c.id % 10], shape: n.data("kind") === "ms" ? "rect" : "circle"})),
          edges: h.edges().map(e => ({source: e.data("source"), target: e.data("target"), width: .5 + 3.5 * Math.min(e.data("weight") || 0, 1)}))};
}
function svgToPng(svg, scale = 3) {
  return new Promise((ok, fail) => {
    const img = new Image(), url = URL.createObjectURL(new Blob([svg], {type: "image/svg+xml"}));
    img.onload = () => {
      const c = Object.assign(document.createElement("canvas"), {width: img.width * scale, height: img.height * scale}), x = c.getContext("2d");
      x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.scale(scale, scale); x.drawImage(img, 0, 0);
      URL.revokeObjectURL(url); c.toBlob(ok, "image/png");
    };
    img.onerror = () => fail(new Error("SVG could not be rasterised")); img.src = url;
  });
}
$("#x_each").onclick = async () => {
  if (!cy) return;
  const fmt = $("#x_fmt").value, labels = $("#x_lab").checked, kind = $("#kind").value, info = $("#x_info");
  const todo = comms.filter(c => c.size >= 2), files = [], csv = [["network", "nodes", "file", "main members"]];
  for (const [i, c] of todo.entries()) {
    info.textContent = `${i + 1}/${todo.length}…`;
    const g = communityGraph(c), name = `network-${kind}-${String(c.id + 1).padStart(2, "0")}-${GraphExport.slug(c.top[0] || "")}.${fmt}`;
    const svg = GraphExport.toSVG(g, {labels});
    files.push({name, data: fmt === "svg" ? svg : fmt === "tex" ? GraphExport.toTikZ(g, {labels}) : new Uint8Array(await (await svgToPng(svg)).arrayBuffer())});
    csv.push([c.id + 1, g.nodes.length, name, c.top.join("; ")]);
  }
  files.push({name: "index.csv", data: csv.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n") + "\n"});
  download(new Blob([GraphExport.toZip(files)], {type: "application/zip"}), `network-${kind}-each-${fmt}.zip`);
  info.textContent = `${todo.length} networks`;
};
loadList();


// ---- alignments view
const A = {lives: [], mss: [], offset: 0};
const cls = (l, c) => !c[0] && c[1] === "" ? "x" : (!c[0] && c[1].toLowerCase() === l.toLowerCase() ? "m" : "d");
function wireAlign() {
  $("#detail").querySelectorAll("a.al").forEach(a => a.onclick = e => { e.preventDefault(); e.stopPropagation(); openAlign(a.dataset.life, a.dataset.q); });
}
async function initAlign() {
  A.lives = await api("/api/lives?min_hits=0"); A.mss = await api("/api/manuscripts?min_hits=0");
  $("#a_life").innerHTML = `<option value="">— any life —</option>` + A.lives.map(l => `<option value="${esc(l.id)}">${esc(l.life_title)}</option>`).join("");
  fillMs();
}
async function fillMs(keepA, keepB) {
  const life = $("#a_life").value;
  const list = life ? (await api(`/api/life/${life}?min_hits=0`)).sources : A.mss;
  const opts = `<option value="">${life ? "(all witnesses)" : "—"}</option>` + list.map(m => `<option value="${m.qid}">${esc(m.shelfmark)}</option>`).join("");
  $("#a_a").innerHTML = opts; $("#a_b").innerHTML = opts.replace("(all witnesses)", "—");
  if (keepA) $("#a_a").value = keepA; if (keepB) $("#a_b").value = keepB;
}
async function openAlign(life, qid) {
  showTab("align"); if (!A.lives.length) await initAlign();
  $("#a_life").value = life; await fillMs(qid, ""); A.offset = 0; runAlign();
}
function renderRow(label, life, cells, extra) {
  return `<div class="row"><div class="lab">${label}</div>` + cells.map((c, i) => {
    const l = life[i], k = extra?.[i] ?? cls(l, c);
    return `<span class="c ${k}">${c[0] ? `<span class="ins">${esc(c[0])}</span>` : ""}${esc(c[1] || (l ? "·" : ""))}</span>`; }).join("") + "</div>";
}
function renderChunk(ch) {
  // each witness is projected on the life's letters, so witnesses can be compared position by position
  const n = ch.life.length, sel = ch.wits;
  const shared = Array.from({length: n}, (_, i) => {
    if (sel.length < 2 || !ch.life[i]) return false;
    const rs = sel.map(w => w.cells[i]);
    const differs = rs.map(r => r[0] || r[1].toLowerCase() !== ch.life[i].toLowerCase());
    return differs.every(Boolean) && rs.every(r => r[0] === rs[0][0] && r[1].toLowerCase() === rs[0][1].toLowerCase());
  });
  const lifeRow = `<div class="row"><div class="lab">life, from char ${ch.begin}</div>${ch.life.map(l => `<span class="c life">${esc(l || " ")}</span>`).join("")}</div>`;
  const rows = sel.map(w => renderRow(`${esc(w.shelfmark)} · fol. ${esc(w.folio)} · identity ${(w.ident * 100).toFixed(0)}%`, ch.life, w.cells,
      w.cells.map((c, i) => shared[i] ? "s" : cls(ch.life[i], c)))).join("");
  const ns = shared.filter(Boolean).length;
  return `<div class="chunk"><h4>passage at char ${ch.begin}${ns ? ` · ${ns} shared variant(s)` : ""}</h4>${lifeRow}${rows}</div>`;
}
async function runAlign() {
  try { await runAlign_(); } catch (e) { alignError(e); }
}
const alignError = e => $("#a_out").innerHTML = `<p class="muted">Could not load alignments (${esc(e.message)}). If this says 404, restart the server so it picks up the new backend code (./run.sh), then hard-refresh the page.</p>`;
async function runAlign_() {
  const life = $("#a_life").value, a = $("#a_a").value, b = $("#a_b").value, ms = [a, b].filter(Boolean);
  const out = $("#a_out");
  if (!life) {
    if (!(a && b)) { out.innerHTML = `<p class="muted">Choose a life, or two manuscripts.</p>`; return; }
    const d = await api(`/api/pair?a=${a}&b=${b}`);
    out.innerHTML = `<h2>${esc(d.a)} ↔ ${esc(d.b)}</h2><p class="muted">${d.lives.length} lives aligned in both. Agreement = share of life positions where both read the same; shared variants = places where both depart from the life in the same way (evidence of a common ancestor).</p>
    <table><tr><th>Life</th><th>Passages</th><th>Ident. A</th><th>Ident. B</th><th>Agreement</th><th>Shared variants</th></tr>
    ${d.lives.map(l => `<tr class="link" data-id="${esc(l.id)}"><td>${esc(l.title)}</td><td>${l.chunks}</td><td>${bar(l.ident_a)}</td><td>${bar(l.ident_b)}</td>
      <td>${l.agreement ?? "–"}</td><td>${l.shared_variants} / ${l.both_differ}</td></tr>`).join("")}</table>`;
    out.querySelectorAll("tr.link").forEach(tr => tr.onclick = async () => { $("#a_life").value = tr.dataset.id; await fillMs(a, b); A.offset = 0; runAlign(); });
    return;
  }
  const p = new URLSearchParams({life, ms: ms.join(","), require_all: $("#a_all").checked && ms.length > 1, min_ident: $("#a_min").value, offset: A.offset});
  const d = await api("/api/chunks?" + p);
  const pager = `<div class="pager"><button id="prev" ${A.offset ? "" : "disabled"}>‹</button><span>${d.n_match ? A.offset + 1 : 0}–${A.offset + d.chunks.length} of ${d.n_match} passages (${d.n_total} aligned in total)</span><button id="next" ${A.offset + d.chunks.length < d.n_match ? "" : "disabled"}>›</button></div>`;
  out.innerHTML = `<h2>${esc(d.title)}</h2><p class="muted">${ms.length ? "Compared with: " + ms.map(q => esc((A.mss.find(m => m.qid === q) || {}).shelfmark || q)).join(" and ") : "All witnesses"}</p>${pager}${d.chunks.map(renderChunk).join("") || '<p class="muted">No passage matches.</p>'}${d.chunks.length > 5 ? pager : ""}`;
  out.querySelectorAll("#prev").forEach(x => x.onclick = () => { A.offset = Math.max(0, A.offset - 100); runAlign(); out.scrollTop = 0; });
  out.querySelectorAll("#next").forEach(x => x.onclick = () => { A.offset += 100; runAlign(); out.scrollTop = 0; });
}
$("#a_life").onchange = async () => { await fillMs(); A.offset = 0; runAlign(); };
["a_a", "a_b", "a_all", "a_min"].forEach(id => $("#" + id).onchange = () => { A.offset = 0; runAlign(); });
$("#a_min").oninput = e => $("#a_o").textContent = (+e.target.value).toFixed(2);
document.querySelector('[data-tab="align"]').addEventListener("click", () => { if (!A.lives.length) initAlign().catch(alignError); });

// ---- date filter bar
function onDateChange() {
  DF.from = $("#d_from").value; DF.to = $("#d_to").value; DF.undated = $("#d_undated").checked;
  document.querySelectorAll("#d_cent button").forEach(b => b.classList.toggle("on", DF.from == b.dataset.lo && DF.to == b.dataset.hi));
  $("#d_info").textContent = DF.from || DF.to || !DF.undated ? "filter active" : "";
  loadList(); loadRank(); redraw && redraw();
  if (cy) $("#go").click();
  if (A.lives.length) { A.offset = 0; initAlign().then(runAlign); }
}
api("/api/date_range").then(r => {
  const roman = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII"];
  $("#d_cent").innerHTML = r.centuries.map(([c, n]) => `<button data-lo="${(c - 1) * 100 + 1}" data-hi="${c * 100}" title="${n} manuscripts">${roman[c]}</button>`).join("");
  $("#d_cent").querySelectorAll("button").forEach(b => b.onclick = () => { $("#d_from").value = b.dataset.lo; $("#d_to").value = b.dataset.hi; onDateChange(); });
}).catch(() => {});
["d_from", "d_to", "d_undated"].forEach(id => $("#" + id).onchange = onDateChange);
$("#d_reset").onclick = () => { $("#d_from").value = ""; $("#d_to").value = ""; $("#d_undated").checked = true; onDateChange(); };

// ---- browse: minimum aligned lines
$("#min_lines").oninput = e => { minLines = +e.target.value; $("#o_mh").textContent = minLines; };
$("#min_lines").onchange = () => { loadList(); redraw && redraw(); };
