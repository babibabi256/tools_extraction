"""携帯電話番号 抽出ツール.

CLAUDE.md / 名寄せ ツールの構造に準拠。

仕様:
    - 携帯番号 (070 / 080 / 090, 11 桁) のみを残す。
    - 050 (IP電話) や 03 / 06 等の固定電話、フリーダイヤル等は論理削除。
    - 元データは破壊せず、論理削除フラグ (is_deleted / delete_reason) で管理。

パイプライン:
    raw -> cleaned -> filtered -> export
    各工程で CSV を保存し、件数ログを出力する。

使い方:
    python main.py --input ./input/sample.csv
    python main.py                       # input/ 配下の最新 CSV を自動採用
    python main.py --keep-all-in-export  # filtered.csv 同等を export にも出す
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

import config
import normalize as nm


# ============================================================================
# ログ
# ============================================================================
def setup_logger(log_path: Path) -> logging.Logger:
    """コンソールとファイルへ同時出力するロガーを構築."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("mobile_extractor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(levelname)s] %(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ============================================================================
# 共通: 内部管理カラム整備
# ============================================================================
def _coerce_bool(series: pd.Series) -> pd.Series:
    """真偽列を bool に強制変換する.

    CSV を `dtype=str` で読み込むと "True"/"False"/"" が文字列で入るため、
    ~ や & 演算ができるよう bool 化する。
    """
    if series.dtype == bool:
        return series
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(("true", "1", "yes", "t"))
    )


def ensure_internal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """内部管理カラム / 携帯抽出カラムが無ければ追加。
    既にある場合も真偽列は bool に正規化する。"""
    for col in config.INTERNAL_COLUMNS:
        if col not in df.columns:
            if col == config.COL_IS_DELETED:
                df[col] = False
            else:
                df[col] = ""
    for col in config.MOBILE_COLUMNS:
        if col not in df.columns:
            if col == config.COL_MOBILE_FLAG:
                df[col] = False
            else:
                df[col] = ""

    # 真偽列は必ず bool に揃える（既存値が "False" 等の文字列でも対応）
    df[config.COL_IS_DELETED] = _coerce_bool(df[config.COL_IS_DELETED])
    df[config.COL_MOBILE_FLAG] = _coerce_bool(df[config.COL_MOBILE_FLAG])
    return df


def stamp_process(
    df: pd.DataFrame, step: str, processed_by: str = config.PROCESSED_BY_DEFAULT
) -> pd.DataFrame:
    """加工日時 / 工程名 / 実行者 / バージョンを記録."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df[config.COL_PROCESS_STEP] = step
    df[config.COL_PROCESSED_AT] = now
    df[config.COL_PROCESSED_BY] = processed_by
    df[config.COL_PIPELINE_VERSION] = config.PIPELINE_VERSION
    return df


# ============================================================================
# 1) raw 保存
# ============================================================================
def load_and_save_raw(input_path: Path, logger: logging.Logger) -> pd.DataFrame:
    logger.info(f"入力ファイル: {input_path}")
    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    logger.info(f"[INFO] 入力件数: {len(df):,}")

    if config.COL_TEL not in df.columns:
        raise ValueError(
            f"必須カラム '{config.COL_TEL}' が入力CSVに存在しません: "
            f"columns={list(df.columns)}"
        )

    df = ensure_internal_columns(df)
    df = stamp_process(df, step="raw")

    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"raw 保存: {config.RAW_CSV}")
    return df


# ============================================================================
# 2) cleaned: TEL を正規化（数字のみ）
# ============================================================================
def clean_data(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """TEL 正規化と種別判定を付与（元 TEL カラムは破壊しない）."""
    df = df.copy()

    df[config.COL_TEL_NORMALIZED] = df[config.COL_TEL].map(nm.normalize_tel)

    # 種別とフラグを付与
    types_and_flags = df[config.COL_TEL_NORMALIZED].map(nm.classify_tel)
    df[config.COL_TEL_TYPE] = types_and_flags.map(lambda t: t[0])
    df[config.COL_MOBILE_FLAG] = types_and_flags.map(lambda t: t[1])

    df = stamp_process(df, step="cleaned")

    config.CLEANED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEANED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"cleaned 保存: {config.CLEANED_CSV}")
    return df


# ============================================================================
# 3) filtered: 携帯以外を論理削除
# ============================================================================
def filter_mobile_only(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """携帯以外を論理削除する。物理削除はしない."""
    df = df.copy()
    df = ensure_internal_columns(df)

    # --- 欠損: TEL 列が空文字 ----------------------------------------------
    raw_tel_blank_mask = df[config.COL_TEL].astype(str).str.strip() == ""
    n_missing = int(raw_tel_blank_mask.sum())
    df.loc[raw_tel_blank_mask, config.COL_IS_DELETED] = True
    df.loc[raw_tel_blank_mask, config.COL_DELETE_REASON] = config.REASON_TEL_MISSING
    logger.info(
        f"[INFO] 欠損除去件数: {n_missing:,}（理由: {config.REASON_TEL_MISSING}）"
    )

    # --- 不正: 数字化したら空 / 桁数不正など --------------------------------
    invalid_mask = (
        ~df[config.COL_IS_DELETED]
        & (df[config.COL_TEL_TYPE] == config.TEL_TYPE_INVALID)
    )
    n_invalid = int(invalid_mask.sum())
    df.loc[invalid_mask, config.COL_IS_DELETED] = True
    df.loc[invalid_mask, config.COL_DELETE_REASON] = config.REASON_TEL_INVALID
    logger.info(
        f"[INFO] 不正除去件数: {n_invalid:,}（理由: {config.REASON_TEL_INVALID}）"
    )

    # --- 携帯以外（050 / 0120 / 03 等） -------------------------------------
    not_mobile_mask = ~df[config.COL_IS_DELETED] & ~df[config.COL_MOBILE_FLAG]
    n_not_mobile = int(not_mobile_mask.sum())
    df.loc[not_mobile_mask, config.COL_IS_DELETED] = True
    df.loc[not_mobile_mask, config.COL_DELETE_REASON] = config.REASON_NOT_MOBILE
    logger.info(
        f"[INFO] 非携帯除去件数: {n_not_mobile:,}（理由: {config.REASON_NOT_MOBILE}）"
    )

    # --- 種別ごとの内訳ログ -------------------------------------------------
    if config.COL_TEL_TYPE in df.columns:
        breakdown = df[config.COL_TEL_TYPE].value_counts(dropna=False).to_dict()
        logger.info(f"[INFO] tel_type 内訳: {breakdown}")

    n_remaining = int((~df[config.COL_IS_DELETED]).sum())
    logger.info(f"[INFO] フィルタ後件数: {n_remaining:,}")

    df = stamp_process(df, step="filtered")

    config.FILTERED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.FILTERED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"filtered 保存: {config.FILTERED_CSV}")
    return df


# ============================================================================
# 4) export: 携帯のみ最終 CSV へ
# ============================================================================
def export_final(
    df: pd.DataFrame,
    logger: logging.Logger,
    project_name: str,
    keep_all: bool = False,
) -> Path:
    df = df.copy()
    df = stamp_process(df, step="export")

    if keep_all:
        final_df = df.copy()
    else:
        final_df = df.loc[~df[config.COL_IS_DELETED]].copy()

    today = datetime.now().strftime("%Y%m%d")
    fname = f"{today}_{project_name}_export.csv"
    out_path = config.EXPORT_DIR / fname
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False, encoding=config.CSV_ENCODING)

    # 規約上の固定パスにもコピー保存
    final_df.to_csv(config.EXPORT_CSV, index=False, encoding=config.CSV_ENCODING)

    logger.info(f"[INFO] 最終出力件数: {len(final_df):,}")
    logger.info(f"export 保存: {out_path}")
    logger.info(f"export 保存: {config.EXPORT_CSV}")
    return out_path


# ============================================================================
# CLI
# ============================================================================
def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="携帯電話番号 (070/080/090) のみを抽出するツール"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="入力 CSV パス（未指定なら input/ 配下の最新 .csv）",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="mobile_extract",
        help="出力ファイル命名に使うプロジェクト名（命名規則: yyyyMMdd_project_export.csv）",
    )
    parser.add_argument(
        "--keep-all-in-export",
        action="store_true",
        help="export にも論理削除行を残す（デバッグ用）。既定は携帯のみ出力。",
    )
    return parser.parse_args(argv)


def resolve_input_path(arg_path: Optional[Path]) -> Path:
    if arg_path is not None:
        if not arg_path.exists():
            raise FileNotFoundError(arg_path)
        return arg_path

    candidates = sorted(
        [p for p in config.INPUT_DIR.glob("*.csv") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"入力 CSV が見つかりません: {config.INPUT_DIR}/*.csv"
        )
    return candidates[0]


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)

    today = datetime.now().strftime("%Y%m%d")
    log_path = config.LOGS_DIR / f"{today}_{args.project}.log"
    logger = setup_logger(log_path)

    try:
        logger.info("=" * 60)
        logger.info(f"mobile_extractor start  project={args.project}")
        logger.info("=" * 60)

        input_path = resolve_input_path(args.input)

        df = load_and_save_raw(input_path, logger)
        df = clean_data(df, logger)
        df = filter_mobile_only(df, logger)
        export_final(df, logger, args.project, keep_all=args.keep_all_in_export)

        logger.info("mobile_extractor done.")
        return 0
    except Exception as e:
        logger.exception(f"処理失敗: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
