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

if [ "${DEBUG_PACKAGES:-0}" != 1 ]; then
  # makepkg builds -debug packages by default; opt out unless DEBUG_PACKAGES=1
  export HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"
  conf="${XDG_CONFIG_HOME:-$HOME/.config}/pacman/makepkg.conf"
  mkdir -p "$(dirname "$conf")"
  cat > "$conf" <<'EOF'
opts=()
for opt in "${OPTIONS[@]}"; do
  [ "$opt" = debug ] || opts+=("$opt")
done
OPTIONS=("${opts[@]}")
unset opt opts
EOF
fi

makepkg --syncdeps --noconfirm --cleanbuild
