#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

repo="${REPO_NAME:-${GITHUB_REPOSITORY##*/}}"
branch="${GITHUB_REF_NAME:-main}"
tag="${RELEASE_TAG:-packages}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git config user.name 'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'

shopt -s nullglob
built=()
for d in artifacts/pkg-*; do
  [ -d "$d" ] || continue
  built+=("${d#artifacts/pkg-}")
done
if [ ${#built[@]} -eq 0 ]; then
  echo 'no built packages; nothing to publish'
  exit 0
fi

if [ -n "${GPG_PRIVATE_KEY:-}" ]; then
  export GNUPGHOME="$HOME/.gnupg"
  mkdir -p "$GNUPGHOME"
  chmod 700 "$GNUPGHOME"
  printf '%s\n' "$GPG_PRIVATE_KEY" | gpg --batch --import
  export SIGN=1
fi

gh release download "$tag" --repo "$GITHUB_REPOSITORY" \
  --pattern "$repo.db.tar.zst" --dir "$work" --clobber 2>/dev/null || true

python -m pkgbot publish --work "$work" --artifacts artifacts --repo "$repo" \
  --release-tag "$tag" --gh-repo "$GITHUB_REPOSITORY"

python -m pkgbot take "${built[@]}"

git add state/oldver
if ! git diff --cached --quiet; then
  git commit -m 'chore: update build state'
  git pull --rebase origin "$branch"
  git push origin "HEAD:$branch"
fi
