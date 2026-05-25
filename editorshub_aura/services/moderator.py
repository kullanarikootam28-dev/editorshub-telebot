"""
AI Moderation Layer — powered by OpenAI Moderation API (free).

Checks every user-generated text for: harassment, hate speech, threats,
violence, sexual content, spam-like patterns.

Fails open: if the API is unavailable, messages are allowed through
so the bot keeps working. Admin is notified of the API failure.
"""
import os
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# Human-readable category labels shown in admin notifications
CATEGORY_LABELS = {
    "harassment":              "Harassment",
    "harassment_threatening":  "Threatening Harassment",
    "hate":                    "Hate Speech",
    "hate_threatening":        "Threatening Hate",
    "illicit":                 "Illicit Content",
    "illicit_violent":         "Violent Illicit Content",
    "self_harm":               "Self-Harm",
    "self_harm_instructions":  "Self-Harm Instructions",
    "self_harm_intent":        "Self-Harm Intent",
    "sexual":                  "Sexual Content",
    "sexual_minors":           "Sexual Content (Minors)",
    "violence":                "Violence",
    "violence_graphic":        "Graphic Violence",
}

# Sent to user when their message is flagged
REDIRECT_MESSAGE = (
    "⚠️ <b>Message Flagged — Not Delivered</b>\n\n"
    "Our AI moderation system detected content that violates our community guidelines. "
    "Your message was <b>not delivered</b> to the other party.\n\n"
    "📌 <b>What you can do here:</b>\n"
    "• 📦 /order — Place a new editing order\n"
    "• 📋 /myorders — Track your existing orders\n"
    "• 🎬 /register — Join as an editor\n"
    "• 🏆 /leaderboard — View top editors\n"
    "• 💬 Use the <b>Message Board</b> buttons in /myorders to contact the other party professionally\n\n"
    "Keep all communication professional and strictly project-related.\n"
    "<i>If you believe this is a mistake, please contact the admin.</i>"
)


def _get_openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it as an environment variable.")
        _client = AsyncOpenAI(api_key=key)
    return _client


async def moderate(text: str) -> dict:
    """
    Run text through OpenAI Moderation.

    Returns:
        {
          "flagged": bool,
          "categories": list[str],   # human-readable labels
          "raw_categories": list[str],
          "reason": str,
          "api_available": bool,
        }
    """
    try:
        client = _get_openai()
        response = await client.moderations.create(
            input=text,
            model="text-moderation-latest",
        )
        result = response.results[0]
        cats_dict = result.categories.model_dump()
        raw_flagged = [k for k, v in cats_dict.items() if v]
        human_labels = [CATEGORY_LABELS.get(k, k) for k in raw_flagged]

        return {
            "flagged": result.flagged,
            "categories": human_labels,
            "raw_categories": raw_flagged,
            "reason": ", ".join(human_labels) if human_labels else "clean",
            "api_available": True,
        }
    except RuntimeError as e:
        logger.warning(f"Moderation skipped: {e}")
        return {"flagged": False, "categories": [], "raw_categories": [], "reason": "no_api_key", "api_available": False}
    except Exception as e:
        logger.error(f"OpenAI Moderation API error: {e}")
        return {"flagged": False, "categories": [], "raw_categories": [], "reason": "api_error", "api_available": False}
