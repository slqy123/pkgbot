from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass

import tomli_w

from .config import (
  NEWVER, NVCHECKER_KEYFILE, NVCHECKER_TOML, OLDVER, PACKAGES_DIR,
  Package, load_packages,
)
from .update import update_package


@dataclass
class NvResult:
  oldver: str | None = None
  newver: str | None = None
  changed: bool = False
  rebuild: bool = False
  error: bool = False


def effective_config(packages: list[Package]) -> dict[str, dict]:
  conf: dict[str, dict] = {}
  for p in packages:
    for i, entry in enumerate(p.update_on):
      e = {k: (p.pkgbase if v in (None, '') else v) for k, v in entry.items()}
      conf[p.pkgbase if i == 0 else f'{p.pkgbase}:{i}'] = e
  return conf


def run_nvchecker(packages: list[Package], proxy: str | None = None) -> dict[str, NvResult]:
  conf = effective_config(packages)
  conf['__config__'] = {'oldver': str(OLDVER), 'newver': str(NEWVER)}
  if proxy:
    conf['__config__']['proxy'] = proxy
  NVCHECKER_TOML.write_bytes(tomli_w.dumps(conf).encode())
  if not OLDVER.exists():
    OLDVER.touch()

  cmd = ['nvchecker', '--logger', 'json', '-c', str(NVCHECKER_TOML)]
  if token := os.environ.get('GITHUB_TOKEN'):
    NVCHECKER_KEYFILE.write_text(f'[keys]\n"github.com" = "{token}"\n')
    cmd += ['--keyfile', str(NVCHECKER_KEYFILE)]

  proc = subprocess.run(cmd, cwd=PACKAGES_DIR, capture_output=True, text=True)
  sys.stderr.write(proc.stderr)
  if proc.returncode != 0:
    raise RuntimeError(f'nvchecker exited with {proc.returncode}')

  versions: dict[str, dict[int, tuple]] = {}
  rebuild: set[str] = set()
  errors: set[str] = set()
  for line in proc.stdout.splitlines():
    line = line.strip()
    if not line.startswith('{'):
      continue
    try:
      event = json.loads(line)
    except json.JSONDecodeError:
      continue
    name = event.get('name')
    if not name:
      continue
    base, _, idx = name.partition(':')
    i = int(idx) if idx else 0
    if event.get('level') in ('warning', 'warn', 'error', 'exception', 'critical'):
      errors.add(base)
      continue
    if event.get('event') == 'updated':
      versions.setdefault(base, {})[i] = (event.get('old_version'), event.get('version'))
      if i > 0:
        rebuild.add(base)
    elif event.get('event') == 'up-to-date':
      versions.setdefault(base, {})[i] = (event.get('version'), event.get('version'))

  results: dict[str, NvResult] = {}
  for p in packages:
    r = NvResult()
    if p.pkgbase in errors:
      r.error = True
    else:
      first = versions.get(p.pkgbase, {}).get(0)
      if first is not None:
        r.oldver, r.newver = first
        r.changed = first[0] != first[1]
      r.rebuild = p.pkgbase in rebuild
    results[p.pkgbase] = r
  return results


EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


def _changed_packages(rev: str) -> set[str]:
  if not rev or set(rev) == {'0'}:
    rev = EMPTY_TREE
  out = subprocess.run(
    ['git', 'diff', '--name-only', rev, 'HEAD', '--', 'packages'],
    capture_output=True, text=True, check=True,
  ).stdout
  names = set()
  for line in out.splitlines():
    parts = line.split('/')
    if len(parts) >= 2 and parts[0] == 'packages':
      names.add(parts[1])
  return names


def detect(
  names: list[str] | None = None,
  changed_since: str | None = None,
  proxy: str | None = None,
) -> list[str]:
  all_packages = load_packages()
  by_name = {p.pkgbase: p for p in all_packages}
  force = bool(names or changed_since)

  if names:
    selected = [by_name[n] for n in names if n in by_name]
  elif changed_since:
    changed = _changed_packages(changed_since)
    selected = [p for p in all_packages if p.pkgbase in changed]
  else:
    selected = all_packages

  detectable = [p for p in selected if p.update_on]
  results = run_nvchecker(detectable, proxy) if detectable else {}
  if not NEWVER.exists():
    NEWVER.write_text('{"version": 2, "data": {}}\n')

  built = []
  for p in selected:
    if p.update_on:
      r = results.get(p.pkgbase)
      if r is None or r.error:
        print(f'{p.pkgbase}: skipped (nvchecker error)', file=sys.stderr)
        continue
      if r.changed or r.rebuild:
        try:
          update_package(p, r.newver)
        except subprocess.CalledProcessError as e:
          print(f'{p.pkgbase}: skipped (update failed: {e})', file=sys.stderr)
          continue
      elif not force:
        continue
    elif not force:
      continue
    built.append(p.pkgbase)
  return built
