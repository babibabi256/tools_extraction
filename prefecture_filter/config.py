"""都道府県フィルタツール 設定値.

CLAUDE.md の規約に沿って、定数はここに集約する。

抽出対象:
    `--prefecture` で指定された都道府県のみ。
    指定外の都道府県は論理削除する。
    都道府県カラムが空 / 未知の値の場合も論理削除する。
"""

from pathlib import Path

# ----------------------------------------------------------------------------
# パイプラインバージョン
# ----------------------------------------------------------------------------
PIPELINE_VERSION = "prefecture_filter-1.0.0"
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
# 都道府県フィルタの追加カラム
# ----------------------------------------------------------------------------
COL_PREF_MATCHED = "pref_matched"  # True なら指定都道府県に一致

PREF_COLUMNS = [
    COL_PREF_MATCHED,
]

# ----------------------------------------------------------------------------
# 削除理由（CLAUDE.md「欠損値処理」を踏襲）
# ----------------------------------------------------------------------------
REASON_PREF_MISSING = "pref_missing"     # 都道府県カラムが空
REASON_PREF_UNMATCHED = "pref_unmatched"  # 指定都道府県と不一致
REASON_INVALID_PREFECTURE = "invalid_prefecture"  # 47都道府県に存在しない値

# ----------------------------------------------------------------------------
# 47 都道府県マスタ（CLI 引数バリデーション用）
# ----------------------------------------------------------------------------
VALID_PREFECTURES = (
    "北海道",
    "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県",
    "沖縄県",
)

# ----------------------------------------------------------------------------
# CSV エンコーディング（UTF-8 固定 / Excel 互換のため BOM 付き）
# ----------------------------------------------------------------------------
CSV_ENCODING = "utf-8-sig"
