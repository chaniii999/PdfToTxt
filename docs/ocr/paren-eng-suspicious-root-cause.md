# "(환각현상)" → "(P환각현상" 오인식 원인

## 현상

- **원본**: (환각현상)
- **추출**: (P환각현상
- **문제**: 괄호 안에 P가 삽입됨 (P가 있어서는 안 되는 위치)

---

## 원인: `_is_eng_suspicious`가 `(`를 eng 의심후보로 분류

### 1. `_ENG_SYMBOLS`에 `(` `)` 포함

```python
_ENG_SYMBOLS = re.compile(r"[|\\/\[\]()+\-!<>]")
#                                    ^^  괄호 포함
```

- `(` `)`가 이 패턴에 포함되어 있음
- `_is_eng_suspicious`에서 `_ENG_SYMBOLS.search(text)`가 True가 되면 eng 의심후보로 분류

### 2. image_to_data에서 `(`가 단독 단어로 나옴

- Tesseract는 구두점을 별도 word로 출력하는 경우가 많음
- `"(환각현상)"` → word: `"("`, `"환각현상"`, `")"`

### 3. 치환 흐름

1. `"("` → `_is_eng_suspicious` True (ENG_SYMBOLS)
2. `"("` bbox로 eng ROI crop
3. eng OCR: `"("` 모양(둥근 부분 + 세로선)을 `"P"`로 오인식
4. `replacements.append(("(", "P"))`
5. `base_text "(환각현상)"`에서 첫 `"("`를 `"P"`로 치환
6. 결과: `"P환각현상)"` (또는 사용자 표현에 따라 `"(P환각현상"`)

### 4. 결론

- **순수 구두점** `(`, `)`, `.`, `,` 등은 eng 단어가 아님
- 이들을 eng 의심후보로 두고 eng OCR을 돌리면, 형태 유사 문자(P, C 등)로 잘못 치환됨
- 따라서 **순수 구두점만 있는 word는 eng 의심후보에서 제외**해야 함
