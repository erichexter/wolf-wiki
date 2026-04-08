"""
Wolf Wiki Browser — serves the three LLM wikis (the-forge, the-brain, the-blueprint)
Renders .md as HTML, also serves raw markdown for LLM scraping.
NAS mounted at /mnt/hex-data on ub24.
Run: uvicorn app:app --host 0.0.0.0 --port 3010
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from pathlib import Path
import markdown2, re, json

app = FastAPI(title="Wolf Wiki")

KNOWLEDGE_ROOT = Path("/mnt/hex-data/knowledge")
WIKIS = ["the-forge", "the-brain", "the-blueprint"]
WIKI_LABELS = {
    "the-forge": ("The Forge", "YouTube & research knowledge base", "#e67e22"),
    "the-brain": ("The Brain", "Hex personal knowledge base", "#3498db"),
    "the-blueprint": ("The Blueprint", "Wolf/OpenClaw ecosystem", "#9b59b6"),
}

STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; }
  a { color: #58a6ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .nav { background: #161b22; padding: 12px 24px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 16px; }
  .nav h1 { font-size: 16px; font-weight: 600; color: #f0f6fc; }
  .nav .breadcrumb { color: #8b949e; font-size: 14px; }
  .nav .raw-link { margin-left: auto; font-size: 12px; background: #21262d; padding: 4px 10px; border-radius: 6px; color: #8b949e; }
  .container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
  .wiki-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 24px; }
  .wiki-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
  .wiki-card h2 { font-size: 18px; margin-bottom: 8px; }
  .wiki-card p { font-size: 13px; color: #8b949e; margin-bottom: 16px; }
  .wiki-card .count { font-size: 12px; color: #8b949e; margin-top: 12px; }
  .file-list { margin-top: 8px; }
  .file-list a { display: block; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 14px; }
  .file-list a:last-child { border-bottom: none; }
  .search-box { width: 100%; padding: 10px 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; color: #e0e0e0; font-size: 14px; margin-bottom: 24px; }
  .search-box:focus { outline: none; border-color: #58a6ff; }
  .md-body h1,h2,h3 { color: #f0f6fc; margin: 24px 0 12px; }
  .md-body h1 { font-size: 28px; border-bottom: 1px solid #30363d; padding-bottom: 12px; }
  .md-body h2 { font-size: 20px; }
  .md-body p { line-height: 1.7; margin: 12px 0; color: #c9d1d9; }
  .md-body ul,ol { padding-left: 24px; margin: 12px 0; }
  .md-body li { margin: 6px 0; line-height: 1.6; color: #c9d1d9; }
  .md-body code { background: #21262d; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #e6db74; }
  .md-body pre { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 16px 0; }
  .md-body pre code { background: none; padding: 0; color: #c9d1d9; }
  .md-body table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  .md-body th { background: #21262d; padding: 8px 12px; text-align: left; border: 1px solid #30363d; font-size: 13px; }
  .md-body td { padding: 8px 12px; border: 1px solid #30363d; font-size: 13px; color: #c9d1d9; }
  .md-body blockquote { border-left: 4px solid #30363d; padding-left: 16px; color: #8b949e; margin: 12px 0; }
  .tag { display: inline-block; background: #21262d; border-radius: 20px; padding: 2px 10px; font-size: 11px; color: #8b949e; margin: 2px; }
  .badge { display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; margin-right: 8px; }
  @media (max-width: 700px) { .wiki-grid { grid-template-columns: 1fr; } }
</style>
"""

def page_count(wiki):
    d = KNOWLEDGE_ROOT / wiki
    if not d.exists(): return 0
    return len([f for f in d.glob("*.md") if f.name not in ("SCHEMA.md","log.md","lint-report.md")])

def render_md(text):
    return markdown2.markdown(text, extras=["tables","fenced-code-blocks","strike","header-ids"])

def nav(breadcrumbs=None, raw_url=None):
    bc = ' <span style="color:#30363d">›</span> '.join(f'<a href="{u}">{t}</a>' if u else t for t,u in (breadcrumbs or []))
    raw = f'<a class="raw-link" href="{raw_url}">📄 raw</a>' if raw_url else ''
    return f'<nav class="nav"><h1>🐺 Wolf Wiki</h1><span class="breadcrumb">{bc}</span>{raw}</nav>'

@app.get("/", response_class=HTMLResponse)
def home():
    cards = ""
    for w in WIKIS:
        label, desc, color = WIKI_LABELS[w]
        cnt = page_count(w)
        cards += f"""
        <a href="/{w}" style="text-decoration:none">
          <div class="wiki-card">
            <h2 style="color:{color}">{label}</h2>
            <p>{desc}</p>
            <span class="count">{cnt} pages</span>
          </div>
        </a>"""
    return f"""<!DOCTYPE html><html><head><title>Wolf Wiki</title>{STYLE}</head><body>
    {nav([("Home",None)])}
    <div class="container">
      <h2 style="color:#f0f6fc;margin-bottom:8px">Wolf Wiki</h2>
      <p style="color:#8b949e;margin-bottom:24px">Three persistent LLM knowledge bases. Browse or scrape raw markdown via <code>/&lt;wiki&gt;/&lt;page&gt;/raw</code>.</p>
      <div class="wiki-grid">{cards}</div>
    </div></body></html>"""

@app.get("/{wiki}", response_class=HTMLResponse)
def wiki_index(wiki: str):
    if wiki not in WIKIS:
        raise HTTPException(404)
    label, desc, color = WIKI_LABELS[wiki]
    d = KNOWLEDGE_ROOT / wiki
    index_file = d / "index.md"
    
    if index_file.exists():
        content = render_md(index_file.read_text(encoding="utf-8"))
        body = f'<div class="md-body">{content}</div>'
    else:
        files = sorted([f for f in d.glob("*.md") if f.name not in ("SCHEMA.md","log.md","lint-report.md","index.md")])
        links = "".join(f'<a href="/{wiki}/{f.stem}">{f.stem}</a>' for f in files)
        body = f'<div class="file-list">{links}</div>'
    
    return f"""<!DOCTYPE html><html><head><title>{label} — Wolf Wiki</title>{STYLE}</head><body>
    {nav([("Home","/"), (label, None)], raw_url=f"/{wiki}/index/raw")}
    <div class="container">{body}</div></body></html>"""

@app.get("/{wiki}/index/raw", response_class=PlainTextResponse)
def wiki_index_raw(wiki: str):
    if wiki not in WIKIS:
        raise HTTPException(404)
    f = KNOWLEDGE_ROOT / wiki / "index.md"
    if not f.exists():
        raise HTTPException(404, "index.md not found")
    return f.read_text(encoding="utf-8")

@app.get("/{wiki}/_list", response_class=JSONResponse)
def wiki_list(wiki: str):
    """List all pages as JSON — useful for LLM scraping."""
    if wiki not in WIKIS:
        raise HTTPException(404)
    d = KNOWLEDGE_ROOT / wiki
    skip = {"SCHEMA.md","log.md","lint-report.md","index.md"}
    files = sorted([f.stem for f in d.glob("*.md") if f.name not in skip])
    return {"wiki": wiki, "count": len(files), "pages": files}

@app.get("/{wiki}/{page}", response_class=HTMLResponse)
def wiki_page(wiki: str, page: str):
    if wiki not in WIKIS:
        raise HTTPException(404)
    label, desc, color = WIKI_LABELS[wiki]
    f = KNOWLEDGE_ROOT / wiki / f"{page}.md"
    if not f.exists():
        raise HTTPException(404, f"Page '{page}' not found in {wiki}")
    text = f.read_text(encoding="utf-8")
    html = render_md(text)
    return f"""<!DOCTYPE html><html><head><title>{page} — {label}</title>{STYLE}</head><body>
    {nav([("Home","/"), (label, f"/{wiki}"), (page, None)], raw_url=f"/{wiki}/{page}/raw")}
    <div class="container"><div class="md-body">{html}</div></div></body></html>"""

@app.get("/{wiki}/{page}/raw", response_class=PlainTextResponse)
def wiki_page_raw(wiki: str, page: str):
    """Return raw markdown — LLM-friendly."""
    if wiki not in WIKIS:
        raise HTTPException(404)
    f = KNOWLEDGE_ROOT / wiki / f"{page}.md"
    if not f.exists():
        raise HTTPException(404)
    return f.read_text(encoding="utf-8")
