import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class BuildTests(unittest.TestCase):
  def test_artifact_names(self):
    script = Path(__file__).resolve().parents[1] / 'scripts/build.sh'
    for version in ('1.0-1', '1:1.0-1'):
      with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / 'packages/example'
        package.mkdir(parents=True)
        (package / 'PKGBUILD').write_text('pkgname=example\n')
        source = package / 'official-example-1.0.tar.zst'
        source.write_text('source')
        binary = root / 'bin'
        binary.mkdir()
        makepkg = binary / 'makepkg'
        makepkg.write_text('''#!/usr/bin/env bash
set -eu
file="$PWD/example-$TEST_VERSION-x86_64.pkg.tar.zst"
if [[ "$1" == --packagelist ]]; then
  printf '%s\\n' "$file" "$PWD/example-debug-$TEST_VERSION-x86_64.pkg.tar.zst"
else
  printf package > "$file"
  printf signature > "$file.sig"
fi
''')
        makepkg.chmod(0o755)
        env = dict(os.environ, DEBUG_PACKAGES='1', TEST_VERSION=version,
                   PATH=f'{binary}:{os.environ["PATH"]}')
        subprocess.run(['bash', str(script), 'example'], cwd=root, env=env, check=True)
        name = f'example-{version.replace(":", "_")}-x86_64.pkg.tar.zst'
        self.assertEqual(sorted(p.name for p in package.glob('*.pkg.tar.zst*')),
                         [name, name + '.sig'])
        self.assertEqual((package / name).read_text(), 'package')
        self.assertEqual((package / (name + '.sig')).read_text(), 'signature')
        self.assertEqual(source.read_text(), 'source')
