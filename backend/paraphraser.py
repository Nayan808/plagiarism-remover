import os
import re
from groq import Groq

SYSTEM_PROMPT = (
    "You are a professional paraphrasing assistant. "
    "Rewrite the given text to make it completely unique and plagiarism-free "
    "while preserving the original meaning, tone, and technical accuracy. "
    "Do NOT add explanations, notes, or commentary. "
    "Return ONLY the rewritten text."
)

def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Get a free key at https://console.groq.com"
        )
    return Groq(api_key=api_key)


def paraphrase_text(text: str, model: str = "llama-3.1-8b-instant") -> str:
    """Paraphrase a chunk of text using Groq API."""
    text = text.strip()
    if not text or len(text) < 10:
        return text

    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Paraphrase this:\n\n{text}"},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    result = response.choices[0].message.content.strip()
    # Remove any surrounding quotes some models add
    result = re.sub(r'^["\']|["\']$', "", result).strip()
    return result


def paraphrase_paragraphs(paragraphs: list[str], model: str = "llama-3.1-8b-instant") -> list[str]:
    results = []
    for para in paragraphs:
        stripped = para.strip()
        if stripped:
            results.append(paraphrase_text(stripped, model))
        else:
            results.append(para)
    return results
