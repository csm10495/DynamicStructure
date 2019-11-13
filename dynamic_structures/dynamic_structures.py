'''
Brief:
    dynamic_structure.py - Contains functionality to allow for a ctypes Structure to self-define itself.
        For example: we can have a header that says the size of an upcoming array.

Author(s):
    Charles Machalow via the MIT License
'''
import inspect
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

class DynamicStructureError(ValueError):
    ''' all errors raised by this stuff extends from this '''
    pass

class BitFieldUnsupportedError(DynamicStructureError):
    ''' raised in the event that a bitfield is attempted to be used in a dynamic structure '''
    pass

class BufferSizeInsufficient(DynamicStructureError):
    ''' raised in the event that we don't have enough buffer space '''
    pass

class BaseStructure(Structure):
    ''' simple base Structure to inherit from '''
    def _getBytes(self):
        ''' returns the bytes for this structure (by reference... sort of) '''
        return cast(byref(self), POINTER(c_uint8))

    def fill(self, buffer):
        ''' fills this instance of the struct with the given buffer '''
        for i in range(min(len(buffer), sizeof(self))):
            self._getBytes()[i] = buffer[i]
        return self

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

        tupleType = type(fieldTuple)

        # handle if the tupleType __new__ wants a tuple or params as tuple fields
        try:
            newFieldTuple = tupleType(name, calculatedDynamicType)
        except TypeError:
            ''' TypeError: tuple() takes at most 1 argument (2 given) '''
            newFieldTuple = tupleType((name, calculatedDynamicType))

        # if the tupleType is inherited from tuple, bring over things that may have been on that object
        if hasattr(newFieldTuple, '__dict__'):
            newFieldTuple.__dict__.update(fieldTuple.__dict__)

    else:
        newFieldTuple = fieldTuple

    class TmpStructure(parent):
        ''' this tmp structure inherits from parent to essentially add one field '''
        _pack_ = pack

        # handle anonymous (only make anonymous if this field is listed)
        _anonymous_ = [] if name not in anonymous else [name]
        _fields_ = [
                newFieldTuple
            ]

    if not issubclass(parent, BaseStructure):
        # make sure we inherit from BaseStructure
        #   to get us the .fill() method.
        class TmpStructure(TmpStructure, BaseStructure):
            pass

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

def getArrayOfDynamicStructuresType(buffer, fieldsOrStructTypePickFunction, maxArrayLength, pack=1):
    ''' takes in a buffer, and a list of fields. The fields will make up a dynamic structure to be continually
    used in an array-like thing of those structs. If a function is given to fieldsOrStructTypePickFunction, it
    should take in a buffer and return a type to use at this point. It can also return False if there isn't
    enough room to process the next element '''

    curatedFieldsList = []
    for idx in range(maxArrayLength):
        if inspect.isfunction(fieldsOrStructTypePickFunction):
            # function to find list of fields given
            ds = fieldsOrStructTypePickFunction(buffer)
            if not ds:
                break
        else:
            # list of fields given.
            ds = getDynamicStructureType(fieldsOrStructTypePickFunction, buffer=buffer, pack=pack)
        curatedFieldsList.append(('_ArrayItem_%d' % idx, ds,))
        buffer = buffer[sizeof(ds):]

    class TmpArrayStructure(BaseStructure):
        ''' structure that will be returned. Main user-entry point is getArrayIndex() '''
        _pack_ = pack
        _fields_ = curatedFieldsList

        def __len__(self):
            ''' returns number of items in this struct's array '''
            return len(curatedFieldsList)

        def getArrayIndex(self, idx):
            ''' user-facing way to get items in the array index '''
            if idx >= len(self) or idx < 0:
                raise IndexError("%d is out of bounds" % idx)
            return getattr(self, '_ArrayItem_%d' % idx)

    return TmpArrayStructure

def getArrayOfDynamicStructures(buffer, fieldsOrStructTypePickFunction, maxArrayLength, pack=1):
    ''' calls getArrayOfDynamicStructuresType() then instantiates it with the buffer '''
    s = getArrayOfDynamicStructuresType(buffer, fieldsOrStructTypePickFunction, maxArrayLength, pack)
    return s().fill(buffer)