Plan's to create a bytecode translator for SPIR-V, similar to what they've got in PyPy for compiling into C. As a starting point there's a prototype python to GLSL -compiler which I wrote last winter. It's really primitive so it's just slightly better than nothing.

Vulkan API's not out yet, so I can't try out my programs anywhere. But there's the glsl compiler I can study. Starting out with a decoder to grasp a general idea of SPIR-V. It might function directly as an intermediate representation for the translator. Additionally it may be nice later, if I want to extract attribute blocks from SPIR-V to help with configuring the shaders.

Requirements for the project:
 * It should be simple to use as a library.
 * The source programs should run in python just fine.
 * If translation turns out to be slow, the SPIR-V files need to be cached.
 * Allow composition of shaders by providing a function entry point, as long as the code is restricted to fit the gpu programming model.
 * Provide just enough vector arithmetic as a library shim, preferably compatible to be passed into vulkan API.

## Extracting Machine Readable Tables

I got to extract the specification from the glslang source files. Left in `misc/get_glslang_tables.py` as an additional documentation. I'm not updating this file, but in case I need to do it again I'll use the tool to do it.

I hope there will be a good machine-readable specification of SPIR-V, possibly in various format everyone will use instead of copy/paste programming names and formatting from the specification.

An idea came out after writing on. The HTML in the registry is so well structured that the tables could be directly recovered from the documents describing them. This would verify they are never out of sync.

There seem to be some differences in variable names between glslang and what SPIR-V specification specifies. I had to rewrite some names to get them match with each other.

I hope the result type and id fields are correct. They denote when an instruction returns a value. Somewhat useful detail for anything that processes the code.

Additionally I wonder what to do with fields that allow masking on themselves. Maybe they need to be specified separately in the generator. Added FunctionControlMask to masks. I'll see how it goes.
## Decoding & Encoding

There's the question what to do when you see a bad instruction. It could be the decoding is used to just analyse the source code, so it may make sense to just pass the bad instructions through. I put the traceback message into the unknown instruction, so it gives a cue if the decoding actually failed.

SPIR-V seems to be slightly easier to encode than it is to decode. There's not big difference in that though. If I improved my decoder a bit, it might become about as simple as my decoder.

I like the SPIR-V string encoding/decoding a lot. It's simpler than I had thought it would be after reading the spec.

It seems that my encoder and decoder works now. The decoder manages to decode all instructions in my sample files. I used the decoder to check that the encoder works too.

## Overview

To translate from python bytecode into SPIR-V, I have to decode, analyse and translate the high level representation of the bytecode into intermediate representation. SPIR-V requires that it's in static single assignment form.

Fortunately there's plenty of knowledge about these problems. RPython got a working implementation I can study and read about.

RPython divides the problem into decoding, annotation and substitution phases. The translation starts with decoding, but eventually annotation issues more code blocks to be decoded. Annotator searches for least generic type, which satisfies every constraint. As in least fixed point. When least generic types have been found, the python operations substitute into target language operations.

I'm planning to do the same.

## Decoding Python Bytecode

The first thing in the puzzle is reading the bytecode. Fortunately python bytecode format isn't complicated. Using the opcode -module you can crack it open in less time than it took me to write the last three sentences here. It's because each instruction has either one argument, or no arguments. if op >= opcode.HAVE_ARGUMENT, then the instruction is 3 bytes long, otherwise it's just one byte. Additionally if the argument doesn't fit into 2 bytes, the whole instruction can be prefixed with the EXTENDED_ARG -instruction to provide additional 2 bytes for the argument.

There are few more complications to decoding python bytecode. First, I won't likely end up translating every instruction, so the finished translator can encounter operations that it cannot translate. The program should produce enough error message that I could quickly locate the cause.

While programming my interpreter, I may intentionally give it bad input. For that I need a small window into the instruction block that cause the problem. If it's too big, it discourages the end-user. For a start I put it return the next 5 instructions. The error message looks like this:

    Traceback (most recent call last):
      File "test.py", line 104, in <module>
        raise Exception(error_message)
    Exception: Operation not accepted by the target language.
      File 'test.py', line 6
    --> 31 COMPARE_OP 4
        34 POP_JUMP_IF_FALSE 50
        37 LOAD_FAST 0
        40 LOAD_CONST 2
        43 BINARY_MULTIPLY 0

There's one thing missing here. The translation starts from the entry point and discovers more function blocks. When there's an error I'd like to present a "discovery traceback" of how we ended up to compile the failing function block.

I'm already mostly beyond what I did in [my previous interpreter](https://gist.github.com/cheery/642cc04394ebbb3b08d6). I named this part of the translation to the discovery -stage. It doesn't do much anything else to the code but dump it to basic blocks.

## Annotation Phase & Basic Blocks

After the python bytecode is ripped into pieces, and if we are doing the same as RPython, we should next find the "least generic type" for everything. This is implemented as a least-fixed-point operation, though the engine may 'discover' more function blocks to translate at this point.

For annotation, every value is first assigned "Unbound" -annotation, which means for an inexistent, most restricted type. The most generic type is "Anything". Between there are abstract types that translate well to our target language. Annotation stage infers types for every annotation and merges them into least generic types until an application of rule no longer cause any changes.

At this point it's may be good to introduce an idea of a translation unit, which memoizes and triggers translation of things inserted into the unit. The contents of the translation unit will be dumped into SPIR-V on success.

Before the annotation phase gets to run, it may make sense to translate the whole function block first, so we can do some flow analysis and insert the phi nodes. This way we don't discourage variable name reuse when it makes sense.

## The Annotator

I am not entirely aware of which rules the annotator should use in its fixed point computation. I'm sure I will figure out something next week. It looks like that annotators work would become easier if I eliminate the variables and assignments early.

Sleeping over it, I figured the annotator mostly cannot work backwards in the flow graph because the python operations and calls depend on the arguments passed into them.

## SSA Construction

I coded abstract interpreter to emit assignment operations, but realised it doesn't need to do that. It's enough to mark into the block which variables it defined.

If it turns out that python holds stack values on branching, it'll be necessary to insert Local -objects for every stack value that passes a block boundary. Refrain implementing that until it's needed.

Once there's an interest to provide loops and conditionals phi-nodes need to be inserted. When doing that, remember the block.defines may contain Local -objects.

## Minor adjustments

Replaced `annotator.unbound` with `None` to remove the discovery stages dependence on the annotation stage. Also had to add backwards links from operations to basic blocks, from basic blocks to function blocks.

'Improvement' of an annotation should trigger a reaction. Additionally some of them, such as the argument annotation should act on the function block.

Normal functions should be fetched and retrieved when annotator hits them. They should cause flowback back to their callees.

Binary operations should wait until they have their arguments, then annotate using the rules defined for them. It seems we have to define an environment of some kind.

The environment brings up an one question. Optimally every spirthon program would be a python program too. But some OpenCL or GLSL functions are dependent on thread state. I haven't heard python would have dynamic scope for this kind of things.

## Complete SSA conversion

I realised if not trying to solve the problem now then solving it later could become unnecessarily hard. Also it's one of the fun problems in the project.

The annotator needs to annotate constants too, so I put it to generate const -instructions for LOAD_CONST. It seems to neatly match the SPIR-V as well.

Reviewing the discovery.py, I found out that my way to complete variables in phi-node insertion could cause an error in complex program flow. The error would appear in situations such as this:

    x = 2
    if a:
        x = 3
        if b:
            pass
        x = 10
    return x

The way the code checked the dominators, it would have assigned `x = 3` to phi -node instead of `x = 10`

Additionally I found a possible problem with definition of function arguments.

Third I found out a situation that happens at the code:

    z = 5
    while a:
        if b:
            z = 20
    return z

The appropriate phi-nodes were simply not inserted.
