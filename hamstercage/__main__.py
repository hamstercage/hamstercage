import argparse
import os
import shutil
import socket
import sys
from datetime import datetime
from difflib import unified_diff
from pathlib import Path

from yaml.scanner import ScannerError

from hamstercage import Manifest
from hamstercage.hamstercage_exception import HamstercageException
from hamstercage.manifest import FileEntry, Host, Tag, Entry


class Hamstercage:
    target: Path
    manifest_file: Path
    files: list[str]
    hostname: str
    repo: Path
    tags: list[str]

    def __init__(self):
        self.target = Path('/')
        self.manifest_file = Path('hamstercage.yaml')
        self.files = []
        self.hostname = socket.gethostname()
        self.repo = Path('.')
        self.tags = []

    def main(self):
        parser = argparse.ArgumentParser(prog='hamstercage', description='Manage the hamster cage.')
        parser.add_argument('-d', '--directory', type=Path, default='/', help='base directory of target files')
        parser.add_argument('-f', '--file', type=Path, default='hamstercage.yaml', help='manifest file to use')
        parser.add_argument('-r', '--repo', type=Path, default='.', help='directory of file repo')
        parser.add_argument('-t', '--tag', type=str, help='tags to apply/save')
        parser.add_argument('-n', '--hostname', default=socket.gethostname(), help='name of this host')
        parser.set_defaults(func=None)

        subparsers = parser.add_subparsers(help='sub-command help')

        subparser = subparsers.add_parser('add', help='add one or more files to the manifest')
        subparser.set_defaults(func=self.add)
        subparser.add_argument('-A', '--allhosts', action='count', default=0, help='copy file to the all repository')
        subparser.add_argument('files', nargs='+', help='files to add')

        subparser = subparsers.add_parser('apply', help='apply files from repo to target')
        subparser.set_defaults(func=self.apply)
        subparser.add_argument('files', nargs='*', help='limit results to these file patterns')

        subparser = subparsers.add_parser('diff', help='print differences between target and repo')
        subparser.set_defaults(func=self.diff)
        subparser.add_argument('files', nargs='*', help='limit results to these file patterns')

        subparser = subparsers.add_parser('init', help='create a new manifest')
        subparser.set_defaults(func=self.init)

        subparser = subparsers.add_parser('list', aliases=['ls'], help='list manifest entries')
        subparser.set_defaults(func=self.list)
        subparser.add_argument('-l', '--long', action='count', default=0, help='list format long')
        subparser.add_argument('files', nargs='*', help='limit results to these file patterns')

        subparser = subparsers.add_parser('save', help='save target files to repo')
        subparser.set_defaults(func=self.save)
        subparser.add_argument('files', nargs='*', help='limit results to these file patterns')

        args = parser.parse_args()

        if args.func:
            self.target = args.directory
            self.manifest_file = args.file
            self.hostname = args.hostname
            self.repo = args.repo
            if args.tag:
                self.tags = [args.tag]

            try:
                return args.func(args)
            except HamstercageException as e:
                print(f'{e}', file=sys.stderr)
                return e.exit_code
        parser.print_help()
        return 64

    def add(self, args):
        """
        Add one or more entries to the manifest.
        :param args:
        :return:
        """
        self._load_manifest()
        if len(args.files) == 0:
            raise HamstercageException(f'Need at least one file to add', 64)
        if len(self.tags) != 1:
            raise HamstercageException(f'Need to specify exactly one tag to add files to', 64)

        for file in args.files:
            entry = self._add(file, self.tags[0])
            if entry.has_repo():
                repo = self._path_repo_absolute(self.tags[0], entry)
                try:
                    self._mkdir_repo(self._path_repo_relative(self.tags[0], entry).parent)
                    shutil.copy2(entry.target, repo, follow_symlinks=False)
                except FileNotFoundError as e:
                    print(f'Unable to add {file}: {e}', file=sys.stderr)
                    return(71)
        self.manifest.dump()
        return 0

    def apply(self, args):
        """
        Copy (all/matching) manifest entries from the repo to the target.
        :return:
        """
        self._load_manifest()
        for t in self.tags:
            for p, e in self.manifest.entries.items():
                if not self._files_match(e):
                    continue
                target = self._path_target(e)
                repo = self._path_repo_absolute(t, e)
                shutil.copy2(repo, target, follow_symlinks=False)
                os.chmod(target, e.mode, follow_symlinks=False)
                shutil.chown(target, e.owner, e.group)
        return 0

    def diff(self, args):
        self._load_manifest()
        has_diff = False
        self.files = args.files

        for (target, repo) in self._files().items():
            if target.exists() and repo.exists():
                diff = list(self._diff(target, repo))
                sys.stdout.writelines(diff)
                if diff:
                    has_diff = True
            else:
                if self._mtime_or_missing(repo, '---'):
                    has_diff = True
                if self._mtime_or_missing(target, '+++'):
                    has_diff = True
        return 1 if has_diff else 0

    def init(self, args) -> int:
        """
        Create a manifest file. Throw an error if the file already exists.
        :return:
        """
        if self.manifest_file.exists():
            raise HamstercageException(f'manifest file "{self.manifest_file}" already exists', 1)
        manifest = Manifest(self.manifest_file)
        manifest.hosts[self.hostname] = Host(self.hostname)
        manifest.hosts[self.hostname].tags = ['all']
        manifest.tags = {'all': Tag.from_dict('all', {
            'description': 'files that apply to all hosts',
            'entries': {}
        })}
        manifest.dump()
        return 0

    def list(self, args):
        """
        Print a list of all manifest entries
        :return:
        """
        self._load_manifest()
        self.files = args.files
        for (target, repo) in self._files().items():
            if args.long > 0:
                print(f'{target} -> {repo}')
            else:
                print(f'{target}')
        return 0

    def save(self, args):
        """
        Copy (all/matching) manifest entries from the target to the repo.
        :return:
        """
        self._load_manifest()
        for (target, repo) in self._files().items():
            shutil.copy2(target, repo, follow_symlinks=False)
        return 0

    def _add(self, path: str, tag: str, ignore_existing=False):
        if tag not in self.manifest.tags:
            raise HamstercageException(f'no tag {tag} in manifest')
        entries = self.manifest.tags[tag].entries
        target_path = self.target / path
        entry = Entry.entry(path, target_path)
        if entry.path in entries and not ignore_existing:
            raise HamstercageException(f'Unable to add {path}: already added')
        entries[path] = entry
        return entry

    @staticmethod
    def _diff(target, repo):
        with open(target) as f:
            t = f.readlines()
        with open(repo) as f:
            r = f.readlines()
        return unified_diff(r, t, fromfile=str(repo), fromfiledate=Hamstercage._mtime(repo), tofile=str(target),
                            tofiledate=Hamstercage._mtime(target))

    @staticmethod
    def _exists_status(path):
        return ' ' if path else '!'

    def _files_match(self, entry):
        if len(self.files) == 0:
            return True
        for f in self.files:
            if Path(entry.path).match(f):
                return True
        return False

    def _files(self) -> dict[Path, Path]:
        """
        Builds a list of files that should be processed. Resolved duplicate entries consistently.
        :return:
        """
        files: dict[Path, Path] = {}
        for t in self.tags:
            for p, e in self.manifest.tags[t].entries.items():
                if not self._files_match(e):
                    continue
                files[self._path_target(e)] = self._path_repo_absolute(t, e)
        return files

    @staticmethod
    def _mtime(path):
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    def _mtime_or_missing(self, path, prefix):
        if path.exists():
            print(f'{prefix} {str(path)}\t{self._mtime(path)}')
            return False
        print(f'{prefix} {str(path)}\tmissing')
        return True

    def _load_manifest(self):
        try:
            self.manifest = Manifest(str(self.manifest_file))
            self.manifest.load()
            if len(self.tags) == 0:
                if self.hostname in self.manifest.hosts:
                    self.tags = self.manifest.hosts[self.hostname].tags
                else:
                    print(f'Warning: No hostname entry for {self.hostname}', file=sys.stderr)
        except FileNotFoundError as e:
            raise HamstercageException(f'Unable to load manifest from "{self.manifest_file}": {e}', 71)
        except ScannerError as e:
            raise HamstercageException(f'Unable to load manifest from "{self.manifest_file}": {e}', 71)

    def _path_repo_absolute(self, tag: str, entry: Entry):
        return self.repo.joinpath(self._path_repo_relative(tag, entry))

    def _path_repo_relative(self, tag: str, entry: Entry):
        return Path("tags") / tag / entry.path

    def _path_target(self, entry: Entry):
        return self.target.joinpath(entry.path)

    def _mkdir_repo(self, path: Path) -> None:
        """
        Create a directory in the repo, copying owner/group/mode from the manifest file
        :param path:
        :return:
        """
        if str(path) != '.':
            self._mkdir_repo(path.parent)
        p = self.repo.joinpath(path)
        if not p.exists():
            p.mkdir(mode=self.manifest.dir_mode)
            os.chmod(str(p), self.manifest.dir_mode, follow_symlinks=False)
            shutil.chown(str(p), self.manifest.owner, self.manifest.group)



def main():
    h = Hamstercage()
    sys.exit(h.main())


if __name__ == '__main__':
    main()
