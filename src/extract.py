import sys
import json

import pdfplumber

# 일부 페이지는 PDF 병합(shuffle) 과정에서 텍스트 전체가 문자 단위로
# 뒤집혀서 추출된다. 예: "MK LENDING CORP" -> "PROC GNIDNEL KM"
# 원본(섞이기 전) 개별 문서에는 이 현상이 없었으므로, 병합 도구가
# 특정 페이지의 인코딩/회전 정보를 잘못 처리해서 생긴 아티팩트로 추정.
#
# 감지 방법: 정상적인 영어 문장이라면 the/and/report 같은 흔한 단어가
# 그대로 등장해야 한다. 텍스트 전체가 반전되면 이 단어들도 "eht", "dna",
# "tropeR"처럼 거꾸로 나타나 흔한 단어 목록과 매칭되지 않는다.
# 따라서 "원문에서 흔한 단어가 몇 개 매칭되는지"와 "뒤집은 문자열에서
# 몇 개 매칭되는지"를 비교해서, 뒤집었을 때 더 많이 매칭되면
# "이 페이지는 반전되어 있었다"고 판단한다.
#
# 주의: on/or/is/at/by/to/in/of 같은 2글자 단어는 일부러 뺐다.
# 예를 들어 체크박스의 "No"가 반전되면 "oN"이 되는데, 소문자로 바꾸면
# 우연히 "on"과 똑같아져서 오탐(false positive)이 생긴다.
# 실제로 이 문제 때문에 3글자 이상 단어만 남기기로 했다.
COMMON_WORDS = {
    "the", "and", "for", "this", "date", "page", "name", "loan",
    "report", "information",
}

# 정방향/역방향 매칭 개수가 근소한 차이(동점 포함)일 때는 반전으로
# 확정 짓지 않기 위한 최소 격차. 실제로 page 23에서 "No"->"oN" 같은
# 우연한 매칭 때문에 3:3 동점이 나서 반전을 놓친 사례가 있었다.
REVERSAL_MARGIN = 2


def looks_reversed(text: str) -> bool:
    """text가 반전된 상태로 추출되었는지 판단한다.

    휴리스틱이므로 100% 정확하지 않다 — 숫자/표 위주라 단어 자체가
    거의 없는 페이지는 양쪽 다 매칭 수가 0에 가까워 판단이 애매해질 수 있다.
    이런 경우 기본값(반전 아님)으로 처리한다.
    """

    def count_common_words(s: str) -> int:
        # 공백 기준으로 토큰을 나누고, 앞뒤에 붙은 구두점(.,:;()[]'")을
        # 제거한 뒤 소문자로 바꿔서 COMMON_WORDS 집합에 있는지 확인한다.
        words = s.split()
        return sum(1 for w in words if w.strip(".,:;()[]\"'").lower() in COMMON_WORDS)

    normal_hits = count_common_words(text)
    # text[::-1] : 문자열 전체를 통째로 뒤집는 슬라이싱 문법.
    # 만약 원래 텍스트가 반전되어 추출된 상태였다면, 이걸 한 번 더
    # 뒤집으면 원래의 정상적인 문장으로 복원된다.
    reversed_hits = count_common_words(text[::-1])

    # 뒤집었을 때 흔한 단어가 REVERSAL_MARGIN개 이상 더 많이 나와야
    # "반전 상태였다"고 확정한다. 근소한 차이/동점은 우연일 수 있으므로
    # 반전 아님(기본값)으로 처리한다.
    return reversed_hits >= normal_hits + REVERSAL_MARGIN


def fix_reversed_text(text: str) -> str:
    """반전된 것으로 판단되면 문자열을 뒤집어 정상 방향으로 복원하고,
    아니면 원본 그대로 돌려준다."""
    return text[::-1] if looks_reversed(text) else text


def extract_pages(pdf_path: str) -> list[dict]:
    """PDF를 열어 페이지별 텍스트를 추출한다.

    반환값은 [{"page_number": 1, "text": "..."}, ...] 형태.
    page_number는 1-indexed.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            raw_text = page.extract_text()
            # extract_text()가 None을 줄 수 있으니(스캔 이미지 등),
            # 이후 로직(looks_reversed의 .split() 등)이 안전하게 동작하도록
            # 빈 문자열로 먼저 정규화한다.
            raw_text = raw_text if raw_text is not None else ""

            # 반전 여부를 먼저 기록해두고(디버깅/감사용), 그 판단에 따라
            # 실제 저장할 text는 복원된(정상 방향) 버전으로 바꿔치기한다.
            reversed_detected = looks_reversed(raw_text)
            text = fix_reversed_text(raw_text)

            pages.append(
                {
                    "page_number": i + 1,
                    "text": text,
                    "char_count": len(text),
                    # 나중에 "이 페이지는 반전 감지로 복원됐다"는 걸 추적하려고
                    # 남겨두는 플래그. 감지 로직이 틀렸을 가능성도 있으니,
                    # 이 필드로 어떤 페이지들이 복원 대상이었는지 확인 가능.
                    "was_reversed": reversed_detected,
                }
            )
    return pages


def main():
    if len(sys.argv) != 2:
        print("Usage: python src/extract.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = extract_pages(pdf_path)

    for p in pages:
        print(f"\n{'=' * 60}")
        print(f"[Page {p['page_number']}] chars={p['char_count']}")
        print("=" * 60)
        if p["char_count"] == 0:
            print("(텍스트 없음 - 스캔 이미지일 가능성)")
        else:
            print(p["text"])

    print(f"\n총 {len(pages)} 페이지, 텍스트 없는 페이지: "
          f"{sum(1 for p in pages if p['char_count'] == 0)}개")


if __name__ == "__main__":
    main()
