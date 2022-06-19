import argparse
import os
import shutil
import socket
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Iterator, Union

import sys
from yaml.scanner import ScannerError

from hamstercage import Manifest
from hamstercage.hamstercage_exception import HamstercageException
from hamstercage.manifest import Host, Tag, Entry, DirEntry, SymlinkEntry, FileEntry
from hamstercage.utils import (
    chmod,
    mode_to_str,
    short_date,
    print_table,
    ListEntry,
    path_as_child_of,
)


class Hamstercage:
    """
    The main progam. Parses command line arguments and invokes sub-commands.
    """

    target: Path
    manifest_file: Path
    files: list
    hostname: str
    repo: Path
    tags: list

    def __init__(self):
        self.files = []
        self.hostname = socket.gethostname()
        self.manifest = None
        self.manifest_file = Path("hamstercage.yaml")
        self.repo = Path(".")
        self.tags = []
        self.target = Path("/")

    def main(self, args=None):
        if args is None:
            args = sys.argv[1:]
        parser = argparse.ArgumentParser(
            prog="hamstercage", description="Manage the hamster cage."
        )
        parser.add_argument(
            "-d",
            "--directory",
            type=Path,
            default="/",
            help="base directory of target files",
        )
        parser.add_argument(
            "-f",
            "--file",
            type=Path,
            default="hamstercage.yaml",
            help="manifest file to use",
        )
        parser.add_argument(
            "-n", "--hostname", default=socket.gethostname(), help="name of this host"
        )
        parser.add_argument(
            "-r", "--repo", type=Path, default=".", help="directory of file repo"
        )
        parser.add_argument("-t", "--tag", type=str, help="tags to apply/save")
        parser.add_argument(
            "-v", "--verbose", action="count", default=0, help="verbose output"
        )
        parser.set_defaults(func=None)

        subparsers = parser.add_subparsers(help="sub-command help")

        subparser = subparsers.add_parser(
            "add", help="add one or more files to the manifest"
        )
        subparser.set_defaults(func=self.add)
        subparser.add_argument(
            "-f",
            "--force",
            action="count",
            default=0,
            help="overwrite existing entries",
        )
        subparser.add_argument("tag", help="tag to add files to")
        subparser.add_argument("files", nargs="+", help="files to add")

        subparser = subparsers.add_parser(
            "apply", help="apply files from repo to target"
        )
        subparser.set_defaults(func=self.apply)
        subparser.add_argument(
            "files", nargs="*", help="limit results to these file patterns"
        )

        subparser = subparsers.add_parser(
            "diff", help="print differences between target and repo"
        )
        subparser.set_defaults(func=self.diff)
        subparser.add_argument(
            "files", nargs="*", help="limit results to these file patterns"
        )

        subparser = subparsers.add_parser("init", help="create a new manifest")
        subparser.set_defaults(func=self.init)

        subparser = subparsers.add_parser(
            "list", aliases=["ls"], help="list manifest entries"
        )
        subparser.set_defaults(func=self.list)
        subparser.add_argument(
            "-l", "--long", action="count", default=0, help="list format long"
        )
        subparser.add_argument(
            "-t",
            "--tabs",
            action="count",
            default=0,
            help="separate columns with tabs instead of spaces",
        )
        subparser.add_argument(
            "files", nargs="*", help="limit results to these file patterns"
        )

        subparser = subparsers.add_parser(
            "remove",
            aliases=["del", "rm"],
            help="remove one or more files from the manifest",
        )
        subparser.set_defaults(func=self.remove)
        subparser.add_argument("tag", help="tag to add files to")
        subparser.add_argument("files", nargs="+", help="files to remove")

        subparser = subparsers.add_parser("save", help="save target files to repo")
        subparser.set_defaults(func=self.save)
        subparser.add_argument(
            "files", nargs="*", help="limit results to these file patterns"
        )

        subparser = subparsers.add_parser(
            "tag",
            help="manage tags in the manifest",
        )
        subparser.set_defaults(func=None)

        tagparsers = subparser.add_subparsers(help="tag command help")

        subparser = tagparsers.add_parser(
            "tag",
            help="manage tags in the manifest",
        )
        subparser.set_defaults(func=self.tag_add)
        subparser.add_argument("name", nargs=1, help="tag name")
        subparser.add_argument(
            "-d",
            "--description",
            type=str,
            default="",
            help="description for this tag",
        )

        args = parser.parse_args(args)

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
                print(f"{e}", file=sys.stderr)
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
        if len(args.files) < 1:
            raise HamstercageException(f"Need at least one file to add", 64)

        self._run_hook(args.tag, "add", "pre")
        for file in args.files:
            entry = self._add_entry(args.tag, file, ignore_existing=args.force > 0)
            self._save_entry(args.tag, entry)
        self._run_hook(args.tag, "add", "post")
        self.manifest.dump()
        return 0

    def apply(self, args):
        """
        Copy (all/matching) manifest entries from the repo to the target.
        :return:
        """
        self._load_manifest()
        self._run_hooks("apply", "pre")
        for t, e in self._entries():
            e.apply(self._path_repo_entry(t, e), self._path_target(e))
        self._run_hooks("apply", "post")
        return 0

    def diff(self, args):
        self._load_manifest()
        has_diff = False
        self.files = args.files

        self._run_hooks("diff", "pre")
        for t, e in self._entries():
            repo = self._path_repo_entry(t, e)
            target = self._path_target(e)
            if not repo.is_file():
                continue  # non-files don't have a file under tags
            if target.exists() and repo.exists():
                diff = list(self._diff(target, repo))
                sys.stdout.writelines(diff)
                if diff:
                    has_diff = True
            else:
                if self._mtime_or_missing(repo, "---"):
                    has_diff = True
                if self._mtime_or_missing(target, "+++"):
                    has_diff = True
        self._run_hooks("diff", "post")
        return 1 if has_diff else 0

    def init(self, args) -> int:
        """
        Create a manifest file. Throw an error if the file already exists.
        :return:
        """
        if self.manifest_file.exists():
            raise HamstercageException(
                f'manifest file "{self.manifest_file}" already exists', 1
            )
        manifest = Manifest(str(self.manifest_file))
        manifest.hosts[self.hostname] = Host(self.hostname)
        manifest.hosts[self.hostname].tags = ["all"]
        manifest.tags = {
            "all": Tag.from_dict(
                "all", {"description": "files that apply to all hosts", "entries": {}}
            )
        }
        manifest.dump()
        return 0

    def list(self, args, file=None):
        """
        Print a list of all manifest entries
        :return:
        """
        if file is None:
            out = sys.stdout
        self._load_manifest()
        self.files = args.files
        items = {}
        for t, e in self._entries():
            repo = self._path_repo_entry(t, e)
            target = self._path_target(e)
            if target not in items:
                items[target] = ListEntry(e, repo, t)
        if args.long == 0:
            for path in sorted(items):
                print(path, file=file)
        else:
            lines = []
            for path in sorted(items):
                item = items[path]
                entry = item.entry
                mtime = "?"
                name = str(path)
                size = "0"
                status = " "
                type = "-"
                if path.exists():
                    stat = path.stat()
                    mtime = short_date(int(stat.st_mtime))
                    if path.is_file():
                        size = str(stat.st_size)
                else:
                    status = "!"
                if isinstance(entry, FileEntry):
                    if path.exists() and list(self._diff(path, item.repo)):
                        status = "*"
                elif isinstance(entry, DirEntry):
                    name = name + "/"
                    type = "d"
                elif isinstance(entry, SymlinkEntry):
                    name = name + " -> " + entry.target
                    type = "l"
                    if path.exists() and os.readlink(path) != entry.target:
                        status = "*"
                lines.append(
                    [
                        status,
                        mode_to_str(type, entry.mode),
                        entry.owner,
                        entry.group,
                        size,
                        mtime,
                        item.tag,
                        name,
                    ]
                )
            print_table(lines, align=["<", "<", "<", "<", ">"], file=file)
        # widths = [0] * 8
        # align = ["<", "<", "<", "<", ">", "<", "<", "<"]
        # for line in lines:
        #     for i in range(0, len(line)):
        #         widths[i] = max(widths[i], len(line[i]))
        # fs = []
        # for i in range(0, len(widths) - 1):
        #     fs.append(f"{{{i}:{align[i]}{widths[i]}}}")
        #     # f = f + f"{{0:{widths[i]}.{widths[i]}s}}"
        # fs.append(f"{{{len(widths)-1}}}")
        # for line in lines:
        #     # print("{0:} {1:}".format(*line), file=out)
        #     print(" ".join(fs).format(*line), file=out)
        return 0

    def remove(self, args):
        """
        Remove one or more entries from the manifest.
        :param args:
        :return:
        """
        self._load_manifest()
        if len(args.files) < 1:
            raise HamstercageException(f"Need at least one file to remove", 64)

        for file in args.files:
            if file in self.manifest.tags[args.tag].entries:
                repo = self._path_repo_entry(
                    args.tag, self.manifest.tags[args.tag].entries[file]
                )
                del self.manifest.tags[args.tag].entries[file]
                repo.unlink(missing_ok=True)
            else:
                print(
                    f"Unable to remove {file}: no such entry in tag {args.tag}",
                    file=sys.stderr,
                )
                return 71
        self.manifest.dump()
        return 0

    def save(self, args):
        """
        Copy (all/matching) manifest entries from the target to the repo.
        :return:
        """
        self._load_manifest()
        self._run_hooks("save", "pre")
        for tag, entry in self._entries():
            self._save_entry(tag, entry)
        self._run_hooks("save", "post")
        return 0

    def tag_add(self, args):
        self._load_manifest()
        if args.name in self.manifest.tags:
            raise HamstercageException(f"A tag named f{args.name} already exists")
        self.manifest.tags[args.name] = Tag(args.name, args.description)
        self.manifest.dump()
        return 0

    def _add_entry(
        self,
        tag: str,
        file,
        ignore_existing=False,
    ) -> Entry:
        """
        Add a new file to, or update its contents and attributes in the repo.

        By default, it is an error if the repo file exists, and no error if the repo file doesn't exist.

        :param tag: the tag to update
        :param ignore_existing: it is not an error if the file already exists in the repo (default False)
        :return: the updated entry
        """
        if tag not in self.manifest.tags:
            raise HamstercageException(f"no tag {tag} in manifest")
        entries = self.manifest.tags[tag].entries
        (repo_path, target_path) = self._normalize_target_path(file)
        entry = Entry.entry(repo_path, target_path)
        if not ignore_existing:
            if entry.path in entries:
                raise HamstercageException(
                    f"Unable to add {target_path}: already added to tag {tag}"
                )
        entries[repo_path] = entry
        return entry

    def _save_entry(self, tag: str, entry: Entry):
        (repo_path, target_path) = self._normalize_target_path(entry.path)
        entry.save(self._path_repo_path_tag(repo_path, tag), target_path, self.manifest)
        return entry

    @staticmethod
    def _diff(target, repo) -> Iterator[str]:
        """
        Generate a unified diff between the target and the repo file.

        :param target: the target file path
        :param repo: the repo file path
        :return: An iterator of diff lines
        """
        if not target.exists() or not repo.exists():
            r = []
            if not target.exists():
                r.append(f"! {target} not found")
            if not repo.exists():
                r.append(f"! {repo} not found")
            return r
        with open(target) as f:
            t = f.readlines()
        with open(repo) as f:
            r = f.readlines()
        return unified_diff(
            r,
            t,
            fromfile=str(repo),
            fromfiledate=Hamstercage._mtime(repo),
            tofile=str(target),
            tofiledate=Hamstercage._mtime(target),
        )

    def _entries(self):
        """
        Generator that produces all entries, potentially filtered by the list of files given on the command line. Only
        returns entries for the first match for a path.
        :return: (tag, entry)
        """
        paths = {}
        for t in self.tags:
            for p, e in self.manifest.tags[t].entries.items():
                if not self._files_match(e):
                    continue
                if p in paths:
                    continue
                paths[p] = True
                yield t, e

    @staticmethod
    def _exists_status(path) -> str:
        """
        Return a string representing whether the path exists or not.
        :param path: to check
        :return: a space if the file exists, an exclamation sign otherwise
        """
        return " " if path else "!"

    def _files_match(self, entry: Entry) -> bool:
        """
        Return if the entry matches the files given on the command line. If the list of files is empty, any entry will
        match.

        :param entry: to check
        :return: True if the list of files matches this entry
        """
        if len(self.files) == 0:
            return True
        for file in self.files:
            (repo_path, target_path) = self._normalize_target_path(file)
            if entry.path == repo_path:
                return True
        return False

    def _load_manifest(self) -> None:
        """
        Load the manifest from the configured path. If the manifest had been loaded previously, do nothing.
        :return: None
        """
        if self.manifest:
            return
        try:
            self.manifest = Manifest(str(self.manifest_file))
            self.manifest.load()
            if len(self.tags) == 0:
                if self.hostname in self.manifest.hosts:
                    self.tags = self.manifest.hosts[self.hostname].tags
                else:
                    print(
                        f"Warning: No hostname entry for {self.hostname}",
                        file=sys.stderr,
                    )
        except FileNotFoundError as e:
            raise HamstercageException(
                f'Unable to load manifest from "{self.manifest_file}": {e}', 71
            )
        except ScannerError as e:
            raise HamstercageException(
                f'Unable to load manifest from "{self.manifest_file}": {e}', 71
            )

    def _mkdir_repo(self, path: Path) -> None:
        """
        Create a directory in the repo, copying owner/group/mode from the manifest file
        :param path: of the new directory
        :return: None
        """
        if str(path) != ".":
            self._mkdir_repo(path.parent)
        p = self.repo.joinpath(path)
        if not p.exists():
            p.mkdir(mode=self.manifest.dir_mode)
            chmod(str(p), self.manifest.dir_mode)
            shutil.chown(str(p), self.manifest.owner, self.manifest.group)

    @staticmethod
    def _mtime(path: Path) -> str:
        """
        Return the modification time of path as a string.
        :param path: of file
        :return: time and date in ISO8601 format
        """
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    def _mtime_or_missing(self, path: Path, prefix: str):
        """
        Print the modification date of path, or "missing" if the file doesn't exist.
        :param path: of the file
        :param prefix: string prefix to print
        :return:
        """
        if path.exists():
            print(f"{prefix} {str(path)}\t{self._mtime(path)}")
            return False
        print(f"{prefix} {str(path)}\tmissing")
        return True

    def _normalize_target_path(self, path: Union[str, Path]) -> (str, Path):
        """
        Returns two paths: the path as it should be entered into the manifest, and the filesystem path for the target
        file.
        :param path:
        :return: list of manifest path (str), and filesystem path (Path)
        """
        ppath = Path(path)
        path = str(path)
        starget = str(self.target) + "/"
        if path.startswith(starget):
            # absolute path including target, strip target
            return path[len(starget) - 1 :], ppath.absolute()
        else:
            if ppath.is_absolute():
                # prepend target to path
                return str(path), Path(str(self.target) + str(path))
            else:
                #
                return "/" + str(path), Path(str(self.target) + "/" + str(path))

    def _path_repo_entry(self, tag: str, entry: Entry) -> Path:
        """
        Return the absolute path for the file of the entry.
        :param tag: the tag for this entry
        :param entry: of the file
        :return: path of file
        """
        return entry.path_as_child_of(self.repo / "tags" / tag)

    def _path_repo_path_tag(self, repo_path, tag: str):
        return path_as_child_of(repo_path, self.repo / "tags" / tag)

    def _path_target(self, entry: Entry) -> Path:
        """
        Return the path to the target file for the entry.
        :param entry: of the file
        :return: path of file
        """
        return entry.path_as_child_of(self.target)

    def _run_hook(self, tagname: str, cmd: str, step: str):
        """
        Execute the defined hook (if any) for the given command and step. If the hook is defined, but cannot be
        executed successfully, a HamstercageException is thrown.
        :param tagname: where the hook is defined
        :param cmd: command that is being executed
        :param step: pre or post
        :return: 0 if successful, any other exit code on failure.
        """
        if not tagname in self.manifest.tags:
            raise HamstercageException(f"Unknown tag {tagname}")
        tag = self.manifest.tags[tagname]
        hook = tag.find_hook(cmd, step)
        if hook:
            return hook.call(self.manifest, cmd, step, tag)
        return 0

    def _run_hooks(self, cmd: str, step: str):
        """
        Execute the defined hook (if any) for the given command and step for all tags. If the hook is defined, but
        cannot be executed successfully, a HamstercageException is thrown.
        :param cmd: command that is being executed
        :param step: pre or post
        :return: 0 if successful, any other exit code on failure.
        """
        for t in self.tags:
            r = self._run_hook(t, cmd, step)
            if r != 0:
                return r
        return 0


def main():
    h = Hamstercage()
    sys.exit(h.main())


if __name__ == "__main__":
    main()
