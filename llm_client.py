import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def get_client() -> Groq:
    """Create a Groq client using the locally stored API key."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from your .env file.")

    return Groq(
        api_key=api_key,
        timeout=60.0,
        max_retries=2,
    )


def generate_response(system_prompt: str, user_prompt: str) -> str:
    """Send instructions and input text to the configured Groq model."""
    client = get_client()

    model = os.getenv("GROQ_MODEL", "").strip()
    if not model:
        raise ValueError("GROQ_MODEL is missing from your .env file.")

    response = client.chat.completions.create(
        model=model,
        reasoning_effort="low",
        max_completion_tokens=3500,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    if not response.choices:
        raise ValueError("Groq returned no response choices.")

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise ValueError(
            "The model reached its output limit. "
            "The response may be incomplete; reduce the batch size."
        )
    content = choice.message.content

    if not content or not content.strip():
        usage = response.usage
        raise ValueError(
            "Groq returned empty answer text. "
            f"finish_reason={choice.finish_reason}; "
            f"prompt_tokens={getattr(usage, 'prompt_tokens', None)}; "
            f"completion_tokens={getattr(usage, 'completion_tokens', None)}"
        )

    return content.strip()


if __name__ == "__main__":
    client = get_client()

    # Check authentication and list accessible models.
    models = client.models.list()
    model_ids = sorted(model.id for model in models.data)

    print("Groq connection successful.")
    print("\nAvailable models:")
    for model_id in model_ids:
        print(f"- {model_id}")