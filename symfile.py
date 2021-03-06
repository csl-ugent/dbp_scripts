import os

# Import own modules
import config
import linker
from operator import attrgetter
from support import hex_int
from support import hex_str

class Location:
    """A class representing a source file location"""
    def __init__(self, linenr, filenum):
        self.linenr = linenr
        self.filenum = filenum

    def __eq__(self, other):
        if self.linenr != other.linenr:
            return False
        if self.filenum != other.filenum:
            return False
        return True

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.linenr +1) * (self.filenum +1))

    def __repr__(self):
        return ' '.join((str(self.linenr), str(self.filenum)))

class Line:
    """A class representing a line record"""
    def __init__(self, line):
        tokens = line.split()
        self.address = hex_int(tokens[0])
        self.size = hex_int(tokens[1])
        self.location = Location(int(tokens[2]), int(tokens[3]))

    def __eq__(self, other):
        if self.address != other.address:
            return False
        if self.size != other.size:
            return False
        if self.location != other.location:
            return False

        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return ' '.join((hex_str(self.address), hex_str(self.size), str(self.location)))

    # Update the address for a line, and all other data associated with it (which is nothing anymore at this point)
    def update_address(self, offset):
        self.address = self.address + offset

class Function:
    """A class representing a function record"""
    def __init__(self, line):
        self.lines = []
        tokens = line.split()
        self.address = hex_int(tokens[1])
        self.size = hex_int(tokens[2])
        self.parameter_size = hex_int(tokens[3])
        self.name = tokens[4:]

        # Data will be added onto these later on
        self.publics = []
        self.stacks = []

    # Compares everything, including the name
    def __eq__(self, other):
        if self.name != other.name:
            return False
        return self.syntactic_compare(other)

    # Compares everything but the name: only the structure of the function is compared
    def syntactic_compare(self, other):
        if self.address != other.address:
            return False
        if self.size != other.size:
            return False
        if self.parameter_size != other.parameter_size:
            return False
        if self.lines != other.lines:
            return False
        if self.stacks != other.stacks:
            return False
        return True

    def __ne__(self, other):
        return not self == other

    def add_line_record(self, line):
        self.lines.append(Line(line))

    # Augment the function with section information (such as alignment). If no section was provided,
    # we will try to find it, using the linkermap. If we can find it by name, use the detailed
    # information provided by the linkermap. If found by address, use default information and take
    # only the section_name. We will search for corresponding section either in the pre or the post
    # sections in the linkermap, depending on the pre_sections argument.
    def augment(self, section, build_dir, linkermap=None, pre_sections=True):
        if not section:
            section, named = linker.find_section_for_function(self, linkermap, linkermap.pre_sections if pre_sections else linkermap.post_sections)
        else:
            named = True

        if named:
            self.alignment = section.alignment
            self.section_size = section.size
            self.section_name = os.path.join(build_dir, section.obj) + ':' + section.name
        else:
            self.alignment = 4
            self.section_size = self.size
            name = ' '.join(self.name)
            if name == '<name omitted>':
                name = 'startup'
            self.section_name = os.path.join(build_dir, section.obj) + ':.text.' + name

    # We calculate the size of the area that doesn't belong to a line, in the beginning of the function
    # For functions without lines, this comes down to their size.
    def calculate_lineless_area(self):
        self.lineless_size = (self.lines[0].address - self.address) if self.lines else self.size

    # Get the stack record containing the stack offset
    def get_stack_offset_record(self):
        for stack in reversed(self.stacks[1:]):
            # Check whether the signature of the entry matches and if it does, return it
            if len(stack.entries) == 4 and stack.entries[0] == '.cfa:' and stack.entries[1] == 'sp' and stack.entries[3] == '+':
                return stack

        return None

    # Rebuild the meta information (address, size, meta records) using the values of the lines
    # and the size of the lineless area in the beginning of the function. Some functions don't
    # have any lines, for these we don't calculate the new address but use the one passed as
    # an argument.
    def rebuild_meta_info(self, new_address):
        old_address = self.address
        if self.lines:
            self.address = self.lines[0].address - self.lineless_size
            self.size = (self.lines[-1].address - self.address) + self.lines[-1].size
        else:
            self.address = new_address
            self.size = self.lineless_size

        self.update_meta_records(self.address - old_address)

    # Update the address for a function and its lines
    def update_address(self, address):
        offset = address - self.address
        self.address = address
        self.update_meta_records(offset)
        for line in self.lines:
            line.update_address(offset)

    # Updates all the meta records
    def update_meta_records(self, offset):
        if self.stacks:
            # Set the information for the STACK CFI INIT record
            stack_init = self.stacks[0]
            stack_init.address = self.address
            stack_init.size = self.size

            # Update the other stack records
            for stack in self.stacks[1:]:
                stack.address = stack.address + offset

        # Update the public records
        for public in self.publics:
            public.address = public.address + offset

    def __repr__(self):
        res = ' '.join(('FUNC', hex_str(self.address), hex_str(self.size), hex_str(self.parameter_size), ' '.join(self.name))) + '\n'
        for line in self.lines:
            res = res + str(line) + '\n'

        return res

class Public:
    """A class representing a public record"""
    def __init__(self, line):
        tokens = line.split()
        self.address = hex_int(tokens[1])
        self.parameter_size = hex_int(tokens[2])
        self.name = tokens[3:]

    def __eq__(self, other):
        if self.address != other.address:
            return False
        if self.parameter_size != other.parameter_size:
            return False
        if self.name != other.name:
            return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return ' '.join(('PUBLIC', hex_str(self.address), hex_str(self.parameter_size), ' '.join(self.name)))

class Stack:
    """A class representing a stack record"""
    def __init__(self, line):
        tokens = line.split()
        # Decode INIT records and other records differently
        if tokens[2] == 'INIT':
            self.address = hex_int(tokens[3])
            self.size = hex_int(tokens[4])
            self.entries = tokens[5:]
        else:
            self.address = hex_int(tokens[2])
            self.size = 0
            self.entries = tokens[3:]

    def __eq__(self, other):
        if self.address != other.address:
            return False
        if self.size != other.size:
            return False
        if self.entries != other.entries:
            return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        if self.size != 0:
            return ' '.join(('STACK CFI INIT', hex_str(self.address), hex_str(self.size), ' '.join(self.entries)))
        else:
            return ' '.join(('STACK CFI', hex_str(self.address), ' '.join(self.entries)))

    def get_frame_size(self):
        return int(self.entries[2])

    def set_frame_size(self, size):
        self.entries[2] = str(size)

class SymFile:
    """A class representing a symfile"""
    def __init__(self):
        self.info = ''
        self.files = []
        self.funcs = []
        self.publics = []
        self.stacks = []

        # Data will be added to these records, but they're not necessarily written out in the
        # new symfile. This doesn't happen for (often duplicate) stack records anymore, and
        # might not happen in the future for publics anymore either.
        self.unassociated_publics = []
        self.unassociated_stacks = []

    def __eq__(self, other):
        # Copy function lists, order on address, and compare
        a = self.funcs
        b = other.funcs
        a.sort(key=attrgetter('address'))
        b.sort(key=attrgetter('address'))
        if a != b:
            return False

        # Disable the comparing of publics. When recreating a symfile we can't guarantee these to be correct. Publics
        # that are located before the first FUNC (such as _init) can after NOP insertion end up on a different address
        # that we can not predict. It is also a question what extra help these publics bring to the primary use of
        # recreated symfiles: using them to interpret crash reports. An improvement here would be to only compare publics
        # whose address (in the correct symfile) comes before the address of the first FUNC record.
        if False:
            # Copy public lists, order on address, and compare
            a = self.publics
            b = other.publics
            a.sort(key=attrgetter('address'))
            b.sort(key=attrgetter('address'))
            if a != b:
                return False

        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        res = self.module
        if self.info:
            res += self.info
        file_str = ''.join([str(f) for f in self.files])
        self.funcs.sort(key=attrgetter('address'))
        func_str = ''.join([str(func) for func in self.funcs])
        self.publics.sort(key=attrgetter('address'))
        public_str = '\n'.join([str(public) for public in self.publics]) + '\n'
        # Get every stack record for every function
        stack_str = '\n'.join([str(stack) for func in self.funcs for stack in func.stacks]) + '\n'
        return res + file_str + func_str + public_str + stack_str

    # Augment the symfile with information from the linkermap
    def augment(self, linkermap, build_dir):
        # Determine how many of each kind of functions there are
        for iii, func in enumerate(self.funcs):
            if linkermap.main_sections[0].address <= (func.address + linkermap.text_start_address):
                self.nr_of_pre_funcs = iii
                break

        self.nr_of_main_funcs = len(linkermap.main_sections)
        self.post_funcs_idx = self.nr_of_pre_funcs + self.nr_of_main_funcs

        # For the pre functions we can't be certain to have section information. This is because
        # -ffunction-sections doesn't always work for initializers. We will provide the linkermap
        # to the augment function to the try to find it.
        for func in self.funcs[:self.nr_of_pre_funcs]:
            func.augment(None, build_dir, linkermap, True)

        # For the main functions we have section information, copy it over to the functions.
        for (func, section) in zip(self.funcs[self.nr_of_pre_funcs:], linkermap.main_sections):
            func.augment(section, build_dir)

        # For the functions at the end, there was no ffunction-sections. Therefore, with possibly
        # multiple functions in a section, we're forced to start searching the corresponding section.
        # Therefore we provide the linkermap to the augment function. We will attempt to determine
        # offsets though from the previous function though.
        if self.post_funcs_idx < len(self.funcs):
            # Get the address at the end of the last main section
            address = self.funcs[self.post_funcs_idx -1].address + linkermap.main_sections[-1].size
            for func in self.funcs[self.post_funcs_idx:]:
                # Get the offset between its address and the address of the last known function
                func.offset = func.address - address
                address = func.address

                # Augment by attempting to find the corresponding section and copy its values.
                func.augment(None, build_dir, linkermap, False)

    # Return the Function that is at this address, or None if nothing is found
    def get_func_by_address(self, address):
        func = self.get_func_containing_address(address)
        if func and func.address == address:
            return func
        else:
            return None

    def get_func_containing_address(self, address):
        first = 0
        last = len(self.funcs) -1
        while first <= last:
            index = (first + last)//2
            func = self.funcs[index]
            if address < func.address:
                last = index -1
            elif address >= (func.address + func.size):
                first = index +1
            else:
                return func

        return None

    # Return the Function associated with a public symbol's address
    def get_func_public(self, address):
        func = self.get_func_containing_address(address)
        if func:
            return func

        # The line might be before the first function or behind the last function. If it's
        # before the first function we can return None as this address does not have to be updated.
        # If it's behind the last function we simply return the last line of the last function.
        if address < self.funcs[0].address:
            return None
        else:
            return self.funcs[-1]

    # The constructor to create a SymFile by reading it in from a path
    @classmethod
    def read_f(cls, path):
        with open(path, 'r') as f:
            return cls.read(f)

    # The constructor to create a SymFile by reading it in from a file
    @classmethod
    def read(cls, f):
        self = cls()
        for line in f:
            # Get the type of this record
            record_type = line.split()[0]

            # Handle a module record (there can be only one)
            if record_type == 'MODULE':
                self.module = line

            # Handle an info record (not described by the documentation, but there's only one of these)
            elif record_type == 'INFO':
                self.info = line

            # Handle a file record (there's a number of them, but we don't expect to ever change them)
            elif record_type == 'FILE':
                self.files.append(line)

            # Handle a public symbol
            elif record_type == 'PUBLIC':
                self.publics.append(Public(line))

            # Handle a function record. We create a new instance of the Function class and append it to the list.
            elif record_type == 'FUNC':
                self.funcs.append(Function(line))

            # Handle a stack (CFI) record.
            elif record_type == 'STACK':
                assert line.split()[1] == 'CFI', 'We can only handle STACK CFI frames.'
                self.stacks.append(Stack(line))

            # Handle a line record, let the Function class handle it.
            else:
                self.funcs[-1].add_line_record(line)

        # Remove duplicate FUNC records if they are completely the same. If there are FUNC records on the same address
        # that differ in anything else but their name (because of <unnamed> vs real names issue) the symfile is malformed
        # and we end it here.
        records = {}
        for func in self.funcs:
            if func.address not in records:
                records[func.address] = func
            else:
                assert records[func.address].syntactic_compare(func), 'Two FUNC records with the same address but differing contents!'

        # Get the functions from the dictionary and sort them by value
        self.funcs = [func for func in records.values()]
        self.funcs.sort(key=attrgetter('address'))

        # Associate all stack records to lines or functions (except for those with negative addresses).
        records = {}
        for stack in (stack for stack in self.stacks if stack.address < 0x8000000):
            # If it's an INIT record we should be able to associate it to a function.
            if stack.size:
                func = self.get_func_by_address(stack.address)
                if func:
                    # The INIT record should be the first element in the stacks list
                    if not func.stacks:
                        func.stacks.append(stack)
                    else:
                        assert func.stacks[0] == stack, 'Two STACK INIT records with the same address but differing contents!'
                else:
                    self.unassociated_stacks.append(stack)
            else:
                # Try to find the function that contains the stack record's address.
                func = self.get_func_containing_address(stack.address)
                if func:
                    assert func.stacks, 'Trying to add a normal STACK record where no INIT record is present yet!'
                    if stack.address not in records:
                        func.stacks.append(stack)
                        records[stack.address] = stack
                    else:
                        assert records[stack.address] == stack, 'Two STACK records with the same address but differing contents!'
                else:
                    self.unassociated_stacks.append(stack)

        # Associate all publics to lines (except for those with negative addresses).
        for public in (public for public in self.publics if public.address < 0x8000000):
            func = self.get_func_public(public.address)
            if func:
                func.publics.append(public)
            else:
                self.unassociated_publics.append(public)

        return self

    # Write to a path
    def write_f(self, path):
        with open(path, 'w') as f:
            self.write(f)

    # Write to a file
    def write(self, f):
        f.write(str(self))
