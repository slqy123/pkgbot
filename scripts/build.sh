#!/usr/bin/env bash
set -euo pipefail

pkg="${1:?usage: build.sh <pkgbase>}"
cd "packages/$pkg"

if grep -q '^validpgpkeys=' PKGBUILD; then
  bash -s <<'EOF' || true
set +u
. /usr/share/makepkg/util.sh 2>/dev/null || true
. ./PKGBUILD
for key in "${validpgpkeys[@]}"; do
  [ -n "$key" ] || continue
  timeout 60 gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys "$key" || true
done
EOF
fi

makepkg --syncdeps --noconfirm --cleanbuild
