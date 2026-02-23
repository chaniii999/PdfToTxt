"""OCR API: PDF 업로드 → 텍스트 반환 (스트리밍 진행 표시)."""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from services.pdf_ocr import extract_text_stream

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("")
async def run_ocr(file: UploadFile = File(...)):
    """PDF 업로드 → 페이지별 진행 스트리밍 → 최종 텍스트 반환."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    return StreamingResponse(
        extract_text_stream(content),
        media_type="application/x-ndjson",
    )
