"""パッケージが読み込めることを確かめる（最初のテストができたら消してよい）。"""

import llm_pdf_table_extractor


def test_import_package_has_docstring() -> None:
    """パッケージを読み込むと docstring がある。"""
    assert llm_pdf_table_extractor.__doc__
