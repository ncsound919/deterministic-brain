from __future__ import annotations

from fastapi import FastAPI
from schemas.api import ChatRequest, ChatResponse
from orchestration.langgraph_app import build_app

app = FastAPI(title='Lane-First Deterministic Brain')
brain = build_app()

@app.post('/chat', response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    result = brain.run(payload.query)
    return ChatResponse(
        lane=result['lane'],
        status=result['status'],
        output_mode=result['output_mode'],
        final_output=result['final_output'],
        confidence=result['confidence'],
        tool_calls=result.get('tool_calls', []),
        verification_results=result.get('verification_results', []),
    )
