# Examples

## Overview

This directory contains a set of examples to illustrate the concepts described
in the paper.

The directory tree is structured as follows:

- `name.py` contains the example presented in Section 2 of the paper.

- `lenses/` contains examples of well-typed programs to illustrate the definition and use of field and method lenses.

- `refactor/` contains examples of well-typed programs with common refactor
  operations, such as removing a method, renaming a field, or changing method
  signatures.

- `typechecker/` contains examples of ill-typed programs that cover most of what the type
  checker can detect, such as missing lenses, wrong fields, etc.