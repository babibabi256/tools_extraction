# prefecture_filter

指定された **都道府県** の行のみを CSV から抽出するツール。
指定外の都道府県、空欄、47都道府県マスタに存在しない値は **論理削除** する。

CLAUDE.md の規約（`raw -> cleaned -> filtered -> export`、論理削除、件数ログ、UTF-8 固定）に準拠。

---

## 構成

```
prefecture_filter/
├── main.py           # CLI エントリポイント / パイプライン
├── config.py         # パス・カラム名・47都道府県マスタ
├── README.md         # このファイル
├── input/            # 入力 CSV を置く
├── output/
│   ├── raw/raw.csv
│   ├── cleaned/cleaned.csv
│   ├── filtered/filtered.csv
│   └── export/
│       ├── final.csv                       # 規約固定パス
│       └── yyyyMMdd_<project>_export.csv   # 命名規則
├── logs/             # yyyyMMdd_<project>.log
└── temp/
```

---

## 使い方

### 入力 CSV

`都道府県` 列が必須。最低限のサンプル:

```csv
名称,TEL,都道府県,住所
山田商店,090-1234-5678,東京都,東京都新宿区...
鈴木電気,03-1111-2222,大阪府,大阪府大阪市...
ヤマダ,080-9999-8888,神奈川県,横浜市...
```

### 実行

```bash
cd tools/prefecture_filter

# 単一の都道府県を抽出
python main.py --input ./input/sample.csv --prefecture 東京都

# 複数都道府県を抽出
python main.py --input ./input/sample.csv --prefecture 東京都 大阪府 京都府

# input/ 配下の最新 CSV を自動採用
python main.py --prefecture 東京都

# プロジェクト名を変える（出力ファイル名に反映）
python main.py --prefecture 東京都 --project tokyo

# デバッグ用: export にも論理削除行を残す
python main.py --prefecture 東京都 --keep-all-in-export
```

### 出力カラム（追加分）

| カラム名 | 内容 |
|---|---|
| `pref_matched` | True なら指定都道府県に一致 |
| `is_deleted` | 論理削除フラグ |
| `delete_reason` | `pref_missing` / `invalid_prefecture` / `pref_unmatched` |

---

## 抽出ルール

`--prefecture 東京都 大阪府` を指定した場合の例:

| 入力 都道府県 例 | 結果 | delete_reason |
|---|---|---|
| `東京都` | 残す | - |
| `大阪府` | 残す | - |
| ` 東京都 ` (前後空白) | 残す（trim 判定） | - |
| `京都府` | 論理削除 | `pref_unmatched` |
| 空欄 | 論理削除 | `pref_missing` |
| `東京` (短縮表記) | 論理削除 | `invalid_prefecture` |
| `TOKYO` | 論理削除 | `invalid_prefecture` |

> 揺らぎ対応（「東京」「TOKYO」を「東京都」と同一視する）は本ツールでは行いません。
> 完全一致のみ。揺らぎを吸収したい場合は事前に正規化ツールを通してください。

---

## CLI 引数

| 引数 | 必須 | 内容 |
|---|---|---|
| `--prefecture` | ◎ | 抽出対象都道府県（複数指定可、半角スペース区切り） |
| `--input` | - | 入力 CSV パス。未指定なら `input/` 配下の最新 .csv |
| `--project` | - | 出力ファイル命名用（既定: `prefecture_filter`） |
| `--keep-all-in-export` | - | export にも論理削除行を残す（デバッグ用） |

47 都道府県マスタに無い値が `--prefecture` に指定された場合は警告ログを出して除外します。
全て無効な場合はエラーで停止します。

---

## ログ仕様

`logs/yyyyMMdd_<project>.log` と stdout に同時出力。

```
[INFO] 抽出対象都道府県: ['東京都', '大阪府']
[INFO] 入力件数: 1,000
[INFO] 欠損除去件数: 12（理由: pref_missing）
[INFO] 不正除去件数: 5（理由: invalid_prefecture）
[INFO] 不一致除去件数: 720（理由: pref_unmatched）
[INFO] 都道府県内訳(生存): {'東京都': 200, '大阪府': 63}
[INFO] フィルタ後件数: 263
[INFO] 最終出力件数: 263
```

---

## 中間ファイル

| ファイル | 内容 |
|---|---|
| `output/raw/raw.csv`           | 入力をそのまま保存（破壊しない原本） |
| `output/cleaned/cleaned.csv`   | `pref_matched` 列付与済み |
| `output/filtered/filtered.csv` | 論理削除を反映（全行残す。`is_deleted` で判定） |
| `output/export/final.csv`      | 指定都道府県のみ（`is_deleted=False` の行のみ） |
