"""汎用抽出ツール 設定値."""

from pathlib import Path

PIPELINE_VERSION = "generic_extractor-1.0.0"
PROCESSED_BY_DEFAULT = "codex"

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"
RULES_DIR = BASE_DIR / "rules"

RAW_DIR = OUTPUT_DIR / "raw"
CLEANED_DIR = OUTPUT_DIR / "cleaned"
FILTERED_DIR = OUTPUT_DIR / "filtered"
EXPORT_DIR = OUTPUT_DIR / "export"

RAW_CSV = RAW_DIR / "raw.csv"
CLEANED_CSV = CLEANED_DIR / "cleaned.csv"
FILTERED_CSV = FILTERED_DIR / "filtered.csv"
EXPORT_CSV = EXPORT_DIR / "final.csv"

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

CSV_ENCODING = "utf-8-sig"
