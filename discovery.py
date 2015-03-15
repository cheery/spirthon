from dis import findlabels
import annotator
import opcode
# The discovery -stage of the translator, and the objects it generates.

class Function(object):
    def __init__(self, annotation, func, entry):
        self.annotation = annotation
        self.func = func
        self.entry = entry

    def __iter__(self): # hack so we won't have to change annotator later for multiple blocks.
        yield self.entry

class Block(object):
    def __init__(self, ops):
        self.ops = ops

# During the translation process, all these operations will be
# substituted by SPIR-V instructions.

# If I consider the upscope of every function be fixed down, this object
# may be substituted away early. Though it can be used to generate stack
# traces later on.
class Global(object):
    def __init__(self, func, org, name):
        self.func = func
        self.org = org
        self.name = name

    def __repr__(self):
        return "<Global {!r}>".format(self.name)
# Locals will be eliminated and substituted by phi -nodes and
# assignment results
class Local(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Local {!r}>".format(self.name)
# These seed the basic blocks, representing 'high level' operations.
class Operation(object):
    def __init__(self, func, org, name, args):
        self.func = func
        self.org = org
        self.name = name
        self.args = args
        self.annotation = annotator.unbound
        self.use = set()
        for arg in self.args:
            if isinstance(arg, Operation):
                arg.use.add(self)
        self.queued = False # True if in annotator's queue.
    # Makes the representation in printouts a little bit cleaner.
    def __str__(self): 
        return "<Op {} {}>".format(self.name, ' '.join(map(str, self.args)))

    def __repr__(self):
        return "<Op {}>".format(self.name)

def build(annotation, func):
    entry = Block(list(interpret(func)))
    return Function(annotation, func, entry)

# This isn't final form of this function. I should later pass it pc,
# stack, vartab, labels as arguments. It should produce basic blocks
# to me. Also this function should memoize the basic block it will generate
def interpret(func):
    #func.func_globals
    co_argcount = func.func_code.co_argcount
    co_code = func.func_code.co_code
    co_consts = func.func_code.co_consts
    co_names = func.func_code.co_names
    co_varnames = func.func_code.co_varnames
    pc = 0
    stack = []
    vartab = [Local(vn) for vn in co_varnames] 
    labels = set(findlabels(co_code))
    while pc < len(co_code):
        org = pc
        if org in labels:
            yield Operation(func, org, 'fallthrough', [stack])
        op, arg, pc = step(co_code, pc)
        name = opcode.opname[op]
        if name == 'CALL_FUNCTION':
            argv = [stack.pop() for i in range(arg+1)]
            argv.reverse()
            operation = Operation(func, org, 'call', argv) 
            yield operation
            stack.append(operation)
        elif name == 'LOAD_ATTR':
            obj = stack.pop()
            operation = Operation(func, org, 'attr', [obj, co_names[arg]])
            yield operation
            stack.append(operation)
        elif name == 'LOAD_CONST':
            stack.append(co_consts[arg])
        elif name == 'LOAD_FAST':
            stack.append(vartab[arg])
        elif name == 'LOAD_GLOBAL':
            stack.append(Global(func, org, co_names[arg]))
        elif name == 'POP_TOP':
            stack.pop()
        elif name == 'RETURN_VALUE':
            yield Operation(func, org, "return", [stack.pop()])
            assert len(stack) == 0 # An assumption.
            break
        elif name == 'STORE_ATTR':
            obj = stack.pop()
            val = stack.pop()
            yield Operation(func, org, "setattr", [obj, co_names[arg], val])
        elif name == 'STORE_FAST':
            yield Operation(func, org, "assign", [co_varnames[arg], stack.pop()])
        elif name in binary_opcodes:
            fn = binary_opcodes[name]
            rhs = stack.pop()
            lhs = stack.pop()
            operation = Operation(func, org, fn, [lhs, rhs])
            yield operation
            stack.append(operation)
        else:
            co_filename = func.func_code.co_filename
            lineno = find_lineno(func, org)
            block = ["--> {} {} {}".format(org, name, arg)]
            while pc < len(co_code) and len(block) < 5:
                org = pc
                op, arg, pc = step(co_code, pc)
                name = opcode.opname[op]
                block.append("    {} {} {}".format(org, name, arg))
            error_message = error_template.format(
                co_filename,
                lineno,
                '\n'.join(block))
            raise Exception(error_message)

def decode_lnotab(func):
    t = func.func_code.co_lnotab
    return [(ord(t[i]), ord(t[i+1])) for i in range(0, len(t), 2)]

def find_lineno(func, pc):
    co_lnotab = decode_lnotab(func)
    lineno = func.func_code.co_firstlineno
    addr = 0
    for addr_incr, line_incr in co_lnotab:
        addr += addr_incr
        if addr > pc:
            return lineno
        lineno += line_incr
    return lineno

# Almost all there is to decoding python instructions.
def step(co_code, pc):
    op = ord(co_code[pc])
    if op >= opcode.HAVE_ARGUMENT:
        b0 = ord(co_code[pc+1])
        b1 = ord(co_code[pc+2])
        arg = b0 | b1 << 16
        pc += 3
    else:
        arg = 0
        pc += 1
    return op, arg, pc

binary_opcodes = {
    'BINARY_MULTIPLY': 'mul',
    'BINARY_ADD': 'add',
    'BINARY_SUB': 'sub',
    'BINARY_MODULO': 'mod',
}

error_template = """Operation not accepted by the target language.
  File {!r}, line {}
{}"""
