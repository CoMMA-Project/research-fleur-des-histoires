import json
import shutil
import subprocess
import xml.dom.minidom
from pathlib import Path

import pytest

EXPORT = Path(__file__).resolve().parent.parent / "frontend" / "export.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")

G = {"nodes": [{"id": "a", "label": "Saint A_b & 50% <x>", "x": 0, "y": 0, "size": 10, "color": "#4e79a7", "shape": "circle"},
               {"id": "b", "label": "Paris, BnF", "x": 100, "y": 50, "size": 20, "color": "#f28e2b", "shape": "rect"}],
     "edges": [{"source": "a", "target": "b", "width": 2}, {"source": "a", "target": "gone", "width": 2}]}


def run(fn, **opts):
    js = f"const E=require({json.dumps(str(EXPORT))});process.stdout.write(E.{fn}({json.dumps(G)},{json.dumps(opts)}))"
    return subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout


def test_svg_is_valid_xml_and_escapes_labels():
    svg = run("toSVG")
    xml.dom.minidom.parseString(svg)
    assert "&amp;" in svg and "&lt;x&gt;" in svg
    assert svg.count("<line") == 1  # the edge to a missing node is dropped
    assert "<rect" in svg and "<circle" in svg


def test_svg_without_labels():
    assert "<text" not in run("toSVG", labels=False)


def test_tikz_document_escapes_and_defines_colours():
    tex = run("toTikZ")
    assert "\\documentclass" in tex and "\\end{document}" in tex
    assert "\\definecolor{c4E79A7}{HTML}{4E79A7}" in tex and "\\definecolor{cF28E2B}{HTML}{F28E2B}" in tex
    assert "Saint A\\_b \\& 50\\% <x>" in tex
    assert tex.count("\\draw") == 1
    assert "\\node" in tex and "rectangle" in tex and "label" not in run("toTikZ", labels=False).split("% nodes")[1]


def test_zip_is_readable_by_python_and_keeps_utf8_names(tmp_path):
    js = ("const E=require(%s);process.stdout.write(Buffer.from(E.toZip([{name:'a/é.svg',data:'<svg/>'},{name:'b.tex',data:'x'.repeat(5000)}])).toString('base64'))"
          % json.dumps(str(EXPORT)))
    import base64, io, zipfile
    z = zipfile.ZipFile(io.BytesIO(base64.b64decode(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)))
    assert z.testzip() is None
    assert z.namelist() == ["a/é.svg", "b.tex"]
    assert z.read("a/é.svg") == b"<svg/>" and z.read("b.tex") == b"x" * 5000


def test_slug():
    js = "const E=require(%s);process.stdout.write(E.slug('Saint Éloi, évêque de Noyon!'))" % json.dumps(str(EXPORT))
    assert subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout == "saint-eloi-eveque-de-noyon"
