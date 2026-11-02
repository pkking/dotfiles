#!/usr/bin/env python3
"""Count supported agent CLI process trees without reading argv or environment."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

TOOLS = ("claude", "opencode", "codex", "agy", "pi")
ALIASES = {"claude": "claude", "opencode": "opencode", "codex": "codex",
           "agy": "agy", "antigravity": "agy", "pi": "pi"}


def classify(name: str) -> str | None:
    """Classify only exact process executable/comm names; never match arguments."""
    token = Path(name.strip()).name.lower()
    return ALIASES.get(token)


def parse_ppid(stat: str) -> int:
    """Read PPID from proc stat while allowing ')' in the parenthesized comm."""
    fields = stat.rsplit(")", 1)[1].split()
    return int(fields[1])


def scan(proc_root: Path, uid: int) -> dict[str, int]:
    """Count top-level same-tool process trees for uid; skip racing/inaccessible PIDs."""
    rows: dict[int, tuple[str, int]] = {}
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise RuntimeError("cannot enumerate process table") from exc

    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            pid = int(entry.name)
            if entry.stat().st_uid != uid:
                continue
            # comm and exe are kernel process identity metadata; cmdline/environ are
            # deliberately never opened, so prompts, credentials, and flags stay out.
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            exe = os.readlink(entry / "exe")
            tool = classify(Path(exe).name) or classify(comm)
            if tool is None:
                continue
            stat = (entry / "stat").read_text(encoding="ascii")
            rows[pid] = (tool, parse_ppid(stat))
        except (OSError, UnicodeError, ValueError, IndexError, PermissionError):
            continue

    roots = set(rows)
    for pid, (tool, parent) in rows.items():
        seen = {pid}
        while parent in rows and parent not in seen:
            seen.add(parent)
            parent_tool, parent = rows[parent]
            if parent_tool == tool:
                roots.discard(pid)
                break

    counts = dict.fromkeys(TOOLS, 0)
    for pid in roots:
        counts[rows[pid][0]] += 1
    return counts


def toml_string(value: str) -> str:
    """Serialize an arbitrary string as a TOML basic string."""
    escapes = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t",
               "\n": "\\n", "\f": "\\f", "\r": "\\r"}
    pieces = []
    for char in value:
        if char in escapes:
            pieces.append(escapes[char])
        elif ord(char) < 0x20 or ord(char) == 0x7f:
            pieces.append(f"\\u{ord(char):04X}")
        else:
            pieces.append(char)
    return '"' + "".join(pieces) + '"'


def render_toml(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    detail = " · ".join(f"{name} ×{counts[name]}" for name in TOOLS if counts[name])
    description = f"{total} 个运行中" + (f" · {detail}" if detail else "")
    lines = ["# Optional aggregate interface; contains no process details.",
             "[agent_status]", 'title = "AI Agents"',
             f"description = {toml_string(description)}", f"total = {total}",
             "[agent_status.counts]"]
    lines.extend(f"{name} = {counts[name]}" for name in TOOLS)
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    """Atomically replace path with private mode; preserve old file on failure."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toml-output", type=Path,
                        help="atomically write aggregate optional TOML instead of JSON")
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        counts = scan(args.proc_root, os.getuid())
        if args.toml_output:
            atomic_write(args.toml_output, render_toml(counts))
        else:
            print(json.dumps({"total": sum(counts.values()), "counts": counts},
                             separators=(",", ":")))
    except (OSError, RuntimeError) as exc:
        # Never echo OS error strings: paths may be sensitive on unusual systems.
        print(f"agent-status-collect: collection/output failed ({type(exc).__name__})",
              file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
