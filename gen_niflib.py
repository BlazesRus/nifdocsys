#!/usr/bin/python

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
# Copyright (c) 2005, NIF File Format Library and Tools
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#
#    * Neither the name of the NIF File Format Library and Tools
#      project nor the names of its contributors may be used to endorse
#      or promote products derived from this software without specific
#      prior written permission.
#
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

from __future__ import unicode_literals
from nifxml import *
from distutils.dir_util import mkpath
import os
import io
import hashlib
import itertools

#
# global data
#

copyright_year = 2017

copyright_notice = r'''/* Copyright (c) {0}, NIF File Format Library and Tools
All rights reserved.  Please see niflib.h for license. */'''.format(copyright_year)

incl_guard = r'''
#ifndef _{0}_H_
#define _{0}_H_
'''

# Partially generated notice
partgen_notice = copyright_notice + r'''

//-----------------------------------NOTICE----------------------------------//
// Some of this file is automatically filled in by a Python script.  Only    //
// add custom code in the designated areas or it will be overwritten during  //
// the next update.                                                          //
//-----------------------------------NOTICE----------------------------------//'''

# Fully generated notice
fullgen_notice = copyright_notice + r'''

//---THIS FILE WAS AUTOMATICALLY GENERATED.  DO NOT EDIT---//

// To change this file, alter the gen_niflib.py script.'''

# NiObject standard declaration
classdecl = r'''/*! Constructor */
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
 * \return A string containing a summary of the information within the object in English.  This is the function that Niflyze calls to generate its analysis, so the output is the same.
 */
NIFLIB_API virtual string asString( bool verbose = false ) const;

/*!
 * Used to determine the type of a particular instance of this object.
 * \return The type constant for the actual type of the object.
 */
NIFLIB_API virtual const Type & GetType() const;'''

# NiObject internals
classinternal = r'''/*! NIFLIB_HIDDEN function.  For internal use only. */
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
compound_decl = r'''/*! Default Constructor */
NIFLIB_API {0}();
/*! Default Destructor */
NIFLIB_API ~{0}();
/*! Copy Constructor */
NIFLIB_API {0}( const {0} & src );
/*! Copy Operator */
NIFLIB_API {0} & operator=( const {0} & src );'''

# Enum stream implementation
enum_impl = r'''//--{0}--//

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
enum_impl_case = r'''case {0}: return out << "{1}";
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
block_types["NiKeyframeData"].find_member("Num Rotation Keys").is_manual_update = True
#block_types["NiTriStripsData"].find_member("Num Triangles").is_manual_update = True


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

    def code(self, txt = None):
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
        if txt == None:
            self.write("\n")
            return
    
        # block end
        if txt[:1] == "}": self.indent -= 1
        # special, private:, public:, and protected:
        if txt[-1:] == ":": self.indent -= 1
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
        if txt[-1:] == "{": self.indent += 1
        # special, private:, public:, and protected:
        if txt[-1:] == ":": self.indent += 1
        
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
        self.code( incl_guard.format(txt) )
    
    def namespace(self, txt):
        """
        Begins a namespace scope for the file
        @param txt: The namespace.
        @type txt: str
        """
        if self.namespaced:
            return
        self.namespaced = True
        self.write( 'namespace {0} {{\n'.format(txt) )
    
    def include(self, txt):
        """
        Includes a file
        @param txt: The include filepath.
        @type txt: str
        """
        self.write( '#include {0}\n'.format(txt) )

    # 
    def comment(self, txt, doxygen = True):
        """
        Wraps text in C++ comments and outputs it to the file.  Handles multilined comments as well.
        Result always ends with a newline
        @param txt: The text to enclose in a Doxygen comment
        @type txt: string
        """

        # skip comments when we are in backslash mode
        if self.backslash_mode: return
        
        lines = txt.split( '\n' )

        txt = ""
        for l in lines:
            txt = txt + fill(l, 80) + "\n"

        txt = txt.strip()
        if not txt:
            return
        
        num_line_ends = txt.count( '\n' )
        

        if doxygen:
            if num_line_ends > 0:
                txt = txt.replace("\n", "\n * ")
                self.code("/*!\n * " + txt + "\n */")  
            else:
                self.code("/*! " + txt + " */" )
        else:
            lines = txt.split('\n')
            for l in lines:
                self.code( "// " + l )
    
    def declare(self, block):
        """
        Formats the member variables for a specific class as described by the XML and outputs the result to the file.
        @param block: The class or struct to generate member functions for.
        @type block: Block, Compound
        """
        if isinstance(block, Block):
            #self.code('protected:')
            prot_mode = True
        for y in block.members:
            if not y.is_duplicate:
                if isinstance(block, Block):
                    if y.is_public and prot_mode:
                        self.code('public:')
                        prot_mode = False
                    elif not y.is_public and not prot_mode:
                        self.code('protected:')
                        prot_mode = True
                self.comment(y.description)
                self.code(y.code_declare())
                if y.func:
                  self.comment(y.description)
                  self.code("%s %s() const;"%(y.ctype,y.func))

    def stream(self, block, action, localprefix = "", prefix = "", arg_prefix = "", arg_member = None):
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
        

        # preperation
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
                    self.code("%s::Read( %s, link_stack, info );"%(block.inherit.cname, stream))
                elif action == ACTION_WRITE:
                    self.code("%s::Write( %s, link_map, missing_link_stack, info );"%(block.inherit.cname, stream))
                elif action == ACTION_OUT:
                    self.code("%s << %s::asString();"%(stream, block.inherit.cname))
                elif action == ACTION_FIXLINKS:
                    self.code("%s::FixLinks( objects, link_stack, missing_link_stack, info );"%block.inherit.cname)
                elif action == ACTION_GETREFS:
                    self.code("refs = %s::GetRefs();"%block.inherit.cname)
                elif action == ACTION_GETPTRS:
                    self.code("ptrs = %s::GetPtrs();"%block.inherit.cname)

        # declare and calculate local variables (TODO: GET RID OF THIS; PREFERABLY NO LOCAL VARIABLES AT ALL)
        if action in [ACTION_READ, ACTION_WRITE, ACTION_OUT]:
            block.members.reverse() # calculated data depends on data further down the structure
            for y in block.members:
                if not y.is_duplicate and not y.is_manual_update and action in [ACTION_WRITE, ACTION_OUT]:
                  if y.func:
                      self.code('%s%s = %s%s();'%(prefix, y.cname, prefix, y.func))
                  elif y.is_calculated:
                      if action in [ACTION_READ, ACTION_WRITE]:
                          self.code('%s%s = %s%sCalc(info);'%(prefix, y.cname, prefix, y.cname))
                      # ACTION_OUT is in asString(), which doesn't take version info
                      # so let's simply not print the field in this case
                  elif y.arr1_ref:
                    if not y.arr1 or not y.arr1.lhs: # Simple Scalar
                      cref = block.find_member(y.arr1_ref[0], True) 
                      # if not cref.is_duplicate and not cref.next_dup and (not cref.cond.lhs or cref.cond.lhs == y.name):
                        # self.code('assert(%s%s == (%s)(%s%s.size()));'%(prefix, y.cname, y.ctype, prefix, cref.cname))
                      self.code('%s%s = (%s)(%s%s.size());'%(prefix, y.cname, y.ctype, prefix, cref.cname))
                  elif y.arr2_ref: # 1-dimensional dynamic array
                    cref = block.find_member(y.arr2_ref[0], True) 
                    if not y.arr1 or not y.arr1.lhs: # Second dimension
                      # if not cref.is_duplicate and not cref.next_dup (not cref.cond.lhs or cref.cond.lhs == y.name):
                       # self.code('assert(%s%s == (%s)((%s%s.size() > 0) ? %s%s[0].size() : 0));'%(prefix, y.cname, y.ctype, prefix, cref.cname, prefix, cref.cname))
                      self.code('%s%s = (%s)((%s%s.size() > 0) ? %s%s[0].size() : 0);'%(prefix, y.cname, y.ctype, prefix, cref.cname, prefix, cref.cname))
                    else:
                        # index of dynamically sized array
                        self.code('for (unsigned int i%i = 0; i%i < %s%s.size(); i%i++)'%(self.indent, self.indent, prefix, cref.cname, self.indent))
                        self.code('\t%s%s[i%i] = (%s)(%s%s[i%i].size());'%(prefix, y.cname, self.indent, y.ctype, prefix, cref.cname, self.indent))
                  # else: #has duplicates needs to be selective based on version
                    # self.code('assert(!"%s");'%(y.name))
            block.members.reverse() # undo reverse


        # now comes the difficult part: processing all members recursively
        for y in block.members:
            # get block
            if y.type in basic_types:
                subblock = basic_types[y.type]
            elif y.type in compound_types:
                subblock = compound_types[y.type]
            elif y.type in enum_types:
                subblock = enum_types[y.type]
            elif y.type in flag_types:
                subblock = flag_types[y.type]
                
            # check for links
            if action in [ACTION_FIXLINKS, ACTION_GETREFS, ACTION_GETPTRS]:
                if not subblock.has_links and not subblock.has_crossrefs:
                    continue # contains no links, so skip this member!
            if action == ACTION_OUT:
                if y.is_duplicate:
                    continue # don't write variables twice
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
                    if lastver1 or lastver2 or lastuserver or lastuserver2 or lastvercond: self.code("};")
                    # close old condition block as well    
                    if lastcond:
                        self.code("};")
                        lastcond = None
                    # start new version block
                    
                    concat = ''
                    verexpr = ''
                    if y.ver1:
                        verexpr = "( info.version >= 0x%08X )"%y.ver1
                        concat = " && "
                    if y.ver2:
                        verexpr = "%s%s( info.version <= 0x%08X )"%(verexpr, concat, y.ver2)
                        concat = " && "
                    if y.userver != None:
                        verexpr = "%s%s( info.userVersion == %s )"%(verexpr, concat, y.userver)
                        concat = " && "
                    if y.userver2 != None:
                        verexpr = "%s%s( info.userVersion2 == %s )"%(verexpr, concat, y.userver2)
                        concat = " && "
                    if y_vercond:
                        verexpr = "%s%s( %s )"%(verexpr, concat, y_vercond)
                    if verexpr:
                        # remove outer redundant parenthesis 
                        bleft, bright = scanBrackets(verexpr)
                        if bleft == 0 and bright == (len(verexpr) - 1):
                            self.code("if %s {"%verexpr)
                        else:
                            self.code("if ( %s ) {"%verexpr)
                    
                    # start new condition block
                    if lastcond != y_cond and y_cond:
                        self.code("if ( %s ) {"%y_cond)
                else:
                    # we remain in the same version block    
                    # check condition block
                    if lastcond != y_cond:
                        if lastcond:
                            self.code("};")
                        if y_cond:
                            self.code("if ( %s ) {"%y_cond)
            elif action == ACTION_OUT:
                # check condition block
                if lastcond != y_cond:
                    if lastcond:
                        self.code("};")
                    if y_cond:
                        self.code("if ( %s ) {"%y_cond)
    
            # loop over arrays
            # and resolve variable name
            if not y.arr1.lhs:
                z = "%s%s"%(y_prefix, y.cname)
            else:
                if action == ACTION_OUT:
                    self.code("array_output_count = 0;")
                if y.arr1.lhs.isdigit() == False:
                    if action == ACTION_READ:
                      # default to local variable, check if variable is in current scope if not then try to use
                      #   definition from resized child
                      memcode = "%s%s.resize(%s);"%(y_prefix, y.cname, y.arr1.code(y_arr1_prefix))
                      mem = block.find_member(y.arr1.lhs, True) # find member in self or parents
                      self.code(memcode)
                      
                    self.code(\
                        "for (unsigned int i%i = 0; i%i < %s%s.size(); i%i++) {"%(self.indent, self.indent, y_prefix, y.cname, self.indent))
                else:
                    self.code(\
                        "for (unsigned int i%i = 0; i%i < %s; i%i++) {"\
                        %(self.indent, self.indent, y.arr1.code(y_arr1_prefix), self.indent))
                if action == ACTION_OUT:
                        self.code('if ( !verbose && ( array_output_count > MAXARRAYDUMP ) ) {')
                        self.code('%s << "<Data Truncated. Use verbose mode to see complete listing.>" << endl;'%stream)
                        self.code('break;')
                        self.code('};')
                        
                if not y.arr2.lhs:
                    z = "%s%s[i%i]"%(y_prefix, y.cname, self.indent-1)
                else:
                    if not y.arr2_dynamic:
                        if y.arr2.lhs.isdigit() == False:
                            if action == ACTION_READ:
                                self.code("%s%s[i%i].resize(%s);"%(y_prefix, y.cname, self.indent-1, y.arr2.code(y_arr2_prefix)))
                            self.code(\
                                "for (unsigned int i%i = 0; i%i < %s%s[i%i].size(); i%i++) {"\
                                %(self.indent, self.indent, y_prefix, y.cname, self.indent-1, self.indent))
                        else:
                            self.code(\
                                "for (unsigned int i%i = 0; i%i < %s; i%i++) {"\
                                %(self.indent, self.indent, y.arr2.code(y_arr2_prefix), self.indent))
                    else:
                        if action == ACTION_READ:
                            self.code("%s%s[i%i].resize(%s[i%i]);"%(y_prefix, y.cname, self.indent-1, y.arr2.code(y_arr2_prefix), self.indent-1))
                        self.code(\
                            "for (unsigned int i%i = 0; i%i < %s[i%i]; i%i++) {"\
                            %(self.indent, self.indent, y.arr2.code(y_arr2_prefix), self.indent-1, self.indent))
                    z = "%s%s[i%i][i%i]"%(y_prefix, y.cname, self.indent-2, self.indent-1)
    
            if y.type in native_types:
                # these actions distinguish between refs and non-refs
                if action in [ACTION_READ, ACTION_WRITE, ACTION_FIXLINKS, ACTION_GETREFS, ACTION_GETPTRS]:
                    if (not subblock.is_link) and (not subblock.is_crossref):
                        # not a ref
                        if action in [ACTION_READ, ACTION_WRITE] and y.is_abstract is False:
                            # hack required for vector<bool>
                            if y.type == "bool" and y.arr1.lhs:
                                self.code("{");
                                if action == ACTION_READ:
                                    self.code("bool tmp;")
                                    self.code("NifStream( tmp, %s, info );"%(stream))
                                    self.code("%s = tmp;" % z)
                                else: # ACTION_WRITE
                                    self.code("bool tmp = %s;" % z)
                                    self.code("NifStream( tmp, %s, info );"%(stream))
                                self.code("};")
                            # the usual thing
                            elif not y.arg:
                                cast = ""
                                if ( y.is_duplicate ):
                                    cast = "(%s&)" % y.ctype
                                self.code("NifStream( %s%s, %s, info );"%(cast, z, stream))
                            else:
                                self.code("NifStream( %s, %s, info, %s%s );"%(z, stream, y_prefix, y.carg))
                    else:
                        # a ref
                        if action == ACTION_READ:
                            self.code("NifStream( block_num, %s, info );"%stream)
                            self.code("link_stack.push_back( block_num );")
                        elif action == ACTION_WRITE:
                            self.code("WriteRef( StaticCast<NiObject>(%s), %s, info, link_map, missing_link_stack );" % (z, stream))
                        elif action == ACTION_FIXLINKS:
                            self.code("%s = FixLink<%s>( objects, link_stack, missing_link_stack, info );"%(z,y.ctemplate))
                                
                        elif action == ACTION_GETREFS and subblock.is_link:
                            if not y.is_duplicate:
                                self.code('if ( %s != NULL )\n\trefs.push_back(StaticCast<NiObject>(%s));'%(z,z))
                        elif action == ACTION_GETPTRS and subblock.is_crossref:
                            if not y.is_duplicate:
                                self.code('if ( %s != NULL )\n\tptrs.push_back((NiObject *)(%s));'%(z,z))
                # the following actions don't distinguish between refs and non-refs
                elif action == ACTION_OUT:
                    if not y.arr1.lhs:
                        self.code('%s << "%*s%s:  " << %s << endl;'%(stream, 2*self.indent, "", y.name, z))
                    else:
                        self.code('if ( !verbose && ( array_output_count > MAXARRAYDUMP ) ) {')
                        self.code('break;')
                        self.code('};')
                        self.code('%s << "%*s%s[" << i%i << "]:  " << %s << endl;'%(stream, 2*self.indent, "", y.name, self.indent-1, z))
                        self.code('array_output_count++;')
            else:
                subblock = compound_types[y.type]
                if not y.arr1.lhs:
                    self.stream(subblock, action, "%s%s_"%(localprefix, y.cname), "%s."%z, y_arg_prefix,  y_arg)
                elif not y.arr2.lhs:
                    self.stream(subblock, action, "%s%s_"%(localprefix, y.cname), "%s."%z, y_arg_prefix, y_arg)
                else:
                    self.stream(subblock, action, "%s%s_"%(localprefix, y.cname), "%s."%z, y_arg_prefix, y_arg)

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
            if lastver1 or lastver2 or not(lastuserver is None) or not(lastuserver2 is None) or lastvercond:
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

    # declaration
    # print "$t Get$n() const; \nvoid Set$n($t value);\n\n";
    def getset_declare(self, block, prefix = ""): # prefix is used to tag local variables only
      for y in block.members:
        if not y.func:
          if y.cname.lower().find("unk") == -1:
            self.code( y.getter_declare("", ";") )
            self.code( y.setter_declare("", ";") )
            self.code()


#
# Function to extract custom code from existing file
#
def ExtractCustomCode( file_name ):
    custom_lines = {}
    custom_lines['MISC'] = []
    custom_lines['FILE HEAD'] = []
    custom_lines['FILE FOOT'] = []
    custom_lines['PRE-READ'] = []
    custom_lines['POST-READ'] = []
    custom_lines['PRE-WRITE'] = []
    custom_lines['POST-WRITE'] = []
    custom_lines['PRE-STRING'] = []
    custom_lines['POST-STRING'] = []
    custom_lines['PRE-FIXLINKS'] = []
    custom_lines['POST-FIXLINKS'] = []
    custom_lines['CONSTRUCTOR'] = []
    custom_lines['DESTRUCTOR'] = []
    
    if os.path.isfile( file_name ) == False:
        custom_lines['MISC'].append( "\n" )
        custom_lines['FILE HEAD'].append( "\n" )
        custom_lines['FILE FOOT'].append( "\n" )
        custom_lines['PRE-READ'].append( "\n" )
        custom_lines['POST-READ'].append( "\n" )
        custom_lines['PRE-WRITE'].append( "\n" )
        custom_lines['POST-WRITE'].append( "\n" )
        custom_lines['PRE-STRING'].append( "\n" )
        custom_lines['POST-STRING'].append( "\n" )
        custom_lines['PRE-FIXLINKS'].append( "\n" )
        custom_lines['POST-FIXLINKS'].append( "\n" )
        custom_lines['CONSTRUCTOR'].append( "\n" )
        custom_lines['DESTRUCTOR'].append( "\n" )
        return custom_lines
    
    f = io.open(file_name, 'rt', 1, 'utf-8')
    lines = f.readlines()
    f.close()
   
    custom_flag = False
    custom_name = ""
    
    for l in lines:
        if custom_flag == True:
            if l.find( END_CUSTOM ) != -1:
                custom_flag = False
            else:
                if not custom_lines[custom_name]:
                    custom_lines[custom_name] = [l]
                else:
                    custom_lines[custom_name].append(l)
        if l.find( BEG_MISC ) != -1:
            custom_flag = True
            custom_name = 'MISC'
        elif l.find( BEG_HEAD ) != -1:
            custom_flag = True
            custom_name = 'FILE HEAD'
        elif l.find( BEG_FOOT ) != -1:
            custom_flag = True
            custom_name = 'FILE FOOT'
        elif l.find( BEG_PRE_READ ) != -1:
            custom_flag = True
            custom_name = 'PRE-READ'
        elif l.find( BEG_POST_READ ) != -1:
            custom_flag = True
            custom_name = 'POST-READ'
        elif l.find( BEG_PRE_WRITE ) != -1:
            custom_flag = True
            custom_name = 'PRE-WRITE'
        elif l.find( BEG_POST_WRITE ) != -1:
            custom_flag = True
            custom_name = 'POST-WRITE'
        elif l.find( BEG_PRE_STRING ) != -1:
            custom_flag = True
            custom_name = 'PRE-STRING'
        elif l.find( BEG_POST_STRING ) != -1:
            custom_flag = True
            custom_name = 'POST-STRING'
        elif l.find( BEG_PRE_FIXLINK ) != -1:
            custom_flag = True
            custom_name = 'PRE-FIXLINKS'
        elif l.find( BEG_POST_FIXLINK ) != -1:
            custom_flag = True
            custom_name = 'POST-FIXLINKS'
        elif l.find( BEG_CTOR ) != -1:
            custom_flag = True
            custom_name = 'CONSTRUCTOR'
        elif l.find( BEG_DTOR ) != -1:
            custom_flag = True
            custom_name = 'DESTRUCTOR'
        elif l.find( BEG_INCL ) != -1:
            custom_flag = True
            custom_name = 'INCLUDE'
    
    return custom_lines

#
# Function to compare two files
#

def OverwriteIfChanged( original_file, candidate_file ):
    files_differ = False

    if os.path.isfile( original_file ):
        f1 = file( original_file, 'r' )
        f2 = file( candidate_file, 'r' )

        s1 = f1.read()
        s2 = f2.read()

        f1.close()
        f2.close()
        
        if s1 != s2:
            files_differ = True
            #remove original file
            os.unlink( original_file )
    else:
        files_differ = True

    if files_differ:
        #Files differ, so overwrite original with candidate
        os.rename( candidate_file, original_file )
   
#
# generate compound code
#

mkpath(os.path.join(ROOT_DIR, "include/obj"))
mkpath(os.path.join(ROOT_DIR, "include/gen"))

mkpath(os.path.join(ROOT_DIR, "src/obj"))
mkpath(os.path.join(ROOT_DIR, "src/gen"))

for n in compound_names:
    x = compound_types[n]
    
    # skip natively implemented types
    if x.name in NATIVETYPES.keys(): continue
    
    if not GENALLFILES and not x.cname in GENBLOCKS:
            continue
        
    #Get existing custom code
    file_name = ROOT_DIR + '/include/gen/' + x.cname + '.h'
    custom_lines = ExtractCustomCode( file_name );

    h = CFile(io.open(file_name, 'wb'))
    h.code( fullgen_notice )
    h.guard( x.cname.upper() )
    h.code()
    h.include( '"../NIF_IO.h"' )
    if n in ["Header", "Footer"]:
        h.include( '"../obj/NiObject.h"' )
    h.code( x.code_include_h() )
    h.namespace( 'Niflib' )
    h.code( x.code_fwd_decl() )
    h.code()
    # header
    h.comment(x.description)
    hdr = "struct %s"%x.cname
    if x.template: hdr = "template <class T >\n%s"%hdr
    hdr += " {"
    h.code(hdr)
    
    #constructor/destructor/assignment
    if not x.template:
        h.code( compound_decl.format(x.cname) )

    # declaration
    h.declare(x)

    # header and footer functions
    if n  == "Header":
        h.code( 'NIFLIB_HIDDEN NifInfo Read( istream& in );' )
        h.code( 'NIFLIB_HIDDEN void Write( ostream& out, const NifInfo & info = NifInfo() ) const;' )
        h.code( 'NIFLIB_HIDDEN string asString( bool verbose = false ) const;' )
    
    if n == "Footer":
        h.code( 'NIFLIB_HIDDEN void Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info );' )
        h.code( 'NIFLIB_HIDDEN void Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const;' )
        h.code( 'NIFLIB_HIDDEN string asString( bool verbose = false ) const;' )

    h.code( BEG_MISC )

    #Preserve Custom code from before
    for l in custom_lines['MISC']:
        h.write(l);
        
    h.code( END_CUSTOM )

    # done
    h.code("};")
    h.code()
    h.end()

    if not x.template:
        #Get existing custom code
        file_name = ROOT_DIR + '/src/gen/' + x.cname + '.cpp'
        custom_lines = ExtractCustomCode( file_name );

        cpp = CFile(io.open(file_name, 'wb'))
        cpp.code( partgen_notice )
        cpp.code()
        cpp.code( x.code_include_cpp( True, "../../include/gen/", "../../include/obj/" ) )
        cpp.code( "using namespace Niflib;" )
        cpp.code()
        cpp.code( '//Constructor' )
        
        # constructor
        x_code_construct = x.code_construct()
        #if x_code_construct:
        cpp.code("%s::%s()"%(x.cname,x.cname) + x_code_construct + " {};")
        cpp.code()

        cpp.code('//Copy Constructor')
        cpp.code( '%s::%s( const %s & src ) {'%(x.cname,x.cname,x.cname) )
        cpp.code( '*this = src;' )
        cpp.code('};')
        cpp.code()

        cpp.code('//Copy Operator')
        cpp.code( '%s & %s::operator=( const %s & src ) {'%(x.cname,x.cname,x.cname) )
        for m in x.members:
            if not m.is_duplicate:
                cpp.code('this->%s = src.%s;'%(m.cname, m.cname) )
        cpp.code('return *this;')
        cpp.code('};')
        cpp.code()

        cpp.code( '//Destructor' )
        
        # destructor
        cpp.code("%s::~%s()"%(x.cname,x.cname) + " {};")

        # header and footer functions
        if n  == "Header":
            cpp.code( 'NifInfo ' + x.cname + '::Read( istream& in ) {' )
            cpp.code( '//Declare NifInfo structure' )
            cpp.code( 'NifInfo info;' )
            cpp.code()
            cpp.stream(x, ACTION_READ)
            cpp.code()
            cpp.code( '//Copy info.version to local version var.' )
            cpp.code( 'version = info.version;' )
            cpp.code()
            cpp.code( '//Fill out and return NifInfo structure.' )
            cpp.code( 'info.userVersion = userVersion;' )
            cpp.code( 'info.userVersion2 = userVersion2;' )
            cpp.code( 'info.endian = EndianType(endianType);' )
            cpp.code( 'info.creator = exportInfo.creator.str;' )
            cpp.code( 'info.exportInfo1 = exportInfo.exportInfo1.str;' )
            cpp.code( 'info.exportInfo2 = exportInfo.exportInfo2.str;' )
            cpp.code()
            cpp.code( 'return info;' )
            cpp.code()
            cpp.code( '}' )
            cpp.code()
            cpp.code( 'void ' + x.cname + '::Write( ostream& out, const NifInfo & info ) const {' )
            cpp.stream(x, ACTION_WRITE)
            cpp.code( '}' )
            cpp.code()
            cpp.code( 'string ' + x.cname + '::asString( bool verbose ) const {' )
            cpp.stream(x, ACTION_OUT)
            cpp.code( '}' )
        
        if n == "Footer":
            cpp.code()
            cpp.code( 'void ' + x.cname + '::Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info ) {' )
            cpp.stream(x, ACTION_READ)
            cpp.code( '}' )
            cpp.code()
            cpp.code( 'void ' + x.cname + '::Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const {' )
            cpp.stream(x, ACTION_WRITE)
            cpp.code( '}' )
            cpp.code()
            cpp.code( 'string ' + x.cname + '::asString( bool verbose ) const {' )
            cpp.stream(x, ACTION_OUT)
            cpp.code( '}' )

        cpp.code()
        cpp.code( BEG_MISC )

        #Preserve Custom code from before
        for l in custom_lines['MISC']:
            cpp.write(l);
        
        cpp.code( END_CUSTOM )

        cpp.end()

    # Write out Public Enumeration header Enumerations
if GENALLFILES:
    out = CFile(io.open(ROOT_DIR + '/include/gen/enums.h', 'wb'))
    out.code( fullgen_notice )
    out.guard( 'NIF_ENUMS' )
    out.code()
    out.include( '<iostream>' )
    out.code( 'using namespace std;' )
    out.code()
    out.namespace( 'Niflib' )
    out.code()
    for n, x in itertools.chain(enum_types.items(), flag_types.items()):
      if x.options:
        if x.description:
          out.comment(x.description)
        out.code('enum %s {'%(x.cname))
        for o in x.options:
          out.code('%s = %s, /*!< %s */'%(o.cname, o.value, o.description))
        out.code('};')
        out.code()
        out.code('ostream & operator<<( ostream & out, %s const & val );'%x.cname)
        out.code()
    out.end()

    # Write out Internal Enumeration header (NifStream functions)
if GENALLFILES:
    out = CFile(io.open(ROOT_DIR + '/include/gen/enums_intl.h', 'wb'))
    out.code( fullgen_notice )
    out.guard( 'NIF_ENUMS_INTL' )
    out.code()
    out.include( '<iostream>' )
    out.code( 'using namespace std;' )
    out.code()
    out.include('"../nif_basic_types.h"')
    out.code()
    out.namespace( 'Niflib' )
    out.code()
    for n, x in itertools.chain(enum_types.items(), flag_types.items()):
      if x.options:
        if x.description:
            out.code()
            out.code( '//---' + x.cname + '---//')
            out.code()
        out.code('void NifStream( %s & val, istream& in, const NifInfo & info = NifInfo() );'%x.cname)
        out.code('void NifStream( %s const & val, ostream& out, const NifInfo & info = NifInfo() );'%x.cname)
        out.code()
    out.end()

    #Write out Enumeration Implementation
if GENALLFILES:
    out = CFile(io.open(ROOT_DIR + '/src/gen/enums.cpp', 'wb'))
    out.code( fullgen_notice )
    out.code()
    out.include('<string>')
    out.include('<iostream>')
    out.include('"../../include/NIF_IO.h"')
    out.include('"../../include/gen/enums.h"')
    out.include('"../../include/gen/enums_intl.h"')
    out.code()
    out.code('using namespace std;')
    out.code()
    out.namespace( 'Niflib' )
    out.code()
    out.code()
    for n, x in itertools.chain(enum_types.items(), flag_types.items()):
      if x.options:
        out.code( enum_impl.format(x.cname, x.storage, r''.join((enum_impl_case.format(o.cname, o.name) for o in x.options))) )
        out.code()
    out.end()

    #
    # NiObject Registration Function
    #
    out = CFile(io.open(ROOT_DIR + '/src/gen/register.cpp', 'wb'))
    out.code( fullgen_notice )
    out.code()
    out.include( '"../../include/ObjectRegistry.h"' )
    for n in block_names:
        x = block_types[n]
        out.include( '"../../include/obj/' + x.cname + '.h"' )
    out.code()
    out.namespace( 'Niflib' )
    out.code( 'void RegisterObjects() {' )
    out.code()
    for n in block_names:
        x = block_types[n]
        out.code( 'ObjectRegistry::RegisterObject( "' + x.name + '", ' + x.cname + '::Create );' )
    out.code()
    out.code( '}' )
    out.end()
    

#
# NiObject Files
#
for n in block_names:
    x = block_types[n]
    x_define_name = define_name(x.cname)

    if not GENALLFILES and not x.cname in GENBLOCKS:
        continue
    
    #
    # NiObject Header File
    #

    #Get existing custom code
    file_name = ROOT_DIR + '/include/obj/' + x.cname + '.h'
    custom_lines = ExtractCustomCode( file_name );

    #output new file
    out = CFile(io.open(file_name, 'wb'))
    out.code( partgen_notice )
    out.guard( x.cname.upper() )
    out.code()
    out.code( BEG_HEAD )

    #Preserve Custom code from before
    for l in custom_lines['FILE HEAD']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.code( x.code_include_h() )
    out.namespace( 'Niflib' )
    if not x.inherit:
        out.code( 'using namespace std;' )
    out.code( x.code_fwd_decl() )
    out.code( 'class ' + x.cname + ';' )
    out.code( 'typedef Ref<' + x.cname + '> ' + x.cname + 'Ref;' )
    out.code()
    out.comment( x.description )
    if x.inherit:
        out.code( 'class ' + x.cname + ' : public ' + x.inherit.cname + ' {' )
    else:
        out.code( 'class ' + x.cname + ' : public RefObject {' )
    
    out.code( 'public:' )
    out.code( classdecl.format(x.cname) )
    out.code()

    #
    # Show example naive implementation if requested
    #
    
    # Create a list of members eligable for functions
    if GENACCESSORS:
        func_members = []
        for y in x.members:
            if not y.arr1_ref and not y.arr2_ref and y.cname.lower().find("unk") == -1:
                func_members.append(y)
    
        if len(func_members) > 0:
            out.code( '/***Begin Example Naive Implementation****' )
            out.code()
            for y in func_members:
                out.comment( y.description + "\n\\return The current value.", False )
                out.code( y.getter_declare("", ";") )
                out.code()
                out.comment( y.description + "\n\\param[in] value The new value.", False )
                out.code(  y.setter_declare("", ";") )
                out.code()
            out.code( '****End Example Naive Implementation***/' )
        else:
            out.code ( '//--This object has no eligible attributes.  No example implementation generated--//' )
        out.code()
    
    out.code( BEG_MISC )

    #Preserve Custom code from before
    for l in custom_lines['MISC']:
        out.write(l);
        
    out.code( END_CUSTOM )
    if x.members:
        out.code( 'protected:' )
    out.declare(x)
    out.code( 'public:' )
    out.code( classinternal )
    out.code( '};' )
    out.code()
    out.code( BEG_FOOT )

    #Preserve Custom code from before
    for l in custom_lines['FILE FOOT']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.end()

    ##Check if the temp file is identical to the target file
    #OverwriteIfChanged( file_name, 'temp' )

    #
    # NiObject Implementation File
    #

    #Get existing custom code
    file_name = ROOT_DIR + '/src/obj/' + x.cname + '.cpp'
    custom_lines = ExtractCustomCode( file_name );
    
    out = CFile(io.open(file_name, 'wb'))
    out.code( partgen_notice )
    out.code()
    out.code( BEG_HEAD )

    #Preserve Custom code from before
    for l in custom_lines['FILE HEAD']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.include( '"../../include/FixLink.h"' )
    out.include( '"../../include/ObjectRegistry.h"' )
    out.include( '"../../include/NIF_IO.h"' )
    out.code( x.code_include_cpp( True, "../../include/gen/", "../../include/obj/" ) )
    out.code( "using namespace Niflib;" );
    out.code()
    out.code( '//Definition of TYPE constant' )
    if x.inherit:
        out.code ( 'const Type ' + x.cname + '::TYPE(\"' + x.name + '\", &' + x.inherit.cname + '::TYPE );' )
    else:
        out.code ( 'const Type ' + x.cname + '::TYPE(\"' + x.name + '\", &RefObject::TYPE );' )
    out.code()
    x_code_construct = x.code_construct()
    if x_code_construct:
        out.code( x.cname + '::' + x.cname + '()' + x_code_construct + ' {' )
    else:
        out.code( x.cname + '::' + x.cname + '() {' )
    out.code ( BEG_CTOR )

    #Preserve Custom code from before
    for l in custom_lines['CONSTRUCTOR']:
        out.write(l);
        
    out.code ( END_CUSTOM )
    out.code ( '}' )
    
    out.code()
    out.code( x.cname + '::' + '~' + x.cname + '() {' )
    out.code ( BEG_DTOR )

    #Preserve Custom code from before
    for l in custom_lines['DESTRUCTOR']:
        out.write(l);
        
    out.code ( END_CUSTOM )
    out.code ( '}' )
    out.code() 
    out.code( 'const Type & %s::GetType() const {'%x.cname )
    out.code( 'return TYPE;' )
    out.code( '}' )
    out.code()
    out.code( 'NiObject * ' + x.cname + '::Create() {' )
    out.code( 'return new ' + x.cname + ';' )
    out.code( '}' )
    out.code()

    out.code("void %s::Read( istream& in, list<unsigned int> & link_stack, const NifInfo & info ) {"%x.cname)
    out.code( BEG_PRE_READ )

    #Preserve Custom code from before
    for l in custom_lines['PRE-READ']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.stream(x, ACTION_READ)
    out.code()
    out.code( BEG_POST_READ )

    #Preserve Custom code from before
    for l in custom_lines['POST-READ']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code("}")
    out.code()
      
    out.code("void %s::Write( ostream& out, const map<NiObjectRef,unsigned int> & link_map, list<NiObject *> & missing_link_stack, const NifInfo & info ) const {"%x.cname)
    out.code( BEG_PRE_WRITE )

    #Preserve Custom code from before
    for l in custom_lines['PRE-WRITE']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.stream(x, ACTION_WRITE)
    out.code()
    out.code( BEG_POST_WRITE )

    #Preserve Custom code from before
    for l in custom_lines['POST-WRITE']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code("}")
    out.code()
      
    out.code("std::string %s::asString( bool verbose ) const {"%x.cname)
    out.code( BEG_PRE_STRING )

    #Preserve Custom code from before
    for l in custom_lines['PRE-STRING']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.stream(x, ACTION_OUT)
    out.code()
    out.code( BEG_POST_STRING )

    #Preserve Custom code from before
    for l in custom_lines['POST-STRING']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code("}")
    out.code()

    out.code("void %s::FixLinks( const map<unsigned int,NiObjectRef> & objects, list<unsigned int> & link_stack, list<NiObjectRef> & missing_link_stack, const NifInfo & info ) {"%x.cname)

    out.code( BEG_PRE_FIXLINK )
    
    #Preserve Custom code from before
    for l in custom_lines['PRE-FIXLINKS']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code()
    out.stream(x, ACTION_FIXLINKS)
    out.code()
    out.code( BEG_POST_FIXLINK )
    #Preserve Custom code from before
    for l in custom_lines['POST-FIXLINKS']:
        out.write(l);
        
    out.code( END_CUSTOM )
    out.code("}")
    out.code()

    out.code("std::list<NiObjectRef> %s::GetRefs() const {"%x.cname)
    out.stream(x, ACTION_GETREFS)
    out.code("}")
    out.code()

    out.code("std::list<NiObject *> %s::GetPtrs() const {"%x.cname)
    out.stream(x, ACTION_GETPTRS)
    out.code("}")
    out.code()

    # Output example implementation of public getter/setter Mmthods if requested
    if GENACCESSORS:
        func_members = []
        for y in x.members:
            if not y.arr1_ref and not y.arr2_ref and y.cname.lower().find("unk") == -1:
                func_members.append(y)
    
        if len(func_members) > 0:
            out.code( '/***Begin Example Naive Implementation****' )
            out.code()
            for y in func_members:
                out.code( y.getter_declare(x.name + "::", " {") )
                out.code( "return %s;"%y.cname )
                out.code( "}" )
                out.code()
                
                out.code( y.setter_declare(x.name + "::", " {") )
                out.code( "%s = value;"%y.cname )
                out.code( "}" )
                out.code()
            out.code( '****End Example Naive Implementation***/' )
        else:
            out.code ( '//--This object has no eligible attributes.  No example implementation generated--//' )
        out.code()
        
    out.code( BEG_MISC )

    #Preserve Custom code from before
    for l in custom_lines['MISC']:
        out.write(l);
        
    out.code( END_CUSTOM )

    ##Check if the temp file is identical to the target file
    #OverwriteIfChanged( file_name, 'temp' )

    out.end()
