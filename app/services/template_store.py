import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.schemas.template import Template


class TemplateStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.db_path = data_dir / "templates.db"
        self.templates_dir = data_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def template_path(self, template_id: str) -> Path:
        return self.templates_dir / f"{template_id}.xlsx"

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    template_id   TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    fields        TEXT NOT NULL,
                    custom_prompt TEXT,
                    created_at    TEXT NOT NULL
                )
            """)
            await db.commit()

    async def save(
        self,
        name: str,
        fields: list[str],
        xlsx_bytes: bytes,
        custom_prompt: str | None = None,
    ) -> Template:
        template_id = f"tpl_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow()
        self.template_path(template_id).write_bytes(xlsx_bytes)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO templates VALUES (?, ?, ?, ?, ?)",
                (template_id, name, ",".join(fields), custom_prompt, created_at.isoformat()),
            )
            await db.commit()
        return Template(
            template_id=template_id,
            name=name,
            fields=fields,
            custom_prompt=custom_prompt,
            created_at=created_at,
        )

    async def list_all(self) -> list[Template]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM templates ORDER BY created_at DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [_row_to_template(r) for r in rows]

    async def get(self, template_id: str) -> Template:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM templates WHERE template_id = ?", (template_id,)
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Template {template_id!r} not found")
        return _row_to_template(row)

    async def update_prompt(self, template_id: str, prompt: str) -> Template:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE templates SET custom_prompt = ? WHERE template_id = ?",
                (prompt, template_id),
            )
            await db.commit()
        return await self.get(template_id)

    async def delete(self, template_id: str) -> None:
        path = self.template_path(template_id)
        if path.exists():
            path.unlink()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM templates WHERE template_id = ?", (template_id,)
            )
            await db.commit()


def _row_to_template(row: aiosqlite.Row) -> Template:
    return Template(
        template_id=row["template_id"],
        name=row["name"],
        fields=row["fields"].split(","),
        custom_prompt=row["custom_prompt"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
