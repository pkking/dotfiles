"""Offline contract checks for the bundled Mocha wallpaper assets/config."""
from __future__ import annotations

import re
import struct
import tomllib
import unittest
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "dotfiles/dot_local/share/wallpapers/ezwallpaper-mocha"
TEMPLATE = ROOT / "dotfiles/dot_config/noctalia/desktop.toml.tmpl"
DOC = ROOT / "docs/mocha-wallpaper-assets.md"
B_PROFILE = ROOT / "dotfiles/dot_config/ezwallpaper/rotation.json.tmpl"
B_PREFLIGHT = ROOT / "dotfiles/dot_local/bin/executable_ezwallpaper-rotation-preflight.py"
EXPECTED = {
    "landscape/mocha-flat-landscape.png": (3840, 2160),
    "portrait/mocha-flat-portrait.png": (2160, 3840),
}


def inspect_png(path: Path) -> tuple[int, int]:
    """Validate PNG chunks/CRCs and fully decompress non-interlaced RGB data."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} is not a PNG")
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    saw_end = False
    while pos < len(data):
        if pos + 12 > len(data):
            raise AssertionError(f"truncated PNG chunk in {path}")
        length = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4 : pos + 8]
        end = pos + 8 + length
        if end + 4 > len(data):
            raise AssertionError(f"truncated PNG payload in {path}")
        payload = data[pos + 8 : end]
        expected_crc = struct.unpack_from(">I", data, end)[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise AssertionError(f"bad PNG CRC for {kind!r} in {path}")
        if kind == b"IHDR":
            if length != 13 or width is not None:
                raise AssertionError("invalid or repeated PNG IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression or filtering or interlace:
                raise AssertionError("only non-interlaced standard PNGs are supported")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if length:
                raise AssertionError("invalid PNG IEND")
            saw_end = True
            pos = end + 4
            break
        pos = end + 4
    if not saw_end or pos != len(data) or width is None:
        raise AssertionError(f"missing IEND/IHDR or trailing bytes in {path}")
    if bit_depth != 8 or color_type != 2:
        raise AssertionError(f"expected 8-bit RGB PNG: depth={bit_depth}, type={color_type}")
    pixels = zlib.decompress(compressed)
    if len(pixels) != height * (1 + width * 3):
        raise AssertionError(f"unexpected decompressed scanline size in {path}")
    return width, height


class MochaWallpaperContractTests(unittest.TestCase):
    def test_assets_are_real_decodable_images_at_expected_dimensions(self) -> None:
        for relative, dimensions in EXPECTED.items():
            path = ASSETS / relative
            self.assertTrue(path.is_file(), f"missing referenced asset: {relative}")
            self.assertFalse(path.is_symlink(), f"asset must be a regular file: {relative}")
            self.assertEqual(inspect_png(path), dimensions)

    def test_svg_sources_are_self_contained_and_parse(self) -> None:
        for relative in (
            "source/mocha-flat-landscape.svg",
            "source/mocha-flat-portrait.svg",
        ):
            root = ET.parse(ASSETS / relative).getroot()
            self.assertEqual(root.tag.rsplit("}", 1)[-1], "svg")
            for element in root.iter():
                self.assertNotIn(element.tag.rsplit("}", 1)[-1], {"script", "image"})
                for key, value in element.attrib.items():
                    if key.rsplit("}", 1)[-1] in {"href", "src"}:
                        self.assertFalse(re.match(r"^[a-z]+:", value, re.I), value)

    def test_rendered_wallpaper_config_references_only_supplied_mocha_paths(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        block = template.split("[wallpaper]\n", 1)[1].split("\n[backdrop]\n", 1)[0]
        paths = re.findall(r'path = "\{\{ \.chezmoi\.homeDir \}\}/\.local/share/wallpapers/([^\"]+)"', block)
        self.assertEqual(paths.count("ezwallpaper-mocha/landscape/mocha-flat-landscape.png"), 2)
        self.assertEqual(paths.count("ezwallpaper-mocha/portrait/mocha-flat-portrait.png"), 1)
        directories = re.findall(r'directory = "\{\{ \.chezmoi\.homeDir \}\}/\.local/share/wallpapers/([^\"]+)"', block)
        self.assertEqual(set(directories), {"ezwallpaper-mocha/landscape", "ezwallpaper-mocha/portrait"})
        for relative in paths:
            self.assertTrue((ROOT / "dotfiles/dot_local/share/wallpapers" / relative).is_file())
        self.assertIn("per_monitor_directories = true", block)
        self.assertIn("[wallpaper.monitor.DP-1]", block)
        self.assertIn("[wallpaper.monitor.HDMI-A-1]", block)
        self.assertIn("[wallpaper.automation]\nenabled = false", block)

    def test_docs_disclose_static_default_and_b_prerequisites(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        profile = B_PROFILE.read_text(encoding="utf-8")
        preflight = B_PREFLIGHT.read_text(encoding="utf-8")
        for path in (
            ".local/share/wallpapers/landscape",
            ".local/share/wallpapers/portrait",
        ):
            self.assertIn(path, profile)
        for path in (
            ".local/share/wallpapers/ezwallpaper-mocha/landscape",
            ".local/share/wallpapers/ezwallpaper-mocha/portrait",
        ):
            self.assertIn(path, preflight)
        self.assertIn("~/.local/share/wallpapers/{landscape,portrait}", doc)
        self.assertIn(
            "~/.local/share/wallpapers/ezwallpaper-mocha/{landscape,portrait}",
            doc,
        )
        self.assertIn("hard-coded", doc)
        self.assertIn(
            "does not make the guard support arbitrary pool paths",
            doc,
        )
        for phrase in (
            "remain static",
            "native automation",
            "ezwallpaper-rotation-b.md",
            "private/local",
            "ezwallpaper-rotation",
            "wallpapers/{landscape,portrait}",
            "native automation is a distinct alternative",
            "cannot prove",
        ):
            self.assertIn(phrase, doc)

    def test_rendered_toml_wallpaper_tables_parse_and_defaults_stay_off(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        rendered = template.replace("{{ .chezmoi.homeDir }}", "/home/test")
        config = tomllib.loads(rendered)
        wallpaper = config["wallpaper"]
        self.assertEqual(wallpaper["directory"], "/home/test/.local/share/wallpapers/ezwallpaper-mocha/landscape")
        self.assertTrue(wallpaper["per_monitor_directories"])
        self.assertEqual(wallpaper["monitors"]["DP-1"]["path"], "/home/test/.local/share/wallpapers/ezwallpaper-mocha/landscape/mocha-flat-landscape.png")
        self.assertEqual(wallpaper["monitors"]["HDMI-A-1"]["path"], "/home/test/.local/share/wallpapers/ezwallpaper-mocha/portrait/mocha-flat-portrait.png")
        self.assertFalse(wallpaper["automation"]["enabled"])


if __name__ == "__main__":
    unittest.main()
