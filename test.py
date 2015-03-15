import discovery

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

import dis

if __name__=='__main__':
    for operation in discovery.interpret(first_program):
        print operation
    for operation in discovery.interpret(second_program):
        print operation
