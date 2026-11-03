"""PDF から表のページだけを切り出す。

LLM には表のページだけを 1ページの PDF で渡す（decisions/0003）。
"""

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def extract_page(pdf_path: Path, page_number: int) -> bytes:
    """PDF の 1ページを、そのページだけの PDF にする。

    Args:
        pdf_path: 元の PDF。
        page_number: 切り出すページ（1 始まり。`meta.json` の `pdf_page`）。

    Returns:
        1ページの PDF のバイト列。

    Raises:
        ValueError: page_number が PDF のページの範囲にない。
    """
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)
    if not 1 <= page_number <= page_count:
        raise ValueError(
            f"{pdf_path} は {page_count} ページで、{page_number} ページはない"
        )
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
