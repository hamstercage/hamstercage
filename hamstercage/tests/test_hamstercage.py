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
        self.assertEquals(tag.description, 'Files that apply to all hosts')
        self.assertIn('one.txt', tag.entries)


    def test_add_dir(self):
        dut = self.prepare_hamstercage()

        dir_to_add = 'a-dir'
        path_to_add = dut.target / dir_to_add
        path_to_add.mkdir()

        Args = namedtuple('Args', 'files')
        args = Args(files=[dir_to_add])
        r = dut.add(args)
        self.assertEquals(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEquals(('hosts:\n'
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
        path_to_add.chmod(0o644)

        Args = namedtuple('Args', 'files')
        args = Args(files=[file_to_add])
        r = dut.add(args)
        self.assertEquals(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEquals(('hosts:\n'
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
                     '        mode: 0o644\n'
                     '        owner: stb\n'
                     '        type: file\n'), m)

        f = (dut.repo / 'tags' / 'all' / file_to_add).read_text('utf-8')
        self.assertEquals('Hello, world!', f)


    def test_add_link(self):
        dut = self.prepare_hamstercage()

        link_to_add = 'a-link'
        path_to_add = dut.target / link_to_add
        path_to_add.symlink_to('/dev/null')

        Args = namedtuple('Args', 'files')
        args = Args(files=[link_to_add])
        r = dut.add(args)
        self.assertEquals(0, r)

        m = dut.manifest_file.read_text('utf-8')
        self.assertEquals(('hosts:\n'
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


    def test_apply(self):
        dut = self.prepare_hamstercage()

        dir_to_add = 'a-dir'
        dir_path = dut.target / dir_to_add
        dir_path.mkdir()

        file_to_add = 'foo.txt'
        file_path = dut.target / file_to_add
        file_path.write_text('Hello, world!', 'utf-8')
        file_path.chmod(0o644)

        link_to_add = 'a-link'
        link_path = dut.target / link_to_add
        link_path.symlink_to('/dev/null')

        Args = namedtuple('Args', 'files')
        args = Args(files=[dir_to_add, file_to_add, link_to_add])
        r = dut.add(args)
        self.assertEquals(0, r)

        dut.target = Path(self.tmpdir) / 'apply'
        args = Args(files=[])
        r = dut.apply(args)
        self.assertEquals(0, r)
        self.assert_path_equal(dir_path, dut.target / dir_to_add)
        self.assert_path_equal(file_path, dut.target / file_to_add)
        self.assert_path_equal(link_path, dut.target / link_to_add)

        # again to make sure it's idempotent
        r = dut.apply(args)
        self.assertEquals(0, r)
        self.assert_path_equal(dir_path, dut.target / dir_to_add)
        self.assert_path_equal(file_path, dut.target / file_to_add)
        self.assert_path_equal(link_path, dut.target / link_to_add)

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

        Args = namedtuple('Args', 'files')
        args = Args(files=[])
        with self.assertRaises(HamstercageException):
            r = dut.apply(args)


    def test_init(self):
        dut = self.prepare_hamstercage()

        m = dut.manifest_file.read_text('utf-8')
        self.assertEquals(('hosts:\n'
                     '  testing.example.com:\n'
                     "    description: ''\n"
                     '    tags:\n'
                     '    - all\n'
                     'tags:\n'
                     '  all:\n'
                     '    description: files that apply to all hosts\n'
                     '    entries: {}\n'), m)


    def assert_path_equal(self, expected_path: Path, actual_path: Path):
        with self.subTest():
            self.assertTrue(actual_path.exists())
        with self.subTest():
            self.assertEquals(expected_path.is_dir(), actual_path.is_dir())
        with self.subTest():
            self.assertEquals(expected_path.is_file(), actual_path.is_file())
        with self.subTest():
            self.assertEquals(expected_path.is_symlink(), actual_path.is_symlink())
        expected_stat = expected_path.stat()
        actual_stat = actual_path.stat()
        with self.subTest():
            self.assertEquals(expected_stat.st_gid, actual_stat.st_gid)
        with self.subTest():
            self.assertEquals(expected_stat.st_uid, actual_stat.st_uid)
        with self.subTest():
            self.assertEquals(expected_stat.st_mode, actual_stat.st_mode)

