"""
FastAPI backend — Skylark Drones BI Agent.

Architecture:
  Browser → FastAPI → Monday GraphQL API (read-only)
                   → Deterministic Python Analytics
                   → LLM (Gemini → Groq → Deterministic fallback)

The LLM NEVER directly calls Monday.com.
All business data retrieval and calculation is done by Python.
The LLM only handles: intent detection, parameter extraction, and
converting structured analytical results into executive-friendly language.

Endpoints:
  GET  /health   → health check (no secrets exposed)
  POST /chat     → main conversational endpoint
  GET  /         → API info
"""
import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import List, Optional

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from backend.config import FRONTEND_URL, MONDAY_API_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Skylark Drones BI Agent",
    description=(
        "AI-powered Business Intelligence for Skylark Drones. "
        "Queries Monday.com (read-only) and uses free LLM for executive insights."
    ),
    version="1.0.0",
)

# CORS: allow frontend origins
# Load CORS origins from environment, with local fallbacks
frontend_urls_env = os.getenv("FRONTEND_URLS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [url.strip() for url in frontend_urls_env.split(",") if url.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response models ────────────────────────────────────────────────

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []


class ChatResponse(BaseModel):
    response: str
    intent: str
    sector: Optional[str] = None
    period: Optional[str] = None
    sources: List[str] = []
    data_quality: dict = {}
    analytics_used: Optional[List[str]] = None
    filters: dict = {}
    timestamp: str = ""


# ─── Agent singleton ───────────────────────────────────────────────────────────

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from backend.agent.agent import BIAgent
        _agent = BIAgent()
    return _agent


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """
    Health check. Never exposes API tokens or secrets.
    Indicates whether Monday token is configured (not its value).
    """
    return {
        "status": "ok",
        "monday_configured": bool(MONDAY_API_TOKEN),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint.

    Flow (backend-controlled, LLM never touches Monday directly):
      1. Validate request
      2. Run agent.chat() in thread pool (non-blocking)
         a. Monday GraphQL fetch → normalize → deterministic analytics
         b. Build structured context from analytics results
         c. LLM generates natural-language response from context
         d. If LLM fails → deterministic structured fallback
      3. Return ChatResponse (no secrets exposed)
    """
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if not MONDAY_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=(
                "Monday.com API token not configured. "
                "Set MONDAY_API_TOKEN environment variable."
            ),
        )

    agent = _get_agent()
    history = [{"role": m.role, "content": m.content} for m in (request.history or [])]

    # Run synchronous agent in a thread pool so we don't block the event loop.
    # Monday API + LLM calls can take 5-30 seconds; this keeps uvicorn responsive.
    try:
        result = await asyncio.to_thread(
            agent.chat, message, history
        )
    except Exception as exc:
        logger.exception("Unhandled error in agent.chat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error. Please try again.")

    # Build source list for transparency
    sources = []
    analytics = result.get("analytics_used", [])
    if any(k in analytics for k in ("pipeline", "deals_analysis", "sector_analysis", "cross_board")):
        sources.append("Deals Board")
    if any(k in analytics for k in ("revenue", "operations", "work_order_analysis", "cross_board")):
        sources.append("Work Orders Board")
    if "leadership_update" in analytics:
        sources = ["Deals Board", "Work Orders Board"]

    # Build filter info for transparency
    filters = {}
    if result.get("sector"):
        filters["sector"] = result["sector"]
    if result.get("period"):
        filters["period"] = result["period"]

    return ChatResponse(
        response=result.get("response", "I encountered an error. Please try again."),
        intent=result.get("intent", "unknown"),
        sector=result.get("sector"),
        period=result.get("period"),
        sources=sources,
        data_quality=result.get("data_quality", {}),
        analytics_used=analytics,
        filters=filters,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """
    Streaming SSE endpoint.
    Streams progress events before returning the final response.
    """
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if not MONDAY_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=(
                "Monday.com API token not configured. "
                "Set MONDAY_API_TOKEN environment variable."
            ),
        )

    agent = _get_agent()
    history = [{"role": m.role, "content": m.content} for m in (request.history or [])]
    
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_callback(event: dict):
        # We need to run this thread-safely because the callback runs in the thread pool
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    async def event_generator():
        # Start background task
        task = asyncio.create_task(asyncio.to_thread(agent.chat, message, history, progress_callback))
        
        while not task.done():
            try:
                # Wait for an event with timeout so we can check if client disconnected
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                if await req.is_disconnected():
                    task.cancel()
                    break

        # Flush any remaining events
        while not queue.empty():
            event = queue.get_nowait()
            yield f"data: {json.dumps(event)}\n\n"
            
        # Get final result or handle error
        if not task.cancelled():
            try:
                result = task.result()
                
                # Build source list for transparency
                sources = []
                analytics = result.get("analytics_used", [])
                if any(k in analytics for k in ("pipeline", "deals_analysis", "sector_analysis", "cross_board")):
                    sources.append("Deals Board")
                if any(k in analytics for k in ("revenue", "operations", "work_order_analysis", "cross_board")):
                    sources.append("Work Orders Board")
                if "leadership_update" in analytics:
                    sources = ["Deals Board", "Work Orders Board"]
                
                filters = {}
                if result.get("sector"):
                    filters["sector"] = result["sector"]
                if result.get("period"):
                    filters["period"] = result["period"]

                final_resp = {
                    "stage": "complete",
                    "status": "complete",
                    "message": "Generated final response",
                    "data": {
                        "response": result.get("response", "I encountered an error. Please try again."),
                        "intent": result.get("intent", "unknown"),
                        "sector": result.get("sector"),
                        "period": result.get("period"),
                        "sources": sources,
                        "data_quality": result.get("data_quality", {}),
                        "analytics_used": analytics,
                        "filters": filters,
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                yield f"data: {json.dumps(final_resp)}\n\n"
            except Exception as exc:
                logger.exception("Unhandled error in agent.chat: %s", exc)
                error_resp = {
                    "stage": "error",
                    "status": "error",
                    "message": "Internal error. Please try again.",
                    "data": {}
                }
                yield f"data: {json.dumps(error_resp)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/")
async def root():
    """API info — no secrets exposed."""
    return {
        "service": "Skylark Drones BI Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "chat": "POST /chat",
        "chat_stream": "POST /chat/stream",
        "monday_source": "read-only",
    }
