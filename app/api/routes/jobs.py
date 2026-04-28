from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.preprocessor import route_file

router = APIRouter()


@router.post("")
async def create_job(files: list[UploadFile] = File(...)):
    summary = []
    for f in files:
        content = await f.read()
        try:
            items = route_file(content, f.filename or "unknown")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        summary.append({"name": f.filename, "pages": len(items)})
    return {"files": summary, "total_pages": sum(s["pages"] for s in summary)}
