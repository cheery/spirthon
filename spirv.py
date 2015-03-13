from array import array
import json
import os
import sys

magic = 0x07230203
magic_um = 0x03022307

# Loads the file in module's directory
basepath = os.path.dirname(__file__)
with open(os.path.join(basepath,'spirv.json')) as fd:
    tables = json.load(fd)
    op_table = tables['instructions']
    const_table = tables['constants']
    for name, table in const_table.items():
        const_table[name] = dict((value, key) for key, value in table.items())
    mask_table = tables.get('masks', {})

# Some of the operands didn't match, so I'm running sanity check over
# the instruction table to find out if there are more operands and 
# constants that do not match.
for instruction in op_table:
    for operand in instruction['operands']:
        if operand not in ['LiteralNumber', 'LiteralString',
                'Id', 'VariableLiterals', 'VariableIds',
                'OptionalId', 'VariableLiteralId']:
            assert operand in const_table, (operand, instruction)

# Literal string parsing, as it appears in the SPIR-V specification
def literal_string(it):
    result = []
    for word in it:
        for _ in range(4):
            octet = word & 255
            if octet == 0:
                assert word == 0
                return ''.join(result).decode('utf-8')
            result.append(chr(octet))
            word >>= 8
    raise Exception("bad encoding")

# IDs are annotated so you won't mix them with ordinary literals.
class Id(object):
    def __init__(self, index):
        self.index = index 

    def __repr__(self):
        return "Id({})".format(self.index)

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
            fmt = op_table[op]
            assert fmt['opcode'] == op # Assuming the tables file is sorted.
            it = iter(dat[start+1:start+length])
            type_id = None
            if fmt['type']:
                type_id = it.next()
            result_id = None
            if fmt['result']:
                result_id = it.next()
            args = []
            for operand in fmt['operands']:
                if operand in const_table:
                    args.append(const_table[operand][it.next()])
                elif operand in mask_table:
                    flag = it.next()
                    mask = set()
                    cover = 0
                    for name, value in const_table[operand].items():
                        if flag & value != 0:
                            mask.add(name)
                            cover |= value
                    if flag & ~cover != 0:
                        mask.add(flag & ~cover)
                    args.append(mask)
                elif operand == 'LiteralNumber':
                    args.append(it.next())
                elif operand == 'LiteralString':
                    args.append(literal_string(it))
                elif operand == 'Id':
                    args.append(Id(it.next()))
                elif operand == 'VariableLiteralId':
                    lit_ids = []
                    seq = list(it)         # Verify literals form pairs like
                    assert len(seq)%2 == 0 # they should.
                    it = iter(seq)
                    for literal in it:
                        lit_ids.append((literal, Id(it.next())))
                    args.append(lit_ids)
                elif operand == 'VariableLiterals':
                    args.append(list(it))
                elif operand == 'VariableIds':
                    args.append(map(Id, it))
                elif operand == 'OptionalId':
                    opt = map(Id, it)
                    assert len(opt) <= 1
                    args.append(None if len(opt) == 0 else opt[0])
                else:
                    assert False, (operand, fmt)
            assert len(fmt['operands']) == len(args)
            assert tuple(it) == ()
            print op_table[op]['name'], type_id, result_id, args
        else:
            print op, map(hex, dat[start+1:start+length])
        start += length
