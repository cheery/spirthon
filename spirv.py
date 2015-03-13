from array import array
import json
import os
import sys
import traceback

magic = 0x07230203
magic_um = 0x03022307
version = 99

# Loads the file in module's directory
basepath = os.path.dirname(__file__)
with open(os.path.join(basepath,'spirv.json')) as fd:
    tables = json.load(fd)

const_name_table = tables['constants']
const_table = {}
for name, table in const_name_table.items():
    const_table[name] = dict((value, key) for key, value in table.items())
bitmask_table = tables.get('masks', {})

opcode_table = {}
opname_table = {}
# Some of the operands didn't match, so I'm running sanity check over
# the instruction table to find out if there are more operands and 
# constants that do not match.
for fmt in tables['instructions']:
    opcode_table[fmt['opcode']] = fmt # Also populating opcode and opname tables.
    opname_table[fmt['name']] = fmt
    for operand in fmt['operands']:
        if operand not in ['LiteralNumber', 'LiteralString',
                'Id', 'VariableLiterals', 'VariableIds',
                'OptionalId', 'VariableLiteralId']:
            assert (operand in const_table or operand in bitmask_table), (operand, fmt)

# IDs are annotated so you won't mix them with ordinary literals.
class Id(object):
    def __eq__(self, other): # Used this to check that the encoding/decoding matches.
        return self.result_id == other.result_id

    def __init__(self, result_id):
        self.result_id = result_id # Can switcheroo with the instruction at encoding.

    def __repr__(self):
        return "Id({})".format(self.result_id)

class Instruction(object):
    def __init__(self, name, type_id=0, result_id=0, args=[]):
        self.name = name
        self.type_id = type_id
        self.result_id = result_id
        self.args = args

    def __repr__(self):
        prefix = ""
        if self.type_id > 0:
            prefix += "({})".format(self.type_id)
        if self.result_id > 0:
            prefix += "{}: ".format(self.result_id)
        return prefix + "{} {}".format(self.name, ' '.join(map(repr, self.args)))

# If the instruction cannot be decoded, you get this instead.
class UnknownInstruction(object):
    def __init__(self, opcode, data, traceback):
        self.opcode = opcode
        self.data = data
        self.traceback = traceback # When decoding fails, we may like to know why

    def __repr__(self):
        if self.traceback is not None:
            return 'UnknownInstruction({!r}, <traceback>)'.format(self.data)
        return 'UnknownInstruction({!r})'.format(self.data)

def decode_spirv(data):
    if data[0] == magic_um: # If it was incompatible endian, we take
        data.byteswap()     # a little penalty in swapping the bytes around.
    if data[0] != magic:
        raise Exception("not a SPIR-V file")
    if data[1] != version:
        raise Exception("version mismatch")
    assert data[4] == 0 # Reserved for an instruction schema
    # The instructions appear in a sequence, so I wouldn't
    # necessarily need a complete decoder/encoder.
    instructions = []
    start = 5
    while start < len(data):
        opcode = data[start] & 0xFFFF
        length = data[start] >> 16
        assert length != 0
        instructions.append(decode_instruction(opcode, data[start+1:start+length]))
        start += length
    return instructions, {
        "bound":data[3], # 0 < id < bound
        "generator_id":data[2]
    }

def decode_instruction(opcode, data):
    if opcode not in opcode_table:
        return UnknownInstruction(opcode, data, None)
    try:
        fmt = opcode_table[opcode]
        it = iter(data)
        type_id = 0
        if fmt['type']:
            type_id = it.next()
        result_id = 0
        if fmt['result']:
            result_id = it.next()
        args = []
        for operand in fmt['operands']:
            if operand in const_table:
                args.append(const_table[operand][it.next()])
            elif operand in bitmask_table:
                flag = it.next()
                mask = set()
                cover = 0
                for name, value in bitmask_table[operand].items():
                    if flag & value != 0:
                        mask.add(name)
                        cover |= value
                if flag & ~cover != 0:
                    mask.add(flag & ~cover)
                args.append(mask)
            elif operand == 'LiteralNumber':
                args.append(it.next())
            elif operand == 'LiteralString':
                args.append(decode_literal_string(it))
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
        assert len(fmt['operands']) == len(args)
        assert tuple(it) == ()
        return Instruction(fmt['name'], type_id, result_id, args)
    except:
        return UnknownInstruction(opcode, data, traceback.format_exc())

# Literal string parsing, as it appears in the SPIR-V specification
def decode_literal_string(it):
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

def encode_spirv(instructions, bound, generator_id=0, schema_id=0):
    result = [magic, version, generator_id, bound, schema_id]
    for instruction in instructions:
        if isinstance(instruction, UnknownInstruction):
            opcode = instruction.opcode
            data = instruction.data
        elif instruction.name not in opname_table:
            raise Exception("cannot encode {}, unknown opname".format(instruction))
        else:
            fmt = opname_table[instruction.name]
            opcode = fmt['opcode']
            data = list(encode_instruction(fmt, instruction))
        assert len(data) <= 0xFFFF
        result.append(len(data)+1 << 16 | opcode & 0xFFFF)
        result.extend(data)
    return result

def encode_instruction(fmt, instruction):
    if fmt['type']:
        yield instruction.type_id
    if fmt['result']:
        yield instruction.result_id
    assert len(fmt['operands']) == len(instruction.args)
    for operand, field in zip(fmt['operands'], instruction.args):
        if operand == 'LiteralNumber':
            yield field
        elif operand == 'LiteralString':
            for data in encode_literal_string(field):
                yield data
        elif operand == 'Id':
            yield field.result_id
        elif operand == 'VariableLiteralId':
            for literal, item in field:
                yield literal
                yield item.result_id
        elif operand == 'VariableLiterals':
            for literal in field:
                yield literal
        elif operand == 'VariableIds':
            for item in field:
                yield item.result_id
        elif operand == 'OptionalId':
            if field is not None:
                yield field.result_id
        elif operand in const_table:
            yield const_name_table[operand][field]
        elif operand in bitmask_table:
            masks = bitmask_table[operand]
            flag = 0
            for name in field:
                flag |= masks[name]
            yield flag
        else:
            assert False, (operand, instructions)

def encode_literal_string(string):
    string = string.encode('utf-8') + '\x00'
    for i in range(0, len(string), 4):
        word = 0
        for ch in reversed(string[i:i+4]):
            word = word << 8 | ord(ch)
        yield word

def load(fd):
    return decode_spirv(array('I', fd.read()))

def stringify_spirv(data):
    return array('I', data).tostring()

if __name__=='__main__':
    instructions, info = load(open(sys.argv[1], 'rb'))
    instructions_, info_ = decode_spirv(encode_spirv(instructions, **info))
    print info, info_
    assert len(instructions) == len(instructions_)
    for a, b in zip(instructions, instructions_):
        print a
        if isinstance(a, UnknownInstruction) and a.traceback:
            print a.traceback
            break
        elif isinstance(b, UnknownInstruction) and b.traceback:
            print b.traceback
            break
        else:
            assert a.name == b.name
            assert a.type_id == b.type_id
            assert a.result_id == b.result_id
            assert a.args == b.args
