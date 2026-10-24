import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from pkgbot import config
from pkgbot.__main__ import cmd_check, cmd_detect
from pkgbot.detect import NvResult, detect, effective_config


class AurTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.pkg = config.Package('example', self.root, 'aur', [{'source': 'aur', 'aur': 'example-base'}])

  def test_commit_source(self):
    self.assertEqual(effective_config([self.pkg]), {
      'example': {'source': 'git', 'git': 'https://aur.archlinux.org/example-base.git', 'use_commit': True},
    })

  def test_selection(self):
    for result, names, expected in [
      (NvResult(newver='a' * 40, changed=True), None, ['example']),
      (NvResult(newver='a' * 40), None, []),
      (NvResult(newver='a' * 40), ['example'], ['example']),
      (NvResult(error=True), ['example'], []),
    ]:
      with self.subTest(result=result, names=names), patch('pkgbot.detect.load_packages', return_value=[self.pkg]), patch('pkgbot.detect.run_nvchecker', return_value={'example': result}), patch('pkgbot.detect.NEWVER', self.root / 'newver'), patch('pkgbot.detect.update_package') as update:
        self.assertEqual(detect(names), expected)
        update.assert_not_called()

  def test_disabled_package(self):
    self.pkg.enabled = False
    with patch('pkgbot.detect.load_packages', return_value=[self.pkg]), patch('pkgbot.detect.NEWVER', self.root / 'newver'), patch('pkgbot.detect.run_nvchecker') as checker:
      self.assertEqual(detect(['example']), [])
      checker.assert_not_called()

  def test_matrix_pins_commit(self):
    versions = self.root / 'newver'
    versions.write_text(json.dumps({'data': {'example': {'version': 'a' * 40}}}))
    output = self.root / 'outputs'
    with patch('pkgbot.__main__.detect', return_value=['example']), patch('pkgbot.__main__.load_packages', return_value=[self.pkg]), patch('pkgbot.__main__.NEWVER', versions), patch('pkgbot.__main__.DETECT_OUTPUTS', output):
      cmd_detect(Namespace(packages=None, changed_since=None, proxy=None))
    matrix = json.loads(output.read_text().splitlines()[0].removeprefix('matrix='))
    self.assertEqual(matrix['include'][0]['aur_commit'], 'a' * 40)
    self.assertEqual(matrix['include'][0]['aur_url'], 'https://aur.archlinux.org/example-base.git')

  def test_check_without_pkgbuild(self):
    with patch('pkgbot.__main__.load_packages', return_value=[self.pkg]):
      cmd_check(Namespace())

  def test_config_without_pkgbuild(self):
    folder = self.root / 'example'
    folder.mkdir()
    (folder / 'pkg.yaml').write_text('strategy: aur\nupdate_on:\n  - source: aur\n')
    with patch.object(config, 'PACKAGES_DIR', self.root):
      self.assertEqual(config.load_package('example').strategy, 'aur')


if __name__ == '__main__':
  unittest.main()
