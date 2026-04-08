"""
Wolf Wiki Browser — serves the three LLM wikis (the-forge, the-brain, the-blueprint)
- Renders .md as HTML with [[wikilink]] support
- Serves raw markdown at /<wiki>/<page>/raw for LLM scraping
- Lists pages as JSON at /<wiki>/_list
NAS mounted at /mnt/hex-data on ub24. Run: uvicorn app:app --host 0.0.0.0 --port 3010
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from pathlib import Path
import markdown2, re

app = FastAPI(title="Wolf Wiki")

KNOWLEDGE_ROOT = Path("/mnt/hex-data/knowledge")
WIKIS = ["the-forge", "the-brain", "the-blueprint"]
WIKI_LABELS = {
    "the-forge":     ("The Forge",     "YouTube & research knowledge base", "#e67e22"),
    "the-brain":     ("The Brain",     "Hex personal knowledge base",       "#3498db"),
    "the-blueprint": ("The Blueprint", "Wolf/OpenClaw ecosystem",            "#9b59b6"),
}
SKIP = {"SCHEMA.md", "log.md", "lint-report.md"}

STYLE = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.nav { background: #161b22; padding: 12px 24px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.nav h1 { font-size: 16px; font-weight: 600; color: #f0f6fc; }
.nav .bc { color: #8b949e; font-size: 14px; flex: 1; }
.raw-link { font-size: 12px; background: #21262d; padding: 4px 10px; border-radius: 6px; color: #8b949e; white-space: nowrap; }
.container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
.wiki-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-top: 24px; }
.wiki-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; transition: border-color .2s; }
.wiki-card:hover { border-color: #58a6ff; }
.wiki-card h2 { font-size: 18px; margin-bottom: 8px; }
.wiki-card p { font-size: 13px; color: #8b949e; margin-bottom: 12px; }
.wiki-card .cnt { font-size: 12px; color: #8b949e; }
.search-wrap { margin-bottom: 20px; }
.search-box { width: 100%; padding: 10px 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; color: #e0e0e0; font-size: 14px; }
.search-box:focus { outline: none; border-color: #58a6ff; }
.page-list { columns: 2; gap: 24px; }
.page-list a { display: block; padding: 4px 0; font-size: 14px; break-inside: avoid; }
/* Markdown body */
.md h1,.md h2,.md h3 { color: #f0f6fc; margin: 24px 0 10px; }
.md h1 { font-size: 26px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
.md h2 { font-size: 20px; }
.md h3 { font-size: 16px; }
.md p { line-height: 1.75; margin: 12px 0; color: #c9d1d9; }
.md ul,.md ol { padding-left: 24px; margin: 10px 0; }
.md li { margin: 5px 0; line-height: 1.65; color: #c9d1d9; }
.md code { background: #21262d; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #e6db74; }
.md pre { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 16px 0; }
.md pre code { background: none; padding: 0; color: #c9d1d9; }
.md table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
.md th { background: #21262d; padding: 8px 12px; text-align: left; border: 1px solid #30363d; }
.md td { padding: 8px 12px; border: 1px solid #30363d; color: #c9d1d9; }
.md blockquote { border-left: 3px solid #30363d; padding-left: 16px; color: #8b949e; margin: 12px 0; }
.md hr { border: none; border-top: 1px solid #30363d; margin: 24px 0; }
.frontmatter { display: none; }
@media(max-width:700px){ .wiki-grid{grid-template-columns:1fr;} .page-list{columns:1;} }
</style>
"""

def page_count(wiki):
    d = KNOWLEDGE_ROOT / wiki
    if not d.exists(): return 0
    return len([f for f in d.glob("*.md") if f.name not in SKIP and f.name != "index.md"])

def resolve_wikilink(slug, wiki):
    """Convert [[slug]] to a browsable URL."""
    slug = slug.strip().lower().replace(" ", "-")
    return f"/{wiki}/{slug}"

def render_md(text, wiki=None):
    # Strip YAML frontmatter
    text = re.sub(r"^---\n.*?\n---\n?", "", text, flags=re.DOTALL)
    # Convert [[slug|label]] and [[slug]] to markdown links
    def wikirepl(m):
        inner = m.group(1)
        if "|" in inner:
            slug, label = inner.split("|", 1)
        else:
            slug = label = inner
        href = resolve_wikilink(slug, wiki) if wiki else f"#{slug.strip().lower().replace(' ','-')}"
        return f"[{label.strip()}]({href})"
    text = re.sub(r"\[\[([^\]]+)\]\]", wikirepl, text)
    return markdown2.markdown(text, extras=["tables", "fenced-code-blocks", "strike", "header-ids", "smarty-pants"])

def nav_html(crumbs, raw_url=None):
    sep = ' <span style="color:#30363d">›</span> '
    bc = sep.join(f'<a href="{u}">{t}</a>' if u else f'<span style="color:#f0f6fc">{t}</span>' for t, u in crumbs)
    raw = f'<a class="raw-link" href="{raw_url}">📄 raw</a>' if raw_url else ""
    return f'<nav class="nav"><h1>🐺 Wolf Wiki</h1><span class="bc">{bc}</span>{raw}</nav>'

def html_page(title, body, crumbs, raw_url=None):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — Wolf Wiki</title>{STYLE}</head><body>{nav_html(crumbs, raw_url)}<div class="container">{body}</div></body></html>"""

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    cards = ""
    for w in WIKIS:
        label, desc, color = WIKI_LABELS[w]
        cnt = page_count(w)
        cards += f'<a href="/{w}" style="text-decoration:none"><div class="wiki-card"><h2 style="color:{color}">{label}</h2><p>{desc}</p><span class="cnt">{cnt:,} pages</span></div></a>'
    body = f"""
      <h2 style="color:#f0f6fc;margin-bottom:6px">Wolf Wiki</h2>
      <p style="color:#8b949e;margin-bottom:24px">Three persistent LLM knowledge bases.
        Browse interactively or scrape raw markdown via <code>/&lt;wiki&gt;/&lt;page&gt;/raw</code>.
        List pages as JSON via <code>/&lt;wiki&gt;/_list</code>.</p>
      <div class="wiki-grid">{cards}</div>"""
    return html_page("Home", body, [("Home", None)])

@app.get("/{wiki}", response_class=HTMLResponse)
def wiki_home(wiki: str):
    if wiki not in WIKIS: raise HTTPException(404)
    label, desc, color = WIKI_LABELS[wiki]
    d = KNOWLEDGE_ROOT / wiki
    index_file = d / "index.md"
    if index_file.exists():
        content = render_md(index_file.read_text(encoding="utf-8"), wiki=wiki)
        body = f'<div class="md">{content}</div>'
    else:
        files = sorted([f for f in d.glob("*.md") if f.name not in SKIP and f.name != "index.md"])
        links = "".join(f'<a href="/{wiki}/{f.stem}">{f.stem.replace("-"," ").title()}</a>' for f in files)
        body = f'<h2 style="color:{color};margin-bottom:16px">{label}</h2><div class="page-list">{links}</div>'
    return html_page(label, body, [("Home", "/"), (label, None)], raw_url=f"/{wiki}/index/raw")

@app.get("/{wiki}/index/raw", response_class=PlainTextResponse)
def wiki_index_raw(wiki: str):
    if wiki not in WIKIS: raise HTTPException(404)
    f = KNOWLEDGE_ROOT / wiki / "index.md"
    if not f.exists(): raise HTTPException(404, "index.md not found")
    return f.read_text(encoding="utf-8")

@app.get("/{wiki}/_list", response_class=JSONResponse)
def wiki_list(wiki: str):
    if wiki not in WIKIS: raise HTTPException(404)
    d = KNOWLEDGE_ROOT / wiki
    pages = sorted([f.stem for f in d.glob("*.md") if f.name not in SKIP and f.name != "index.md"])
    return {"wiki": wiki, "count": len(pages), "pages": pages,
            "raw_base": f"http://192.168.1.59:3010/{wiki}"}

@app.get("/{wiki}/{page}", response_class=HTMLResponse)
def wiki_page(wiki: str, page: str):
    if wiki not in WIKIS: raise HTTPException(404)
    label, _, color = WIKI_LABELS[wiki]
    f = KNOWLEDGE_ROOT / wiki / f"{page}.md"
    if not f.exists(): raise HTTPException(404, f"'{page}' not found in {wiki}")
    text = f.read_text(encoding="utf-8")
    html = render_md(text, wiki=wiki)
    title = page.replace("-", " ").title()
    body = f'<div class="md">{html}</div>'
    return html_page(title, body, [("Home","/"), (label, f"/{wiki}"), (title, None)], raw_url=f"/{wiki}/{page}/raw")

@app.get("/{wiki}/{page}/raw", response_class=PlainTextResponse)
def wiki_page_raw(wiki: str, page: str):
    if wiki not in WIKIS: raise HTTPException(404)
    f = KNOWLEDGE_ROOT / wiki / f"{page}.md"
    if not f.exists(): raise HTTPException(404)
    return f.read_text(encoding="utf-8")
