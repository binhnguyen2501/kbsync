"""Sanity check: ask OptiBot a question against the vector store, using OPENAI_MODEL."""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def main() -> int:
    load_dotenv()
    question = " ".join(sys.argv[1:]) or "How do I add a YouTube video?"
    store_id = os.getenv("VECTOR_STORE_ID")
    if not store_id:
        print("Set VECTOR_STORE_ID", file=sys.stderr)
        return 2
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY"))
    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        instructions=SYSTEM_PROMPT,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [store_id], "max_num_results": 5}],
    )
    print(f"Q: {question}\n\n{resp.output_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
