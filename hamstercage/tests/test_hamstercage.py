import grp
import io
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from pwd import getpwuid
from unittest import TestCase

import pytest
from importlib_resources import files

from hamstercage.__main__ import Hamstercage
from hamstercage.hamstercage_exception import HamstercageException
from hamstercage.manifest import Hook
from hamstercage.utils import chmod


class TestHamstercage(TestCase):
    @pytest.fixture(autouse=True)
    def initdir(self, tmpdir):
        self.tmpdir = tmpdir
        self.user = getpwuid(os.stat(self.tmpdir).st_uid).pw_name
        self.group = grp.getgrgid(os.stat(self.tmpdir).st_gid).gr_name
        self.now = time.time()

    def prepare_hamstercage(self) -> Hamstercage:
        dut = Hamstercage()
        dut.manifest_file = self.tmpdir / "hamstercage.yaml"
        dut.hostname = "testing.example.com"
        dut.target = Path(self.tmpdir) / "target"
        dut.repo = Path(self.tmpdir) / "repo"
        dut.init(None)
        chmod(dut.manifest_file, 0o664)
        dut.target.mkdir()
        return dut

    def test_load(self):
        dut = Hamstercage()
        dut.manifest_file = files("hamstercage.tests") / "hamstercage.yaml"
        dut.hostname = "testing.example.com"
        dut._load_manifest()

        self.assertIn("testing.example.com", dut.manifest.hosts)
        host = dut.manifest.hosts["testing.example.com"]
        self.assertIn("all", host.tags)

        self.assertIn("all", dut.manifest.tags)
        tag = dut.manifest.tags["all"]
        self.assertEqual(tag.description, "files that apply to all hosts")
        self.assertIn("foo.txt", tag.entries)

    def test_add_dir(self):
        dut = self.prepare_hamstercage()

        dir_to_add = "a-dir"
        path_to_add = dut.target / dir_to_add
        path_to_add.mkdir()
        os.utime(path_to_add, (self.now, self.now))

        args = Args(files=[dir_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text("utf-8")
        self.assertEqual(
            (
                "hosts:\n"
                "  testing.example.com:\n"
                "    tags:\n"
                "    - all\n"
                "tags:\n"
                "  all:\n"
                "    description: files that apply to all hosts\n"
                "    entries:\n"
                "      a-dir:\n"
                "        group: " + self.group + "\n"
                "        mode: 0o755\n"
                "        owner: " + self.user + "\n"
                "        type: dir\n"
            ),
            m,
        )

        self.assertFalse((dut.repo / "tags" / "all" / dir_to_add).exists())

    def test_add_file(self):
        dut = self.prepare_hamstercage()

        file_to_add = "foo.txt"
        path_to_add = dut.target / file_to_add
        path_to_add.write_text("Hello, world!", "utf-8")
        path_to_add.chmod(0o760)
        os.utime(path_to_add, (self.now, self.now))

        args = Args(files=[file_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text("utf-8")
        self.assertEqual(
            (
                "hosts:\n"
                "  testing.example.com:\n"
                "    tags:\n"
                "    - all\n"
                "tags:\n"
                "  all:\n"
                "    description: files that apply to all hosts\n"
                "    entries:\n"
                "      foo.txt:\n"
                "        group: " + self.group + "\n"
                "        mode: 0o760\n"
                "        owner: " + self.user + "\n"
                "        type: file\n"
            ),
            m,
        )

        f = (dut.repo / "tags" / "all" / file_to_add).read_text("utf-8")
        self.assertEqual("Hello, world!", f)

    def test_add_link(self):
        dut = self.prepare_hamstercage()

        link_to_add = "a-link"
        path_to_add = dut.target / link_to_add
        path_to_add.symlink_to("/dev/null")
        os.utime(path_to_add, (self.now, self.now), follow_symlinks=False)

        args = Args(files=[link_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text("utf-8")
        self.assertEqual(
            (
                "hosts:\n"
                "  testing.example.com:\n"
                "    tags:\n"
                "    - all\n"
                "tags:\n"
                "  all:\n"
                "    description: files that apply to all hosts\n"
                "    entries:\n"
                "      a-link:\n"
                "        target: /dev/null\n"
                "        type: link\n"
            ),
            m,
        )

        self.assertFalse((dut.repo / "tags" / "all" / link_to_add).exists())

    def test_add_many(self) -> Hamstercage:
        dut = self.prepare_hamstercage()

        self.dir_to_add = "a-dir"
        self.dir_path = dut.target / self.dir_to_add
        self.dir_path.mkdir()
        os.utime(self.dir_path, (self.now, self.now))

        self.file_to_add = "foo.txt"
        self.file_path = dut.target / self.file_to_add
        self.file_path.write_text("Hello, world!", "utf-8")
        self.file_path.chmod(0o750)
        os.utime(self.file_path, (self.now, self.now))

        self.link_to_add = "a-link"
        self.link_path = dut.target / self.link_to_add
        self.link_path.symlink_to("/dev/null")
        os.utime(self.link_path, (self.now, self.now), follow_symlinks=False)

        args = Args(files=[self.dir_to_add, self.file_to_add, self.link_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        return dut

    def test_apply(self):
        dut = self.test_add_many()
        hook_status_file = self.tmpdir / "hook-ran"
        hook = Hook.from_dict(
            "post-apply",
            {"command": f"echo foo >{hook_status_file}", "type": "shell"},
        )
        dut.manifest.tags["all"].hooks[hook.name] = hook

        dut.target = Path(self.tmpdir) / "apply"
        args = Args(files=[])
        r = dut.apply(args)
        self.assertEqual(0, r)
        self.assert_path_equal(self.dir_path, dut.target / self.dir_to_add)
        self.assert_path_equal(self.file_path, dut.target / self.file_to_add)
        self.assert_path_equal(self.link_path, dut.target / self.link_to_add)
        assert hook_status_file.exists()

        # again to make sure it's idempotent
        r = dut.apply(args)
        self.assertEqual(0, r)
        self.assert_path_equal(self.dir_path, dut.target / self.dir_to_add)
        self.assert_path_equal(self.file_path, dut.target / self.file_to_add)
        self.assert_path_equal(self.link_path, dut.target / self.link_to_add)

        return dut

    def test_apply_target_exists(self):
        dut = self.test_apply()

        dir_to_add = "a-dir"
        dir_path = dut.target / dir_to_add
        file_to_add = "foo.txt"
        file_path = dut.target / file_to_add
        link_to_add = "a-link"
        link_path = dut.target / link_to_add

        dir_path.rename(dut.target / "temp")
        file_path.rename(dut.target / "a-dir")
        link_path.rename(dut.target / "foo.txt")
        (dut.target / "temp").rename(dut.target / "a-link")

        args = Args(files=[])
        with self.assertRaises(HamstercageException):
            r = dut.apply(args)

    def test_diff_unchanged(self):
        dut = self.test_add_many()

        args = Args(files=[])
        r = dut.diff(args)
        self.assertEqual(0, r)

    def test_diff_changed(self):
        dut = self.test_add_many()

        self.file_path.write_text("Goodbye, world!", "utf-8")

        args = Args(files=[])
        r = dut.diff(args)
        self.assertEqual(1, r)

    def test_entries(self):
        dut = self.test_add_many()

        entries = {}
        for (t, e) in dut._entries():
            entries[e.path] = (t, e)
        assert len(entries) == 3
        assert "foo.txt" in entries
        assert "a-dir" in entries
        assert "a-link" in entries

    def test_entries_duplicate(self):
        dut = self.prepare_hamstercage()

        file_to_add = "foo.txt"
        path_to_add = dut.target / file_to_add
        path_to_add.write_text("Hello, world!", "utf-8")
        path_to_add.chmod(0o760)
        os.utime(path_to_add, (self.now, self.now))

        args = Args(name="other")
        r = dut.tag_add(args)
        self.assertEqual(0, r)

        args = Args(files=[file_to_add])
        dut.tags = ["all"]
        r = dut.add(args)
        self.assertEqual(0, r)

        dut.tags = ["other"]
        r = dut.add(args)
        self.assertEqual(0, r)

        entries = {}
        for (t, e) in dut._entries():
            entries[e.path] = (t, e)
        assert len(entries) == 1
        assert "foo.txt" in entries

    def test_init(self):
        dut = self.prepare_hamstercage()

        m = dut.manifest_file.read_text("utf-8")
        self.assertEqual(
            (
                "hosts:\n"
                "  testing.example.com:\n"
                "    tags:\n"
                "    - all\n"
                "tags:\n"
                "  all:\n"
                "    description: files that apply to all hosts\n"
            ),
            m,
        )

    def test_list_short(self):
        dut = self.test_add_many()
        out = io.StringIO()

        args = Args(files=[], long=0)
        r = dut.list(args, file=out)
        self.assertEqual(0, r)

        t = datetime.fromtimestamp(os.stat(self.file_path).st_mtime).strftime("%H:%M")
        self.assertEqual(
            [
                str(self.dir_path),
                str(self.link_path),
                str(self.file_path),
                "",
            ],
            out.getvalue().split("\n"),
        )

    def test_list_long(self):
        dut = self.test_add_many()
        out = io.StringIO()

        args = Args(files=[], long=1)
        r = dut.list(args, file=out)
        self.assertEqual(0, r)

        ts_dir = datetime.fromtimestamp(os.stat(self.dir_path).st_mtime).strftime(
            "%H:%M"
        )
        ts_file = datetime.fromtimestamp(os.stat(self.file_path).st_mtime).strftime(
            "%H:%M"
        )
        ts_link = datetime.fromtimestamp(os.stat(self.link_path).st_mtime).strftime(
            "%H:%M"
        )
        self.assertEqual(
            [
                f" \tdrwxr-xr-x\t{self.user}\t{self.group}\t0\t{ts_dir}\tall\t{self.dir_path}/",
                f" \tlrw-r--r--\troot\troot\t0\t{ts_link}\tall\t{self.link_path} -> /dev/null",
                f" \t-rwxr-x---\t{self.user}\t{self.group}\t13\t{ts_file}\tall\t{self.file_path}",
                "",
            ],
            out.getvalue().split("\n"),
        )

    def test_list_long_one(self):
        dut = self.test_add_many()
        out = io.StringIO()

        args = Args(files=[str(self.file_path)], long=1)
        r = dut.list(args, file=out)
        self.assertEqual(0, r)

        ts_file = datetime.fromtimestamp(os.stat(self.file_path).st_mtime).strftime(
            "%H:%M"
        )
        self.assertEqual(
            [
                f" \t-rwxr-x---\t{self.user}\t{self.group}\t13\t{ts_file}\tall\t{self.file_path}",
                "",
            ],
            out.getvalue().split("\n"),
        )

    def test_main(self):
        dut = self.prepare_hamstercage()
        dut.main([])

    def test_normalize_path(self):
        dut = self.prepare_hamstercage()

        assert dut._normalize_path("/foo") == "foo"
        assert dut._normalize_path(str(dut.target / "foo")) == "foo"

    def test_remove_file(self):
        dut = self.prepare_hamstercage()

        file_to_add = "foo.txt"
        path_to_add = dut.target / file_to_add
        path_to_add.write_text("Hello, world!", "utf-8")
        path_to_add.chmod(0o760)

        args = Args(files=[file_to_add])
        r = dut.add(args)
        self.assertEqual(0, r)

        m = dut.manifest_file.read_text("utf-8")
        self.assertEqual(
            (
                "hosts:\n"
                "  testing.example.com:\n"
                "    tags:\n"
                "    - all\n"
                "tags:\n"
                "  all:\n"
                "    description: files that apply to all hosts\n"
                "    entries:\n"
                "      foo.txt:\n"
                "        group: " + self.group + "\n"
                "        mode: 0o760\n"
                "        owner: " + self.user + "\n"
                "        type: file\n"
            ),
            m,
        )

        f = (dut.repo / "tags" / "all" / file_to_add).read_text("utf-8")
        self.assertEqual("Hello, world!", f)

        r = dut.remove(args)
        self.assertEqual(0, r)
        self.assertFalse((dut.repo / "tags" / "all" / file_to_add).exists())

    def test_save(self):
        dut = self.test_add_many()

        dir_to_add = "a-dir"
        dir_path = dut.target / dir_to_add
        file_to_add = "foo.txt"
        file_path = dut.target / file_to_add
        link_to_add = "a-link"
        link_path = dut.target / link_to_add

        dir_path.chmod(0o700)
        file_path.write_text("Foo bar", "utf-8")
        link_path.unlink()
        link_path.symlink_to("/dev/zero")

        r = dut.save(Args(files=[], force=0))
        self.assertEqual(0, r)

        entry = dut.manifest.tags["all"].entries[dir_to_add]
        self.assertEqual(0o700, entry.mode)
        entry = dut.manifest.tags["all"].entries[file_to_add]
        self.assertEqual("Foo bar", dut._path_repo_absolute("all", entry).read_text())
        entry = dut.manifest.tags["all"].entries[link_to_add]
        self.assertEqual("/dev/zero", entry.target)

    def test_tag_add(self):
        dut = self.prepare_hamstercage()
        dut._load_manifest()

        args = Args(name="other")
        r = dut.tag_add(args)
        self.assertEqual(0, r)

        assert "other" in dut.manifest.tags
        assert dut.manifest.tags["other"].description == ""

        args = Args(name="other")
        with self.assertRaises(HamstercageException):
            dut.tag_add(args)

        args = Args(name="foo", description="bar")
        r = dut.tag_add(args)
        self.assertEqual(0, r)

        assert "foo" in dut.manifest.tags
        assert dut.manifest.tags["foo"].description == "bar"

    def assert_path_equal(self, expected_path: Path, actual_path: Path):
        self.assertTrue(actual_path.exists())
        self.assertEqual(expected_path.is_dir(), actual_path.is_dir())
        self.assertEqual(expected_path.is_file(), actual_path.is_file())
        self.assertEqual(expected_path.is_symlink(), actual_path.is_symlink())
        expected_stat = expected_path.stat()
        actual_stat = actual_path.stat()
        self.assertEqual(expected_stat.st_gid, actual_stat.st_gid)
        self.assertEqual(expected_stat.st_uid, actual_stat.st_uid)
        try:
            self.assertEqual(expected_stat.st_mode, actual_stat.st_mode)
        except AssertionError as e:
            print(
                f"Warning: mode of {expected_path}: expected {expected_stat.st_mode:o}, but was {actual_stat.st_mode:o}",
                sys.stderr,
            )


class Args:
    files = []
    force = 0

    def __init__(self, description=None, files=None, force=0, long=0, name=None):
        if files is None:
            files = []
        self.description = description
        self.files = files
        self.force = force
        self.long = long
        self.name = name
