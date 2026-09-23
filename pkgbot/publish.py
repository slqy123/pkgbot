from __future__ import annotations

import os
import re
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
  passphrase = os.environ.get('GPG_PASSPHRASE')
  if passphrase:
    cmd += ['--pinentry-mode', 'loopback', '--passphrase-fd', '0']
  if key := os.environ.get('SIGNING_KEY'):
    cmd += ['--local-user', key]
  cmd.append(str(path))
  print('+', ' '.join(cmd), flush=True)
  subprocess.run(cmd, input=(passphrase or '').encode(), check=True)


def _db_filenames(db: Path) -> set[str]:
  out = subprocess.check_output(
    ['bsdtar', '-xOf', str(db), '--include', '*/desc'], text=True,
  )
  return {line.strip() for line in out.splitlines() if line.strip().endswith('.pkg.tar.zst')}


def _db_names(db: Path) -> set[str]:
  out = subprocess.check_output(
    ['bsdtar', '-xOf', str(db), '--include', '*/desc'], text=True,
  )
  return set(re.findall(r'^%NAME%\n(.+)$', out, re.M))


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
  work: Path, artifacts: Path, repo: str, release_tag: str, gh_repo: str,
  debug: bool = False,
) -> None:
  work = Path(work).resolve()
  work.mkdir(parents=True, exist_ok=True)
  signing = sign_enabled()

  uploaded: list[Path] = []
  for pkg in sorted(Path(artifacts).rglob('*.pkg.tar.zst')):
    if signing:
      _sign(pkg)
    uploaded.append(pkg)
    sig = pkg.with_name(pkg.name + '.sig')
    if sig.exists():
      uploaded.append(sig)

  db = work / f'{repo}.db.tar.zst'
  packages = [p for p in uploaded if p.name.endswith('.pkg.tar.zst')]
  _run(['repo-add', str(db), *[str(p) for p in packages]])
  for old in work.glob('*.old'):
    old.unlink()

  if not debug:
    stale = sorted(n for n in _db_names(db) if n.endswith('-debug'))
    if stale:
      _run(['repo-remove', str(db), *stale])

  for ext in ('db', 'files'):
    real = work / f'{repo}.{ext}.tar.zst'
    copy = work / f'{repo}.{ext}'
    copy.unlink(missing_ok=True)
    shutil.copy2(real, copy)
    if signing:
      _sign(copy)
    uploaded.append(real)
    uploaded.append(copy)
    sig = copy.with_name(copy.name + '.sig')
    if sig.exists():
      uploaded.append(sig)

  if signing:
    out = subprocess.run(
      ['gpg', '--armor', '--export'] + ([os.environ['SIGNING_KEY']] if os.environ.get('SIGNING_KEY') else []),
      capture_output=True, check=True,
    ).stdout
    keyfile = work / f'{repo}.gpg'
    keyfile.write_bytes(out)
    uploaded.append(keyfile)

  release.ensure_release(gh_repo, release_tag)
  release.upload(gh_repo, release_tag, uploaded)

  keep = _db_filenames(db)
  keep |= {n + '.sig' for n in keep}
  release.cleanup(gh_repo, release_tag, keep)
