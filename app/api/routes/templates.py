from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.api.deps import get_template_store
from app.schemas.template import Template
from app.services.excel_mapper import validate_template
from app.services.template_store import TemplateStore

router = APIRouter()


@router.post("", response_model=Template)
async def register_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    system_prompt: str | None = Form(None),
    store: TemplateStore = Depends(get_template_store),
):
    content = await file.read()
    try:
        fields = validate_template(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await store.save(name=name, fields=fields, xlsx_bytes=content, custom_prompt=system_prompt)


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
    prompt: str = Form(...),
    store: TemplateStore = Depends(get_template_store),
):
    try:
        return await store.update_prompt(template_id, prompt)
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
