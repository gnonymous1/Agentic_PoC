"""
SEPE — Sovereign Executive Proxy Engine
RAIG Agent System: Research, Asymmetric Critic, Information Copywriter, Grounded Voice

This module implements the RAIG content manufacturing pipeline:
  - Node B (Research): Grounded fact search via 'gemini-3.1-flash-lite' with googleSearch tools.
  - Node C (Copywriting): Multi-platform layouts via 'deepseek/deepseek-v4-flash:free'.
  - Node D (Adversarial Critic): Alignment check via 'nvidia/nemotron-3-super'.
  - Self-Healing Loops: Auto-correction on style, jargon, or syntax errors.
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field, ValidationError
import httpx

logger = logging.getLogger(__name__)

# ===========================================================================
# 1. PYDANTIC STRUCURED LAYOUT SCHEMAS
# ===========================================================================

class TwitterContent(BaseModel):
    posts: List[str] = Field(
        ...,
        description="A thread of 5 to 10 conversational posts, each post strictly under 240 characters."
    )


class LinkedInContent(BaseModel):
    body: str = Field(
        ...,
        description="Analytical, metric-driven corporate post with clean spacing and bullet points."
    )


class BlogspotContent(BaseModel):
    title: str = Field(..., description="SEO-Optimized technical article title.")
    html_body: str = Field(
        ...,
        description="Long-form technical article in semantic HTML5 markup (using h2, h3, strong tags, list elements), min 600 words."
    )


class MultiPlatformPayload(BaseModel):
    """Unified layout contract generated for targeted communication networks."""
    twitter: TwitterContent
    linkedin: LinkedInContent
    blogspot: BlogspotContent


# ===========================================================================
# 2. PROMPT TEMPLATES & SYSTEM INSTRUCTIONS
# ===========================================================================

RESEARCH_SYSTEM_PROMPT = """You are the lead SEPE Research and Grounding Agent.
Your objective is to:
1. Accept a trend signal or news topic from the operator.
2. Search and verify facts using real-time search grounding.
3. Strip out internet junk, clickbait, advertising tracking blocks, and fluff.
4. Output a comprehensive plain-text Unified Truth Document (UTD) containing verified data points, inline source citations, and clear labels for unverified claims.

Format Rules:
- Output only the clean factual summary. Do not include introductory conversational text or markdown fences.
- Cite sources inline using bracketed domain names, e.g., [bloomberg.com].
- Highlight unverified rumors clearly as [UNVERIFIED].
- Minimum word count: 400 words.
"""

COPYWRITING_SYSTEM_PROMPT = """You are the SEPE Omni-Channel Copywriting Agent.
Your job is to transform the provided Unified Truth Document (UTD) into structured corporate and social content.
You must adhere strictly to the executive persona guidelines provided.

You MUST format your output as a single, valid JSON object matching the following schema:
{
  "twitter": {
    "posts": [
      "Tweet 1 (max 240 characters)...",
      "Tweet 2 (max 240 characters)..."
    ]
  },
  "linkedin": {
    "body": "Analytical, metric-driven post...",
    "hashtags": ["#Tag1"]
  },
  "blogspot": {
    "title": "Technical Article Title",
    "html_body": "<h2>Intro</h2><p>Deep dive with <strong>metrics</strong>...</p>"
  }
}

RULES:
1. Twitter Thread: 5-10 sequential posts. Every post MUST be 240 characters or fewer.
2. LinkedIn Post: Deep corporate analysis. Use spacing, bullet points (•), and lead with concrete metrics.
3. Blogspot Post: Semantic HTML5 long-form article. Must use <h2>, <h3>, <strong>, and lists. Minimum 600 words of textual HTML content.
4. ABSOLUTE BAN on AI fluff words: delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge.
5. All numbers and claims must match the facts in the UTD exactly. Do not hallucinate metrics.
"""

CRITIC_SYSTEM_PROMPT = """You are the SEPE Asymmetric Critic Alignment Filter.
Your role is to run adversarial quality control and grammatical/stylistic checks on generated executive clone content.

You MUST analyze the content payloads and check for:
1. Occurrence of banned generic AI terminology ("delve", "testament", "revolutionizing", "moreover", "groundbreaking", "game-changer", "leverage", "synergy", "cutting-edge").
2. Twitter length limits (each post MUST be under 240 characters).
3. Twitter thread size (must be between 5 and 10 posts).
4. LinkedIn layout requirements (proper line spacing, analytical executive tone, clear bullet lists).
5. Blogspot markup validation (valid semantic HTML5, min 600 words).
6. Consistency with the high-authority corporate brand voice.

You MUST return a JSON object with this exact structure (no markdown wrapper, no other text):
{
  "approved": false,
  "refinement_notes": "A list of specific defects spotted and instructions for the copywriter to fix them."
}
Set approved to true ONLY if there are zero styling, linguistic, or structural violations.
"""


# ===========================================================================
# 3. RAIG CONTENT FACTORY ENGINE IMPLEMENTATION
# ===========================================================================

class ContentFactoryEngine:
    """Manages the full RAIG pipeline: Research -> Copywriting -> Critic -> Self-Healing."""

    def __init__(self, gemini_key: str, openrouter_key: str):
        self.gemini_key = gemini_key
        self.openrouter_key = openrouter_key
        
        if not self.gemini_key or self.gemini_key == "mock-key-for-simulation":
            raise ValueError("PRODUCTION SECURITY BOUNDARY: Active, valid 'GEMINI_API_KEY' required for RAIG.")
        if not self.openrouter_key or self.openrouter_key == "mock-key-for-simulation":
            raise ValueError("PRODUCTION SECURITY BOUNDARY: Active, valid 'OPENROUTER_API_KEY' required for RAIG.")
            
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

    async def execute_web_research(self, topic: str, persona_prompt: str) -> str:
        """
        [Node B: Research and Grounding Agent]
        Model Target: gemini-3.1-flash-lite
        Configuration: generationConfig: {"responseMimeType": "text/plain"}, tools: [{"googleSearch": {}}]
        """
        logger.info("RAIG Node B: Starting fact grounding via gemini-3.1-flash-lite on topic: '%s'", topic)
        
        payload = {
            "systemInstruction": {"parts": [{"text": RESEARCH_SYSTEM_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": f"Grounded research on trend: {topic}\nPersona constraints: {persona_prompt}"}]}
            ],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "text/plain"
            }
        }
        
        url_with_key = f"{self.gemini_url}?key={self.gemini_key}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url_with_key, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
        try:
            utd = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("RAIG Node B: Unified Truth Document synthesized successfully. UTD length: %d chars.", len(utd))
            return utd.strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Failed to parse Gemini 3.1 grounding response: {exc}")

    async def generate_draft(
        self, utd: str, persona_prompt: str, critic_feedback: Optional[str] = None
    ) -> MultiPlatformPayload:
        """
        [Node C: Omni-Channel Copywriting Agent]
        Model Target: deepseek/deepseek-v4-flash:free
        Configuration: Strict JSON schema validations mapping to platform contracts.
        """
        logger.info("RAIG Node C: Generating platform drafts via deepseek/deepseek-v4-flash:free...")
        
        system_instructions = COPYWRITING_SYSTEM_PROMPT
        user_message = f"Unified Truth Document:\n\n{utd}\n\nPersona prompt: {persona_prompt}"
        
        if critic_feedback:
            user_message += (
                f"\n\nCRITICAL ERROR FEEDBACK FROM PREVIOUS RUN:\n"
                f"{critic_feedback}\n"
                f"You MUST fix every error listed above in the updated output payload."
            )

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Copywriter"
        }
        
        payload = {
            "model": "deepseek/deepseek-v4-flash:free",
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(self.openrouter_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_json = data["choices"][0]["message"]["content"]
            parsed_dict = json.loads(raw_json)
            # Enforce strongly typed data contracts through Pydantic guardrails
            return MultiPlatformPayload.model_validate(parsed_dict)
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            logger.error("RAIG Node C: Data contract validation failed: %s", exc)
            raise RuntimeError(f"Failed to generate valid copywriting layout contracts: {exc}")

    async def evaluate_with_critic(self, draft: MultiPlatformPayload) -> Tuple[bool, str]:
        """
        [Node D: Asymmetric Critic Verification Loop]
        Model Target: nvidia/nemotron-3-super (Critic Mode)
        """
        logger.info("RAIG Node D: Executing asymmetric critic check via nvidia/nemotron-3-super...")
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Critic"
        }
        
        draft_str = json.dumps(draft.model_dump(), indent=2)
        payload = {
            "model": "nvidia/nemotron-3-super",
            "messages": [
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": f"Critique this payload:\n{draft_str}"}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.openrouter_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_response = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_response)
            approved = bool(parsed.get("approved", False))
            notes = str(parsed.get("refinement_notes", ""))
            return approved, notes
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.warning("RAIG Node D: Critic API decode failed, falling back to local verification: %s", exc)
            return self._heuristic_check(draft)

    def _heuristic_check(self, draft: MultiPlatformPayload) -> Tuple[bool, str]:
        """Heuristic safety verification check fallback."""
        banned = ["delve", "testament", "revolutionizing", "moreover", "groundbreaking", "game-changer", "leverage", "synergy", "cutting-edge"]
        failures = []
        
        if not (5 <= len(draft.twitter.posts) <= 10):
            failures.append("Twitter thread size must be between 5 and 10 posts.")
        for i, post in enumerate(draft.twitter.posts):
            if len(post) > 240:
                failures.append(f"Tweet {i+1} exceeds 240 characters.")
            for word in banned:
                if word in post.lower():
                    failures.append(f"Tweet {i+1} contains banned AI word '{word}'.")
                    
        text_corpus = (draft.linkedin.body + draft.blogspot.html_body).lower()
        for word in banned:
            if word in text_corpus:
                failures.append(f"Body payload contains banned word: '{word}'.")

        if len(draft.blogspot.html_body.split()) < 300:
            failures.append("Blogspot HTML body size is below executive publication length.")

        if failures:
            return False, "HEURISTIC DEFECTS: " + "; ".join(failures)
        return True, "Heuristic pass."

    async def execute_publishing_pipeline(
        self, topic: str, persona_prompt: str, max_healing_turns: int = 3
    ) -> Tuple[MultiPlatformPayload, str, bool]:
        """
        Orchestrates the entire RAIG DAG state machine:
        Node B (Gemini 3.1) -> Node C (DeepSeek-v4) -> Node D (Nemotron Critic Loop) -> Self-Healing Rewrites.
        """
        utd = await self.execute_web_research(topic, persona_prompt)
        
        critic_feedback = None
        current_draft = None
        approved = False
        
        for turn in range(1, max_healing_turns + 1):
            logger.info("RAIG DAG Pipeline: Turn %d/%d", turn, max_healing_turns)
            
            # 1. Copywriting Generator
            current_draft = await self.generate_draft(
                utd=utd, persona_prompt=persona_prompt, critic_feedback=critic_feedback
            )
            
            # 2. Adversarial Critic Cross-Examination
            approved, critic_feedback = await self.evaluate_with_critic(current_draft)
            
            if approved:
                logger.info("RAIG Node D: Critic verification PASSED on turn %d.", turn)
                break
            else:
                logger.warning(
                    "RAIG Node D: Critic verification FAILED. Triggering Self-Healing Loop on turn %d. Notes: %s",
                    turn, critic_feedback
                )
                
        if not approved:
            logger.error("RAIG DAG Pipeline: Failed to heal content defects after %d turns.", max_healing_turns)
            
        return current_draft, utd, approved
