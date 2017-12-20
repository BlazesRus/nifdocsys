#!/usr/bin/python

# TODO: split in multiple files

"""
This module generates C++ code for Niflib from the NIF file format specification XML.

@author: Amorilia
@author: Shon

@contact: http://niftools.sourceforge.net

@copyright:
Copyright (c) 2005, NIF File Format Library and Tools.
All rights reserved.

@license:
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

  - Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  - Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

  - Neither the name of the NIF File Format Library and Tools
    project nor the names of its contributors may be used to endorse
    or promote products derived from this software without specific
    prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

@var native_types: Maps name of basic or compound type to name of type implemented manually in Niflib.
    These are the types tagged by the niflibtype tag in the XML. For example,
    if a (basic or compound) type with C{name="ferrari"} has C{niflibtype="car"}
    then C{native_types["ferrari"]} equals the string C{"car"}.
@type native_types: C{dictionary}

@var basic_types: Maps name of basic type to L{Basic} instance.
@type basic_types: C{dictionary}

@var compound_types:  Maps name of compound type to a L{Compound} instance.
@type compound_types: C{dictionary}

@var block_types: Maps name of the block name to a L{Block} instance.
@type block_types: C{list}

@var basic_names: Sorted keys of L{basic_types}.
@type basic_names: C{list}

@var compound_names: Sorted keys of L{compound_types}.
@type compound_names: C{list}

@var block_names: Sorted keys of L{block_types}.
@type block_names: C{list}
"""

from __future__ import unicode_literals

from xml.dom.minidom import Node, parse

import os
import io
import re
import types

#
# global data
#

native_types = {}
native_types['TEMPLATE'] = 'T'
basic_types = {}
enum_types = {}
flag_types = {}
compound_types = {}
block_types = {}
version_types = {}

basic_names = []
compound_names = []
enum_names = []
flag_names = []
block_names = []
version_names = []

NATIVETYPES = {
    'bool' : 'bool',
    'byte' : 'byte',
    'uint' : 'unsigned int',
    'ulittle32' : 'unsigned int',
    'ushort' : 'unsigned short',
    'int' : 'int',
    'short' : 'short',
    'BlockTypeIndex' : 'unsigned short',
    'char' : 'byte',
    'FileVersion' : 'unsigned int',
    'Flags' : 'unsigned short',
    'float' : 'float',
    'hfloat' : 'hfloat',
    'HeaderString' : 'HeaderString',
    'LineString' : 'LineString',
    'Ptr' : '*',
    'Ref' : 'Ref',
    'StringOffset' : 'unsigned int',
    'StringIndex' : 'IndexString',
    'SizedString' : 'string',
    'string' : 'IndexString',
    'Color3' : 'Color3',
    'Color4' : 'Color4',
    #'ByteColor3' : 'ByteColor3', # TODO: Niflib type
    'ByteColor4' : 'ByteColor4',
    'FilePath' : 'IndexString',
    'Vector3' : 'Vector3',
    'Vector4' : 'Vector4',
    'Quaternion' : 'Quaternion',
    'Matrix22' : 'Matrix22',
    'Matrix33' : 'Matrix33',
    'Matrix34' : 'Matrix34',
    'Matrix44' : 'Matrix44',
    'hkMatrix3' : 'InertiaMatrix',
    'ShortString' : 'ShortString',
    'Key' : 'Key',
    'QuatKey' : 'Key',
    'TexCoord' : 'TexCoord',
    'Triangle' : 'Triangle',
    'BSVertexData' : 'BSVertexData',
    'BSVertexDataSSE' : 'BSVertexData',
    #'BSVertexDesc' : 'BSVertexDesc'
}

#
# HTML Template class
#

class Template:
    """
    This class processes template files.  These files have tags enclosed
    in curly brackets like this: {tag}, which are replaced when a template
    is processed.
    """
    def __init__(self):
        """Initialize variable dictionary"""
        self.vars = {}

    def set_var(self, var_name, value):
        """Set data in variable dictionary"""
        self.vars[var_name] = value

    def parse(self, file_name):
        """Open file and read contents to txt variable"""
        f = io.open(file_name, 'rt', 1, 'utf-8')
        txt = f.read()
        f.close()

        #Loop through all variables, replacing them in the template text
        for i in self.vars:
            txt = txt.replace('{' + i + '}', self.vars[i].encode('utf-8').decode('utf-8', 'strict'))

        #return result
        return txt

def class_name(name_in):
    """
    Formats a valid C++ class name from the name format used in the XML.
    @param n: The class name to format in C++ style.
    @type n: string
    @return The resulting valid C++ class name
    @rtype: string
    """
    if name_in is None:
        return None
    try:
        return native_types[name_in]
    except KeyError:
        return name_in.replace(' ', '_').replace(":", "_")

    if name_in is None:
        return None
    try:
        return native_types[name_in]
    except KeyError:
        pass
    if name_in == 'TEMPLATE':
        return 'T'
    name_out = ''
    for i, char in enumerate(name_in):
        if char.isupper():
            if i > 0:
                name_out += '_'
            name_out += char.lower()
        elif char.islower() or char.isdigit():
            name_out += char
        else:
            name_out += '_'
    return name_out

def define_name(name_in):
    """
    Formats an all-uppercase version of the name for use in C++ defines.
    @param n: The class name to format in define style.
    @type n: string
    @return The resulting valid C++ define name
    @rtype: string
    """
    name_out = ''
    for i, char in enumerate(name_in):
        if char.isupper():
            if i > 0:
                name_out += '_'
                name_out += char
            else:
                name_out += char
        elif char.islower() or char.isdigit():
            name_out += char.upper()
        else:
            name_out += '_'
    return name_out

def member_name(name_in):
    """
    Formats a version of the name for use as a C++ member variable.
    @param name_in: The attribute name to format in variable style.
    @type name_in: string
    @return The resulting valid C++ variable name
    @rtype: string
    """
    if name_in is None or name_in == 'ARG':
        return name_in
    name_out = ''
    lower = True
    for char in name_in:
        if char == ' ':
            lower = False
        elif char.isalnum():
            if lower:
                name_out += char.lower()
            else:
                name_out += char.upper()
                lower = True
        elif char == '\\': # arg member access operator
            name_out += '.'
        else:
            name_out += '_'
            lower = True
    return name_out

def version2number(s):
    """
    Translates a legible NIF version number to the packed-byte numeric representation. For example, "10.0.1.0" is translated to 0x0A000100.
    @param s: The version string to translate into numeric form.
    @type s: string
    @return The resulting numeric version of the given version string.
    @rtype: int
    """
    if not s:
        return None
    l = s.split('.')
    if len(l) > 4:
        assert False
        return int(s)
    if len(l) == 2:
        version = 0
        version += int(l[0]) << (3 * 8)
        if len(l[1]) >= 1:
            version += int(l[1][0]) << (2 * 8)
        if len(l[1]) >= 2:
            version += int(l[1][1]) << (1 * 8)
        if len(l[1]) >= 3:
            version += int(l[1][2:])
        return version
    else:
        version = 0
        for i in range(0, len(l)):
            version += int(l[i]) << ((3-i) * 8)
            #return (int(l[0]) << 24) + (int(l[1]) << 16) + (int(l[2]) << 8) + int(l[3])
        return version

def userversion2number(s):
    """
    Translates a legible NIF user version number to the packed-byte numeric representation.
    Currently just converts the string to an int as this may be a raw number.
    Probably to be used just in case this understanding changes.
    @param s: The version string to translate into numeric form.
    @type s: string
    @return The resulting numeric version of the given version string.
    @rtype: int
    """
    if not s:
        return None
    return int(s)

def scanBrackets(expr_str, fromIndex=0):
    """Looks for matching brackets.

    >>> scanBrackets('abcde')
    (-1, -1)
    >>> scanBrackets('()')
    (0, 1)
    >>> scanBrackets('(abc(def))g')
    (0, 9)
    >>> s = '  (abc(dd efy 442))xxg'
    >>> startpos, endpos = scanBrackets(s)
    >>> print s[startpos+1:endpos]
    abc(dd efy 442)
    """
    startpos = -1
    endpos = -1
    scandepth = 0
    for scanpos in range(fromIndex, len(expr_str)):
        scanchar = expr_str[scanpos]
        if scanchar == "(":
            if startpos == -1:
                startpos = scanpos
            scandepth += 1
        elif scanchar == ")":
            scandepth -= 1
            if scandepth == 0:
                endpos = scanpos
                break
    else:
        if startpos != -1 or endpos != -1:
            raise ValueError("expression syntax error (non-matching brackets?)")
    return (startpos, endpos)

class Expression(object):
    """This class represents an expression.

    >>> class A(object):
    ...     x = False
    ...     y = True
    >>> a = A()
    >>> e = Expression('x || y')
    >>> e.eval(a)
    1
    >>> Expression('99 & 15').eval(a)
    3
    >>> bool(Expression('(99&15)&&y').eval(a))
    True
    >>> a.hello_world = False
    >>> def nameFilter(s):
    ...     return 'hello_' + s.lower()
    >>> bool(Expression('(99 &15) &&WoRlD', name_filter = nameFilter).eval(a))
    False
    >>> Expression('c && d').eval(a)
    Traceback (most recent call last):
        ...
    AttributeError: 'A' object has no attribute 'c'
    >>> bool(Expression('1 == 1').eval())
    True
    >>> bool(Expression('1 != 1').eval())
    False
    """
    operators = ['==', '!=', '>=', '<=', '&&', '||', '&', '|', '-', '+', '>', '<', '/', '*']
    def __init__(self, expr_str, name_filter=None):
        self._code = expr_str
        left, self._op, right = self._partition(expr_str)
        self._left = self._parse(left, name_filter)
        if right:
            self._right = self._parse(right, name_filter)
        else:
            self._right = ''

    def eval(self, data=None):
        """Evaluate the expression to an integer."""

        if isinstance(self._left, Expression):
            left = self._left.eval(data)
        elif isinstance(self._left, str):
            left = getattr(data, self._left) if self._left != '""' else ""
        else:
            assert isinstance(self._left, int) # debug
            left = self._left

        if not self._op:
            return left

        if isinstance(self._right, Expression):
            right = self._right.eval(data)
        elif isinstance(self._right, str):
            right = getattr(data, self._right) if self._right != '""' else ""
        else:
            assert isinstance(self._right, int) # debug
            right = self._right

        if self._op == '==':
            return int(left == right)
        elif self._op == '!=':
            return int(left != right)
        elif self._op == '>=':
            return int(left >= right)
        elif self._op == '<=':
            return int(left <= right)
        elif self._op == '&&':
            return int(left and right)
        elif self._op == '||':
            return int(left or right)
        elif self._op == '&':
            return left & right
        elif self._op == '|':
            return left | right
        elif self._op == '-':
            return left - right
        elif self._op == '+':
            return left + right
        elif self._op == '/':
            return left / right
        elif self._op == '*':
            return left * right
        elif self._op == '!':
            return not left
        else:
            raise NotImplementedError("expression syntax error: operator '" + self._op + "' not implemented")

    def __str__(self):
        """Reconstruct the expression to a string."""

        left = str(self._left)
        if not self._op:
            return left
        right = str(self._right)
        return left + ' ' + self._op + ' ' + right

    def encode(self, encoding):
        """
        To allow encode() to be called on an Expression directly as if it were a string
        (For Python 2/3 cross-compatibility.)
        """
        return self.__str__().encode(encoding)

    @classmethod
    def _parse(cls, expr_str, name_filter=None):
        """Returns an Expression, string, or int, depending on the
        contents of <expr_str>."""
        # brackets or operators => expression
        if ("(" in expr_str) or (")" in expr_str):
            return Expression(expr_str, name_filter)
        for op in cls.operators:
            if expr_str.find(op) != -1:
                return Expression(expr_str, name_filter)

        mver = re.compile("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+")
        iver = re.compile("[0-9]+")
        # try to convert it to an integer
        try:
            if mver.match(expr_str):
                return "0x%08X"%(version2number(expr_str))
            elif iver.match(expr_str):
                return str(int(expr_str))
        except ValueError:
            pass
        # failed, so return the string, passed through the name filter
        return name_filter(expr_str) if name_filter else expr_str

    @classmethod
    def _partition(cls, expr_str):
        """Partitions expr_str. See examples below.

        >>> Expression._partition('abc || efg')
        ('abc', '||', 'efg')
        >>> Expression._partition('abc||efg')
        ('abc', '||', 'efg')
        >>> Expression._partition('abcdefg')
        ('abcdefg', '', '')
        >>> Expression._partition(' abcdefg ')
        ('abcdefg', '', '')
        >>> Expression._partition(' (a | b) & c ')
        ('a | b', '&', 'c')
        >>> Expression._partition('(a | b)!=(b&c)')
        ('a | b', '!=', 'b&c')
        >>> Expression._partition('(a== b) &&(( b!=c)||d )')
        ('a== b', '&&', '( b!=c)||d')
        """
        # check for unary operators
        if expr_str.strip().startswith('!'):
            return expr_str.lstrip(' !'), '!', None
        lenstr = len(expr_str)
        # check if the left hand side starts with brackets
        # and if so, find the position of the starting bracket and the ending
        # bracket
        left_startpos, left_endpos = cls._scanBrackets(expr_str)
        if left_startpos >= 0:
            # yes, it is a bracketted expression
            # so remove brackets and whitespace,
            # and let that be the left hand side
            left_str = expr_str[left_startpos+1:left_endpos].strip()

            # the next token should be the operator
            # find the position where the operator should start
            op_startpos = left_endpos+1
            while op_startpos < lenstr and expr_str[op_startpos] == " ":
                op_startpos += 1
            if op_startpos < lenstr:
                # to avoid confusion between && and &, and || and |,
                # let's first scan for operators of two characters
                # and then for operators of one character
                for op_endpos in range(op_startpos+1, op_startpos-1, -1):
                    op_str = expr_str[op_startpos:op_endpos+1]
                    if op_str in cls.operators:
                        break
                else:
                    raise ValueError("expression syntax error: expected operator at '%s'"%expr_str[op_startpos:])
            else:
                return cls._partition(left_str)
        else:
            # it's not... so we need to scan for the first operator
            for op_startpos, ch in enumerate(expr_str):
                if ch == ' ':
                    continue
                if ch == '(' or ch == ')':
                    raise ValueError("expression syntax error: expected operator before '%s'"%expr_str[op_startpos:])
                # to avoid confusion between && and &, and || and |,
                # let's first scan for operators of two characters
                for op_endpos in range(op_startpos+1, op_startpos-1, -1):
                    op_str = expr_str[op_startpos:op_endpos+1]
                    if op_str in cls.operators:
                        break
                else:
                    continue
                break
            else:
                # no operator found, so we are done
                left_str = expr_str.strip()
                op_str = ''
                right_str = ''
                return left_str, op_str, right_str
            # operator found! now get the left hand side
            left_str = expr_str[:op_startpos].strip()

        return left_str, op_str, expr_str[op_endpos+1:].strip()

    @staticmethod
    def _scanBrackets(expr_str, fromIndex=0):
        """Looks for matching brackets.

        >>> Expression._scanBrackets('abcde')
        (-1, -1)
        >>> Expression._scanBrackets('()')
        (0, 1)
        >>> Expression._scanBrackets('(abc(def))g')
        (0, 9)
        >>> s = '  (abc(dd efy 442))xxg'
        >>> startpos, endpos = Expression._scanBrackets(s)
        >>> print s[startpos+1:endpos]
        abc(dd efy 442)
        """
        startpos = -1
        endpos = -1
        scandepth = 0
        for scanpos in range(fromIndex, len(expr_str)):
            scanchar = expr_str[scanpos]
            if scanchar == "(":
                if startpos == -1:
                    startpos = scanpos
                scandepth += 1
            elif scanchar == ")":
                scandepth -= 1
                if scandepth == 0:
                    endpos = scanpos
                    break
        else:
            if startpos != -1 or endpos != -1:
                raise ValueError("expression syntax error (non-matching brackets?)")
        return (startpos, endpos)

    def code(self, prefix='', brackets=True, name_filter=None):
        """Format an expression as a string.
        @param prefix: An optional prefix.
        @type prefix: string
        @param brackets: If C{True}, then put expression between brackets.
        @type prefix: string
        @return The expression formatted into a string.
        @rtype: string
        """
        lbracket = "(" if brackets else ""
        rbracket = ")" if brackets else ""
        if not self._op:
            if not self.lhs:
                return ''
            if isinstance(self.lhs, int):
                return self.lhs
            elif self.lhs in block_types:
                return 'IsDerivedType(%s::TYPE)' % self.lhs
            else:
                return prefix + (name_filter(self.lhs) if name_filter else self.lhs)
        elif self._op == '!':
            lhs = self.lhs
            if isinstance(lhs, Expression):
                lhs = lhs.code(prefix, True, name_filter)
            elif lhs in block_types:
                lhs = 'IsDerivedType(%s::TYPE)' % lhs
            elif lhs and not lhs.isdigit() and not lhs.startswith('0x'):
                lhs = prefix + (name_filter(lhs) if name_filter else lhs)
            return '%s%s%s%s'%(lbracket, self._op, lhs, rbracket)
        else:
            lhs = self.lhs
            rhs = self.rhs
            if isinstance(lhs, Expression):
                lhs = lhs.code(prefix, True, name_filter)
            elif lhs in block_types:
                lhs = 'IsDerivedType(%s::TYPE)' % lhs
            elif lhs and not lhs.isdigit() and not lhs.startswith('0x'):
                lhs = prefix + (name_filter(lhs) if name_filter else lhs)
            if isinstance(rhs, Expression):
                rhs = rhs.code(prefix, True, name_filter)
            elif rhs in block_types:
                rhs = 'IsDerivedType(%s::TYPE)' % rhs
            elif rhs and not rhs.isdigit() and not rhs.startswith('0x'):
                rhs = prefix + (name_filter(rhs) if name_filter else rhs)
            return '%s%s %s %s%s'%(lbracket, lhs, self._op, rhs, rbracket)

    def get_terminals(self):
        """Return all terminal names (without operators or brackets)."""
        if isinstance(self.lhs, Expression):
            for terminal in self.lhs.get_terminals():
                yield terminal
        elif self.lhs:
            yield self.lhs
        if isinstance(self.rhs, Expression):
            for terminal in self.rhs.get_terminals():
                yield terminal
        elif self.rhs:
            yield self.rhs

    def __getattr__(self, name):
        if name == 'lhs':
            return getattr(self, '_left')
        if name == 'rhs':
            return getattr(self, '_right')
        if name == 'op':
            return getattr(self, '_op')
        return object.__getattribute__(self, name)

    def isdigit(self):
        """ducktyping: pretend we're also a string with isdigit() method"""
        return False

class Expr(Expression):
    """
    Represents a mathmatical expression?
    @ivar lhs: The left hand side of the expression?
    @type lhs: string
    @ivar clhs: The C++ formatted version of the left hand side of the expression?
    @type clhs: string
    @ivar op: The operator used in the expression.  ==, &&, !=, etc.
    @type op: string
    @ivar rhs: The right hand side of the expression?
    @type rhs: string
    """
    def __init__(self, n, name_filter=None):
        """
        This constructor takes the expression in the form of a string and tokenizes it into left-hand side, operator, right hand side, and something called clhs.
        @param n: The expression to tokenize.
        @type n: string
        """
        Expression.__init__(self, n, name_filter)

    def code(self, prefix='', brackets=True, name_filter=None):
        if not name_filter:
            name_filter = member_name
        return Expression.code(self, prefix, brackets, name_filter)

class Option:
    """
    This class represents an option in an option list.
    @ivar value: The C++ value of option variable.  Comes from the "value" attribute of the <option> tag.
    @type value: string
    @ivar name: The name of this member variable.  Comes from the "name" attribute of the <option> tag.
    @type name: string
    @ivar description: The description of this option.  Comes from the text between <option> and </option>.
    @type description: string
    @ivar cname: The name of this member for use in C++.
    @type cname: string
    """
    def __init__(self, element):
        """
        This constructor converts an XML <option> element into an Option object.
        """
        assert element.tagName == 'option'
        parent = element.parentNode
        #sisters = parent.getElementsByTagName('option')

        # member attributes
        self.value = element.getAttribute('value')
        self.name = element.getAttribute('name')
        if element.firstChild:
            assert element.firstChild.nodeType == Node.TEXT_NODE
            self.description = element.firstChild.nodeValue.strip()
        else:
            self.description = self.name
        self.cname = self.name.upper().replace(" ", "_").replace("-", "_").replace("/", "_").replace("=", "_").replace(":", "_")

class Member:
    """
    This class represents the nif.xml <add> tag.
    @ivar name:  The name of this member variable.  Comes from the "name" attribute of the <add> tag.
    @type name: string
    @ivar type: The type of this member variable.  Comes from the "type" attribute of the <add> tag.
    @type type: string
    @ivar arg: The argument of this member variable.  Comes from the "arg" attribute of the <add> tag.
    @type arg: string
    @ivar template: The template type of this member variable.  Comes from the "template" attribute of the <add> tag.
    @type template: string
    @ivar arr1: The first array size of this member variable.  Comes from the "arr1" attribute of the <add> tag.
    @type arr1: Eval
    @ivar arr2: The first array size of this member variable.  Comes from the "arr2" attribute of the <add> tag.
    @type arr2: Eval
    @ivar cond: The condition of this member variable.  Comes from the "cond" attribute of the <add> tag.
    @type cond: Eval
    @ivar func: The function of this member variable.  Comes from the "func" attribute of the <add> tag.
    @type func: string
    @ivar default: The default value of this member variable.  Comes from the "default" attribute of the <add> tag.
        Formatted to be ready to use in a C++ constructor initializer list.
    @type default: string
    @ivar ver1: The first version this member exists.  Comes from the "ver1" attribute of the <add> tag.
    @type ver1: string
    @ivar ver2: The last version this member exists.  Comes from the "ver2" attribute of the <add> tag.
    @type ver2: string
    @ivar userver: The user version where this member exists.  Comes from the "userver" attribute of the <add> tag.
    @type userver: string
    @ivar userver2: The user version 2 where this member exists.  Comes from the "userver2" attribute of the <add> tag.
    @type userver2: string
    @ivar vercond: The version condition of this member variable.  Comes from the "vercond" attribute of the <add> tag.
    @type vercond: Eval
    @ivar is_public: Whether this member will be declared public.  Comes from the "public" attribute of the <add> tag.
    @type is_public: string
    @ivar is_abstract: Whether this member is abstract.  This means that it does not factor into read/write.
    @type is_abstract: bool
    @ivar description: The description of this member variable.  Comes from the text between <add> and </add>.
    @type description: string
    @ivar uses_argument: Specifies whether this attribute uses an argument.
    @type uses_argument: bool
    @ivar type_is_native: Specifies whether the type is implemented natively
    @type type_is_native: bool
    @ivar is_duplicate: Specifies whether this is a duplicate of a previously declared member
    @type is_duplicate: bool
    @ivar arr2_dynamic: Specifies whether arr2 refers to an array (?)
    @type arr2_dynamic: bool
    @ivar arr1_ref: Names of the attributes it is a (unmasked) size of (?)
    @type arr1_ref: string array?
    @ivar arr2_ref: Names of the attributes it is a (unmasked) size of (?)
    @type arr2_ref: string array?
    @ivar cond_ref: Names of the attributes it is a condition of (?)
    @type cond_ref: string array?
    @ivar cname: Unlike default, name isn't formatted for C++ so use this instead?
    @type cname: string
    @ivar ctype: Unlike default, type isn't formatted for C++ so use this instead?
    @type ctype: string
    @ivar carg: Unlike default, arg isn't formatted for C++ so use this instead?
    @type carg: string
    @ivar ctemplate: Unlike default, template isn't formatted for C++ so use this instead?
    @type ctemplate: string
    @ivar carr1_ref: Unlike default, arr1_ref isn't formatted for C++ so use this instead?
    @type carr1_ref: string
    @ivar carr2_ref: Unlike default, arr2_ref isn't formatted for C++ so use this instead?
    @type carr2_ref: string
    @ivar ccond_ref: Unlike default, cond_ref isn't formatted for C++ so use this instead?
    @type ccond_ref: string
    @ivar next_dup: Next duplicate member
    @type next_dup: Member
    @ivar is_manual_update: True if the member value is manually updated by the code
    @type is_manual_update: bool
    """
    def __init__(self, element):
        """
        This constructor converts an XML <add> element into a Member object.
        Some sort of processing is applied to the various variables that are copied from the XML tag...
        Seems to be trying to set reasonable defaults for certain types, and put things into C++ format generally.
        @param prefix: An optional prefix used in some situations?
        @type prefix: string
        @return The expression formatted into a string?
        @rtype: string?
        """
        assert element.tagName == 'add'
        parent = element.parentNode
        sisters = parent.getElementsByTagName('add')

        # member attributes
        self.name      = element.getAttribute('name')
        self.suffix    = element.getAttribute('suffix')
        self.type      = element.getAttribute('type')
        self.arg       = element.getAttribute('arg')
        self.template  = element.getAttribute('template')
        self.arr1      = Expr(element.getAttribute('arr1'))
        self.arr2      = Expr(element.getAttribute('arr2'))
        self.cond      = Expr(element.getAttribute('cond'))
        self.func      = element.getAttribute('function')
        self.default   = element.getAttribute('default')
        self.orig_ver1 = element.getAttribute('ver1')
        self.orig_ver2 = element.getAttribute('ver2')
        self.ver1      = version2number(element.getAttribute('ver1'))
        self.ver2      = version2number(element.getAttribute('ver2'))
        self.userver   = userversion2number(element.getAttribute('userver'))
        self.userver2  = userversion2number(element.getAttribute('userver2'))
        self.vercond   = Expr(element.getAttribute('vercond'))
        self.is_public = (element.getAttribute('public') == "1")
        self.is_abstract = (element.getAttribute('abstract') == "1")
        self.next_dup  = None
        self.is_manual_update = False
        self.is_calculated = (element.getAttribute('calculated') == "1")

        #Get description from text between start and end tags
        if element.firstChild:
            assert element.firstChild.nodeType == Node.TEXT_NODE
            self.description = element.firstChild.nodeValue.strip()
        elif self.name.lower().find("unk") == 0:
            self.description = "Unknown."
        else:
            self.description = ""

        # Format default value so that it can be used in a C++ initializer list
        if not self.default and (not self.arr1.lhs and not self.arr2.lhs):
            if self.type in ["unsigned int", "unsigned short", "byte", "int", "short", "char"]:
                self.default = "0"
            elif self.type == "bool":
                self.default = "false"
            elif self.type in ["Ref", "Ptr"]:
                self.default = "NULL"
            elif self.type in "float":
                self.default = "0.0"
            elif self.type == "HeaderString":
                pass
            elif self.type == "Char8String":
                pass
            elif self.type == "StringOffset":
                self.default = "-1"
            elif self.type in basic_names:
                self.default = "0"
            elif self.type in flag_names or self.type in enum_names:
                self.default = "0"
        if self.default:
            if self.default[0] == '(' and self.default[-1] == ')':
                self.default = self.default[1:-1]
            if self.arr1.lhs: # handle static array types
                if self.arr1.lhs.isdigit():
                    sep = (',(%s)'%class_name(self.type))
                    self.default = self.arr1.lhs + sep + sep.join(self.default.split(' ', int(self.arr1.lhs)))
            elif self.type == "string" or self.type == "IndexString":
                self.default = "\"" + self.default + "\""
            elif self.type == "float":
                # Cast to float then back to string to add any missing ".0"
                self.default = str(float(self.default)) + "f"
            elif self.type in ["Ref", "Ptr", "bool", "Vector3"]:
                pass
            elif self.default.find(',') != -1:
                pass
            else:
                self.default = "(%s)%s"%(class_name(self.type), self.default)

        # calculate other stuff
        self.uses_argument = (self.cond.lhs == '(ARG)' or self.arr1.lhs == '(ARG)' or self.arr2.lhs == '(ARG)')
        self.type_is_native = self.name in native_types # true if the type is implemented natively

        # calculate stuff from reference to previous members
        # true if this is a duplicate of a previously declared member
        self.is_duplicate = False
        self.arr2_dynamic = False  # true if arr2 refers to an array
        sis = element.previousSibling
        while sis:
            if sis.nodeType == Node.ELEMENT_NODE:
                sis_name = sis.getAttribute('name')
                if sis_name == self.name and not self.suffix:
                    self.is_duplicate = True
                sis_arr1 = Expr(sis.getAttribute('arr1'))
                sis_arr2 = Expr(sis.getAttribute('arr2'))
                if sis_name == self.arr2.lhs and sis_arr1.lhs:
                    self.arr2_dynamic = True
            sis = sis.previousSibling

        # calculate stuff from reference to next members
        self.arr1_ref = [] # names of the attributes it is a (unmasked) size of
        self.arr2_ref = [] # names of the attributes it is a (unmasked) size of
        self.cond_ref = [] # names of the attributes it is a condition of
        sis = element.nextSibling
        while sis != None:
            if sis.nodeType == Node.ELEMENT_NODE:
                sis_name = sis.getAttribute('name')
                sis_arr1 = Expr(sis.getAttribute('arr1'))
                sis_arr2 = Expr(sis.getAttribute('arr2'))
                sis_cond = Expr(sis.getAttribute('cond'))
                if sis_arr1.lhs == self.name and (not sis_arr1.rhs or sis_arr1.rhs.isdigit()):
                    self.arr1_ref.append(sis_name)
                if sis_arr2.lhs == self.name and (not sis_arr2.rhs or sis_arr2.rhs.isdigit()):
                    self.arr2_ref.append(sis_name)
                if sis_cond.lhs == self.name:
                    self.cond_ref.append(sis_name)
            sis = sis.nextSibling

        # C++ names
        self.cname     = member_name(self.name if not self.suffix else self.name + "_" + self.suffix)
        self.ctype     = class_name(self.type)
        self.carg      = member_name(self.arg)
        self.ctemplate = class_name(self.template)
        self.carr1_ref = [member_name(n) for n in self.arr1_ref]
        self.carr2_ref = [member_name(n) for n in self.arr2_ref]
        self.ccond_ref = [member_name(n) for n in self.cond_ref]

    def code_construct(self):
        """
        Class construction
        don't construct anything that hasn't been declared
        don't construct if it has no default
        """
        if self.default and not self.is_duplicate:
            return "%s(%s)"%(self.cname, self.default)

    def code_declare(self, prefix=""):
        """
        Class member declaration
        prefix is used to tag local variables only
        """
        result = self.ctype
        suffix1 = ""
        suffix2 = ""
        keyword = ""
        if not self.is_duplicate: # is dimension for one or more arrays
            if self.arr1_ref:
                if not self.arr1 or not self.arr1.lhs: # Simple Scalar
                    keyword = "mutable "
            elif self.arr2_ref: # 1-dimensional dynamic array
                keyword = "mutable "
            elif self.is_calculated:
                keyword = "mutable "

        if self.ctemplate:
            if result != "*":
                result += "<%s >"%self.ctemplate
            else:
                result = "%s *"%self.ctemplate
        if self.arr1.lhs:
            if self.arr1.lhs.isdigit():
                if self.arr2.lhs and self.arr2.lhs.isdigit():
                    result = "array< %s, array<%s,%s > >"%(self.arr1.lhs, self.arr2.lhs, result)
                else:
                    result = "array<%s,%s >"%(self.arr1.lhs, result)
            else:
                if self.arr2.lhs and self.arr2.lhs.isdigit():
                    result = "vector< array<%s,%s > >"%(self.arr2.lhs, result)
                else:
                    if self.arr2.lhs:
                        result = "vector< vector<%s > >"%result
                    else:
                        result = "vector<%s >"%result
        result = keyword + result + " " + prefix + self.cname + suffix1 + suffix2 + ";"
        return result

    def getter_declare(self, scope="", suffix=""):
        """Getter member function declaration."""
        ltype = self.ctype
        if self.ctemplate:
            if ltype != "*":
                ltype += "<%s >"%self.ctemplate
            else:
                ltype = "%s *"%self.ctemplate
        if self.arr1.lhs:
            if self.arr1.lhs.isdigit():
                ltype = "array<%s,%s > "%(self.arr1.lhs, ltype)
                # ltype = ltype
            else:
                if self.arr2.lhs and self.arr2.lhs.isdigit():
                    ltype = "vector< array<%s,%s > >"%(self.arr2.lhs, ltype)
                else:
                    ltype = "vector<%s >"%ltype
            if self.arr2.lhs:
                if self.arr2.lhs.isdigit():
                    if self.arr1.lhs.isdigit():
                        ltype = "array<%s,%s >"%(self.arr2.lhs, ltype)
                        # ltype = ltype
                else:
                    ltype = "vector<%s >"%ltype
        result = ltype + " " + scope + "Get" + self.cname[0:1].upper() + self.cname[1:] + "() const" + suffix
        return result

    def setter_declare(self, scope="", suffix=""):
        """Setter member function declaration."""
        ltype = self.ctype
        if self.ctemplate:
            if ltype != "*":
                ltype += "<%s >"%self.ctemplate
            else:
                ltype = "%s *"%self.ctemplate
        if self.arr1.lhs:
            if self.arr1.lhs.isdigit():
                # ltype = "const %s&"%ltype
                if self.arr2.lhs and self.arr2.lhs.isdigit():
                    ltype = "const array< %s, array<%s,%s > >&"%(self.arr1.lhs, self.arr2.lhs, ltype)
                else:
                    ltype = "const array<%s,%s >& "%(self.arr1.lhs, ltype)
            else:
                if self.arr2.lhs and self.arr2.lhs.isdigit():
                    ltype = "const vector< array<%s,%s > >&"%(self.arr2.lhs, ltype)
                else:
                    ltype = "const vector<%s >&"%ltype
        else:
            if not self.type in basic_names:
                ltype = "const %s &"%ltype

        result = "void " + scope + "Set" + self.cname[0:1].upper() + self.cname[1:] + "( " + ltype + " value )" + suffix
        return result

class Version:
    """This class represents the nif.xml <version> tag."""
    def __init__(self, element):
        self.num = element.getAttribute('num')
        self.description = element.firstChild.nodeValue.strip()

class Basic:
    """This class represents the nif.xml <basic> tag."""
    def __init__(self, element):
        global native_types

        self.name = element.getAttribute('name')
        assert self.name # debug
        self.cname = class_name(self.name)
        if element.firstChild and element.firstChild.nodeType == Node.TEXT_NODE:
            self.description = element.firstChild.nodeValue.strip()
        elif self.name.lower().find("unk") == 0:
            self.description = "Unknown."
        else:
            self.description = ""

        self.count = element.getAttribute('count')

        self.is_link = False
        self.is_crossref = False
        self.has_links = False
        self.has_crossrefs = False

        self.nativetype = NATIVETYPES.get(self.name)
        if self.nativetype:
            native_types[self.name] = self.nativetype
            if self.nativetype == "Ref":
                self.is_link = True
                self.has_links = True
            if self.nativetype == "*":
                self.is_crossref = True
                self.has_crossrefs = True

        self.template = (element.getAttribute('istemplate') == "1")
        self.options = []

class Enum(Basic):
    """This class represents the nif.xml <enum> tag."""
    def __init__(self, element):
        Basic.__init__(self, element)

        self.storage = element.getAttribute('storage')
        self.prefix = element.getAttribute('prefix')
        # Find the native storage type
        self.storage = basic_types[self.storage].nativetype
        self.description = element.firstChild.nodeValue.strip()

        self.nativetype = self.cname
        native_types[self.name] = self.nativetype

        # Locate all special enumeration options
        for option in element.getElementsByTagName('option'):
            if self.prefix and option.hasAttribute('name'):
                option.setAttribute('name', self.prefix + "_" + option.getAttribute('name'))
            self.options.append(Option(option))

class Flag(Enum):
    """This class represents the nif.xml <bitflags> tag."""
    def __init__(self, element):
        Enum.__init__(self, element)
        for option in self.options:
            option.bit = option.value
            option.value = 1 << int(option.value)

class Compound(Basic):
    """This class represents the nif.xml <compound> tag."""
    def __init__(self, element):
        Basic.__init__(self, element)

        #the relative path to files in the gen folder
        self.gen_file_prefix = ""
        #the relative path to files in the obj folder
        self.obj_file_prefix = "../obj/"
        #the relative path to files in the root folder
        self.root_file_prefix = "../"

        self.members = []     # list of all members (list of Member)
        self.argument = False # does it use an argument?

        # store all attribute data & calculate stuff
        for member in element.getElementsByTagName('add'):
            x = Member(member)
            #***********************
            #** NIFLIB HACK BEGIN **
            #***********************
            if self.name == "BoundingVolume" and x.name == "Union":
                # ignore this one because niflib cannot handle
                # recursively defined structures... so we remove
                # this one to avoid the problem
                # as a result a minority of nifs won't load
                continue
            #*********************
            #** NIFLIB HACK END **
            #*********************
            self.members.append(x)

            # detect templates
            #if x.type == 'TEMPLATE':
            #    self.template = True
            #if x.template == 'TEMPLATE':
            #    self.template = True

            # detect argument
            self.argument = bool(x.uses_argument)

            # detect links & crossrefs
            mem = None
            try:
                mem = basic_types[x.type]
            except KeyError:
                try:
                    mem = compound_types[x.type]
                except KeyError:
                    pass
            if mem:
                if mem.has_links:
                    self.has_links = True
                if mem.has_crossrefs:
                    self.has_crossrefs = True

        # create duplicate chains for items that need it (only valid in current object scope)
        #  prefer to use iterators to avoid O(n^2) but I dont know how to reset iterators
        for outer in self.members:
            atx = False
            for inner in self.members:
                if atx:
                    if outer.name == inner.name: # duplicate
                        outer.next_dup = inner
                        break
                elif outer == inner:
                    atx = True

    def code_construct(self):
        # constructor
        result = ''
        first = True
        for mem in self.members:
            y_code_construct = mem.code_construct()
            if y_code_construct:
                if not first:
                    result += ', ' + y_code_construct
                else:
                    result += ' : ' + y_code_construct
                    first = False
        return result

    def code_include_h(self):
        if self.nativetype:
            return ""

        result = ""

        # include all required structures
        used_structs = []
        for mem in self.members:
            file_name = None
            if mem.type != self.name:
                if mem.type in compound_names:
                    if not compound_types[mem.type].nativetype:
                        file_name = "%s%s.h"%(self.gen_file_prefix, mem.ctype)
                elif mem.type in basic_names:
                    if basic_types[mem.type].nativetype == "Ref":
                        file_name = "%sRef.h"%(self.root_file_prefix)
            if file_name and file_name not in used_structs:
                used_structs.append( file_name )
        if used_structs:
            result += "\n// Include structures\n"
        for file_name in used_structs:
            result += '#include "%s"\n'%file_name
        return result

    def code_fwd_decl(self):
        if self.nativetype:
            return ""
        result = ""

        # forward declaration of blocks
        used_blocks = []
        for mem in self.members:
            if mem.template in block_names and mem.template != self.name:
                if not mem.ctemplate in used_blocks:
                    used_blocks.append( mem.ctemplate )
        if used_blocks:
            result += '\n// Forward define of referenced NIF objects\n'
        for fwd_class in used_blocks:
            result += 'class %s;\n'%fwd_class
        return result

    def code_include_cpp_set(self, usedirs=False, gen_dir=None, obj_dir=None):
        if self.nativetype:
            return ""

        if not usedirs:
            gen_dir = self.gen_file_prefix
            obj_dir = self.obj_file_prefix

        result = []

        if self.name in compound_names:
            result.append('#include "%s%s.h"\n'%(gen_dir, self.cname))
        elif self.name in block_names:
            result.append('#include "%s%s.h"\n'%(obj_dir, self.cname))
        else: assert False # bug

        # include referenced blocks
        used_blocks = []
        for mem in self.members:
            if mem.template in block_names and mem.template != self.name:
                file_name = '#include "%s%s.h"\n'%(obj_dir, mem.ctemplate)
                if file_name not in used_blocks:
                    used_blocks.append( file_name )
            if mem.type in compound_names:
                subblock = compound_types[mem.type]
                used_blocks.extend(subblock.code_include_cpp_set(True, gen_dir, obj_dir))
            for terminal in mem.cond.get_terminals():
                if terminal in block_types:
                    used_blocks.append('#include "%s%s.h"\n'%(obj_dir, terminal))
        for file_name in sorted(set(used_blocks)):
            result.append(file_name)

        return result

    def code_include_cpp(self, usedirs=False, gen_dir=None, obj_dir=None):
        return ''.join(self.code_include_cpp_set(True, gen_dir, obj_dir))

    def find_member(self, name, inherit=False):
        """Find member by name"""
        for mem in self.members:
            if mem.name == name:
                return mem
        return None

    def find_first_ref(self, name):
        """Find first reference of name in class."""
        for mem in self.members:
            if mem.arr1 and mem.arr1.lhs == name:
                return mem
            elif mem.arr2 and mem.arr2.lhs == name:
                return mem
        return None

    def has_arr(self):
        """Tests recursively for members with an array size."""
        for mem in self.members:
            if mem.arr1.lhs or (mem.type in compound_types and compound_types[mem.type].has_arr()):
                return True
        return False

class Block(Compound):
    """This class represents the nif.xml <niobject> tag."""
    def __init__(self, element):
        Compound.__init__(self, element)
        #the relative path to files in the gen folder
        self.gen_file_prefix = "../gen/"
        #the relative path to files in the obj folder
        self.obj_file_prefix = ""

        self.is_ancestor = (element.getAttribute('abstract') == "1")
        inherit = element.getAttribute('inherit')
        if inherit:
            self.inherit = block_types[inherit]
        else:
            self.inherit = None
        self.has_interface = (element.getElementsByTagName('interface') != [])

    def code_include_h(self):
        result = ""
        if self.inherit:
            result += '#include "%s.h"\n'%self.inherit.cname
        else:
            result += """#include "../RefObject.h"
#include "../Type.h"
#include "../Ref.h"
#include "../nif_basic_types.h"
#include <iostream>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <list>
#include <map>
#include <vector>"""
        result += Compound.code_include_h(self)
        return result

    # find member by name
    def find_member(self, name, inherit=False):
        ret = Compound.find_member(self, name)
        if not ret and inherit and self.inherit:
            ret = self.inherit.find_member(name, inherit)
        return ret

    # find first reference of name in class
    def find_first_ref(self, name):
        ret = None
        if self.inherit:
            ret = self.inherit.find_first_ref(name)
        if not ret:
            ret = Compound.find_first_ref(self, name)
        return ret

#
# import elements into our code generating classes
#

# import via "import nifxml" from .
if os.path.exists("nif.xml"):
    XML = parse("nif.xml")
# import via "import docsys" from ..
elif os.path.exists("docsys/nif.xml"):
    XML = parse("docsys/nif.xml")
# new submodule system
elif os.path.exists("nifxml/nif.xml"):
    XML = parse("nifxml/nif.xml")
else:
    raise ImportError("nif.xml not found")

for el in XML.getElementsByTagName('version'):
    x = Version(el)
    version_types[x.num] = x
    version_names.append(x.num)

for el in XML.getElementsByTagName('basic'):
    x = Basic(el)
    assert not x.name in basic_types
    basic_types[x.name] = x
    basic_names.append(x.name)

for el in XML.getElementsByTagName('enum'):
    x = Enum(el)
    assert not x.name in enum_types
    enum_types[x.name] = x
    enum_names.append(x.name)

for el in XML.getElementsByTagName('bitflags'):
    x = Flag(el)
    assert not x.name in flag_types
    flag_types[x.name] = x
    flag_names.append(x.name)

for el in XML.getElementsByTagName("compound"):
    x = Compound(el)
    assert not x.name in compound_types
    compound_types[x.name] = x
    compound_names.append(x.name)

for el in XML.getElementsByTagName("niobject"):
    x = Block(el)
    assert not x.name in block_types
    block_types[x.name] = x
    block_names.append(x.name)
