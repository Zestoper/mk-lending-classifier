import sys
import json
from collections import defaultdict

from extract import extract_pages
from rule_classifier import classify_pages
from config import CATEGORIES

# match_count가 이 값 이하인 페이지는 "규칙 기반 확신이 낮다"고 보고
# LLM 폴백 후보로 분류한다.
#
# 원래는 1(=1개만 매칭돼도 애매하다고 간주)로 뒀었는데, 실제로
# page 3("XACTUS" 단 하나만 매칭)처럼 매칭 개수는 적어도 매우
# 특이적인(specific) 키워드라 오히려 신뢰도가 높은 케이스가 있었다.
# 이런 페이지까지 LLM으로 넘기면 규칙이 이미 맞춘 답을 LLM이 다시
# 틀리게 뒤집는 역효과가 생겨서(38/39 -> 37/39로 오히려 하락),
# "패턴이 1개라도 있으면 일단 신뢰"하는 쪽으로 기준을 낮췄다.
# 0으로 두면 "정규식이 단 하나도 못 찾은(=OTHER) 페이지"만 LLM으로
# 넘어간다.
LOW_CONFIDENCE_THRESHOLD = 0


def load_gt(gt_path: str) -> dict:
    with open(gt_path) as f:
        entries = json.load(f)
    return {e["page_number"]: e["category"] for e in entries}


def evaluate(predictions: list[dict], gt: dict) -> dict:
    """예측 결과와 GT를 비교해서 정확도와 confusion matrix를 계산한다.

    confusion matrix는 confusion[정답][예측] = 개수 형태의 중첩 딕셔너리.
    """
    total = len(predictions)
    correct = 0
    confusion = defaultdict(lambda: defaultdict(int))
    wrong_pages = []

    for pred in predictions:
        page_number = pred["page_number"]
        predicted = pred["category"]
        actual = gt[page_number]

        confusion[actual][predicted] += 1
        if predicted == actual:
            correct += 1
        else:
            wrong_pages.append((page_number, actual, predicted))

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "confusion": confusion,
        "wrong_pages": wrong_pages,
    }


def print_confusion_matrix(confusion: dict):
    labels = sorted(set(confusion.keys()) | {p for row in confusion.values() for p in row})
    header = " " * 16 + "".join(f"{l[:12]:>13s}" for l in labels)
    print(header)
    for actual in labels:
        row = "".join(f"{confusion[actual].get(pred, 0):>13d}" for pred in labels)
        print(f"{actual[:15]:15s} {row}")


def find_low_confidence_pages(predictions: list[dict]) -> list[int]:
    """GT 없이도(=실전 배포 상황에서도) 판단 가능한 기준으로 뽑은,
    LLM 폴백이 필요해 보이는 페이지 번호 목록."""
    return [
        p["page_number"]
        for p in predictions
        if p["match_count"] <= LOW_CONFIDENCE_THRESHOLD
    ]


def main():
    if len(sys.argv) != 3:
        print("Usage: python src/evaluate.py <pdf_path> <gt_json_path>")
        sys.exit(1)

    pdf_path, gt_path = sys.argv[1], sys.argv[2]

    pages = extract_pages(pdf_path)
    predictions = classify_pages(pages)
    gt = load_gt(gt_path)

    result = evaluate(predictions, gt)

    print(f"정확도: {result['correct']}/{result['total']} = {result['accuracy']*100:.1f}%")
    print()
    print("Confusion Matrix (행=정답, 열=예측):")
    print_confusion_matrix(result["confusion"])
    print()

    if result["wrong_pages"]:
        print("틀린 페이지:")
        for page_number, actual, predicted in result["wrong_pages"]:
            print(f"  page {page_number}: 정답={actual}, 예측={predicted}")
    print()

    low_conf = find_low_confidence_pages(predictions)
    print(f"규칙 기반 확신이 낮은 페이지 (LLM 폴백 후보, match_count<={LOW_CONFIDENCE_THRESHOLD}): {low_conf}")


if __name__ == "__main__":
    main()
