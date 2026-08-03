def group_pages(predictions: list[dict]) -> list[dict]:
    """페이지별 분류 결과를 받아, 연속된 페이지 중 카테고리가 같은
    것들을 하나의 문서로 묶는다.

    predictions: [{"page_number": ..., "category": ...}, ...]
    (main.py의 classify_hybrid, rule_classifier.classify_pages 결과 모두 호환)

    반환값: [{"category": ..., "start_page": ..., "end_page": ..., "page_count": ...}, ...]
    """
    if not predictions:
        return []

    # page_number 순서로 정렬해야 "연속"이라는 개념이 성립한다.
    sorted_preds = sorted(predictions, key=lambda p: p["page_number"])

    groups = []
    current = None

    for pred in sorted_preds:
        page_number = pred["page_number"]
        category = pred["category"]

        # 직전 그룹과 카테고리가 같고, 페이지 번호도 바로 다음(+1)이어야
        # 같은 문서로 묶는다. 둘 중 하나라도 깨지면 새 문서 시작.
        if (
            current is not None
            and category == current["category"]
            and page_number == current["end_page"] + 1
        ):
            current["end_page"] = page_number
        else:
            if current is not None:
                groups.append(current)
            current = {"category": category, "start_page": page_number, "end_page": page_number}

    if current is not None:
        groups.append(current)

    for g in groups:
        g["page_count"] = g["end_page"] - g["start_page"] + 1

    return groups


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from extract import extract_pages
    from main import classify_hybrid

    if len(sys.argv) != 2:
        print("Usage: python src/grouping.py <pdf_path>")
        sys.exit(1)

    pages = extract_pages(sys.argv[1])
    predictions = classify_hybrid(pages)
    groups = group_pages(predictions)

    for g in groups:
        if g["page_count"] == 1:
            print(f"{g['category']:15s} page {g['start_page']}")
        else:
            print(f"{g['category']:15s} page {g['start_page']}-{g['end_page']} ({g['page_count']}페이지)")

    print(f"\n총 {len(predictions)}페이지 -> {len(groups)}개 문서 그룹")
