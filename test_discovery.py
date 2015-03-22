import discovery

def hello(x, y, z):
    while x:
        y = 10
        if True:
            z = 20
        elif True:
            pass
    return z

def hello2(x, a, b):
    if a:
        x = 3
        if b:
            pass
        x = 10
    return x

print discovery.read(hello)
