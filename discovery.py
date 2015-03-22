from collections import namedtuple
from dis import findlabels
import itertools
import opcode

# Discovery -stage converts functions into SSA -form.
class Procedure(object):
    def __init__(self, func):
        self.blocks = []
        self.func = func
        self.counter = itertools.count(1) # helps at finding out errors from this code.

    def __str__(self):
        return "Procedure {}\n{}".format(
            self.func,
            '\n'.join(map(str, self.blocks)))

    def new_block(self):
        block = Block(proc=self)
        self.blocks.append(block)
        return block

class Argument(object):
    def __init__(self, proc, index):
        self.proc = proc
        self.index = index

    def __repr__(self):
        return "Arg{}".format(self.index)

class Block(object):
    def __init__(self, proc):
        self.proc = proc
        self.instructions = []
        self.depends = set()
        self.defines = {}
        self.prec = []
        self.succ = []
        self.idom = None
        self.phi = {}
        self.frontiers = set()

    def __str__(self):
        return "{:3}: {}{}".format(
            self.index,
            '\n     '.join(map(str, self.phi.values() + self.instructions)),
            ''.join('\n     {} <- {}'.format(n, v) for n, v in self.defines.items()))

    def __repr__(self):
        return "L{}".format(self.index)

    @property
    def index(self):
        return self.proc.blocks.index(self)

class Instruction(object):
    def __init__(self, block, pc, name, args):
        self.block = block
        self.pc = pc
        self.name = name
        self.args = args
        block.instructions.append(self)
        for arg in args:
            if isinstance(arg, Block):
                block.succ.append(arg)
                arg.prec.append(block)
        self.result_id = block.proc.counter.next()

    # Makes the representation in printouts a little bit cleaner.
    def __str__(self): 
        return "i{} = (Op {} {})".format(self.result_id, self.name, ' '.join(map(repr, self.args)))

    def __repr__(self):
        return "i{}".format(self.result_id)

# If I consider the upscope of every function be fixed down, this object
# may be substituted away early. Though it can be used to generate stack
# traces later on.
class Global(object):
    def __init__(self, block, pc, name):
        self.block = block
        self.pc = pc
        self.name = name

    def __repr__(self):
        return "(Global {})".format(self.name)

class Phi(object):
    def __init__(self, block, args):
        self.block = block
        self.args = args
        self.result_id = block.proc.counter.next()

    def __str__(self):
        return "p{} = (Phi {})".format(self.result_id, self.args)

    def __repr__(self):
        return "p{}".format(self.result_id)

# Locals are eliminated and substituted by phi -nodes and
# assignment results in ssa_conversion
class Local(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "(Local {!r})".format(self.name)

Tables = namedtuple('Tables', ['jump', 'labels', 'variables'])

# This is supposed to be called through TranslationUnit, where the
# results are memoized.
def read(func):
    proc = Procedure(func)
    tables = Tables(
        jump = {},
        labels = findlabels(func.func_code.co_code),
        variables = [Local(n) for n in func.func_code.co_varnames])
    entry = interpret(proc, 0, [], tables)
    assert len(entry.prec) == 0 # If this assertion fails, then code in the
                                # interpret() for Arguments need to be fixed.
    ssa_conversion(proc)
    return proc

def interpret(proc, pc, cont, tables):
    if pc in tables.jump:
        block, cont_ = tables.jump[pc]
        assert cont_ == cont, "An assumption that continuation table is not abused"
        return block
    block = proc.new_block()
    tables.jump[pc] = block, cont
    func_code = proc.func.func_code
    co_code = func_code.co_code
    co_consts = func_code.co_consts
    co_names = func_code.co_names
    # If something branches into the entry node, it might cause phi -nodes
    # to be generated on arguments. The way to define arguments like this
    # will produce errors for such programs.
    if block.index == 0:
        for i in range(func_code.co_argcount):
            block.defines[tables.variables[i]] = Argument(proc, i)
    stack = []
    while pc < len(co_code):
        org = pc
        if org in tables.labels and len(block.instructions) > 0:
            assert len(stack) == 0
            Instruction(block, org, 'fallthrough', [
                interpret(proc, org, cont, jump_table, labels)])
            break
        op, arg, pc = step(co_code, pc)
        name = opcode.opname[op]
        if name == 'LOAD_CONST':
            stack.append(Instruction(block, org, 'const', [co_consts[arg]]))
        elif name == 'LOAD_FAST':
            var = tables.variables[arg]
            if var not in block.defines:
                block.depends.add(var)
            stack.append(block.defines.get(var, var))
        elif name == 'LOAD_GLOBAL':
            stack.append(Global(block, org, co_names[arg]))
        elif name == 'JUMP_ABSOLUTE':
            assert len(stack) == 0
            Instruction(block, org, 'jump', [
                interpret(proc, arg, cont, tables)])
            break
        elif name == 'JUMP_FORWARD':
            assert len(stack) == 0
            Instruction(block, org, 'jump', [
                interpret(proc, pc+arg, cont, tables)])
            break
        elif name == 'POP_JUMP_IF_FALSE':
            assert len(stack) == 1
            Instruction(block, org, 'cond', [
                stack.pop(),
                interpret(proc, pc, cont, tables),
                interpret(proc, arg, cont, tables)])
            break
        elif name == 'POP_BLOCK':
            cont = cont[:-1]
        elif name == 'POP_TOP':
            stack.pop()
        elif name == 'RETURN_VALUE':
            assert len(stack) == 1
            Instruction(block, org, 'return', [stack.pop()])
            break
        elif name == 'SETUP_LOOP':
            cont = cont + [('loop', arg)]
        elif name == 'STORE_FAST':
            block.defines[tables.variables[arg]] = stack.pop()
        else:
            co_filename = func_code.co_filename
            lineno = find_lineno(proc.func, org)
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
    return block
# Will be inserted back when they become useful.
#        if name == 'CALL_FUNCTION':
#            argv = [stack.pop() for i in range(arg+1)]
#            argv.reverse()
#            operation = Operation(func, org, 'call', argv) 
#            yield operation
#            stack.append(operation)
#        elif name == 'LOAD_ATTR':
#            obj = stack.pop()
#            operation = Operation(func, org, 'attr', [obj, co_names[arg]])
#            yield operation
#            stack.append(operation)
#        elif name == 'STORE_ATTR':
#            obj = stack.pop()
#            val = stack.pop()
#            yield Operation(func, org, "setattr", [obj, co_names[arg], val])
#        elif name in binary_opcodes:
#            fn = binary_opcodes[name]
#            rhs = stack.pop()
#            lhs = stack.pop()
#            operation = Operation(func, org, 'call', [fn, lhs, rhs])
#            yield operation
#            stack.append(operation)

# Some variables are pre-set for ssa conversion
# The conversion must map every remaining Local to
# a value: argument, phi, global or instruction.
def ssa_conversion(proc):
    entry = proc.blocks[0]
    # Every path from entry to a block includes the immediate
    # dominator of the block. We use this information to convert
    # a depth first search into dominator search.
    def depth_first_flow(block, prec):
        if block is not entry and block.idom is None:
            block.idom = prec
            for succ in block.succ:
                depth_first_flow(succ, block)
    for succ in entry.succ:
        depth_first_flow(succ, entry)
    assert entry.idom is None
    # Distance to entry lets to find a common dominator
    # in the chain.
    def distance(block):
        count = 0
        while block.idom is not None:
            block = block.idom
            count += 1
        return count
    def common_dominator(lhs, rhs):
        lhs_d = distance(lhs)
        rhs_d = distance(rhs)
        while lhs_d > rhs_d:
            lhs = lhs.idom
            lhs_d -= 1
        while rhs_d > lhs_d:
            rhs = rhs.idom
            rhs_d -= 1
        while lhs != rhs:
            lhs = lhs.idom
            rhs = rhs.idom
        return lhs
    # In this way, finding the immediate dominators turn into
    # a least-fixed-point computation. Common idom of the block
    # must match idom of its precedent blocks.
    adjust = True
    while adjust:
        adjust = False
        for block in proc.blocks[1:]:
            idom = reduce(common_dominator, block.prec)
            adjust |= (idom <> block.idom)
            block.idom = idom
    # At this point we've got dominance figured out. Next we want
    # to know where Locals are live.
    adjust = True
    while adjust:
        adjust = False
        for block in proc.blocks:
            L = len(block.depends)
            for succ in block.succ:
                block.depends.update(succ.depends)
                block.depends.difference_update(block.defines)
            if len(block.depends) > L:
                adjust = True
    # Next we recognize dominance frontiers. We cannot insert
    # phi -nodes here, because phi-nodes themselves are definitions.
    for block in proc.blocks:
        if len(block.prec) >= 2:
            for prec in block.prec:
                runner = prec
                while runner != block.idom:
                    runner.frontiers.add(block)
                    runner = runner.idom
    # Now it's time to insert the phi-nodes.
    for block in proc.blocks:
        for frontier in block.frontiers:
            for variable in block.defines:
                insert_phi(frontier, variable)
    # Next fill in the dominating flow into the phi-nodes and
    # substitute every Local with it's lookup value.
    # These operations are independent, so they can be done
    # inside the same loop.
    for block in proc.blocks:
        for prec in block.prec:
            for variable, phi in block.phi.items():
                phi.args[prec] = lookup(prec, variable)
        for instruction in block.instructions:
            for i, arg in enumerate(instruction.args):
                if isinstance(arg, Local):
                    instruction.args[i] = lookup_up(block, arg)

# phi-node insertion can be understood as yet another definition.
# therefore when inserting a phi-node, you need to trigger the
# insertion for dominance frontiers of the current block.
def insert_phi(block, variable):
    if variable in block.depends and variable not in block.phi:
        block.phi[variable] = Phi(block, {})
        for frontier in block.frontiers:
            insert_phi(frontier, variable)

# lookup & lookup_up are guarranteed to return a value 
# (and not a Local) once we have dominators figured out.
# They are mutually recursive.
def lookup(block, variable):
    if variable in block.defines:
        value = block.defines[variable]
        if isinstance(value, Local):
            return lookup_up(block, value)
        return value
    return lookup_up(block, variable)

# Difference between lookup and lookup_up is that lookup
# looks for variable from the definitions of the block.
def lookup_up(block, variable):
    if variable in block.phi:
        return block.phi[variable]
    return lookup(block.idom, variable)

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

# Will get their own module soon.
#class Binop(object):
#    def __init__(self, name):
#        self.name = name
#
#    def __repr__(self):
#        return self.name
#
#binary_opcodes = {
#    'BINARY_MULTIPLY': Binop('mul'),
#    'BINARY_ADD': Binop('add'),
#    'BINARY_SUB': Binop('sub'),
#    'BINARY_MODULO': Binop('mod'),
#}

# Error template for messaging about bad instruction.
error_template = """Operation not accepted by the target language.
  File {!r}, line {}
{}"""
