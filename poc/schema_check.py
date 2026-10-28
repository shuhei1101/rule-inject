"""PoC: 索引の JSON Schema で違反の種類ごとに、場所と理由が取れるかを確かめる。"""
import sys

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

SCHEMA = YAML(typ="safe").load("""\
type: object
additionalProperties: false
properties:
  default_on: {type: array, items: {enum: [read, write]}}
  rules:
    type: array
    items:
      type: object
      additionalProperties: false
      required: [rule]
      properties:
        rule: {type: string}
        paths: {type: array, items: {type: string}}
        enabled: {enum: ["true", "false", true, false]}
""")

INDEX = YAML(typ="safe").load("""\
rules:
  - rule: rules/a.md
    paths: "src/**/*.py"
  - rule: rules/b.md
    color: red
  - paths: ["docs/**"]
""")


def main() -> int:
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(INDEX), key=lambda e: list(e.absolute_path))
    for error in errors:
        print(error.validator, list(error.absolute_path), error.message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
