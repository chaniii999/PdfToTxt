from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import ocr

app = FastAPI()
app.include_router(ocr.router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_front():
    """기능 테스트용 프론트: PDF 업로드 → OCR 텍스트 표시."""
    return FileResponse(STATIC_DIR / "index.html")

@app.get('/items')
def read_item(
    skip: int = 0,
    limit: int = 10,
    q: str | None = None
):
    # GET /items?skip=0&limit=10&q=search
    return {
        'skip': skip,
        'limit': limit,
        'q': q,
    }

