import argparse

from extract import extract_pages
from rule_classifier import classify_pages
from llm_classifier import classify_with_llm
from evaluate import load_gt, evaluate, print_confusion_matrix, find_low_confidence_pages


def classify_hybrid(pages: list[dict]) -> list[dict]:
    """규칙 기반으로 1차 분류하고, 확신이 낮은(=정규식이 하나도 못 찾은)
    페이지만 LLM(Groq -> Cerebras 폴백)으로 재분류하는 하이브리드 파이프라인.

    반환값: [{"page_number": ..., "category": ..., "source": "rule"|"llm:groq"|"llm:cerebras"}, ...]
    """
    rule_predictions = classify_pages(pages)
    low_conf_numbers = set(find_low_confidence_pages(rule_predictions))
    pages_by_number = {p["page_number"]: p for p in pages}

    final = []
    for pred in rule_predictions:
        page_number = pred["page_number"]
        if page_number in low_conf_numbers:
            text = pages_by_number[page_number]["text"]
            category, provider = classify_with_llm(text)
            final.append(
                {
                    "page_number": page_number,
                    "category": category,
                    "source": f"llm:{provider}",
                }
            )
        else:
            final.append(
                {
                    "page_number": page_number,
                    "category": pred["category"],
                    "source": "rule",
                }
            )
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--gt", required=False, help="정답 JSON 경로 (있으면 정확도까지 출력)")
    args = parser.parse_args()

    pages = extract_pages(args.pdf)
    results = classify_hybrid(pages)

    for r in results:
        print(f"page {r['page_number']:2d}: {r['category']:15s} (source={r['source']})")

    if args.gt:
        gt = load_gt(args.gt)
        eval_result = evaluate(results, gt)
        print()
        print(f"정확도: {eval_result['correct']}/{eval_result['total']} = {eval_result['accuracy']*100:.1f}%")
        print()
        print("Confusion Matrix (행=정답, 열=예측):")
        print_confusion_matrix(eval_result["confusion"])
        if eval_result["wrong_pages"]:
            print()
            print("틀린 페이지:")
            for page_number, actual, predicted in eval_result["wrong_pages"]:
                print(f"  page {page_number}: 정답={actual}, 예측={predicted}")


if __name__ == "__main__":
    main()
