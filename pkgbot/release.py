from __future__ import annotations

import subprocess
from pathlib import Path

PACKAGE_SUFFIXES = ('.pkg.tar.zst', '.pkg.tar.zst.sig')


def _run(cmd: list[str]) -> None:
  print('+', ' '.join(cmd), flush=True)
  subprocess.run(cmd, check=True)


def ensure_release(repo: str, tag: str) -> None:
  exists = subprocess.run(
    ['gh', 'release', 'view', tag, '--repo', repo],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
  ).returncode == 0
  if not exists:
    _run([
      'gh', 'release', 'create', tag, '--repo', repo,
      '--title', tag, '--notes', 'Arch Linux package repository assets',
    ])


def list_assets(repo: str, tag: str) -> list[str]:
  out = subprocess.check_output(
    ['gh', 'release', 'view', tag, '--repo', repo,
     '--json', 'assets', '--jq', '.assets[].name'],
    text=True,
  )
  return out.split()


def upload(repo: str, tag: str, files: list[Path]) -> None:
  if not files:
    return
  _run(['gh', 'release', 'upload', tag, '--repo', repo, '--clobber',
        *[str(f) for f in files]])


def cleanup(repo: str, tag: str, keep: set[str]) -> None:
  for name in list_assets(repo, tag):
    if name.endswith(PACKAGE_SUFFIXES) and name not in keep:
      _run(['gh', 'release', 'delete-asset', tag, name, '--repo', repo, '--yes'])
