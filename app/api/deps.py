from app.core.config import get_config
from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient
from app.services.template_store import TemplateStore

_job_manager: InMemoryJobManager | None = None
_template_store: TemplateStore | None = None


def get_job_manager() -> InMemoryJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = InMemoryJobManager()
    return _job_manager


def get_ollama_client() -> OllamaClient:
    config = get_config()
    return OllamaClient(base_url=config.ollama_base_url, model=config.ollama_model)


def get_template_store() -> TemplateStore:
    global _template_store
    if _template_store is None:
        config = get_config()
        _template_store = TemplateStore(data_dir=config.data_dir)
    return _template_store
