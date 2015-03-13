from array import array
import json
import os
import sys

magic = 0x07230203
magic_um = 0x03022307

# Loads the file in module's directory
basepath = os.path.dirname(__file__)
with open(os.path.join(basepath,'spirv.json')) as fd:
    op_table = json.load(fd)['instructions']
    print op_table

if __name__=='__main__':
    dat = array('I', open(sys.argv[1], 'rb').read())
    if dat[0] == magic_um: # If it was incompatible endian, we take
        dat.byteswap()     # a little penalty in swapping the bytes around.
    elif dat[0] != magic:
        raise Exception("not a SPIR-V file")
    if dat[1] != 99:
        raise Exception("version mismatch")
    generator_magic = dat[2]
    bound = dat[3] # 0 < id < bound
    assert dat[4] == 0 # Reserved for an instruction schema
    # The instructions appear in a sequence, so I wouldn't
    # necessarily need a complete decoder/encoder.
    start = 5
    while start < len(dat):
        op = dat[start] & 0xFFFF
        length = dat[start] >> 16
        assert length != 0
        if op < len(op_table):
            assert op_table[op]['opcode'] == op # Assuming the tables file is sorted.
            print op_table[op]['name'], dat[start+1:start+length]
        else:
            print op, map(hex, dat[start+1:start+length])
        start += length
