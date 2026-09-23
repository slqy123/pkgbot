from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import tomli_w

from . import release
from .config import NEWVER, NVCHECKER_TOML, OLDVER, PACKAGES_DIR, load_packages
from .detect import effective_config


def _run(cmd: list[str], cwd: Path | None = None) -> None:
  print('+', ' '.join(str(c) for c in cmd), flush=True)
  subprocess.run(cmd, cwd=cwd, check=True)


def sign_enabled() -> bool:
  return os.environ.get('SIGN') == '1' or bool(os.environ.get('SIGNING_KEY'))


def _sign(path: Path) -> None:
  cmd = ['gpg', '--batch', '--yes', '--detach-sign']
  if key := os.environ.get('SIGNING_KEY'):
    cmd += ['--local-user', key]
  cmd.append(str(path))
  _run(cmd)


def _db_filenames(db: Path) -> set[str]:
  out = subprocess.check_output(
    ['bsdtar', '-xOf', str(db), '--include', '*/desc'], text=True,
  )
  return {line.strip() for line in out.splitlines() if line.strip().endswith('.pkg.tar.zst')}


def take(names: list[str]) -> None:
  by_name = {p.pkgbase: p for p in load_packages()}
  names = [n for n in names if n in by_name and by_name[n].update_on]
  if not names:
    return
  conf = effective_config(load_packages())
  conf['__config__'] = {'oldver': str(OLDVER), 'newver': str(NEWVER)}
  NVCHECKER_TOML.write_bytes(tomli_w.dumps(conf).encode())
  _run(['nvtake', '--ignore-nonexistent', '-c', str(NVCHECKER_TOML), *names], cwd=PACKAGES_DIR)


def publish(
  pages: Path,
  artifacts: Path,
  repo: str,
  release_tag: str | None = None,
  gh_repo: str | None = None,
) -> None:
  pages = Path(pages).resolve()
  arch_dir = pages / 'x86_64'
  arch_dir.mkdir(parents=True, exist_ok=True)
  signing = sign_enabled()

  added = []
  for pkg in sorted(Path(artifacts).rglob('*.pkg.tar.zst')):
    if signing:
      _sign(pkg)
    added.append(pkg)

  db = arch_dir / f'{repo}.db.tar.zst'
  if added:
    _run(['repo-add', str(db), *[str(p) for p in added]])
    for old in arch_dir.glob('*.old'):
      old.unlink()

  for ext in ('db', 'files'):
    real = arch_dir / f'{repo}.{ext}.tar.zst'
    if not real.exists():
      continue
    copy = arch_dir / f'{repo}.{ext}'
    copy.unlink(missing_ok=True)
    shutil.copy2(real, copy)
    if signing:
      _sign(copy)

  if signing:
    out = subprocess.run(
      ['gpg', '--armor', '--export'] + ([os.environ['SIGNING_KEY']] if os.environ.get('SIGNING_KEY') else []),
      capture_output=True, check=True,
    ).stdout
    (pages / f'{repo}.gpg').write_bytes(out)

  if added and release_tag and gh_repo:
    release.ensure_release(gh_repo, release_tag)
    files = list(added)
    files += [s for p in added if (s := p.with_name(p.name + '.sig')).exists()]
    release.upload(gh_repo, release_tag, files)
    keep = _db_filenames(db)
    keep |= {n + '.sig' for n in keep}
    release.cleanup(gh_repo, release_tag, keep)

  index = pages / 'index.html'
  if not index.exists():
    index.write_text(f'<!doctype html>\n<meta charset="utf-8">\n<title>{repo}</title>\n<h1>{repo}</h1>\n')
