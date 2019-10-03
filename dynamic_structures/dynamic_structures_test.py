''' tests for dynamic_structure.py '''

import pytest

from dynamic_structures import *

def test_get_structure_type_no_dynamic_invalid_anon():
    ''' tests getStructureType() without a dynamic field and with an invalid anonymous '''
    fieldTuple = ('A', c_uint32)
    buffer = [28, 0, 0, 0]
    s = getStructureType(fieldTuple, buffer, pack=4, anonymous=['not_here'])

    assert s._pack_ == 4
    assert s._anonymous_ == []
    assert s._fields_ == [('A', c_uint32)]
    assert sizeof(s) == 4
    assert s().fill(buffer).A == 28

def test_get_structure_type_no_dynamic_valid_anon():
    ''' tests getStructureType() without a dynamic field and with a valid anonymous '''
    class Tmp(Structure):
        _fields_ = [('A', c_uint32)]

    fieldTuple = ('A', Tmp)
    buffer = [28, 0, 0, 0]
    s = getStructureType(fieldTuple, buffer, pack=4, anonymous=['A'])

    assert s._pack_ == 4
    assert s._anonymous_ == ['A']
    assert sizeof(s) == 4
    assert s().fill(buffer).A == 28

    s = getStructureType(fieldTuple, buffer, pack=2, anonymous=['A'])
    assert s._pack_ == 2

def test_get_structure_type_from_parent():
    ''' tests getStructureType() with a parent '''
    class Tmp(BaseStructure):
        _pack_ = 1
        _fields_ = [('A', c_uint32)]

    fieldTuple = ('B', c_uint8)
    buffer = [28, 0, 0, 0, 17]
    s = getStructureType(fieldTuple, buffer, parent=Tmp, pack=1)

    assert s._pack_ == 1
    assert sizeof(s) == 5
    assert s().fill(buffer).A == 28
    assert s().fill(buffer).B == 17

def test_get_structure_fails_bitfield():
    ''' tests getStructureType() raises if a bitfield is given '''
    buffer = [28, 0, 0, 0]
    with pytest.raises(BitFieldUnsupportedError):
        s = getStructureType(('A', c_uint32, 8), buffer, pack=4)

def test_get_structure_fails_lack_of_buffer():
    ''' tests getStructureType() raises if a dynamic structure can't be continued due to lack of buffer '''
    buffer = []
    with pytest.raises(BufferSizeInsufficient):
        s = getStructureType(('A', lambda self, buffer: False), buffer, pack=4)

def test_get_dynamic_structure_not_enough_space():
    ''' tests getDynamicStructure() with not enough buffer '''
    with pytest.raises(BufferSizeInsufficient):
        struct = getDynamicStructure(fields=[
                ('NumElements', c_uint8),
                ('Elements',    lambda self, buffer: self.NumElements * c_uint8),
            ], buffer=[10, 0, 1, 2, 3, 4, 5, 6, 7, 8]
        )

def test_get_dynamic_structure_enough_space():
    ''' tests getDynamicStructure() with enough buffer '''
    struct = getDynamicStructure(fields=[
            ('NumElements', c_uint8),
            ('Elements',    lambda self, buffer: self.NumElements * c_uint8),
            ('Post',        c_uint8),
        ], buffer=[10, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 99], docstring="DOCSTR_TEST", pack=1
    )

    assert struct.NumElements == 10
    assert struct.Post == 99
    assert list(struct.Elements) == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert struct.__doc__ == 'DOCSTR_TEST'
    assert struct._pack_ == 1
    assert sizeof(struct) == 12

def test_get_dynamic_structure_enough_space_alt_pack():
    ''' tests getDynamicStructure() with enough buffer and a different pack '''
    struct = getDynamicStructure(fields=[
            ('NumElements', c_uint8),
            # pack 4 inserts 3 bytes here.
            ('AfterPad',    c_uint32),
        ], buffer=[10, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9], docstring="DOCSTR_TEST", pack=4
    )

    assert struct.NumElements == 10
    assert struct.AfterPad == 0x06050403
    assert struct.__doc__ == 'DOCSTR_TEST'
    assert struct._pack_ == 4
    assert sizeof(struct) == 8
