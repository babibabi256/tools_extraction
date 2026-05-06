# generic_extractor

JSONルールで抽出条件を変えられる汎用CSV抽出ツールです。

既存の `mobile_extractor` や `prefecture_filter` のような単機能ツールを残しつつ、抽出内容を柔軟に変えたい場合はこちらを使います。

## 使い方

```bash
cd generic_extractor

# 携帯番号だけ抽出
python main.py --input ./input/sample.csv --rule tel_mobile --project mobile

# 都道府県抽出（rules/prefecture.json の values を変更して対象を変える）
python main.py --input ./input/sample.csv --rule prefecture --project pref

# HPありだけ抽出
python main.py --input ./input/sample.csv --rule hp_exists --project hp
```

`--input` を省略すると `input/` 配下の最新CSVを使います。

## ルール追加

`rules/_template.json` をコピーして `rules/任意名.json` を追加するだけで新しい抽出を作れます。

基本構造:

```json
{
  "name": "抽出名",
  "required_columns": ["TEL"],
  "derived_columns": [
    {
      "name": "tel_normalized",
      "source": "TEL",
      "transforms": ["nfkc", "digits_only"]
    }
  ],
  "flag_columns": [
    {
      "name": "mobile_flag",
      "conditions": [
        {"column": "tel_normalized", "operator": "regex", "value": "^(?:070|080|090)[0-9]{8}$"}
      ]
    }
  ],
  "delete_rules": [
    {
      "reason": "tel_missing",
      "conditions": [
        {"column": "TEL", "operator": "is_empty"}
      ]
    }
  ],
  "keep_rule": {
    "unmatched_reason": "not_mobile",
    "conditions": [
      {"column": "mobile_flag", "operator": "equals", "value": "True"}
    ]
  }
}
```

## 使える変換

| transform | 内容 |
|---|---|
| `strip` | 前後空白を削除 |
| `nfkc` | 全角英数字などを半角寄りに正規化 |
| `digits_only` | 数字以外を削除 |
| `remove_spaces` | 空白を削除 |
| `lower` | 小文字化 |
| `upper` | 大文字化 |

## 使える条件

| operator | 内容 |
|---|---|
| `is_empty` / `not_empty` | 空欄判定 |
| `equals` / `not_equals` | 完全一致 |
| `in` / `not_in` | 値リストに含まれるか |
| `prefix_in` | 指定プレフィクスで始まるか |
| `regex` / `not_regex` | 正規表現 |
| `length_eq` | 文字数一致 |
| `valid_prefecture` / `not_valid_prefecture` | 47都道府県に含まれるか |

## 出力

規約通り、各工程を保存します。

| ファイル | 内容 |
|---|---|
| `output/raw/raw.csv` | 入力をそのまま保存 |
| `output/cleaned/cleaned.csv` | 派生カラム・フラグ付与後 |
| `output/filtered/filtered.csv` | 論理削除反映後。全行残る |
| `output/export/final.csv` | 生存行のみ |
| `output/export/yyyyMMdd_project_export.csv` | 命名規則付きの最終出力 |
