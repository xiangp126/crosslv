import re
import gdb
import argparse

class PrintErrno(gdb.Command):
    """Custom GDB command 'perrno' to display the current errno value."""
    def __init__(self):
        super().__init__("perrno", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        try:
            # Fetch the current errno value
            errno = int(gdb.parse_and_eval("*((int*(*)())__errno_location)()"))

            # Lookup the errno in the errors dictionary
            errno_info = self.errors.get(errno, ("Unknown", "Unknown error"))

            # Display the results
            print(f"errno: {errno}")
            print(f"Symbol: {errno_info[0]}")
            print(f"Description: {errno_info[1]}")
        except gdb.error as e:
            print(f"Error: {e}")

    errors = {
        1: ("EPERM", "Operation not permitted"),
        2: ("ENOENT", "No such file or directory"),
        3: ("ESRCH", "No such process"),
        4: ("EINTR", "Interrupted system call"),
        5: ("EIO", "Input/output error"),
        6: ("ENXIO", "No such device or address"),
        7: ("E2BIG", "Argument list too long"),
        8: ("ENOEXEC", "Exec format error"),
        9: ("EBADF", "Bad file descriptor"),
        10: ("ECHILD", "No child processes"),
        11: ("EAGAIN", "Resource temporarily unavailable"),
        11: ("EWOULDBLOCK", "(Same value as EAGAIN) Resource temporarily unavailable"),
        12: ("ENOMEM", "Cannot allocate memory"),
        13: ("EACCES", "Permission denied"),
        14: ("EFAULT", "Bad address"),
        15: ("ENOTBLK", "Block device required"),
        16: ("EBUSY", "Device or resource busy"),
        17: ("EEXIST", "File exists"),
        18: ("EXDEV", "Invalid cross-device link"),
        19: ("ENODEV", "No such device"),
        20: ("ENOTDIR", "Not a directory"),
        21: ("EISDIR", "Is a directory"),
        22: ("EINVAL", "Invalid argument"),
        23: ("ENFILE", "Too many open files in system"),
        24: ("EMFILE", "Too many open files"),
        25: ("ENOTTY", "Inappropriate ioctl for device"),
        26: ("ETXTBSY", "Text file busy"),
        27: ("EFBIG", "File too large"),
        28: ("ENOSPC", "No space left on device"),
        29: ("ESPIPE", "Illegal seek"),
        30: ("EROFS", "Read-only file system"),
        31: ("EMLINK", "Too many links"),
        32: ("EPIPE", "Broken pipe"),
        33: ("EDOM", "Numerical argument out of domain"),
        34: ("ERANGE", "Numerical result out of range"),
        35: ("EDEADLK", "Resource deadlock avoided"),
        35: ("EDEADLOCK", "(Same value as EDEADLK) Resource deadlock avoided"),
        36: ("ENAMETOOLONG", "File name too long"),
        37: ("ENOLCK", "No locks available"),
        38: ("ENOSYS", "Function not implemented"),
        39: ("ENOTEMPTY", "Directory not empty"),
        40: ("ELOOP", "Too many levels of symbolic links"),
        41: ("", "not implemented"),
        42: ("ENOMSG", "No message of desired type"),
        43: ("EIDRM", "Identifier removed"),
        44: ("ECHRNG", "Channel number out of range"),
        45: ("EL2NSYNC", "Level 2 not synchronized"),
        46: ("EL3HLT", "Level 3 halted"),
        47: ("EL3RST", "Level 3 reset"),
        48: ("ELNRNG", "Link number out of range"),
        49: ("EUNATCH", "Protocol driver not attached"),
        50: ("ENOCSI", "No CSI structure available"),
        51: ("EL2HLT", "Level 2 halted"),
        52: ("EBADE", "Invalid exchange"),
        53: ("EBADR", "Invalid request descriptor"),
        54: ("EXFULL", "Exchange full"),
        55: ("ENOANO", "No anode"),
        56: ("EBADRQC", "Invalid request code"),
        57: ("EBADSLT", "Invalid slot"),
        58: ("", "not implemented"),
        59: ("EBFONT", "Bad font file format"),
        60: ("ENOSTR", "Device not a stream"),
        61: ("ENODATA", "No data available"),
        62: ("ETIME", "Timer expired"),
        63: ("ENOSR", "Out of streams resources"),
        64: ("ENONET", "Machine is not on the network"),
        65: ("ENOPKG", "Package not installed"),
        66: ("EREMOTE", "Object is remote"),
        67: ("ENOLINK", "Link has been severed"),
        68: ("EADV", "Advertise error"),
        69: ("ESRMNT", "Srmount error"),
        70: ("ECOMM", "Communication error on send"),
        71: ("EPROTO", "Protocol error"),
        72: ("EMULTIHOP", "Multihop attempted"),
        73: ("EDOTDOT", "RFS specific error"),
        74: ("EBADMSG", "Bad message"),
        75: ("EOVERFLOW", "Value too large for defined data type"),
        76: ("ENOTUNIQ", "Name not unique on network"),
        77: ("EBADFD", "File descriptor in bad state"),
        78: ("EREMCHG", "Remote address changed"),
        79: ("ELIBACC", "Can not access a needed shared library"),
        80: ("ELIBBAD", "Accessing a corrupted shared library"),
        81: ("ELIBSCN", ".lib section in a.out corrupted"),
        82: ("ELIBMAX", "Attempting to link in too many shared libraries"),
        83: ("ELIBEXEC", "Cannot exec a shared library directly"),
        84: ("EILSEQ", "Invalid or incomplete multibyte or wide character"),
        85: ("ERESTART", "Interrupted system call should be restarted"),
        86: ("ESTRPIPE", "Streams pipe error"),
        87: ("EUSERS", "Too many users"),
        88: ("ENOTSOCK", "Socket operation on non-socket"),
        89: ("EDESTADDRREQ", "Destination address required"),
        90: ("EMSGSIZE", "Message too long"),
        91: ("EPROTOTYPE", "Protocol wrong type for socket"),
        92: ("ENOPROTOOPT", "Protocol not available"),
        93: ("EPROTONOSUPPORT", "Protocol not supported"),
        94: ("ESOCKTNOSUPPORT", "Socket type not supported"),
        95: ("EOPNOTSUPP", "Operation not supported"),
        95: ("ENOTSUP", "(Same value as EOPNOTSUPP) Operation not supported"),
        96: ("EPFNOSUPPORT", "Protocol family not supported"),
        97: ("EAFNOSUPPORT", "Address family not supported by protocol"),
        98: ("EADDRINUSE", "Address already in use"),
        99: ("EADDRNOTAVAIL", "Cannot assign requested address"),
        100: ("ENETDOWN", "Network is down"),
        101: ("ENETUNREACH", "Network is unreachable"),
        102: ("ENETRESET", "Network dropped connection on reset"),
        103: ("ECONNABORTED", "Software caused connection abort"),
        104: ("ECONNRESET", "Connection reset by peer"),
        105: ("ENOBUFS", "No buffer space available"),
        106: ("EISCONN", "Transport endpoint is already connected"),
        107: ("ENOTCONN", "Transport endpoint is not connected"),
        108: ("ESHUTDOWN", "Cannot send after transport endpoint shutdown"),
        109: ("ETOOMANYREFS", "Too many references: cannot splice"),
        110: ("ETIMEDOUT", "Connection timed out"),
        111: ("ECONNREFUSED", "Connection refused"),
        112: ("EHOSTDOWN", "Host is down"),
        113: ("EHOSTUNREACH", "No route to host"),
        114: ("EALREADY", "Operation already in progress"),
        115: ("EINPROGRESS", "Operation now in progress"),
        116: ("ESTALE", "Stale file handle"),
        117: ("EUCLEAN", "Structure needs cleaning"),
        118: ("ENOTNAM", "Not a XENIX named type file"),
        119: ("ENAVAIL", "No XENIX semaphores available"),
        120: ("EISNAM", "Is a named type file"),
        121: ("EREMOTEIO", "Remote I/O error"),
        122: ("EDQUOT", "Disk quota exceeded"),
        123: ("ENOMEDIUM", "No medium found"),
        124: ("EMEDIUMTYPE", "Wrong medium type"),
        125: ("ECANCELED", "Operation canceled"),
        126: ("ENOKEY", "Required key not available"),
        127: ("EKEYEXPIRED", "Key has expired"),
        128: ("EKEYREVOKED", "Key has been revoked"),
        129: ("EKEYREJECTED", "Key was rejected by service"),
        130: ("EOWNERDEAD", "Owner died"),
        131: ("ENOTRECOVERABLE", "State not recoverable"),
        132: ("ERFKILL", "Operation not possible due to RF-kill"),
        133: ("EHWPOISON", "Memory page has hardware error")
    }

# Instantiate the command
PrintErrno()

class PrettyPrintMemory(gdb.Command):
    """Print memory at the specified address using various formats."""
    def __init__(self, name):
        super(PrettyPrintMemory, self).__init__(name, gdb.COMMAND_USER)
        self.parser = self._create_parser()

    def print_session_ctx(self, address, type):
        mem = f"({type} *) {address}"
        addresses = [
            f"&({mem})->src_addr.sa4.sin_addr",
            f"&({mem})->dst_addr.sa4.sin_addr",
            f"&({mem})->orig_src_addr.sa4.sin_addr",
            f"&({mem})->orig_dst_addr.sa4.sin_addr",
        ]

        ports = [
            f"&({mem})->src_addr.sa4.sin_port",
            f"&({mem})->dst_addr.sa4.sin_port",
            f"&({mem})->orig_src_addr.sa4.sin_port",
            f"&({mem})->orig_dst_addr.sa4.sin_port",
        ]

        for (address, port) in zip(addresses, ports):
            try:
                # The address
                ret_addr = gdb.execute(f'x/4bu {address}', to_string=True)
                # Format each number in the address to 3 digits
                # (gdb) x/4bu &((struct wad_session_context *) 0x7fcd4e948fb0)->src_addr.sa4.sin_addr
                # +x/4bu &((struct wad_session_context *) 0x7fcd4e948fb0)->src_addr.sa4.sin_addr
                # 0x7fcd4e9491c4: 172     16      67      185
                addr_parts = ret_addr.split(':')
                numbers = re.findall(r'\b\d+\b', addr_parts[1])
                formatted_numbers = '    '.join(f"{int(num):<3d}" for num in numbers)
                formatted_addr = f"{addr_parts[0]}: {formatted_numbers}"
                # The port
                ret_port = gdb.execute(f"x/2bu {port}", to_string=True)
                numbers = re.findall(r'\b\d+\b', ret_port)
                int_values = [int(num) for num in numbers]
                port_value = (int_values[0] << 8) | (int_values[1])
                # print(f"{ret_addr.rstrip()}    (Big-endian Port = {port_value})")
                print(f"{formatted_addr}    (Big-endian Port = {port_value})")

            except gdb.error as e:
                print(f"Error: {e}")
                break

    def print_memory(self, address, type, size):
        try:
            if "ip_addr_t" in str(type) or 'wad_addr' in str(type):
                self.print_ip_address(address, type)
            elif "wad_session_context" in str(type):
                self.print_session_ctx(address, type)
            else:
                mem = f"({type} *) {address}"
                self.print_memory_bytes(mem, size)
        except gdb.error as e:
            print(f"Error accessing memory at {address}: {e}")

    def print_ip_address(self, address, type):
        size = 4
        _addr = f"&(({type} *) {address})->sa4.sin_addr"
        self.print_memory_bytes(_addr, size)

        size = 2
        _port = f"&(({type} *) {address})->sa4.sin_port"
        self.print_memory_bytes(_port, size)

    def print_memory_bytes(self, mem, size):
        print(f"++x/{size}bu {mem}")
        result = gdb.execute(f"x/{size}bu {mem}", to_string=True)

        # 0x7f9c1ba2e83c: 172     16      67      185
        # (?:...): A non-capturing group, which groups part of the RE but does not create a separate capturing group.
        # re.findall(): Returns a list of all non-overlapping matches of the RE pattern in the input string.
        # It returns all matched substrings based on the capturing groups.
        # re.search(): Searches for the first location where the regular RE matches in the input string.
        # numbers = ['172     16      67      185 ']

        # numbers = re.findall(r':\s*((?:\d+\s+)+)', result)
        # if not numbers:
        #     print("No values found in memory")
        #     return

        # # numbers[0]: Represents the first matched group
        # bytes_list = [int(x) for x in numbers[0].split()]

        numbers = re.search(r':\s*((?:\d+\s+)+)', result)
        if not numbers:
            print("No values found in memory")
            return

        # match.group(0): This corresponds to the entire matched string (the full match).
        # match.group(1): This corresponds to the first captured group.
        bytes_list = [int(x) for x in numbers.group(1).split()]

        # Calculate values in both endianness
        le_val = sum(byte << (8 * i) for i, byte in enumerate(bytes_list))
        be_val = sum(byte << (8 * (size - 1 - i)) for i, byte in enumerate(bytes_list))

        # Convert back to bytes in big-endian order for verification
        bytes_be = be_val.to_bytes(size, byteorder='big')
        hex_string = ' '.join(f'0x{format(byte, "02X")}' for byte in bytes_be)
        dec_string = ' '.join(f'{byte:<4}' for byte in bytes_be)

        print(f"Big-endian Hex string: {hex_string}")
        print(f'Big-endian Dec string: {dec_string}')
        print(f"Big-endian Decimal:    {be_val}")
        print(f"Little-endian Decimal: {le_val}")
        gdb.execute(f"x/{size}bt {mem}")

    def _create_parser(self):
        # Note: We can't use argparse directly with GDB's argument string
        # so we'll create a custom parser
        parser = argparse.ArgumentParser(
            prog="pm",
            description="Print memory at the specified address using various formats",
            add_help=False  # Disable built-in help to handle it ourselves
        )
        parser.add_argument(
            "address",
            nargs="?",
            help="Memory address to print (e.g., 0x7f01609f1e90)",
        )
        parser.add_argument(
            "-s", "--size",
            type=int,
            choices=[1, 2, 4, 8, 16],
            default=0,
            help="Size of memory bytes to print (1, 2, 4, 8, 16 bytes), default: 0"
        )
        parser.add_argument(
            "-h", "--help",
            action="store_true",
            help="Show this help message"
        )
        return parser

    def print_help(self):
        """Print command help."""
        self.parser.print_help()
        print("\nExamples:")
        print("  pm 0x7f01609f1e90            # Print N bytes at address, N is derived automatically")
        print("  pm 0x7f01609f1e90 -s 2       # Print 2 bytes at address")

    def parse_args(self, args):
        current_args = []
        current_arg = []
        in_quotes = False

        # Args Input: &fs->new_ip.sa4.sin_port -l 2
        # print(f"Args Input: {args}")

        for char in args:
            if char == '"':
                in_quotes = not in_quotes
            elif char.isspace() and not in_quotes:
                if current_arg:
                    current_args.append(''.join(current_arg))
                    current_arg = []
            else:
                current_arg.append(char)

        if current_arg:
            current_args.append(''.join(current_arg))

        # Args Parsed: ['&fs->new_ip.sa4.sin_port', '-l', '2']
        # print(f"Args Parsed: {current_args}")

        try:
            return self.parser.parse_args(current_args)
        except SystemExit:
            return None
        except Exception as e:
            print(f"Error parsing arguments: {e}")
            self.print_help()
            return None

    def invoke(self, args, from_tty):
        parsed_args = self.parse_args(args)
        if not parsed_args:
            return

        if parsed_args.help:
            self.print_help()
            return

        if parsed_args.address:
            addr = parsed_args.address
            ret = gdb.parse_and_eval(addr)
            code = ret.type.code
            type = None
            size = 0

            if code != gdb.TYPE_CODE_PTR:
                addr = ret.address
                type = ret.type
            else:
                addr = ret
                type = ret.type.target()

            size = type.sizeof
            if parsed_args.size:
                size = parsed_args.size
            self.print_memory(addr, type, min(16, size))
        else:
            self.print_help()

# Instantiate the command
PrettyPrintMemory("pm")
PrettyPrintMemory("pmem")

class SetWatch(gdb.Command):
    """Set a watchpoint on the memory location of the given input."""
    def __init__(self):
        super(SetWatch, self).__init__("setwatch", gdb.COMMAND_USER)

    def invoke(self, args, from_tty):
        # Parse the input argument
        if not args:
            print("Usage: setwatch <variable>")
            return

        try:
            # Evaluate the input argument to get its address
            ret = gdb.parse_and_eval(args)
            code = ret.type.code
            type = None
            address = None
            watch_point = None

            if code != gdb.TYPE_CODE_PTR:
                address = ret.address
                type = ret.type
                watch_point=f'({type} *) {address}'
            else:
                address = ret
                type = ret.type.target()
                watch_point=f'({type}*) {address}'

            # Set a watchpoint on the memory location
            gdb.execute(f"watch *({watch_point})")

        except gdb.error as e:
            print(f"Error: {e}")
            return

# Instantiate the command
SetWatch()

class PDataCommand(gdb.Command):
    def __init__(self, name):
        super(PDataCommand, self).__init__(name, gdb.COMMAND_DATA)

    def invoke(self, argument, from_tty):
        arg = argument.strip()
        if not arg:
            print("Usage: pdata <data_to_print>")
            print("Example: pdata req->req_line->data")
            print("Example: pdata resp->req_line->data")
            return

        try:
            var = gdb.parse_and_eval(arg)
            # Look up the canonical type for 'struct wad_sstr'
            wad_sstr_type = gdb.lookup_type("struct wad_sstr")
            wad_buff_region_type = gdb.lookup_type("struct wad_buff_region")
            wad_str_type = gdb.lookup_type("struct wad_str")
            wad_line_type = gdb.lookup_type("struct wad_line")
            wad_http_hdr_type = gdb.lookup_type("struct wad_http_hdr")
            wad_http_hdr_line_type = gdb.lookup_type("struct wad_http_hdr_line")
            wad_http_start_line_type = gdb.lookup_type("struct wad_http_start_line")

            type = var.type
            addr = var.address

            if type.code == gdb.TYPE_CODE_PTR:
                # Get the type of the object that the pointer points to
                type = var.type.target()
                addr = var
                var = var.dereference()

            if addr == 0:
                gdb.execute(f"p {arg}")
                return

            # Strip qualifiers (const, volatile) from the type
            unqualified_type = type.unqualified()
            if unqualified_type in [wad_buff_region_type, wad_line_type, wad_http_hdr_type, wad_http_hdr_line_type,
                                    wad_http_start_line_type]:
                var = gdb.parse_and_eval(f"(({type} *){addr})->data")
                addr = var.address
            elif unqualified_type == wad_str_type:
                gdb.execute(f"p *(({type} *){addr})")
                return True
            elif unqualified_type == wad_sstr_type:
                pass
            else:
                print(f"Error: Unexpected type: {unqualified_type}")
                return False

            print(var)

            buff_addr = var['buff']
            buff_start = var['start']
            buff_length = var['len']

            if buff_addr == 0:
                gdb.execute(f"p {buff_addr}")
                return

            # Construct the command string for the substring.
            cmd = "p/s (({0} *){1})->buff->data[{2}]@{3}".format(wad_sstr_type, addr, buff_start, buff_length)
            gdb.execute(cmd)
        except gdb.error as e:
            print("Error executing command: {}".format(e))

# Register the command with GDB.
PDataCommand("pdata")
PDataCommand("pd")

class PrintListCommand(gdb.Command):
    """Traverse and print a linked list in GDB.

    Modes:
      1. Raw mode (one argument): plist <list_head>
         - Simply prints the raw list element addresses in groups of 5 per line.
      2. Container mode (three or four arguments):
             plist <list_head> <container_type> <member_name> [fields_to_print]
         - Computes the container from the list node and prints additional details.
         - If [fields_to_print] is provided, only the fields specified will be printed.
         - Otherwise, the entire container is printed.
    """

    def __init__(self, name):
        super(PrintListCommand, self).__init__(name, gdb.COMMAND_USER)
        # Maximum nodes to search/traverse to avoid infinite loops.
        self._max_search_nodes = 1000
        # Maximum nodes to print.
        self._max_print_nodes = 80
        self.list_head_type = gdb.lookup_type("struct list_head")
        self.wad_buff_type = gdb.lookup_type("struct wad_buff")
        # Initialize the PData command.
        self.pdata = PDataCommand("pdata")

    def get_offset_of(self, container_type, member_name):
        # Compute the offset of the member in the container type.
        return int(gdb.parse_and_eval(f"(unsigned long)&(({container_type} *)0)->{member_name}"))

    def container_of(self, list_ptr, container_type, member_name):
        # Given a pointer to a list element, compute the pointer to the container structure.
        offset = self.get_offset_of(container_type, member_name)
        return (list_ptr.cast(gdb.lookup_type("unsigned long")) - offset).cast(
            gdb.lookup_type(container_type).pointer()
        )

    def traverse_list(self, reverse, head, container_type, member_name, fields_to_print=None):
        # Container mode traversal.
        node_ptrs = []
        wad_sstr_type = gdb.lookup_type("struct wad_sstr")

        # By default, reverse is enabled (using 'prev'); if --no-reverse is provided, use 'next'.
        if reverse:
            current = head['prev']
            next_field = 'prev'
        else:
            current = head['next']
            next_field = 'next'

        while current != head:
            node_ptrs.append(current)
            current = current[next_field]
            if len(node_ptrs) >= self._max_search_nodes:
                print(f"Warning: More than {self._max_search_nodes} nodes found. Only count {self._max_search_nodes}.")
                break

        total_nodes = len(node_ptrs)
        print(f"=== Total nodes found: {total_nodes} ===")

        idx = 1
        nodes_to_print = node_ptrs[:self._max_print_nodes]
        if reverse:
            nodes_to_print = node_ptrs[-self._max_print_nodes:]
            idx = len(nodes_to_print)

        for node in nodes_to_print:
            try:
                # Compute the container from the list element.
                real_node_ptr = self.container_of(node, container_type, member_name)
                real_node = real_node_ptr.dereference()

                print(f"\n=== Node {idx}/{total_nodes} ===")
                print(f"{'List Elem:':<10} {node}, member in container: {member_name}")
                print(f"{'Container:':<10} {real_node_ptr}, (({container_type} *) {real_node_ptr})")

                if fields_to_print:
                    for field in fields_to_print:
                        # field_val = real_node[fields_to_print]
                        # field_type = field_val.type
                        formatted_field=f"((({container_type} *) {real_node_ptr})->{field})"
                        field_val = gdb.parse_and_eval(formatted_field)
                        field_type = field_val.type
                        print(f"{'Field:':<{6}} {field}, Type: {field_type}")
                        print(f"((({container_type} *) {real_node_ptr})->{field})")

                        if field_type.code == gdb.TYPE_CODE_PTR:
                            field_val = field_val.dereference()
                            field_type = field_val.type

                        # for wad_sstr_type, call pdata to print the data
                        if field_type == wad_sstr_type:
                            self.pdata.invoke(f"((({container_type} *) {real_node_ptr})->{field})", False)
                            if real_node_ptr == f"{self.wad_buff_type} *":
                                gdb.execute(f"p (({container_type} *) {real_node_ptr})->hdr_attr->name")
                                gdb.execute(f"p (({container_type} *) {real_node_ptr})->hdr_attr->id")
                        else:
                            print(field_val)
                else:
                    print(real_node)

                # Print the embedded list pointers for verification.
                list_entry = real_node[member_name]
                print("\nCurrent pointers:")
                print(f"  next: {list_entry['next']} (head: {head})")
                print(f"  prev: {list_entry['prev']}")

            except Exception as e:
                print(f"\n=== Error at Node {idx} ===")
                print(f"Failed to process node: {str(e)}")
                print("=== Stopping traversal ===")
                return # Exit loop immediately on error

            if reverse:
                idx -= 1
            else:
                idx += 1
        # Print a summary message.
        summary_message = "=== Summary: {0} nodes found, {1} nodes printed ".format(total_nodes, min(total_nodes, self._max_print_nodes))
        if reverse:
            summary_message += "(in reverse order) ==="
        summary_message += "===\n"
        print(summary_message)

    def traverse_raw_list(self, head):
        # Raw mode: simply collect the linked list element addresses.
        node_ptrs = []
        current = head['next']

        while current != head:
            node_ptrs.append(current)
            current = current['next']
            if len(node_ptrs) >= self._max_search_nodes:
                print(f"Warning: More than {self._max_search_nodes} nodes found. Breaking to avoid infinite loop.")
                break

        # Add the head node to the list.
        # node_ptrs.append(head_addr)
        total_nodes = len(node_ptrs)
        print(f"=== Total nodes found: {total_nodes} ===")
        print("Raw List Nodes (addresses):")

        # Print 5 nodes per line.
        for i in range(0, total_nodes, 5):
            group = node_ptrs[i:i+5]
            # Format each node's address as hex.
            addresses = [hex(int(n)) for n in group]
            print("     " + " => ".join(addresses))

        print(f"=== Summary: {total_nodes} nodes found ===")

    def invoke(self, arg, from_tty):
        parser = argparse.ArgumentParser(
        prog="plist",
        description="Traverse and print a linked list in GDB.\n\n"
                    "Modes:\n"
                    "  1. Raw mode: Simply print raw list element addresses.\n"
                    "  2. Container mode: Compute container from the list node and print details.\n\n"
                    "Examples:\n"
                    "  Raw mode:\n"
                    "    plist resp->headers\n"
                    "  Container mode:\n"
                    "    plist req->headers wad_http_hdr link\n"
                    "    plist req->headers wad_http_hdr link val\n"
                    "    plist buff --buff-region\n"
                    "    plist buff --buff-region-data\n"
                    "    plist buff --buff-region --fields data\n"
                    "    plist buff --buff-region --fields ref_count data\n"
                    "    plist req->headers --http-header\n"
                    "    plist &msg->headers --http-header --fields hdr_attr data",
        formatter_class=argparse.RawTextHelpFormatter  # Preserves newlines in help text
        )
        # Optional arguments for the list traversal.
        # If dest is specified, the attribute will use the name provided in dest instead of the default derived name.
        parser.add_argument("--no-reverse", action="store_false", dest="reverse",
                            default=True, help="Disable reverse traversal. Only for container mode.")
        parser.add_argument("--max-search", type=int, default=self._max_search_nodes,
                            help="Max nodes to search before stopping (default: 1000).")
        parser.add_argument("--max-print", type=int, default=self._max_print_nodes,
                            help="Max nodes to print before stopping (default: 50).")
        parser.add_argument("--buff-region", action="store_true",
                        help="Set container type to 'struct wad_buff_region' and member name to 'link'.")
        parser.add_argument("--buff-region-data", action="store_true",
                        help="Set container type to 'struct wad_buff_region', member name to 'link', and fields to 'data'.")
        parser.add_argument("--http-header", action="store_true",
                        help="Set container type to 'struct wad_http_hdr' and member name to 'link'.")
        parser.add_argument("--http-header-data", action="store_true",
                        help="Set container type to 'struct wad_http_hdr' member name to 'link', and fields to 'data'.")
        parser.add_argument("--dynamic-proc", action="store_true",
                        help="Set container type to 'struct wad_http_dyn_proc' and member name to 'link'.")
        parser.add_argument("--fields", nargs="*", default=[],
                        help="List of fields from the container to print.")
        # Positional arguments for the list traversal.
        parser.add_argument("list_head", help="The head pointer for the list.")
        parser.add_argument("container_type", nargs="?", default=None,
                            help="The container type.")
        parser.add_argument("member_name", nargs="?", default=None,
                            help="The member name of the list node in the container.")
        parser.add_argument("fields_to_print", nargs="*", default=None,
                            help="Optional fields from the container to print.")
        try:
            argv = gdb.string_to_argv(arg)
            args = parser.parse_args(argv)
        except SystemExit:
            return

        if args.buff_region:
            args.container_type = "struct wad_buff_region"
            args.member_name = "link"
        if args.buff_region_data:
            args.container_type = "struct wad_buff_region"
            args.member_name = "link"
            args.fields_to_print = ["data"]
        if args.http_header:
            args.container_type = "struct wad_http_hdr"
            args.member_name = "link"
        if args.http_header_data:
            args.container_type = "struct wad_http_hdr"
            args.member_name = "link"
            args.fields_to_print = ["data"]
        if args.dynamic_proc:
            args.container_type = "struct wad_http_dyn_proc"
            args.member_name = "link"
        if args.fields:
            args.fields_to_print = args.fields

        self._max_search_nodes = args.max_search
        self._max_print_nodes = args.max_print

	    # Process list_head argument.
        try:
            parsed = gdb.parse_and_eval(args.list_head)
        except gdb.error as e:
            print(f"Error: {e}")
            return

        type = parsed.type
        addr = parsed.address

        if type.code == gdb.TYPE_CODE_PTR:
            # Get the type of the object that the pointer points to
            type = parsed.type.target()
            addr = parsed
            parsed = parsed.dereference()

        # Strip qualifiers (const, volatile) from the type
        unqualified_type = type.unqualified()
        if unqualified_type == self.wad_buff_type:
            list_head = parsed['regions'].address
            print(f"(({type} *) {addr})")
        elif unqualified_type == self.list_head_type:
            list_head = addr
        else:
            print(f"Error: Unexpected type: {unqualified_type}")

        # print(f"Head:  (({list_head_type} *) {list_head})")
        print(f"Head: {list_head}")

        if args.container_type is None:
            try:
                self.traverse_raw_list(list_head)
            except Exception as e:
                print(f"Error: {str(e)}")
                raise
        elif args.container_type is not None and args.member_name is not None:
            try:
                container_type = args.container_type
                member_name = args.member_name
                fields_to_print = args.fields_to_print

                try:
                    gdb.lookup_type(container_type)
                except gdb.error:
                    container_type = "struct " + container_type
                    gdb.lookup_type(container_type)

                if list_head.type.code != gdb.TYPE_CODE_PTR:
                    list_head = list_head.address

                self.traverse_list(args.reverse, list_head, container_type, member_name, fields_to_print)
            except Exception as e:
                print(f"Error: {str(e)}")
                raise
        else:
            parser.print_help()

PrintListCommand("plist")
PrintListCommand("pl")
