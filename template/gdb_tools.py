import re
import gdb
import argparse

class PrintErrno(gdb.Command):
    """Custom GDB command 'perrno' to display the current errno value."""
    def __init__(self, name):
        super().__init__(name, gdb.COMMAND_USER)

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
PrintErrno("perrno")
PrintErrno("pe")

class PrintMemory(gdb.Command):
    """Print memory at the specified address using various formats."""
    def __init__(self, name):
        super(PrintMemory, self).__init__(name, gdb.COMMAND_USER)
        self.parser = self.create_parser()
        self.max_size_to_calc_decimal = 8
        self.max_print_size = 120
        self.ojb_size = 0
        self.wad_addr_type = "wad_addr"
        self.ip_addr_t_type = "ip_addr_t"
        self.wad_session_context_type = "struct wad_session_context"

    def invoke(self, argument, from_tty):
        try:
            argument = re.sub(r';', '', argument) # Remove the trailing semicolon
            args = self.parser.parse_args(gdb.string_to_argv(argument))
            args = self.process_command_args(args)
        except SystemExit:
            return
        except gdb.error as e:
            print(f"Error: {e}")
            return

        try:
            parsed = gdb.parse_and_eval(args.address)
            type = parsed.type
            addr = parsed.address
            if type.code == gdb.TYPE_CODE_PTR:
                type = parsed.type.target()
                addr = parsed
                # parsed = parsed.dereference()

            unqualified_type = type.unqualified() # strip qualifiers (const, volatile) from the type
            addr = str(addr).split()[0]
            print_size = self.ojb_size = unqualified_type.sizeof
            if args.size:
                print_size = args.size

            unqualified_type = str(unqualified_type)
            if unqualified_type in [self.wad_addr_type, self.ip_addr_t_type]:
                self.print_ip_address(addr, unqualified_type)
            elif unqualified_type == self.wad_session_context_type:
                self.print_session_ctx(addr, unqualified_type)
            else:
                self.print_memory(addr, unqualified_type, print_size, args.count)

        except gdb.error as e:
            print(f"Error: {e}")

    def process_command_args(self, args):
        if not args.address:
            print("Error: No address provided")
            self.parser.print_help()
            raise SystemExit
        if args.count:
            args.count = gdb.parse_and_eval(args.count)
        else:
            args.count = 1
        if args.size:
            args.size = gdb.parse_and_eval(args.size)
        else:
            args.size = 0
        return args

    def create_parser(self):
        parser = argparse.ArgumentParser(
            prog="pm",
            description="Print memory at the specified address using various formats",
            add_help=True
        )
        parser.add_argument(
            "address",
            nargs="?",
            help="Memory address to print (e.g., 0x7f01609f1e90)",
        )
        parser.add_argument(
            "-s", "--size",
            nargs="?",
            # default=0,
            help="Size of memory bytes to print (default: Object size)"
        )
        parser.add_argument(
            "-c", "--count",
            # type=int,
            nargs="?",
            # default=1,
            help="Number of consecutive objects to print"
        )
        return parser

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

    def print_memory(self, address, type, size, count):
        size = min(size, self.max_print_size)
        try:
            mem = f"({type} *) {address}"
            base_addr = int(str(address).split()[0], 16)
            byte_offset = self.ojb_size
            if self.ojb_size != size:
                print(f"Warning: Object Size and Print Size mismatch. Obj size: {self.ojb_size}, Print size: {size}")
                byte_offset = size

            if count > 1:
                for i in range(count - 1, -1, -1):
                    curr_addr = hex(base_addr + byte_offset * i)
                    print(f"=== Object {i + 1}/{count} at {curr_addr} ===")
                    mem = f"({type} *) {curr_addr}"
                    self.print_raw_memory(mem, size)
            else:
                self.print_raw_memory(mem, size)

        except gdb.error as e:
            print(f"Error accessing memory at {address}: {e}")

    def print_ip_address(self, address, type):
        addr = f"&(({type} *) {address})->sa4.sin_addr"
        self.print_raw_memory(addr, 4)

        port = f"&(({type} *) {address})->sa4.sin_port"
        self.print_raw_memory(port, 2)

    def print_raw_memory(self, mem, size):
        print(f"++x/{size}bu {mem}, Object Size: {self.ojb_size} bytes")
        result = gdb.execute(f"x/{size}bu {mem}", to_string=True)
        if size > self.max_size_to_calc_decimal:
            # ++x/32bu (struct wad_port_ops *) 0x55cb770625a0
            # 0x55cb770625a0 <g_wad_app_trap_port_ops>:       155     221     76      115     203     85      0       0
            # 0x55cb770625a8 <g_wad_app_trap_port_ops+8>:     59      222     76      115     203     85      0       0
            # 0x55cb770625b0 <g_wad_app_trap_port_ops+16>:    213     222     76      115     203     85      0       0
            # 0x55cb770625b8 <g_wad_app_trap_port_ops+24>:    0       223     76      115     203     85      0       0
            output = {}
            line_formatted = {
                'dec': ["Big-endian Dec:"],
                'hex': ["Big-endian Hex:"],
                'bin': ["Big-endian Bin:"],
            }

            lines = result.strip().split('\n')
            if not lines:
                print("No lines found in the command output")
                return

            for line in lines[1:]:
                # Remove anything in angle brackets including the brackets
                line_without_brackets = re.sub(r'<[^>]*>', '', line)
                # Extract the address and numbers
                parts = line_without_brackets.split(':')
                if len(parts) > 1:
                    address = parts[0].strip()
                    numbers = re.findall(r'\d+', parts[1])
                    bytes_list = []
                    for group in numbers:
                        bytes_list.extend([int(x) for x in group.split()])

                    dec_string = ' '.join(f'{byte:<8}' for byte in bytes_list)
                    hex_string = ' '.join(f'0x{format(byte, "02X"):<6}' for byte in bytes_list)
                    bin_string = ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in bytes_list)

                    line_formatted["dec"].append(f"{address}: {dec_string}")
                    line_formatted["hex"].append(f"{address}: {hex_string}")
                    line_formatted["bin"].append(f"{address}: {bin_string}")

            output['dec'] = '\n'.join(line_formatted['dec'])
            output['hex'] = '\n'.join(line_formatted['hex'])
            output['bin'] = '\n'.join(line_formatted['bin'])

            for formatted_output in output.values():
                print(formatted_output)
        else:
            # ========================================================
            # Use re.findall() to extract the values from the result.
            # re.findall(): Returns a list of all non-overlapping matches of the RE pattern in the input string.
            # It returns all matched substrings based on the capturing groups.
            # 0x7f9c1ba2e83c: 172     16      67      185
            # (?:...): A non-capturing group, which groups part of the RE but does not create a separate capturing group.
            # \s matches any whitespace character, including spaces, tabs, and newlines (\n).
            # ========================================================
            numbers = re.findall(r':\s*((?:\d+\s+)+)', result)
            if not numbers:
                print("No values found in memory")
                return
            # numbers[0]: Represents the first matched group
            bytes_list = []
            for group in numbers:
                bytes_list.extend([int(x) for x in group.split()])

            # ========================================================
            # Use re.search() to extract the values from the result.
            # re.search(): Searches for the first location where the regular RE matches in the input string.
            # numbers = ['172     16      67      185 ']

            # numbers = re.search(r':\s*((?:\d+\s+)+)', result)
            # if not numbers:
            #     print("No values found in memory")
            #     return

            # match.group(0): This corresponds to the entire matched string (the full match).
            # match.group(1): This corresponds to the first captured group.
            # bytes_list = [int(x) for x in numbers.group(1).split()]
            # ========================================================

            dec_string = ' '.join(f'{byte:<8}' for byte in bytes_list)
            hex_string = ' '.join(f'0x{format(byte, "02X"):<6}' for byte in bytes_list)
            bin_string = ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in bytes_list)
            print(f'Big-endian Dec string: {dec_string}')
            print(f"Big-endian Hex string: {hex_string}")
            print(f'Big-endian Bin string: {bin_string}')

            be_val = le_val = 0
            for i, byte in enumerate(bytes_list):
                be_val = (be_val << 8) | byte
                le_val |= byte << (8 * i)
            print(f"Big-endian Decimal:    {be_val}")
            print(f"Little-endian Decimal: {le_val}")

# Instantiate the command
PrintMemory("pm")
PrintMemory("pmem")

class SetWatch(gdb.Command):
    """Set a watchpoint on the memory location of the given input."""
    def __init__(self, name):
        super(SetWatch, self).__init__(name, gdb.COMMAND_USER)
        self.parser = argparse.ArgumentParser(
            description="Set a watchpoint on the memory location of the given input",
            add_help=True
        )
        self.parser.add_argument(
            "variable",
            nargs="?",
            help="Variable to set a watchpoint on"
        )

    def invoke(self, arg, from_tty):
        # +setw tcp_port->port->in_ops
        # ++watch *((struct wad_port_ops*) 0x5575380b85a0 <g_wad_app_trap_port_ops>)
        # Error: A syntax error in expression, near `)'.
        try:
            if not (arg.startswith("'") or arg.startswith('"')):
                arg = f'"{arg}"'
            args = self.parser.parse_args(gdb.string_to_argv(arg))
            gdb.execute(f"watch -l {args.variable}")
        except SystemExit:
            return
        except gdb.error as e:
            print(f"Error: {e}")

# Instantiate the command
SetWatch("setw")
SetWatch("sw")

# Print Data in WAD
class PrintData(gdb.Command):
    def __init__(self, name):
        super(PrintData, self).__init__(name, gdb.COMMAND_DATA)
        # No need to lookup the canonical type of the structures using gdb.lookup_type()
        self.wad_addr_type = "wad_addr"
        self.wad_str_type  = "struct wad_str"
        self.fts_fstr_type = "struct fts_fstr"
        self.wad_sstr_type = "struct wad_sstr"
        self.wad_line_type = "struct wad_line"
        self.in_port_t_type = "in_port_t"
        self.ip_addr_t_type = "ip_addr_t"
        self.in_addr_type = "struct in_addr"
        self.wad_buff_region_type   = "struct wad_buff_region"
        self.wad_http_hdr_line_type = "struct wad_http_hdr_line"
        self.wad_fts_sstr_type  = "struct fts_sstr"
        self.wad_http_hdr_type  = "struct wad_http_hdr"
        self.unsigned_char_type = "unsigned char"
        self.wad_http_start_line_type = "struct wad_http_start_line"
        self.wad_session_context_type = "struct wad_session_context"
        # Define the formats
        self.formats = {
            "str": "s", "s": "s",
            "hex": "x", "h": "x", "x": "x",
            "dec": "d", "d": "d",
            "bin": "t", "b": "t", "t": "t",
        }
        self.pmem = PrintMemory("pmem")
        self.parser = self._create_parser()

    def invoke(self, argument, from_tty):
        try:
            # Remove any semicolons from the argument string
            argument = re.sub(r';', '', argument)
            args = self.parser.parse_args(gdb.string_to_argv(argument))
        except SystemExit:
            return

        if not args.data:
            print("Error: No data provided")
            self.parser.print_help()
            return

        try:
            var = gdb.parse_and_eval(args.data)
            type = var.type
            addr = var.address
            if 'void' in str(type):
                gdb.execute(f"p {args.data}") # Print it as is
                return

            # Debug Purpose
            # print(f"var: {var}, type: {type}, addr: {addr}")

            if type.code == gdb.TYPE_CODE_PTR:
                # Get the type of the object that the pointer points to
                type = var.type.target()
                addr = var
                var = var.dereference()

            # Remove any text in double quotes (string literals) or angle brackets (function names)
            # This is needed because addresses in GDB output may contain these elements
            # EXp: (struct list_head *) 0x55b9de5da327 <wad_http_session_get_from_resp+11>
            # Exp: (struct list_head *) 0x55b9de5da327 "CONNECT 172.16.67.182:921 HTTP/1.1"
            if re.search(r'(?:<[^>]+>|"[^"]+")', str(addr)):
                addr = re.sub(r'(?:<[^>]+>|"[^"]+")', '', str(addr)).strip()

            if addr == 0:
                print("Warning: The address is null")
                return

            unqualified_type = str(type.unqualified()) # strip qualifiers (const, volatile) from the type
            fmt = self.formats.get(args.format, "s")

            # Handle types with 'data' member
            if unqualified_type in [self.wad_buff_region_type, self.wad_line_type, self.wad_http_hdr_type,
                                    self.wad_http_hdr_line_type, self.wad_http_start_line_type]:
                # Replace the addr with the address of the 'data' member
                var = gdb.parse_and_eval(f"(({type} *){addr})->data")
                addr = var.address
            elif unqualified_type == self.unsigned_char_type:
                # (unsigned char *) 0x7f80fce8d408 "172.16.67.182"
                # addr = re.sub(r'(?:<[^>]+>|"[^"]+")', '', str(addr)).strip()
                gdb.execute(f"p/s (({type} *){addr})")
                return
            elif unqualified_type in [self.fts_fstr_type, self.wad_str_type] and args.start is not None:
                start = gdb.parse_and_eval(args.start)
                len = gdb.parse_and_eval(args.len)
                cmd = "p/{0} (({1} *){2})->data[{3}]@{4}".format(fmt, type, addr, start, len)
                gdb.execute(cmd)
                return
            elif unqualified_type in [self.wad_sstr_type, self.wad_fts_sstr_type]:
                pass
            elif unqualified_type in [self.wad_addr_type, self.ip_addr_t_type, self.in_addr_type,
                                      self.in_port_t_type, self.wad_session_context_type]:
                self.pmem.invoke(f"\"({type} *){addr}\"", False)
                return
            else:
                # For other types, print the value as is
                gdb.execute(f"p *(({type} *){addr})")
                return

            print(var)

            # For wad_fts_ssrt, the buffer is stored in the 'data' field, not the 'buff' field as in wad_sstr
            if unqualified_type == self.wad_fts_sstr_type:
                buff_addr = var['data']
            else:
                buff_addr = var['buff']
            buff_start = var['start']
            buff_length = var['len']

            if buff_addr == 0:
                print("Warning: The buffer address is null")
                return

            # Construct the command string based on the format
            cmd = "p/{0} (({1} *){2})->buff->data[{3}]@{4}".format(fmt, self.wad_sstr_type, addr, buff_start, buff_length)

            gdb.execute(cmd)
        except gdb.error as e:
            print("Error executing command: {}".format(e))
            return -1

    def _create_parser(self):
        parser = argparse.ArgumentParser(description='Print data with optional formatting')
        parser.add_argument('data', nargs='?', help='Data to print')
        parser.add_argument('start', nargs='?', help='Starting index to print from')
        parser.add_argument('len', nargs='?', default='1', help='Number of elements to print')
        parser.add_argument('--format', '-f',
                            choices=['str', 'hex', 'dec', 'bin', 's', 'x', 'd', 'b', 'h', 't'],
                            default='str', help='Output format (default: str). Shortcuts: s=str, x/h=hex, d=dec, b/t=bin')
        return parser

# Instantiate the command
PrintData("pd")

class SuperTraverse(gdb.Command):
    def __init__(self, name):
        super(SuperTraverse, self).__init__(name, gdb.COMMAND_USER)
        # Maximum nodes to search/traverse to avoid infinite loops.
        self.max_search_nodes = 1000
        # Maximum nodes to print.
        self.max_print_nodes = 100
        # Performance optimization
        self.cached_offset = 0
        self.container_type = None
        # The names of the left and right fields in the tree structure.
        self.left_field = 'left'
        self.right_field = 'right'
        # No need to to get the canonical type of the structures using gdb.lookup_type()
        self.list_head_type = "struct list_head"
        self.wad_buff_type = "struct wad_buff"
        self.wad_sstr_type = "struct wad_sstr"
        self.wad_http_msg_hdrs_type = "struct wad_http_msg_hdrs"
        self.wad_http_proc_msg_type = "struct wad_http_proc_msg"
        self.wad_ips_buff_type = "struct wad_ips_buff"
        self.fg_avl_tree_type  = "struct fg_avl_tree"
        self.wad_input_buff_type = "struct wad_input_buff"
        self.fts_pkt_queue_type  = "struct fts_pkt_queue"
        self.wad_http_body_type  = "struct wad_http_body"
        self.parser = self.create_parser()
        # Use a PrintData object to print data
        self.pdata = PrintData("pdata")

    def invoke(self, argument, from_tty):
        try:
            argument = re.sub(r';', '', argument)
            args = self.parser.parse_args(gdb.string_to_argv(argument))
            args = self.process_command_args(args)
        except SystemExit:
            return
        except gdb.error as e:
            print(f"Error: {e}")
            return

        try:
            parsed = gdb.parse_and_eval(args.head)
            type = parsed.type
            addr = parsed.address
            if type.code == gdb.TYPE_CODE_PTR:
                type = parsed.type.target()
                addr = parsed
                parsed = parsed.dereference()

            unqualified_type = str(type.unqualified()) # strip qualifiers (const, volatile) from the type

            # Function Pointers
            traverse_raw_func = self.traverse_raw_list
            traverse_func = self.traverse_list
            traverse_info_func = self.traverse_list_info

            if unqualified_type == self.wad_http_body_type:
                head = parsed['buff']['regions'].address
            if unqualified_type == self.wad_ips_buff_type:
                head = parsed['data']['regions'].address
            elif unqualified_type in [self.wad_buff_type, self.wad_input_buff_type]:
                head = parsed['regions'].address
            elif unqualified_type == self.fts_pkt_queue_type:
                head = parsed['pkts'].address
            elif unqualified_type in [self.wad_http_msg_hdrs_type, self.wad_http_proc_msg_type]:
                head = parsed['headers'].address
            elif unqualified_type == self.list_head_type:
                head = addr
            elif unqualified_type == self.fg_avl_tree_type:
                head = parsed['root']
                traverse_raw_func = self.traverse_raw_tree
                traverse_func = self.traverse_tree
                traverse_info_func = self.traverse_tree_info
            else:
                print(f"Error: Unexpected type: {unqualified_type}")
                return

            traverse_info_func(head, type, addr)

            if args.container_type is None:
                try:
                    traverse_raw_func(head)
                except Exception as e:
                    print(f"Error: {str(e)}")
                    raise
            elif args.container_type is not None and args.member_name is not None:
                try:
                    container_type = args.container_type
                    member_name = args.member_name
                    fields_to_print = args.fields_to_print

                    self.container_type, container_type = self.lookup_type_with_variants(container_type)
                    self.cached_offset = -1 # Reset the cached offset
                    traverse_func(args.reverse, head, container_type, member_name, fields_to_print)
                except SystemExit:
                    return
                except Exception as e:
                    print(f"Error: {str(e)}")
                    return
            else:
                self.parser.print_help()

        except gdb.error as e:
            print(f"Error: {e}")
            return

    def lookup_type_with_variants(self, type_name):
        variants = [
            type_name,                 # Try as-is first
            "struct " + type_name,     # Try with struct prefix
            "union " + type_name,      # For unions
        ]

        for variant in variants:
            try:
                print(f"Trying to lookup type: {variant}")
                type_obj = gdb.lookup_type(variant)
                return type_obj, variant
            except gdb.error:
                continue

        print(f"Error: Could not find type '{type_name}' with any common prefixes")
        raise SystemExit

    def traverse_list_info(self, list_head, type, addr):
        print(f"Head: {list_head}, Input: (({type} *) {addr})")

    def traverse_tree_info(self, root, type, addr):
        print(f"Tree Root: {root}, Input: (({type} *) {addr})")

    def create_parser(self):
        parser = argparse.ArgumentParser(
            prog="super-traverse",
            description="Traverse and print linked lists and tree structures in GDB.\n\n"
                "Modes:\n"
                "  1. List Raw mode: pl <list_head>\n"
                "  2. List Container mode: pl <list_head> <container_type> <member_name> [fields]\n"
                "  3. Tree Raw mode: pt <tree_root>\n"
                "  4. Tree Container mode: pt <tree_root> <container_type> <member_name> [fields]\n\n"
                "Examples:\n"
                "  List Raw mode:\n"
                "    pl resp->headers\n"
                "  List Container mode:\n"
                "    pl req->headers wad_http_hdr link\n"
                "    pl req->headers wad_http_hdr link val\n"
                "    pl buff --buff-region\n"
                "    pl buff --buff-region-data\n"
                "    pl buff --buff-region --fields data\n"
                "    pl buff --buff-region --fields ref_count data\n"
                "    pl req->headers --http-header\n"
                "    pl &msg->headers --http-header --fields hdr_attr data\n"
                "  Tree Raw mode:\n"
                "    pt tree->root\n"
                "  Tree Container mode:\n"
                "    pl tree fg_avl_node node [fields]",
            formatter_class=argparse.RawTextHelpFormatter  # Preserves newlines in help text
        )

        # Keyword Arguments
        # If dest is specified, the attribute will use the name provided in dest instead of the default derived name.
        parser.add_argument("--no-reverse", action="store_false", dest="reverse",
                default=True, help="Disable reverse traversal. Only for container mode.")
        parser.add_argument("--max-search", type=int, help="Max nodes to search.")
        parser.add_argument("--max-print", type=int, help="Max nodes to print.")
        # --buff-region
        parser.add_argument("--buff-region", "--br", action="store_true",
                help="Set container type to 'struct wad_buff_region' and member name to 'link'.")
        parser.add_argument("--buff-region-data", "--brd", action="store_true",
                help="Set container type to 'struct wad_buff_region', member name to 'link', and fields to 'data'.")
        # --http-header
        parser.add_argument("--http-header", "--hh", action="store_true",
                help="Set container type to 'struct wad_http_hdr' and member name to 'link'.")
        parser.add_argument("--http-header-data", "--hhd", action="store_true",
                help="Set container type to 'struct wad_http_hdr' member name to 'link', and fields to 'data'.")
        # --dynamic-proc
        parser.add_argument("--dynamic-proc", "--dp", action="store_true",
                help="Set container type to 'struct wad_http_dyn_proc' and member name to 'link'.")
        # --fts-pkt
        parser.add_argument("--fts-pkt", "--fp", action="store_true",
                help="Set container type to 'struct fts_pkt_queue' and member name to 'link'.")
        # --ftp-cmd
        parser.add_argument("--ftp-cmd", "--fc", action="store_true",
                help="Set container type to 'struct ftp_cmd' and member name to 'list'.")
        # --fields
        parser.add_argument("--fields", nargs="*", default=[],
                help="List of fields from the container to print.")
        # --avl-node
        parser.add_argument("--avl-node", "--an", action="store_true",
                help="Set container type to 'struct fg_avl_node' and member name to 'node'.")
        # --ips-candidata
        parser.add_argument("--ips-candidate", "--ic", action="store_true",
                help="Set container type to 'struct wad_ips_candidate' and member name to 'node'.")

        # Positional Arguments
        parser.add_argument("head", nargs="?", help="The head pointer for the list or tree.")
        parser.add_argument("container_type", nargs="?", default=None,
                    help="The container type.")
        parser.add_argument("member_name", nargs="?", default=None,
                    help="The member name of the list node in the container.")
        parser.add_argument("fields_to_print", nargs="*", default=None,
                    help="Optional fields from the container to print.")
        return parser

    def process_command_args(self, args):
        if not args.head:
            print("Error: No list head provided")
            self.parser.print_help()
            raise SystemExit
        # --max-search, --max-print
        if args.max_search:
            self.max_search_nodes = args.max_search
        if args.max_print:
            self.max_print_nodes = args.max_print
        # --buff-resion --fields data
        if args.buff_region:
            args.container_type = "struct wad_buff_region"
            args.member_name = "link"
        if args.buff_region_data:
            args.container_type = "struct wad_buff_region"
            args.member_name = "link"
            args.fields_to_print = ["data"]
        # --http-header --fields data
        if args.http_header:
            args.container_type = "struct wad_http_hdr"
            args.member_name = "link"
        if args.http_header_data:
            args.container_type = "struct wad_http_hdr"
            args.member_name = "link"
            args.fields_to_print = ["data"]
        # --dynamic-proc
        if args.dynamic_proc:
            args.container_type = "struct wad_http_dyn_proc"
            args.member_name = "link"
        # --fts-pkt
        if args.fts_pkt:
            args.container_type = "struct wad_fts_pkt"
            args.member_name = "link"
        # --ftp-cmd
        if args.ftp_cmd:
            args.container_type = "struct wad_ftp_cmd"
            args.member_name = "list"
        # --fields
        if args.fields:
            args.fields_to_print = args.fields
        # --avl-node
        if args.avl_node:
            args.container_type = "struct fg_avl_node"
            args.member_name = "node"
        # --ips-candidate
        if args.ips_candidate:
            args.container_type = "struct wad_ips_candidate"
            args.member_name = "node"
        return args

    def offsetof(self, type, member):
        return int(gdb.parse_and_eval(f"(unsigned long)&(({type} *)0)->{member}"))

    def list_entry(self, ptr, type, member):
        if self.cached_offset >= 0:
            offset = self.cached_offset
        else:
            offset = self.cached_offset = self.offsetof(type, member)
        # return (ptr.cast(gdb.lookup_type("unsigned long")) - offset).cast(self.container_type.pointer())
        return gdb.Value(int(ptr) - offset).cast(self.container_type.pointer())

    def addr_sanity_check(self, addr):
        if not addr:
            print("Error: The address is null")
            return False
        # Remove any text in double quotes (string literals) or angle brackets (function names)
        # This is needed because addresses in GDB output may contain these elements
        # EXp: (struct list_head *) 0x55b9de5da327 <wad_http_session_get_from_resp+11>
        # Exp: (struct list_head *) 0x55b9de5da327 "CONNECT 172.16.67.182:921 HTTP/1.1"
        if re.search(r'(?:<[^>]+>|"[^"]+")', str(addr)):
            print(f"Warning: The list head contains unexpected characters: {addr}")
            return False
        return True

    def traverse_list(self, reverse, head, container_type, member_name, fields_to_print=None):
        if not self.addr_sanity_check(head):
            print("Warning: Calling raw list traversal instead")
            return self.traverse_raw_list(head)

        nodes = []
        current = head['next']

        while current and current != head:
            nodes.append(current)
            current = current['next']
            if len(nodes) >= self.max_search_nodes:
                print(f"Warning: More than {self.max_search_nodes} nodes found. Only count {self.max_search_nodes}.")
                break

        total_nodes = len(nodes)
        print(f"=== Total nodes found: {total_nodes} ===")

        idx = 1
        nodes_to_print = nodes[0:self.max_print_nodes:1]
        if reverse:
            nodes_to_print = nodes_to_print[::-1]
            idx = len(nodes_to_print)

        for node in nodes_to_print:
            try:
                # Compute the container from the list element.
                container_ptr = self.list_entry(node, container_type, member_name)
                container = container_ptr.dereference()

                print(f"\n=== Node {idx}/{total_nodes} ===")
                print(f"{'List Elem:':<10} {node}, member in container: {member_name}")
                print(f"{'Container:':<10} {container_ptr}, (({container_type} *) {container_ptr})")

                if fields_to_print:
                    for field in fields_to_print:
                        # field_val = real_node[fields_to_print]
                        # field_type = field_val.type
                        formatted_field=f"((({container_type} *) {container_ptr})->{field})"
                        field_val = gdb.parse_and_eval(formatted_field)
                        field_type = field_val.type
                        print(f"{'Field:':<{6}} {field}, Type: {field_type}")
                        print(f"((({container_type} *) {container_ptr})->{field})")

                        if field_type.code == gdb.TYPE_CODE_PTR:
                            field_val = field_val.dereference()
                            field_type = field_val.type

                        # for wad_sstr_type, call pdata to print the data
                        if str(field_type) == self.wad_sstr_type:
                            # Pass the field expression as a quoted string to prevent parsing issues
                            ret = self.pdata.invoke(f"\"((({container_type} *) {container_ptr})->{field})\"", False)
                            if ret == -1:
                                print("Error: Did you provide the correct Container Type?")
                                return
                            if container_ptr == f"{self.wad_buff_type} *":
                                gdb.execute(f"p (({container_type} *) {container_ptr})->hdr_attr->name")
                                gdb.execute(f"p (({container_type} *) {container_ptr})->hdr_attr->id")
                        else:
                            print(field_val)
                else:
                    print(container)

                # Print the embedded list pointers for verification.
                list_entry = container[member_name]
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
        summary_message = "=== Summary: {0} nodes found, {1} nodes printed ".format(total_nodes, min(total_nodes, self.max_print_nodes))
        if reverse:
            summary_message += "(in reverse order) ==="
        summary_message += "==="
        print(summary_message)

    def traverse_raw_list(self, head):
        # Raw mode: simply collect the linked list element addresses.
        node_ptrs = []
        current = head['next']

        while current and current != head:
            node_ptrs.append(current)
            current = current['next']
            if len(node_ptrs) >= self.max_search_nodes:
                print(f"Warning: More than {self.max_search_nodes} nodes found. Breaking to avoid infinite loop.")
                break

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

    def traverse_tree(self, reverse, head, container_type, member_name, fields_to_print=None):
        root = head
        if not self.addr_sanity_check(root):
            print("Warning: Calling raw tree traversal instead")
            return self.traverse_raw_tree(root)

        stack = []  # Use for iterative in-order traversal
        nodes = []  # Store nodes in in-order traversal sequence
        node_containers = {}  # Map tree nodes to container pointers
        current = root
        total_nodes = 0
        left_field = self.left_field
        right_field = self.right_field

        # Perform an iterative in-order traversal using a classical algorithm.
        while stack or current:
            if total_nodes > self.max_search_nodes:
                break

            while current:
                stack.append(current)
                # Move to the left child
                current = current[left_field]

            if stack:
                current = stack.pop()
                nodes.append(current)

                total_nodes += 1
                # Try to get the container for this node
                try:
                    container_ptr = self.list_entry(current, container_type, member_name)
                    node_containers[current] = container_ptr
                except Exception as e:
                    print(f"Error: Failed to get container for node {current}: {e}")
                    raise SystemExit

                # Move to the right child
                current = current[right_field]

        print(f"=== Total nodes found: {total_nodes} ===")

        idx = 1
        nodes_to_print = nodes[0:self.max_print_nodes:1]
        if reverse:
            nodes_to_print = nodes_to_print[::-1]
            idx = len(nodes_to_print)

        for node in nodes_to_print:
            # Get container pointer
            container_ptr = node_containers.get(node)
            try:
                container = container_ptr.dereference()

                print(f"\n=== Node {idx}/{total_nodes} ===")
                print(f"{'Tree Node:':<10} {node}, member in container: {member_name}")
                print(f"{'Container:':<10} {container_ptr}, (({container_type} *) {container_ptr})")

                # Print selected fields
                if fields_to_print:
                    for field in fields_to_print:
                        formatted_field = f"((({container_type} *) {container_ptr})->{field})"
                        field_val = gdb.parse_and_eval(formatted_field)
                        field_type = field_val.type

                        print(f"{'Field:':<6} {field}, Type: {field_type}")
                        print(f"{formatted_field}")
                        print(field_val)
                else:
                    # Print the whole container
                    print(container)

                print("\nNode connections:")
                left_child = node[left_field]
                print(f"  left:  {left_child}")

                right_child = node[right_field]
                print(f"  right: {right_child}")

            except Exception as e:
                print(f"Error processing node {node}: {e}")
                raise SystemExit

            if reverse:
                idx -= 1
            else:
                idx += 1

        # Print a summary message.
        summary_message = "=== Summary: {0} nodes found, {1} nodes printed ".format(total_nodes, min(total_nodes, self.max_print_nodes))
        if reverse:
            summary_message += "(in reverse order) ==="
        summary_message += "==="
        print(summary_message)

    def traverse_raw_tree(self, root):
        if not root:
            print("Error: Root node is null")
            return

        left_field = self.left_field
        right_field = self.right_field

        queue = [root]
        nodes_info = {}
        total_nodes = 0

        while queue and total_nodes < self.max_search_nodes:
            if total_nodes > self.max_search_nodes:
                print(f"Warning: Reached limit of {self.max_search_nodes} nodes. Some nodes may not be shown.")
                break

            total_nodes += 1
            node = queue.pop(0)
            nodes_info[node] = {
                'left': None,
                'right': None
            }

            try:
                left_child = node[left_field]
                if left_child:
                    queue.append(left_child)
                    nodes_info[node]['left'] = left_child

                right_child = node[right_field]
                if right_child:
                    queue.append(right_child)
                    nodes_info[node]['right'] = right_child
            except gdb.error as e:
                print(f"Error: Unable to access left/right field for node {node}: {e}")
                raise SystemExit

        print(f"=== Total nodes found: {total_nodes} ===")

        print(f"Tree Visualization (right nodes 'above', left nodes 'below')")
        # is_last: If this is the last child of its parent
        print_stack = [(root, '', True, True)] # (node, prefix, is_last, is_root)

        while print_stack:
            node, prefix, is_last, is_root = print_stack.pop()

            branch = ('└── ' if is_last else '├── ') if not is_root else ''
            print(f"{prefix}{branch}{node}")

            child_prefix = prefix + ('    ' if is_last else '│   ')

            left = nodes_info[node]['left'] if node in nodes_info else None
            right = nodes_info[node]['right'] if node in nodes_info else None

            if left:
                print_stack.append((left, child_prefix, True, False))
            if right:
                print_stack.append((right, child_prefix, left is None, False))

        print(f"=== Summary: {total_nodes} nodes found ===")

SuperTraverse("pl")
SuperTraverse("pt")
