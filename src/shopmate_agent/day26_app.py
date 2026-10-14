"""Day 26 entrypoint: add a narrow performance guard to the working Day 25 app."""
import os

from shopmate_agent.perf_guard import AdmissionMiddleware, configured_guard
from shopmate_agent.public_demo import app

app.add_middleware(
    AdmissionMiddleware,
    guard=configured_guard(),
    timeout_seconds=float(os.getenv("SHOPMATE_STREAM_TIMEOUT_S", "60")),
)
