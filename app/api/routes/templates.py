import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.api.deps import get_template_store
from app.schemas.template import Template
from app.services.excel_mapper import analyze_template, inject_named_ranges, validate_template
from app.services.template_store import TemplateStore

router = APIRouter()


class PromptUpdate(BaseModel):
    custom_prompt: str | None = None


@router.post("/analyze")
async def analyze_template_structure(file: UploadFile = File(...)):
    """Named Range 없는 xlsx의 시트·헤더 구조를 반환."""
    content = await file.read()
    try:
        result = analyze_template(content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.post("", response_model=Template)
async def register_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    system_prompt: str | None = Form(None),
    field_map: str | None = Form(None),   # JSON: {field: col, ..., "__sheet": "시트명", "__data_start": 6}
    store: TemplateStore = Depends(get_template_store),
):
    content = await file.read()

    if field_map:
        # UI에서 컬럼을 직접 매핑한 경우 — Named Range를 주입해서 저장
        try:
            mapping = json.loads(field_map)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="field_map JSON 파싱 실패")

        sheet_name = mapping.pop("__sheet", None)
        data_start_row = int(mapping.pop("__data_start", 6))

        if not sheet_name:
            raise HTTPException(status_code=422, detail="시트명(__sheet)이 누락되었습니다.")
        if not mapping:
            raise HTTPException(status_code=422, detail="하나 이상의 필드를 매핑해야 합니다.")

        try:
            content, fields = inject_named_ranges(content, sheet_name, mapping, data_start_row)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        # 기존 FIELD_* Named Range 방식
        try:
            fields = validate_template(content)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    return await store.save(
        name=name,
        fields=fields,
        xlsx_bytes=content,
        custom_prompt=system_prompt,
    )


@router.get("", response_model=list[Template])
async def list_templates(store: TemplateStore = Depends(get_template_store)):
    return await store.list_all()


@router.get("/{template_id}", response_model=Template)
async def get_template(
    template_id: str,
    store: TemplateStore = Depends(get_template_store),
):
    try:
        return await store.get(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")


@router.put("/{template_id}/prompt", response_model=Template)
async def update_prompt(
    template_id: str,
    body: PromptUpdate,
    store: TemplateStore = Depends(get_template_store),
):
    try:
        return await store.update_prompt(template_id, body.custom_prompt)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    store: TemplateStore = Depends(get_template_store),
):
    try:
        await store.delete(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")
    return Response(status_code=204)
