# Python to SPIR-V Compiler

**Notice:** This library is outdated a lot. I advice you to get familiar with the machine readable specification in the [Khronos SPIR-V registry][spec], as well as read the official specification.

 [spec]: https://www.khronos.org/registry/spir-v/

Translation from python bytecode to SPIR-V.

This might come out as something, or then not. It would be a shame to not try.

There's something here that could be useful on its own:

 * A SPIR-V decoder/encoder (or assembler/disassembler if you fancy that name) in the `spirv.py`.
 * Machine readable specification for SPIR-V in json -format that can be used to drive a decoder/encoder. And the script used to generate it.

## Status

Made an instruction decoder and encoder that work from the specification I generated from glslang earlier. Now I need to adjust my translator prototype to use SPIR-V instructions.

[Development log](DEV.md)

## Links

 * [Khronos SPIR-V registry](https://www.khronos.org/registry/spir-v/)
