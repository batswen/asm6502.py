from Const import *

from Token import Token
from Lexer import Lexer

class Assembler:
    def __init__(self, lexer, labels):
        self.lexer = lexer
        self.labels = labels
        self.pc = 0
        self.current_token = self.lexer.next_token()
        self.line = self.current_token.line
        self.run = 1

    def assemble(self):
        try:
            self.lexer.reset()
            self.pc = 0
            self.current_token = self.lexer.next_token()
            self.line = self.current_token.line
            print("Pass 1")
            self.run = 1
            self.compile() # pass 1: define labels

            self.lexer.reset()
            self.pc = 0
            self.current_token = self.lexer.next_token()
            self.line = self.current_token.line
            print("Pass 2")
            self.run = 2
            self.compile() # pass 2: assemble
        except Exception as e:
            print(f"{e} in {self.line}")

    def skip(self, token_type):
        if self.current_token.test(token_type):
            self.current_token = self.lexer.next_token()
            self.line = self.current_token.line
        else:
            raise Exception(f"Syntax (Expected: {token_type}, got: {self.current_token.token_type})")

    def factor(self):
        # print("factor",self.current_token)
        if self.current_token.test(LPAREN): #this could be a problem
            self.skip(LPAREN)
            result = self.expression()
            self.skip(RPAREN)
            return result
        if self.current_token.test(NUMBER): #hex/dec/bin
            token = self.current_token
            self.skip(NUMBER)
            return token.value
        if self.current_token.test(LT): # <expr
            self.skip(LT)
            return self.expression() % 256
        if self.current_token.test(GT): # >expr
            self.skip(GT)
            return self.expression() // 256
        if self.current_token.test(LABEL):
            token = self.current_token
            self.skip(LABEL)
            if token.value not in self.labels:
                self.labels[token.value] = { "value": 0xffff, "line": self.line }
            return self.labels[token.value]["value"]
        return None

    def term(self):
        result = self.factor()
        while self.current_token.token_type in (MUL, DIV):
            if self.current_token.test(MUL):
                self.skip(MUL)
                result *= self.factor()
            else:
                self.skip(DIV)
                result /= self.factor()
        return result

    def pm_expr(self):
        result = self.term()
        while self.current_token.token_type in (PLUS, MINUS):
            if self.current_token.test(PLUS):
                self.skip(PLUS)
                result += self.term()
            else:
                self.skip(MINUS)
                result -= self.term()
        return result
    def and_expr(self):
        result = self.pm_expr()
        while self.current_token.token_type == AND:
            self.skip(AND)
            result &= self.pm_expr()
        return result
    def eor_expr(self):
        result = self.and_expr()
        while self.current_token.token_type == EOR:
            self.skip(EOR)
            result ^= self.and_expr()
        return result
    def expression(self):
        result = self.eor_expr()
        while self.current_token.token_type == OR:
            self.skip(OR)
            result |= self.eor_expr()
        return result

    def set_label(self, label, arg):
        if label not in self.labels:
            self.labels[label] = { "value": 0xffff, "line": self.line }
        self.labels[label]["value"] = arg
    def dump_labels(self):
        for label in self.labels:
            if self.labels[label]["line"] != -1:
                print(f"{self.labels[label]['line']:05} {label:16}=${self.labels[label]['value']:04x} ({self.labels[label]['value']})")

    def compile(self):
        while self.current_token.token_type != EOF:
            token = self.current_token
            if token.line != self.line:
                print(self.line,token)
            if token.test(NEWLINE):
                self.skip(NEWLINE)
                continue
            if token.test(COLON):
                self.skip(COLON)
                continue
            if token.test(LABEL):
                self.skip(LABEL)
                if self.current_token.test(ASSIGN):
                    self.skip(ASSIGN)
                    self.set_label(token.value, self.expression())
                else:
                    self.set_label(token.value, self.pc)
                    if self.run == 2: # fix forward refs
                        self.labels[token.value]["line"] = self.line
                continue
            if token.test(ORG):
                self.skip(ORG)
                self.pc = self.expression()
                continue
            # if token.test(LET:
            #     self.skip(LET)
            #     label = self.current_token
            #     self.skip(LABEL)
            #     self.skip(ASSIGN)
            #     arg = self.expression()
            #     self.set_label(label.value, arg)
            #     continue
            self.skip(OPCODE)
            if self.current_token.token_type in (COLON, NEWLINE, EOF): #akku/implied
                self.asm_command(token, IMPLIED, None)
                continue

            if self.current_token.test(HASH): # token is immediate
                self.skip(HASH)
                arg = self.expression()
                if arg > 255:
                    raise Exception("Illegal quantity (#)")
                self.asm_command(token, IMMEDIATE, arg)
                continue

            if self.current_token.test(LPAREN): # ()
                self.skip(LPAREN)
                arg = self.expression()
                if self.current_token.test(COMMAX): # ,x)
                    self.skip(COMMAX)
                    self.skip(RPAREN)
                    if arg > 255:
                        raise Exception("Illegal quantity (must be 0..255)")
                    self.asm_command(token, USELESS, arg)
                elif self.current_token.test(RPAREN): # )
                    self.skip(RPAREN)
                    if self.current_token.test(COMMAY): # ),y
                        self.skip(COMMAY)
                        if arg > 255:
                            raise Exception("Illegal quantity (must be 0..255)")
                        self.asm_command(token, INDIRECTY, arg)
                    else: # indirect )
                        self.asm_command(token, INDIRECT, arg)
                continue
            #abs/zp (,x,y)
            arg = self.expression()

            # zp,x/abs,x
            if self.current_token.test(COMMAX):
                self.skip(COMMAX)
                if arg <= 255 and ZP in OPCODES[token.value]:
                    self.asm_command(token, ZPX, arg)
                else:
                    self.asm_command(token, ABSOLUTEX, arg)
                continue
            # zp,y/abs,y
            if self.current_token.test(COMMAY):
                self.skip(COMMAY)
                if arg <= 255 and ZP in OPCODES[token.value]:
                    self.asm_command(token, ZPY, arg)
                else:
                    self.asm_command(token, ABSOLUTEY, arg)
                continue
            # zp/abs
            if arg <= 255 and ZP in OPCODES[token.value]:
                self.asm_command(token, ZP, arg)
            elif RELATIVE in OPCODES[token.value]:
                self.asm_command(token, RELATIVE, arg)
            else:
                self.asm_command(token, ABSOLUTE, arg)
    def asm_command(self, token, mode, arg):
        if mode not in OPCODES[token.value.lower()]:
            raise Exception("Unknown addressing mode")
        if arg is not None:
            arg_low = arg % 256
            arg_high = arg // 256
            arg_relative = 0

            if arg <= self.pc:
                arg_relative = 254 - (self.pc - arg)
            else:
                arg_relative = arg - self.pc - 2

        if self.run == 2:
            if mode == IMPLIED:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x}       {token.value}")
            # zero page
            elif mode == IMMEDIATE:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} #${arg:02x}    ;{arg}")
            elif mode == ZP:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} ${arg:02x}     ;{arg}")
            elif mode == ZPX:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} ${arg:02x},x   ;{arg}")
            elif mode == ZPY:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} ${arg:02x},y   ;{arg}")
            elif mode == USELESS:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} (${arg:02x},x) ;{arg}")
            elif mode == INDIRECTY:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg:02x}    {token.value} (${arg:02x}),y ;{arg}")
            # relative
            elif mode == RELATIVE:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg_relative:02x}    {token.value} ${arg:04x}   ;{arg}")
            # absolute
            elif mode == ABSOLUTE:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg_low:02x} {arg_high:02x} {token.value} ${arg:04x}   ;{arg}")
            elif mode == ABSOLUTEX:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg_low:02x} {arg_high:02x} {token.value} ${arg:04x},x ;{arg}")
            elif mode == ABSOLUTEY:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg_low:02x} {arg_high:02x} {token.value} ${arg:04x},y ;{arg}")
            elif mode == INDIRECT:
                print(f"{self.line:05} {self.pc:04x} {OPCODES[token.value][mode]:02x} {arg_low:02x} {arg_high:02x} {token.value} (${arg:04x}) ;{arg}")
        self.pc += 1
        if mode > IMPLIED:
            self.pc += 1
        if mode >= ABSOLUTE:
            self.pc += 1

if __name__ == "__main__":
    pass