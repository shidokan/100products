"""
Outlander Gear RAG — FastAPI service
=====================================
Wraps the RAG pipeline in a REST endpoint plus a tiny HTML test page,
suitable for deployment to Azure Container Apps, Azure App Service, or
any Python container host.

Endpoints:
  GET  /             — simple HTML test page
  POST /chat         — JSON {"question": "...", "history": [...]} -> {"answer": "...", "citations": [...]}
  GET  /health       — health check (returns 200)

Run locally:
    uvicorn app:app --host 0.0.0.0 --port 8000

Run in a container:
    docker build -t outlander-rag .
    docker run -p 8000:8000 --env-file .env outlander-rag
"""

from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from outlander_rag import answer

app = FastAPI(
    title="Outlander Gear RAG Assistant",
    description="Retrieval-augmented chat over Outlander Gear Co. product catalog",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    question: str = Field(..., description="User question about Outlander Gear products")
    history: Optional[List[dict]] = Field(default_factory=list, description="Prior chat turns")


class ChatResponse(BaseModel):
    answer: str
    citations: List[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        reply, citations = answer(req.question, req.history or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG pipeline error: {e}")
    return ChatResponse(answer=reply, citations=citations)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Outlander Gear · RAG Product Assistant</title>
  <style>
    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface-2: #21262d;
      --border: #30363d;
      --text: #e6edf3;
      --text-dim: #8b949e;
      --accent: #58a6ff;
      --accent-hover: #79c0ff;
      --code-bg: #1f242c;
      --green: #56d364;
      --green-bg: rgba(46, 160, 67, 0.15);
      --red: #f85149;
      --red-bg: rgba(248, 81, 73, 0.10);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      -webkit-font-smoothing: antialiased;
    }
    .container {
      max-width: 880px;
      margin: 0 auto;
      width: 100%;
      padding: 0 1.5rem;
    }
    header {
      border-bottom: 1px solid var(--border);
      padding: 0.875rem 0;
    }
    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .logo {
      font-size: 1.05rem;
      font-weight: 600;
      letter-spacing: -0.01em;
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    }
    .logo-accent { color: var(--accent); }
    .nav-links { display: flex; gap: 0.5rem; align-items: center; }
    .nav-link {
      color: var(--text-dim);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.7rem;
      border-radius: 6px;
      font-size: 0.875rem;
      transition: all 0.15s;
    }
    .nav-link:hover { color: var(--text); background: var(--surface); }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.25rem 0.75rem;
      background: var(--green-bg);
      color: var(--green);
      border: 1px solid rgba(46, 160, 67, 0.4);
      border-radius: 99px;
      font-size: 0.78rem;
      font-weight: 500;
    }
    .status-dot {
      width: 7px; height: 7px;
      background: var(--green);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
    main { flex: 1; padding: 2rem 0; }
    h1 {
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      margin: 0 0 0.5rem;
    }
    .subtitle {
      color: var(--text-dim);
      margin: 0 0 1.25rem;
      font-size: 0.95rem;
    }
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-bottom: 1.75rem;
    }
    .badge {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 0.72rem;
      padding: 0.22rem 0.55rem;
      background: var(--code-bg);
      color: var(--text-dim);
      border: 1px solid var(--border);
      border-radius: 5px;
    }
    .badge.accent { color: var(--accent); border-color: rgba(88,166,255,0.3); }
    .samples-label {
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-bottom: 0.5rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .samples {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-bottom: 1rem;
    }
    .chip {
      font-family: inherit;
      font-size: 0.85rem;
      padding: 0.4rem 0.85rem;
      background: var(--surface);
      color: var(--text-dim);
      border: 1px solid var(--border);
      border-radius: 99px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover {
      background: var(--surface-2);
      color: var(--text);
      border-color: var(--accent);
    }
    textarea {
      width: 100%;
      min-height: 88px;
      padding: 0.85rem 1rem;
      font-family: inherit;
      font-size: 0.95rem;
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      resize: vertical;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(88,166,255,0.15);
    }
    .button-row {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      margin-top: 0.75rem;
    }
    button.primary {
      background: var(--accent);
      color: #0d1117;
      border: 0;
      padding: 0.65rem 1.5rem;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      border-radius: 8px;
      transition: background 0.15s;
      font-family: inherit;
    }
    button.primary:hover { background: var(--accent-hover); }
    button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .meta {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 0.8rem;
      color: var(--text-dim);
    }
    .kbd {
      font-family: ui-monospace, monospace;
      font-size: 0.72rem;
      padding: 0.1rem 0.4rem;
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-dim);
    }
    .answer-card {
      margin-top: 1.5rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
    }
    .answer-content {
      font-size: 0.97rem;
      line-height: 1.65;
    }
    .answer-content p { margin: 0 0 0.75rem; }
    .answer-content p:last-child { margin-bottom: 0; }
    .answer-content strong { color: #f0f6fc; font-weight: 600; }
    .citations {
      margin-top: 1.25rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
    }
    .citations-label {
      font-size: 0.72rem;
      color: var(--text-dim);
      margin-bottom: 0.5rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 600;
    }
    .citation-list { display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .citation-tag {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.3rem 0.6rem 0.3rem 0.5rem;
      background: var(--code-bg);
      color: var(--accent);
      border: 1px solid rgba(88,166,255,0.2);
      border-radius: 6px;
      font-family: ui-monospace, monospace;
      font-size: 0.78rem;
    }
    .citation-num { color: var(--text-dim); font-weight: 600; }
    .loading {
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      color: var(--text-dim);
    }
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .error {
      color: var(--red);
      background: var(--red-bg);
      padding: 0.75rem 1rem;
      border: 1px solid rgba(248,81,73,0.3);
      border-radius: 6px;
      font-size: 0.9rem;
    }
    footer {
      border-top: 1px solid var(--border);
      padding: 1.25rem 0;
      color: var(--text-dim);
      font-size: 0.82rem;
    }
    .footer-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.75rem;
    }
    .footer-tech { display: flex; gap: 1rem; align-items: center; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    @media (max-width: 640px) {
      h1 { font-size: 1.4rem; }
      .container { padding: 0 1rem; }
      .nav-link span.label { display: none; }
    }
  </style>
</head>
<body>
  <header>
    <div class="container header-content">
      <div class="logo">outlander<span class="logo-accent">·rag</span></div>
      <div class="nav-links">
        <span class="status-pill">
          <span class="status-dot"></span>
          Live
        </span>
        <a href="https://github.com/shidokan/100products" target="_blank" rel="noopener" class="nav-link">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
          <span class="label">Source</span>
        </a>
      </div>
    </div>
  </header>
  <main>
    <div class="container">
      <h1>Outlander Gear · Product Assistant</h1>
      <p class="subtitle">Retrieval-augmented chat over a 100-product outdoor-equipment catalog. Hybrid vector + keyword + semantic search; grounded responses with citations.</p>
      <div class="badges">
        <span class="badge accent">Azure AI Foundry</span>
        <span class="badge">gpt-4o</span>
        <span class="badge">text-embedding-ada-002</span>
        <span class="badge">Azure AI Search</span>
        <span class="badge">FastAPI</span>
        <span class="badge">Container Apps</span>
      </div>
      <div class="samples-label">Try a sample query</div>
      <div class="samples">
        <button class="chip" onclick="setQuery(this)">Which sleeping pad has the highest R-value?</button>
        <button class="chip" onclick="setQuery(this)">What's the cheapest climbing harness?</button>
        <button class="chip" onclick="setQuery(this)">Compare the kayaks available.</button>
        <button class="chip" onclick="setQuery(this)">Which tent is the most waterproof?</button>
        <button class="chip" onclick="setQuery(this)">What multi-tools do you sell?</button>
        <button class="chip" onclick="setQuery(this)">Show me items under $25.</button>
      </div>
      <textarea id="q" placeholder="Ask about products, prices, specs, or warranties..."></textarea>
      <div class="button-row">
        <button class="primary" id="askBtn" onclick="ask()">Ask</button>
        <span class="meta" id="timing"></span>
        <span class="meta" style="margin-left: auto;"><span class="kbd">⌘ Enter</span> to submit</span>
      </div>
      <div id="answerSection" style="display:none;">
        <div class="answer-card" id="answerCard"></div>
      </div>
    </div>
  </main>
  <footer>
    <div class="container footer-content">
      <span>100 products indexed · ~750 chunks · 1536-dim vectors · scale-to-zero</span>
      <div class="footer-tech">
        <a href="https://github.com/shidokan/100products" target="_blank" rel="noopener">GitHub</a>
        <span style="color: var(--border)">|</span>
        <span>MIT License</span>
      </div>
    </div>
  </footer>
  <script>
    function setQuery(btn) {
      const q = document.getElementById('q');
      q.value = btn.textContent;
      q.focus();
    }
    function escapeHTML(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function renderAnswer(text) {
      const escaped = escapeHTML(text);
      const withBold = escaped.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
      const paragraphs = withBold.split(/\\n\\s*\\n/).map(p => '<p>' + p.replace(/\\n/g, '<br>') + '</p>').join('');
      return paragraphs;
    }
    async function ask() {
      const q = document.getElementById('q').value.trim();
      if (!q) return;
      const btn = document.getElementById('askBtn');
      const section = document.getElementById('answerSection');
      const card = document.getElementById('answerCard');
      const timing = document.getElementById('timing');
      btn.disabled = true;
      btn.textContent = 'Thinking…';
      timing.textContent = '';
      section.style.display = 'block';
      card.innerHTML = '<span class="loading"><span class="spinner"></span>Retrieving and generating…</span>';
      const start = performance.now();
      try {
        const r = await fetch('/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({question: q})
        });
        const data = await r.json();
        const elapsed = ((performance.now() - start) / 1000).toFixed(1);
        if (!r.ok) {
          card.innerHTML = '<div class="error">' + escapeHTML(data.detail || r.statusText) + '</div>';
          return;
        }
        const content = '<div class="answer-content">' + renderAnswer(data.answer) + '</div>';
        const cites = (data.citations || []).map((c, i) =>
          '<span class="citation-tag"><span class="citation-num">[' + (i+1) + ']</span>' + escapeHTML(c) + '</span>'
        ).join('');
        const citationsBlock = cites ?
          '<div class="citations"><div class="citations-label">Sources</div><div class="citation-list">' + cites + '</div></div>' : '';
        card.innerHTML = content + citationsBlock;
        timing.textContent = elapsed + 's · ' + (data.citations || []).length + ' sources';
      } catch (e) {
        card.innerHTML = '<div class="error">' + escapeHTML(e.message) + '</div>';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Ask';
      }
    }
    document.getElementById('q').addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') ask();
    });
  </script>
</body>
</html>"""
