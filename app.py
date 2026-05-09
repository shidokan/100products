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
<html><head><meta charset="utf-8"><title>Outlander Gear Assistant</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }
  h1 { color: #1F3864; }
  textarea { width: 100%; min-height: 80px; font-size: 1rem; padding: 0.5rem; }
  button { background: #1F3864; color: white; border: 0; padding: 0.6rem 1.2rem; font-size: 1rem; cursor: pointer; }
  button:hover { background: #2E74B5; }
  #answer { background: #f4f6fa; padding: 1rem; margin-top: 1rem; border-radius: 4px; white-space: pre-wrap; }
  .citations { color: #666; font-size: 0.9rem; margin-top: 0.5rem; }
  .loading { color: #888; font-style: italic; }
</style></head><body>
<h1>Outlander Gear — Product Assistant</h1>
<p>Ask about products, prices, specs, and warranties from the Outlander Gear catalog.</p>
<textarea id="q" placeholder="e.g. Which tent is the most waterproof?"></textarea>
<br><br>
<button onclick="ask()">Ask</button>
<div id="answer"></div>
<script>
async function ask() {
  const q = document.getElementById("q").value.trim();
  if (!q) return;
  const out = document.getElementById("answer");
  out.innerHTML = '<span class="loading">Thinking...</span>';
  try {
    const r = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q})
    });
    const data = await r.json();
    if (!r.ok) {
      out.innerHTML = "Error: " + (data.detail || r.statusText);
      return;
    }
    let cites = (data.citations || []).map((c,i) => "[" + (i+1) + "] " + c).join("<br>");
    out.innerHTML = data.answer + '<div class="citations">' + cites + '</div>';
  } catch (e) {
    out.innerHTML = "Error: " + e.message;
  }
}
</script>
</body></html>"""
