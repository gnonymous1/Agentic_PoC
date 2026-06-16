"""
Real-time WebSocket sandbox for conversing with a digital clone.
Endpoint: /api/v1/clone/sandbox
Bidirectional text/audio streaming with pgvector context retrieval and Gemini inference.
"""

import asyncio
import json
import logging
import os
from typing import Optional
from uuid import UUID, uuid4
import httpx
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import AgentProfile, CorporateKnowledgeVector
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clone", tags=["Clone Sandbox"])

GEMINI_CHAT_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:streamGenerateContent"
    f"?key={settings.gemini_api_key}"
)

_GEMINI_SAFETY_BLOCK_MEDIUM = [
    {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for c in [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
]

_SYSTEM_INSTRUCTION_TEMPLATE = """You are {agent_name}, a digital clone operating inside the Sovereign Executive Proxy Engine.
You are speaking on behalf of the actual human executive.

PERSONA INSTRUCTIONS:
{system_prompt}

BEHAVIORAL RULES:
1. Never break character — you ARE {agent_name}.
2. Use the knowledge context provided to answer factually.
3. If you don't know something, say so honestly rather than hallucinating.
4. Maintain the brand tone: {brand_tone}.
5. Keep responses concise and natural for a voice conversation.
6. Never reveal you are an AI clone unless explicitly asked and authorized.

CONTEXT FROM KNOWLEDGE BASE:
{knowledge_context}
"""


async def _generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dimensional embedding using Gemini embedding API."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"text-embedding-004:embedContent"
        f"?key={settings.gemini_api_key}"
    )
    payload = {
        "model": "models/text-embedding-004",
        "content": {"parts": [{"text": text[:3000]}]},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["embedding"]["values"]


async def _retrieve_knowledge(
    db_session: AsyncSession,
    client_id: UUID,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Perform async pgvector similarity search against the clone's knowledge base.
    Uses cosine distance via the HNSW index.
    """
    try:
        query_embedding = await _generate_embedding(query)
        embedding_json = json.dumps(query_embedding)

        sql = text(
            """
            SELECT content_chunk, title, source_type,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM corporate_knowledge_vectors
            WHERE client_id = :client_id
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
            """
        )
        rows = await db_session.execute(
            sql,
            {
                "embedding": embedding_json,
                "client_id": client_id,
                "top_k": top_k,
            },
        )
        results = []
        for row in rows:
            results.append({
                "content": row.content_chunk,
                "title": row.title,
                "source_type": row.source_type,
                "similarity": float(row.similarity) if row.similarity else 0.0,
            })
        return results

    except Exception as exc:
        logger.warning("Knowledge retrieval failed (non-fatal): %s", exc)
        return []


async def _stream_gemini_response(
    messages: list[dict],
    system_instruction: str,
    ws: WebSocket,
) -> str:
    """
    Stream a Gemini response token-by-token through the WebSocket.
    Returns the full concatenated response text.
    """
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": messages,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
            "topP": 0.9,
            "topK": 20,
        },
        "safetySettings": _GEMINI_SAFETY_BLOCK_MEDIUM,
    }

    full_text = ""
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", GEMINI_CHAT_ENDPOINT, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    chunk_str = line[6:]
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text_fragment = part.get("text", "")
                                if text_fragment:
                                    full_text += text_fragment
                                    await ws.send_json({
                                        "type": "token",
                                        "payload": {"text": text_fragment},
                                    })
                    except json.JSONDecodeError:
                        continue

    await ws.send_json({
        "type": "response_complete",
        "payload": {"full_text": full_text},
    })
    return full_text


@router.websocket("/sandbox")
async def clone_sandbox(
    ws: WebSocket,
    agent_profile_id: str = Query(None, description="UUID of the AgentProfile to converse with"),
    client_id: str = Query(None, description="UUID of the client account"),
):
    """
    Real-time bidirectional sandbox for testing a digital clone.
    - Sends text messages → clone responds with streaming text tokens
    - Automatically retrieves relevant knowledge from pgvector
    - Maintains conversation history within the session
    """
    await ws.accept()
    session_id = str(uuid4())
    logger.info("Clone sandbox session %s opening — agent_profile_id=%s", session_id, agent_profile_id)

    conversation_history: list[dict] = []
    agent_profile: Optional[AgentProfile] = None
    db_session: Optional[AsyncSession] = None

    try:
        if agent_profile_id:
            try:
                db_session = await anext(get_session())
                stmt = select(AgentProfile).where(AgentProfile.id == UUID(agent_profile_id))
                result = await db_session.execute(stmt)
                agent_profile = result.scalar_one_or_none()
            except Exception as exc:
                logger.warning("Could not load agent profile: %s", exc)
                await ws.send_json({
                    "type": "error",
                    "payload": {"message": f"Agent profile not found: {agent_profile_id}"},
                })
                await ws.close()
                return

        if not agent_profile:
            agent_profile = AgentProfile(
                agent_name="SEPE Digital Clone",
                system_prompt="You are a helpful executive assistant clone.",
                guardrails={"brand_tone": "professional"},
            )
            if client_id:
                try:
                    agent_profile.client_id = UUID(client_id)
                except Exception:
                    pass

        system_prompt = agent_profile.system_prompt or ""
        brand_tone = (agent_profile.guardrails or {}).get("brand_tone", "professional")

        await ws.send_json({
            "type": "sandbox_ready",
            "payload": {
                "session_id": session_id,
                "agent_name": agent_profile.agent_name,
                "brand_tone": brand_tone,
            },
        })

        while True:
            raw = await ws.receive()

            if raw["type"] == "websocket.disconnect":
                break

            text_message = None
            if raw.get("text"):
                text_message = raw["text"]
            elif raw.get("bytes"):
                await ws.send_json({
                    "type": "audio_ack",
                    "payload": {
                        "session_id": session_id,
                        "bytes_received": len(raw["bytes"]),
                    },
                })
                text_message = json.dumps({
                    "type": "audio_transcript_pending",
                    "text": "[Audio input received — ASR not yet connected]",
                })

            if text_message:
                try:
                    msg_data = json.loads(text_message)
                except json.JSONDecodeError:
                    msg_data = {"type": "text", "text": text_message}

                msg_type = msg_data.get("type", "text")
                msg_text = msg_data.get("text", msg_data.get("payload", {}).get("text", ""))

                if not msg_text:
                    continue

                if msg_type == "reset":
                    conversation_history = []
                    await ws.send_json({
                        "type": "reset_ack",
                        "payload": {"message": "Conversation reset"},
                    })
                    continue

                conversation_history.append({
                    "role": "user",
                    "parts": [{"text": msg_text}],
                })

                knowledge_context = ""
                if agent_profile and client_id and db_session:
                    try:
                        knowledge_docs = await _retrieve_knowledge(
                            db_session,
                            agent_profile.client_id,
                            msg_text,
                        )
                        if knowledge_docs:
                            knowledge_context = "\n\n".join(
                                f"[{d['source_type']}] {d['title']}:\n{d['content'][:500]}"
                                for d in knowledge_docs[:3]
                            )
                    except Exception as exc:
                        logger.warning("Knowledge retrieval error: %s", exc)

                system_instruction = _SYSTEM_INSTRUCTION_TEMPLATE.format(
                    agent_name=agent_profile.agent_name,
                    system_prompt=system_prompt,
                    brand_tone=brand_tone,
                    knowledge_context=knowledge_context or "No specific knowledge context loaded.",
                )

                max_history = conversation_history[-10:]
                gemini_messages = [
                    {"role": m["role"], "parts": m["parts"]}
                    for m in max_history
                ]

                response_text = await _stream_gemini_response(
                    gemini_messages,
                    system_instruction,
                    ws,
                )

                conversation_history.append({
                    "role": "model",
                    "parts": [{"text": response_text}],
                })

    except WebSocketDisconnect:
        logger.info("Sandbox session %s disconnected", session_id)
    except Exception as exc:
        logger.error("Sandbox session %s error: %s", session_id, exc, exc_info=True)
        try:
            await ws.send_json({
                "type": "error",
                "payload": {"message": f"Internal error: {str(exc)[:200]}"},
            })
        except Exception:
            pass
    finally:
        if db_session:
            await db_session.close()
        logger.info("Sandbox session %s closed", session_id)
