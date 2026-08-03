import sys
import json
import io

import pdfplumber
import pytesseract
from pypdf import PdfReader, PdfWriter

# 일부 페이지는 PDF 병합(shuffle) 과정에서 텍스트 전체가 문자 단위로
# 뒤집혀서 추출된다. 예: "MK LENDING CORP" -> "PROC GNIDNEL KM"
# 원본(섞이기 전) 개별 문서에는 이 현상이 없었으므로, 병합 도구가
# 특정 페이지에 실제로는 필요 없는 회전 플래그(/Rotate)를 잘못 씌운
# 것으로 확인했다.
#
# 처음엔 "흔한 영어 단어가 정방향/역방향 중 어디에 더 많은지" 세는
# 휴리스틱으로 감지했었는데, 나중에 PDF 산출물을 직접 눈으로 검증하는
# 과정에서 pdfplumber가 노출하는 page.rotation(=/Rotate 값)을 그대로
# 원인으로 확인할 수 있다는 걸 알게 됐다. 휴리스틱은 우연한 단어 충돌로
# 오탐이 생길 수 있는 반면(예: "No"가 뒤집히면 "oN"이 되어 "on"과 혼동),
# /Rotate는 PDF 자체에 박힌 값이라 훨씬 결정적(deterministic)이다.
#
# 실제 데이터로 검증: package_01 39페이지에서 이 방식으로 분류했을 때
# 기존 휴리스틱과 정확히 동일한 38/39(97.4%) 결과가 나왔다 — 즉 이
# 방식이 최소한 이 데이터셋에서는 휴리스틱을 완전히 대체할 수 있다.
#
# 90도 회전 페이지는 반전이 아니라 단어 "순서"만 뒤섞이고 개별 단어
# 철자는 정상이라(정규식 키워드 매칭에는 영향 없음), 여기에 반전을
# 적용하면 오히려 망가진다. 그래서 180/270도만 반전 대상으로 삼는다.
REVERSAL_ROTATIONS = (180, 270)


def needs_reversal_fix(rotation: int) -> bool:
    """페이지의 /Rotate 값(page.rotation)을 보고 반전 복원이 필요한지 결정한다."""
    return rotation in REVERSAL_ROTATIONS


def ocr_page_text(reader: PdfReader, page_index: int) -> str:
    """extract_text()가 완전히 실패한(빈 문자열) 페이지를 OCR로 복구한다.

    이런 페이지는 폰트에 문자->유니코드 매핑(ToUnicode CMap)이 없어
    텍스트 레이어 자체를 못 읽는 경우로 확인됐다(package_02의 11/26/40번
    페이지). 글자 모양(글리프)은 정상 렌더링되므로, 페이지를 이미지로
    그려서 OCR로 문자를 인식한다.

    /Rotate 메타데이터가 병합 과정에서 잘못 붙어있는 경우가 많아(원본은
    똑바른 페이지인데 회전 플래그만 얹힌 상태), 렌더링 전에 회전을 0도로
    정규화하지 않으면 이미지 자체가 거꾸로/옆으로 나와 OCR도 실패한다.
    """
    page = reader.pages[page_index]
    rotation = page.get("/Rotate", 0)
    if rotation:
        page.rotate(-rotation)

    writer = PdfWriter()
    writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    with pdfplumber.open(buf) as single_page_pdf:
        image = single_page_pdf.pages[0].to_image(resolution=200).original
        return pytesseract.image_to_string(image)


def extract_pages(pdf_path: str) -> list[dict]:
    """PDF를 열어 페이지별 텍스트를 추출한다.

    반환값은 [{"page_number": 1, "text": "..."}, ...] 형태.
    page_number는 1-indexed.
    """
    pages = []
    # OCR 폴백(ocr_page_text)에서 페이지 회전 정규화를 하려면 pypdf의
    # PdfReader가 필요해서, pdfplumber와 별개로 한 번만 열어둔다.
    reader = PdfReader(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            raw_text = page.extract_text()
            # extract_text()가 None을 줄 수 있으니(폰트 인코딩 문제 등),
            # 이후 로직이 안전하게 동작하도록 빈 문자열로 먼저 정규화한다.
            raw_text = raw_text if raw_text is not None else ""

            used_ocr = False
            reversed_fixed = False

            if not raw_text.strip():
                # 텍스트 레이어 자체가 비어있는 경우에만 OCR로 폴백한다.
                # OCR은 느리고 완벽하지 않아서, 정상 추출되는 페이지에는
                # 쓰지 않는다. OCR은 회전을 이미 정규화한 상태로 렌더링해서
                # 읽으므로, 아래 반전 로직을 또 적용하면 안 된다.
                text = ocr_page_text(reader, i)
                used_ocr = True
            elif needs_reversal_fix(page.rotation):
                # /Rotate가 180/270도인 페이지만 문자열을 통째로 뒤집어
                # 정상 방향으로 복원한다.
                text = raw_text[::-1]
                reversed_fixed = True
            else:
                text = raw_text

            pages.append(
                {
                    "page_number": i + 1,
                    "text": text,
                    "char_count": len(text),
                    # 나중에 "이 페이지는 반전 복원 대상이었다"는 걸
                    # 추적하려고 남겨두는 플래그.
                    "was_reversed": reversed_fixed,
                    # OCR로 복구된 페이지인지 추적(정확도가 상대적으로
                    # 낮을 수 있음을 나중에 참고하기 위함).
                    "used_ocr": used_ocr,
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
        ocr_tag = " [OCR]" if p["used_ocr"] else ""
        print(f"[Page {p['page_number']}] chars={p['char_count']}{ocr_tag}")
        print("=" * 60)
        if p["char_count"] == 0:
            print("(텍스트 없음 - OCR도 실패)")
        else:
            print(p["text"])

    print(f"\n총 {len(pages)} 페이지, 텍스트 없는 페이지: "
          f"{sum(1 for p in pages if p['char_count'] == 0)}개, "
          f"OCR로 복구된 페이지: {sum(1 for p in pages if p['used_ocr'])}개")


if __name__ == "__main__":
    main()
