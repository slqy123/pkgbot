#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

repo="${REPO_NAME:-${GITHUB_REPOSITORY##*/}}"
branch="${GITHUB_REF_NAME:-main}"
pages="$(mktemp -d)"
trap 'git worktree remove --force "$pages" 2>/dev/null || true; rm -rf "$pages"' EXIT

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

if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
  git fetch origin gh-pages
  git worktree add --detach "$pages" origin/gh-pages
else
  git worktree add --detach "$pages"
  git -C "$pages" checkout --orphan gh-pages
  git -C "$pages" rm -rf . >/dev/null 2>&1 || true
fi

if [ -n "${GPG_PRIVATE_KEY:-}" ]; then
  export GNUPGHOME="$HOME/.gnupg"
  mkdir -p "$GNUPGHOME"
  chmod 700 "$GNUPGHOME"
  printf '%s\n' "$GPG_PRIVATE_KEY" | gpg --batch --import
  export SIGN=1
fi

python -m pkgbot publish --pages "$pages" --artifacts artifacts --repo "$repo" \
  --release-tag "${RELEASE_TAG:-}" --gh-repo "$GITHUB_REPOSITORY"

git -C "$pages" add -A
if ! git -C "$pages" diff --cached --quiet; then
  git -C "$pages" commit -m "publish: ${built[*]}"
  git -C "$pages" push origin "HEAD:gh-pages"
fi

python -m pkgbot take "${built[@]}"

git add state/oldver
if ! git diff --cached --quiet; then
  git commit -m 'chore: update build state'
  git pull --rebase origin "$branch"
  git push origin "HEAD:$branch"
fi
