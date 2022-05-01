import shutil
from pathlib import Path
from typing import List

import yaml

from hamstercage.hamstercage_exception import HamstercageException

"""
Manifest of files to be managed.
"""


class FileMode(int):
    pass


class Entry:
    mode: int
    group: str
    owner: str
    path: str
    target: str

    def __init__(self, path):
        self.path = path
        self.form = 'normal'
        self.mode = 0o644
        self.owner = 0
        self.group = 0
        self.target = None

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
                return DirEntry.from_dict(path, {
                    'mode': e.stat().st_mode & 0o7777,  # limit to standard POSIX bits
                    'owner': e.owner(),
                    'group': e.group(),
                })
            elif e.is_file():
                return FileEntry.from_dict(path, {
                    'target': e,
                    'mode': e.stat().st_mode & 0o7777,  # limit to standard POSIX bits
                    'owner': e.owner(),
                    'group': e.group(),
                })
            elif e.is_symlink():
                return SymlinkEntry.from_dict(path, {
                    'target': str(e.resolve())
                })
            raise HamstercageException(f'Unable to create entry for {path}: unknown file type')

        t = e.get('type', 'file')
        match t:
            case 'file':
                return FileEntry.from_dict(path, e)
            case _:
                raise Exception(f'Unknown entry type "{e["type"]}')

    def has_repo(self):
        """
        Returns true if this entry has a file in repo
        :return:
        """
        return False


class DirEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> 'DirEntry':
        e = DirEntry(path)
        if 'mode' in d:
            e.mode = d['mode']
        if 'owner' in d:
            e.owner = d['owner']
        if 'group' in d:
            e.group = d['group']
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
            'type': 'dir',
            'mode': f'{self.mode:#o}',
            'owner': self.owner,
            'group': self.group,
        }

    def __str__(self):
        return f'SymlinkEntry<form={self.form}, path={self.path}, target={self.target}>'


class FileEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> 'FileEntry':
        e = FileEntry(path)
        if 'target' in d:
            e.target = d['target']
        if 'mode' in d:
            e.mode = d['mode']
        if 'owner' in d:
            e.owner = d['owner']
        if 'group' in d:
            e.group = d['group']
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
            'type': 'file',
            'mode': f'{self.mode:#o}',
            'owner': self.owner,
            'group': self.group,
        }

    def has_repo(self):
        """
        Returns true if this entry has a file in repo
        :return:
        """
        return True

    def __str__(self):
        return f'FileEntry<form={self.form}, path={self.path}, mode={self.mode:#o}' \
               + ', owner={self.owner}, group={self.group}>'


class SymlinkEntry(Entry):
    def __init__(self, path):
        super().__init__(path)

    @staticmethod
    def from_dict(path: str, d: dict) -> 'SymlinkEntry':
        e = SymlinkEntry(path)
        if not 'target' in d:
            raise HamstercageException('missing target attribute for symlink')
        e.target = d['target']
        if 'mode' in d:
            e.mode = d['mode']
        if 'owner' in d:
            e.owner = d['owner']
        if 'group' in d:
            e.group = d['group']
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
            'type': 'link',
            'target': self.target,
        }

    def __str__(self):
        return f'SymlinkEntry<form={self.form}, path={self.path}, target={self.target}>'


class Host:
    """
    Represents one host in the manifest.
    """
    description: str = ''
    name: str
    tags: List[str] = ()

    def __init__(self, n: str) -> None:
        self.name = n
        pass

    @staticmethod
    def from_dict(n: str, d: dict) -> 'Host':
        host = Host(n)
        host.description = d.get('description', '')
        host.tags = d['tags']
        return host

    def to_dict(self) -> dict:
        return {
            'description': self.description,
            'tags': self.tags,
        }


class Tag:
    """
    Represents a tag definition in the manifest.
    """
    description: str = ''
    entries: dict[str, Entry]
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.description = ''
        self.entries = {}

    @staticmethod
    def from_dict(name: str, d: dict) -> 'Tag':
        tag = Tag(name)
        tag.description = d['description']
        for p, e in d['entries'].items():
            entry = Entry.entry(p, e)
            tag.entries[p] = entry
        return tag

    def to_dict(self) -> dict:
        d = {
            'description': self.description,
            'entries': {}
        }
        for (path, entry) in self.entries.items():
            d['entries'][path] = entry.to_dict()
        return d

    def __str__(self):
        return f'<Tag name={self.name} entries={len(self.entries)}>'


class Manifest:
    dir_mode: int
    file_mode: int
    group: int
    hosts: dict[str, Host]
    manifest_file: str
    owner: int
    tags: dict[str, Tag]

    def __init__(self, file: str) -> None:
        self.manifest_file = file
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
        self.dir_mode = self.file_mode | (self.file_mode & 0o0444) >> 2  # copy r bit to x bit
        self.entries = {}
        self.hosts = {}
        self.tags = {}
        for name, tag in manifest['tags'].items():
            self.tags[name] = Tag.from_dict(name, tag)
        for n, h in manifest['hosts'].items():
            host = Host.from_dict(n, h)
            self.hosts[n] = host

    def dump(self) -> None:
        """
        Save the manifest to the repository.
        :return:
        """
        manifest = {
            'hosts': {},
            'tags': {},
        }
        for name, entry in self.hosts.items():
            manifest['hosts'][name] = entry.to_dict()
        for name, entry in self.tags.items():
            manifest['tags'][name] = (entry.to_dict())
        with open(self.manifest_file, "w") as stream:
            yaml.dump(manifest, stream)

    @staticmethod
    def normalize_path(path):
        """
        Returns the normal form of a path
        :return:
        """
        if path.startswith('/'):
            path = path[1:]
        return path
