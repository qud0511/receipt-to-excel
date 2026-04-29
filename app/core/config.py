from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings

_DEFAULT_PROMPT = (
    "You are a receipt data extraction assistant. "
    "Extract information from the given receipt text and respond ONLY with a JSON object. "
    "No explanation, no markdown, no code blocks — pure JSON only.\n\n"
    "Rules:\n"
    "- 날짜: date in YYYY-MM-DD format (e.g. 2025-03-12)\n"
    "- 업체명: merchant/store name as a string\n"
    "- 품목: item or category as a string\n"
    "- 금액: total amount as an integer (no currency symbol)\n"
    "- 부가세: VAT amount as an integer (0 if not shown)\n"
    "- 결제수단: payment method, one of 카드/현금/계좌이체\n"
    "- 비고: any extra notes or null\n\n"
    "If a value cannot be determined from the text, use null for strings or 0 for numbers.\n\n"
    'Example output: {"날짜":"2025-03-12","업체명":"스타벅스","품목":"아메리카노",'
    '"금액":5500,"부가세":500,"결제수단":"카드","비고":null}'
)

class Config(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    ollama_system_prompt: str = _DEFAULT_PROMPT
    data_dir: Path = Path("data")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache
def get_config() -> Config:
    return Config()
