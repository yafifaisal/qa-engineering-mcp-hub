"""Read-only local Git metadata using a fixed argument list.

Purpose: report branch, origin URL, HEAD, and dirty state for one approved checkout.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.git_metadata
Dependencies: Repository models, bounded process policy, and source references.
Expected tests: detached heads, multiple remotes, dirty state, timeouts, and redaction.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from qa_mcp_hub.core.errors import GitInspectionError, PathAllowlistError
from qa_mcp_hub.repositories.models import GitMetadata
from qa_mcp_hub.security.path_allowlist import resolve_within

_GIT_TIMEOUT_SECONDS = 10


def redact_git_url(url: str) -> str:
    """Drop userinfo from an HTTP(S) URL and a leading user from an scp-style URL."""
    if "://" in url:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    if "@" in url:
        return url.split("@", 1)[1]
    return url


def assert_git_dir_contained(
    repository: Path, roots: tuple[Path, ...] | list[Path]
) -> None:
    """Reject a ``.git`` symlink or gitdir pointer that leaves the approved roots."""
    git_entry = repository / ".git"
    if not git_entry.exists():
        raise GitInspectionError("directory is not a Git repository")
    if git_entry.is_symlink():
        resolve_within(git_entry, roots)
        return
    if git_entry.is_file():
        pointer = git_entry.read_text(encoding="utf-8", errors="replace")[:200]
        if pointer.startswith("gitdir:"):
            raw = pointer.split(":", 1)[1].strip()
            target = Path(raw)
            if not target.is_absolute():
                target = repository / target
            resolve_within(target, roots)


def read_git_metadata(
    repository: Path,
    roots: tuple[Path, ...] | list[Path],
) -> GitMetadata:
    """Inspect one local checkout. The command list is fixed and shell is disabled."""
    approved = resolve_within(repository, roots)
    assert_git_dir_contained(approved, roots)
    head = _git(approved, ["rev-parse", "HEAD"]).strip().lower()
    valid_hex = all(character in "0123456789abcdef" for character in head)
    if len(head) != 40 or not valid_hex:
        raise GitInspectionError("HEAD is not a commit")
    branch_name = _git(approved, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    detached = branch_name == "HEAD"
    remote_url = _remote_url(approved)
    dirty = bool(_git(approved, ["status", "--porcelain"]).strip())
    return GitMetadata(
        branch=None if detached else branch_name,
        detached=detached,
        remote_url=remote_url,
        head_sha=head,
        dirty=dirty,
    )


def _remote_url(repository: Path) -> str | None:
    completed = _run(repository, ["remote", "get-url", "origin"])
    if completed.returncode != 0:
        return None
    url = completed.stdout.strip()
    if not url:
        return None
    return redact_git_url(url)


def list_tracked_files(
    repository: Path,
    roots: tuple[Path, ...] | list[Path],
) -> tuple[str, ...]:
    """Return tracked paths. Untracked files are omitted and are not indexed."""
    approved = resolve_within(repository, roots)
    output = _git(approved, ["ls-files", "-z"])
    return tuple(
        item for item in output.split("\0") if item and ".." not in item.split("/")
    )


def last_commit_for_path(
    repository: Path,
    roots: tuple[Path, ...] | list[Path],
    relative_path: str,
) -> tuple[str, datetime | None]:
    """Return the last commit that touched one tracked file, plus its timestamp."""
    approved = resolve_within(repository, roots)
    if relative_path.startswith("/") or ".." in relative_path.split("/"):
        raise PathAllowlistError("file path is not inside the repository")
    completed = _run(
        approved,
        ["log", "-1", "--format=%H%x09%cI", "--", relative_path],
    )
    if completed.returncode != 0:
        raise GitInspectionError("file revision is unavailable")
    line = completed.stdout.strip()
    sha, separator, stamp = line.partition("\t")
    valid = len(sha) == 40 and all(character in "0123456789abcdef" for character in sha)
    if not separator or not valid:
        raise GitInspectionError("file revision is unavailable")
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        parsed = None
    return sha, parsed


def changed_tracked_paths(
    repository: Path,
    roots: tuple[Path, ...] | list[Path],
) -> tuple[str, ...]:
    """Return tracked paths that ``git status`` reports as changed."""
    approved = resolve_within(repository, roots)
    if not read_git_metadata(approved, roots).dirty:
        return ()
    completed = _run(approved, ["status", "--porcelain"])
    if completed.returncode != 0:
        raise GitInspectionError("git status could not be read")
    tracked = set(list_tracked_files(approved, roots))
    names: list[str] = []
    for line in completed.stdout.splitlines():
        path = line[3:].strip().replace("\\", "/")
        if ".." in path.split("/") or path not in tracked:
            continue
        names.append(path)
    return tuple(dict.fromkeys(names))


def _git(repository: Path, args: list[str]) -> str:
    completed = _run(repository, args)
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        summary = detail[0][:180] if detail else "git command failed"
        raise GitInspectionError(summary)
    return completed.stdout


def _run(repository: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    if executable is None:
        raise GitInspectionError("git executable is not available")
    try:
        return subprocess.run(  # noqa: S603 - fixed executable and argument list
            [executable, "-C", str(repository), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitInspectionError("git command timed out") from exc
    except OSError as exc:
        raise PathAllowlistError("git metadata could not be read") from exc
