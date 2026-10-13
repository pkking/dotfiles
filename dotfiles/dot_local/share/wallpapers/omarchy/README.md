# Omarchy sunset lake wallpaper

Source: Omarchy `themes/tokyo-night/backgrounds/4-sunset-lake.webp`.
Pinned upstream commit: `492b8837deea69663c7a5418871f07ed075a9686`.

https://github.com/omacom/omarchy/blob/492b8837deea69663c7a5418871f07ed075a9686/themes/tokyo-night/backgrounds/4-sunset-lake.webp

The original image includes the artist's signature, Louis Coyle. Credit remains with the original artist; cropping does not confer ownership or establish a separate artwork license. Consult upstream and the artist for redistribution rights.

- `sunset-lake-original.webp`: unchanged upstream image, 7680×3215.
- `sunset-lake-4k.webp`: centre-cropped 3840×2160 wallpaper.
- `sunset-lake-portrait.webp`: sunset-centred 1080×1920 crop (not a stretched landscape).

Derived with ImageMagick:

```bash
magick sunset-lake-original.webp -resize '3840x2160^' -gravity center -extent 3840x2160 -quality 92 sunset-lake-4k.webp
magick sunset-lake-original.webp -crop 1808x3215+3380+0 +repage -resize 1080x1920 -quality 92 sunset-lake-portrait.webp
```

Desktop configuration and first-apply instructions: `docs/niri-noctalia.md` in the dotfiles repository.
