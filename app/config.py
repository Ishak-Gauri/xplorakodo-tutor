"""Settings read from environment variables (and a .env file if python-dotenv is installed)."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional
    pass


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "mock"          # mock | openai | anthropic
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-haiku-5-5"
    db_path: str = "xplorakodo.db"
    daily_token_budget: int = 20000     # per student per day (estimated tokens)


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "mock").lower(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        db_path=os.getenv("DB_PATH", "xplorakodo.db"),
        daily_token_budget=int(os.getenv("DAILY_TOKEN_BUDGET", "20000")),
    )
