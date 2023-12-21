The .test files in this directory are used to quickly confirm expected behaviour of the puya compiler

Each case is indicated with the prefix `## case: ` followed by a name for the case
Multiple files can be created in a test by using the prefix `## path: ` followed by the file name
After these directives the following code is treated as puya code, and used as the input source files

The puya code can be annotated with expected compiler log messages from the compiler using the following prefixes

`## E: ` An expected error fo this line
`## W: ` An expected warning for this line
`## N: ` An expected info for this line

The AWST (Abstract Puya Syntax Tree) can also be verified by using
`## expected: awst` followed by the expected output for the AWST after it is transformed back to text

To ensure tests run as quick as possible all test cases in a `.test` file are compiled together in one pass, and then
analyzed for expected output
