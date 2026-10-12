import re
import secrets
import sys
from pathlib import Path


SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "CLICKHOUSE_PASSWORD",
    "REDIS_AUTH",
    "MINIO_ROOT_PASSWORD",
    "SALT",
    "ENCRYPTION_KEY",
    "NEXTAUTH_SECRET",
)
PROJECT_KEYS = {
    "LANGFUSE_PUBLIC_KEY": "pk-lf-",
    "LANGFUSE_SECRET_KEY": "sk-lf-",
}
PROJECT_DEFAULTS = {
    "LANGFUSE_INIT_PROJECT_ID": "local-project",
    "LANGFUSE_INIT_PROJECT_NAME": "Local Project",
}
PLACEHOLDER_MARKERS = ("REPLACE_WITH", "CHANGE_ME", "CHANGEME", "YOUR_")


def needs_secret(value: str) -> bool:
    normalized = value.strip().strip("\"'")
    return not normalized or any(marker in normalized.upper() for marker in PLACEHOLDER_MARKERS)


def generated_value(key: str) -> str:
    if key in PROJECT_KEYS:
        return PROJECT_KEYS[key] + secrets.token_hex(32)
    if key in PROJECT_DEFAULTS:
        return PROJECT_DEFAULTS[key]
    return secrets.token_hex(32)


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    env_path = project_dir / ".env"
    example_path = project_dir / ".env.example"

    if not env_path.exists():
        if not example_path.exists():
            print("Neither .env nor .env.example was found.", file=sys.stderr)
            return 1
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated_keys: set[str] = set()
    output_lines = []
    managed_keys = set(SECRET_KEYS) | set(PROJECT_KEYS) | set(PROJECT_DEFAULTS)
    present_keys: set[str] = set()

    for line in lines:
        match = re.match(r"^(\s*)([A-Z0-9_]+)(\s*=\s*)(.*?)(\r?\n)?$", line)
        if not match or match.group(2) not in managed_keys:
            output_lines.append(line)
            continue

        key = match.group(2)
        value = match.group(4)
        present_keys.add(key)
        if key in PROJECT_KEYS:
            normalized = value.strip().strip("\"'")
            valid = normalized.startswith(PROJECT_KEYS[key]) and len(normalized) > len(PROJECT_KEYS[key])
        elif key in PROJECT_DEFAULTS:
            valid = bool(value.strip())
        else:
            valid = not needs_secret(value)
        if not valid:
            value = generated_value(key)
            updated_keys.add(key)
        output_lines.append(f"{match.group(1)}{key}{match.group(3)}{value}{match.group(5) or ''}")

    if output_lines and not output_lines[-1].endswith(("\n", "\r")):
        output_lines[-1] += "\n"

    for key in sorted(managed_keys - present_keys):
        output_lines.append(f"{key}={generated_value(key)}\n")
        updated_keys.add(key)

    env_path.write_text("".join(output_lines), encoding="utf-8")

    if updated_keys:
        print("Updated .env settings for: " + ", ".join(sorted(updated_keys)))
    else:
        print("All Langfuse secrets are already set; nothing was changed.")
    print("Secret values were not displayed. Keep .env private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())