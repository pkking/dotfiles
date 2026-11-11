"""Sanitized producer-shaped ezwallpaper v1 fixtures (no real paths or IDs).

Pinned serde Option fields for present secondary outputs may independently be
null; the outputs map itself is sparse when a secondary output was not saved.
"""
from __future__ import annotations

import hashlib

PROFILE_OUTPUTS = ("DP-1", "HDMI-A-1")

def content_id(label: str) -> str:
    return "sha256:" + hashlib.sha256(("fixture:" + label).encode("ascii")).hexdigest()

def profile_json(home: str) -> dict:
    return {
        "schema_version": 1,
        "owner": "ezwallpaper",
        "outputs": [
            {"name": "DP-1", "dir": home + "/landscape", "recursive": False},
            {"name": "HDMI-A-1", "dir": home + "/portrait", "recursive": False},
        ],
    }

def state_entry(label: str, epoch: int = 17, *, remaining: list[str] | None = None, cycle: int = 3) -> dict:
    return {
        "schema_version": 1,
        "last_epoch": epoch,
        "last_content_id": content_id(label),
        "remaining": list(remaining if remaining is not None else [content_id(label + "-queued")]),
        "cycle": cycle,
    }

def state_json(profile: str, *, portrait_first: bool = False, primary_id: str | None = None) -> dict:
    entries = {
        "DP-1": state_entry("landscape"),
        "HDMI-A-1": state_entry("portrait"),
    }
    if primary_id is not None:
        entries["DP-1"]["last_content_id"] = primary_id
    if portrait_first:
        entries = {name: entries[name] for name in ("HDMI-A-1", "DP-1")}
    return {"schema_version": 1, "profile": profile, "outputs": entries}
