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

@pytest.mark.parametrize('baseClass', [BaseStructure, Structure])
def test_get_structure_type_from_parent(baseClass):
    ''' tests getStructureType() with a parent (also is testing if something doesn't inherit from BaseStructure) '''
    class Tmp(baseClass):
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

def test_get_array_of_dynamic_structures_type_not_dynamic():
    ''' tests getArrayOfDynamicStructuresType to make sure it works with non-dynamic fields
        Also happens to test getArrayOfDynamicStructures() while here'''
    buffer = [a for a in range(255)]

    ARRAY_LIKE_FIELDS = [
        ('A', c_uint8),
        ('B', c_uint8),
    ]

    typ = getArrayOfDynamicStructuresType(buffer, ARRAY_LIKE_FIELDS, maxArrayLength=3)
    inst = typ().fill(buffer)
    assert inst.getArrayIndex(0).A == 0
    assert inst.getArrayIndex(0).B == 1
    assert inst.getArrayIndex(1).A == 2
    assert inst.getArrayIndex(1).B == 3
    assert inst.getArrayIndex(2).A == 4
    assert inst.getArrayIndex(2).B == 5

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(3)

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(-2)

    assert sizeof(inst) == 6
    assert len(inst) == 3

    inst = getArrayOfDynamicStructures(buffer, ARRAY_LIKE_FIELDS, maxArrayLength=3)

    assert inst.getArrayIndex(0).A == 0
    assert inst.getArrayIndex(0).B == 1
    assert inst.getArrayIndex(1).A == 2
    assert inst.getArrayIndex(1).B == 3
    assert inst.getArrayIndex(2).A == 4
    assert inst.getArrayIndex(2).B == 5

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(3)

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(-2)

    assert sizeof(inst) == 6
    assert len(inst) == 3

def test_get_array_of_dynamic_structures_type_dynamic():
    ''' tests getArrayOfDynamicStructuresType to make sure it works with dynamic fields'''
    buffer = [a for a in range(255)]

    ARRAY_LIKE_FIELDS = [
        ('NumElements', c_uint8),
        ('Array', lambda self, buffer: c_uint8 * self.NumElements)
    ]

    typ = getArrayOfDynamicStructuresType(buffer, ARRAY_LIKE_FIELDS, maxArrayLength=3)
    inst = typ().fill(buffer)
    assert inst.getArrayIndex(0).NumElements == 0
    assert len(inst.getArrayIndex(0).Array) == 0

    assert inst.getArrayIndex(1).NumElements == 1
    assert list(inst.getArrayIndex(1).Array) == [2]

    assert inst.getArrayIndex(2).NumElements == 3
    assert list(inst.getArrayIndex(2).Array) == [4, 5, 6]

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(3)

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(-2)

    assert len(inst) == 3

def test_get_array_of_dynamic_structures_type_dynamic_with_struct_pick_function():
    ''' tests getArrayOfDynamicStructuresType to make sure it works with dynamic fields and if we give a struct pick function
    instead of giving in a list of fields '''
    buffer = [a for a in range(255)]

    def structPickFunction(buffer):
        if buffer[0] == 0:
            fields = [
                ('Field0', c_uint8),
            ]

        elif buffer[0] == 1:
            fields = [
                ('Field1', c_uint16),
            ]

        else:
            return False

        class TmpStructure(BaseStructure):
            _pack_ = 1
            _fields_ = fields

        return TmpStructure

    typ = getArrayOfDynamicStructuresType(buffer, structPickFunction, maxArrayLength=3)
    inst = typ().fill(buffer)

    assert inst.getArrayIndex(0).Field0 == 0
    assert inst.getArrayIndex(1).Field1 == 0x0201

    with pytest.raises(IndexError):
        assert inst.getArrayIndex(2)

    assert len(inst) == 2