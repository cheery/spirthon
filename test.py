from annotator import *
import discovery
import translate

def first_program(a, b, c):
    hello(world, abc)
    r.y = r.z
    a = a * 20
    return a + b.x * c % 5

# The second program demonstrates how errors are produced
# and presented to the user.
def second_program(a, b, c):
    if c > 10:
        a = a * 20
    return a + b.x * c % 5

def third_program(a, b):
    return a + b * 20

if __name__=='__main__':
    t_func = FuncType(t_int, [t_int, t_int])
    unit = translate.TranslationUnit()
    fn = unit.build_function(t_func, third_program)
    for op in fn.entry.ops:
        print op
    unit.annotator.run()
    instructions = unit.translate()
    for instruction in instructions:
        print instruction


# get it produce:
    from spirv import Instruction, Id
    output = [
        Instruction('OpConstant', 1234, 3, [20]),
        Instruction('OpIMul', 1234, 4, [Id(2), Id(3)]),
        Instruction('OpIAdd', 1234, 5, [Id(1), Id(4)]),
        Instruction('OpReturnValue', 0, 0, [Id(5)])
    ]

#    for operation in discovery.interpret(first_program):
#        print operation
#    print union(anything, unbound)
#    print union(t_vec2(t_uint), t_vec2(t_int))
#    print union(t_vec2(t_float), t_vec2(t_float))
#    print union(t_vec2(t_int), t_vec2(t_float))
#    print union(Constant(t_bool, True), Constant(t_bool, True))
#    print union(Constant(t_bool, False), Constant(t_bool, True))
#    for operation in discovery.interpret(second_program):
#        print operation
