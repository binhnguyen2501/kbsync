"""Sanity check: ask OptiBot a question against the vector store, using OPENAI_MODEL."""
import sys

from openai import OpenAI

from kbsync.config import Settings
from kbsync.prompt import SYSTEM_PROMPT


def main() -> int:
    settings = Settings.from_env()
    question = " ".join(sys.argv[1:]) or "How do I add a YouTube video?"
    if not settings.vector_store_id:
        print("Set VECTOR_STORE_ID", file=sys.stderr)
        return 2
    client = OpenAI(api_key=settings.api_key)
    resp = client.responses.create(
        model=settings.model,
        instructions=SYSTEM_PROMPT,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [settings.vector_store_id], "max_num_results": 5}],
    )
    print(f"Q: {question}\n\n{resp.output_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
