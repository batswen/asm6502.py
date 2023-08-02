# asm6502.py
An assembler for the 6502 cpu written in python

Start: python asm.py

byte, word, text are missing

## opcodes
Case insensitive

## pseudo opcodes
Case insensitive
* org/base/.ba adr or label: set start address
* label = number: define label

## labels
Case sensitive

Must start with a letter or underscore or dot (a-z_.), then (a-z0-9_.)

## numbers
Numbers must be in range 0..65535 or 0..255 depending on the command.
Hex numbers must start with $, binary numbers with a %.

Use +,-,*,/ for addition, subtraction, multiplication and division