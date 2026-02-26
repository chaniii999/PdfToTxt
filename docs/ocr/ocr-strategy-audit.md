# OCR 전략 전체 분석 (의회문서 기준)

의회문서 OCR 파이프라인을 **1.5초/페이지** 목표에 맞춰 점검한 결과.

---

## 1. 벤치마크 기준 (참고)

| 구간 | 판정 | 조치 |
|------|------|------|
| ~1.5초 | 정상 | 유지 |
| 2초 이상 | 개선 여지 | 최적화 검토 |
| 3초 이상 | 병목 분석 | 원인 파악 후 수정 |
| 5초 이상 | 의심 | 즉시 점검 |

**기준 환경**: 350 DPI, 노이즈 거의 없음, A4

---

## 2. 의회문서 특성 반영

| 특성 | 현재 대응 | PSM 권장 |
|------|-----------|----------|
| 표 많음 | PSM 6(블록), 4(열) | ✅ 6, 4 사용 중 |
| 줄 간격 좁음 | - | PSM 6 적합 |
| 2단 구조 | PSM 4(단일 열) | ✅ 4 사용 중 |
| 각주 | - | PSM 6로 블록 단위 처리 |

**PSM 3(자동 레이아웃)**: 레이아웃 자동 판단으로 느려질 수 있음 → 1차 후보에 포함 중.

---

## 3. 현재 파이프라인 점검

### 3.1 ✅ 양호 항목

| 항목 | 상태 | 비고 |
|------|------|------|
| DPI 350 | ✅ | 600 DPI 미사용 |
| PNG 디스크 저장 | ✅ | fitz → numpy 메모리 전달 |
| PSM 6, 4 | ✅ | 의회문서에 적합 |
| 1차 4개 병렬 | ✅ | ThreadPoolExecutor |
| early stop 500 | ✅ | 2차 phase 진입 감소 |
| preset D, A만 | ✅ | B, C 제거로 2차 단축 |

### 3.2 ⚠️ 개선 필요

| 항목 | 현재 | 이슈 | 권장 |
|------|------|------|------|
| **PSM 3** | 1차 후보 4개 중 1개 | 자동 레이아웃으로 느림 | PSM 3 제거 또는 후순위 |
| **correct_orientation** | 매 페이지 `image_to_osd` | Tesseract 1회 추가 호출 | OSD 생략 또는 샘플링 |
| **deskew_rgb** | Hough(Canny, HoughLinesP) | A4 350 DPI에서 비용 큼 | 각도 임계값으로 스킵 확대 |
| **bilateralFilter** | preset A `denoise_adaptive` | 사용자 첨언 "과다" | medianBlur만 또는 경량화 |
| **adaptiveThreshold** | preset A, B | 사용자 첨언 "과다" | Otsu 위주로 단순화 |
| **OMP_NUM_THREADS** | 미설정 | Tesseract 기본값 사용 가능 | 2~4로 제한 검토 |

### 3.3 Tesseract 호출 수 (페이지당)

| 구간 | 호출 수 | 비고 |
|------|---------|------|
| correct_orientation | 1회 (OSD) | **추가 부담** |
| 1차 (병렬) | 4회 | rgb+psm6, otsu×3(psm6/4/3) |
| 2차 (score≤500) | 1~3회 | enhance + preset D + preset A |
| **합계** | **5~8회** | OSD 포함 시 6~9회 |

**목표 1.5초**: Tesseract 1회당 ~0.2~0.3초 필요. kor+eng tessdata_best 기준 2~3초/회가 일반적이라, **호출 수 축소**가 핵심.

---

## 4. 병목 가능성 순위

### 1순위: Tesseract 호출 수
- OSD 1회 + 1차 4회 + 2차 최대 3회 = 최대 8회
- 1회당 2~3초 가정 시 16~24초/페이지
- **조치**: OSD 생략/샘플링, PSM 3 제거, 2차 phase 축소

### 2순위: PSM 3
- 자동 레이아웃으로 레이아웃 분석 비용 증가
- **조치**: 1차 후보에서 PSM 3 제거 → 4회 → 3회

### 3순위: correct_orientation (OSD)
- 페이지마다 `image_to_osd` 호출
- **조치**: 첫 페이지만 OSD 또는 90/180/270 고정 문서는 생략

### 4순위: deskew (Hough)
- Canny + HoughLinesP on A4 350 DPI
- **조치**: 각도 0.3° 미만이면 스킵(현재 적용), 추가로 이미지 축소 후 Hough 등

### 5순위: preset A (bilateralFilter, adaptiveThreshold)
- denoise_adaptive → bilateralFilter
- _preset_a → adaptiveThreshold
- **조치**: preset A 단순화 또는 2차에서 제외

---

## 5. 권장 조치 (가성비 순)

| 순위 | 조치 | 예상 효과 | 품질 영향 |
|------|------|-----------|-----------|
| 1 | **PSM 3 제거** | 1차 4→3회, ~2~3초 절감 | 낮음 (6, 4로 대체) |
| 2 | **OSD 샘플링** | 첫 페이지만 또는 생략 | 회전된 스캔본에서만 영향 |
| 3 | **OMP_NUM_THREADS=2** | CPU 경합 완화 | 없음 |
| 4 | **preset A 단순화** | 2차 전처리 시간 감소 | 실측 필요 |
| 5 | **early stop 550** | 2차 진입 추가 감소 | 실측 필요 |

---

## 6. 결론

- **현재**: Tesseract 5~8회/페이지 + OSD + Hough deskew → **10~30초/페이지** 예상
- **목표**: 1.5초/페이지
- **격차**: Tesseract 호출 수가 가장 큰 원인. 1.5초 달성은 **단일 Tesseract 호출 + 최소 전처리** 수준 필요.
- **현실적 목표**: PSM 3 제거, OSD 최소화, 2차 축소로 **5~10초/페이지** 구간을 먼저 목표로 두는 것이 타당.

---

## 7. 적용된 개선 (5~10초/페이지 목표)

| 항목 | 적용 |
|------|------|
| PSM 3 제거 | 1차 4→3회 |
| OSD 샘플링 | 첫 페이지만 OSD, 나머지는 첫 페이지 각도 적용 |
| OMP_NUM_THREADS | 2 (미설정 시) |
| early stop 550 | 500→550 |
| preset A 제거 | preset D만 (bilateralFilter, adaptiveThreshold 제거) |

---

## 참고

- `ocr-performance-analysis.md`: Tesseract 호출 구조
- `ocr-strategy.md`: DPI, preset, PSM 설정
- `preprocess.py`: denoise_adaptive, preset A/B/D
