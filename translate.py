import annotator
import discovery

class TranslationUnit(object):
    def __init__(self):
        self.annotator = annotator.Annotator(self)
        self.procedures = {}

    def build_function(self, functype, func):
        if func not in self.procedures:
            self.procedures[func] = proc = discovery.read(func)
            proc.annotation = functype
            self.annotator.update(proc)
            return proc
        return self.procedures[proc]

    def translate(self):
        # should translate the program, or crash.
        return []
