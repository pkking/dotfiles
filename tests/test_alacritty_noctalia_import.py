from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AlacrittyNoctaliaImportContract(unittest.TestCase):
    def test_noctalia_import_follows_rose_pine(self):
        path = ROOT / "dotfiles/dot_config/alacritty/private_alacritty.toml"
        config = tomllib.loads(path.read_text())
        imports = config["general"]["import"]
        self.assertEqual(
            imports,
            [
                "~/.config/alacritty/themes/rose-pine.toml",
                "~/.config/alacritty/themes/noctalia.toml",
            ],
        )

    def test_noctalia_enables_only_builtin_alacritty_template(self):
        path = ROOT / "dotfiles/dot_config/noctalia/desktop.toml.tmpl"
        config = tomllib.loads(path.read_text().replace("{{ .chezmoi.homeDir }}", "/home/test"))
        self.assertTrue(config["theme"]["templates"]["enable_builtin_templates"])
        self.assertEqual(config["theme"]["templates"]["builtin_ids"], ["alacritty"])


if __name__ == "__main__":
    unittest.main()
