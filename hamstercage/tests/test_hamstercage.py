import os
import shutil
from collections import namedtuple
from pathlib import Path

from hamstercage.__main__ import Hamstercage

from importlib.resources import files


def test_load():
    dut = Hamstercage()
    dut.manifest_file = files('hamstercage.tests') / 'manifest.yaml'
    dut.hostname = 'testing.example.com'
    dut._load_manifest()

    assert 'testing.example.com' in dut.manifest.hosts
    host = dut.manifest.hosts['testing.example.com']
    assert 'all' in host.tags

    assert 'all' in dut.manifest.tags
    tag = dut.manifest.tags['all']
    assert tag.description == 'Files that apply to all hosts'
    assert 'one.txt' in tag.entries


def test_add_dir(tmpdir):
    dut = Hamstercage()
    dut.manifest_file = tmpdir / 'manifest.yaml'
    dut.hostname = 'testing.example.com'
    dut.target = Path(tmpdir) / 'target'
    dut.repo = Path(tmpdir) / 'repo'
    dut.init(None)
    os.chmod(dut.manifest_file, 0o664)
    dut.target.mkdir()

    dir_to_add = 'a-dir'
    path_to_add = dut.target / dir_to_add
    path_to_add.mkdir()

    Args = namedtuple('Args', 'files')
    args = Args(files=[dir_to_add])
    r = dut.add(args)
    assert r == 0

    m = dut.manifest_file.read_text('utf-8')
    assert m == ('hosts:\n'
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
                 '        type: dir\n')

    assert not (dut.repo / 'tags' / 'all' / dir_to_add).exists()

def test_add_file(tmpdir):
    dut = Hamstercage()
    dut.manifest_file = tmpdir / 'manifest.yaml'
    dut.hostname = 'testing.example.com'
    dut.target = Path(tmpdir) / 'target'
    dut.repo = Path(tmpdir) / 'repo'
    dut.init(None)
    os.chmod(dut.manifest_file, 0o664)
    dut.target.mkdir()

    file_to_add = 'foo.txt'
    path_to_add = dut.target / file_to_add
    path_to_add.write_text('Hello, world!', 'utf-8')
    path_to_add.chmod(0o644)

    Args = namedtuple('Args', 'files')
    args = Args(files=[file_to_add])
    r = dut.add(args)
    assert r == 0

    m = dut.manifest_file.read_text('utf-8')
    assert m == ('hosts:\n'
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
                 '        type: file\n')

    f = (dut.repo / 'tags' / 'all' / file_to_add).read_text('utf-8')
    assert f == 'Hello, world!'


def test_add_link(tmpdir):
    dut = Hamstercage()
    dut.manifest_file = tmpdir / 'manifest.yaml'
    dut.hostname = 'testing.example.com'
    dut.target = Path(tmpdir) / 'target'
    dut.repo = Path(tmpdir) / 'repo'
    dut.init(None)
    os.chmod(dut.manifest_file, 0o664)
    dut.target.mkdir()

    link_to_add = 'a-link'
    path_to_add = dut.target / link_to_add
    path_to_add.symlink_to('/dev/null')

    Args = namedtuple('Args', 'files')
    args = Args(files=[link_to_add])
    r = dut.add(args)
    assert r == 0

    m = dut.manifest_file.read_text('utf-8')
    assert m == ('hosts:\n'
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
                 '        type: link\n')

    assert not (dut.repo / 'tags' / 'all' / link_to_add).exists()

def test_init(tmpdir):
    dut = Hamstercage()
    dut.manifest_file = tmpdir / 'manifest.yaml'
    dut.hostname = 'testing.example.com'
    dut.init(None)

    m = dut.manifest_file.read_text('utf-8')
    assert m == ('hosts:\n'
                 '  testing.example.com:\n'
                 "    description: ''\n"
                 '    tags:\n'
                 '    - all\n'
                 'tags:\n'
                 '  all:\n'
                 '    description: files that apply to all hosts\n'
                 '    entries: {}\n')
