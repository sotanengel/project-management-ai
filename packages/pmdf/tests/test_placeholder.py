"""pmdfパッケージの最小プレースホルダテスト。

CIパイプライン(pytest)が「テストなしで失敗する」状態を避けるため、
最低1件のテストを常に存在させる。
"""

import pmdf


def test_pmdf_has_version() -> None:
    assert isinstance(pmdf.__version__, str)
    assert pmdf.__version__ != ""
