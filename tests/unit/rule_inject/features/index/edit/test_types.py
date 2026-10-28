"""features/index/edit/types.py の単体テスト。"""

from __future__ import annotations


def test_lock_for() -> None:
    """同じ場所には同じロック、違う場所には別のロックを返す（正常系）。"""
    from rule_inject.features.index.edit import IndexLocks

    # 準備
    locks = IndexLocks()
    # 実行
    first = locks.lock_for("/p/a.yaml")
    second = locks.lock_for("/p/a.yaml")
    other = locks.lock_for("/p/b.yaml")
    # 検証
    assert first is second
    assert first is not other
