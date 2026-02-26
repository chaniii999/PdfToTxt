# ") ol이" — ol 추가 원인

## 현상

- **원본**: 초거대 언어 모델(LLM)률이 임계치를...
- **추출**: 초거대 언어 모델(L L e M m ) **ol**이 임계치를...
- **문제**: "이"는 정상 추출됐는데, 그 앞에 "ol"이 추가로 삽입됨

---

## 원인: 자모 전용 word를 eng ROI로 치환

### 1. image_to_data에서 "률"이 "ㄹ"로 분리

- kor OCR이 "률"을 완성형이 아닌 **자모 "ㄹ"**만 word로 내는 경우가 있음
- "률" = ㅇ+ㅠ+ㄹ → ㅇ·ㅠ가 누락되거나, "ㄹ"만 별도 블록으로 인식

### 2. "ㄹ"이 eng 의심후보로 분류

```python
if _JAMO.search(text):
    return True  # "ㄹ" → eng_suspicious
```

- `_JAMO`에 "ㄹ"이 포함되므로 `_is_eng_suspicious`가 True
- "ㄹ"은 완성형 한글이 아니므로 `_has_complete_syllable`은 False

### 3. eng OCR → "ol"로 오인식

- "ㄹ" bbox로 crop 후 eng OCR 수행
- 실제 crop에는 "률" 전체 또는 인접 문자가 포함될 수 있음
- eng OCR: ㅇ(원형) → "o", ㄹ(꺾임) → "l"로 해석 → "ol" 출력

### 4. 치환 결과

- `replacements.append(("ㄹ", "ol"))`
- base_text "...률이..."에서 첫 "ㄹ"을 "ol"로 치환
- 결과: "...ol이..." (률 → ol이)

---

## 결론

- **자모 전용 word**(ㄹ, ㅇ, ㅣ 등)는 한글 음절의 일부
- 이를 eng ROI로 치환하면 한글→영문 오인식으로 텍스트가 깨짐
- **자모만 있는 word는 eng 의심후보에서 제외**해야 함
