import os
import stat
import sys

from datetime import datetime, timedelta
from pathlib import Path


def chmod(path, mode):
    """
    Change access mode on a target directory entry. Do not follow symlinks if the platform supports it.

    :param path: path to the file
    :param mode: mode to be set
    :return:
    """
    if os.chmod in os.supports_follow_symlinks:
        os.chmod(path, mode, follow_symlinks=False)
    else:
        pass


def mode_to_str(type: str, mode: int) -> str:
    """
    Converts the mode bits (from for example os.stat st_mode) into a string like ls.
    :param mode:
    :return:
    """
    return type + stat.filemode(mode)[1:]


def short_date(ts: int) -> str:
    """
    Returns a short date/time string based on the epoch timestamp
    :param ts:
    :return:
    """
    dt = datetime.fromtimestamp(ts)
    delta = abs(dt - datetime.now())
    f = "%Y"
    if delta < timedelta(days=1):
        f = "%H:%M"
    elif delta < timedelta(days=365 / 2):
        f = "%d.%m."
    return dt.strftime(f)


def print_table(table: list, align=None, file=None, tabs=None) -> None:
    """
    Prints the contents of the two-dimensional list.
    :param table:
    :param file:
    :return:
    """
    if align is None:
        align = []
    if file is None:
        file = sys.stdout
    if tabs is None:
        tabs = not file.isatty()
    cols = 0
    for line in table:
        cols = max(cols, len(line))
    if tabs:
        f = "\t".join(["{}"] * cols)
    else:
        widths = [0] * cols
        if len(align) < cols:
            align.extend(["<"] * (cols - len(align)))
        for line in table:
            for i in range(0, len(line)):
                widths[i] = max(widths[i], len(line[i]))
        fs = []
        for i in range(0, len(widths) - 1):
            fs.append(f"{{{i}:{align[i]}{widths[i]}}}")
            # f = f + f"{{0:{widths[i]}.{widths[i]}s}}"
        fs.append(f"{{{len(widths)-1}}}")
        f = " ".join(fs)
    for line in table:
        # print("{0:} {1:}".format(*line), file=out)
        print(f.format(*line), file=file)


class ListEntry:
    # noinspection PyUnresolvedReferences
    def __init__(self, entry: "Entry", repo: Path, tag: str):
        self.entry = entry
        self.repo = repo
        self.tag = tag
