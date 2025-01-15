import argparse
import re
import gdb

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
    def __init__(self):
        super(PrettyPrintMemory, self).__init__("pp", gdb.COMMAND_USER)
        self.parser = self._create_parser()

    def print_session_ctx(self):
        """Print session context details."""
        addresses = [
            "&ses_ctx->src_addr.sa4.sin_addr",
            "&ses_ctx->dst_addr.sa4.sin_addr",
            "&ses_ctx->orig_src_addr.sa4.sin_addr",
            "&ses_ctx->orig_dst_addr.sa4.sin_addr",
        ]

        ports = [
            "&ses_ctx->src_addr.sa4.sin_port",
            "&ses_ctx->dst_addr.sa4.sin_port",
            "&ses_ctx->orig_src_addr.sa4.sin_port",
            "&ses_ctx->orig_dst_addr.sa4.sin_port",
        ]

        for (address, port) in zip(addresses, ports):
            try:
                ret_port = gdb.execute(f"x/2bu {port}", to_string=True)
                numbers = re.findall(r'\b\d+\b', ret_port)
                int_values = [int(num) for num in numbers]
                port_value = int_values[0] * 256 + int_values[1]

                ret_addr = gdb.execute(f'x/4bu {address}', to_string=True)
                print(f"{ret_addr.rstrip()}    (Big-endian Port = {port_value})")

            except gdb.error as e:
                print(f"Error: {e}")
                break

    def print_memory(self, address, type, size):
        try:
            if "ip_addr_t" in str(type) or 'wad_addr' in str(type):
                self.print_ip_address(address, type)
            else:
                mem = f"({type} *) {address}"
                self.print_memory_bytes(mem, type, size)
        except gdb.error as e:
            print(f"Error accessing memory at {address}: {e}")

    def print_ip_address(self, address, type):
        size = 4
        _addr = f"&(({type} *) {address})->sa4.sin_addr"
        self.print_memory_bytes(_addr, type, size)

        size = 2
        _port = f"&(({type} *) {address})->sa4.sin_port"
        self.print_memory_bytes(_port, type, size)

    def print_memory_bytes(self, mem, type, size):
        print(f"++x/{size}bu {mem}")
        result = gdb.execute(f"x/{size}bu {mem}", to_string=True)

        numbers = re.findall(r':\s*((?:\d+\s+)+)', result)
        if not numbers:
            print("No values found in memory")
            return

        bytes_list = [int(x) for x in numbers[0].split()]

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

    def _create_parser(self):
        """Create the argument parser for the command."""
        # Note: We can't use argparse directly with GDB's argument string
        # so we'll create a custom parser
        parser = argparse.ArgumentParser(
            prog="pp",
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
            choices=[1, 2, 4, 8],
            default=0,
            help="Size of memory bytes to print (1, 2, 4, 8 bytes), default: 0"
        )
        parser.add_argument(
            "-c", "--context",
            action="store_true",
            help="Print the session context details"
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
        print("  pp 0x7f01609f1e90            # Print N bytes at address, N is derived automatically")
        print("  pp 0x7f01609f1e90 -s 2       # Print 2 bytes at address")
        print("  pp -c                        # Print session context")

    def parse_args(self, args):
        current_args = []
        current_arg = []
        in_quotes = False

        # Args Input: &fs->new_ip.sa4.sin_port -l 2
        # print(f"Args Input: {arg}")

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

        if parsed_args.context:
            self.print_session_ctx()
            return

        if parsed_args.address:
            addr = parsed_args.address
            ret = gdb.parse_and_eval(addr)
            code = ret.type.code
            type = None
            size = 0

            if code != gdb.TYPE_CODE_PTR:
                print(f"Warning: {addr} is not a pointer, use its address instead")
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
PrettyPrintMemory()

class CircularDoublyLinkedList(gdb.Command):
    """Command to print and count elements in a circular doubly linked list."""

    def __init__(self):
        super(CircularDoublyLinkedList, self).__init__("ptlist", gdb.COMMAND_USER)

    def get_node(self, ptr):
        """Retrieve node data from the given pointer."""
        return gdb.parse_and_eval(f"(struct list_head *){ptr}")

    def invoke(self, arg, from_tty):
        """Execute the command."""
        if not arg:
            print("Usage: ptlist <head_pointer>")
            return

        try:
            head = self.get_node(f"(struct list_head *){arg}")
            # print(f"Value of arg: {head_ptr}")
            # print(f"Type of arg: {type(head_ptr)}")
            # return

            # +p g_wad_app_sessions.sessions
            # $77 = {
            #   next = 0x7f36fc296700,
            #   prev = 0x7f364883df60
            # }

            elements = []
            count = 0
            curr = self.get_node(head['next'])  # Start from head->next
            max_count = 20

            while True:
                if curr == head:
                    break
                if count >= max_count:
                    break
                elements.append(f"{curr}")
                count += 1
                curr = self.get_node(curr['next'])

            for i in range(0, len(elements), 5):
                print(" -> ".join(elements[i:i+5]))

            if count < max_count:
                print(f"Total number of elements: {count}")
            else:
                print(f"Note: Displayed only the first {max_count} elements")

        except gdb.error as e:
            print(f"Error: {e}")

# Instantiate the command
CircularDoublyLinkedList()
