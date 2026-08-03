"""분류 결과표 및 시각화 자료를 PDF로 생성한다 (자유형식 제출물)."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from extract import extract_pages
from main import classify_hybrid
from grouping import group_pages
from evaluate import load_gt, evaluate
from config import CATEGORIES

FONT = "AppleGothic"
plt.rcParams["font.family"] = FONT
plt.rcParams["axes.unicode_minus"] = False

A4 = (8.27, 11.69)


def page_text(pdf, lines, fontsize=11):
    fig, ax = plt.subplots(figsize=A4)
    ax.axis("off")
    ax.text(0.05, 0.97, "\n".join(lines), va="top", ha="left", fontsize=fontsize, family=FONT)
    pdf.savefig(fig)
    plt.close(fig)


def page_confusion_matrix(pdf, confusion, accuracy, correct, total):
    labels = [c for c in CATEGORIES if c in confusion or any(c in row for row in confusion.values())]
    matrix = np.array([[confusion.get(actual, {}).get(pred, 0) for pred in labels] for actual in labels])

    fig, ax = plt.subplots(figsize=A4)
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", family=FONT)
    ax.set_yticklabels(labels, family=FONT)
    ax.set_xlabel("예측 (Predicted)", family=FONT)
    ax.set_ylabel("정답 (Actual)", family=FONT)
    ax.set_title(f"package_01 Confusion Matrix\n정확도: {correct}/{total} = {accuracy*100:.1f}%", family=FONT)

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = matrix[i, j]
            if val > 0:
                ax.text(j, i, str(val), ha="center", va="center",
                        color="white" if val > matrix.max() / 2 else "black")

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def page_table(pdf, title, rows, gt=None):
    """rows: [{"page_number", "category", "source"}, ...]"""
    lines = [title, ""]
    header = f"{'Page':>5} {'Category':<15} {'Source':<14}"
    if gt:
        header += f" {'GT':<15} {'결과'}"
    lines.append(header)
    lines.append("-" * len(header))

    for r in rows:
        line = f"{r['page_number']:>5} {r['category']:<15} {r['source']:<14}"
        if gt:
            actual = gt.get(r["page_number"], "?")
            ok = "OK" if actual == r["category"] else "X"
            line += f" {actual:<15} {ok}"
        lines.append(line)

    # 페이지 하나에 다 안 들어가면 여러 페이지로 쪼갠다.
    lines_per_page = 55
    for i in range(0, len(lines), lines_per_page):
        chunk = lines[i:i + lines_per_page]
        if i > 0:
            chunk = [title + " (계속)", ""] + chunk
        page_text(pdf, chunk, fontsize=9)


def main():
    # package_01 (정답 있음)
    pages_01 = extract_pages("../data/01.990145627/01.990145627_shuffled.pdf")
    pred_01 = classify_hybrid(pages_01)
    gt_01 = load_gt("../data/01.990145627/package_01_gt.json")
    eval_01 = evaluate(pred_01, gt_01)
    groups_01 = group_pages(pred_01)

    # package_02 (정답 없음)
    pages_02 = extract_pages("../data/02.990367284_shuffled.pdf")
    pred_02 = classify_hybrid(pages_02)
    groups_02 = group_pages(pred_02)

    with PdfPages("../classification_report.pdf") as pdf:
        # Page 1: 개요
        page_text(pdf, [
            "MK Lending 대출서류 분류 프로젝트",
            "",
            "파이프라인 구조",
            "  1. extract.py       PDF 페이지별 텍스트 추출 + 반전 아티팩트 복원",
            "  2. rule_classifier   정규식 키워드 기반 1차 분류",
            "  3. llm_classifier    정규식이 아무 것도 못 찾은 페이지만",
            "                       Groq -> Cerebras 폴백으로 재분류",
            "  4. grouping.py       연속된 동일 카테고리 페이지를 문서 단위로 그룹핑",
            "  5. evaluate.py       정답(GT) 대비 정확도 / confusion matrix 산출",
            "",
            "핵심 결과 (package_01, 정답 있음)",
            f"  - 정확도: {eval_01['correct']}/{eval_01['total']} = {eval_01['accuracy']*100:.1f}%",
            f"  - 규칙 기반으로 {eval_01['total'] - 1}페이지, LLM 폴백은 정확히 1페이지(page 8)만 호출됨",
            "",
            f"package_02 (44페이지, 정답 없음) 분류 결과도 본 리포트에 포함",
            "",
            "주요 발견 및 한계",
            "  - 일부 페이지는 PDF 병합 과정에서 텍스트 전체가 문자 단위로",
            "    반전되어 추출됨 (원본 개별 문서에는 없던 현상)",
            "    -> 흔한 영어 단어 매칭 개수 비교 휴리스틱으로 감지/복원",
            "  - 두 shuffled 파일 모두 페이지 단위로 완전히 랜덤 셔플되어 있어",
            "    인접 페이지가 같은 카테고리인 경우가 전무함",
            "    -> 그룹핑 결과가 항상 1페이지짜리 그룹으로 나옴",
            "    (그룹핑 로직 자체는 합성 데이터로 다중 페이지 그룹 정상 동작 검증됨)",
            "  - INCOME_DOC 카테고리는 학습/검증 가능한 예시가 1페이지뿐이라",
            "    패턴 일반화에 근본적 한계 있음",
        ])

        # Page 2: confusion matrix
        page_confusion_matrix(pdf, eval_01["confusion"], eval_01["accuracy"], eval_01["correct"], eval_01["total"])

        # Page 3+: package_01 상세 결과표
        page_table(pdf, "package_01 페이지별 분류 결과 (정답 대비)", pred_01, gt=gt_01)

        # package_01 그룹핑 요약
        page_text(pdf, [
            "package_01 문서 그룹핑 결과",
            "",
            f"총 {len(pred_01)}페이지 -> {len(groups_01)}개 그룹",
            "(전부 1페이지짜리 그룹 - 위 '주요 발견' 참고)",
        ])

        # package_02 상세 결과표 (정답 없음)
        page_table(pdf, "package_02 페이지별 분류 결과 (정답 없음, 참고용)", pred_02, gt=None)

        page_text(pdf, [
            "package_02 문서 그룹핑 결과",
            "",
            f"총 {len(pred_02)}페이지 -> {len(groups_02)}개 그룹",
            "(전부 1페이지짜리 그룹)",
            "",
            "OTHER로 분류된 페이지 (원인 미확인, 후속 검토 필요)",
        ] + [f"  - page {p['page_number']}" for p in pred_02 if p["category"] == "OTHER"])

    print("classification_report.pdf 생성 완료")


if __name__ == "__main__":
    main()
