#!/usr/bin/env python3
"""Validate ezwallpaper policy and optionally run an offline preview."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PIN = "4e72605fe788f1c1da1cb9aeba103353df547838"
PINNED_ROOT = Path.home() / ".local/lib/ezwallpaper" / PIN
DEFAULT_BINARY = str(PINNED_ROOT / "bin/ezwallpaper")
OUTPUT_NAMES = ("DP-1", "HDMI-A-1")
OUTCOME_KEYS = {
    "output", "epoch", "decision", "content_id", "path",
    "applied_path_observed", "visually_verified", "reason",
}
UPSTREAM_GAPS = {
    "schedule_idempotency": (
        "https://github.com/pkking/ezwallpaper/issues/54"
        "#issuecomment-6321506337"
    ),
    "retention_budget": (
        "https://github.com/pkking/ezwallpaper/issues/57"
        "#issuecomment-6321507997"
    ),
    "streaming_download_limit": (
        "https://github.com/pkking/ezwallpaper/issues/79"
    ),
}


class ConfigError(ValueError):
    """Raised when an integration configuration is unsafe or malformed."""


def positive_integer(value: object, label: str) -> int:
    """Return a strictly positive integer, excluding booleans.

    Args:
        value: Value to validate.
        label: Field name included in any diagnostic.

    Returns:
        The validated integer.

    Raises:
        ConfigError: If the value is not a positive integer.
    """
    if type(value) is not int or value <= 0:
        raise ConfigError(f"{label} must be a positive integer")
    return value


def resolve_pool(raw: str, label: str) -> Path:
    """Resolve a home-relative pool path and enforce home containment.

    Args:
        raw: Configured path beginning with ``~/``.
        label: Output name for diagnostic context.

    Returns:
        Resolved pool path.

    Raises:
        ConfigError: If resolving fails or the pool escapes the home directory.
    """
    if not raw.startswith("~/"):
        raise ConfigError(
            f"outputs.{label}.pool must be under the home directory"
        )
    if "\0" in raw:
        raise ConfigError(f"outputs.{label}.pool contains a null byte")
    home = Path.home().resolve()
    candidate = Path(os.path.expanduser(raw))
    try:
        try:
            path = candidate.resolve(strict=True)
        except FileNotFoundError:
            path = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError(
            f"outputs.{label}.pool cannot be resolved: {exc}"
        ) from None
    if path == home or not path.is_relative_to(home):
        raise ConfigError(
            f"outputs.{label}.pool must be a dedicated home-directory pool"
        )
    return path


def validate(config: object) -> dict[str, object]:
    """Validate public settings and return normalized policy data.

    Args:
        config: Parsed JSON configuration object.

    Returns:
        Validated settings with resolved output paths.

    Raises:
        ConfigError: If configuration is malformed or violates policy.
    """
    expected = {
        "schema_version", "binary", "interval_seconds", "pool_capacity_bytes",
        "provider", "retention", "outputs",
    }
    if not isinstance(config, dict) or set(config) != expected:
        raise ConfigError(
            "configuration keys must be exactly: "
            + ", ".join(sorted(expected))
        )
    if (type(config["schema_version"]) is not int
            or config["schema_version"] != 1):
        raise ConfigError("schema_version must be 1")
    binary = config["binary"]
    if (not isinstance(binary, str) or not os.path.isabs(binary)
            or os.path.normpath(binary) != binary):
        raise ConfigError("binary must be a normalized absolute path")
    if binary != DEFAULT_BINARY:
        raise ConfigError(
            "binary must be the pinned ezwallpaper commit executable"
        )

    interval = positive_integer(config["interval_seconds"], "interval_seconds")
    capacity = positive_integer(
        config["pool_capacity_bytes"], "pool_capacity_bytes"
    )
    provider = config["provider"]
    expected_provider = {
        "name": "wallhaven", "purity": "sfw", "query": "nature",
    }
    if not isinstance(provider, dict) or provider != expected_provider:
        raise ConfigError("provider must use Wallhaven SFW with query=nature")

    retention = config["retention"]
    if (not isinstance(retention, dict)
            or retention.get("mode") not in ("capacity", "time")):
        raise ConfigError("retention.mode must be capacity or time")
    mode = retention["mode"]
    keys = {"mode", "on_full"}
    if mode == "time":
        keys.add("max_age_seconds")
    if set(retention) != keys:
        raise ConfigError("retention keys do not match the selected mode")
    if retention["on_full"] not in ("stop", "delete_oldest"):
        raise ConfigError("retention.on_full must be stop or delete_oldest")
    if mode == "time":
        positive_integer(
            retention["max_age_seconds"], "retention.max_age_seconds"
        )

    outputs = config["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != set(OUTPUT_NAMES):
        raise ConfigError("outputs must name exactly DP-1 and HDMI-A-1")
    pools = []
    for name in OUTPUT_NAMES:
        item = outputs[name]
        if (not isinstance(item, dict) or set(item) != {"pool"}
                or not isinstance(item["pool"], str)):
            raise ConfigError(f"outputs.{name}.pool must be a path")
        pools.append(resolve_pool(item["pool"], name))
    if (pools[0] == pools[1] or pools[0] in pools[1].parents
            or pools[1] in pools[0].parents):
        raise ConfigError("output pools must be disjoint")
    return {
        "binary": binary,
        "interval_seconds": interval,
        "pool_capacity_bytes": capacity,
        "provider": provider,
        "retention": retention,
        "outputs": dict(zip(OUTPUT_NAMES, pools)),
    }


def run_preview(config: dict[str, object]) -> dict[str, object]:
    """Run a bounded dry-run using temporary profile and state paths.

    Args:
        config: Validated policy data.

    Returns:
        Validated upstream preview response.

    Raises:
        ConfigError: If pools or the upstream preview response are invalid.
    """
    profile_outputs = []
    for name in OUTPUT_NAMES:
        pool = config["outputs"][name]
        if not pool.exists() or not pool.is_dir():
            raise ConfigError(
                f"preview pool does not exist or is not a directory: {pool}"
            )
        profile_outputs.append({
            "name": name, "dir": str(pool), "recursive": False,
        })

    with tempfile.TemporaryDirectory(prefix="ezwallpaper-preview-") as temp:
        root = Path(temp)
        profile = root / "profile.json"
        state = root / "state.json"
        profile.write_text(json.dumps({
            "schema_version": 1,
            "owner": "ezwallpaper",
            "outputs": profile_outputs,
        }), encoding="utf-8")
        command = [
            config["binary"], "rotate", "next", "--profile", str(profile),
            "--state", str(state), "--dry-run", "--force", "--json",
        ]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConfigError(f"preview process failed: {exc}") from None
        if result.returncode:
            raise ConfigError(
                f"preview process exited with status {result.returncode}"
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise ConfigError("preview returned invalid JSON") from None
        if (not isinstance(data, dict)
                or set(data) != {"schema_version", "outputs"}
                or type(data["schema_version"]) is not int
                or data["schema_version"] != 1
                or not isinstance(data["outputs"], list)):
            raise ConfigError("preview returned an invalid response schema")
        if len(data["outputs"]) != len(OUTPUT_NAMES):
            raise ConfigError("preview must return exactly two output results")

        seen = set()
        for item in data["outputs"]:
            if not isinstance(item, dict) or set(item) != OUTCOME_KEYS:
                raise ConfigError("preview output has an invalid schema")
            name = item["output"]
            if name not in OUTPUT_NAMES or name in seen:
                raise ConfigError(
                    "preview output names are missing, unknown, or duplicated"
                )
            if (type(item["epoch"]) is not int
                    or item["decision"] not in (
                        "select", "already_applied", "empty_pool",
                        "no_alternative",
                    )
                    or (item["content_id"] is not None
                        and not isinstance(item["content_id"], str))
                    or (item["path"] is not None
                        and not isinstance(item["path"], str))
                    or not isinstance(item["reason"], str)):
                raise ConfigError(
                    "preview output contains invalid field values"
                )
            if (item["applied_path_observed"] is not False
                    or item["visually_verified"] is not False):
                raise ConfigError(
                    "preview response claims apply or visual verification"
                )
            selected_path = item["path"]
            if item["decision"] == "select":
                if not isinstance(selected_path, str):
                    raise ConfigError(
                        "preview select decision requires a path"
                    )
                pool = config["outputs"][name]
                try:
                    resolved = Path(selected_path).resolve(strict=False)
                except (OSError, RuntimeError, ValueError):
                    raise ConfigError(
                        "preview selected path cannot be resolved"
                    ) from None
                if (not Path(selected_path).is_absolute()
                        or not resolved.is_relative_to(pool)):
                    raise ConfigError(
                        "preview selected path must be inside its output pool"
                    )
            seen.add(name)
        if seen != set(OUTPUT_NAMES):
            raise ConfigError("preview is missing an expected output")
        return data


def main() -> int:
    """Validate and print a plan, optionally with offline preview.

    Returns:
        Process exit status (zero on success, two on validation failure).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        raw_config = Path(args.config).read_text(encoding="utf-8")
        config = validate(json.loads(raw_config))
        preview = run_preview(config) if args.preview else None
        plan = {
            "readiness": "blocked",
            "reason": (
                "scheduling and retention enforcement are not implemented"
            ),
            "interval_seconds": config["interval_seconds"],
            "pool_capacity_bytes": config["pool_capacity_bytes"],
            "retention": config["retention"],
            "outputs": {
                key: str(value) for key, value in config["outputs"].items()
            },
            "unsupported_capabilities": [
                "fetch_interval", "pool_retention_budget",
                "retention_gc", "on_full",
            ],
            "upstream_gaps": UPSTREAM_GAPS,
            "external_process_started": args.preview,
            "preview": preview,
        }
        if args.json:
            print(json.dumps(plan, indent=2, sort_keys=True))
        else:
            print("Configuration valid; readiness=blocked")
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ConfigError) as exc:
        print(f"ezwallpaper-plan: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
