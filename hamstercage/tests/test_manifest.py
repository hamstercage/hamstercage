from ..manifest import FileEntry

def test_FileEntry_from_dict():
    dut = FileEntry.from_dict('foo', {
        'group': 'wheel',
        'mode': 0o755,
        'owner': 'root',
        'type': 'file',
    })
    assert dut.path == 'foo'
    assert dut.group == 'wheel'
    assert dut.mode == 0o644
    assert dut.owner == 'root'
