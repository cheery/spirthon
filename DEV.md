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
