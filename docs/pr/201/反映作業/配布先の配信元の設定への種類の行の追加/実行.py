"""配布先の配信元の設定へ、エージェント・MCP サーバー・LLM の呼び出し・精度評価の種類の行を追加する。

使い方: python -B 実行.py [対象のリポジトリ] [--dry-run]
"""

import difflib
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

CONFIG_NAMES = ("project-index.yaml", "dev-docs.yaml")
# 種類の行の ID・タイトル・パス・除外・knowledge のスキーマ・metadata
KINDS = [
    ("agent", "エージェントの定義", '"docs/agent/*.yaml"', "[index.yaml]", "agent", "lead"),
    (
        "mcp_server",
        "MCP サーバーの定義",
        '"docs/mcp-server/*.yaml"',
        "[index.yaml]",
        "mcp_server",
        "lead",
    ),
    ("launch", "起動の構成", '"docs/launch/*.yaml"', "[index.yaml]", "launch", "lead"),
    (
        "agent_flow",
        "エージェントフロー",
        '"docs/agent-flow/*.yaml"',
        "[index.yaml]",
        "agent_flow",
        "flow",
    ),
    ("llm_call", "LLM の呼び出し", '"docs/llm-call/*.yaml"', "[index.yaml]", "llm_call", "lead"),
    (
        "evaluation",
        "精度評価のスイート",
        '"docs/evaluation/**/*.yaml"',
        '[index.yaml, "**/criteria/*.yaml", "**/cases/*.yaml"]',
        "evaluation",
        "lead",
    ),
    (
        "eval_criterion",
        "精度評価の観点",
        '"docs/evaluation/**/criteria/*.yaml"',
        "[index.yaml]",
        "eval_criterion",
        "criterion",
    ),
    (
        "eval_case",
        "精度評価のケース",
        '"docs/evaluation/**/cases/*.yaml"',
        "[index.yaml]",
        "eval_case",
        "case",
    ),
]
METADATA = {
    "lead": [
        ("name", "title"),
        ("description", "lead"),
        ("visibility", "visibility"),
        ("tags", "tags[].name"),
        ("main_tags", "tags[main].name"),
        ("related", '"**.refs[]"'),
    ],
    "flow": [
        ("name", "title"),
        ("description", "summary"),
        ("visibility", "visibility"),
        ("tags", "tags"),
        ("related", '"**.refs[]"'),
    ],
    "criterion": [("name", "title"), ("visibility", "visibility"), ("tags", "tags")],
    "case": [("name", "summary"), ("visibility", "visibility"), ("tags", "tags")],
}


def fail(step, detail=""):
    print(f"{step}: failed")
    if detail:
        print(detail)
    sys.exit(1)


def parse_args(argv):
    args = list(argv)
    dry_run = False
    if args and args[-1] == "--dry-run":
        dry_run = True
        args = args[:-1]
    if len(args) > 1 or (args and args[0].startswith("--")):
        fail("前提確認", f"受け付けない引数: {argv}")
    root = Path(args[0]) if args else Path.cwd()
    return root.resolve(), dry_run


def knowledge_ref(documents):
    """既存の行が指す knowledge の design-schemas のタグを返す。"""
    for doc in documents:
        schema = doc.get("schema")
        if isinstance(schema, dict) and schema.get("source") == "knowledge":
            ref = str(schema.get("ref", ""))
            if ref.startswith("design-schemas/"):
                return ref
    return None


def base_row(documents):
    """新しい行へ写す validators・writable・after_write を、既存のインターフェース定義の行から返す。"""
    for doc in documents:
        if doc.get("id") == "interface":
            return {k: doc[k] for k in ("validators", "writable", "after_write") if k in doc}
    return {}


def flow(value):
    return "[" + ", ".join(str(v) for v in value) + "]"


def render_row(indent, kind, ref, base):
    kid, title, paths, exclude, schema, meta = kind
    pad = " " * indent
    lines = [
        f"{pad}- id: {kid}",
        f"{pad}  title: {title}",
        f"{pad}  paths: [{paths}]",
        f"{pad}  exclude: {exclude}",
        f"{pad}  schema:",
        f"{pad}    source: knowledge",
        f"{pad}    path: schemas/design/{schema}.schema.yaml",
        f"{pad}    ref: {ref}",
    ]
    for key in ("validators", "after_write"):
        if key in base:
            lines.append(f"{pad}  {key}: {flow(base[key])}")
    if "writable" in base:
        lines.append(f"{pad}  writable: {'true' if base['writable'] else 'false'}")
    lines.append(f"{pad}  metadata:")
    lines += [f"{pad}    {k}: {v}" for k, v in METADATA[meta]]
    return lines


def documents_end(lines):
    """documents: の並びの最後の行の次の位置と、並びの要素の字下げを返す。"""
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "documents:"), None)
    if start is None:
        return None, None
    indent = None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and not line.startswith("-"):
            end = i
            break
        if indent is None and line.lstrip().startswith("- "):
            indent = len(line) - len(line.lstrip())
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    return end, indent


def main():
    root, dry_run = parse_args(sys.argv[1:])
    if not (root / ".git").exists():
        fail("前提確認", f"リポジトリではない: {root}")
    config = next((root / n for n in CONFIG_NAMES if (root / n).is_file()), None)
    if config is None:
        fail("前提確認", f"配信元の設定が無い: {root}")
    text = config.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    documents = data.get("documents") or []
    ref = knowledge_ref(documents)
    if ref is None:
        fail("前提確認", "knowledge の design-schemas を指す行が無い")
    lines = text.split("\n")
    end, indent = documents_end(lines)
    if end is None or indent is None:
        fail("前提確認", "documents: の並びが無い")
    print("前提確認: ok")

    # 計画（--dry-run もここを通る）
    existing = {doc.get("id"): doc for doc in documents}
    base = base_row(documents)
    copied = []
    new_lines = []
    for kind in KINDS:
        kid = kind[0]
        doc = existing.get(kid)
        if doc is None:
            new_lines += render_row(indent, kind, ref, base)
            continue
        schema = doc.get("schema")
        if isinstance(schema, str):
            copied.append((kid, schema))
    # 複製したスキーマを指す既存の行は書き換えず、確認で failed になるので実行者が knowledge の参照へ置き換える
    for kid, schema in copied:
        print(f"複製したスキーマの行（{kid}: {schema}）: missing")
    if not new_lines:
        print("種類の行の追加: skipped")
        return
    new_text = "\n".join(lines[:end] + new_lines + lines[end:])
    rel = config.name
    sys.stdout.writelines(
        difflib.unified_diff(text.splitlines(True), new_text.splitlines(True), rel, rel)
    )
    if dry_run:
        print("種類の行の追加: changed")
        return

    # 適用（検証 → 退避 → 置き換え）
    parsed = yaml.safe_load(new_text) or {}
    ids = {doc.get("id") for doc in parsed.get("documents") or []}
    if not all(kind[0] in ids for kind in KINDS):
        fail("検証", "追加した行が YAML として読めない")
    print("検証: ok")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=root) as tmp:
        tmp.write(new_text)
    shutil.copy2(config, config.with_name(config.name + ".bak"))
    Path(tmp.name).replace(config)
    print("種類の行の追加: changed")


if __name__ == "__main__":
    main()
