import re

from config import KEYWORD_PATTERNS, OTHER


def classify_page(text: str) -> tuple[str, int]:
    """페이지 텍스트를 KEYWORD_PATTERNS와 대조해서 카테고리를 정한다.

    각 카테고리의 정규식 리스트 중 몇 개가 매칭됐는지 세고,
    매칭 수가 가장 많은 카테고리를 채택한다. 아무 카테고리도
    매칭이 안 되면 OTHER로 분류한다.

    반환값: (카테고리, 매칭된 패턴 개수)
    매칭 개수를 같이 돌려주는 이유는, 이 값이 낮으면(예: 1개) 확신이
    낮다는 뜻이라 나중에 LLM 폴백 대상으로 걸러낼 때 참고할 수 있어서다.
    """
    scores = {}
    for category, patterns in KEYWORD_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        if hits > 0:
            scores[category] = hits

    if not scores:
        return OTHER, 0

    best_category = max(scores, key=scores.get)
    return best_category, scores[best_category]


def classify_pages(pages: list[dict]) -> list[dict]:
    """extract_pages()가 반환한 페이지 리스트를 받아 각 페이지에
    분류 결과를 덧붙인다.

    반환값은 [{"page_number": 1, "category": "...", "match_count": 3}, ...]
    """
    results = []
    for page in pages:
        category, match_count = classify_page(page["text"])
        results.append(
            {
                "page_number": page["page_number"],
                "category": category,
                "match_count": match_count,
            }
        )
    return results


if __name__ == "__main__":
    import sys
    from extract import extract_pages

    if len(sys.argv) != 2:
        print("Usage: python src/rule_classifier.py <pdf_path>")
        sys.exit(1)

    pages = extract_pages(sys.argv[1])
    results = classify_pages(pages)
    for r in results:
        print(f"page {r['page_number']:2d}: {r['category']:15s} (match_count={r['match_count']})")
