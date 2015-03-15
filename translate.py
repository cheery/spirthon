import annotator
import discovery

class TranslationUnit(object):
    def __init__(self):
        self.annotator = annotator.Annotator(self)
        self.functions = {}

    def build_function(self, functype, func):
        if func not in self.functions:
            self.functions[func] = f = discovery.build(functype, func)
            self.annotator.update(f)
            return f
        return self.functions[func]

    def translate(self):
        # should translate the program, or crash.
        return []
