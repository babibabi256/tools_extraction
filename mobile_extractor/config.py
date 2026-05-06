"""携帯番号抽出ツール 設定値.

CLAUDE.md の規約に沿って、定数はここに集約する。

抽出対象:
    携帯番号 (070 / 080 / 090) のみ。
    050 や 03 などの固定電話・IP 電話は対象外として論理削除する。
"""

from pathlib import Path

# ----------------------------------------------------------------------------
# パイプラインバージョン
# ----------------------------------------------------------------------------
PIPELINE_VERSION = "mobile_extractor-1.0.0"
PROCESSED_BY_DEFAULT = "claude"

# ----------------------------------------------------------------------------
# パス
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

# パイプライン中間ファイル
RAW_DIR = OUTPUT_DIR / "raw"
CLEANED_DIR = OUTPUT_DIR / "cleaned"
FILTERED_DIR = OUTPUT_DIR / "filtered"
EXPORT_DIR = OUTPUT_DIR / "export"

RAW_CSV = RAW_DIR / "raw.csv"
CLEANED_CSV = CLEANED_DIR / "cleaned.csv"
FILTERED_CSV = FILTERED_DIR / "filtered.csv"
EXPORT_CSV = EXPORT_DIR / "final.csv"

# ----------------------------------------------------------------------------
# 抽出ルール
# ----------------------------------------------------------------------------
# CLAUDE.md「携帯番号抽出」に準拠
# 携帯番号は 11 桁（先頭が 070 / 080 / 090）
MOBILE_PREFIXES = ("070", "080", "090")
MOBILE_LENGTH = 11  # 例: 09012345678

# 明示的に除外するプレフィクス（ログで内訳を出すため）
# 050: IP 電話
# 020: M2M / IoT 用
# 0120 / 0800: フリーダイヤル
# 0570: ナビダイヤル
# その他は「固定電話 / その他」として一括分類
NON_MOBILE_KNOWN_PREFIXES = {
    "050": "ip_phone",
    "020": "m2m",
    "0120": "free_dial",
    "0800": "free_dial",
    "0570": "navi_dial",
}

# ----------------------------------------------------------------------------
# CSV 標準カラム（CLAUDE.md「CSV標準仕様」）
# ----------------------------------------------------------------------------
COL_NAME = "名称"
COL_TEL = "TEL"
COL_PREF = "都道府県"
COL_ADDR = "住所"
COL_REP = "代表者名"
COL_CAT_L = "大業種"
COL_CAT_M = "中業種"
COL_CAT_S = "小業種"
COL_CAT_XS = "細業種"
COL_HP = "HP"

BASE_COLUMNS = [
    COL_NAME,
    COL_TEL,
    COL_PREF,
    COL_ADDR,
    COL_REP,
    COL_CAT_L,
    COL_CAT_M,
    COL_CAT_S,
    COL_CAT_XS,
    COL_HP,
]

# ----------------------------------------------------------------------------
# 内部管理カラム（CLAUDE.md「内部管理カラム」）
# ----------------------------------------------------------------------------
COL_IS_DELETED = "is_deleted"
COL_DELETE_REASON = "delete_reason"
COL_PROCESS_STEP = "process_step"
COL_PROCESSED_AT = "processed_at"
COL_PROCESSED_BY = "processed_by"
COL_PIPELINE_VERSION = "pipeline_version"

INTERNAL_COLUMNS = [
    COL_IS_DELETED,
    COL_DELETE_REASON,
    COL_PROCESS_STEP,
    COL_PROCESSED_AT,
    COL_PROCESSED_BY,
    COL_PIPELINE_VERSION,
]

# ----------------------------------------------------------------------------
# 携帯抽出の追加カラム
# ----------------------------------------------------------------------------
COL_TEL_NORMALIZED = "tel_normalized"  # 正規化後の TEL（数字のみ）
COL_MOBILE_FLAG = "mobile_flag"        # True なら携帯（070/080/090）
COL_TEL_TYPE = "tel_type"              # mobile / ip_phone / free_dial / navi_dial / m2m / landline_or_other / invalid

MOBILE_COLUMNS = [
    COL_TEL_NORMALIZED,
    COL_MOBILE_FLAG,
    COL_TEL_TYPE,
]

# ----------------------------------------------------------------------------
# 削除理由（CLAUDE.md「欠損値処理」「重複除去ルール」を踏襲）
# ----------------------------------------------------------------------------
REASON_TEL_MISSING = "tel_missing"        # TEL 列が空
REASON_TEL_INVALID = "tel_invalid"        # 数字化しても空 / 桁数不正
REASON_NOT_MOBILE = "not_mobile"          # 070/080/090 以外（050 等）

# tel_type の値（出力用）
TEL_TYPE_MOBILE = "mobile"
TEL_TYPE_IP_PHONE = "ip_phone"
TEL_TYPE_FREE_DIAL = "free_dial"
TEL_TYPE_NAVI_DIAL = "navi_dial"
TEL_TYPE_M2M = "m2m"
TEL_TYPE_LANDLINE_OR_OTHER = "landline_or_other"
TEL_TYPE_INVALID = "invalid"

# ----------------------------------------------------------------------------
# CSV エンコーディング（UTF-8 固定 / Excel 互換のため BOM 付き）
# ----------------------------------------------------------------------------
CSV_ENCODING = "utf-8-sig"
