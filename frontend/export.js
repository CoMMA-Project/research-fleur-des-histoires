// Export of the network graph as SVG or TikZ (PNG is done by Cytoscape itself, see app.js).
// Pure functions: they take a plain description of the drawn graph, so they can be tested in Node.
//   g = {nodes: [{id, label, x, y, size, color, shape: "circle"|"rect"}],
//        edges: [{source, target, width}]}      // x, y, size, width in screen pixels (y points down)
(function (root) {
  const PAD = 12, EDGE = "#888888", EDGE_OPACITY = 0.5, LABEL = "#555566", FONT = 8;

  function bounds(g) {
    if (!g.nodes.length) return {x0: 0, y0: 0, x1: 1, y1: 1};
    const xs = g.nodes.flatMap(n => [n.x - n.size / 2, n.x + n.size / 2]);
    const ys = g.nodes.flatMap(n => [n.y - n.size / 2, n.y + n.size / 2 + FONT * 1.4]); // room for labels
    return {x0: Math.min(...xs) - PAD, y0: Math.min(...ys) - PAD, x1: Math.max(...xs) + PAD, y1: Math.max(...ys) + PAD};
  }
  const xml = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const r2 = v => Math.round(v * 100) / 100;

  function toSVG(g, {labels = true} = {}) {
    const b = bounds(g), pos = Object.fromEntries(g.nodes.map(n => [n.id, n]));
    const out = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${r2(b.x0)} ${r2(b.y0)} ${r2(b.x1 - b.x0)} ${r2(b.y1 - b.y0)}" width="${r2(b.x1 - b.x0)}" height="${r2(b.y1 - b.y0)}">`,
      `<g stroke="${EDGE}" stroke-opacity="${EDGE_OPACITY}" fill="none">`];
    for (const e of g.edges) {
      const s = pos[e.source], t = pos[e.target];
      if (s && t) out.push(`<line x1="${r2(s.x)}" y1="${r2(s.y)}" x2="${r2(t.x)}" y2="${r2(t.y)}" stroke-width="${r2(e.width)}"/>`);
    }
    out.push("</g>", "<g>");
    for (const n of g.nodes) {
      out.push(n.shape === "rect"
        ? `<rect x="${r2(n.x - n.size / 2)}" y="${r2(n.y - n.size / 2)}" width="${r2(n.size)}" height="${r2(n.size)}" fill="${n.color}"/>`
        : `<circle cx="${r2(n.x)}" cy="${r2(n.y)}" r="${r2(n.size / 2)}" fill="${n.color}"/>`);
    }
    out.push("</g>");
    if (labels) {
      out.push(`<g font-family="sans-serif" font-size="${FONT}" fill="${LABEL}" text-anchor="middle">`);
      for (const n of g.nodes) if (n.label) out.push(`<text x="${r2(n.x)}" y="${r2(n.y + n.size / 2 + FONT)}">${xml(n.label)}</text>`);
      out.push("</g>");
    }
    out.push("</svg>");
    return out.join("\n");
  }

  const TEX = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$", "&": "\\&", "#": "\\#", "^": "\\^{}", "_": "\\_", "%": "\\%", "~": "\\~{}"};
  const texEsc = s => String(s).replace(/[\\{}$&#^_%~]/g, c => TEX[c]);

  // standalone TikZ document, `widthCm` wide (resize with \resizebox / scale if you \input it)
  function toTikZ(g, {labels = true, widthCm = 16} = {}) {
    const b = bounds(g), k = widthCm / Math.max(b.x1 - b.x0, 1);   // px -> cm
    const X = x => r2((x - b.x0) * k), Y = y => r2(-(y - b.y0) * k); // TikZ y points up
    const pt = px => r2(Math.max(px * k * 28.4528, 0.15));            // px -> pt, never invisible
    const fs = r2(Math.max(FONT * k * 28.4528, 3));                    // label size follows the graph scale (min 3pt)
    const pos = Object.fromEntries(g.nodes.map(n => [n.id, n]));
    const colors = [...new Set(g.nodes.map(n => n.color.replace("#", "").toUpperCase()))];
    const out = ["\\documentclass[tikz,border=4pt]{standalone}", "\\usepackage[utf8]{inputenc}", "\\usepackage[T1]{fontenc}",
      ...colors.map(c => `\\definecolor{c${c}}{HTML}{${c}}`),
      "\\begin{document}", `\\begin{tikzpicture}[font=\\fontsize{${fs}pt}{${r2(fs * 1.2)}pt}\\selectfont]`,
      `  % edges (line width ~ similarity)`];
    for (const e of g.edges) {
      const s = pos[e.source], t = pos[e.target];
      if (s && t) out.push(`  \\draw[line width=${pt(e.width)}pt, black!45, opacity=${EDGE_OPACITY}] (${X(s.x)},${Y(s.y)}) -- (${X(t.x)},${Y(t.y)});`);
    }
    out.push("  % nodes: circles = lives, squares = manuscripts; colour = community");
    for (const n of g.nodes) {
      const d = r2(n.size * k), shape = n.shape === "rect" ? "rectangle" : "circle";
      out.push(`  \\node[${shape}, fill=c${n.color.replace("#", "").toUpperCase()}, inner sep=0pt, minimum size=${d}cm] at (${X(n.x)},${Y(n.y)}) {};`);
    }
    if (labels) {
      out.push("  % labels");
      for (const n of g.nodes) if (n.label)
        out.push(`  \\node[anchor=north, text=black!65, inner sep=1pt] at (${X(n.x)},${Y(n.y + n.size / 2)}) {${texEsc(n.label)}};`);
    }
    out.push("\\end{tikzpicture}", "\\end{document}", "");
    return out.join("\n");
  }

  // ---- minimal ZIP writer (stored, no compression): files = [{name, data: string | Uint8Array | Blob-free bytes}]
  const CRC = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function toZip(files) {
    const enc = new TextEncoder(), parts = [], central = [];
    let offset = 0;
    const u16 = v => [v & 255, v >>> 8 & 255], u32 = v => [v & 255, v >>> 8 & 255, v >>> 16 & 255, v >>> 24 & 255];
    for (const f of files) {
      const name = enc.encode(f.name), data = typeof f.data === "string" ? enc.encode(f.data) : f.data, crc = crc32(data);
      const common = [...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(name.length), ...u16(0)];
      parts.push(Uint8Array.from([0x50, 0x4b, 3, 4, ...common]), name, data);
      central.push(Uint8Array.from([0x50, 0x4b, 1, 2, ...u16(20), ...common, ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(offset)]), name);
      offset += 30 + name.length + data.length;
    }
    const cdSize = central.reduce((n, a) => n + a.length, 0);
    const end = Uint8Array.from([0x50, 0x4b, 5, 6, 0, 0, 0, 0, ...u16(files.length), ...u16(files.length), ...u32(cdSize), ...u32(offset), 0, 0]);
    const all = [...parts, ...central, end], out = new Uint8Array(all.reduce((n, a) => n + a.length, 0));
    let o = 0; for (const a of all) { out.set(a, o); o += a.length; }
    return out;
  }
  const slug = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "network";

  const api = {toSVG, toTikZ, texEsc, toZip, slug};
  if (typeof module !== "undefined") module.exports = api; else root.GraphExport = api;
})(typeof window !== "undefined" ? window : globalThis);
