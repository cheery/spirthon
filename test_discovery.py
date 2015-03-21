import discovery

def hello(x, y, z):
    while x:
        y = 10
        if True:
            z = 20
        elif True:
            pass
    return y

print discovery.read(hello)
