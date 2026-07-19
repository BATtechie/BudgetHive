"""
A2 — Need / Want Agent
======================
Two-step flow:
  Step 1 (no history)  → generate_questions():
                          LLM generates 3-4 open-ended, product-specific
                          questions. NO options — user types freely.
  Step 2               → run_need_agent():
                          LLM reads the free-text answers and scores.
                          OR uses purchase history for returning users.
"""

import json
import logging
from enum import Enum
from typing import List, Optional, Dict

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Classification tiers
# ------------------------------------------------------------------
class NeedClassification(str, Enum):
    ESSENTIAL_NEED = "ESSENTIAL_NEED"   # Medical, work-critical, safety
    STRONG_WANT    = "STRONG_WANT"      # Genuinely useful, improves life
    MODERATE_WANT  = "MODERATE_WANT"    # Nice-to-have, not urgent
    WEAK_WANT      = "WEAK_WANT"        # Low utility, rarely used
    IMPULSE        = "IMPULSE"          # Emotional / hype / social pressure


# ------------------------------------------------------------------
# Structured output models
# ------------------------------------------------------------------
class ClarifyingQuestion(BaseModel):
    """A single open-ended question — no options, user types freely."""
    question: str = Field(
        ...,
        description="An open-ended question the user answers in their own words.",
    )


class NeedQuestions(BaseModel):
    """
    Returned by Step 1 (generate_questions).
    Contains product-specific open questions the UI renders as text inputs.
    """
    questions: List[ClarifyingQuestion] = Field(
        ...,
        description="3–4 open-ended questions for this specific product.",
    )
    reason_for_asking: str = Field(
        ...,
        description="One sentence telling the user why we're asking.",
    )


class NeedEvaluation(BaseModel):
    """Returned by Step 2. The final scored output."""
    score: float = Field(
        ..., ge=0, le=100,
        description="0 = pure impulse, 100 = absolute essential need.",
    )
    classification: NeedClassification
    reasoning: str = Field(
        ...,
        description="Explanation referencing exactly what the user said.",
    )
    data_source: str = Field(
        ...,
        description="'USER_ANSWERS' or 'PURCHASE_HISTORY'.",
    )


# ------------------------------------------------------------------
# Fallbacks
# ------------------------------------------------------------------
_FALLBACK_QUESTIONS = NeedQuestions(
    questions=[
        ClarifyingQuestion(question="Do you already own something similar? If yes, what's its condition?"),
        ClarifyingQuestion(question="What would you use this for, and how often?"),
        ClarifyingQuestion(question="Is there a specific reason you need this right now?"),
    ],
    reason_for_asking="Your answers help us give you an accurate, personalised verdict.",
)

_FALLBACK_EVALUATION = NeedEvaluation(
    score=50.0,
    classification=NeedClassification.MODERATE_WANT,
    reasoning="Could not reach the AI model — defaulting to a neutral score.",
    data_source="FALLBACK",
)


# ------------------------------------------------------------------
# System prompts
# ------------------------------------------------------------------
_QUESTION_SYSTEM_PROMPT = """
You are the Need/Utility Agent for BudgetHive, an AI purchase decision assistant.

Your job in this step is to generate 3–4 open-ended questions about a product
the user wants to buy. These questions must be short, natural, and conversational.

Critical rules:
- Questions must be SPECIFIC to this exact product — not generic.
- Do NOT provide multiple-choice options. The user must type their own answer.
- Ask about: current ownership/situation, intended use, frequency, urgency.
- Write questions as if a knowledgeable friend is asking — friendly, not formal.
- Return ONLY valid JSON. No markdown. No extra text.
""".strip()

_EVAL_SYSTEM_PROMPT = """
You are the Need/Utility Agent for BudgetHive, an AI purchase decision assistant.

Your job is to read what the user wrote in their own words and judge how much
of a genuine NEED this purchase is vs a WANT or IMPULSE.

Classification guide:
  ESSENTIAL_NEED  (85-100): Medical, work-critical, safety, or survival item.
  STRONG_WANT     (65-84) : Genuinely useful, used frequently, hard to substitute.
  MODERATE_WANT   (40-64) : Useful but not urgent; alternatives exist.
  WEAK_WANT       (20-39) : Low utility, unlikely to be used much.
  IMPULSE         (0-19)  : Emotion, hype, or social pressure is the main driver.

Critical rules:
- Read the user's free-text answers carefully — take them at face value.
- Do NOT assume anything the user did not explicitly say.
- Score based on UTILITY and GENUINE NEED only — not on price or affordability.
- Reference what the user actually said in your reasoning sentence.
- Return ONLY valid JSON. No markdown. No extra text.
""".strip()


# ------------------------------------------------------------------
# Helper — return a GenAI Client
# ------------------------------------------------------------------
def _get_client() -> Optional[genai.Client]:
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured.")
        return None
    return genai.Client(api_key=key)


# ------------------------------------------------------------------
# STEP 1 — Generate open-ended questions (first-time / no history)
# ------------------------------------------------------------------
def generate_questions(
    product_name: str,
    category: str,
    price: float,
) -> NeedQuestions:
    """
    Called when the user has no purchase history in this category.

    The LLM generates 3-4 open-ended questions specific to this product.
    The frontend renders each question with a plain text input — no options.

    Example output for Sony WH-1000XM5:
        Q1: "Do you currently own any earphones or headphones?
              What happened to them?"
        Q2: "What's your main reason for wanting these specifically?"
        Q3: "How many hours a day do you think you'd actually use them?"
        Q4: "Is there anything specific about your situation that makes
              you feel you need these right now?"
    """
    client = _get_client()
    if client is None:
        return _FALLBACK_QUESTIONS

    prompt = f"""
Generate 3–4 open-ended questions for this purchase.
The user will type their answers freely — no options provided.

Product  : {product_name}
Category : {category}
Price    : ₹{price:,.0f}

Return JSON in this exact format:
{{
  "questions": [
    {{ "question": "<question text>" }},
    {{ "question": "<question text>" }},
    {{ "question": "<question text>" }}
  ],
  "reason_for_asking": "<one sentence>"
}}
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_QUESTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        data = json.loads(response.text.strip())
        return NeedQuestions(**data)

    except json.JSONDecodeError as exc:
        logger.error("generate_questions — JSON decode error: %s", exc)
        return _FALLBACK_QUESTIONS
    except Exception as exc:
        logger.error("generate_questions — LLM error: %s", exc)
        return _FALLBACK_QUESTIONS


# ------------------------------------------------------------------
# STEP 2A — Score from user's free-text answers
# ------------------------------------------------------------------
def evaluate_need_from_answers(
    product_name: str,
    category: str,
    price: float,
    user_answers: Dict[str, str],
) -> NeedEvaluation:
    """
    Called after the user types their free-text answers.

    The LLM reads exactly what the user wrote and scores accordingly.
    No assumptions. No options. Just the user's own words.

    user_answers format:
        {
          "Do you currently own any earphones?": "I had AirPods but my dog chewed them",
          "What would you use these for?":       "Zoom calls from home, maybe gym",
          "Is there urgency?":                   "Kind of — I have a big presentation next week"
        }
    """
    client = _get_client()
    if client is None:
        return _FALLBACK_EVALUATION

    # Format answers into a readable block
    answers_block = "\n".join(
        f"  Q: {q}\n  A: {a}" for q, a in user_answers.items()
    )

    prompt = f"""
Evaluate this purchase based solely on what the user wrote below.

Product  : {product_name}
Category : {category}
Price    : ₹{price:,.0f}

User's answers (in their own words):
{answers_block}

Return JSON in this exact format:
{{
  "score": <number 0–100>,
  "classification": <"ESSENTIAL_NEED"|"STRONG_WANT"|"MODERATE_WANT"|"WEAK_WANT"|"IMPULSE">,
  "reasoning": "<one sentence that directly references what the user said>",
  "data_source": "USER_ANSWERS"
}}
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(response.text.strip())
        return NeedEvaluation(**data)

    except json.JSONDecodeError as exc:
        logger.error("evaluate_need_from_answers — JSON decode error: %s", exc)
        return _FALLBACK_EVALUATION
    except Exception as exc:
        logger.error("evaluate_need_from_answers — LLM error: %s", exc)
        return _FALLBACK_EVALUATION


# ------------------------------------------------------------------
# STEP 2B — Score from purchase history (returning users, skip questions)
# ------------------------------------------------------------------
def evaluate_need_from_history(
    product_name: str,
    category: str,
    price: float,
    purchase_history_summary: str,
) -> NeedEvaluation:
    """
    Called when the user has past purchase history in this category.
    Questions are skipped entirely — history provides the context.

    purchase_history_summary example:
        "User bought 3 Electronics items in past 6 months.
         Bluetooth speaker (kept, used daily), Smart watch (returned),
         USB hub (kept, used weekly). Average regret: 25/100."
    """
    client = _get_client()
    if client is None:
        return _FALLBACK_EVALUATION

    prompt = f"""
Evaluate this purchase using the user's past purchase behaviour as context.

Product  : {product_name}
Category : {category}
Price    : ₹{price:,.0f}

User's purchase history in this category:
{purchase_history_summary}

Return JSON in this exact format:
{{
  "score": <number 0–100>,
  "classification": <"ESSENTIAL_NEED"|"STRONG_WANT"|"MODERATE_WANT"|"WEAK_WANT"|"IMPULSE">,
  "reasoning": "<one sentence referencing their past behaviour>",
  "data_source": "PURCHASE_HISTORY"
}}
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(response.text.strip())
        return NeedEvaluation(**data)

    except json.JSONDecodeError as exc:
        logger.error("evaluate_need_from_history — JSON decode error: %s", exc)
        return _FALLBACK_EVALUATION
    except Exception as exc:
        logger.error("evaluate_need_from_history — LLM error: %s", exc)
        return _FALLBACK_EVALUATION


# ------------------------------------------------------------------
# MAIN ENTRY POINT — Orchestrator calls this
# ------------------------------------------------------------------
def run_need_agent(
    product_name: str,
    category: str,
    price: float,
    user_answers: Optional[Dict[str, str]] = None,
    purchase_history_summary: Optional[str] = None,
) -> NeedEvaluation:
    """
    Smart router — picks the right path:

    Path A (returning user):
        purchase_history_summary provided → score directly from history.

    Path B (new user, answers collected):
        user_answers provided → score from free-text answers.

    Path C (answers not yet collected):
        Returns fallback. Orchestrator should call generate_questions()
        first, show them in UI, collect answers, then call this.
    """
    if purchase_history_summary:
        logger.info("NeedAgent → PURCHASE_HISTORY path.")
        return evaluate_need_from_history(
            product_name, category, price, purchase_history_summary
        )

    if user_answers:
        logger.info("NeedAgent → USER_ANSWERS path.")
        return evaluate_need_from_answers(
            product_name, category, price, user_answers
        )

    logger.warning("NeedAgent → no history or answers provided. Returning fallback.")
    return _FALLBACK_EVALUATION
