#!/usr/bin/python3

# gen_niflib.py
#
# This script generates C++ code for Niflib.
#
# --------------------------------------------------------------------------
# Command line options
#
# -p /path/to/niflib : specifies the path where niflib can be found
#
# -b : enable bootstrap mode (generates templates)
#
# -i : do NOT generate implmentation; place all code in defines.h
#
# -a : generate accessors for data in classes
#
# -n <block>: generate only files which match the specified name
#
# --------------------------------------------------------------------------
# ***** BEGIN LICENSE BLOCK *****
#
# This file is part of nifxml <https://www.github.com/niftools/nifxml>
# Copyright (c) 2017-2019 NifTools
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# This file incorporates work covered by the following copyright and permission notice:
# Copyright (c) 2005, NIF File Format Library and Tools.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#   - Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   - Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#   - Neither the name of the NIF File Format Library and Tools
#     project nor the names of its contributors may be used to endorse
#     or promote products derived from this software without specific
#     prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#
# ***** END LICENSE BLOCK *****
# --------------------------------------------------------------------------
"""
@var ACTION_READ: Constant for use with CFile::stream. Causes it to generate Niflib's Read function.
@type ACTION_READ: C{int}

@var ACTION_WRITE: Constant for use with CFile::stream.  Causes it to generate Niflib's Write function.
@type ACTION_WRITE: C{int}

@var ACTION_OUT: Constant for use with CFile::stream.  Causes it to generate Niflib's asString function.
@type ACTION_OUT: C{int}

@var ACTION_FIXLINKS: Constant for use with CFile::stream.  Causes it to generate Niflib's FixLinks function.
@type ACTION_FIXLINKS: C{int}

@var ACTION_GETREFS: Constant for use with CFile::stream.  Causes it to generate Niflib's GetRefs function.
@type ACTION_GETREFS: C{int}

@var ACTION_GETPTRS: Constant for use with CFile::stream.  Causes it to generate Niflib's GetPtrs function.
@type ACTION_GETPTRS: C{int}
"""

from textwrap import fill
from distutils.dir_util import mkpath
import sys
import os
import io
import itertools

from nifxml import Member, Compound, Block
from nifxml import TYPES_BLOCK, TYPES_BASIC, TYPES_COMPOUND, TYPES_ENUM, TYPES_FLAG, TYPES_NATIVE
from nifxml import NAMES_BLOCK, NAMES_BASIC, NAMES_COMPOUND
from nifxml import scanBrackets, define_name, parse_xml

# The relative path to the project root for compounds and NiObjects (Compound and Block)
ROOT_FILE_PREFIX = "../"

# The relative path to NiObject for compounds (Block and Compound)
CMP_OBJ_FILE_PREFIX = "../obj/"
CMP_GEN_FILE_PREFIX = ""

# The relative path to compounds for NiObject (Compound and Block)
BLK_GEN_FILE_PREFIX = "../gen/"
BLK_OBJ_FILE_PREFIX = ""

# The XML to niflib type mapping
NATIVETYPES = {
    'bool': 'bool',
    'byte': 'byte',
    'uint': 'unsigned int',
    'ulittle32': 'unsigned int',
    'ushort': 'unsigned short',
    'int': 'int',
    'short': 'short',
    'BlockTypeIndex': 'unsigned short',
    'char': 'byte',
    'FileVersion': 'unsigned int',
    'Flags': 'unsigned short',
    'float': 'float',
    'hfloat': 'hfloat',
    'HeaderString': 'HeaderString',
    'LineString': 'LineString',
    'Ptr': '*',
    'Ref': 'Ref',
    'StringOffset': 'unsigned int',
    'StringIndex': 'IndexString',
    'SizedString': 'string',
    'string': 'IndexString',
    'Color3': 'Color3',
    'Color4': 'Color4',
    # 'ByteColor3': 'ByteColor3', # TODO: Niflib type
    # 'ByteColor4': 'ByteColor4', # TODO: Niflib type
    'FilePath': 'IndexString',
    'Vector3': 'Vector3',
    'Vector4': 'Vector4',
    'Quaternion': 'Quaternion',
    'Matrix22': 'Matrix22',
    'Matrix33': 'Matrix33',
    # 'Matrix34': 'Matrix34', # TODO: Niflib type
    'Matrix44': 'Matrix44',
    'hkMatrix3': 'InertiaMatrix',
    'ShortString': 'ShortString',
    'Key': 'Key',
    'QuatKey': 'Key',
    'TexCoord': 'TexCoord',
    'Triangle': 'Triangle',
    # 'BSVertexData': 'BSVertexData',
    # 'BSVertexDataSSE': 'BSVertexData',
    # 'BSVertexDesc': 'BSVertexDesc'
}


#
# Member Patching
#

def member_code_construct(self):
    """
    Class construction
    don't construct anything that hasn't been declared
    don't construct if it has no default
    """
    if self.default and not self.is_duplicate:
        return "%s(%s)" % (self.cname, self.default)


def member_code_declare(self, prefix=""):
    """
    Class member declaration
    prefix is used to tag local variables only
    """
    result = self.ctype
    suffix1 = ""
    suffix2 = ""
    keyword = ""
    if not self.is_duplicate:  # is dimension for one or more arrays
        if self.arr1_ref:
            if not self.arr1 or not self.arr1.lhs:  # Simple Scalar
                keyword = "mutable "
        elif self.arr2_ref or self.is_calculated:  # 1-dimensional dynamic array or is calculated
            keyword = "mutable "

    if self.ctemplate:
        if result != "*":
            result += "<%s >" % self.ctemplate
        else:
            result = "%s *" % self.ctemplate
    if self.arr1.lhs:
        if self.arr1.lhs.isdigit():
            if self.arr2.lhs and self.arr2.lhs.isdigit():
                result = "Niflib::NifArray< %s, Niflib::NifArray<%s,%s > >" % (self.arr1.lhs, self.arr2.lhs, result)
            else:
                result = "Niflib::NifArray<%s,%s >" % (self.arr1.lhs, result)
        else:
            if self.arr2.lhs and self.arr2.lhs.isdigit():
                result = "vector< Niflib::NifArray<%s,%s > >" % (self.arr2.lhs, result)
            else:
                if self.arr2.lhs:
                    result = "vector< vector<%s > >" % result
                else:
                    result = "vector<%s >" % result
    result = keyword + result + " " + prefix + self.cname + suffix1 + suffix2 + ";"
    return result


def member_getter_declare(self, scope="", suffix=""):
    """Getter member function declaration."""
    ltype = self.ctype
    if self.ctemplate:
        if ltype != "*":
            ltype += "<%s >" % self.ctemplate
        else:
            ltype = "%s *" % self.ctemplate
    if self.arr1.lhs:
        if self.arr1.lhs.isdigit():
            ltype = "Niflib::NifArray<%s,%s > " % (self.arr1.lhs, ltype)
            # ltype = ltype
        else:
            if self.arr2.lhs and self.arr2.lhs.isdigit():
                ltype = "vector< Niflib::NifArray<%s,%s > >" % (self.arr2.lhs, ltype)
            else:
                ltype = "vector<%s >" % ltype
        if self.arr2.lhs:
            if self.arr2.lhs.isdigit():
                if self.arr1.lhs.isdigit():
                    ltype = "Niflib::NifArray<%s,%s >" % (self.arr2.lhs, ltype)
                    # ltype = ltype
            else:
                ltype = "vector<%s >" % ltype
    result = ltype + " " + scope + "Get" + self.cname[0:1].upper() + self.cname[1:] + "() const" + suffix
    return result


def member_setter_declare(self, scope="", suffix=""):
    """Setter member function declaration."""
    ltype = self.ctype
    if self.ctemplate:
        if ltype != "*":
            ltype += "<%s >" % self.ctemplate
        else:
            ltype = "%s *" % self.ctemplate
    if self.arr1.lhs:
        if self.arr1.lhs.isdigit():
            # ltype = "const %s&"%ltype
            if self.arr2.lhs and self.arr2.lhs.isdigit():
                ltype = "const Niflib::NifArray< %s, Niflib::NifArray<%s,%s > >&" % (
                self.arr1.lhs, self.arr2.lhs, ltype)
            else:
                ltype = "const Niflib::NifArray<%s,%s >& " % (self.arr1.lhs, ltype)
        else:
            if self.arr2.lhs and self.arr2.lhs.isdigit():
                ltype = "const vector< Niflib::NifArray<%s,%s > >&" % (self.arr2.lhs, ltype)
            else:
                ltype = "const vector<%s >&" % ltype
    else:
        if self.type not in NAMES_BASIC:
            ltype = "const %s &" % ltype

    result = "void " + scope + "Set" + self.cname[0:1].upper() + self.cname[1:] + "( " + ltype + " value )" + suffix
    return result


Member.code_construct = member_code_construct
Member.code_declare = member_code_declare
Member.getter_declare = member_getter_declare
Member.setter_declare = member_setter_declare


#
# Compound Patching
#

def compound_code_construct(self):
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


def compound_code_include_h(self):
    if self.nativetype:
        return ""

    result = ""

    # include all required structures
    used_structs = []
    for mem in self.members:
        file_name = None
        if mem.type != self.name:
            if mem.type in NAMES_COMPOUND:
                if not TYPES_COMPOUND[mem.type].nativetype:
                    file_name = "%s%s.h" % (self.gen_file_prefix, mem.ctype)
            elif mem.type in NAMES_BASIC:
                if TYPES_BASIC[mem.type].nativetype == "Ref":
                    file_name = "%sRef.h" % self.root_file_prefix
        if file_name and file_name not in used_structs:
            used_structs.append(file_name)
    if used_structs:
        result += "\n// Include structures\n"
    for file_name in used_structs:
        result += '#include "%s"\n' % file_name
    return result


def compound_code_fwd_decl(self):
    if self.nativetype:
        return ""
    result = ""

    # forward declaration of blocks
    used_blocks = []
    for mem in self.members:
        if mem.template in NAMES_BLOCK and mem.template != self.name:
            if not mem.ctemplate in used_blocks:
                used_blocks.append(mem.ctemplate)
    if used_blocks:
        result += '\n// Forward define of referenced NIF objects\n'
    for fwd_class in used_blocks:
        result += 'class %s;\n' % fwd_class
    return result


def compound_code_include_cpp_set(self, usedirs=False, gen_dir=None, obj_dir=None):
    if self.nativetype:
        return ""

    if not usedirs:
        gen_dir = self.gen_file_prefix
        obj_dir = self.obj_file_prefix

    result = []

    if self.name in NAMES_COMPOUND:
        result.append('#include "%s%s.h"\n' % (gen_dir, self.cname))
    elif self.name in NAMES_BLOCK:
        result.append('#include "%s%s.h"\n' % (obj_dir, self.cname))
    else:
        assert False  # bug

    # include referenced blocks
    used_blocks = []
    for mem in self.members:
        if mem.template in NAMES_BLOCK and mem.template != self.name:
            file_name = '#include "%s%s.h"\n' % (obj_dir, mem.ctemplate)
            if file_name not in used_blocks:
                used_blocks.append(file_name)
        if mem.type in NAMES_COMPOUND:
            subblock = TYPES_COMPOUND[mem.type]
            used_blocks.extend(subblock.code_include_cpp_set(True, gen_dir, obj_dir))
        for terminal in mem.cond.get_terminals():
            if terminal in TYPES_BLOCK:
                used_blocks.append('#include "%s%s.h"\n' % (obj_dir, terminal))
    for file_name in sorted(set(used_blocks)):
        result.append(file_name)

    return result


def compound_code_include_cpp(self, usedirs=False, gen_dir=None, obj_dir=None):
    return ''.join(self.code_include_cpp_set(True, gen_dir, obj_dir))


Compound.root_file_prefix = ROOT_FILE_PREFIX
Compound.gen_file_prefix = CMP_GEN_FILE_PREFIX
Compound.obj_file_prefix = CMP_OBJ_FILE_PREFIX
Compound.code_construct = compound_code_construct
Compound.code_include_h = compound_code_include_h
Compound.code_fwd_decl = compound_code_fwd_decl
Compound.code_include_cpp_set = compound_code_include_cpp_set
Compound.code_include_cpp = compound_code_include_cpp


#
# Block Patching
#

def block_code_include_h(self):
    result = ""
    if self.inherit:
        result += '#include "%s.h"\n' % self.inherit.cname
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


Block.gen_file_prefix = BLK_GEN_FILE_PREFIX
Block.obj_file_prefix = BLK_OBJ_FILE_PREFIX
Block.code_include_h = block_code_include_h

#
# Parse XML after patching classes
#

parse_xml(NATIVETYPES)

#
# global data
#

COPYRIGHT_YEAR = "2005-2020"

COPYRIGHT_NOTICE = r'''/* Copyright (c) {0}, NIF File Format Library and Tools
All rights reserved.  Please see niflib.h for license. */'''.format(COPYRIGHT_YEAR)

INCL_GUARD = r'''
#ifndef _{0}_H_
#define _{0}_H_
'''

# Partially generated notice
PARTGEN_NOTICE = COPYRIGHT_NOTICE + r'''

//-----------------------------------NOTICE----------------------------------//
// Some of this file is automatically filled in by a Python script.  Only    //
// add custom code in the designated areas or it will be overwritten during  //
// the next update.                                                          //
//-----------------------------------NOTICE----------------------------------//'''

# Fully generated notice
FULLGEN_NOTICE = COPYRIGHT_NOTICE + r'''

//---THIS FILE WAS AUTOMATICALLY GENERATED.  DO NOT EDIT---//

// To change this file, alter the gen_niflib.py script.'''

# NiObject standard declaration
CLASS_DECL = r'''/*! Constructor */
NIFLIB_API {0}();

/*! Destructor */
NIFLIB_API virtual ~{0}();

/*!
 * A constant value which uniquly identifies objects of this type.
 */
NIFLIB_API static const Type TYPE;

/*!
 * A factory function used during file reading to create an instance of this type of object.
 * \return A pointer to a newly allocated instance of this type of object.
 */
NIFLIB_API static NiObject * Create();

/*!
 * Summarizes the information contained in this object in English.
 * \param[in] verbose Determines whether or not detailed information about large areas of data will be printed out.
 * \return A string containing a summary of the information within the object in English.
 *  This is the function that Niflyze calls to generate its analysis, so the output is the same.
 */
NIFLIB_API virtual string asString( bool verbose = false ) const;

/*!
 * Used to determine the type of a particular instance of this object.
 * \return The type constant for the actual type of the object.
 */
NIFLIB_API virtual const Type & GetType() const;'''

# NiObject internals
CLASS_INTL = r'''/*! NIFLIB_HIDDEN function.  For internal use only. */
NIFLIB_HIDDEN virtual void Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info );
/*! NIFLIB_HIDDEN function.  For internal use only. */
NIFLIB_HIDDEN virtual void Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const;
/*! NIFLIB_HIDDEN function.  For internal use only. */
NIFLIB_HIDDEN virtual void FixLinks( const map<unsigned int,NiObjectRef> & objects, list<unsigned int> & link_stack, list<NiObjectRef> & missing_link_stack, const NifInfo & info );
/*! NIFLIB_HIDDEN function.  For internal use only. */
NIFLIB_HIDDEN virtual list<NiObjectRef> GetRefs() const;
/*! NIFLIB_HIDDEN function.  For internal use only. */
NIFLIB_HIDDEN virtual list<NiObject *> GetPtrs() const;'''

# Compound standard declaration
COMPOUND_DECL = r'''/*! Default Constructor */
NIFLIB_API {0}();
/*! Default Destructor */
NIFLIB_API ~{0}();
/*! Copy Constructor */
NIFLIB_API {0}( const {0} & src );
/*! Copy Operator */
NIFLIB_API {0} & operator=( const {0} & src );'''

# Enum stream implementation
ENUM_IMPL = r'''//--{0}--//

void NifStream( {0} & val, istream& in, const NifInfo & info ) {{
	{1} temp;
	NifStream( temp, in, info );
	val = {0}(temp);
}}

void NifStream( {0} const & val, ostream& out, const NifInfo & info ) {{
	NifStream( ({1})(val), out, info );
}}

ostream & operator<<( ostream & out, {0} const & val ) {{
	switch ( val ) {{
		{2}default: return out << "Invalid Value! - " << ({1})(val);
	}}
}}'''

# Enum stream implementation switch case
ENUM_IMPL_CASE = r'''case {0}: return out << "{1}";
		'''

# Custom Code section comments

BEG_MISC = '//--BEGIN MISC CUSTOM CODE--//'
BEG_HEAD = '//--BEGIN FILE HEAD CUSTOM CODE--//'
BEG_FOOT = '//--BEGIN FILE FOOT CUSTOM CODE--//'
BEG_PRE_READ = '//--BEGIN PRE-READ CUSTOM CODE--//'
BEG_POST_READ = '//--BEGIN POST-READ CUSTOM CODE--//'
BEG_PRE_WRITE = '//--BEGIN PRE-WRITE CUSTOM CODE--//'
BEG_POST_WRITE = '//--BEGIN POST-WRITE CUSTOM CODE--//'
BEG_PRE_STRING = '//--BEGIN PRE-STRING CUSTOM CODE--//'
BEG_POST_STRING = '//--BEGIN POST-STRING CUSTOM CODE--//'
BEG_PRE_FIXLINK = '//--BEGIN PRE-FIXLINKS CUSTOM CODE--//'
BEG_POST_FIXLINK = '//--BEGIN POST-FIXLINKS CUSTOM CODE--//'
BEG_CTOR = '//--BEGIN CONSTRUCTOR CUSTOM CODE--//'
BEG_DTOR = '//--BEGIN DESTRUCTOR CUSTOM CODE--//'
BEG_INCL = '//--BEGIN INCLUDE CUSTOM CODE--//'

END_CUSTOM = '//--END CUSTOM CODE--//'

ROOT_DIR = ".."
BOOTSTRAP = False
GENIMPL = True
GENACCESSORS = False
GENBLOCKS = []
GENALLFILES = True

prev = ""
for i in sys.argv:
    if prev == "-p":
        ROOT_DIR = i
    elif i == "-b":
        BOOTSTRAP = True
    elif i == "-i":
        GENIMPL = False
    elif i == "-a":
        GENACCESSORS = True
    elif prev == "-n":
        GENBLOCKS.append(i)
        GENALLFILES = False
    prev = i

# Fix known manual update attributes. For now hard code here.
TYPES_BLOCK["NiKeyframeData"].find_member("Num Rotation Keys").is_manual_update = True
# TYPES_BLOCK["NiTriStripsData"].find_member("Num Triangles").is_manual_update = True


ACTION_READ = 0
ACTION_WRITE = 1
ACTION_OUT = 2
ACTION_FIXLINKS = 3
ACTION_GETREFS = 4
ACTION_GETPTRS = 5


#
# C++ code formatting functions
#

class CFile(io.TextIOWrapper):
    """
    This class represents a C++ source file.  It is used to open the file for output
    and automatically handles indentation by detecting brackets and colons.
    It also handles writing the generated Niflib C++ code.
    @ivar indent: The current level of indentation.
    @type indent: int
    @ivar backslash_mode: Determines whether a backslash is appended to each line for creation of multi-line defines
    @type backslash_mode: bool
    """

    def __init__(self, buffer, encoding='utf-8', errors=None, newline=None, line_buffering=False, write_through=False):
        io.TextIOWrapper.__init__(self, buffer, encoding, errors, newline, line_buffering)
        self.indent = 0
        self.backslash_mode = False
        self.guarding = False
        self.namespaced = False

    def end(self):
        """
        Closes any namespaces and include guards and closes the file.
        """
        if self.namespaced:
            self.write('}\n')
            self.namespaced = False
        if self.guarding:
            self.code('#endif')
            self.guarding = False
        self.close()

    def code(self, txt=None):
        r"""
        Formats a line of C++ code; the returned result always ends with a newline.
        If txt starts with "E{rb}", indent is decreased, if it ends with "E{lb}", indent is increased.
        Text ending in "E{:}" de-indents itself.  For example "publicE{:}"
        Result always ends with a newline
        @param txt: None means just a line break.  This will also break the backslash, which is kind of handy.
            "\n" will create a backslashed newline in backslash mode.
        @type txt: string, None
        """
        # txt
        # this will also break the backslash, which is kind of handy
        # call code("\n") if you want a backslashed newline in backslash mode
        if txt is None:
            self.write("\n")
            return

        # block end
        if txt[:1] == "}":
            self.indent -= 1
        # special, private:, public:, and protected:
        if txt[-1:] == ":":
            self.indent -= 1
        # endline string
        if self.backslash_mode:
            endl = " \\\n"
        else:
            endl = "\n"
        # indent string
        prefix = "\t" * self.indent
        # strip trailing whitespace, including newlines
        txt = txt.rstrip()
        # indent, and add newline
        result = prefix + txt.replace("\n", endl + prefix) + endl
        # block start
        if txt[-1:] == "{":
            self.indent += 1
        # special, private:, public:, and protected:
        if txt[-1:] == ":":
            self.indent += 1

        self.write(result.encode('utf-8').decode('utf-8', 'strict'))

    def guard(self, txt):
        """
        Begins an include guard scope for the file
        @param txt: The unique identifier for the header.
        @type txt: str
        """
        if self.guarding:
            return
        self.guarding = True
        self.code(INCL_GUARD.format(txt))

    def namespace(self, txt):
        """
        Begins a namespace scope for the file
        @param txt: The namespace.
        @type txt: str
        """
        if self.namespaced:
            return
        self.namespaced = True
        self.write(f'namespace {txt} {{\n')

    def include(self, txt):
        """
        Includes a file
        @param txt: The include filepath.
        @type txt: str
        """
        if (txt.startswith('<') and txt.endswith('>')) or (txt.startswith('"') and txt.endswith('"')):
            self.write(f'#include {txt}\n')
        else:
            self.write(f'#include "{txt}"\n')

    def comment(self, txt, doxygen):
        """
        Wraps text in C++ comments and outputs it to the file.  Handles multilined comments as well.
        Result always ends with a newline
        @param txt: The text to enclose in a Doxygen comment
        @type txt: string
        @param doxygen: Indicates if writes comment as doxygen style comment
        @type doxygen: bool
        """

        # skip comments when we are in backslash mode
        if self.backslash_mode:
            return

        lines = txt.split('\n')

        txt = ""
        for com in lines:
            txt = txt + fill(com, 80) + "\n"

        txt = txt.strip()
        if not txt:
            return

        num_line_ends = txt.count('\n')

        if doxygen:
            if num_line_ends > 0:
                txt = txt.replace("\n", "\n * ")
                self.code("/*!\n * " + txt + "\n */")
            else:
                self.code("/*! " + txt + " */")
        else:
            lines = txt.split('\n')
            for com in lines:
                self.code("// " + com)

    def declare(self, block):
        """
        Formats the member variables for a specific class as described by the XML and outputs the result to the file.
        @param block: The class or struct to generate member functions for.
        @type block: Block, Compound
        """
        if isinstance(block, Block):
            # self.code('protected:')
            prot_mode = True
        for mem in block.members:
            if not mem.is_duplicate:
                if isinstance(block, Block):
                    if mem.is_public and prot_mode:
                        self.code('public:')
                        prot_mode = False
                    elif not mem.is_public and not prot_mode:
                        self.code('protected:')
                        prot_mode = True
                self.comment(mem.description, True)
                self.code(mem.code_declare())
                if mem.func:
                    self.comment(mem.description)
                    self.code("%s %s() const;" % (mem.ctype, mem.func))

    def stream(self, block, action, localprefix="", prefix="", arg_prefix="", arg_member=None):
        """
        Generates the function code for various functions in Niflib and outputs it to the file.
        @param block: The class or struct to generate the function for.
        @type block: Block, Compound
        @param action: The type of function to generate, valid values are::
            ACTION_READ - Read function.
            ACTION_WRITE - Write function
            ACTION_OUT - asString function
            ACTION_FIXLINKS - FixLinks function
            ACTION_GETREFS - GetRefs function
            ACTION_GETPTRS - GetPtrs function
        @type action: ACTION_X constant
        @param localprefix: ?
        @type localprefix: string
        @param prefix: ?
        @type prefix: string
        @param arg_prefix: ?
        @type arg_prefix: string
        @param arg_member: ?
        @type arg_member: None, ?
        """
        lastver1 = None
        lastver2 = None
        lastuserver = None
        lastuserver2 = None
        lastcond = None
        lastvercond = None
        # stream name
        if action == ACTION_READ:
            stream = "in"
        else:
            stream = "out"

        # preparation
        if isinstance(block, Block) or block.name in ["Footer", "Header"]:
            if action == ACTION_READ:
                if block.has_links or block.has_crossrefs:
                    self.code("unsigned int block_num;")
            if action == ACTION_OUT:
                self.code("stringstream out;")
                # declare array_output_count, only if it will actually be used
                if block.has_arr():
                    self.code("unsigned int array_output_count = 0;")

            if action == ACTION_GETREFS:
                self.code("list<Ref<NiObject> > refs;")
            if action == ACTION_GETPTRS:
                self.code("list<NiObject *> ptrs;")

        # stream the ancestor
        if isinstance(block, Block):
            if block.inherit:
                if action == ACTION_READ:
                    self.code("%s::Read( %s, link_stack, info );" % (block.inherit.cname, stream))
                elif action == ACTION_WRITE:
                    self.code("%s::Write( %s, link_map, missing_link_stack, info );" % (block.inherit.cname, stream))
                elif action == ACTION_OUT:
                    self.code("%s << %s::asString();" % (stream, block.inherit.cname))
                elif action == ACTION_FIXLINKS:
                    self.code("%s::FixLinks( objects, link_stack, missing_link_stack, info );" % block.inherit.cname)
                elif action == ACTION_GETREFS:
                    self.code("refs = %s::GetRefs();" % block.inherit.cname)
                elif action == ACTION_GETPTRS:
                    self.code("ptrs = %s::GetPtrs();" % block.inherit.cname)

        # declare and calculate local variables (TODO: GET RID OF THIS; PREFERABLY NO LOCAL VARIABLES AT ALL)
        if action in [ACTION_READ, ACTION_WRITE, ACTION_OUT]:
            block.members.reverse()  # calculated data depends on data further down the structure
            for y in block.members:
                if not y.is_duplicate and not y.is_manual_update and action in [ACTION_WRITE, ACTION_OUT]:
                    if y.func:
                        self.code('%s%s = %s%s();' % (prefix, y.cname, prefix, y.func))
                    elif y.is_calculated:
                        if action in [ACTION_READ, ACTION_WRITE]:
                            self.code('%s%s = %s%sCalc(info);' % (prefix, y.cname, prefix, y.cname))
                        # ACTION_OUT is in asString(), which doesn't take version info
                        # so let's simply not print the field in this case
                    elif y.arr1_ref:
                        if not y.arr1 or not y.arr1.lhs:  # Simple Scalar
                            cref = block.find_member(y.arr1_ref[0], True)
                            # if not cref.is_duplicate and not cref.next_dup and (not cref.cond.lhs or cref.cond.lhs == y.name):
                            # self.code('assert(%s%s == (%s)(%s%s.size()));'%(prefix, y.cname, y.ctype, prefix, cref.cname))
                            self.code('%s%s = (%s)(%s%s.size());' % (prefix, y.cname, y.ctype, prefix, cref.cname))
                    elif y.arr2_ref:  # 1-dimensional dynamic array
                        cref = block.find_member(y.arr2_ref[0], True)
                        if not y.arr1 or not y.arr1.lhs:  # Second dimension
                            # if not cref.is_duplicate and not cref.next_dup (not cref.cond.lhs or cref.cond.lhs == y.name):
                            # self.code('assert(%s%s == (%s)((%s%s.size() > 0) ? %s%s[0].size() : 0));'\
                            # %(prefix, y.cname, y.ctype, prefix, cref.cname, prefix, cref.cname))
                            self.code('%s%s = (%s)((%s%s.size() > 0) ? %s%s[0].size() : 0);' \
                                      % (prefix, y.cname, y.ctype, prefix, cref.cname, prefix, cref.cname))
                        else:
                            # index of dynamically sized array
                            self.code('for (unsigned int i%i = 0; i%i < %s%s.size(); i%i++)' \
                                      % (self.indent, self.indent, prefix, cref.cname, self.indent))
                            self.code('\t%s%s[i%i] = (%s)(%s%s[i%i].size());' \
                                      % (prefix, y.cname, self.indent, y.ctype, prefix, cref.cname, self.indent))
                    # else: #has duplicates needs to be selective based on version
                    # self.code('assert(!"%s");'%(y.name))
            block.members.reverse()  # undo reverse

        # now comes the difficult part: processing all members recursively
        for y in block.members:
            # get block
            if y.type in TYPES_BASIC:
                subblock = TYPES_BASIC[y.type]
            elif y.type in TYPES_COMPOUND:
                subblock = TYPES_COMPOUND[y.type]
            elif y.type in TYPES_ENUM:
                subblock = TYPES_ENUM[y.type]
            elif y.type in TYPES_FLAG:
                subblock = TYPES_FLAG[y.type]

            # check for links
            if action in [ACTION_FIXLINKS, ACTION_GETREFS, ACTION_GETPTRS]:
                if not subblock.has_links and not subblock.has_crossrefs:
                    continue  # contains no links, so skip this member!
            if action == ACTION_OUT:
                if y.is_duplicate:
                    continue  # don't write variables twice
            # resolve array & cond references
            y_arr1_lmember = None
            y_arr2_lmember = None
            y_cond_lmember = None
            y_arg = None
            y_arr1_prefix = ""
            y_arr2_prefix = ""
            y_cond_prefix = ""
            y_arg_prefix = ""
            if y.arr1.lhs or y.arr2.lhs or y.cond.lhs or y.arg:
                for z in block.members:
                    if not y_arr1_lmember and y.arr1.lhs == z.name:
                        y_arr1_lmember = z
                    if not y_arr2_lmember and y.arr2.lhs == z.name:
                        y_arr2_lmember = z
                    if not y_cond_lmember:
                        if y.cond.lhs == z.name:
                            y_cond_lmember = z
                        elif y.cond.op == '&&' and y.cond.lhs == z.name:
                            y_cond_lmember = z
                        elif y.cond.op == '||' and y.cond.lhs == z.name:
                            y_cond_lmember = z
                    if not y_arg and y.arg == z.name:
                        y_arg = z
                if y_arr1_lmember:
                    y_arr1_prefix = prefix
                if y_arr2_lmember:
                    y_arr2_prefix = prefix
                if y_cond_lmember:
                    y_cond_prefix = prefix
                if y_arg:
                    y_arg_prefix = prefix
            # resolve this prefix
            y_prefix = prefix
            # resolve arguments
            if y.arr1 and y.arr1.lhs == 'ARG':
                y.arr1.lhs = arg_member.name
                y.arr1.clhs = arg_member.cname
                y_arr1_prefix = arg_prefix
            if y.arr2 and y.arr2.lhs == 'ARG':
                y.arr2.lhs = arg_member.name
                y.arr2.clhs = arg_member.cname
                y_arr2_prefix = arg_prefix
            if y.cond and y.cond.lhs == 'ARG':
                y.cond.lhs = arg_member.name
                y.cond.clhs = arg_member.cname
                y_cond_prefix = arg_prefix
            # conditioning
            y_cond = y.cond.code(y_cond_prefix)
            y_vercond = y.vercond.code('info.')
            if action in [ACTION_READ, ACTION_WRITE, ACTION_FIXLINKS]:
                if lastver1 != y.ver1 or lastver2 != y.ver2 or lastuserver != y.userver or lastuserver2 != y.userver2 or lastvercond != y_vercond:
                    # we must switch to a new version block
                    # close old version block
                    if lastver1 or lastver2 or lastuserver or lastuserver2 or lastvercond:
                        self.code("};")
                    # close old condition block as well
                    if lastcond:
                        self.code("};")
                        lastcond = None
                    # start new version block
                    concat = ''
                    verexpr = ''
                    if y.ver1:
                        verexpr = "( info.version >= 0x%08X )" % y.ver1
                        concat = " && "
                    if y.ver2:
                        verexpr = "%s%s( info.version <= 0x%08X )" % (verexpr, concat, y.ver2)
                        concat = " && "
                    if y.userver is not None:
                        verexpr = "%s%s( info.userVersion == %s )" % (verexpr, concat, y.userver)
                        concat = " && "
                    if y.userver2 is not None:
                        verexpr = "%s%s( info.userVersion2 == %s )" % (verexpr, concat, y.userver2)
                        concat = " && "
                    if y_vercond:
                        verexpr = "%s%s( %s )" % (verexpr, concat, y_vercond)
                    if verexpr:
                        # remove outer redundant parenthesis
                        bleft, bright = scanBrackets(verexpr)
                        if bleft == 0 and bright == (len(verexpr) - 1):
                            self.code("if %s {" % verexpr)
                        else:
                            self.code("if ( %s ) {" % verexpr)
                    # start new condition block
                    if lastcond != y_cond and y_cond:
                        self.code("if ( %s ) {" % y_cond)
                else:
                    # we remain in the same version block
                    # check condition block
                    if lastcond != y_cond:
                        if lastcond:
                            self.code("};")
                        if y_cond:
                            self.code("if ( %s ) {" % y_cond)
            elif action == ACTION_OUT:
                # check condition block
                if lastcond != y_cond:
                    if lastcond:
                        self.code("};")
                    if y_cond:
                        self.code("if ( %s ) {" % y_cond)
            # loop over arrays
            # and resolve variable name
            if not y.arr1.lhs:
                z = "%s%s" % (y_prefix, y.cname)
            else:
                if action == ACTION_OUT:
                    self.code("array_output_count = 0;")
                if not y.arr1.lhs.isdigit():
                    if action == ACTION_READ:
                        # default to local variable, check if variable is in current scope if not then try to use
                        #   definition from resized child
                        memcode = "%s%s.resize(%s);" % (y_prefix, y.cname, y.arr1.code(y_arr1_prefix))
                        mem = block.find_member(y.arr1.lhs, True)  # find member in self or parents
                        self.code(memcode)
                    self.code( \
                        "for (unsigned int i%i = 0; i%i < %s%s.size(); i%i++) {" \
                        % (self.indent, self.indent, y_prefix, y.cname, self.indent))
                else:
                    self.code( \
                        "for (unsigned int i%i = 0; i%i < %s; i%i++) {" \
                        % (self.indent, self.indent, y.arr1.code(y_arr1_prefix), self.indent))
                if action == ACTION_OUT:
                    self.code('if ( !verbose && ( array_output_count > MAXARRAYDUMP ) ) {')
                    self.code('%s << "<Data Truncated. Use verbose mode to see complete listing.>" << endl;' % stream)
                    self.code('break;')
                    self.code('};')
                if not y.arr2.lhs:
                    z = "%s%s[i%i]" % (y_prefix, y.cname, self.indent - 1)
                else:
                    if not y.arr2_dynamic:
                        if not y.arr2.lhs.isdigit():
                            if action == ACTION_READ:
                                self.code("%s%s[i%i].resize(%s);" % (
                                y_prefix, y.cname, self.indent - 1, y.arr2.code(y_arr2_prefix)))
                            self.code( \
                                "for (unsigned int i%i = 0; i%i < %s%s[i%i].size(); i%i++) {" \
                                % (self.indent, self.indent, y_prefix, y.cname, self.indent - 1, self.indent))
                        else:
                            self.code( \
                                "for (unsigned int i%i = 0; i%i < %s; i%i++) {" \
                                % (self.indent, self.indent, y.arr2.code(y_arr2_prefix), self.indent))
                    else:
                        if action == ACTION_READ:
                            self.code("%s%s[i%i].resize(%s[i%i]);" \
                                      % (
                                      y_prefix, y.cname, self.indent - 1, y.arr2.code(y_arr2_prefix), self.indent - 1))
                        self.code( \
                            "for (unsigned int i%i = 0; i%i < %s[i%i]; i%i++) {" \
                            % (self.indent, self.indent, y.arr2.code(y_arr2_prefix), self.indent - 1, self.indent))
                    z = "%s%s[i%i][i%i]" % (y_prefix, y.cname, self.indent - 2, self.indent - 1)

            if y.type in TYPES_NATIVE:
                # these actions distinguish between refs and non-refs
                if action in [ACTION_READ, ACTION_WRITE, ACTION_FIXLINKS, ACTION_GETREFS, ACTION_GETPTRS]:
                    if (not subblock.is_link) and (not subblock.is_crossref):
                        # not a ref
                        if action in [ACTION_READ, ACTION_WRITE] and y.is_abstract is False:
                            # hack required for vector<bool>
                            if y.type == "bool" and y.arr1.lhs:
                                self.code("{")
                                if action == ACTION_READ:
                                    self.code("bool tmp;")
                                    self.code("NifStream( tmp, %s, info );" % (stream))
                                    self.code("%s = tmp;" % z)
                                else:  # ACTION_WRITE
                                    self.code("bool tmp = %s;" % z)
                                    self.code("NifStream( tmp, %s, info );" % (stream))
                                self.code("};")
                            # the usual thing
                            elif not y.arg:
                                cast = ""
                                if y.is_duplicate:
                                    cast = "(%s&)" % y.ctype
                                self.code("NifStream( %s%s, %s, info );" % (cast, z, stream))
                            else:
                                self.code("NifStream( %s, %s, info, %s%s );" % (z, stream, y_prefix, y.carg))
                    else:
                        # a ref
                        if action == ACTION_READ:
                            self.code("NifStream( block_num, %s, info );" % stream)
                            self.code("link_stack.push_back( block_num );")
                        elif action == ACTION_WRITE:
                            self.code(
                                "WriteRef( StaticCast<NiObject>(%s), %s, info, link_map, missing_link_stack );" % (
                                z, stream))
                        elif action == ACTION_FIXLINKS:
                            self.code(
                                "%s = FixLink<%s>( objects, link_stack, missing_link_stack, info );" % (z, y.ctemplate))
                        elif action == ACTION_GETREFS and subblock.is_link:
                            if not y.is_duplicate:
                                self.code('if ( %s != NULL )\n\trefs.push_back(StaticCast<NiObject>(%s));' % (z, z))
                        elif action == ACTION_GETPTRS and subblock.is_crossref:
                            if not y.is_duplicate:
                                self.code('if ( %s != NULL )\n\tptrs.push_back((NiObject *)(%s));' % (z, z))
                # the following actions don't distinguish between refs and non-refs
                elif action == ACTION_OUT:
                    if not y.arr1.lhs:
                        self.code('%s << "%*s%s:  " << %s << endl;' % (stream, 2 * self.indent, "", y.name, z))
                    else:
                        self.code('if ( !verbose && ( array_output_count > MAXARRAYDUMP ) ) {')
                        self.code('break;')
                        self.code('};')
                        self.code('%s << "%*s%s[" << i%i << "]:  " << %s << endl;' % (
                        stream, 2 * self.indent, "", y.name, self.indent - 1, z))
                        self.code('array_output_count++;')
            else:
                subblock = TYPES_COMPOUND[y.type]
                if not y.arr1.lhs:
                    self.stream(subblock, action, "%s%s_" % (localprefix, y.cname), "%s." % z, y_arg_prefix, y_arg)
                elif not y.arr2.lhs:
                    self.stream(subblock, action, "%s%s_" % (localprefix, y.cname), "%s." % z, y_arg_prefix, y_arg)
                else:
                    self.stream(subblock, action, "%s%s_" % (localprefix, y.cname), "%s." % z, y_arg_prefix, y_arg)

            # close array loops
            if y.arr1.lhs:
                self.code("};")
                if y.arr2.lhs:
                    self.code("};")

            lastver1 = y.ver1
            lastver2 = y.ver2
            lastuserver = y.userver
            lastuserver2 = y.userver2
            lastcond = y_cond
            lastvercond = y_vercond

        if action in [ACTION_READ, ACTION_WRITE, ACTION_FIXLINKS]:
            if lastver1 or lastver2 or not (lastuserver is None) or not (lastuserver2 is None) or lastvercond:
                self.code("};")
        if action in [ACTION_READ, ACTION_WRITE, ACTION_FIXLINKS, ACTION_OUT]:
            if lastcond:
                self.code("};")

        # the end
        if isinstance(block, Block) or block.name in ["Header", "Footer"]:
            if action == ACTION_OUT:
                self.code("return out.str();")
            if action == ACTION_GETREFS:
                self.code("return refs;")
            if action == ACTION_GETPTRS:
                self.code("return ptrs;")

    def getset_declare(self, block, prefix=""):
        """
        Declare getter and setter
        prefix is used to tag local variables only
        """
        for y in block.members:
            if not y.func:
                if y.cname.lower().find("unk") == -1:
                    self.code(y.getter_declare("", ";"))
                    self.code(y.setter_declare("", ";"))
                    self.code()


#
# Function to extract custom code from existing file
#
def extract_custom_code(name):
    custom = {'MISC': [], 'FILE HEAD': [], 'FILE FOOT': [], 'PRE-READ': [], 'POST-READ': [], 'PRE-WRITE': [],
              'POST-WRITE': [], 'PRE-STRING': [], 'POST-STRING': [], 'PRE-FIXLINKS': [], 'POST-FIXLINKS': [],
              'CONSTRUCTOR': [], 'DESTRUCTOR': []}

    if os.path.isfile(name) is False:
        custom['MISC'].append('\n')
        custom['FILE HEAD'].append('\n')
        custom['FILE FOOT'].append('\n')
        custom['PRE-READ'].append('\n')
        custom['POST-READ'].append('\n')
        custom['PRE-WRITE'].append('\n')
        custom['POST-WRITE'].append('\n')
        custom['PRE-STRING'].append('\n')
        custom['POST-STRING'].append('\n')
        custom['PRE-FIXLINKS'].append('\n')
        custom['POST-FIXLINKS'].append('\n')
        custom['CONSTRUCTOR'].append('\n')
        custom['DESTRUCTOR'].append('\n')
        return custom

    f = open(name, 'rt', 1, 'utf-8')
    lines = f.readlines()
    f.close()

    custom_flag = False
    custom_name = ""

    for cln in lines:
        if custom_flag is True:
            if cln.find(END_CUSTOM) != -1:
                custom_flag = False
            else:
                if not custom[custom_name]:
                    custom[custom_name] = [cln]
                else:
                    custom[custom_name].append(cln)
        if cln.find(BEG_MISC) != -1:
            custom_flag = True
            custom_name = 'MISC'
        elif cln.find(BEG_HEAD) != -1:
            custom_flag = True
            custom_name = 'FILE HEAD'
        elif cln.find(BEG_FOOT) != -1:
            custom_flag = True
            custom_name = 'FILE FOOT'
        elif cln.find(BEG_PRE_READ) != -1:
            custom_flag = True
            custom_name = 'PRE-READ'
        elif cln.find(BEG_POST_READ) != -1:
            custom_flag = True
            custom_name = 'POST-READ'
        elif cln.find(BEG_PRE_WRITE) != -1:
            custom_flag = True
            custom_name = 'PRE-WRITE'
        elif cln.find(BEG_POST_WRITE) != -1:
            custom_flag = True
            custom_name = 'POST-WRITE'
        elif cln.find(BEG_PRE_STRING) != -1:
            custom_flag = True
            custom_name = 'PRE-STRING'
        elif cln.find(BEG_POST_STRING) != -1:
            custom_flag = True
            custom_name = 'POST-STRING'
        elif cln.find(BEG_PRE_FIXLINK) != -1:
            custom_flag = True
            custom_name = 'PRE-FIXLINKS'
        elif cln.find(BEG_POST_FIXLINK) != -1:
            custom_flag = True
            custom_name = 'POST-FIXLINKS'
        elif cln.find(BEG_CTOR) != -1:
            custom_flag = True
            custom_name = 'CONSTRUCTOR'
        elif cln.find(BEG_DTOR) != -1:
            custom_flag = True
            custom_name = 'DESTRUCTOR'
        elif cln.find(BEG_INCL) != -1:
            custom_flag = True
            custom_name = 'INCLUDE'
    return custom


#
# Function to compare two files
#

def overwrite_if_changed(original_file, candidate_file):
    files_differ = False

    if os.path.isfile(original_file):
        file1 = open(original_file, 'r')
        file2 = open(candidate_file, 'r')

        str1 = file1.read()
        str2 = file2.read()

        file1.close()
        file2.close()

        if str1 != str2:
            files_differ = True
            # remove original file
            os.unlink(original_file)
    else:
        files_differ = True

    if files_differ:
        # Files differ, so overwrite original with candidate
        os.rename(candidate_file, original_file)


#
# generate compound code
#

mkpath(os.path.join(ROOT_DIR, "include/obj"))
mkpath(os.path.join(ROOT_DIR, "include/gen"))

mkpath(os.path.join(ROOT_DIR, "src/obj"))
mkpath(os.path.join(ROOT_DIR, "src/gen"))

for n in NAMES_COMPOUND:
    x = TYPES_COMPOUND[n]
    # skip natively implemented types
    if x.name in list(NATIVETYPES.keys()):
        continue
    if not GENALLFILES and not x.cname in GENBLOCKS:
        continue

    # Get existing custom code
    file_name = ROOT_DIR + '/include/gen/' + x.cname + '.h'
    custom_lines = extract_custom_code(file_name)

    HDR = CFile(io.open(file_name, 'wb'))
    print("Generating " + file_name)
    HDR.code(FULLGEN_NOTICE)
    HDR.guard(x.cname.upper())
    HDR.code()
    HDR.include('../NIF_IO.h')
    if n in ["Header", "Footer"]:
        HDR.include('../obj/NiObject.h')
    HDR.code(x.code_include_h())
    HDR.namespace('Niflib')
    HDR.code(x.code_fwd_decl())
    HDR.code()
    # header
    HDR.comment(x.description, True)
    hdr = "struct %s" % x.cname
    if x.template:
        hdr = "template <class T >\n%s" % hdr
    hdr += " {"
    HDR.code(hdr)

    # constructor/destructor/assignment
    if not x.template:
        HDR.code(COMPOUND_DECL.format(x.cname))

    # declaration
    HDR.declare(x)

    # header and footer functions
    if n == "Header":
        HDR.code('NIFLIB_HIDDEN NifInfo Read( istream& in );')
        HDR.code('NIFLIB_HIDDEN void Write( ostream& out, const NifInfo & info = NifInfo() ) const;')
        HDR.code('NIFLIB_HIDDEN string asString( bool verbose = false ) const;')

    if n == "Footer":
        HDR.code('NIFLIB_HIDDEN void Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info );')
        HDR.code(
            'NIFLIB_HIDDEN void Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const;')
        HDR.code('NIFLIB_HIDDEN string asString( bool verbose = false ) const;')

    HDR.code(BEG_MISC)

    # Preserve Custom code from before
    for line in custom_lines['MISC']:
        HDR.write(line)

    HDR.code(END_CUSTOM)

    # done
    HDR.code("};")
    HDR.code()
    HDR.end()

    if not x.template:
        # Get existing custom code
        file_name = ROOT_DIR + '/src/gen/' + x.cname + '.cpp'
        custom_lines = extract_custom_code(file_name)

        CPP = CFile(io.open(file_name, 'wb'))
        print("Generating " + file_name)
        CPP.code(PARTGEN_NOTICE)
        CPP.code()
        CPP.code(x.code_include_cpp(True, "../../include/gen/", "../../include/obj/"))
        CPP.code("using namespace Niflib;")
        CPP.code()
        CPP.code('//Constructor')

        # constructor
        x_code_construct = x.code_construct()
        # if x_code_construct:
        CPP.code("%s::%s()" % (x.cname, x.cname) + x_code_construct + " {};")
        CPP.code()

        CPP.code('//Copy Constructor')
        CPP.code('%s::%s( const %s & src ) {' % (x.cname, x.cname, x.cname))
        CPP.code('*this = src;')
        CPP.code('};')
        CPP.code()

        CPP.code('//Copy Operator')
        CPP.code('%s & %s::operator=( const %s & src ) {' % (x.cname, x.cname, x.cname))
        for m in x.members:
            if not m.is_duplicate:
                CPP.code('this->%s = src.%s;' % (m.cname, m.cname))
        CPP.code('return *this;')
        CPP.code('};')
        CPP.code()

        CPP.code('//Destructor')

        # destructor
        CPP.code("%s::~%s()" % (x.cname, x.cname) + " {};")

        # header and footer functions
        if n == "Header":
            CPP.code('NifInfo ' + x.cname + '::Read( istream& in ) {')
            CPP.code('//Declare NifInfo structure')
            CPP.code('NifInfo info;')
            CPP.code()
            CPP.stream(x, ACTION_READ)
            CPP.code()
            CPP.code('//Copy info.version to local version var.')
            CPP.code('version = info.version;')
            CPP.code()
            CPP.code('//Fill out and return NifInfo structure.')
            CPP.code('info.userVersion = userVersion;')
            CPP.code('info.userVersion2 = userVersion2;')
            CPP.code('info.endian = EndianType(endianType);')
            CPP.code('info.author = exportInfo.author;')
            CPP.code('info.exportScript = exportInfo.exportScript;')
            CPP.code('info.processScript = exportInfo.processScript;')
            CPP.code()
            CPP.code('return info;')
            CPP.code()
            CPP.code('}')
            CPP.code()
            CPP.code('void ' + x.cname + '::Write( ostream& out, const NifInfo & info ) const {')
            CPP.stream(x, ACTION_WRITE)
            CPP.code('}')
            CPP.code()
            CPP.code('string ' + x.cname + '::asString( bool verbose ) const {')
            CPP.stream(x, ACTION_OUT)
            CPP.code('}')

        if n == "Footer":
            CPP.code()
            CPP.code(
                'void ' + x.cname + '::Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info ) {')
            CPP.stream(x, ACTION_READ)
            CPP.code('}')
            CPP.code()
            CPP.code(
                'void ' + x.cname + '::Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const {')
            CPP.stream(x, ACTION_WRITE)
            CPP.code('}')
            CPP.code()
            CPP.code('string ' + x.cname + '::asString( bool verbose ) const {')
            CPP.stream(x, ACTION_OUT)
            CPP.code('}')

        CPP.code()
        CPP.code(BEG_MISC)

        # Preserve Custom code from before
        for line in custom_lines['MISC']:
            CPP.write(line)

        CPP.code(END_CUSTOM)

        CPP.end()

    # Write out Public Enumeration header Enumerations
if GENALLFILES:
    HDR = CFile(open(ROOT_DIR + '/include/gen/enums.h', 'wb'))
    HDR.code(FULLGEN_NOTICE)
    HDR.guard('NIF_ENUMS')
    HDR.code()
    HDR.include('<iostream>')
    HDR.code('using namespace std;')
    HDR.code()
    HDR.namespace('Niflib')
    HDR.code()
    for n, x in itertools.chain(list(TYPES_ENUM.items()), list(TYPES_FLAG.items())):
        if x.options:
            if x.description:
                HDR.comment(x.description, True)
            HDR.code('enum class %s {' % (x.cname))
            for o in x.options:
                HDR.code('%s = %s, /*!< %s */' % (o.cname, o.value, o.description))
            HDR.code('};')
            HDR.code()
            HDR.code('ostream & operator<<( ostream & out, %s const & val );' % x.cname)
            HDR.code()
    HDR.end()

    # Write out Internal Enumeration header (NifStream functions)
if GENALLFILES:
    HDR = CFile(open(ROOT_DIR + '/include/gen/enums_intl.h', 'wb'))
    HDR.code(FULLGEN_NOTICE)
    HDR.guard('NIF_ENUMS_INTL')
    HDR.code()
    HDR.include('<iostream>')
    HDR.code('using namespace std;')
    HDR.code()
    HDR.include('../nif_basic_types.h')
    HDR.code()
    HDR.namespace('Niflib')
    HDR.code()
    for n, x in itertools.chain(list(TYPES_ENUM.items()), list(TYPES_FLAG.items())):
        if x.options:
            if x.description:
                HDR.code()
                HDR.code('//---' + x.cname + '---//')
                HDR.code()
            HDR.code('void NifStream( %s & val, istream& in, const NifInfo & info = NifInfo() );' % x.cname)
            HDR.code('void NifStream( %s const & val, ostream& out, const NifInfo & info = NifInfo() );' % x.cname)
            HDR.code()
    HDR.end()

    # Write out Enumeration Implementation
if GENALLFILES:
    CPP = CFile(open(ROOT_DIR + '/src/gen/enums.cpp', 'wb'))
    CPP.code(FULLGEN_NOTICE)
    CPP.code()
    CPP.include('<string>')
    CPP.include('<iostream>')
    CPP.include('../../include/NIF_IO.h')
    CPP.include('../../include/gen/enums.h')
    CPP.include('../../include/gen/enums_intl.h')
    CPP.code()
    CPP.code('using namespace std;')
    CPP.code()
    CPP.namespace('Niflib')
    CPP.code()
    CPP.code()
    for n, x in itertools.chain(list(TYPES_ENUM.items()), list(TYPES_FLAG.items())):
        if x.options:
            CPP.code(ENUM_IMPL.format(x.cname, x.storage,
                                      r''.join(ENUM_IMPL_CASE.format(o.cname, o.name) for o in x.options)))
            CPP.code()
    CPP.end()

    #
    # NiObject Registration Function
    #
    CPP = CFile(open(ROOT_DIR + '/src/gen/register.cpp', 'wb'))
    CPP.code(FULLGEN_NOTICE)
    CPP.code()
    CPP.include('../../include/ObjectRegistry.h')
    for n in NAMES_BLOCK:
        x = TYPES_BLOCK[n]
        CPP.include('../../include/obj/' + x.cname + '.h')
    CPP.code()
    CPP.namespace('Niflib')
    CPP.code('void RegisterObjects() {')
    CPP.code()
    for n in NAMES_BLOCK:
        x = TYPES_BLOCK[n]
        CPP.code('ObjectRegistry::RegisterObject( "' + x.name + '", ' + x.cname + '::Create );')
    CPP.code()
    CPP.code('}')
    CPP.end()

#
# NiObject Files
#
for n in NAMES_BLOCK:
    x = TYPES_BLOCK[n]
    x_define_name = define_name(x.cname)

    if not GENALLFILES and not x.cname in GENBLOCKS:
        continue

    #
    # NiObject Header File
    #

    # Get existing custom code
    file_name = ROOT_DIR + '/include/obj/' + x.cname + '.h'
    custom_lines = extract_custom_code(file_name)

    # output new file
    HDR = CFile(io.open(file_name, 'wb'))
    print("Generating " + file_name)
    HDR.code(PARTGEN_NOTICE)
    HDR.guard(x.cname.upper())
    HDR.code()
    HDR.code(BEG_HEAD)

    # Preserve Custom code from before
    for line in custom_lines['FILE HEAD']:
        HDR.write(line)

    HDR.code(END_CUSTOM)
    HDR.code()
    HDR.code(x.code_include_h())
    HDR.namespace('Niflib')
    if not x.inherit:
        HDR.code('using namespace std;')
    HDR.code(x.code_fwd_decl())
    HDR.code('class ' + x.cname + ';')
    HDR.code('typedef Ref<' + x.cname + '> ' + x.cname + 'Ref;')
    HDR.code()
    HDR.comment(x.description, True)
    if x.inherit:
        HDR.code('class ' + x.cname + ' : public ' + x.inherit.cname + ' {')
    else:
        HDR.code('class ' + x.cname + ' : public RefObject {')
    HDR.code('public:')
    HDR.code(CLASS_DECL.format(x.cname))
    HDR.code()

    #
    # Show example naive implementation if requested
    #

    # Create a list of members eligible for functions
    if GENACCESSORS:
        func_members = []
        for bmem in x.members:
            if not bmem.arr1_ref and not bmem.arr2_ref and bmem.cname.lower().find("unk") == -1:
                func_members.append(bmem)

        if func_members:
            HDR.code('/***Begin Example Naive Implementation****')
            HDR.code()
            for fmem in func_members:
                HDR.comment(fmem.description + "\n\\return The current value.", False)
                HDR.code(fmem.getter_declare("", ";"))
                HDR.code()
                HDR.comment(fmem.description + "\n\\param[in] value The new value.", False)
                HDR.code(fmem.setter_declare("", ";"))
                HDR.code()
            HDR.code('****End Example Naive Implementation***/')
        else:
            HDR.code('//--This object has no eligible attributes.  No example implementation generated--//')
        HDR.code()

    HDR.code(BEG_MISC)

    # Preserve Custom code from before
    for line in custom_lines['MISC']:
        HDR.write(line)

    HDR.code(END_CUSTOM)
    if x.members:
        HDR.code('protected:')
    HDR.declare(x)
    HDR.code('public:')
    HDR.code(CLASS_INTL)
    HDR.code('};')
    HDR.code()
    HDR.code(BEG_FOOT)

    # Preserve Custom code from before
    for line in custom_lines['FILE FOOT']:
        HDR.write(line)

    HDR.code(END_CUSTOM)
    HDR.code()
    HDR.end()

    # Check if the temp file is identical to the target file
    # overwrite_if_changed( file_name, 'temp' )

    #
    # NiObject Implementation File
    #

    # Get existing custom code
    file_name = ROOT_DIR + '/src/obj/' + x.cname + '.cpp'
    custom_lines = extract_custom_code(file_name)

    CPP = CFile(io.open(file_name, 'wb'))
    print("Generating " + file_name)
    CPP.code(PARTGEN_NOTICE)
    CPP.code()
    CPP.code(BEG_HEAD)

    # Preserve Custom code from before
    for line in custom_lines['FILE HEAD']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code()
    CPP.include('../../include/FixLink.h')
    CPP.include('../../include/ObjectRegistry.h')
    CPP.include('../../include/NIF_IO.h')
    CPP.code(x.code_include_cpp(True, "../../include/gen/", "../../include/obj/"))
    CPP.code("using namespace Niflib;")
    CPP.code()
    CPP.code('//Definition of TYPE constant')
    if x.inherit:
        CPP.code('const Type ' + x.cname + '::TYPE(\"' + x.name + '\", &' + x.inherit.cname + '::TYPE );')
    else:
        CPP.code('const Type ' + x.cname + '::TYPE(\"' + x.name + '\", &RefObject::TYPE );')
    CPP.code()
    x_code_construct = x.code_construct()
    if x_code_construct:
        CPP.code(x.cname + '::' + x.cname + '()' + x_code_construct + ' {')
    else:
        CPP.code(x.cname + '::' + x.cname + '() {')
    CPP.code(BEG_CTOR)

    # Preserve Custom code from before
    for line in custom_lines['CONSTRUCTOR']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code('}')

    CPP.code()
    CPP.code(x.cname + '::' + '~' + x.cname + '() {')
    CPP.code(BEG_DTOR)

    # Preserve Custom code from before
    for line in custom_lines['DESTRUCTOR']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code('}')
    CPP.code()
    CPP.code('const Type & %s::GetType() const {' % x.cname)
    CPP.code('return TYPE;')
    CPP.code('}')
    CPP.code()
    CPP.code('NiObject * ' + x.cname + '::Create() {')
    CPP.code('return new ' + x.cname + ';')
    CPP.code('}')
    CPP.code()

    CPP.code("void %s::Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info ) {" % x.cname)
    CPP.code(BEG_PRE_READ)

    # Preserve Custom code from before
    for line in custom_lines['PRE-READ']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code()
    CPP.stream(x, ACTION_READ)
    CPP.code()
    CPP.code(BEG_POST_READ)

    # Preserve Custom code from before
    for line in custom_lines['POST-READ']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code("}")
    CPP.code()

    CPP.code(
        "void %s::Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const {" % x.cname)
    CPP.code(BEG_PRE_WRITE)

    # Preserve Custom code from before
    for line in custom_lines['PRE-WRITE']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code()
    CPP.stream(x, ACTION_WRITE)
    CPP.code()
    CPP.code(BEG_POST_WRITE)

    # Preserve Custom code from before
    for line in custom_lines['POST-WRITE']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code("}")
    CPP.code()

    CPP.code("std::string %s::asString( bool verbose ) const {" % x.cname)
    CPP.code(BEG_PRE_STRING)

    # Preserve Custom code from before
    for line in custom_lines['PRE-STRING']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code()
    CPP.stream(x, ACTION_OUT)
    CPP.code()
    CPP.code(BEG_POST_STRING)

    # Preserve Custom code from before
    for line in custom_lines['POST-STRING']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code("}")
    CPP.code()

    CPP.code(
        "void %s::FixLinks( const map<unsigned int,NiObjectRef> & objects, list<unsigned int> & link_stack, list<NiObjectRef> & missing_link_stack, const NifInfo & info ) {" % x.cname)

    CPP.code(BEG_PRE_FIXLINK)

    # Preserve Custom code from before
    for line in custom_lines['PRE-FIXLINKS']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code()
    CPP.stream(x, ACTION_FIXLINKS)
    CPP.code()
    CPP.code(BEG_POST_FIXLINK)
    # Preserve Custom code from before
    for line in custom_lines['POST-FIXLINKS']:
        CPP.write(line)

    CPP.code(END_CUSTOM)
    CPP.code("}")
    CPP.code()

    CPP.code("std::list<NiObjectRef> %s::GetRefs() const {" % x.cname)
    CPP.stream(x, ACTION_GETREFS)
    CPP.code("}")
    CPP.code()

    CPP.code("std::list<NiObject *> %s::GetPtrs() const {" % x.cname)
    CPP.stream(x, ACTION_GETPTRS)
    CPP.code("}")
    CPP.code()

    # Output example implementation of public getter/setter Methods if requested
    if GENACCESSORS:
        func_members = []
        for bmem in x.members:
            if not bmem.arr1_ref and not bmem.arr2_ref and bmem.cname.lower().find("unk") == -1:
                func_members.append(bmem)

        if func_members:
            CPP.code('/***Begin Example Naive Implementation****')
            CPP.code()
            for fmem in func_members:
                CPP.code(fmem.getter_declare(x.name + "::", " {"))
                CPP.code("return %s;" % fmem.cname)
                CPP.code("}")
                CPP.code()
                CPP.code(fmem.setter_declare(x.name + "::", " {"))
                CPP.code("%s = value;" % fmem.cname)
                CPP.code("}")
                CPP.code()
            CPP.code('****End Example Naive Implementation***/')
        else:
            CPP.code('//--This object has no eligible attributes.  No example implementation generated--//')
        CPP.code()

    CPP.code(BEG_MISC)

    # Preserve Custom code from before
    for line in custom_lines['MISC']:
        CPP.write(line)

    CPP.code(END_CUSTOM)

    # Check if the temp file is identical to the target file
    # overwrite_if_changed( file_name, 'temp' )

    CPP.end()
