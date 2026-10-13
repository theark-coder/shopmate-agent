"""Day 25 public preview app; reuses Day 22/23 routes without replacing them."""
from fastapi.responses import HTMLResponse

from shopmate_agent.embedding_index import ROOT
from shopmate_agent.health_api import router as health_router
from shopmate_agent.stream_api import app

app.include_router(health_router)


@app.get("/day25", response_class=HTMLResponse, include_in_schema=False)
def preview_page():
    return (ROOT / "web/day25.html").read_text(encoding="utf-8")
