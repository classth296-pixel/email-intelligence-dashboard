import os
import time
from dotenv import load_dotenv
from google import genai

import config

load_dotenv(override=True)   # ← add override=True
_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def run_prompt(email_body: str) -> str:
    """Send prompt to Gemini with automatic retry on rate limit (429)."""
    client = get_client()
    prompt_text = config.PROMPT_TEMPLATE.format(email_body=email_body)

    max_retries = 4
    wait_seconds = 10

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt_text,
                config={
                    "max_output_tokens": config.GEMINI_MAX_TOKENS,
                },
            )
            return (response.text or "").strip()

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                if attempt < max_retries - 1:
                    print(f"  Rate limited by Gemini. Retrying in {wait_seconds}s "
                          f"(attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_seconds)
                    wait_seconds *= 2   # exponential backoff: 10 → 20 → 40 → 80s
                else:
                    raise
            else:
                raise