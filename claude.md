# CLAUDE.md

# データ加工・スクレイピング作業標準

## 目的
公開情報を取得・整理・加工し、再利用しやすいCSVデータを生成する。

主な用途：
- 公共施設一覧整理
- 企業情報整理
- 電話番号正規化
- 都道府県別抽出
- 重複除去
- データクリーニング
- CSV統合
- データ加工パイプライン構築

---

# 基本原則

## 元データを破壊しない
raw データは変更禁止。

必ず以下の流れで処理する：

raw -> cleaned -> filtered -> export

---

## 加工履歴を必ず残す
すべての処理で以下を記録：

- 入力件数
- 除去件数
- 除去理由
- 最終件数
- 実行日時
- 使用スクリプト

---

## 削除は論理削除を優先

可能な限り物理削除しない。

使用カラム：

- is_deleted
- delete_reason

## tools ディレクトリ方針

tools/ 配下に用途ごとのツールを作成する。

例：

project/
├── tools/
│   ├── csv_cleaner/
│   ├── tel_normalizer/
│   ├── duplicate_checker/
│   ├── merger/
│   ├── scraper/
│   ├── geocoder/
│   ├── meiyose/
│   ├── hp_checker/

---

# ツール共通ルール

すべてのツールは以下を守る：

- 単機能で作る
- 再利用可能にする
- 入出力を明確にする
- CSVベースで扱う
- logging対応
- UTF-8固定
- pandas中心で実装
- CLI実行可能にする

---

# tools 共通構成

各ツールは以下構成を基本とする：

tool_name/
├── main.py
├── config.py
├── README.md
├── input/
├── output/
├── logs/
├── temp/

---

# 使用技術

## 基本
- Python
- pandas
- requests
- BeautifulSoup

## 必要時のみ
- Playwright
- Selenium

---

# スクレイピングルール

## 必須
- robots.txt を確認
- 過剰アクセス禁止
- rate limit を設定
- User-Agent を明示
- エラー時はリトライ制御

## 禁止
- ログイン突破
- CAPTCHA回避
- 不正アクセス
- 利用規約違反行為
- 個人情報の違法取得

---

# CSV標準仕様

## 必須基本カラム

| カラム名 | 内容 |
|---|---|
| 名称　| 名称 |
| TEL | 電話番号 |
| 都道府県 | 都道府県 |
| 住所 | 住所 |
| 代表者名 | 代表者 |
| 大業種 | 分類 |
| 中業種 | 分類 |
| 小業種 | 分類 |
| 細業種 | 分類 |
| HP | ホームページURL |

---

# 内部管理カラム

| カラム名 | 内容 |
|---|---|
| is_deleted | 論理削除フラグ |
| delete_reason | 削除理由 |
| process_step | 処理工程 |
| processed_at | 加工日時 |
| processed_by | 実行者 |
| pipeline_version | パイプラインバージョン |

---

# 追加カラム方針

基本カラムは固定。

案件ごとの追加カラムは後ろに append する。

例：
- mobile_flag
- industry
- score
- memo

---

# データ加工ルール

## 電話番号正規化
- ハイフン統一
- 全角を半角へ変換
- 空白除去

---

## 携帯番号抽出

対象：
- 070
- 080
- 090

固定電話は除外可能にする。

使用カラム：
- mobile_flag

---

# 重複除去ルール

以下一致で重複判定：

- name
- tel

削除理由：
duplicate

---

# 欠損値処理

欠損時は delete_reason に記録：

- tel_missing
- address_missing
- invalid_prefecture

---

# ログ出力標準

すべての処理で以下を表示：

[INFO] 入力件数: XXXX
[INFO] 欠損除去件数: XXXX
[INFO] 重複除去件数: XXXX
[INFO] フィルタ後件数: XXXX
[INFO] 最終出力件数: XXXX

---

# 中間ファイル保存ルール

各工程でCSV保存：

- raw/raw.csv
- cleaned/cleaned.csv
- filtered/filtered.csv
- export/final.csv

---

# pandas実装ルール

## 必須
- pandas中心で実装
- UTF-8で保存
- 関数分割を行う
- logging を使用
- try-except を実装

---

# 推奨実装フロー

1. raw保存
2. CSV構造確認
3. 欠損確認
4. 正規化
5. 重複除去
6. フィルタ
7. export生成
8. ログ保存

---

# AI実装ルール

Claude Code は以下を必ず守る：

- 件数ログを出力
- 削除理由を記録
- 各工程CSVを保存
- コメント付きで実装
- 関数分割を行う
- 再利用可能なコードにする
- 設定値は定数化する

---

# 過去案件管理

past-projects/ に案件ごとの md を保存する。

記録内容：
- 使用元データ
- 処理内容
- 使用スクリプト
- 出力結果
- 問題点
- 次回改善点

---

# テンプレート方針

templates/ に以下を保存：

- scraping_template.py
- csv_cleaner.py
- duplicate_remover.py
- tel_normalizer.py
- prefecture_filter.py

---

# 命名規則

## CSV
yyyyMMdd_projectname_step.csv

例：
20260503_tokyo_cleaned.csv

---

# ログ保存

logs/ に保存：

yyyyMMdd_project.log

---

# 最終目標

- 同じ処理を再利用可能にする
- AIに毎回説明しなくて済む構造にする
- 加工履歴を追跡可能にする
- 大規模CSVでも安全に処理可能にする
- 誰が見ても再現可能な構造にする