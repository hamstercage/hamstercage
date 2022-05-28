import os
import shutil
from collections import namedtuple
from pathlib import Path
from unittest import TestCase

import pytest

from hamstercage.__main__ import Hamstercage

from importlib.resources import files

from hamstercage.hamstercage_exception import HamstercageException


class TestHamstercage(TestCase):

    @pytest.fixture(autouse=True)
    def initdir(self, tmpdir):
        self.tmpdir = tmpdir


    def prepare_hamstercage(self) -> Hamstercage:
        dut = Hamstercage()
        dut.manifest_file = self.tmpdir / 'manifest.yaml'
        dut.hostname = 'testing.example.com'
        dut.target = Path(self.tmpdir) / 'target'
        dut.repo = Path(self.tmpdir) / 'repo'
        dut.init(None)
        os.chmod(dut.manifest_file, 0o664)
        dut.target.mkdir()
        return dut


    def test_load(self):
        dut = Hamstercage()
        dut.manifest_file = files('hamstercage.tests') / 'manifest.yaml'
        dut.hostname = 'testing.example.com'
        dut._load_manifest()

        self.assertIn('testing.example.com', dut.manifest.hosts)
        host = dut.manifest.hosts['testing.example.com']
        self.assertIn('all', host.tags)

        self.assertIn('all', dut.manifest.tags)
        tag = dut.manifest.tags['all']
        self.assertEqual(tag.description, 'Files that apply to all hosts')
        self.assertIn('one.txt', tag.entries)


    def test_add_dir(self):
        dut = self.prepare_hamstercage()

        dir_to_add = 'a-dir'
        path_to_add = dut.target / dir_to_add
        path_to_add.mkdir()

        args = Args(files=[dir_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEqual(('hosts:\n'
                     '  testing.example.com:\n'
                     "    description: ''\n"
                     '    tags:\n'
                     '    - all\n'
                     'tags:\n'
                     '  all:\n'
                     '    description: files that apply to all hosts\n'
                     '    entries:\n'
                     '      a-dir:\n'
                     '        group: staff\n'
                     '        mode: 0o755\n'
                     '        owner: stb\n'
                     '        type: dir\n'), m)

        self.assertFalse((dut.repo / 'tags' / 'all' / dir_to_add).exists())


    def test_add_file(self):
        dut = self.prepare_hamstercage()

        file_to_add = 'foo.txt'
        path_to_add = dut.target / file_to_add
        path_to_add.write_text('Hello, world!', 'utf-8')
        path_to_add.chmod(0o760)

        args = Args(files=[file_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEqual(('hosts:\n'
                     '  testing.example.com:\n'
                     "    description: ''\n"
                     '    tags:\n'
                     '    - all\n'
                     'tags:\n'
                     '  all:\n'
                     '    description: files that apply to all hosts\n'
                     '    entries:\n'
                     '      foo.txt:\n'
                     '        group: staff\n'
                     '        mode: 0o760\n'
                     '        owner: stb\n'
                     '        type: file\n'), m)

        f = (dut.repo / 'tags' / 'all' / file_to_add).read_text('utf-8')
        self.assertEqual('Hello, world!', f)


    def test_add_link(self):
        dut = self.prepare_hamstercage()

        link_to_add = 'a-link'
        path_to_add = dut.target / link_to_add
        path_to_add.symlink_to('/dev/null')

        args = Args(files=[link_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEqual(('hosts:\n'
                     '  testing.example.com:\n'
                     "    description: ''\n"
                     '    tags:\n'
                     '    - all\n'
                     'tags:\n'
                     '  all:\n'
                     '    description: files that apply to all hosts\n'
                     '    entries:\n'
                     '      a-link:\n'
                     '        target: /dev/null\n'
                     '        type: link\n'), m)

        self.assertFalse((dut.repo / 'tags' / 'all' / link_to_add).exists())


    def test_add_many(self):
        dut = self.prepare_hamstercage()

        self.dir_to_add = 'a-dir'
        self.dir_path = dut.target / self.dir_to_add
        self.dir_path.mkdir()

        self.file_to_add = 'foo.txt'
        self.file_path = dut.target / self.file_to_add
        self.file_path.write_text('Hello, world!', 'utf-8')
        self.file_path.chmod(0o750)

        self.link_to_add = 'a-link'
        self.link_path = dut.target / self.link_to_add
        self.link_path.symlink_to('/dev/null')

        args = Args(files=[self.dir_to_add, self.file_to_add, self.link_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        return dut

    def test_apply(self):
        dut = self.test_add_many()

        dut.target = Path(self.tmpdir) / 'apply'
        args = Args(files=[])
        r = dut.apply(args)
        self.assertEqual(0, r)
        self.assert_path_equal(self.dir_path, dut.target / self.dir_to_add)
        self.assert_path_equal(self.file_path, dut.target / self.file_to_add)
        self.assert_path_equal(self.link_path, dut.target / self.link_to_add)

        # again to make sure it's idempotent
        r = dut.apply(args)
        self.assertEqual(0, r)
        self.assert_path_equal(self.dir_path, dut.target / self.dir_to_add)
        self.assert_path_equal(self.file_path, dut.target / self.file_to_add)
        self.assert_path_equal(self.link_path, dut.target / self.link_to_add)

        return dut


    def test_apply_target_exists(self):
        dut = self.test_apply()

        dir_to_add = 'a-dir'
        dir_path = dut.target / dir_to_add
        file_to_add = 'foo.txt'
        file_path = dut.target / file_to_add
        link_to_add = 'a-link'
        link_path = dut.target / link_to_add

        dir_path.rename(dut.target / 'temp')
        file_path.rename(dut.target / 'a-dir')
        link_path.rename(dut.target / 'foo.txt')
        (dut.target / 'temp').rename(dut.target / 'a-link')

        args = Args(files=[])
        with self.assertRaises(HamstercageException):
            r = dut.apply(args)


    def test_init(self):
        dut = self.prepare_hamstercage()

        m = dut.manifest_file.read_text('utf-8')
        self.assertEqual(('hosts:\n'
                     '  testing.example.com:\n'
                     "    description: ''\n"
                     '    tags:\n'
                     '    - all\n'
                     'tags:\n'
                     '  all:\n'
                     '    description: files that apply to all hosts\n'
                     '    entries: {}\n'), m)


    def test_remove_file(self):
        dut = self.prepare_hamstercage()

        file_to_add = 'foo.txt'
        path_to_add = dut.target / file_to_add
        path_to_add.write_text('Hello, world!', 'utf-8')
        path_to_add.chmod(0o760)

        args = Args(files=[file_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEqual(('hosts:\n'
                           '  testing.example.com:\n'
                           "    description: ''\n"
                           '    tags:\n'
                           '    - all\n'
                           'tags:\n'
                           '  all:\n'
                           '    description: files that apply to all hosts\n'
                           '    entries:\n'
                           '      foo.txt:\n'
                           '        group: staff\n'
                           '        mode: 0o760\n'
                           '        owner: stb\n'
                           '        type: file\n'), m)

        f = (dut.repo / 'tags' / 'all' / file_to_add).read_text('utf-8')
        self.assertEqual('Hello, world!', f)

        r = dut.remove(args)
        self.assertEqual(0, r)
        self.assertFalse((dut.repo / 'tags' / 'all' / file_to_add).exists())


    def test_save(self):
        dut = self.test_add_many()

        dir_to_add = 'a-dir'
        dir_path = dut.target / dir_to_add
        file_to_add = 'foo.txt'
        file_path = dut.target / file_to_add
        link_to_add = 'a-link'
        link_path = dut.target / link_to_add

        dir_path.chmod(0o700)
        file_path.write_text('Foo bar', 'utf-8')
        link_path.unlink()
        link_path.symlink_to('/dev/zero')

        r = dut.save(Args(files=[], force=0))
        self.assertEqual(0, r)

        entry = dut.manifest.tags['all'].entries[dir_to_add]
        self.assertEqual(0o700, entry.mode)
        entry = dut.manifest.tags['all'].entries[file_to_add]
        self.assertEqual('Foo bar', dut._path_repo_absolute('all', entry).read_text())
        entry = dut.manifest.tags['all'].entries[link_to_add]
        self.assertEqual('/dev/zero', entry.target)


    def assert_path_equal(self, expected_path: Path, actual_path: Path):
        self.assertTrue(actual_path.exists())
        self.assertEqual(expected_path.is_dir(), actual_path.is_dir())
        self.assertEqual(expected_path.is_file(), actual_path.is_file())
        self.assertEqual(expected_path.is_symlink(), actual_path.is_symlink())
        expected_stat = expected_path.stat()
        actual_stat = actual_path.stat()
        self.assertEqual(expected_stat.st_gid, actual_stat.st_gid)
        self.assertEqual(expected_stat.st_uid, actual_stat.st_uid)
        self.assertEqual(expected_stat.st_mode, actual_stat.st_mode)


class Args:
    files = []
    force = 0

    def __init__(self, files=[], force=0):
        self.files = files
        self.force = force
