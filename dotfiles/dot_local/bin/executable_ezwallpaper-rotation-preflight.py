#!/usr/bin/env python3
"""Fail-closed guard for the opt-in ezwallpaper rotation service."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tomllib

CONFLICT_UNITS = (
    "wallpaper-daily.timer",
    "wallpaper-daily.service",
    "wallpaper-hourly.timer",
    "wallpaper-hourly.service",
    "beautify-scene-follow.timer",
    "beautify-scene-follow.service",
    "ezwallpaper-rotation.timer",
    "ezwallpaper-rotation.service",
)
GRAPHICS_ENV = (
    "WAYLAND_DISPLAY",
    "XDG_RUNTIME_DIR",
    "DBUS_SESSION_BUS_ADDRESS",
)


class PreflightError(Exception):
    """A condition makes applying a wallpaper unsafe or unavailable."""


def _automation_enabled(path: Path) -> bool:
    """Read the effective automation flag from base and GUI override TOML."""
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PreflightError(f"cannot read Noctalia config {path}: {exc}") from exc
    try:
        value = data["wallpaper"]["automation"]["enabled"]
    except (KeyError, TypeError):
        raise PreflightError(
            f"Noctalia config {path} has no wallpaper.automation.enabled"
        ) from None
    if not isinstance(value, bool):
        raise PreflightError(
            f"Noctalia config {path} wallpaper.automation.enabled is not boolean"
        )
    return value


def check_noctalia_automation(config_home: Path, state_home: Path) -> None:
    """Require automation disabled in managed config and any GUI override."""
    base = config_home / "noctalia" / "desktop.toml"
    if _automation_enabled(base):
        raise PreflightError(f"Noctalia automation is enabled in {base}")

    override = state_home / "noctalia" / "settings.toml"
    if override.exists():
        try:
            with override.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise PreflightError(
                f"cannot read Noctalia GUI override {override}: {exc}"
            ) from exc
        wallpaper = data.get("wallpaper", {})
        automation = (
            wallpaper.get("automation", {})
            if isinstance(wallpaper, dict) else None
        )
        if not isinstance(automation, dict):
            raise PreflightError(
                f"Noctalia GUI override {override} has invalid wallpaper "
                "automation data"
            )
        value = automation.get("enabled")
        if value is True:
            raise PreflightError(
                f"Noctalia GUI override enables automation in {override}"
            )
        if value is not None and not isinstance(value, bool):
            raise PreflightError(
                f"Noctalia GUI override {override} automation flag is not boolean"
            )


def check_graphical_environment() -> None:
    """Require user-manager session variables for Noctalia IPC access."""
    missing = [name for name in GRAPHICS_ENV if not os.environ.get(name)]
    if missing:
        raise PreflightError(
            "graphical session environment missing: " + ", ".join(missing)
        )


def _systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightError(f"cannot inspect user systemd state: {exc}") from exc


def _show_properties(unit: str, *properties: str) -> dict[str, str]:
    """Read an exact, complete systemd property set or fail closed."""
    result = _systemctl(
        "show", unit, *(f"--property={name}" for name in properties), "--no-pager"
    )
    if result.returncode != 0 or result.stderr.strip() or not result.stdout.strip():
        raise PreflightError(
            f"cannot establish systemd properties for {unit} (systemctl exit "
            f"{result.returncode}): {result.stderr.strip()}"
        )
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            raise PreflightError(f"malformed systemd property for {unit}: {line!r}")
        name, value = line.split("=", 1)
        if name not in properties or name in parsed:
            raise PreflightError(f"unexpected or duplicate systemd property for {unit}: {name}")
        parsed[name] = value
    if set(parsed) != set(properties):
        raise PreflightError(f"incomplete systemd properties for {unit}")
    return parsed


def _is_enabled(unit: str) -> tuple[str, int, str]:
    result = _systemctl("is-enabled", unit)
    return result.stdout.strip(), result.returncode, result.stderr.strip()


def _check_masked_daily_service() -> None:
    """Require a persistently masked daily service and a disabled, idle timer."""
    service = "wallpaper-daily.service"
    timer = "wallpaper-daily.timer"
    service_props = _show_properties(
        service, "LoadState", "ActiveState", "SubState", "UnitFileState", "Job"
    )
    timer_props = _show_properties(
        timer, "LoadState", "ActiveState", "SubState", "UnitFileState"
    )
    service_enabled = _is_enabled(service)
    timer_enabled = _is_enabled(timer)

    # systemd may retain an already-loaded failed unit after its persistent
    # mask is installed, so both documented load presentations are possible.
    # Runtime masks are intentionally not accepted as durable protection.
    service_safe = (
        service_props["LoadState"] in {"loaded", "masked"}
        and service_props["UnitFileState"] == "masked"
        and (service_props["ActiveState"], service_props["SubState"])
        in {("inactive", "dead"), ("failed", "failed")}
        and service_props["Job"] == ""
        and service_enabled == ("masked", 1, "")
        and _has_persistent_user_mask(service)
    )
    timer_safe = (
        timer_props["LoadState"] == "loaded"
        and timer_props["ActiveState"] == "inactive"
        and timer_props["SubState"] == "dead"
        and timer_props["UnitFileState"] == "disabled"
        and timer_enabled == ("disabled", 1, "")
    )
    if not service_safe or not timer_safe:
        raise PreflightError(
            "cannot establish a persistently masked, idle wallpaper-daily.service "
            "and disabled, inactive wallpaper-daily.timer"
        )


def _has_persistent_user_mask(unit: str) -> bool:
    """Check the known user unit path is a direct /dev/null mask symlink."""
    path = Path.home() / ".config/systemd/user" / unit
    try:
        return path.is_symlink() and os.readlink(path) == "/dev/null"
    except OSError:
        return False


def check_conflicting_units() -> None:
    """Reject active or enabled legacy/new rotation units."""
    for unit in CONFLICT_UNITS:
        active = _systemctl("is-active", "--quiet", unit)
        if active.returncode == 0:
            raise PreflightError(f"conflicting unit is active: {unit}")
        if active.returncode not in (3, 4):
            raise PreflightError(
                f"cannot establish activity for {unit} (systemctl exit "
                f"{active.returncode}): {active.stderr.strip()}"
            )

        if unit == "wallpaper-daily.service":
            _check_masked_daily_service()
            continue
        else:
            enabled = _systemctl("is-enabled", unit)
        state = enabled.stdout.strip()
        conflict_states = {
            "enabled", "enabled-runtime", "linked", "linked-runtime", "alias",
            "generated", "transient",
        }
        if state in conflict_states:
            raise PreflightError(f"conflicting unit is enabled ({state}): {unit}")
        # is-enabled uses nonzero statuses for several normal unit-file states;
        # only explicit disabled/not-found answers establish a safe absence.
        safe_answers = {("disabled", 1), ("not-found", 4)}
        if enabled.stderr.strip() or (state, enabled.returncode) not in safe_answers:
            raise PreflightError(
                f"cannot establish enablement for {unit} (systemctl exit "
                f"{enabled.returncode}, state {state!r}): {enabled.stderr.strip()}"
            )


def check_pool_directories(home: Path) -> None:
    """Require the expected pools to be real, non-symlink directories."""
    for relative in (
        ".local/share/wallpapers/ezwallpaper-mocha/landscape",
        ".local/share/wallpapers/ezwallpaper-mocha/portrait",
    ):
        pool = home / relative
        if pool.is_symlink() or not pool.is_dir():
            raise PreflightError(f"pool must be an existing real directory: {pool}")
        entries = list(pool.iterdir())
        if any(item.is_symlink() for item in entries):
            raise PreflightError(f"pool contains unsupported symlinks: {pool}")
        if not any(item.is_file() for item in entries):
            raise PreflightError(f"pool has no regular local image candidates: {pool}")


def run() -> None:
    """Run non-mutating checks before each scheduled apply."""
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    check_graphical_environment()
    check_noctalia_automation(config_home, state_home)
    check_conflicting_units()
    check_pool_directories(home)
    print("ezwallpaper preflight: safe to attempt hourly local rotation")


def main() -> int:
    try:
        run()
    except PreflightError as exc:
        print(f"ezwallpaper preflight: blocked: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
