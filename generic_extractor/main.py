"""設定JSONで条件を変えられる汎用CSV抽出ツール.

パイプライン:
    raw -> cleaned -> filtered -> export

抽出ロジックは `rules/*.json` に定義する。
Pythonコードを触らずに、TEL・都道府県・業種・HP有無などの抽出条件を追加できる。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

import config


def setup_logger(log_path: Path) -> logging.Logger:
    """コンソールとファイルへ同時出力するロガーを構築."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("generic_extractor")
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


def _coerce_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(("true", "1", "yes", "t"))


def ensure_internal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """内部管理カラムを追加し、真偽列を正規化する."""
    for col in config.INTERNAL_COLUMNS:
        if col not in df.columns:
            df[col] = False if col == config.COL_IS_DELETED else ""
    df[config.COL_IS_DELETED] = _coerce_bool(df[config.COL_IS_DELETED])
    return df


def stamp_process(df: pd.DataFrame, step: str, processed_by: str) -> pd.DataFrame:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df[config.COL_PROCESS_STEP] = step
    df[config.COL_PROCESSED_AT] = now
    df[config.COL_PROCESSED_BY] = processed_by
    df[config.COL_PIPELINE_VERSION] = config.PIPELINE_VERSION
    return df


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
        raise FileNotFoundError(f"入力 CSV が見つかりません: {config.INPUT_DIR}/*.csv")
    return candidates[0]


def resolve_rule_path(rule: str) -> Path:
    path = Path(rule)
    if path.exists():
        return path

    named = config.RULES_DIR / rule
    if named.exists():
        return named

    with_suffix = config.RULES_DIR / f"{rule}.json"
    if with_suffix.exists():
        return with_suffix

    raise FileNotFoundError(f"ルールJSONが見つかりません: {rule}")


def load_rule(rule_name_or_path: str) -> dict[str, Any]:
    rule_path = resolve_rule_path(rule_name_or_path)
    with rule_path.open(encoding="utf-8") as f:
        rule = json.load(f)
    rule["_rule_path"] = str(rule_path)
    return rule


def require_columns(df: pd.DataFrame, rule: dict[str, Any]) -> None:
    required = set(rule.get("required_columns", []))
    for derived in rule.get("derived_columns", []):
        source = derived.get("source")
        if source:
            required.add(source)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"必須カラムが入力CSVに存在しません: {missing}")


def apply_transforms(series: pd.Series, transforms: list[str]) -> pd.Series:
    """JSONで指定された変換を順に適用する."""
    result = series.astype(str)
    for transform in transforms:
        if transform == "strip":
            result = result.str.strip()
        elif transform == "nfkc":
            result = result.map(lambda value: unicodedata.normalize("NFKC", value))
        elif transform == "digits_only":
            result = result.str.replace(r"\D", "", regex=True)
        elif transform == "remove_spaces":
            result = result.str.replace(r"\s+", "", regex=True)
        elif transform == "lower":
            result = result.str.lower()
        elif transform == "upper":
            result = result.str.upper()
        else:
            raise ValueError(f"未対応のtransformです: {transform}")
    return result


def build_derived_columns(df: pd.DataFrame, rule: dict[str, Any]) -> pd.DataFrame:
    """ルールに従い判定用カラムを追加する."""
    df = df.copy()
    for derived in rule.get("derived_columns", []):
        name = derived["name"]
        source = derived["source"]
        transforms = derived.get("transforms", [])
        df[name] = apply_transforms(df[source], transforms)
    return df


def condition_mask(df: pd.DataFrame, condition: dict[str, Any]) -> pd.Series:
    """条件1つをbool Seriesに変換する."""
    column = condition["column"]
    if column not in df.columns:
        raise ValueError(f"条件カラムが存在しません: {column}")

    values = df[column].astype(str)
    op = condition.get("operator", "equals")
    expected = condition.get("value")

    if op == "is_empty":
        return values.str.strip() == ""
    if op == "not_empty":
        return values.str.strip() != ""
    if op == "equals":
        return values == str(expected)
    if op == "not_equals":
        return values != str(expected)
    if op == "in":
        return values.isin([str(v) for v in condition.get("values", [])])
    if op == "not_in":
        return ~values.isin([str(v) for v in condition.get("values", [])])
    if op == "prefix_in":
        prefixes = tuple(str(v) for v in condition.get("values", []))
        return values.str.startswith(prefixes)
    if op == "regex":
        return values.str.contains(str(expected), regex=True, na=False)
    if op == "not_regex":
        return ~values.str.contains(str(expected), regex=True, na=False)
    if op == "length_eq":
        return values.str.len() == int(expected)
    if op == "valid_prefecture":
        return values.isin(config.VALID_PREFECTURES)
    if op == "not_valid_prefecture":
        return ~values.isin(config.VALID_PREFECTURES)

    raise ValueError(f"未対応のoperatorです: {op}")


def combine_conditions(df: pd.DataFrame, conditions: list[dict[str, Any]]) -> pd.Series:
    """複数条件をANDで結合する。空なら全行True."""
    if not conditions:
        return pd.Series(True, index=df.index)

    mask = pd.Series(True, index=df.index)
    for condition in conditions:
        mask &= condition_mask(df, condition)
    return mask


def load_and_save_raw(
    input_path: Path, rule: dict[str, Any], logger: logging.Logger, processed_by: str
) -> pd.DataFrame:
    logger.info(f"入力ファイル: {input_path}")
    logger.info(f"使用ルール: {rule.get('name', '')} ({rule.get('_rule_path')})")
    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    logger.info(f"[INFO] 入力件数: {len(df):,}")

    require_columns(df, rule)
    df = ensure_internal_columns(df)
    df = stamp_process(df, step="raw", processed_by=processed_by)

    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"raw 保存: {config.RAW_CSV}")
    return df


def clean_data(
    df: pd.DataFrame, rule: dict[str, Any], logger: logging.Logger, processed_by: str
) -> pd.DataFrame:
    df = build_derived_columns(df, rule)

    for column in rule.get("flag_columns", []):
        name = column["name"]
        df[name] = combine_conditions(df, column.get("conditions", []))
        logger.info(f"[INFO] 付与カラム: {name}")

    df = stamp_process(df, step="cleaned", processed_by=processed_by)
    config.CLEANED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEANED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"cleaned 保存: {config.CLEANED_CSV}")
    return df


def apply_delete_rule(
    df: pd.DataFrame, delete_rule: dict[str, Any], logger: logging.Logger
) -> int:
    reason = delete_rule["reason"]
    mask = ~df[config.COL_IS_DELETED] & combine_conditions(
        df, delete_rule.get("conditions", [])
    )
    count = int(mask.sum())
    df.loc[mask, config.COL_IS_DELETED] = True
    df.loc[mask, config.COL_DELETE_REASON] = reason
    logger.info(f"[INFO] 除去件数: {count:,}（理由: {reason}）")
    return count


def filter_data(
    df: pd.DataFrame,
    rule: dict[str, Any],
    logger: logging.Logger,
    processed_by: str,
) -> pd.DataFrame:
    df = ensure_internal_columns(df.copy())
    removal_counts: dict[str, int] = {}

    for delete_rule in rule.get("delete_rules", []):
        count = apply_delete_rule(df, delete_rule, logger)
        removal_counts[delete_rule["reason"]] = count

    keep_rule = rule.get("keep_rule")
    if keep_rule:
        keep_mask = combine_conditions(df, keep_rule.get("conditions", []))
        unmatched_mask = ~df[config.COL_IS_DELETED] & ~keep_mask
        reason = keep_rule.get("unmatched_reason", "unmatched")
        count = int(unmatched_mask.sum())
        df.loc[unmatched_mask, config.COL_IS_DELETED] = True
        df.loc[unmatched_mask, config.COL_DELETE_REASON] = reason
        removal_counts[reason] = count
        logger.info(f"[INFO] 不一致除去件数: {count:,}（理由: {reason}）")

    for column in rule.get("breakdown_columns", []):
        if column in df.columns:
            breakdown = (
                df.loc[~df[config.COL_IS_DELETED], column].value_counts().to_dict()
            )
            logger.info(f"[INFO] {column} 内訳(生存): {breakdown}")

    missing_count = sum(
        count for reason, count in removal_counts.items() if "missing" in reason
    )
    duplicate_count = removal_counts.get("duplicate", 0)
    logger.info(f"[INFO] 欠損除去件数: {missing_count:,}")
    logger.info(f"[INFO] 重複除去件数: {duplicate_count:,}")

    n_remaining = int((~df[config.COL_IS_DELETED]).sum())
    logger.info(f"[INFO] フィルタ後件数: {n_remaining:,}")

    df = stamp_process(df, step="filtered", processed_by=processed_by)
    config.FILTERED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.FILTERED_CSV, index=False, encoding=config.CSV_ENCODING)
    logger.info(f"filtered 保存: {config.FILTERED_CSV}")
    return df


def export_final(
    df: pd.DataFrame,
    rule: dict[str, Any],
    logger: logging.Logger,
    project_name: str,
    keep_all: bool,
    processed_by: str,
) -> Path:
    df = stamp_process(df.copy(), step="export", processed_by=processed_by)
    final_df = df.copy() if keep_all else df.loc[~df[config.COL_IS_DELETED]].copy()

    export_columns = rule.get("export_columns", [])
    if export_columns:
        existing = [col for col in export_columns if col in final_df.columns]
        missing = [col for col in export_columns if col not in final_df.columns]
        if missing:
            logger.warning(f"export_columns のうち存在しないカラムを無視: {missing}")
        final_df = final_df[existing]

    today = datetime.now().strftime("%Y%m%d")
    out_path = config.EXPORT_DIR / f"{today}_{project_name}_export.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False, encoding=config.CSV_ENCODING)
    final_df.to_csv(config.EXPORT_CSV, index=False, encoding=config.CSV_ENCODING)

    logger.info(f"[INFO] 最終出力件数: {len(final_df):,}")
    logger.info(f"export 保存: {out_path}")
    logger.info(f"export 保存: {config.EXPORT_CSV}")
    return out_path


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="設定JSONで動く汎用CSV抽出ツール")
    parser.add_argument("--input", type=Path, default=None, help="入力CSVパス")
    parser.add_argument(
        "--rule",
        required=True,
        help="ルール名またはJSONパス。例: tel_mobile / rules/tel_mobile.json",
    )
    parser.add_argument("--project", default="generic_extract", help="出力ファイル名用")
    parser.add_argument(
        "--keep-all-in-export",
        action="store_true",
        help="exportにも論理削除行を残す",
    )
    parser.add_argument(
        "--processed-by",
        default=config.PROCESSED_BY_DEFAULT,
        help="processed_by に記録する実行者",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    today = datetime.now().strftime("%Y%m%d")
    log_path = config.LOGS_DIR / f"{today}_{args.project}.log"
    logger = setup_logger(log_path)

    try:
        logger.info("=" * 60)
        logger.info(f"generic_extractor start  project={args.project}")
        logger.info("=" * 60)

        rule = load_rule(args.rule)
        input_path = resolve_input_path(args.input)

        df = load_and_save_raw(input_path, rule, logger, args.processed_by)
        df = clean_data(df, rule, logger, args.processed_by)
        df = filter_data(df, rule, logger, args.processed_by)
        export_final(
            df,
            rule,
            logger,
            args.project,
            keep_all=args.keep_all_in_export,
            processed_by=args.processed_by,
        )

        logger.info("generic_extractor done.")
        return 0
    except Exception as exc:
        logger.exception(f"処理失敗: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
