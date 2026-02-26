"""OCR API: PDF 업로드 → 텍스트 반환 (스트리밍 진행 표시)."""

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from services.ocr.pdf_ocr import extract_text_stream

router = APIRouter(prefix="/ocr", tags=["ocr"])


def _parse_force_ocr(value: str | None) -> bool:
    if not value:
        return False
    return value.lower() in ("1", "true", "yes", "on")


@router.post("")
async def run_ocr(
    file: UploadFile = File(...),
    force_ocr: str | None = Form(None),
):
    """PDF 업로드 → 페이지별 진행 스트리밍 → 최종 텍스트 반환. force_ocr=true면 항상 OCR."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    return StreamingResponse(
        extract_text_stream(content, force_ocr=_parse_force_ocr(force_ocr)),
        media_type="application/x-ndjson",
    )
