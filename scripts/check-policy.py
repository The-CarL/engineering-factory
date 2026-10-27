#!/usr/bin/env python3
"""Small repository guardrails; content-aware secret detection runs separately."""
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
required = ["README.md", "AGENTS.md", "LICENSE", ".gitignore", ".env.example",
            ".github/CODEOWNERS", ".github/pull_request_template.md",
            "standards/software-quality.md", "standards/testing.md", "standards/security.md",
            "standards/infrastructure.md", "standards/deployment.md", "standards/conversational-delivery.md",
            "docs/architecture.md", "docs/setup.md", "docs/security-model.md",
            "docs/mobile-workflow.md", "docs/credential-checklist.md",
            "standards/android.md", "docs/android-delivery.md", "scripts/android-sign.py",
            "scripts/android-artifact.py", "scripts/android-release.py"]
errors = [f"Missing required file: {name}" for name in required if not (root / name).is_file()]
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
for name in filter(None, tracked):
    path = PurePosixPath(name)
    if (any(part in (".aws", ".terraform", "workspaces", ".vercel") for part in path.parts)
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in ("id_rsa", "id_ed25519")
            or re.search(r"\.(?:pem|key|tfvars|jks|keystore|p12|pfx|apk|aab)$|\.tfstate(?:\.|$)", path.name)):
        errors.append(f"Forbidden tracked credential/state/workspace path: {name}")
example = root / ".env.example"
if example.is_file():
    for line in example.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and not re.fullmatch(r"[A-Z][A-Z0-9_]*=", line):
            errors.append(".env.example must contain only comments and blank-valued variable names")
for path in root.glob(".github/workflows/*"):
    text = path.read_text()
    if "pull_request_target" in text or "secrets." in text:
        errors.append(f"Privileged event or explicit secret reference in {path.name}")
    for match in re.finditer(r"^\s*uses:\s*(\S+)", text, re.MULTILINE):
        if not re.fullmatch(r"actions/[A-Za-z0-9_-]+@[a-f0-9]{40}", match[1]):
            errors.append(f"Action must be GitHub-owned and full SHA-pinned in {path.name}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("Repository policy checks passed.")
