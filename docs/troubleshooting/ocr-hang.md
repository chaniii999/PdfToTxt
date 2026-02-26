# OCR 추출 멈춤/지연 트러블슈팅

## 현상
- 1페이지 PDF 업로드 후 1분 이상 지나도 응답 없음
- "대기" 상태에서 진행되지 않음

## 원인 후보

### 1. 1페이지는 멀티프로세싱 미사용
- `total >= 2`일 때만 ProcessPoolExecutor 사용
- 1페이지는 `asyncio.to_thread`로 단일 스레드 처리
- 멀티프로세싱 코드와 무관

### 2. OCR 처리 시간
- 이미지 기반 PDF 1페이지: OCR에 10~60초 이상 소요 가능
- 복잡한 레이아웃/해상도면 더 오래 걸림
- DPI 300, kor+eng 2단계 처리 시 시간 증가

### 3. uvicorn 멀티 워커
- `uvicorn main:app --workers 2` 이상 사용 시 ProcessPoolExecutor와 충돌 가능
- **권장**: `uvicorn main:app` (워커 1개) 또는 `--workers 1` 명시

### 4. 스트리밍 버퍼
- `started` 메시지는 즉시 전송됨
- 페이지 결과는 해당 페이지 OCR 완료 후 전송
- 1페이지면 전체 완료까지 대기 후 한 번에 전송될 수 있음

## 확인 방법

```bash
# 서버 로그 확인 (다른 터미널에서)
uvicorn main:app --reload

# 1페이지 PDF로 테스트
python -c "
from services.ocr.pdf_ocr import extract_text_stream
import asyncio
# 실제 PDF 바이트로 교체
pdf = open('your.pdf', 'rb').read()
async def t():
    async for c in extract_text_stream(pdf):
        print('chunk:', c[:80])
asyncio.run(t())
"
```

## 조치
- OCR 모드 끄고 디지털 PDF로 테스트 (직접 추출이면 즉시 완료)
- `OCR_USE_MULTIPROCESS=0`으로 멀티프로세싱 비활성화 후 재시도
- 서버를 `--workers 1`로 실행

## 멀티프로세싱 개선 (4페이지 이상 멈춤 방지)

### 적용된 구조
1. **submit + as_completed**: `executor.map` 대신 `submit`과 `asyncio.wait(FIRST_COMPLETED)`로 완료되는 페이지부터 즉시 yield
2. **timeout**: `OCR_TESSERACT_TIMEOUT`(기본 120초)으로 특정 페이지 무한 대기 방지
3. **이미지 압축 전달**: 메인에서 `cv2.imencode`로 PNG 압축 후 워커에 전달. PDF 반복 열기 I/O·pickle 오버헤드 감소
4. **stdout/stderr 버퍼**: pytesseract는 각 Tesseract 호출마다 독립 subprocess 사용. `proc.communicate(timeout)`으로 파이프 읽어 버퍼 꼬임 방지
