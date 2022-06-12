import os
import shutil
import subprocess
import sys
import textwrap
import traceback
from abc import ABC
from pathlib import Path
from typing import List

import yaml

from hamstercage.hamstercage_exception import HamstercageException
from hamstercage.utils import chmod

"""
Manifest of files to be managed.
"""


class FileMode(int):
    pass


class Entry(ABC):
    mode: int
    group: str
    owner: str
    path: str
    target: str

    def __init__(self, path):
        self.path = path
        self.form = "normal"
        self.mode = 0o644
        self.owner = "root"
        self.group = "root"
        self.target = ""

    @staticmethod
    def entry(path: str, e):
        """
        Create a new entry.
        :param path: the relative path of the entry,
        :param e: a dict or Path describing the file to be added
        :return:
        """
        if isinstance(e, Path):
            if e.is_dir():
                return DirEntry.from_dict(
                    path,
                    {
                        "mode": e.stat().st_mode
                        & 0o7777,  # limit to standard POSIX bits
                        "owner": e.owner(),
                        "group": e.group(),
                    },
                )
            elif e.is_file():
                return FileEntry.from_dict(
                    path,
                    {
                        "target": e,
                        "mode": e.stat().st_mode
                        & 0o7777,  # limit to standard POSIX bits
                        "owner": e.owner(),
                        "group": e.group(),
                    },
                )
            elif e.is_symlink():
                return SymlinkEntry.from_dict(path, {"target": str(e.resolve())})
            raise HamstercageException(
                f'Unable to create entry for "{path}": unknown file type'
            )

        t = e.get("type", "file")
        if t == "dir":
            return DirEntry.from_dict(path, e)
        elif t == "file":
            return FileEntry.from_dict(path, e)
        elif t == "link":
            return SymlinkEntry.from_dict(path, e)
        else:
            raise HamstercageException(f'Unknown entry type "{e["type"]}"')

    def has_repo(self):
        """
        Returns true if this entry has a file in repo
        :return:
        """
        return False

    def apply(self, repo: Path, target: Path):
        """
        Apply the entry to the target dir.
        :param repo: Repo base dir
        :param target: Target base dir
        :return:
        """
        raise HamstercageException(f"class {self} does not implement apply()")

    def path_as_child_of(self, target_path: Path) -> Path:
        """
        Returns the entry path as a child of target_path.
        :param target_path: the base path
        :return: path
        """
        path = str(self.path)
        if path.startswith("/"):
            path = path[1:]
        return target_path / path


class DirEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> "DirEntry":
        e = DirEntry(path)
        if "mode" in d:
            e.mode = d["mode"]
        if "owner" in d:
            e.owner = d["owner"]
        if "group" in d:
            e.group = d["group"]
        if isinstance(e.mode, str):
            e.mode = int(e.mode, 8)
        e.path = Manifest.normalize_path(e.path)
        return e

    def to_dict(self):
        """
        Returns a dict representing this entry.
        :return:
        """
        return {
            "type": "dir",
            "mode": f"{self.mode:#o}",
            "owner": self.owner,
            "group": self.group,
        }

    def apply(self, repo: Path, target: Path):
        if target.exists() and not target.is_dir():
            raise HamstercageException(
                f'Unable to update "{target}" because it exists and is not a directory'
            )
        target.mkdir(self.mode, exist_ok=True, parents=True)
        shutil.chown(str(target), self.owner, self.group)

    def __str__(self):
        return f"SymlinkEntry<form={self.form}, path={self.path}, target={self.target}>"


class FileEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> "FileEntry":
        e = FileEntry(path)
        if "target" in d:
            e.target = d["target"]
        if "mode" in d:
            e.mode = d["mode"]
        if "owner" in d:
            e.owner = d["owner"]
        if "group" in d:
            e.group = d["group"]
        if isinstance(e.mode, str):
            e.mode = int(e.mode, 8)
        e.path = Manifest.normalize_path(e.path)
        return e

    def to_dict(self):
        """
        Returns a dict representing this entry.
        :return:
        """
        return {
            "type": "file",
            "mode": f"{self.mode:#o}",
            "owner": self.owner,
            "group": self.group,
        }

    def has_repo(self):
        """
        Returns true if this entry has a file in repo
        :return:
        """
        return True

    def apply(self, repo: Path, target: Path):
        if target.exists() and not target.is_file():
            raise HamstercageException(
                f'Unable to update "{target}" because it exists and is not a file'
            )
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(str(repo), str(target))
        chmod(str(target), self.mode)
        shutil.chown(str(target), self.owner, self.group)

    def __str__(self):
        return (
            f"FileEntry<form={self.form}, path={self.path}, mode={self.mode:#o}"
            + ", owner={self.owner}, group={self.group}>"
        )


class SymlinkEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> "SymlinkEntry":
        e = SymlinkEntry(path)
        if not "target" in d:
            raise HamstercageException("missing target attribute for symlink")
        e.target = d["target"]
        if "mode" in d:
            e.mode = d["mode"]
        if "owner" in d:
            e.owner = d["owner"]
        if "group" in d:
            e.group = d["group"]
        if isinstance(e.mode, str):
            e.mode = int(e.mode, 8)
        e.path = Manifest.normalize_path(e.path)
        return e

    def to_dict(self):
        """
        Returns a dict representing this entry.
        :return:
        """
        return {
            "type": "link",
            "target": self.target,
        }

    def apply(self, repo: Path, target: Path):
        if target.exists() and not target.is_symlink():
            raise HamstercageException(
                f'Unable to update "{target}" because it exists and is not a symbolic link'
            )
        target.parent.mkdir(exist_ok=True, parents=True)
        if target.exists():
            target.unlink()
        target.symlink_to(self.target)

    def __str__(self):
        return f"SymlinkEntry<form={self.form}, path={self.path}, target={self.target}>"


class Host:
    """
    Represents one host in the manifest.
    """

    description: str
    name: str
    tags: List[str]

    def __init__(self, n: str) -> None:
        self.description = ""
        self.name = n
        self.tags = []
        pass

    @staticmethod
    def from_dict(n: str, d: dict) -> "Host":
        host = Host(n)
        if "description" in d:
            host.description = d.get("description", "")
        if not "tags" in d:
            raise HamstercageException(
                f'Invalid host definition for "{n}": must have a list of tags'
            )
        host.tags = d["tags"]
        return host

    def to_dict(self) -> dict:
        d = {"tags": self.tags}
        if len(self.description) > 0:
            d["description"] = self.description
        return d


class Hook:
    """
    Represents one hook in a tag.
    """

    command: str
    description: str
    name: str
    type: str

    valid_types = ["exec", "python", "shell"]

    def __init__(self, name: str):
        pass

    @staticmethod
    def from_dict(name: str, d: dict) -> "Hook":
        hook = Hook(name)
        if "command" not in d:
            raise HamstercageException(
                f'In definition of hook "{hook.name}": missing "command"'
            )
        hook.command = d["command"]
        hook.description = d.get("description", "")
        hook.name = name
        hook.type = d["type"]
        if hook.type not in Hook.valid_types:
            raise HamstercageException(
                f'In definition of hook "{hook.name}": Invalid hook type "{hook.type}", must be one of {", ".join(Hook.valid_types)}'
            )
        return hook

    def to_dict(self) -> dict:
        d = {
            "command": self.command,
            "description": self.description,
            "type": self.type,
        }
        return d

    def call(self, manifest: "Manifest", cmd: str, step: str, tag: "Tag") -> int:
        if self.type == "exec":
            return self._call_shell(
                [str(self._get_path(manifest)), cmd, step, tag.name],
                manifest,
                cmd,
                step,
                tag,
                shell=False,
            )
        elif self.type == "python":
            return self._call_python(manifest, cmd, step, tag)
        elif self.type == "shell":
            return self._call_shell(
                [self.command], manifest, cmd, step, tag, shell=True
            )
        else:
            raise HamstercageException(
                f'In definition of hook "{self.name}": Invalid hook type "{self.type}", must be one of {", ".join(Hook.valid_types)}'
            )

    def _call_python(self, manifest: "Manifest", cmd: str, step: str, tag: "Tag"):
        path = self._get_path(manifest)
        globals = {
            "cmd": cmd,
            "manifest": manifest,
            "hook": self.name,
            "repo": str(Path(manifest.manifest_file).parent),
            "step": step,
            "tag": tag,
            "__file__": str(path),
            "__name__": "__hamstercage__",
        }
        script = path.read_text("utf-8")
        try:
            exec(script, globals)
            return 0
        except SyntaxError as e:
            lines = script.split("\n")
            raise HamstercageException(
                f'Error executing hook "{self.name}" Python command "{self.command}" line {e.lineno}::\n\t{lines[e.lineno - 1]}'
            )
        except Exception as e:
            _, _, tb = sys.exc_info()
            tb_info = traceback.extract_tb(tb)
            filename, line, func, text = tb_info[-1]
            lines = script.split("\n")
            print(
                textwrap.dedent(
                    f"""
                            Error executing hook "{self.name}" Python command "{self.command}" line {line}: {e.__class__.__name__}{e.args}
                            \t{lines[line - 1]}
                            """
                ),
                file=sys.stderr,
            )
            return 1

    def _call_shell(
        self,
        args: [],
        manifest: "Manifest",
        cmd: str,
        step: str,
        tag: "Tag",
        shell: bool,
    ):
        env = dict(os.environ)
        env["HAMSTERCAGE_CMD"] = cmd
        env["HAMSTERCAGE_MANIFEST"] = manifest.manifest_file
        env["HAMSTERCAGE_HOOK"] = self.name
        env["HAMSTERCAGE_REPO"] = str(Path(manifest.manifest_file).parent)
        env["HAMSTERCAGE_STEP"] = step
        env["HAMSTERCAGE_TAG"] = tag.name
        r = subprocess.call(args, env=env, shell=shell)
        if r != 0:
            raise HamstercageException(
                f'Error executing hook "{self.name}" "{" ".join(args)}": command exited with {r}',
                r,
            )
        return 0

    def _get_path(self, manifest: "Manifest"):
        path = Path(self.command)
        if not path.is_absolute():
            path = Path(manifest.manifest_file).parent / path
        return path


class Tag:
    """
    Represents a tag definition in the manifest.
    """

    description: str
    entries: {}
    hooks: {}
    name: str

    def __init__(self, name: str, description=None) -> None:
        self.name = name
        self.description = ""
        if description is not None:
            self.description = description
        self.entries = {}
        self.hooks = {}

    @staticmethod
    def from_dict(name: str, d: dict) -> "Tag":
        tag = Tag(name)
        if "description" in d:
            tag.description = d["description"]
        if "entries" in d:
            for p, e in d["entries"].items():
                entry = Entry.entry(p, e)
                tag.entries[p] = entry
        if "hooks" in d:
            for p, e in d["hooks"].items():
                entry = Hook.from_dict(p, e)
                tag.hooks[p] = entry
        return tag

    def to_dict(self) -> dict:
        d = {}
        if len(self.description) > 0:
            d["description"] = self.description
        if len(self.entries) > 0:
            d["entries"] = {}
            for (path, entry) in self.entries.items():
                d["entries"][path] = entry.to_dict()
        if len(self.hooks) > 0:
            d["hooks"] = {}
            for (path, entry) in self.hooks.items():
                d["hooks"][path] = entry.to_dict()
        return d

    def find_hook(self, command: str, step: str) -> Hook:
        """
        Find the best match hook for this command and step. If no such hook is defined, return None.
        :param command:
        :param step:
        :return:
        """
        hook = None
        for n in (f"{step}-{command}", f"*-{command}", f"{step}-*", "*"):
            hook = self.hooks.get(n)
            if hook:
                break
        return hook

    def __str__(self):
        return f"<Tag name={self.name} entries={len(self.entries)}>"


class Manifest:
    dir_mode: int
    file_mode: int
    group: int
    hosts: dict
    manifest_file: str
    owner: int
    tags: dict

    def __init__(self, file: str) -> None:
        self.manifest_file = str(file)
        self.hosts = {}
        self.tags = {}

    def load(self) -> None:
        """
        Load the manifest from the repository.
        :return:
        """
        with open(self.manifest_file, "r") as stream:
            manifest = yaml.safe_load(stream)
        mp = Path(self.manifest_file)
        mst = mp.stat()
        self.owner = mst.st_uid
        self.group = mst.st_gid
        self.file_mode = mst.st_mode
        self.dir_mode = (
            self.file_mode | (self.file_mode & 0o0444) >> 2
        )  # copy r bit to x bit
        self.hosts = {}
        self.tags = {}
        for name, tag in manifest["tags"].items():
            self.tags[name] = Tag.from_dict(name, tag)
        for n, h in manifest["hosts"].items():
            host = Host.from_dict(n, h)
            self.hosts[n] = host

    def dump(self) -> None:
        """
        Save the manifest to the repository.
        :return:
        """
        manifest = {
            "hosts": {},
            "tags": {},
        }
        for name, entry in self.hosts.items():
            manifest["hosts"][name] = entry.to_dict()
        for name, entry in self.tags.items():
            manifest["tags"][name] = entry.to_dict()
        with open(self.manifest_file, "w") as stream:
            yaml.dump(manifest, stream)

    @staticmethod
    def normalize_path(path):
        """
        Returns the normal form of a path
        :return:
        """
        path = str(path)
        if path.endswith("/"):
            path = path[0:-1]
        return path
