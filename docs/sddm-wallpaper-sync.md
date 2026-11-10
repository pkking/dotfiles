# Optional SDDM wallpaper cache synchronization

This feature is an unprivileged, opt-in follow-up to the existing `ezwallpaper-rotate.service`. It publishes only the current DP-1 image when the rotation owner reports `Result=success`/status 0, the committed `rotation-v1.json` identity matches the exact source bytes, and a fresh `noctalia msg wallpaper-get DP-1` still returns that source path. The state ID is confirmed to be SHA-256 of raw file bytes (`ezwallpaper hash <fixture>`). This is path/state corroboration, **not pixel-level visual verification**.

## Defaults and prerequisites

The managed policy is `~/.config/sddm-wallpaper-sync/policy.json`; it is disabled by default. No timer, auto-enable, lifecycle installer, root publisher, or change to the existing rotation unit is provided. Install ImageMagick (`magick`) using the host's reviewed package-management procedure; it is used unprivileged with fixed arguments and bounded resource/time limits to normalize approved PNG/JPEG into one static PNG. ImageMagick policy must disable external delegates for this use. The only input pool is the configured non-recursive DP-1 landscape directory. The source/user cache writer intentionally has no elevated privileges.

## One-time manual root setup (not performed by chezmoi)

After separately approving deployment, verify that group `sddm` exists and that the SDDM account can traverse `/var/cache` and read group-readable files. As an administrator, create `/var/cache/sddm-wallpaper-sync` as root:root mode 0755, then its numeric-UID leaf as `<desktop-uid>:sddm` mode 2750. Do not make user-writable parent directories, weaken HOME permissions, or change the theme yet. The fixed program destination is `/var/cache/sddm-wallpaper-sync/<uid>`; there is no production destination override. If an existing path has unexpected owner, group, or mode, stop and investigate rather than changing it in place.

## Opt-in and first publish

1. Review the exact landscape pool and privacy implications. Enable policy only after that approval (`enabled: true`), preserving its schema and paths.
2. Manually start the user unit once in a valid graphical session and inspect its result/log. Do not manually rotate wallpaper to test this feature.
3. Only after a valid `current.png` exists and its ownership/mode are verified, separately back up the SDDM user's `theme.conf.user`. In the `[General]` group merge only `CustomBackground=true` and `Background=/var/cache/sddm-wallpaper-sync/<uid>/current.png`. Preserve all unknown keys and existing theme selection. Do not point the theme at the cache before a successful first publish. Existing theme `cache: true` behavior means a running greeter may retain its prior image; only a fresh greeter instance can be expected to load the new path. Do not promise hot reload.
4. For automatic follow-up, create a *manual* user drop-in at `~/.config/systemd/user/ezwallpaper-rotate.service.d/10-sddm-sync.conf` containing:

   ```ini
   [Unit]
   OnSuccess=sddm-wallpaper-sync.service
   ```

   Reload the user manager only during an approved deployment window. `OnSuccess` is opt-in, follows a successful owner unit, and does not alter that unit's result if sync fails. Do not enable a timer or make a root service.

## Rollback

Remove the optional drop-in and reload the user manager during an approved window; disable policy (`enabled:false`). Restore the saved `theme.conf.user` background values, preserving other configuration. The last cache image may remain until an administrator removes the known `current.png` and leaf after confirming ownership; no recursive cleanup is needed. Do not remove parent cache paths or unrelated files.

## Failure and durability contract

Disabled policy is a no-op (does not inspect Noctalia/cache). Missing provisioning, missing session IPC, failed/unknown owner, invalid/stale state, source change, readback mismatch, invalid/oversized image, lock contention, or any pre-rename write/fsync error fails closed and preserves the prior image. Same-directory exclusive temporary files are cleaned only when created by this invocation. Atomic rename is the commit point: if directory fsync fails after rename, the new image is already visible and is reported as **committed with durability uncertain**, not falsely described as rolled back. The cache keeps one current image and is never recursively cleaned. The user may replace/deny service to their own cache; the SDDM account receives only the published static file. Image path equality cannot establish rendered pixels.

## Remaining acceptance gates

This source change does not provision the cache, change theme config, install packages, activate units, restart SDDM, log out, or verify a greeter. Before deployment/release, independently review path/race defenses, validate SDDM group/config precedence, perform the approved first publish and a human visual check in a separately authorized window. The existing Catppuccin theme's `theme.conf.user` may override bundled background defaults; keep its other keys unchanged.
