"""All settings come from environment variables (or .env); see .env.sample."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    vector_store_id: str | None
    vector_store_name: str
    max_articles: int
    zendesk_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            vector_store_id=os.getenv("VECTOR_STORE_ID") or None,
            vector_store_name=os.getenv("VECTOR_STORE_NAME", "optibot-kb"),
            max_articles=int(os.getenv("MAX_ARTICLES", "0")),
            zendesk_base_url=os.getenv("ZENDESK_BASE_URL", "https://support.optisigns.com"),
        )
