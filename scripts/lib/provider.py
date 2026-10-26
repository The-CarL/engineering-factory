"""Bounded provider transport and diagnostics; raw responses never become errors."""
import errno
import json
import os
import re
import socket
import ssl
import subprocess
import urllib.error
import urllib.request


METADATA = ("factoryProjectId", "factoryEnvironment", "factoryOwner", "factoryManagedBy",
            "factorySourceRepo", "factorySourceCommit", "factoryCreatedBy", "factoryCreatedAt",
            "factoryCreationRunId", "factoryLastRunId", "factoryLastSourceCommit",
            "factoryProvenanceVersion", "factoryExpiresAt")

# Additive v1 extension; old journals/receipts keep their original bytes.
READABLE_METADATA = ("factoryProjectName", "factoryRepoName", "factorySourceBranch",
                     "factorySourceAuthor", "factoryLastSourceBranch", "factoryLastSourceAuthor")
CREATION_METADATA = ("factorySourceRepo", "factorySourceCommit", "factoryCreatedBy",
                     "factoryCreatedAt", "factoryCreationRunId",
                     "factoryRepoName", "factorySourceBranch", "factorySourceAuthor")


class ProviderError(Exception):
    """Contains only a fixed classification and allowlisted diagnostic fields."""


def validate_metadata_shape(meta):
    """Accept the exact legacy core or complete readable extension; no arbitrary keys."""
    core, readable = set(METADATA), set(READABLE_METADATA)
    if not isinstance(meta, dict) or set(meta) not in (core, core | readable):
        raise ProviderError("Provide canonical provenance with either no readable extension or all six readable fields")
    if readable <= set(meta):
        for key in READABLE_METADATA:
            value = meta[key]
            if not (isinstance(value, str) and 0 < len(value) <= 256 and value == value.strip()
                    and all(c.isalnum() or c in " ._:/=+-@" for c in value)
                    and "://" not in value and not re.search(r"[^ ]+@[^ ]+\.[^ ]+", value)):
                raise ProviderError("Use bounded nonsecret readable labels without email addresses, URLs or control characters")
        repo = meta.get("factorySourceRepo")
        if not isinstance(repo, str) or meta["factoryRepoName"] != repo.rsplit("/", 1)[-1]:
            raise ProviderError("Readable repository name must match the original source repository")
    return meta


def preserve_creation_metadata(meta, previous):
    """Never drop/rewrite known original attribution, including readable snapshots."""
    if not isinstance(previous, dict):
        raise ProviderError("Original creation attribution is unavailable")
    for key in CREATION_METADATA:
        if (key in METADATA or key in previous) and meta.get(key) != previous.get(key):
            raise ProviderError("Updates must preserve original creation attribution")


# Never echo arbitrary provider messages, codes, headers, URLs, or exception text.
CODES = {"forbidden", "unauthorized", "bad_request", "invalid_request", "invalid_target",
         "invalid_engines_value", "not_found", "rate_limited", "deployment_not_found"}
TRANSPORT_REASONS = (
    ("[errno 1]", "OS denied network or process access; HTTP unconfirmed"),
    ("[errno 13]", "OS denied network or process access; HTTP unconfirmed"),
    ("socket: operation not permitted", "OS denied network or process access; HTTP unconfirmed"),
    ("connect: operation not permitted", "OS denied network or process access; HTTP unconfirmed"),
    ("socket: permission denied", "OS denied network or process access; HTTP unconfirmed"),
    ("connect: permission denied", "OS denied network or process access; HTTP unconfirmed"),
    ("network is unreachable", "network unreachable; HTTP unconfirmed"),
    ("connection timed out", "connection timeout; HTTP unconfirmed"),
    ("could not resolve host", "Git host resolution failed"),
    ("ssl certificate problem", "Git TLS certificate verification failed"),
    ("tls connection", "Git TLS connection failed"),
    ("failed to connect", "Git connection failed"),
)
REASONS = (
    ("resource not accessible by personal access token", "token cannot access this resource"),
    ("resource not accessible by integration", "integration cannot access this resource"),
    ("authentication failed", "Git credentials rejected"),
    ("repository not found", "repository absent or inaccessible"),
    ("bad credentials", "credentials rejected"),
    ("requires authentication", "authentication required"),
    ("ebadengine", "unsupported package engines configuration"),
    ("invalid_engines_value", "unsupported package engines configuration"),
    ("invalid target", "invalid deployment target"),
    ("rate limit", "provider rate limit"),
    ("validation failed", "request validation failed"),
)


def transport_reason(error):
    """Classify exception types/errno; never expose exception text or request data."""
    if isinstance(error, urllib.error.URLError):
        error = error.reason
    if isinstance(error, OSError) and error.errno in (errno.EPERM, errno.EACCES):
        return "os_permission_denied"
    if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
        return "timeout"
    if isinstance(error, socket.gaierror):
        return "dns_failure"
    if isinstance(error, ssl.SSLError):
        return "tls_failure"
    if "tunnel connection failed" in str(error).lower():
        return "proxy_tunnel_failure"
    if isinstance(error, OSError) and error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ECONNREFUSED, errno.ECONNRESET):
        return "connection_failure"
    return "transport_or_response_failure"


def diagnostic(provider, status=None, headers=None, body=b"", stderr=b""):
    """Emit classifications, never provider-authored free text (even after redaction)."""
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if isinstance(body, bytes):
        body = body[:65536].decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr[:65536].decode("utf-8", "replace")
    message = ""
    code = None
    try:
        obj = json.loads(body)
        error = obj.get("error", obj) if isinstance(obj, dict) else {}
        if isinstance(error, dict):
            message = error.get("message", "")
            candidate = error.get("code")
            if candidate in CODES:
                code = candidate
    except (ValueError, TypeError):
        pass
    text = (str(message) + " " + str(stderr)).lower()
    if status is None:
        match = re.search(r"\bHTTP[ /](\d{3})\b", stderr, re.IGNORECASE)
        if match:
            status = int(match[1])
    reason = next((safe for fragment, safe in TRANSPORT_REASONS if status is None and fragment in stderr.lower()), None)
    if reason is None:
        reason = next((safe for fragment, safe in REASONS if fragment in text), "provider detail withheld")
    fields = [provider, "HTTP " + str(status) if isinstance(status, int) and 100 <= status <= 599 else "status unknown"]
    if code:
        fields.append("code=" + code)
    fields.append("reason=" + reason)
    # Only the actual provider's request-ID syntax, not arbitrary header values.
    request_id = headers.get("x-github-request-id", "") if provider == "GitHub" else headers.get("x-vercel-id", "")
    pattern = r"[A-Fa-f0-9]{4}:[A-Fa-f0-9]{4,8}:[A-Fa-f0-9]{4,8}:[A-Fa-f0-9]{4,8}:[A-Fa-f0-9]{8}" if provider == "GitHub" else r"[a-z]{3}[0-9](?::[a-z]{3}[0-9])?::[a-z0-9]{5}-[0-9]{13}-[a-f0-9]{12}"
    if re.fullmatch(pattern, request_id):
        fields.append("request_id=" + request_id)
    return "; ".join(fields)


def gh_environment():
    source = os.environ.get("FACTORY_GITHUB_CREDENTIAL_SOURCE", "cli")
    if source not in ("cli", "factory-token"):
        raise ProviderError("GitHub credential source must be cli or factory-token")
    selected = None
    if source == "factory-token":
        selected = os.environ.get("FACTORY_GITHUB_TOKEN", "")
        if not selected.strip():
            raise ProviderError("FACTORY_GITHUB_TOKEN binding is required for factory-token mode")
    env = dict(os.environ, GH_HOST="github.com", GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0")
    # The namespaced value is consumed here, never forwarded as an extra secret.
    env.pop("FACTORY_GITHUB_TOKEN", None)
    if selected is not None:
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
            env.pop(key, None)
        env["GH_TOKEN"] = selected
    for key in list(env):
        if key.startswith("GIT_TRACE") or key in ("GH_DEBUG", "DEBUG", "GIT_CURL_VERBOSE"):
            del env[key]
    return env


def gh(args, payload=None, include=False):
    command = ["gh", "api", "--hostname", "github.com"]
    if include:
        command.append("--include")
    env = gh_environment()
    try:
        result = subprocess.run(command + args, input=None if payload is None else json.dumps(payload).encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProviderError("GitHub; " + transport_reason(error) + "; HTTP unconfirmed; outcome may be unknown") from None
    data, status, headers = result.stdout, None, {}
    if include:
        # --include is used for a single creation request, never paginated output.
        raw = data.replace(b"\r\n", b"\n")
        head, separator, data = raw.partition(b"\n\n")
        if separator:
            lines = head.decode("utf-8", "replace").splitlines()
            match = re.match(r"HTTP/\S+ (\d{3})", lines[0]) if lines else None
            status = int(match[1]) if match else None
            headers = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
            headers = {key.lower(): value.strip() for key, value in headers.items()}
        else:
            data = raw
    if result.returncode or (status is not None and status >= 400):
        raise ProviderError(diagnostic("GitHub", status, headers, data, result.stderr))
    if include and status != 201:
        raise ProviderError("GitHub; unexpected creation response; reconcile before retry")
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Authorization to a redirect destination.


class Vercel:
    def __init__(self):
        self.token = os.environ.get("VERCEL_TOKEN")
        if not self.token:
            raise ProviderError("VERCEL_TOKEN binding is required")
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        # Callers construct paths from validated IDs; no arbitrary origin is accepted.
        if not re.fullmatch(r"/v\d+/[A-Za-z0-9_/?=&.-]+", path):
            raise ProviderError("Invalid Vercel API path")
        request = urllib.request.Request("https://api.vercel.com" + path, method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise ProviderError("Vercel response exceeds size limit; reconcile before retry")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError()
                return data
        except urllib.error.HTTPError as error:
            raise ProviderError(diagnostic("Vercel", error.code, error.headers, error.read(65536))) from None
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise ProviderError("Vercel; " + transport_reason(error) + "; HTTP unconfirmed; reconcile before retry") from None


def gh_clone(target, path):
    env = gh_environment()
    try:
        result = subprocess.run(["gh", "repo", "clone", target, path], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProviderError("GitHub clone; " + transport_reason(error) + "; HTTP unconfirmed; inspect retained remote repository before retry") from None
    if result.returncode:
        raise ProviderError(diagnostic("GitHub", stderr=result.stderr))
