import os
from pathlib import Path


def _strip_inline_comment(value: str) -> str:
    in_quote: str | None = None
    escaped = False
    output: list[str] = []

    for index, char in enumerate(value):
        if escaped:
            output.append(char)
            escaped = False
            continue

        if char == "\\" and in_quote == '"':
            output.append(char)
            escaped = True
            continue

        if char in {"'", '"'}:
            if in_quote is None:
                in_quote = char
            elif in_quote == char:
                in_quote = None
            output.append(char)
            continue

        if char == "#" and in_quote is None and (index == 0 or value[index - 1].isspace()):
            break

        output.append(char)

    return "".join(output).strip()


def load_project_env(start_path: str | Path) -> None:
    current_path = Path(start_path).resolve()
    env_path = None
    for parent in current_path.parents:
        candidate = parent / ".env"
        if candidate.exists():
            env_path = candidate
            break
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def get_env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default
