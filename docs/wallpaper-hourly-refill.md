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

Each response is bounded to 20 MiB and HTTP operations time out. Redirects are
validated before a follow-up request: HTTPS, exact `www.bing.com` authority with
no custom port or userinfo, and only the expected API or narrowly shaped UHD
image path are accepted. Downloaded data must be a JPEG that ImageMagick
`identify` can decode before same-directory atomic publication. The decoder has
a 15-second timeout, memory/map/disk/thread/area limits, and explicit maximum
width, height, and pixel count. A nonblocking lock serializes attempts. Directory,
lock, temporary-image, and destination operations are anchored to no-follow file
descriptors; a replaced pool path fails closed. This job never removes existing
images: it accepts at most 12 matching owned image files and refuses acquisition
when full, requiring manual removal of an old owned image before resuming.
Unrelated pool files are not followed, replaced, or removed. Network, parse,
decode, capacity, and pre-publication filesystem failures leave existing files
available and remove any temporary download. No manifest or automatic retention
cleanup is used, so publication has one atomic image-file commit point. The
runtime requires Python 3 and ImageMagick's `identify` executable. Errors are
generic and do not print response URLs or bodies.

To inspect before any separately authorized deployment, use a scoped
`chezmoi diff` for the refill script, unit pair, and this document. Do not run
`chezmoi apply`, start/enable the timer, or perform a live download as part of
review. Offline behavior is covered by `tests/test_wallpaper_hourly_refill.py`.
