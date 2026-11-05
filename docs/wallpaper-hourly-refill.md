# Optional hourly wallpaper pool refill

`wallpaper-hourly-refill.timer` is an **opt-in acquisition timer**. It is not
an image renderer or rotation scheduler. The merged `ezwallpaper-rotation`
integration remains the only opt-in renderer/scheduler; this refill neither
invokes Noctalia/ezwallpaper nor writes their configuration or state. No unit is
enabled by these source files.

The job fetches one Bing UHD JPEG over HTTPS and adds it to
`~/.local/share/wallpapers/landscape/hourly-refill/`. This is a dedicated child
of the recursive landscape pool in `~/.config/ezwallpaper/rotation.json`, so
these pictures are eligible for the existing profile without changing it.
Only landscape is populated; existing portrait content is untouched. It does
not use, prune, or change the separate `ezwallpaper-mocha` non-recursive pool.

Each response is bounded to 20 MiB and HTTP operations time out. The provider
path is constrained to Bing HTTPS, and downloaded data must be a JPEG that
ImageMagick `identify` can decode before same-directory atomic publication.
A nonblocking lock serializes attempts. A private ownership manifest limits
retention to the 12 newest names created by this job; unrelated pool files and
symlinks are not followed or removed. On network, parse, or decode failure the
existing pool is left available and the temporary download is removed. The
runtime therefore requires Python 3, curl-free Python HTTPS access, and
ImageMagick's `identify` executable. Errors are intentionally generic and do
not print response URLs or bodies.

To inspect before any separately authorized deployment, use a scoped
`chezmoi diff` for the refill script, unit pair, and this document. Do not run
`chezmoi apply`, start/enable the timer, or perform a live download as part of
review. Offline behavior is covered by `tests/test_wallpaper_hourly_refill.py`.
