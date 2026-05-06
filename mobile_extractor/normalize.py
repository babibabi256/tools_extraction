"""電話番号 正規化ユーティリティ.

CLAUDE.md「データ加工ルール / 電話番号正規化」に準拠。
    - 全角を半角へ変換 (NFKC)
    - 空白除去
    - ハイフン等の記号を除去 (数字のみへ)

携帯判定ヘルパも同梱する。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Tuple

import config


# ============================================================================
# 共通
# ============================================================================
_NON_DIGIT = re.compile(r"\D")


def _safe_str(value) -> str:
    """None / NaN を空文字に変換した上で str 化."""
    if value is None:
        return ""
    try:
        if value != value:  # NaN チェック
            return ""
    except Exception:
        pass
    return str(value)


def _to_halfwidth(text: str) -> str:
    """全角→半角 (NFKC)."""
    return unicodedata.normalize("NFKC", text)


# ============================================================================
# TEL 正規化
# ============================================================================
def normalize_tel(tel) -> str:
    """電話番号を数字のみに正規化する.

    例:
        "090-1234-5678"        -> "09012345678"
        "０９０ー１２３４ー５６７８" -> "09012345678"
        "(03) 1234-5678"       -> "0312345678"
    """
    s = _safe_str(tel)
    if not s:
        return ""

    # 全角→半角
    s = _to_halfwidth(s)
    # 数字以外を除去（ハイフン・空白・括弧などまとめて）
    s = _NON_DIGIT.sub("", s)
    return s


# ============================================================================
# 携帯判定 / 種別判定
# ============================================================================
def is_mobile_tel(normalized_tel: str) -> bool:
    """正規化済み TEL が携帯番号 (070/080/090) か判定.

    桁数も併せて確認する（携帯は 11 桁固定）.
    """
    if not normalized_tel:
        return False
    if len(normalized_tel) != config.MOBILE_LENGTH:
        return False
    return normalized_tel.startswith(config.MOBILE_PREFIXES)


def classify_tel(normalized_tel: str) -> Tuple[str, bool]:
    """正規化済み TEL を種別分類する.

    Returns:
        (tel_type, is_mobile)
        tel_type は config.TEL_TYPE_* のいずれか。
    """
    if not normalized_tel:
        return config.TEL_TYPE_INVALID, False

    # 携帯（11 桁 + 070/080/090）
    if is_mobile_tel(normalized_tel):
        return config.TEL_TYPE_MOBILE, True

    # 既知の非携帯プレフィクスを長い順にチェック
    for prefix in sorted(config.NON_MOBILE_KNOWN_PREFIXES.keys(), key=len, reverse=True):
        if normalized_tel.startswith(prefix):
            label = config.NON_MOBILE_KNOWN_PREFIXES[prefix]
            # config の文字列にマッピング
            mapping = {
                "ip_phone": config.TEL_TYPE_IP_PHONE,
                "free_dial": config.TEL_TYPE_FREE_DIAL,
                "navi_dial": config.TEL_TYPE_NAVI_DIAL,
                "m2m": config.TEL_TYPE_M2M,
            }
            return mapping.get(label, config.TEL_TYPE_LANDLINE_OR_OTHER), False

    # 桁数不正（携帯プレフィクスだが 11 桁に満たない / 超える など）
    if normalized_tel.startswith(config.MOBILE_PREFIXES):
        return config.TEL_TYPE_INVALID, False

    # それ以外（03/06 等の固定電話 等）
    return config.TEL_TYPE_LANDLINE_OR_OTHER, False
