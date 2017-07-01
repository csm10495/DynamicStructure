'''
Brief:
    dynamic_structure.py - Contains functionality to allow for a ctypes Structure to self-define itself.
        For example: we can have a header that says the size of an upcoming array.

Author(s):
    Charles Machalow via the MIT License
'''
from ctypes import *
import inspect
import pdb
from time import time
pm = pdb.pm

'''
This would be most optimal:

class S(DynamicStructure):
    _pack_ = 1
    _fields_ = [
        ('arraySize', c_uint32),
        ('arrayA',    c_uint8 * arraySize),
        ('arrayB',    c_uint16 * arraySize),
    ]
'''

def getStructureType(fieldTuple, buffer, parent=Structure, pack=1, anonymous=None):
    '''
    adds the fieldTuple to the given parent using the buffer.

    if fieldTuple[1] is a function, it must have self (a structure up to just before now) and
                                        the buffer at this point onward as parameters.
                                            They can be used by a lambda to calculate out this field's size.
    '''

    if anonymous is None:
        anonymous = []

    if len(fieldTuple) >= 2 and not inspect.isclass(fieldTuple[1]):
        # extended?
        parentFilled = parent().fill(buffer)
        
        remainderOfBuffer = buffer[sizeof(parent):]
        fieldList = [fieldTuple[0]] # to list
        fieldList.append(fieldTuple[1](parentFilled, remainderOfBuffer))
        fieldList + list(fieldTuple[2:]) # add bitfield... if that is somehow possible...

        fieldTuple = tuple(fieldList) # copy back to tuple

        # todo:
        # If we see that this is a bitfield, look ahead to combine other bitfields tp complete
        #   the given type (to the byte level)
        # Remember, we can't make TmpStructure with bitfields that don't complete bytes
        #    since ctypes will pack to the nearest byte

    # handle anonymous
    qualifiedAnonymous = [] # only anon in this structure
    for fieldName in anonymous:
        if fieldName == fieldTuple[0]:
            qualifiedAnonymous.append(fieldName)

    class TmpStructure(parent):
        _pack_ = pack
        _anonymous_ = qualifiedAnonymous
        _fields_ = [
                fieldTuple
            ]

    return TmpStructure

def getDynamicStructure(fields, buffer=None, pack=1, anonymous=None, docstring=''):
    '''
    gets a self-defining structure with the given fields, buffer, pack.
    '''
    if anonymous is None:
        anonymous = []

    class BuildStructure(Structure):
        '''
        define this in here to not be messed up when called again
        '''
        _pack_ = pack
        def getBytes(self):
            return cast(byref(self), POINTER(c_uint8))

        def getBytesCopy(self):
            return cast(byref(self), POINTER(c_uint8))[:sizeof(self)]

        def fill(self, buffer):
            for i in range(min(len(buffer), sizeof(self))):
                self.getBytes()[i] = buffer[i]
            return self

        def getAllFields(self):
            fields = []
            for i in type(self).mro():
                if hasattr(i, '_fields_'):
                    fields += i._fields_

            return fields[::-1]

        def getUpdated(self, fieldName, fieldType):
            fieldsCopy = self.getAllFields()
            found = False
            for idx, i in enumerate(fieldsCopy):
                i = list(i)
                if i[0] == fieldName:
                    i[1] = fieldType
                    fieldsCopy[idx] = tuple(i)
                    found = True

                    break

            if not found:
                return False

            class TmpStructure(Structure):
                _pack_ = self._pack_
                _fields_ = fieldsCopy

            return TmpStructure
                    

    if buffer is None:
        buffer = []

    for idx, fieldTuple in enumerate(fields):
        BuildStructure = getStructureType(fieldTuple, buffer, BuildStructure, pack=pack, anonymous=anonymous)
    
    BuildStructure.__doc__ = inspect.cleandoc(docstring)
    retStruct = BuildStructure().fill(buffer)
    return retStruct

def getCorrectVersionStructure(buffer):
    '''
    example to show dynamic versioning working
    '''
    major = buffer[0]
    if major == 1:
        class s_1(Structure):
            _pack_=1
            _fields_=[
                    ('VMaj', c_uint8),
                    ('ValueA', c_uint64),
                ]
        return s_1

    if major == 4:
        class s_4(Structure):
            _pack_=1
            _fields_=[
                    ('VMaj', c_uint8),
                    ('ValueA', c_uint64),
                    ('ValueB', c_uint32),
                    ('ValueC', c_uint16),
                ]
        return s_4

    raise Exception("No matching version found for %d" % major)

if __name__ == '__main__':
    t = time()
    buf = [200, 1, 0, 3, 4, 5, 6, 1, 4, 5, 6]
    buf *= 10000
    t2 = time()
    bufTime = t2 - t
    t = time()
    s = getDynamicStructure([
                ('A', c_uint8),
                ('B', lambda self, buffer: c_uint32 * self.A),              # A is telling us the number of 32 bit items for B
                ('C', lambda self, buffer: c_uint64 * (len(self.B) * 4)),   # 4 * len(B) is telling us the length of C
                ('VerStruct', lambda self, buffer: getCorrectVersionStructure(buffer)), # The buffer at this point is telling us the structure needed
                #('BitField1', c_uint8, 4),  # Broken right now since bitfields are expanding in the initial substructure (so this is 1 byte instead of 4 bits)
                #('BitField2', c_uint8, 4),  # Broken right now since bitfields are expanding in the initial substructure (so this is 1 byte instead of 4 bits)
            ], buf, pack=1, anonymous=['VerStruct'], docstring="""
            Brief:
                Test Structure

            Author(s):
                Charles Machalow
            """)
    t2 = time()

    print ("sizeof(s) == %d" % sizeof(s))
    print ("buffer generation time: %f seconds" % (bufTime))
    print ("getDynamicStructure time: %f seconds" % (t2 - t))


