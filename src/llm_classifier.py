import os

from dotenv import load_dotenv
from groq import Groq
from cerebras.cloud.sdk import Cerebras

from config import CATEGORIES, OTHER

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile 2026-08-16 종료
CEREBRAS_MODEL = "llama3.3-70b"

CATEGORY_DESCRIPTIONS = {
    "URLA_1003": "대출 신청서 (Uniform Residential Loan Application, Form 1003)",
    "INCOME_DOC": "소득 증빙 (Paystub, W-2, 1040, 1099, VOE 등)",
    "CREDIT_REPORT": "신용 보고서 (Tri-merge Credit Report)",
    "TITLE_REPORT": "권원 보고서 (Title Commitment / Preliminary Title Report)",
    "OTHER": "위 항목에 해당하지 않는 페이지",
}

# 규칙 기반 분류가 확신하지 못한 페이지들(evaluate.py의
# find_low_confidence_pages 참고)의 실제 텍스트를 직접 보고,
# "이런 식으로 애매한 페이지는 이렇게 판단한다"는 예시를 골라 채울 것.
# 형식: {"text": "실제 페이지 텍스트 일부", "category": "CREDIT_REPORT"}
FEW_SHOT_EXAMPLES = [
]


def build_prompt(text: str) -> str:
    categories_block = "\n".join(
        f"- {cat}: {CATEGORY_DESCRIPTIONS.get(cat, '')}" for cat in CATEGORIES
    )

    examples_block = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_block += f"\n[예시 텍스트]\n{ex['text']}\n[정답] {ex['category']}\n"

    return f"""너는 대출 서류 PDF의 한 페이지 텍스트를 보고 문서 유형을 분류하는 분류기다.
아래 카테고리 중 정확히 하나만 골라서, 카테고리 이름만 출력해라. 다른 설명은 하지 마라.

카테고리:
{categories_block}
{examples_block}
[분류할 텍스트]
{text[:3000]}

[정답]"""


def _parse_category(response_text: str) -> str:
    response_text = response_text.strip()
    for cat in CATEGORIES:
        if cat in response_text:
            return cat
    return OTHER


def _call_groq(prompt: str) -> str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        extra_body={"reasoning_effort": "low"},  # gpt-oss는 추론형 모델 — 분류는 짧게 생각해도 충분
    )
    return completion.choices[0].message.content


def _call_cerebras(prompt: str) -> str:
    client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])
    completion = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return completion.choices[0].message.content


def classify_with_llm(text: str) -> tuple[str, str]:
    """Groq를 1순위로 시도하고, 예외(rate limit, 타임아웃, 오류 등) 발생 시
    Cerebras로 폴백한다.

    반환값: (카테고리, 사용된 provider 또는 실패 사유)
    """
    prompt = build_prompt(text)

    try:
        raw = _call_groq(prompt)
        return _parse_category(raw), "groq"
    except Exception as groq_error:
        try:
            raw = _call_cerebras(prompt)
            return _parse_category(raw), "cerebras"
        except Exception as cerebras_error:
            return OTHER, f"both failed: groq={groq_error!r}, cerebras={cerebras_error!r}"


if __name__ == "__main__":
    import sys
    from extract import extract_pages
    from rule_classifier import classify_pages
    from evaluate import find_low_confidence_pages

    if len(sys.argv) != 2:
        print("Usage: python src/llm_classifier.py <pdf_path>")
        sys.exit(1)

    pages = extract_pages(sys.argv[1])
    predictions = classify_pages(pages)
    low_conf_page_numbers = set(find_low_confidence_pages(predictions))

    pages_by_number = {p["page_number"]: p for p in pages}

    for page_number in sorted(low_conf_page_numbers):
        text = pages_by_number[page_number]["text"]
        category, provider = classify_with_llm(text)
        print(f"page {page_number:2d}: {category:15s} (provider={provider})")
