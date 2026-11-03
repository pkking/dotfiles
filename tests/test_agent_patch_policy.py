"""No-network regression tests for the publisher's file-path trust boundary."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

POLICY = Path(__file__).resolve().parents[1] / 'scripts/agent_patch_policy.py'
spec = importlib.util.spec_from_file_location('agent_patch_policy', POLICY)
policy = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(policy)


class PatchPolicyTests(unittest.TestCase):
    def test_allows_product_test_and_document_changes(self) -> None:
        policy.validate_names(['README.md', 'dotfiles/dot_config/fixture',
                               'scripts/new-helper.py', 'tests/test_feature.py', 'docs/usage.md'])

    def test_rejects_control_plane_and_sensitive_paths(self) -> None:
        for name in ('.github/workflows/test.yml', 'AGENTS.md', 'CLAUDE.md',
                     'scripts/ci_quality.py', 'scripts/agent_patch_policy.py',
                     'dotfiles/private_dot_ssh/id', 'dotfiles/encrypted_token.age',
                     'dotfiles/dot_config/private_key', 'dotfiles/secret.age',
                     '.git/config', 'outside-file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.validate_names([name])

    def test_rejects_missing_or_excessive_patch(self) -> None:
        for paths in ([], [f'docs/file{i}.md' for i in range(policy.MAX_FILES + 1)]):
            with self.assertRaises(ValueError):
                policy.validate_names(paths)


if __name__ == '__main__':
    unittest.main()
