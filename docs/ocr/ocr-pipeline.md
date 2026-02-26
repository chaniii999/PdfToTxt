# OCR 파이프라인 흐름

커스텀 전략 기준. 훑어보기용.

---

## 1. 진입

PDF가 업로드되면 바이트를 받아 `extract_text_stream`으로 진입한다.  
시작 시 Tesseract 학습 데이터(kor, eng)가 `tessdata_best` 버전인지 검증한다.

---

## 2. 페이지별 판별

각 페이지마다 단어 수, 텍스트 면적 비율, 이미지 면적 비율을 계산한다.

- **디지털 PDF**라면: 텍스트 레이어가 충분히 있다고 판단되면 `page.get_text()`로 직접 추출하고 OCR을 건너뛴다.
- **스캔본 PDF**라면: 아래 이미지 준비부터 OCR 파이프라인을 진행한다.

---

## 3. 이미지 준비 (스캔본만)

스캔본으로 판별된 페이지는 다음 순서로 이미지를 준비한다.

1. **렌더링** — 페이지를 350 DPI로 이미지로 변환한다.
2. **회전 보정** — Tesseract OSD로 90/180/270도 감지 후 보정한다.
3. **기울기 보정** — Hough 변환으로 텍스트 라인 각도를 추정해 ±15° 이내로 보정한다.
4. **테두리 추가** — Tesseract 권장대로 10px 흰색 테두리를 둘러 인식 안정성을 높인다.

---

## 4. OCR 실행 (커스텀 전략)

준비된 이미지로 여러 후보를 만들고, 점수로 최적 결과를 선택한다.

**1차 후보 4개**: rgb+PSM 6, otsu+PSM 6, otsu+PSM 4, otsu+PSM 3. 각각 Tesseract를 돌려 텍스트를 얻는다.

**점수 계산**: `길이 × (0.2 + 0.8 × 한글비율)`. 한글 비율이 높을수록 점수가 올라가고, Latin 오인식을 억제하는 효과가 있다.

**최고 점수 선택**: 4개 중 점수가 가장 높은 결과를 `best`로 둔다.

**조기 종료**: `best` 점수가 450을 넘으면 바로 반환한다. enhance·프리셋 시도는 생략한다.

**점수 부족 시**: enhance(sharpen 0.9 + CLAHE)를 시도하고, 이어서 preset D → A → B → C 순으로 `preprocess_for_ocr`를 적용한 뒤 각각 Tesseract를 돌린다. 기존 `best`보다 점수가 높으면 `best`를 갱신한다.

**후처리**: `correct_ocr_text` — 오탈자사전 기반 오인식 치환 (0!!→PII, 표준만→표준안, 개민→개인 등).

- **언어**: kor+eng
- **출력**: `image_to_string` 사용 (띄어쓰기 유지. `image_to_data`는 한글에서 글자 단위로 나와 띄어쓰기가 깨진다.)

---

## 5. 출력

선택된 최종 텍스트를 NDJSON 스트리밍으로 클라이언트에 전달한다.

---

## 흐름 요약

```
PDF 업로드 → tessdata 검증
    ↓
페이지별: 디지털? → 직접 추출
    ↓ 스캔본
렌더(350 DPI) → 회전 보정 → 기울기 보정 → 테두리 추가
    ↓
1차 후보 4개(rgb, otsu×3) → 점수 계산 → best 선택
    ↓
점수 > 450? → 바로 반환
    ↓ 아니면
enhance → preset D → A → B → C 추가 시도 → best 갱신
    ↓
길이×(0.2+0.8×한글비율) 최대값 = 최종 텍스트
    ↓
correct_ocr_text (오탈자사전 치환)
    ↓
NDJSON 스트리밍 반환
```

---

## 참고

- `docs/ocr/ocr-strategy-comparison.md`: 커스텀 전략 개요·장단점
- `docs/ocr/ocr-strategy.md`: 상세 전략·설정
- `docs/ocr/ocr-error-patterns.md`: 오인식 패턴
- `docs/ocr/ocr-misrecognition-encyclopedia.md`: 한글↔Latin 형태 유사 쌍 백과사전
