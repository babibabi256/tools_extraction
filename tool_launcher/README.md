# Tool Launcher

ローカルページから `tools/` 配下のCLIツールを選んで実行するための軽量ランチャーです。

## 起動

```bash
cd tools/tool_launcher
python server.py
```

ブラウザで `http://127.0.0.1:8765` を開きます。

## ツール追加

画面右上の「ツールを追加」から登録できます。登録内容は `tools.json` に保存されます。

よく使う形:

```json
{
  "id": "csv_cleaner",
  "name": "CSVクリーナー",
  "description": "CSVを整形します。",
  "cwd": "../csv_cleaner",
  "command": ["{python}", "main.py"],
  "fields": [
    {"name": "input", "label": "入力CSVパス", "type": "text"},
    {"name": "project", "label": "プロジェクト名", "type": "text"}
  ],
  "args": [
    {"flag": "--input", "field": "input", "skip_empty": true},
    {"flag": "--project", "field": "project", "skip_empty": true}
  ]
}
```

`"{python}"` はランチャーを起動しているPythonに置き換えられます。

## 登録済み

- 携帯番号抽出
- 名寄せ
- 個人ダミーデータ生成
