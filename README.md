# pkgbot

An Arch Linux package repository built and published automatically by GitHub
Actions.

## Usage

Add the repository to `/etc/pacman.conf`:

```
[pkgbot]
Server = https://github.com/slqy123/pkgbot/releases/download/packages
```

Packages, the repository database and the signing key are all assets of a
single fixed-tag GitHub Release. Import and locally sign the repository key
once, so `pacman` trusts the signed packages:

```bash
curl -fsSLO https://github.com/slqy123/pkgbot/releases/download/packages/pkgbot.gpg
sudo pacman-key --add pkgbot.gpg
sudo pacman-key --lsign-key "$(gpg --show-keys --with-colons pkgbot.gpg | awk -F: '/^fpr/{print $10; exit}')"
```

Then install packages:

```bash
sudo pacman -Sy
sudo pacman -S <package>
```

---

# pkgbot (the builder)

The tool that produces the repository above. It runs entirely on GitHub
Actions: it checks upstream versions with
[nvchecker](https://nvchecker.readthedocs.io/), updates PKGBUILDs, builds each
package in a clean Arch container, signs the results, and publishes them as
assets of a single fixed-tag GitHub Release.

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

`update_on` entries are passed to nvchecker verbatim. `strategy` selects how the
PKGBUILD is kept up to date:

| strategy | upstream | PKGBUILD update |
| --- | --- | --- |
| `aur` | `source: aur` | pull the AUR PKGBUILD and its files |
| `github-release` | any nvchecker source | set `pkgver`, reset `pkgrel`, refresh checksums |
| `vcs` | `source: git` with `use_commit: true` | run `pkgver()` and bump `pkgrel` when unchanged |
| `none` | — | never updated automatically |

`strategy: none` packages are built only when their directory is changed or when
the workflow is dispatched manually.

Optional `repo_depends` lists other packages in this repository that must be
available when building.

## GPG signing key

Every package and the repository database are signed. Create a dedicated,
passphrase-less key for CI in a temporary keyring, so it never touches your
personal one:

```bash
export GNUPGHOME=$(mktemp -d)
chmod 700 "$GNUPGHOME"

cat > /tmp/ci-key.params <<'EOF'
%no-protection
Key-Type: eddsa
Key-Curve: ed25519
Name-Real: pkgbot signing
Name-Email: pkgbot@example.com
Expire-Date: 0
%commit
EOF

gpg --batch --gen-key /tmp/ci-key.params
gpg --list-secret-keys --with-colons | awk -F: '/^fpr/{print $10; exit}'
gpg --armor --export-secret-keys pkgbot@example.com > /tmp/ci-key.asc
```

Register the key as repository secrets:

```bash
gh secret set GPG_PRIVATE_KEY < /tmp/ci-key.asc
gh secret set SIGNING_KEY --body 'pkgbot@example.com'
```

Then delete the temporary material — a passphrase-less secret key must not leak:

```bash
gpgconf --kill gpg-agent 2>/dev/null
rm -rf "$GNUPGHOME" /tmp/ci-key.asc /tmp/ci-key.params
```

The workflow imports `GPG_PRIVATE_KEY`, signs every package and both database
files, and uploads the public key to the Release as `<repo-name>.gpg`. Consumers
import that file as shown in [Usage](#usage). `SIGNING_KEY` is optional and
defaults to the only key in the keyring.

## Configuration

- `REPO_NAME` — repository name; defaults to the GitHub repository name.
- `RELEASE_TAG` — tag of the Release that holds packages; defaults to `packages`.
- `GPG_PRIVATE_KEY`, `SIGNING_KEY` — see [GPG signing key](#gpg-signing-key).

## Running locally

On an Arch system with `nvchecker`, `python-yaml` and `python-tomli-w` installed:

```bash
python -m pkgbot check                        # validate configuration
python -m pkgbot detect --packages <pkgbase>  # check upstream, update PKGBUILD
bash scripts/build.sh <pkgbase>               # build in the current environment
```

## Workflows

- `update.yml` — scheduled (daily) and manual version check, matrix build, and
  publish to the fixed-tag Release.
- `check.yml` — validates package configuration on pull requests.
