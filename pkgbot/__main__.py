from __future__ import annotations

import argparse
import json
import os
import sys

from .config import load_packages
from .detect import detect
from .publish import publish, take


def set_output(key: str, value: str) -> None:
  path = os.environ.get('GITHUB_OUTPUT')
  if path:
    with open(path, 'a') as f:
      f.write(f'{key}={value}\n')
  else:
    print(f'{key}={value}')


def cmd_detect(args: argparse.Namespace) -> None:
  built = detect(args.packages or None, args.changed_since, args.proxy)
  matrix = {'include': [{'pkg': n} for n in built]} if built else {'include': [{'pkg': '__skip__'}]}
  set_output('matrix', json.dumps(matrix))
  set_output('count', str(len(built)))
  print(f'{len(built)} package(s) to build: {built}', file=sys.stderr)


def cmd_take(args: argparse.Namespace) -> None:
  take(args.packages)


def cmd_publish(args: argparse.Namespace) -> None:
  publish(args.pages, args.artifacts, args.repo, args.release_tag, args.gh_repo)


def cmd_check(_args: argparse.Namespace) -> None:
  bad = []
  for p in load_packages():
    if not (p.path / 'PKGBUILD').is_file():
      bad.append(f'{p.pkgbase}: missing PKGBUILD')
  if bad:
    print('\n'.join(bad), file=sys.stderr)
    raise SystemExit(1)
  print('configuration OK')


def main(argv: list[str] | None = None) -> None:
  parser = argparse.ArgumentParser(prog='pkgbot')
  sub = parser.add_subparsers(dest='command', required=True)

  p = sub.add_parser('detect', help='run nvchecker and update PKGBUILDs')
  p.add_argument('--packages', nargs='*')
  p.add_argument('--changed-since')
  p.add_argument('--proxy')
  p.set_defaults(func=cmd_detect)

  p = sub.add_parser('take', help='record built versions into state/oldver')
  p.add_argument('packages', nargs='+')
  p.set_defaults(func=cmd_take)

  p = sub.add_parser('publish', help='sign packages and update the repository database')
  p.add_argument('--pages', required=True)
  p.add_argument('--artifacts', required=True)
  p.add_argument('--repo', required=True)
  p.add_argument('--release-tag')
  p.add_argument('--gh-repo', default=os.environ.get('GITHUB_REPOSITORY'))
  p.set_defaults(func=cmd_publish)

  p = sub.add_parser('check', help='validate package configuration')
  p.set_defaults(func=cmd_check)

  args = parser.parse_args(argv)
  args.func(args)


if __name__ == '__main__':
  main()
