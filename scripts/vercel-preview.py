#!/usr/bin/env python3
"""Narrow Vercel REST preview path; explicit opt-in, no linking or production."""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import subprocess
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from provider import METADATA, ProviderError, Vercel, diagnostic  # noqa: E402

PROTECTED = {"all", "all_except_custom_domains", "preview", "prod_deployment_urls_and_all_previews"}


def require(condition, message):
    if not condition:
        raise ProviderError(message)


def config():
    values = [os.environ.get(name, "") for name in
              ("FACTORY_VERCEL_TEAM_ID", "FACTORY_VERCEL_TEAM_SLUG", "VERCEL_PROJECT_ID")]
    require(re.fullmatch(r"team_[A-Za-z0-9]+", values[0]), "Set an approved FACTORY_VERCEL_TEAM_ID")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]*", values[1]), "Set an approved FACTORY_VERCEL_TEAM_SLUG")
    if values[2]:
        require(re.fullmatch(r"prj_[A-Za-z0-9]+", values[2]), "Invalid VERCEL_PROJECT_ID")
    return values


def identity(api, team, slug):
    user = api.request("GET", "/v2/user").get("user")
    require(isinstance(user, dict) and isinstance(user.get("id"), str) and user["id"],
            "Vercel principal response cannot be verified")
    data = api.request("GET", "/v2/teams/" + team)
    require(data.get("id") == team and data.get("slug") == slug, "Vercel team differs from approved target")


def project(api, team, project_id):
    data = api.request("GET", "/v9/projects/" + project_id + "?teamId=" + team)
    require(data.get("id") == project_id and data.get("accountId") == team,
            "Vercel project ownership differs from approved team/project")
    protection = data.get("ssoProtection")
    require(isinstance(protection, dict) and protection.get("deploymentType") in PROTECTED,
            "Required Vercel Authentication protection is missing; no settings changed")
    return data


def deployment(api, team, deployment_id, project_id):
    require(re.fullmatch(r"dpl_[A-Za-z0-9]+", deployment_id or ""), "Invalid deployment identity")
    data = api.request("GET", "/v13/deployments/" + deployment_id + "?teamId=" + team)
    require(data.get("id") == deployment_id and data.get("projectId") == project_id,
            "Vercel deployment identity/project mismatch; reconcile before further writes")
    return data


def preview_guard(api, team, project_id, data):
    # Vercel assigns a project's first deployment to production even without
    # --prod/target. A READY production baseline is required, not a failed attempt.
    baseline = (data.get("targets") or {}).get("production")
    require(isinstance(baseline, dict) and baseline.get("readyState") == "READY",
            "Preview blocked: no verified READY production baseline. A protected first production deployment needs separate approval.")
    actual = deployment(api, team, baseline.get("id"), project_id)
    require(actual.get("readyState") == "READY" and actual.get("target") == "production",
            "Preview blocked: production baseline cannot be verified")


def git_bytes(source, *args):
    # Never print Git diagnostics; an origin/config hook is not used here.
    env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, timeout=60, env=env)
    require(result.returncode == 0, "Source Git validation failed")
    return result.stdout


def verify_source(source, payload):
    source = source.resolve(strict=True)
    require((source / ".git").is_dir() and not (source / ".git").is_symlink(), "Source must be an independent app clone")
    require(git_bytes(source, "rev-parse", "--show-toplevel").decode().strip() == str(source), "Source checkout root mismatch")
    commit = payload["meta"]["factoryLastSourceCommit"]
    require(git_bytes(source, "rev-parse", "HEAD").decode().strip() == commit, "Source HEAD differs from declared commit")
    require(not git_bytes(source, "status", "--porcelain=v1", "--untracked-files=normal"), "Source checkout must be clean")
    expected = {}
    for raw in git_bytes(source, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not raw:
            continue
        detail, name = raw.split(b"\t", 1)
        mode, kind, object_id = detail.split()
        require(mode in (b"100644", b"100755") and kind == b"blob", "Symlink/submodule source is unsupported")
        expected[name.decode("utf-8")] = git_bytes(source, "cat-file", "blob", object_id.decode())
    require(set(expected) == {item["file"] for item in payload["files"]}, "Upload file set differs from committed source")
    for item in payload["files"]:
        actual = base64.b64decode(item["data"], validate=True) if item.get("encoding") == "base64" else item["data"].encode("utf-8")
        require(actual == expected[item["file"]], "Upload bytes differ from committed source")


def read_request(path, project_id, source):
    require(not path.is_symlink() and path.is_file() and not path.stat().st_mode & 0o077,
            "Request must be an existing private regular file (mode 600)")
    require(path.stat().st_size <= 12 * 1024 * 1024, "Preview request exceeds 12 MiB limit")
    raw = path.read_bytes()
    payload = json.loads(raw)
    require(isinstance(payload, dict) and set(payload) <= {"name", "project", "files", "meta", "projectSettings", "gitMetadata"},
            "Preview request contains unsupported fields; target, environment, env, gitSource and credentials are not accepted")
    require(payload.get("project") == project_id, "Request project differs from VERCEL_PROJECT_ID")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", payload.get("name", "")), "Invalid project name")
    files = payload.get("files")
    require(isinstance(files, list) and 0 < len(files) <= 1000, "Provide reviewed inline source files")
    seen = set()
    for file in files:
        require(isinstance(file, dict) and set(file) <= {"file", "data", "encoding"}, "Only inline source files are supported")
        name = file.get("file")
        require(isinstance(name, str) and len(name) < 512 and not name.startswith("/")
                and "\\" not in name and all(part not in ("", ".", "..", ".git", ".aws", ".vercel") for part in name.split("/"))
                and not any(part.startswith(".env") or part in ("id_rsa", "id_ed25519") or part.endswith((".pem", ".key")) for part in name.split("/"))
                and name not in seen, "Unsafe, duplicate or credential source path")
        require(isinstance(file.get("data"), str) and file.get("encoding", "utf-8") in ("utf-8", "base64"), "Malformed inline file")
        seen.add(name)
    meta = payload.get("meta")
    require(isinstance(meta, dict) and set(meta) == set(METADATA) and all(isinstance(meta.get(key), str) and 0 < len(meta[key]) <= 256 for key in METADATA),
            "All required provenance metadata must be present")
    require(meta["factoryEnvironment"] == "preview" and meta["factoryManagedBy"] == "engineering-factory"
            and meta["factoryProvenanceVersion"] == "1", "Invalid preview provenance mapping")
    require(re.fullmatch(r"[a-f0-9]{40}", meta["factoryLastSourceCommit"]), "Exact source commit is required")
    git = payload.get("gitMetadata", {})
    require(isinstance(git, dict) and git.get("commitSha") == meta["factoryLastSourceCommit"]
            and git.get("dirty") is False, "Reviewed committed source and matching gitMetadata commitSha/dirty=false required")
    # No git branch hint: production branch inference must not override preview.
    require(set(git) <= {"commitSha", "dirty"}, "Preview request must not contain a branch/remote hint")
    verify_source(source, payload)
    return payload, hashlib.sha256(raw).hexdigest()


def append(stream, event):
    event = dict(event, timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    stream.write(json.dumps(event, sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def run_preview(api, team, slug, project_id, payload, digest, record, wait_seconds=600, interval=5):
    require(project_id, "VERCEL_PROJECT_ID is required; auto-linking is unsupported")
    require(record.parent.is_dir() and not record.parent.stat().st_mode & 0o077,
            "Operation record parent must be a private directory (mode 700)")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(record, flags, 0o600)
    with os.fdopen(descriptor, "r+", encoding="utf-8") as stream:
        mode = os.fstat(stream.fileno()).st_mode
        require(stat.S_ISREG(mode) and not mode & 0o077, "Operation record must be a private regular file (mode 600)")
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProviderError("Operation is locked by another process") from None
        events = [json.loads(line) for line in stream if line.strip()]
        intent = {"event": "intent", "transport": "vercel-rest-v13", "team": team, "project": project_id,
                  "request_sha256": digest, "source_commit": payload["meta"]["factoryLastSourceCommit"],
                  "run_id": payload["meta"]["factoryLastRunId"]}
        if events:
            require({key: value for key, value in events[0].items() if key != "timestamp"} == intent, "Operation record/request mismatch; no mutation attempted")
        identity(api, team, slug)
        current = project(api, team, project_id)
        require(current.get("name") == payload["name"], "Project name differs from reviewed request")
        known = [event.get("id") for event in events if event.get("event") == "created"]
        require(len(known) <= 1, "Operation has multiple deployment identities; reconcile privately")
        if events:
            require(known, "Prior mutation outcome unknown/rejected. Reconcile inventory; this operation will not POST again.")
            deployment_id = known[0]
        else:
            preview_guard(api, team, project_id, current)
            append(stream, intent)  # Durable intent before the single POST.
            try:
                created = api.request("POST", "/v13/deployments?teamId=" + team, payload)
                deployment_id = created.get("id")
                require(re.fullmatch(r"dpl_[A-Za-z0-9]+", deployment_id or ""), "Create response lacks deployment identity; reconcile privately")
                append(stream, {"event": "created", "id": deployment_id})
            except ProviderError:
                append(stream, {"event": "outcome-unknown-or-rejected"})
                raise
        deadline = time.monotonic() + wait_seconds
        while True:
            actual = deployment(api, team, deployment_id, project_id)
            require("target" in actual and actual["target"] is None,
                    "Deployment is not preview; stop and reconcile. No promotion, cancellation or retry attempted.")
            require(isinstance(actual.get("meta"), dict) and all(actual["meta"].get(key) == value for key, value in payload["meta"].items()),
                    "Deployment provenance/source mismatch; no further writes")
            state = actual.get("readyState")
            require(state in {"READY", "ERROR", "CANCELED", "BLOCKED", "QUEUED", "INITIALIZING", "BUILDING"}, "Unknown deployment state")
            if state == "READY":
                project(api, team, project_id)  # Protection still present at acceptance.
                hostname = actual.get("url", "")
                require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,200}\.vercel\.app", hostname), "Deployment hostname cannot be verified")
                append(stream, {"event": "ready", "id": deployment_id, "hostname": hostname, "target": "preview"})
                print("Vercel REST: verified preview READY, exact project/provenance and protection. Deployed HTTPS/browser checks remain separate.")
                return
            if state in {"ERROR", "CANCELED", "BLOCKED"}:
                append(stream, {"event": "terminal", "id": deployment_id, "state": state})
                raise ProviderError("Vercel deployment " + state + "; " + diagnostic("Vercel", body=json.dumps({"error": {"code": actual.get("errorCode"), "message": actual.get("errorMessage", "")}})))
            require(time.monotonic() < deadline, "Deployment wait timed out. Known ID retained; rerun the same operation to read/poll only.")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("identity", "deploy"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--wait-seconds", type=int, default=600)
    args = parser.parse_args()
    team, slug, project_id = config()
    api = Vercel()
    if args.command == "identity":
        identity(api, team, slug)
        print("Vercel REST: principal and approved team verified. Native CLI compatibility and deployment permissions UNVERIFIED.")
    else:
        require(args.confirm == team + "/" + project_id and project_id, "Confirm the exact approved team/project")
        require(args.request and args.record and args.source and 0 <= args.wait_seconds <= 1800, "Private request/record and bounded wait are required")
        payload, digest = read_request(args.request, project_id, args.source)
        run_preview(api, team, slug, project_id, payload, digest, args.record, args.wait_seconds)


if __name__ == "__main__":
    try:
        main()
    except ProviderError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        print("ERROR: Invalid private file/configuration or provider response. Reconcile before retry.", file=sys.stderr)
        sys.exit(1)
