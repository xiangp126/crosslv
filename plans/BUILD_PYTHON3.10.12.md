# Build Python 3.10.12 with sqlite3 Support

## Environment

- OS: Ubuntu 20.04 (Linux 5.4.240)
- GCC: 10.5.0
- GNU Make: 4.2.1
- No sudo access
- System Python: 3.8.10 (too old)
- `libsqlite3-dev` not installed (headers missing)

## Prerequisites

The following dev libraries were already installed on the system:

- libssl-dev (OpenSSL 1.1.1f)
- zlib1g-dev
- libffi-dev
- libreadline-dev
- libncurses-dev
- liblzma-dev

**Missing** (not critical): `libsqlite3-dev`, `libbz2-dev`, `libgdbm-dev`

Since `libsqlite3-dev` was missing and no sudo was available, sqlite3 was built from source first.

## Step 1: Build sqlite3 from Source

```bash
cd /auto/fwgwork1/pexiang

# Download and extract
wget https://www.sqlite.org/2023/sqlite-autoconf-3420000.tar.gz
tar xzf sqlite-autoconf-3420000.tar.gz

# Build and install to local prefix
cd sqlite-autoconf-3420000
./configure --prefix=/auto/fwgwork1/pexiang/sqlite3 --quiet
make -j32 -s
make install -s
```

This installs sqlite3 3.42.0 to `/auto/fwgwork1/pexiang/sqlite3/` with headers in `include/` and libraries in `lib/`.

## Step 2: Download and Extract Python 3.10.12

```bash
cd /auto/fwgwork1/pexiang

wget https://www.python.org/ftp/python/3.10.12/Python-3.10.12.tgz
tar xzf Python-3.10.12.tgz
```

## Step 3: Configure Python with Local sqlite3

```bash
cd /auto/fwgwork1/pexiang/Python-3.10.12

CPPFLAGS="-I/auto/fwgwork1/pexiang/sqlite3/include" \
LDFLAGS="-L/auto/fwgwork1/pexiang/sqlite3/lib -Wl,-rpath,/auto/fwgwork1/pexiang/sqlite3/lib" \
./configure --prefix=/labhome/pexiang/.usr --quiet
```

Key flags:
- `CPPFLAGS` — tells the compiler where to find `sqlite3.h`
- `LDFLAGS` — tells the linker where to find `libsqlite3.so`, and embeds the rpath so the library is found at runtime without setting `LD_LIBRARY_PATH`
- `--prefix=/labhome/pexiang/.usr` — install into `~/.usr` so binaries land in `~/.usr/bin/` which is already in PATH

## Step 4: Build and Install

```bash
make -j32
make install
```

Build output confirms `_sqlite3` module was built. Only `_bz2` and `_gdbm` were not built (non-critical, missing dev headers).

## Step 5: Verify

```bash
python3.10 --version
# Output: Python 3.10.12

python3.10 -c "import sqlite3; print('sqlite3 version:', sqlite3.sqlite_version)"
# Output: sqlite3 version: 3.42.0
```

`python3.10`, `pip3.10`, and `python3.10-config` are now directly available in PATH via `~/.usr/bin/`.

## Step 6: Install pip Packages (Optional)

```bash
pip3.10 install <package_name>
```

## Installed Directory Structure

```
/labhome/pexiang/.usr/              # Python 3.10.12 install (in PATH)
├── bin/python3.10
├── bin/pip3.10
├── bin/python3.10-config
├── include/
├── lib/python3.10/
└── share/

/auto/fwgwork1/pexiang/
├── sqlite3/                        # sqlite3 3.42.0 install (keep — Python depends on it)
│   ├── bin/
│   ├── include/
│   └── lib/
├── sqlite-autoconf-3420000/        # sqlite3 source (can delete)
├── sqlite-autoconf-3420000.tar.gz  # sqlite3 tarball (can delete)
├── Python-3.10.12/                 # Python source (can delete)
└── Python-3.10.12.tgz             # Python tarball (can delete)
```

## Cleanup (Optional)

```bash
rm -rf /auto/fwgwork1/pexiang/sqlite-autoconf-3420000 /auto/fwgwork1/pexiang/sqlite-autoconf-3420000.tar.gz
rm -rf /auto/fwgwork1/pexiang/Python-3.10.12 /auto/fwgwork1/pexiang/Python-3.10.12.tgz
rm -rf /auto/fwgwork1/pexiang/python3.10.12  # old install from first build attempt
```
