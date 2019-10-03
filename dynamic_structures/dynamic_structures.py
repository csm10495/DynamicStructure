'''
Brief:
    dynamic_structure.py - Contains functionality to allow for a ctypes Structure to self-define itself.
        For example: we can have a header that says the size of an upcoming array.

Author(s):
    Charles Machalow via the MIT License
'''
import inspect
import pdb
from ctypes import *

'''
This would be most optimal:

class S(DynamicStructure):
    _pack_ = 1
    _fields_ = [
        ('arraySize', c_uint32),
        ('arrayA',    c_uint8 * arraySize),
        ('arrayB',    c_uint16 * arraySize),
    ]

instead we do:
getDynamicStructure(fields=[
    ('arraySize', c_uint32),
    ('arrayA',    lambda self, buffer: c_uint8  * self.arraySize),
    ('arrayB',    lambda self, buffer: c_uint16 * self.arraySize),
], pack=1)
'''

class BitFieldUnsupportedError(ValueError):
    ''' raised in the event that a bitfield is attempted to be used in a dynamic structure '''
    pass

class BufferSizeInsufficient(ValueError):
    ''' raised in the event that we don't have enough buffer space '''
    pass

class BaseStructure(Structure):
    ''' simple base Structure to inherit from '''
    def getBytes(self):
        ''' returns the bytes for this structure (by reference... sort of) '''
        return cast(byref(self), POINTER(c_uint8))

    def getBytesCopy(self):
        ''' gets a copy of the bytes for this structure '''
        return cast(byref(self), POINTER(c_uint8))[:sizeof(self)]

    def fill(self, buffer):
        ''' fills this instance of the struct with the given buffer '''
        for i in range(min(len(buffer), sizeof(self))):
            self.getBytes()[i] = buffer[i]
        return self

    def getAllFields(self):
        ''' gets all fields from the _fields_ for this and things in the
        module resolution order (mro) for inheritence '''
        fields = []
        for i in type(self).mro():
            if hasattr(i, '_fields_'):
                fields += i._fields_

        return fields[::-1]

def getStructureType(fieldTuple, buffer, parent=BaseStructure, pack=1, anonymous=None):
    '''
    adds the fieldTuple to the given parent using the buffer.

    if fieldTuple[1] is a function, it must have self (a structure up to just before now) and
                                        the buffer at this point onward as parameters.
                                            They can be used by a lambda to calculate out this field's size.
    '''

    if anonymous is None:
        anonymous = []

    if len(fieldTuple) != 2:
        # todo... maybe?:
        # If we see that this is a bitfield, look ahead to combine other bitfields to complete
        #   the given type (to the byte level)
        # Remember, we can't make TmpStructure with bitfields that don't complete bytes
        #    since ctypes will pack to the nearest byte
        raise BitFieldUnsupportedError('bit fields are not supported')

    name, typeOrFunction = fieldTuple

    if inspect.isfunction(typeOrFunction):
        # function was given... evaluate dynamically
        #  if a function is given it will have self (struct to this point) and buffer as params
        parentFilledTillNow = parent().fill(buffer)
        remainderOfBuffer = buffer[sizeof(parent):]

        if len(remainderOfBuffer) == 0:
            raise BufferSizeInsufficient("not enough remaining space to process: %s (remaining size == 0)" % name)

        # now call the function with what we have to get the actual tuple we need here
        calculatedDynamicType = typeOrFunction(parentFilledTillNow, remainderOfBuffer)

        if len(remainderOfBuffer) < sizeof(calculatedDynamicType()):
            raise BufferSizeInsufficient("not enough remaining space to process: %s... need %d bytes, have %d bytes" % (name, sizeof(calculatedDynamicType()), len(remainderOfBuffer)))

        fieldTuple = type(fieldTuple)([name, calculatedDynamicType])

    class TmpStructure(parent):
        ''' this tmp structure inherits from parent to essentially add one field '''
        _pack_ = pack

        # handle anonymous (only make anonymous if this field is listed)
        _anonymous_ = [] if name not in anonymous else [name]
        _fields_ = [
                fieldTuple
            ]

    return TmpStructure

def getDynamicStructureType(fields, buffer=None, pack=1, anonymous=None, docstring=''):
    '''
    gets a self-defining structure type with the given fields, buffer, pack.
    '''
    if anonymous is None:
        anonymous = []

    class BuildStructure(BaseStructure):
        ''' a base structure-like instance to set a given pack '''
        _pack_ = pack

    if buffer is None:
        buffer = []

    for idx, fieldTuple in enumerate(fields):
        BuildStructure = getStructureType(fieldTuple, buffer, BuildStructure, pack=pack, anonymous=anonymous)

    BuildStructure.__doc__ = inspect.cleandoc(docstring)
    return BuildStructure

def getDynamicStructure(fields, buffer=None, pack=1, anonymous=None, docstring=''):
    '''
    gets a self-defining structure with the given fields, buffer, pack.
    '''
    structType = getDynamicStructureType(fields, buffer, pack, anonymous, docstring)
    return structType().fill(buffer)
