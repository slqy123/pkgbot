from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(os.environ.get('PKGBOT_ROOT') or Path(__file__).resolve().parent.parent)
PACKAGES_DIR = ROOT / 'packages'
STATE_DIR = ROOT / 'state'
OLDVER = STATE_DIR / 'oldver'
NEWVER = STATE_DIR / 'newver'
NVCHECKER_TOML = STATE_DIR / 'nvchecker.toml'
NVCHECKER_KEYFILE = STATE_DIR / 'nvchecker_keyfile.toml'
DETECT_OUTPUTS = STATE_DIR / 'detect.outputs'

STRATEGIES = ('aur', 'github-release', 'vcs', 'none')
VCS_SUFFIXES = ('-git', '-hg', '-svn', '-bzr')


@dataclass
class Package:
  pkgbase: str
  path: Path
  strategy: str
  update_on: list[dict] = field(default_factory=list)
  repo_depends: list[str] = field(default_factory=list)


def load_package(pkgbase: str) -> Package:
  path = PACKAGES_DIR / pkgbase
  conf_path = path / 'pkg.yaml'
  if not conf_path.is_file():
    raise ValueError(f'{pkgbase}: missing pkg.yaml')
  with conf_path.open() as f:
    conf = yaml.safe_load(f) or {}

  strategy = conf.get('strategy')
  if strategy not in STRATEGIES:
    raise ValueError(f'{pkgbase}: strategy must be one of {STRATEGIES}, got {strategy!r}')

  update_on = conf.get('update_on') or []
  if not isinstance(update_on, list) or not all(isinstance(x, dict) for x in update_on):
    raise ValueError(f'{pkgbase}: update_on must be a list of dicts')
  if strategy != 'none' and not update_on:
    raise ValueError(f'{pkgbase}: update_on is required for strategy {strategy!r}')

  return Package(
    pkgbase = pkgbase,
    path = path,
    strategy = strategy,
    update_on = update_on,
    repo_depends = list(conf.get('repo_depends') or []),
  )


def load_packages() -> list[Package]:
  if not PACKAGES_DIR.is_dir():
    return []
  return [
    load_package(d.name)
    for d in sorted(PACKAGES_DIR.iterdir())
    if (d / 'pkg.yaml').is_file()
  ]
