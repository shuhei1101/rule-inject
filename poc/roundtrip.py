"""PoC: ruamel.yaml の round-trip で索引を書き換え、フックの読み取りで読めるかを確かめる。"""
import difflib
import sys
import tempfile
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from rule_inject.features.index.service import load_indexes, match_path

ORIGINAL = """\
# rule-inject のルール索引
default_on: [write]
rules:
  # Python のルール
  - rule: "rules/python.md"
    paths: ["src/**/*.py", 'tests/**/*.py']
  - rule: rules/docs.md
    paths: ["docs/**/*.md"]
    enabled: false
"""

LONG_PATH = "**/src/very/deep/nested/package/with/a/long/name/for/round/trip/check/**/*.py"
NEW_RULE = "rules/ルール の 長い 名前 を 持つ 場所/with spaces/and/a/very/long/path/to/rule.md"


def make_yaml() -> YAML:
    yaml = YAML()
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.preserve_quotes = True
    return yaml


def flow(values: list[str]) -> CommentedSeq:
    seq = CommentedSeq(values)
    seq.fa.set_flow_style()
    return seq


def main() -> int:
    yaml = make_yaml()
    data = yaml.load(ORIGINAL)
    data["rules"][0]["paths"].append(LONG_PATH)
    entry = CommentedMap()
    entry["rule"] = NEW_RULE
    entry["paths"] = flow([LONG_PATH.replace("/src/", "/lib/")])
    data["rules"].append(entry)
    out = StringIO()
    yaml.dump(data, out)
    text = out.getvalue()
    print(text)
    print("--- diff ---")
    print("".join(difflib.unified_diff(ORIGINAL.splitlines(True), text.splitlines(True))))

    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "rules.yaml"
        index.write_text(text, encoding="utf-8")
        result = load_indexes([str(index)], {})
        print("entries:", len(result.entries), "failures:", result.failures)
        hit = match_path(result.entries, f"{tmp}/src/very/deep/nested/package/with/a/long/name/for/round/trip/check/x.py", "write")
        hit_new = match_path(result.entries, f"{tmp}/lib/very/deep/nested/package/with/a/long/name/for/round/trip/check/x.py", "write")
        print("long path hit:", hit)
        print("new entry hit:", hit_new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
