"""都道府県フィルタツール.

CLAUDE.md / mobile_extractor の構造に準拠。

仕様:
    - `--prefecture` で指定された都道府県の行のみを残す（複数指定可）。
    - 指定外の都道府県、空欄、47都道府県マスタに無い値は論理削除する。
    - 元データは破壊せず、論理削除フラグ (is_deleted / delete_reason) で管理。
    - 都道府県カラムの揺らぎ（「東京」「TOKYO」等）は対象外（完全一致のみ）。

パイプライン:
    raw -> cleaned -> filtered -> export
    各工程で CSV を保存し、件数ログを出力する。

使い方:
    python main.py --input ./input/sample.csv --prefecture 東京都
    python main.py --input ./input/sample.csv --prefecture 東京都 大阪府 京都府
    python main.py --prefecture 東京都  # input/ 配下の最新 CSV を自動採用
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

import config


# ============================================================================
# ログ
# ============================================================================
def setup_logger(log_path: Path) -> logging.Logger:
    """コンソールとファイルへ同時出力するロガーを構築."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("prefecture_filter")
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
    """内部管理カラム / 都道府県判定カラムが無ければ追加。
    既にある場合も真偽列は bool に正規化する。"""
    for col in config.INTERNAL_COLUMNS:
        if col not in df.columns:
            if col == config.COL_IS_DELETED:
                df[col] = False
            else:
                df[col] = ""
    for col in config.PREF_COLUMNS:
        if col not in df.columns:
            if col == config.COL_PREF_MATCHED:
                df[col] = False
            else:
                df[col] = ""

    df[config.COL_IS_DELETED] = _coerce_bool(df[config.COL_IS_DELETED])
    df[config.COL_PREF_MATCHED] = _coerce_bool(df[config.COL_PREF_MATCHED])
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

    if config.COL_PREF not in df.columns:
        raise ValueError(
            f"必須カラム '{config.COL_PREF}' が入力CSVに存在しません: "
            f"columns={list(df.columns)}"
        )

    df = ensure_internal_columns(df)
    df = stamp_process(df, step="raw")

    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"raw 保存: {config.RAW_CSV}")
    return df


# ============================================================================
# 2) cleaned: 都道府県カラムをトリムして pref_matched を付与
# ============================================================================
def clean_data(
    df: pd.DataFrame,
    target_prefectures: List[str],
    logger: logging.Logger,
) -> pd.DataFrame:
    """都道府県カラムをトリムし、指定都道府県と一致するかフラグを立てる.

    元の 都道府県 カラムは破壊しない（trim 済み値は内部判定にのみ使用）。
    """
    df = df.copy()

    pref_trimmed = df[config.COL_PREF].astype(str).str.strip()
    target_set = set(target_prefectures)
    df[config.COL_PREF_MATCHED] = pref_trimmed.isin(target_set)

    df = stamp_process(df, step="cleaned")

    config.CLEANED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEANED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"cleaned 保存: {config.CLEANED_CSV}")
    return df


# ============================================================================
# 3) filtered: 指定都道府県以外を論理削除
# ============================================================================
def filter_by_prefecture(
    df: pd.DataFrame, logger: logging.Logger
) -> pd.DataFrame:
    """指定都道府県以外を論理削除する。物理削除はしない."""
    df = df.copy()
    df = ensure_internal_columns(df)

    pref_trimmed = df[config.COL_PREF].astype(str).str.strip()

    # --- 欠損: 都道府県 列が空文字 ----------------------------------------
    missing_mask = ~df[config.COL_IS_DELETED] & (pref_trimmed == "")
    n_missing = int(missing_mask.sum())
    df.loc[missing_mask, config.COL_IS_DELETED] = True
    df.loc[missing_mask, config.COL_DELETE_REASON] = config.REASON_PREF_MISSING
    logger.info(
        f"[INFO] 欠損除去件数: {n_missing:,}（理由: {config.REASON_PREF_MISSING}）"
    )

    # --- 不正: 47 都道府県マスタに無い値 -----------------------------------
    invalid_mask = (
        ~df[config.COL_IS_DELETED]
        & ~pref_trimmed.isin(config.VALID_PREFECTURES)
    )
    n_invalid = int(invalid_mask.sum())
    df.loc[invalid_mask, config.COL_IS_DELETED] = True
    df.loc[invalid_mask, config.COL_DELETE_REASON] = config.REASON_INVALID_PREFECTURE
    logger.info(
        f"[INFO] 不正除去件数: {n_invalid:,}"
        f"（理由: {config.REASON_INVALID_PREFECTURE}）"
    )

    # --- 指定都道府県と不一致 ----------------------------------------------
    unmatched_mask = ~df[config.COL_IS_DELETED] & ~df[config.COL_PREF_MATCHED]
    n_unmatched = int(unmatched_mask.sum())
    df.loc[unmatched_mask, config.COL_IS_DELETED] = True
    df.loc[unmatched_mask, config.COL_DELETE_REASON] = config.REASON_PREF_UNMATCHED
    logger.info(
        f"[INFO] 不一致除去件数: {n_unmatched:,}"
        f"（理由: {config.REASON_PREF_UNMATCHED}）"
    )

    # --- 都道府県ごとの内訳ログ（生存行のみ） -----------------------------
    alive = df.loc[~df[config.COL_IS_DELETED], config.COL_PREF]
    breakdown = alive.astype(str).str.strip().value_counts().to_dict()
    logger.info(f"[INFO] 都道府県内訳(生存): {breakdown}")

    n_remaining = int((~df[config.COL_IS_DELETED]).sum())
    logger.info(f"[INFO] フィルタ後件数: {n_remaining:,}")

    df = stamp_process(df, step="filtered")

    config.FILTERED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.FILTERED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"filtered 保存: {config.FILTERED_CSV}")
    return df


# ============================================================================
# 4) export: 指定都道府県のみ最終 CSV へ
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
        description="指定都道府県の行のみを抽出するツール"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="入力 CSV パス（未指定なら input/ 配下の最新 .csv）",
    )
    parser.add_argument(
        "--prefecture",
        type=str,
        nargs="+",
        required=True,
        help="抽出対象の都道府県（複数指定可）。例: --prefecture 東京都 大阪府",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="prefecture_filter",
        help="出力ファイル命名に使うプロジェクト名（命名規則: yyyyMMdd_project_export.csv）",
    )
    parser.add_argument(
        "--keep-all-in-export",
        action="store_true",
        help="export にも論理削除行を残す（デバッグ用）。既定は対象都道府県のみ出力。",
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


def validate_prefectures(
    prefectures: List[str], logger: logging.Logger
) -> List[str]:
    """指定都道府県が 47 都道府県マスタに存在するか検証.

    存在しないものは警告ログを出して除外する。全て無効なら ValueError。
    """
    valid = []
    invalid = []
    for p in prefectures:
        p_stripped = p.strip()
        if p_stripped in config.VALID_PREFECTURES:
            valid.append(p_stripped)
        else:
            invalid.append(p_stripped)

    if invalid:
        logger.warning(
            f"指定都道府県のうち無効なもの（除外）: {invalid}"
        )
    if not valid:
        raise ValueError(
            f"有効な都道府県が指定されていません: {prefectures}"
        )

    logger.info(f"抽出対象都道府県: {valid}")
    return valid


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)

    today = datetime.now().strftime("%Y%m%d")
    log_path = config.LOGS_DIR / f"{today}_{args.project}.log"
    logger = setup_logger(log_path)

    try:
        logger.info("=" * 60)
        logger.info(f"prefecture_filter start  project={args.project}")
        logger.info("=" * 60)

        target_prefectures = validate_prefectures(args.prefecture, logger)
        input_path = resolve_input_path(args.input)

        df = load_and_save_raw(input_path, logger)
        df = clean_data(df, target_prefectures, logger)
        df = filter_by_prefecture(df, logger)
        export_final(df, logger, args.project, keep_all=args.keep_all_in_export)

        logger.info("prefecture_filter done.")
        return 0
    except Exception as e:
        logger.exception(f"処理失敗: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
