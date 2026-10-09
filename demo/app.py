"""Hugging Face Space front end for Rosetta.

Serves the pre-computed sweep results, and optionally re-runs the pipeline live
for one corpus program when a Nebius key is present.

The program list is fixed on purpose. Comparing a port against the original
means executing model-generated Python, and in a Space that happens in the same
container as the web server, so accepting arbitrary source here would be
careless. The CLI does accept any file and isolates each run in a network-less
container.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parent
PRECOMPUTED = ROOT / "precomputed"
REPO = "https://github.com/pradeeptrain9/rosetta"

app = FastAPI(title="Rosetta", docs_url=None, redoc_url=None)


def _live_enabled() -> bool:
    return bool(os.environ.get("NEBIUS_API_KEY", "").strip())


def _index() -> list[dict]:
    f = PRECOMPUTED / "index.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())


def _program(pid: str) -> dict:
    # pid comes from the URL, so it must never be allowed to escape the folder.
    if not pid.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "bad program id")
    f = PRECOMPUTED / f"{pid}.json"
    if not f.exists():
        raise HTTPException(404, f"no results for {pid}")
    return json.loads(f.read_text())


# ---------------------------------------------------------------- styling

CSS = """
:root{--bg:#fbfbfd;--fg:#16161a;--dim:#5d6069;--line:#e3e4e8;--card:#fff;
--ok:#0a7c4a;--bad:#b4232b;--accent:#3b4cca;--code:#f5f5f8}
@media(prefers-color-scheme:dark){:root{--bg:#121316;--fg:#e9e9ee;--dim:#9a9ca5;
--line:#2a2c33;--card:#1a1b20;--ok:#3ecf8e;--bad:#ff6b6b;--accent:#8c9eff;--code:#16171b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:17px;margin:32px 0 10px}
.sub{color:var(--dim);margin:0 0 24px;max-width:70ch}
a{color:var(--accent)}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 26px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px 16px;min-width:116px}
.kpi b{display:block;font-size:24px;letter-spacing:-.02em}
.kpi span{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);font-weight:600}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--ok);font-weight:600}
.bad{color:var(--bad);font-weight:600}
pre{background:var(--code);border:1px solid var(--line);border-radius:10px;
padding:14px;overflow:auto;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
margin:0;max-height:460px}
pre.diff{max-height:none}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:8px;padding:12px 14px;color:var(--dim);font-size:13.5px;margin:18px 0}
.back{display:inline-block;margin-bottom:18px;text-decoration:none}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:13px}
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang=en><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style>"
        f"<div class=wrap>{body}</div></html>"
    )


# ---------------------------------------------------------------- routes


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    rows = _index()
    if not rows:
        return _page(
            "Rosetta",
            "<h1>Rosetta</h1><div class=note>No pre-computed results in this image. "
            "Run <code>rosetta bench benchmarks/programs</code> then "
            "<code>python3 demo/precompute.py</code> before building.</div>",
        )

    equiv = sum(1 for r in rows if r["equivalent"])
    vectors = sum(r["vectors_total"] for r in rows)
    passed = sum(r["vectors_passed"] for r in rows)
    no_repair = sum(1 for r in rows if r["equivalent"] and r["repair_iterations"] == 0)

    body = [
        "<h1>Rosetta</h1>",
        "<p class=sub>COBOL migrated to Python, with equivalence checked against "
        "the GnuCOBOL-compiled original rather than asserted by a model. A program "
        "counts as migrated only when every generated test input produces "
        "byte-identical output.</p>",
        "<div class=kpis>",
        f"<div class=kpi><b>{equiv}/{len(rows)}</b><span>proven equivalent</span></div>",
        f"<div class=kpi><b>{no_repair}</b><span>first try</span></div>",
        f"<div class=kpi><b>{passed}/{vectors}</b><span>vectors passed</span></div>",
        "</div>",
        "<table><tr><th>Program</th><th class=n>COBOL LOC</th><th class=n>Vectors</th>"
        "<th class=n>Passed</th><th class=n>Repairs</th><th>Equivalent</th></tr>",
    ]
    for r in rows:
        pid = html.escape(r["program_id"])
        mark = (
            "<span class=ok>yes</span>"
            if r["equivalent"]
            else "<span class=bad>no</span>"
        )
        body.append(
            f"<tr><td><a href='/p/{pid}'>{pid}</a></td>"
            f"<td class=n>{r['loc']}</td><td class=n>{r['vectors_total']}</td>"
            f"<td class=n>{r['vectors_passed']}</td>"
            f"<td class=n>{r['repair_iterations']}</td><td>{mark}</td></tr>"
        )
    body.append("</table>")
    body.append(
        "<div class=note>Translation and repair run on Nemotron Ultra; the I/O "
        "contract and test vectors come from Nemotron Nano. Everything is served "
        f"by Nebius Token Factory. Source and method: <a href='{REPO}'>{REPO}</a>.</div>"
    )
    if not _live_enabled():
        body.append(
            "<p class=sub>Showing pre-computed results. Set <code>NEBIUS_API_KEY</code> "
            "as a Space secret to enable live re-runs.</p>"
        )
    return _page("Rosetta", "".join(body))


@app.get("/p/{pid}", response_class=HTMLResponse)
def program(pid: str) -> HTMLResponse:
    d = _program(pid)
    name = html.escape(d["program_id"])
    mark = (
        "<span class=ok>proven equivalent</span>"
        if d["equivalent"]
        else "<span class=bad>not equivalent</span>"
    )
    fails = d.get("diffs") or []

    body = [
        "<a class=back href='/'>&larr; all programs</a>",
        f"<h1>{name}</h1>",
        f"<p class=sub>{mark} &mdash; {d['vectors_passed']}/{d['vectors_total']} "
        f"vectors matched byte for byte, after {d['repair_iterations']} repair "
        f"iteration(s).</p>",
    ]

    # Evidence before source. The diffs are what make the claim checkable, and
    # two full file listings push them a long way below the fold.
    if fails:
        body.append(f"<h2>Failing vectors ({len(fails)})</h2>")
        body.append(
            "<p class=sub>Each block is the original's output against the port's, "
            "for one generated input. Minus is COBOL, plus is Python.</p>"
        )
        for f in fails[:12]:
            body.append(
                f"<p class=sub><code>{html.escape(f.get('kind',''))}</code> on input "
                f"{html.escape(repr(f.get('stdin','')))}</p>"
                f"<pre class=diff>{html.escape(f.get('detail',''))}</pre>"
            )
        if len(fails) > 12:
            body.append(f"<p class=sub>{len(fails) - 12} further failing vector(s) not shown.</p>")
    else:
        body.append(
            "<div class=note>No failing vectors. Every generated input - including "
            "boundary and overflow cases derived from the program's own PIC clauses "
            "- produced identical output from both programs.</div>"
        )

    body += [
        "<div class=cols>",
        f"<div><h2>COBOL original</h2><pre>{html.escape(d.get('cobol',''))}</pre></div>",
        f"<div><h2>Migrated Python</h2><pre>{html.escape(d.get('python',''))}</pre></div>",
        "</div>",
    ]
    return _page(f"Rosetta - {d['program_id']}", "".join(body))


@app.get("/api/index")
def api_index() -> JSONResponse:
    return JSONResponse(_index())


@app.get("/api/p/{pid}")
def api_program(pid: str) -> JSONResponse:
    return JSONResponse(_program(pid))


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True, "programs": len(_index()), "live": _live_enabled()})


@app.post("/api/run/{pid}")
def run_live(pid: str) -> JSONResponse:
    """Re-run the pipeline for one corpus program."""
    if not _live_enabled():
        raise HTTPException(503, "live runs disabled: NEBIUS_API_KEY is not set")

    known = {r["program_id"] for r in _index()}
    if pid not in known:
        raise HTTPException(404, f"{pid} is not in the corpus")

    from rosetta.config import Settings, resolve_models
    from rosetta.llm import LLMClient
    from rosetta.pipeline import migrate_program
    from rosetta.sandbox import Sandbox

    source = next(
        (p for p in (Path("benchmarks/programs")).glob("*.cbl")
         if p.stem.upper() == pid.upper()),
        None,
    )
    if source is None:
        raise HTTPException(404, f"source for {pid} not found")

    settings = Settings.from_env()
    client = LLMClient(settings)
    routing = resolve_models(served=client.served_models())
    result = migrate_program(source, client, routing, settings, Sandbox(settings))
    return JSONResponse(result.summary())
