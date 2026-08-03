"""분류 결과를 바탕으로 원본 PDF를 카테고리별 파일로 실제로 쪼갠다.

과제 배경에 나온 "문서 분류(Document Classification / Splitting)"를
결과 라벨만 내는 게 아니라 실제 산출물(PDF 파일)로도 보여주기 위한 스크립트.
"""

import os
import sys

from pypdf import PdfReader, PdfWriter

from extract import extract_pages
from main import classify_hybrid


def split_pdf_by_category(pdf_path: str, output_dir: str) -> dict:
    """pdf_path를 분류한 뒤, 카테고리별로 페이지를 모아 별도 PDF로 저장한다.

    반환값: {"CREDIT_REPORT": "path/to/CREDIT_REPORT.pdf", ...}
    """
    pages = extract_pages(pdf_path)
    predictions = classify_hybrid(pages)

    # 카테고리 -> [0-indexed page 번호] 로 모은다.
    # pypdf는 0-indexed, 우리 page_number는 1-indexed라 -1 필요.
    pages_by_category: dict[str, list[int]] = {}
    for pred in predictions:
        pages_by_category.setdefault(pred["category"], []).append(pred["page_number"] - 1)

    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(pdf_path)

    output_paths = {}
    for category, page_indices in pages_by_category.items():
        writer = PdfWriter()
        for idx in sorted(page_indices):
            page = reader.pages[idx]
            # 원본 페이지의 /Rotate 메타데이터(90/180/270도)를 그대로
            # 복사하면 쪼갠 파일에서도 화면에 돌아간 채로 보인다.
            # 회전을 상쇄해서 0도로 정규화한다.
            current_rotation = page.get("/Rotate", 0)
            if current_rotation:
                page.rotate(-current_rotation)
            writer.add_page(page)

        out_path = os.path.join(output_dir, f"{category}.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        output_paths[category] = out_path

    return output_paths


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/split_by_category.py <pdf_path> <output_dir>")
        sys.exit(1)

    pdf_path, output_dir = sys.argv[1], sys.argv[2]
    result = split_pdf_by_category(pdf_path, output_dir)

    for category, path in result.items():
        page_count = len(PdfReader(path).pages)
        print(f"{category:15s} -> {path} ({page_count}페이지)")
