import grp
import os
import pwd
import textwrap
import unittest
from pathlib import Path

import pytest
import yaml

from ..__main__ import Hamstercage
from ..hamstercage_exception import HamstercageException
from ..manifest import FileEntry, Manifest, Tag


class TestHamstercage(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def initdir(self, tmpdir):
        self.tmpdir = tmpdir
        self.user = pwd.getpwuid(os.stat(self.tmpdir).st_uid).pw_name
        self.group = grp.getgrgid(os.stat(self.tmpdir).st_gid).gr_name

    def prepare_hamstercage(self) -> Hamstercage:
        dut = Hamstercage()
        dut.manifest_file = self.tmpdir / "hamstercage.yaml"
        dut.hostname = "testing.example.com"
        dut.target = Path(self.tmpdir) / "target"
        dut.repo = Path(self.tmpdir) / "repo"
        dut.init(None)
        os.chmod(dut.manifest_file, 0o664)
        dut.target.mkdir()
        return dut

    def manifest_with_hooks(self, hooks: dict) -> Manifest:
        manifest = {
            "hosts": {
                "testing.example.com": {"description": "testing hooks", "tags": ["all"]}
            },
            "tags": {
                "all": {
                    "description": "files that apply to all hosts",
                    "entries": {
                        "foo.txt": {
                            "group": self.group,
                            "mode": 0o644,
                            "owner": self.user,
                            "type": "file",
                        }
                    },
                    "hooks": hooks,
                }
            },
        }
        p = self.tmpdir / "with_hook.yaml"
        with open(p, "w") as stream:
            yaml.dump(manifest, stream)
        dut = Manifest(p)
        dut.load()
        return dut

    def test_FileEntry_from_dict(self):
        dut = FileEntry.from_dict(
            "foo",
            {
                "group": "wheel",
                "mode": 0o755,
                "owner": "root",
                "type": "file",
            },
        )
        assert dut.path == "foo"
        assert dut.group == "wheel"
        assert dut.mode == 0o755
        assert dut.owner == "root"

    def test_load_hook(self):
        dut = self.manifest_with_hooks(
            {
                "*": {
                    "command": "true",
                    "description": "a simple shell command",
                    "type": "shell",
                }
            }
        )

        assert "all" in dut.tags
        assert "*" in dut.tags["all"].hooks

        h = dut.tags["all"].hooks["*"]
        assert h.command == "true"
        assert h.description == "a simple shell command"
        assert h.type == "shell"

    def test_load_hook_invalid_type(self):
        with self.assertRaises(HamstercageException) as e:
            dut = self.manifest_with_hooks(
                {
                    "*": {
                        "command": "true",
                        "description": "a simple shell command",
                        "type": "foo",
                    }
                }
            )
        assert (
            e.exception.msg
            == 'In definition of hook "*": Invalid hook type "foo", must be one of exec, python, shell'
        )

    def hook_exec(self, command: str, script: Path):
        dut = self.manifest_with_hooks(
            {
                "*": {
                    "command": command,
                    "description": "a simple shell command",
                    "type": "exec",
                }
            }
        )
        assert "all" in dut.tags
        assert "*" in dut.tags["all"].hooks

        script.write_text(
            textwrap.dedent(
                f"""\
                #!/bin/sh
                set -e
                test "$1" = "apply"
                test "$2" = "post"
                test "$3" = "all"
                test "$HAMSTERCAGE_CMD" = "apply"
                test "$HAMSTERCAGE_HOOK" = "*"
                test "$HAMSTERCAGE_MANIFEST" = "{dut.manifest_file}"
                test "$HAMSTERCAGE_REPO" = "{str(Path(dut.manifest_file).parent)}"
                test "$HAMSTERCAGE_STEP" = "post"
                test "$HAMSTERCAGE_TAG" = "all"
                """
            ),
            "utf-8",
        )
        os.chmod(script, 0o755)

        h = dut.tags["all"].hooks["*"]
        r = h.call(dut, "apply", "post", dut.tags["all"])
        assert r == 0

    def test_run_hook_exec_absolute(self):
        self.hook_exec(str(self.tmpdir / "exec_test.sh"), self.tmpdir / "exec_test.sh")

    def test_run_hook_exec_relative(self):
        self.hook_exec("exec_test.sh", self.tmpdir / "exec_test.sh")

    def run_hook_python(self, python: str):
        script = self.tmpdir / "python_hook"
        dut = self.manifest_with_hooks(
            {
                "*": {
                    "command": "python_hook",
                    "description": "a simple shell command",
                    "type": "python",
                }
            }
        )
        assert "all" in dut.tags
        assert "*" in dut.tags["all"].hooks

        script.write_text(
            python,
            "utf-8",
        )
        return dut

    def test_run_hook_python_success(self):
        dut = self.run_hook_python(
            textwrap.dedent(
                f"""
                assert cmd == "apply"
                assert manifest is not None
                assert hook == "*"
                assert repo == "{self.tmpdir}"
                assert step == "post"
                assert tag.name == "all"
                print(__file__)
                assert __name__ == "__hamstercage__"
                """
            )
        )

        h = dut.tags["all"].hooks["*"]
        r = h.call(dut, "apply", "post", dut.tags["all"])
        assert r == 0

    def test_run_hook_python_syntax_error(self):
        dut = self.run_hook_python(
            textwrap.dedent(
                f"""
                in == valid
                """
            )
        )

        h = dut.tags["all"].hooks["*"]
        with self.assertRaises(HamstercageException) as e:
            r = h.call(dut, "apply", "post", dut.tags["all"])
        assert (
            e.exception.msg
            == 'Error executing hook "*" Python command "python_hook" line 2::\n\tin == valid'
        )

    def test_run_hook_shell_false(self):
        dut = self.manifest_with_hooks(
            {
                "*": {
                    "command": "true && false",
                    "description": "a simple shell command",
                    "type": "shell",
                }
            }
        )
        assert "all" in dut.tags
        assert "*" in dut.tags["all"].hooks

        h = dut.tags["all"].hooks["*"]
        with self.assertRaises(HamstercageException) as e:
            r = h.call(dut, "apply", "post", dut.tags["all"])
        assert (
            e.exception.msg
            == 'Error executing hook "*" "true && false": command exited with 1'
        )

    def test_run_hook_shell_true(self):
        dut = self.manifest_with_hooks(
            {
                "*": {
                    "command": "true && true",
                    "description": "a simple shell command",
                    "type": "shell",
                }
            }
        )
        assert "all" in dut.tags
        assert "*" in dut.tags["all"].hooks

        h = dut.tags["all"].hooks["*"]
        r = h.call(dut, "apply", "post", dut.tags["all"])
        assert r == 0

    def test_tag_find_hook_with_star(self):
        dut = Tag.from_dict(
            "all",
            {
                "hooks": {
                    "pre-add": {
                        "command": "pre-add",
                        "type": "shell",
                    },
                    "*-apply": {
                        "command": "star-apply",
                        "type": "shell",
                    },
                    "post-*": {
                        "command": "post-star",
                        "type": "shell",
                    },
                    "*": {
                        "command": "star",
                        "type": "shell",
                    },
                }
            },
        )

        h = dut.find_hook("add", "pre")
        assert h is not None and h.command == "pre-add"
        h = dut.find_hook("apply", "pre")
        assert h is not None and h.command == "star-apply"
        h = dut.find_hook("add", "post")
        assert h is not None and h.command == "post-star"
        h = dut.find_hook("list", "pre")
        assert h is not None and h.command == "star"

    def test_tag_find_hook_no_star(self):
        dut = Tag.from_dict(
            "all",
            {
                "hooks": {
                    "pre-add": {
                        "command": "pre-add",
                        "type": "shell",
                    },
                    "post-apply": {
                        "command": "post-apply",
                        "type": "shell",
                    },
                }
            },
        )

        h = dut.find_hook("add", "pre")
        assert h is not None and h.command == "pre-add"
        h = dut.find_hook("apply", "post")
        assert h is not None and h.command == "post-apply"
        h = dut.find_hook("add", "post")
        assert h is None
        h = dut.find_hook("list", "pre")
        assert h is None
