# mobile_extractor

携帯電話番号（**070 / 080 / 090**）だけを抽出するツール。
050（IP電話）、03/06 等の固定電話、0120/0800（フリーダイヤル）、0570（ナビダイヤル）などは対象外として **論理削除** する。

CLAUDE.md の規約（`raw -> cleaned -> filtered -> export`、論理削除、件数ログ、UTF-8 固定）に準拠。

---

## 構成

```
mobile_extractor/
├── main.py           # CLI エントリポイント / パイプライン
├── normalize.py      # 電話番号 正規化 / 種別判定
├── config.py         # パス・カラム名・定数
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

`TEL` 列が必須。最低限のサンプル:

```csv
名称,TEL
山田商店,090-1234-5678
鈴木電気,03-1111-2222
ヤマダ,０８０ー９９９９ー８８８８
```

### 実行

```bash
cd tools/mobile_extractor
python main.py --input ./input/sample.csv

# input/ 配下の最新 CSV を自動採用
python main.py

# プロジェクト名を変える（出力ファイル名に反映）
python main.py --project tokyo

# デバッグ用: export にも論理削除行を残す
python main.py --keep-all-in-export
```

### 出力カラム（追加分）

| カラム名 | 内容 |
|---|---|
| `tel_normalized` | 正規化後の TEL（数字のみ） |
| `mobile_flag` | True なら携帯（070/080/090, 11桁） |
| `tel_type` | `mobile` / `ip_phone` / `free_dial` / `navi_dial` / `m2m` / `landline_or_other` / `invalid` |
| `is_deleted` | 論理削除フラグ |
| `delete_reason` | `tel_missing` / `tel_invalid` / `not_mobile` |

---

## 抽出ルール

| 入力 TEL 例 | tel_type | 結果 |
|---|---|---|
| `090-1234-5678` | mobile | 残す |
| `080 9999 8888` | mobile | 残す |
| `070-0000-0000` | mobile | 残す |
| `050-1234-5678` | ip_phone | 論理削除（not_mobile） |
| `03-1234-5678`  | landline_or_other | 論理削除（not_mobile） |
| `0120-444-555`  | free_dial | 論理削除（not_mobile） |
| `0570-000-000`  | navi_dial | 論理削除（not_mobile） |
| `090-1` (桁数不足) | invalid | 論理削除（tel_invalid） |
| 空欄 | invalid | 論理削除（tel_missing） |

---

## 正規化ルール（CLAUDE.md「電話番号正規化」準拠）

- 全角数字 → 半角数字（NFKC）
- ハイフン / 空白 / 括弧 等の記号を除去
- 数字以外を一括除去 → `tel_normalized` 列に格納

例: `０９０ー１２３４ー５６７８` → `09012345678`

---

## ログ仕様

`logs/yyyyMMdd_<project>.log` と stdout に同時出力。

```
[INFO] 入力件数: 1,000
[INFO] 欠損除去件数: 12（理由: tel_missing）
[INFO] 不正除去件数: 3（理由: tel_invalid）
[INFO] 非携帯除去件数: 605（理由: not_mobile）
[INFO] tel_type 内訳: {'mobile': 380, 'landline_or_other': 500, 'ip_phone': 100, ...}
[INFO] フィルタ後件数: 380
[INFO] 最終出力件数: 380
```

---

## 中間ファイル

| ファイル | 内容 |
|---|---|
| `output/raw/raw.csv`           | 入力をそのまま保存（破壊しない原本） |
| `output/cleaned/cleaned.csv`   | TEL 正規化と tel_type / mobile_flag 付与済み |
| `output/filtered/filtered.csv` | 論理削除を反映（全行残す。is_deleted で判定） |
| `output/export/final.csv`      | 携帯のみ（is_deleted=False の行のみ） |
