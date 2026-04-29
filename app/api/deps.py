from app.core.config import get_config
from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient

_job_manager: InMemoryJobManager | None = None


def get_job_manager() -> InMemoryJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = InMemoryJobManager()
    return _job_manager


def get_ollama_client() -> OllamaClient:
    config = get_config()
    return OllamaClient(base_url=config.ollama_base_url, model=config.ollama_model)
