import os
from dotenv import load_dotenv


def _reload_env():
    load_dotenv(override=True)


class Settings:
    @property
    def LLM_API_KEY(self) -> str:
        _reload_env()
        return os.getenv("LLM_API_KEY", "")

    @property
    def LLM_BASE_URL(self) -> str:
        return os.getenv("LLM_BASE_URL", "")

    @property
    def LLM_MODEL(self) -> str:
        return os.getenv("LLM_MODEL", "")

    @property
    def MAX_CONTEXT_TOKENS(self) -> int:
        _reload_env()
        return int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))

    @property
    def NUDGE_INTERVAL(self) -> int:
        """Number of user-assistant rounds before triggering memory reflection."""
        return int(os.getenv("NUDGE_INTERVAL", "5"))

    @property
    def SERVER_HOST(self) -> str:
        return os.getenv("SERVER_HOST", "0.0.0.0")

    @property
    def SERVER_PORT(self) -> int:
        return int(os.getenv("SERVER_PORT", "8000"))

    @property
    def TAVILY_API_KEY(self) -> str:
        _reload_env()
        return os.getenv("TAVILY_API_KEY", "")


_reload_env()
settings = Settings()
