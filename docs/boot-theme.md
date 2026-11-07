# Local Catppuccin Mocha Plymouth source

This repository includes a source-only copy of the Catppuccin Plymouth theme at
`dotfiles/dot_local/share/beautify/plymouth-local-catppuccin-mocha/`. It contains
the Plymouth theme descriptor and image assets, the upstream MIT license notice,
and `source-manifest.toml` with the upstream repository, pinned revision, license
identifier, and SHA-256 digests for the distributed assets and license.

The manifest identifies
[`catppuccin/plymouth`](https://github.com/catppuccin/plymouth) at revision
`198eba2071d80e4a23b8f51a5859e8f4acf8de6c`. Preserve the included `LICENSE`
when redistributing these files. The recorded digests are integrity checks for
this copy; they are not a signature or an independent guarantee about upstream
history.

## Scope and limits

These files are source material only. Their presence in the chezmoi source tree
does not install or select the theme, alter Plymouth configuration, regenerate
an initramfs, or prove compatibility with any particular distribution, graphics
driver, boot chain, or machine. No successful installation or boot test is
claimed. There are no lifecycle installers or service changes in this source
subset.

The `.plymouth` descriptor refers to the conventional
`/usr/share/plymouth/themes/local-catppuccin-mocha` asset directory. That is a
theme-runtime reference, not an instruction executed by this repository. Any
manual deployment is an operator-managed system change and must be reviewed and
validated for the target system separately; this project does not perform it.

## Offline integrity test

From the repository root, run:

```sh
python3 -m unittest tests.test_plymouth_local_catppuccin_mocha
```

The test uses only Python's standard library and local files. It checks the
pinned metadata, that manifest entries are safe basenames resolving to regular
non-symlink files, each listed asset digest, and the license notice digest. It
does not download, install, or invoke Plymouth or privileged system tools.
