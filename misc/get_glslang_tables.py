import ast, re, sys, os, json
from collections import defaultdict

# I used this program to generate spirv.json, this is a throwaway program
# here so it might not be up-to-date at all times.

# This program retrieves SPIR-V tables from glslang -project and translates
# them to JSON. It does so using some regular expressions.
# There was not other machine readable specifications available.

# Pass in the repository's directory as an argument. It dumps the
# generated tables into standard output.

spirv_src = open(os.path.join(sys.argv[1], 'SPIRV', 'spirv.h')).read()
doc_src = open(os.path.join(sys.argv[1], 'SPIRV', 'doc.cpp')).read()

# In the SPIRV/doc.cpp, there's code that describes the format of each
# instruction. Very straightforward to extract.
has_result = {}
has_type = {}
for name, res, typ in re.findall(r"InstructionDesc\[(.+)\].*setResultAndType\((true|false).*(true|false)\);", doc_src):
    has_result[name] = {'true':True, 'false':False}[res]
    has_type[name] = {'true':True, 'false':False}[typ]

# Some of the constant operands do not match with the constants table.
renamed_operands = {
    'Source': 'SourceLanguage',
    'Addressing': 'AddressingModel',
    'Memory': 'MemoryModel',
    'Dimensionality': 'Dim',
    'Storage': 'StorageClass',
    'Loop': 'LoopControl',
    'Select': 'SelectionControl',
    'Function': 'FunctionControl',
}

operands = defaultdict(list)
for name, operand in re.findall(r"InstructionDesc\[(.+)\].*operands\.push\((\w*)(?:,.*)?\);", doc_src):
    if operand.startswith('Operand'):      # Everything starts with an Operand
        operand = operand[len('Operand'):] # But it's not in the specification so lets clean it out.
    operands[name].append(renamed_operands.get(operand, operand))

# In the SPIRV/spirv.h there are several useful constants and flags used by the engine.
constants = {}
masks = {}
for name, body in re.findall(r"enum\W(\w+)\W\{(.*?)\}", spirv_src, re.DOTALL):
    if name.endswith('_'):
        continue # Spv.*_ seem to be duplicate of some tables.
    if name.endswith('Shift'):
        continue # Shift seem to be a duplicate of masks.
                 # hm. It could be more useful than the masks..
    if name.endswith('Mask'):
        name = re.sub("Mask$", "", name)
        to = masks
    else:
        to = constants
    table = {}
    index = 0
    for key, value in re.findall(r"^\s*(\w+)\s*(?:=\s*([0-9xA-Fa-f]+))?\s*\,?\s*(?://.*)?$", body, re.MULTILINE):
        if value != '':                     # Python and C literal syntax
            index = ast.literal_eval(value) # are similar enough.
        if name != 'Op': # The Op -prefix remains in the specification.
            key = re.sub("^"+name, "", key) # But other prefixes do not.
        if to == masks: # Also Masks do not have Mask -postfix.
            key = re.sub("Mask$", "", key)
            if key == 'MaskNone': # Isn't significant, and could be harmful to reader, so we can skip it.
                assert index == 0, index # Assuming it's zero.
                continue           
        assert key != '' # Substitutions might eliminate keys
        assert key not in table # If it appears again, something went wrong.
        table[key] = index # Allows ints to be ints in the json.
        index += 1 # enum increments if no constant is specified
    if name == 'Op': # Merge the opcode constants with instruction table.
        opcodes = table
    else:
        #name = renamed_constant_tables.get(name, name)
        to[name] = table

# Finally lets put everything together for easy consumption and pretty-print it out.
instructions = []
for name in sorted(opcodes, key=lambda x: opcodes[x]):
    record = dict(
        opcode = opcodes[name],
        name = name,
        result = has_result.get(name, True), # Apparently, if the result was not assumed in the
        type = has_type.get(name, True),     # C++ source code, it was assumed to be 'true'
        operands = operands.get(name, []),
    )
    instructions.append(record)
specification = dict(instructions=instructions, constants=constants, masks=masks)
print json.dumps(specification, indent=4)
