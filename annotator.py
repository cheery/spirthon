# Annotator needs to find the least generic type for everything. 
# To do that, it needs to hold a model of our types.
class Annotator(object):
    def __init__(self, unit):
        self.unit = unit
        self.stack = []

    def update(self, func):
        for block in func:
            for op in block.ops:
                if not op.queued:
                    self.stack.append(op)
                    op.queued = True

    def run(self):
        while len(self.stack) > 0:
            op = self.stack.pop()
            # Should annotate here, if some of the fields change,
            # should reschedule the used fields.

# SPIR-V annotation may need much simpler rules than specified here.

# Anything -annotation in translation unit most likely means
# that the translation failed.
class Anything(object):
    specificity = 0
    parametric = False

    def __repr__(self):
        return 'anything'

# The next most specific type after 'Unbound'.
class Constant(object):
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def __repr__(self):
        return 'Constant({}, {})'.format(self.type, self.value)

class Unbound(object):
    def __repr__(self):
        return 'unbound'

class FuncType(object):
    def __init__(self, restype, argtypes):
        self.restype = restype
        self.argtypes = argtypes

    def __getitem__(self, index):
        return self.argtypes[index]

    def __len__(self):
        return len(self.argtypes)

    def __repr__(self):
        return '({}) ->'.format(', '.join(map(repr, self.argtypes)), self.restype)

class Type(object):
    def __call__(self, parameter):
        assert self.parametric
        return Parametric(self, parameter)

    def __init__(self, name, generic, parametric=False):
        self.name = name
        self.generic = generic
        self.parametric = parametric
        self.specificity = generic.specificity+1

    def __repr__(self):
        return self.name

class Parametric(object):
    def __init__(self, func, parameter):
        self.func = func
        self.parameter = parameter

    def __repr__(self):
        return "{}({})".format(self.func, self.parameter)

# Types are treated as notation. They should be uniquely identified.
anything = Anything()
unbound = Unbound()

# not sure whether these belong here.
t_int = Type('int', anything)
t_uint = Type('uint', t_int)
t_bool = Type('bool', t_uint)

t_float = Type('float', anything)

t_vec2 = Type('vec2', anything, parametric=True)
t_vec3 = Type('vec3', anything, parametric=True)
t_vec4 = Type('vec4', anything, parametric=True)

# Thought about doing them this way, but realized types
# would require unification by their type hierarchies.
# # nullable = Type('nullable', anything, parametric=True)
# # instance = Type('instance', nullable, parametric=True)
# # t_null = Type('null', nullable)

# I don't want parametric types to leak from
# their parametric container.
def union(a, b):
    c = union_raw(a, b)
    while isinstance(c, Type) and c.parametric:
        c = c.generic
    return c
# But we still may use unification results which
# return parametric types.
def union_raw(a, b):
    if a is b:
        return a
    if a is unbound:
        return b
    if b is unbound:
        return a
    if isinstance(a, Constant) and isinstance(b, Constant):
        if a.value == b.value:
            return a
        else:
            return union_raw(a.type, b.type)
    elif isinstance(a, Constant):
        return union_raw(a.type, b)
    elif isinstance(b, Constant):
        return union_raw(a, b.type)
    if isinstance(a, Type) and isinstance(b, Type):
        specificity = min(a.specificity, b.specificity)
        while a.specificity > specificity:
            a = a.generic
        while b.specificity > specificity:
            b = b.generic
        while a is not b:
            a = a.generic
            b = b.generic
        assert a is not None
        return a
    elif isinstance(a, Parametric) and isinstance(b, Parametric):
        tp = union_raw(a.func, b.func)
        if tp.parametric:
            return Parametric(tp, union(a.parameter, b.parameter))
        else:
            return tp
    elif isinstance(a, Parametric):
        tp = union_raw(a.func, b)
        if tp.parametric:
            return Parametric(tp, a.parameter)
        else:
            return tp
    elif isinstance(b, Parametric):
        tp = union_raw(b.func, a)
        if tp.parametric:
            return Parametric(tp, b.parameter)
        else:
            return tp
    elif isinstance(a, FuncType) and isinstance(b, FuncType) and len(a) == len(b):
        return FuncType(
            union(a.restype, b.restype),
            [union(c, d) for c, d in zip(a, b)])
    return anything
