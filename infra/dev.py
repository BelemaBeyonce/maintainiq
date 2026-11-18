"""One-command local startup on Windows/macOS/Linux; standard library only."""

import argparse
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ensure_environment():
    path = ROOT / ".env"
    if path.exists():
        content = path.read_text()
        if "GENERATE_LOCALLY" in content:
            raise SystemExit(
                ".env contains placeholders. Remove the unused template copy and rerun, or set your own secrets."
            )
        return
    password = secrets.token_hex(24)
    content = (
        (ROOT / ".env.example")
        .read_text()
        .replace(
            "DJANGO_SECRET_KEY=GENERATE_LOCALLY",
            f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}",
        )
        .replace("GENERATE_LOCALLY", password)
    )
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(content)
    print(
        "Created private .env with random local secrets; existing environments are never overwritten."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["up", "down", "credentials", "config"])
    args = parser.parse_args()
    ensure_environment()
    base = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "compose.yaml"),
    ]
    suffix = {
        "up": ["up", "--build", "-d", "--wait"],
        "down": ["down"],
        "credentials": ["exec", "-T", "backend", "cat", "/data/demo-credentials.json"],
        "config": ["config", "--quiet"],
    }[args.command]
    subprocess.run(base + suffix, cwd=ROOT, check=True)
    if args.command == "up":
        print(
            "MaintainIQ: http://localhost:3000 | API docs: http://localhost:3000/api/docs/ | local mail: http://localhost:8025"
        )


if __name__ == "__main__":
    main()
