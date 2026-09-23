from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import Package, VCS_SUFFIXES

AUR_URL = 'https://aur.archlinux.org/{}.git'
AUR_SKIP = {'.git', '.SRCINFO', '.AURINFO', '.gitignore'}


def _run(cmd: list[str], cwd: Path) -> None:
  print('+', ' '.join(cmd), f'(in {cwd})', flush=True)
  subprocess.run(cmd, cwd=cwd, check=True)


def _srcinfo(path: Path) -> dict[str, str]:
  out = subprocess.run(
    ['makepkg', '--printsrcinfo'], cwd=path,
    check=True, capture_output=True, text=True,
  ).stdout
  info: dict[str, str] = {}
  for line in out.splitlines():
    if ' = ' in line:
      k, _, v = line.partition(' = ')
      info[k.strip()] = v.strip()
  return info


def _pkgver_pkgrel(path: Path) -> tuple[str, str]:
  info = _srcinfo(path)
  return info['pkgver'], info['pkgrel']


def _write_srcinfo(path: Path) -> None:
  out = subprocess.run(
    ['makepkg', '--printsrcinfo'], cwd=path,
    check=True, capture_output=True,
  ).stdout
  (path / '.SRCINFO').write_bytes(out)


def _next_pkgrel(rel: str) -> str:
  return str(int(str(rel).split('.')[0]) + 1)


def update_pkgver(pkg: Package, newver: str) -> bool:
  pkgver, pkgrel = _pkgver_pkgrel(pkg.path)
  build_file = pkg.path / 'PKGBUILD'
  lines = build_file.read_text().splitlines(keepends=True)
  for i, line in enumerate(lines):
    if line.startswith('pkgver='):
      if pkgver != newver:
        lines[i] = f'pkgver={newver}\n'
    elif line.startswith('pkgrel='):
      lines[i] = 'pkgrel=1\n' if pkgver != newver else f'pkgrel={_next_pkgrel(pkgrel)}\n'
  build_file.write_text(''.join(lines))
  _run(['updpkgsums'], cwd=pkg.path)
  return True


def _clean_generated(path: Path, before: set[str]) -> None:
  for item in path.iterdir():
    if item.name not in before and item.name != '.SRCINFO':
      shutil.rmtree(item) if item.is_dir() else item.unlink()


def update_vcs(pkg: Package) -> bool:
  before = {p.name for p in pkg.path.iterdir()}
  try:
    pkgver, pkgrel = _pkgver_pkgrel(pkg.path)
    _run(['makepkg', '-od', '--noprepare', '-A'], cwd=pkg.path)
    new_pkgver, _ = _pkgver_pkgrel(pkg.path)
    if new_pkgver == pkgver:
      build_file = pkg.path / 'PKGBUILD'
      text = re.sub(r'(?m)^pkgrel=.*$', f'pkgrel={_next_pkgrel(pkgrel)}', build_file.read_text(), count=1)
      build_file.write_text(text)
    _write_srcinfo(pkg.path)
    return True
  finally:
    _clean_generated(pkg.path, before)


def update_aur(pkg: Package) -> bool:
  name = pkg.update_on[0].get('aur') or pkg.pkgbase
  with tempfile.TemporaryDirectory() as td:
    _run(['git', 'clone', '--depth=1', AUR_URL.format(name), name], cwd=Path(td))
    src = Path(td) / name
    for item in src.iterdir():
      if item.name in AUR_SKIP:
        continue
      dest = pkg.path / item.name
      if item.is_dir():
        shutil.copytree(item, dest, dirs_exist_ok=True)
      else:
        shutil.copy2(item, dest)
  if name.endswith(VCS_SUFFIXES):
    update_vcs(pkg)
  return True


def update_package(pkg: Package, newver: str | None) -> bool:
  if pkg.strategy == 'aur':
    return update_aur(pkg)
  if pkg.strategy == 'github-release':
    if not newver:
      return False
    return update_pkgver(pkg, newver)
  if pkg.strategy == 'vcs':
    return update_vcs(pkg)
  return False
