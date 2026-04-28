from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings

_DEFAULT_PROMPT = (
    "당신은 영수증·매출전표 데이터 추출 전문가입니다."
    " 이미지 또는 텍스트에서 영수증 정보를 추출하여"
    " 반드시 아래 JSON 형식으로만 응답하세요."
    " 마크다운 코드블록 없이 순수 JSON만 출력하세요.\n\n"
    '{"날짜":"YYYY-MM-DD","업체명":"string","품목":"string",'
    '"금액":0,"부가세":0,"결제수단":"카드","비고":null}'
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
