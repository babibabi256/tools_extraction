from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
TOOLS_FILE = BASE_DIR / "tools.json"
HOST = "127.0.0.1"
PORT = 8765

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def load_tools() -> list[dict[str, Any]]:
    if not TOOLS_FILE.exists():
        return []
    return json.loads(TOOLS_FILE.read_text(encoding="utf-8"))


def save_tools(tools: list[dict[str, Any]]) -> None:
    TOOLS_FILE.write_text(
        json.dumps(tools, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_tool(tool_id: str) -> dict[str, Any] | None:
    return next((tool for tool in load_tools() if tool.get("id") == tool_id), None)


def resolve_command(command: list[str]) -> list[str]:
    return [sys.executable if part == "{python}" else str(part) for part in command]


def build_args(tool: dict[str, Any], values: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for spec in tool.get("args", []):
        field = spec.get("field")
        value = values.get(field)
        if spec.get("type") == "flag":
            if value is True or str(value).lower() in {"true", "1", "yes", "on"}:
                args.append(str(spec["flag"]))
            continue
        if spec.get("skip_empty") and (value is None or str(value).strip() == ""):
            continue
        if "flag" in spec:
            args.append(str(spec["flag"]))
        args.append(str(value if value is not None else ""))
    return args


def run_job(job_id: str, tool: dict[str, Any], values: dict[str, Any]) -> None:
    command = resolve_command(tool.get("command", [])) + build_args(tool, values)
    cwd = (BASE_DIR / tool.get("cwd", ".")).resolve()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with JOBS_LOCK:
        JOBS[job_id].update(
            {
                "status": "running",
                "started_at": started_at,
                "command": command,
                "cwd": str(cwd),
                "output": "",
            }
        )

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            with JOBS_LOCK:
                JOBS[job_id]["output"] += line
        return_code = process.wait()
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with JOBS_LOCK:
            JOBS[job_id].update(
                {
                    "status": "success" if return_code == 0 else "failed",
                    "return_code": return_code,
                    "finished_at": finished_at,
                }
            )
    except Exception as exc:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with JOBS_LOCK:
            JOBS[job_id].update(
                {
                    "status": "failed",
                    "return_code": 1,
                    "finished_at": finished_at,
                    "output": JOBS[job_id].get("output", "") + f"\n{exc}\n",
                }
            )


def json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw)


class ToolLauncherHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/tools":
            json_response(self, {"tools": load_tools()})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            json_response(self, {"job": job}, 200 if job else 404)
            return
        json_response(self, {"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = read_json(self)
        except json.JSONDecodeError:
            json_response(self, {"error": "invalid json"}, 400)
            return

        if path == "/api/tools":
            tool = payload.get("tool", {})
            if not tool.get("id") or not tool.get("name") or not tool.get("command"):
                json_response(self, {"error": "id, name, command are required"}, 400)
                return
            tools = [t for t in load_tools() if t.get("id") != tool["id"]]
            tools.append(tool)
            save_tools(tools)
            json_response(self, {"tool": tool}, 201)
            return

        if path == "/api/run":
            tool_id = payload.get("tool_id")
            tool = find_tool(tool_id)
            if tool is None:
                json_response(self, {"error": "tool not found"}, 404)
                return
            job_id = uuid.uuid4().hex
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "id": job_id,
                    "tool_id": tool_id,
                    "tool_name": tool.get("name", tool_id),
                    "status": "queued",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            thread = threading.Thread(
                target=run_job,
                args=(job_id, tool, payload.get("values", {})),
                daemon=True,
            )
            thread.start()
            json_response(self, {"job_id": job_id}, 202)
            return

        json_response(self, {"error": "not found"}, 404)


INDEX_HTML = r"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tool Launcher</title>
  <style>
    :root {
      --bg: #f7f4ef;
      --ink: #202124;
      --muted: #68635d;
      --line: #ddd6cb;
      --panel: #fffdf8;
      --accent: #146c67;
      --accent-dark: #0d4e4a;
      --danger: #a33d2d;
      --shadow: 0 14px 38px rgba(39, 33, 24, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 28px auto;
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 18px;
    }
    header {
      grid-column: 1 / -1;
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 28px; letter-spacing: 0; }
    .subtitle { margin: 6px 0 0; color: var(--muted); }
    button {
      border: 0;
      border-radius: 7px;
      background: var(--accent);
      color: white;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button.secondary {
      background: transparent;
      color: var(--accent);
      border: 1px solid var(--line);
    }
    aside, section, dialog {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    aside { padding: 12px; height: fit-content; }
    section { padding: 18px; min-width: 0; }
    .tool-list {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .tool-item {
      width: 100%;
      text-align: left;
      background: transparent;
      color: var(--ink);
      border: 1px solid transparent;
      padding: 12px;
    }
    .tool-item.active {
      border-color: var(--accent);
      background: #e9f3f1;
    }
    .tool-item strong { display: block; margin-bottom: 4px; }
    .tool-item span { color: var(--muted); font-size: 13px; }
    .title-row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: start;
      border-bottom: 1px solid var(--line);
      padding-bottom: 14px;
      margin-bottom: 16px;
    }
    h2 { margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }
    form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px 11px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    textarea { min-height: 120px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .checkbox {
      align-self: end;
      display: flex;
      min-height: 42px;
      align-items: center;
      gap: 9px;
      color: var(--ink);
    }
    .checkbox input { width: 18px; height: 18px; }
    .help { color: var(--muted); font-size: 12px; }
    .actions {
      grid-column: 1 / -1;
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 4px;
    }
    pre {
      margin: 16px 0 0;
      min-height: 260px;
      max-height: 46vh;
      overflow: auto;
      padding: 14px;
      border-radius: 8px;
      background: #1f2525;
      color: #eef7f3;
      white-space: pre-wrap;
      font-size: 13px;
      line-height: 1.5;
    }
    .status { color: var(--muted); font-size: 13px; }
    dialog {
      width: min(760px, calc(100vw - 32px));
      padding: 18px;
    }
    dialog::backdrop { background: rgba(32, 33, 36, 0.38); }
    .modal-grid { display: grid; gap: 12px; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
    @media (max-width: 760px) {
      main { grid-template-columns: 1fr; }
      header { align-items: start; flex-direction: column; }
      form { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Tool Launcher</h1>
      <p class="subtitle">登録したツールを選んで、必要な値だけ入れて実行します。</p>
    </div>
    <button id="openAdd">ツールを追加</button>
  </header>

  <aside>
    <strong>ツール</strong>
    <div id="toolList" class="tool-list"></div>
  </aside>

  <section>
    <div id="empty">左からツールを選択してください。</div>
    <div id="toolPanel" hidden>
      <div class="title-row">
        <div>
          <h2 id="toolName"></h2>
          <div id="toolDescription" class="status"></div>
        </div>
        <div id="toolCwd" class="status"></div>
      </div>
      <form id="runForm"></form>
      <pre id="output">実行ログがここに表示されます。</pre>
    </div>
  </section>
</main>

<dialog id="addDialog">
  <h2>ツールを追加</h2>
  <div class="modal-grid">
    <label>ID<input id="addId" placeholder="csv_cleaner"></label>
    <label>表示名<input id="addName" placeholder="CSVクリーナー"></label>
    <label>説明<input id="addDescription" placeholder="CSVを整形します"></label>
    <label>作業ディレクトリ<input id="addCwd" placeholder="../csv_cleaner"></label>
    <label>コマンド(JSON配列)<textarea id="addCommand">["{python}", "main.py"]</textarea></label>
    <label>入力項目(JSON配列)<textarea id="addFields">[
  {"name": "input", "label": "入力CSVパス", "type": "text"},
  {"name": "project", "label": "プロジェクト名", "type": "text"}
]</textarea></label>
    <label>引数(JSON配列)<textarea id="addArgs">[
  {"flag": "--input", "field": "input", "skip_empty": true},
  {"flag": "--project", "field": "project", "skip_empty": true}
]</textarea></label>
  </div>
  <div class="modal-actions">
    <button class="secondary" id="cancelAdd">閉じる</button>
    <button id="saveAdd">保存</button>
  </div>
</dialog>

<script>
let tools = [];
let selected = null;
let pollTimer = null;

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "request failed");
  return data;
}

async function loadTools() {
  const data = await api("/api/tools");
  tools = data.tools;
  renderList();
  if (!selected && tools.length) selectTool(tools[0].id);
}

function renderList() {
  el("toolList").innerHTML = "";
  tools.forEach((tool) => {
    const button = document.createElement("button");
    button.className = "tool-item" + (selected?.id === tool.id ? " active" : "");
    button.innerHTML = `<strong>${escapeHtml(tool.name)}</strong><span>${escapeHtml(tool.description || "")}</span>`;
    button.onclick = () => selectTool(tool.id);
    el("toolList").appendChild(button);
  });
}

function selectTool(id) {
  selected = tools.find((tool) => tool.id === id);
  renderList();
  el("empty").hidden = true;
  el("toolPanel").hidden = false;
  el("toolName").textContent = selected.name;
  el("toolDescription").textContent = selected.description || "";
  el("toolCwd").textContent = selected.cwd || ".";
  renderForm();
  el("output").textContent = "実行ログがここに表示されます。";
}

function renderForm() {
  const form = el("runForm");
  form.innerHTML = "";
  (selected.fields || []).forEach((field) => {
    if (field.type === "checkbox") {
      const label = document.createElement("label");
      label.className = "checkbox";
      label.innerHTML = `<input name="${field.name}" type="checkbox" ${field.default ? "checked" : ""}> ${escapeHtml(field.label)}`;
      form.appendChild(label);
      return;
    }
    const label = document.createElement("label");
    label.textContent = field.label;
    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      (field.options || []).forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        if (option.value === field.default) opt.selected = true;
        input.appendChild(opt);
      });
    } else {
      input = document.createElement("input");
      input.type = field.type || "text";
      if (field.placeholder) input.placeholder = field.placeholder;
      if (field.min !== undefined) input.min = field.min;
      if (field.max !== undefined) input.max = field.max;
      if (field.step !== undefined) input.step = field.step;
      if (field.default !== undefined) input.value = field.default;
    }
    input.name = field.name;
    label.appendChild(input);
    if (field.help) {
      const help = document.createElement("span");
      help.className = "help";
      help.textContent = field.help;
      label.appendChild(help);
    }
    form.appendChild(label);
  });
  const actions = document.createElement("div");
  actions.className = "actions";
  actions.innerHTML = `<button type="submit">実行</button><span id="runStatus" class="status"></span>`;
  form.appendChild(actions);
}

el("runForm").onsubmit = async (event) => {
  event.preventDefault();
  if (!selected) return;
  const values = {};
  new FormData(el("runForm")).forEach((value, key) => values[key] = value);
  (selected.fields || []).filter((f) => f.type === "checkbox").forEach((f) => {
    values[f.name] = el("runForm").elements[f.name].checked;
  });
  el("output").textContent = "実行開始...";
  el("runStatus").textContent = "running";
  const data = await api("/api/run", {
    method: "POST",
    body: JSON.stringify({tool_id: selected.id, values})
  });
  pollJob(data.job_id);
};

async function pollJob(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const data = await api(`/api/jobs/${jobId}`);
    const job = data.job;
    if (!job) return;
    el("runStatus").textContent = job.status;
    el("output").textContent = [
      `$ ${job.command ? job.command.join(" ") : ""}`,
      `cwd: ${job.cwd || ""}`,
      "",
      job.output || ""
    ].join("\n");
    if (["success", "failed"].includes(job.status)) {
      clearInterval(pollTimer);
      el("runStatus").textContent = `${job.status} (${job.return_code})`;
    }
  }, 700);
}

el("openAdd").onclick = () => el("addDialog").showModal();
el("cancelAdd").onclick = (event) => {
  event.preventDefault();
  el("addDialog").close();
};
el("saveAdd").onclick = async (event) => {
  event.preventDefault();
  const tool = {
    id: el("addId").value.trim(),
    name: el("addName").value.trim(),
    description: el("addDescription").value.trim(),
    cwd: el("addCwd").value.trim() || ".",
    command: JSON.parse(el("addCommand").value),
    fields: JSON.parse(el("addFields").value),
    args: JSON.parse(el("addArgs").value)
  };
  await api("/api/tools", {method: "POST", body: JSON.stringify({tool})});
  el("addDialog").close();
  selected = null;
  await loadTools();
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
}

loadTools().catch((error) => {
  el("toolList").textContent = error.message;
});
</script>
</body>
</html>
"""


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), ToolLauncherHandler)
    print(f"Tool Launcher: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
