from datetime import datetime
from pydantic import BaseModel, computed_field


class Template(BaseModel):
    template_id: str
    name: str
    fields: list[str]
    custom_prompt: str | None
    created_at: datetime

    @computed_field
    @property
    def has_custom_prompt(self) -> bool:
        return self.custom_prompt is not None
