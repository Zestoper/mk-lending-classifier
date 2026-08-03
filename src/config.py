CREDIT_REPORT = "CREDIT_REPORT"
URLA_1003 = "URLA_1003"
TITLE_REPORT = "TITLE_REPORT"
INCOME_DOC = "INCOME_DOC"
OTHER = "OTHER"

CATEGORIES = [CREDIT_REPORT, URLA_1003, TITLE_REPORT, INCOME_DOC, OTHER]

# pages_by_category.txt(39페이지 실제 텍스트, 반전 복원 적용됨)를 보고
# 카테고리별로 반복 등장하는 고유 문구를 뽑았다. 대소문자는 무시하고
# 매칭할 것(re.IGNORECASE)을 전제로 작성함.
KEYWORD_PATTERNS = {
    # 18페이지 전부에서 확인: 신용평가 3사(TUC/EXP/EQX) 관련 표/용어,
    # XACTUS(신용조회 대행사) 헤더, ECOA(신용기회균등법) 표 라벨.
    CREDIT_REPORT: [
        r"\bECOA\b",
        r"Trended Data",
        r"Repositories:\s*[A-Z]{3}/[A-Z]{3}/[A-Z]{3}",
        r"Credit Score (Information|Disclosure)",
        r"\bXACTUS\b",
        r"consumer reporting agenc(y|ies)",
        r"Credit Report",
    ],
    # 11페이지 전부의 바닥글에 거의 그대로 반복됨: 폼 이름 + 버전 표기.
    URLA_1003: [
        r"Uniform Residential Loan Application",
        r"Fannie Mae Form\s*1003",
        r"Freddie Mac Form\s*65",
        r"GURLA20S",
        r"Borrower Name:",
    ],
    # 9페이지 대부분에서 확인: 발급사(Fidelity National Title)와
    # 문서 양식 코드(CLTA Preliminary Report, PRELIM NO.)가 반복.
    TITLE_REPORT: [
        r"FIDELITY NATIONAL TITLE",
        r"CLTA Preliminary Report",
        r"PRELIM(INARY)?\s*(NO\.|REPORT)",
        r"Title Insurance",
        r"Schedule [AB]\b",
    ],
    # 주의: 표본이 1페이지뿐이라 일반화하기 어려움. 이 페이지는 실제로는
    # 부동산 중개인(Realtor)의 손익 정산서 형태였고, "Profit and Loss"
    # 같은 일반적인 문구 자체가 없었음 — 아래 패턴들은 이 1개 예시에서
    # 뽑은 것이라 다른 INCOME_DOC(Paystub, W-2, 1040, 1099, VOE 등)에는
    # 전혀 안 맞을 가능성이 높다. rule_classifier 정확도 측정 후
    # 반드시 재검토가 필요한 카테고리.
    INCOME_DOC: [
        r"CTEC #",
        r"\bRealtor\b",
        r"Profit and Loss",
        r"P\s*&\s*L\b",
        r"\bW-?2\b",
        r"\b1099\b",
        r"\b1040\b",
        r"Pay ?stub",
        r"Verification of Employment",
    ],
}
