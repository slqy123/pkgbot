# pkgbot

An automatic Arch Linux package repository builder that runs entirely on GitHub
Actions. It checks upstream versions, updates PKGBUILDs, builds packages in a
clean Arch container, signs them, and publishes a `pacman` repository to the
`gh-pages` branch.

## Usage

Users add the published repository to `/etc/pacman.conf`:

```
[<repo-name>]
Server = https://github.com/<owner>/<repo>/releases/download/<tag>
Server = https://<owner>.github.io/<repo>/$arch
```

Packages are uploaded as assets of a single fixed-tag GitHub Release
(`<tag>`, default `packages`); the repository database and the public signing
key live on the `gh-pages` branch, so GitHub Pages must be enabled. The first
`Server` line serves packages, the second the database. Import the public key
(`<repo-name>.gpg`) with `pacman-key --add` and `pacman-key --lsign-key`.

## Adding a package

Create `packages/<pkgbase>/` containing the `PKGBUILD` and a `pkg.yaml`:

```yaml
strategy: github-release
update_on:
  - source: github
    github: owner/project
    use_latest_release: true
    prefix: v
```

`update_on` entries are passed to [nvchecker](https://nvchecker.readthedocs.io/)
verbatim. `strategy` selects how the PKGBUILD is kept up to date:

| strategy | upstream | PKGBUILD update |
| --- | --- | --- |
| `aur` | `source: aur` | pull the AUR PKGBUILD and its files |
| `github-release` | any nvchecker source | set `pkgver`, reset `pkgrel`, refresh checksums |
| `vcs` | `source: vcs` | run `pkgver()` and bump `pkgrel` when unchanged |
| `none` | — | never updated automatically |

`strategy: none` packages are built only when their directory is changed or when
the workflow is dispatched manually.

Optional `repo_depends` lists other packages in this repository that must be
available when building.

## Configuration

Repository secrets:

- `GPG_PRIVATE_KEY` — armored private key used to sign packages and the database.
- `SIGNING_KEY` — key id or email of the signing key (optional; defaults to the
  key's own identity).

Set `REPO_NAME` to override the repository name, which otherwise defaults to the
GitHub repository name, and `RELEASE_TAG` to change the fixed release tag
(default `packages`).

## Running locally

On an Arch system with `nvchecker`, `python-yaml` and `python-tomli-w` installed:

```bash
python -m pkgbot check                        # validate configuration
python -m pkgbot detect --packages <pkgbase>  # check upstream, update PKGBUILD
bash scripts/build.sh <pkgbase>               # build in the current environment
```

## Workflows

- `update.yml` — scheduled (daily) and manual version check, matrix build, and
  publish to the fixed-tag release and `gh-pages`.
- `check.yml` — validates package configuration on pull requests.
