# Chrome OCR 기술 → PdfToTxt 적용 가능 항목

크롬 스캔본 PDF 텍스트 추출 기술(WASM, 온디바이스 AI, Lazy Loading) 분석 후, **현재 파이썬/FastAPI 백엔드에 적용 가능한 것**만 추린 문서.

---

## 1. 적용 가능 (우선 적용 권장)

### 1.1 멀티 프로세싱 (ProcessPoolExecutor)

**크롬 원리**: 여러 페이지를 동시에 처리.  
**현재 상태**: `for idx in range(total)`로 페이지 **순차** 처리.  
**적용**: `ProcessPoolExecutor`로 4~8페이지 동시 OCR → **속도 4배 이상** 기대.

```
현재: p1 → p2 → p3 → p4 … (순차)
적용: [p1,p2,p3,p4] 동시 → [p5,p6,p7,p8] 동시 …
```

- `ocr-performance-analysis.md`에서도 "1차 후보 병렬화"로 이미 언급됨.
- Tesseract는 프로세스 기반이라 GIL 영향 없음. 페이지 단위 병렬화에 적합.

### 1.2 DPI 최적화 (문서 특성별)

**크롬 원리**: 무조건 고해상도가 아니라, 글자 크기에 맞춰 DPI 조절.  
**현재 상태**: 350 DPI 고정.  
**적용**: 글자 큰 문서는 200~250 DPI로 낮춰 연산량 감소. (품질 유지 범위 내)

- 의회문서 30~50페이지: 대부분 비슷한 레이아웃 → **문서 타입별 DPI preset** 또는 **첫 페이지 샘플링 후 DPI 결정** 가능.
- 품질 테스트 후 적용 권장.

---

## 2. 이미 적용됨

### 2.1 FastAPI 스트리밍 (NDJSON)

**크롬 원리**: 50페이지 전부 끝날 때까지 기다리지 않고, 한 페이지 끝날 때마다 바로 전송.  
**현재 상태**: `extract_text_stream` → `StreamingResponse(application/x-ndjson)`로 **이미 구현됨**.

- 클라이언트는 첫 페이지 결과를 먼저 받고, 나머지는 순차 수신.

### 2.2 Lazy Loading 개념

**크롬**: 현재 보이는 페이지만 우선 OCR.  
**백엔드**: 스트리밍으로 "첫 페이지 먼저" 효과는 이미 있음.  
- 브라우저 UX와 달리, 백엔드는 전체 처리 필요. 스트리밍이 이에 해당하는 최선.

---

## 3. 적용 부담 큼 (중장기 검토)

### 3.1 가벼운 모델 (Lite Model)

**크롬**: tessdata_best 대신 특정 폰트·문서에 최적화된 가벼운 딥러닝 모델.  
**적용**: tessdata_fast 사용 시 속도 ↑, 품질 ↓. 한글 의회문서는 품질이 중요해 **신중 검토** 필요.

- **TensorRT/ONNX**: Tesseract 대체 수준. 아키텍처 변경이 큼. 별도 프로젝트로 검토.

### 3.2 GPU 가속

**크롬**: WebGL/WebGPU로 병렬 픽셀 처리.  
**적재**: Tesseract는 CPU 기반. GPU 활용하려면 PaddleOCR, EasyOCR 등 **엔진 교체** 필요.

---

## 4. 적용 불가 (참고용)

### 4.1 WASM / 브라우저 내장 OCR

**크롬**: C++ OCR 엔진을 WASM으로 브라우저에 내장. 네트워크 지연 0.  
**현재**: FastAPI 백엔드 + Tesseract. 서버 측 처리 구조.

- Tesseract.js로 브라우저 OCR을 쓰면 **아키텍처 전환** 필요.
- 의회문서 30~50페이지, 보안·품질 요구를 고려하면 서버 OCR 유지가 현실적.

---

## 5. 적용 우선순위 요약

| 순위 | 항목 | 효과 | 구현 난이도 |
|------|------|------|-------------|
| 1 | **ProcessPoolExecutor 페이지 병렬** | 속도 4배↑ | 중 |
| 2 | **DPI 최적화** (문서별 200~350) | 연산량 감소 | 하 |
| 3 | tessdata_fast 실험 | 속도↑ 품질↓ | 하 |
| 4 | TensorRT/ONNX, GPU 엔진 | 대폭 속도↑ | 상 |

---

## 참고

- `docs/ocr/ocr-performance-analysis.md`: Tesseract 호출 구조, early stop, PSM 병렬화
- `services/ocr/pdf_ocr.py`: `extract_text_stream`, `_process_page_sync`
