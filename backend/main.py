from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from agent import PostExplainerAgent
from models import ExplainRequest, ExplainResponse

app = FastAPI(title="Post Explainer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = PostExplainerAgent()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/explain", response_model=ExplainResponse)
async def explain_post(request: ExplainRequest):
    """
    Takes a social media post URL or raw text and returns 3-5 bullet point explanations
    with context from web search.
    """
    try:
        result = await agent.explain(
            url=request.url,
            text=request.text,
            image_url=request.image_url,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare")
async def compare_providers(request: ExplainRequest):
    """
    Optional: Compare explanations across multiple LLM providers.
    """
    try:
        result = await agent.compare_providers(
            url=request.url,
            text=request.text,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
