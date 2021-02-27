"""
Utilities for use by the various scripts.
"""
import io
import multiprocessing
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tarfile
import traceback
import urllib.request

from config import CONFIG as cfg


def warn(message):
    """
    Prints a warning message
    """
    print(f'\x1b[33;1m[!]\x1b[m {message}')


def ensure_root():
    """
    Terminates the program if not run as root
    """
    if os.getuid() != 0:
        print("\x1b[31;1mplease run as root\x1b[m")
        raise SystemExit(1)


def get_consent():
    """
    Prompts the user to confirm a - presumably controversial - action

    No means no*!

    *disclaimer: no actually has no defined meaning here
    """
    while True:
        res = input('type "yes", "skip", or "abort": ')
        if res == "yes":
            return True
        if res == "skip":
            return False
        if res == "abort":
            print("aborting")
            raise SystemExit(1)


def command(*cmd, silent=False, nspawn=None, shell=False, confirm=False,
            stdin=None, capture_stdout=False, env=None, get_retval=False,
            cwd='.'):
    """
    Prints and runs the given command.

    @param silent
        defaults to False. If True, the command is not printed.
    @param nspawn
        defaults to None. If not None, the command is run inside that nspawn
        container.
    @param shell
        defaults to False. If True, the command is expected to be exactly
        one string, and will be run through 'sh -c'
    @param confirm
        defaults to False. If True, the user must confirm before the command
        is run.
    @param stdin
        defaults to None. If not None, this is fed to the command as stdin
        (must be str or bytes)
    @param capture_stdout
        defaults to False. If True, the command stdout is captured and
        returned as bytes.
    @param env
        environment variables to use.
    @param get_retval
        defaults to False. If True, the command return code is returned,
        as an integer, instead of verifying that the command has succeeded.
    @param cwd
        defaults to None. If given, the command is run in this directory.
    """
    if capture_stdout and get_retval:
        raise RuntimeError("cannot capture stdout AND get retval")

    if shell:
        if len(cmd) != 1:
            raise RuntimeError(
                "expected exactly one command string for shell=True, "
                f"but got {cmd!r}"
            )
        cmd = ['sh', '-c'] + list(cmd)
    if nspawn is not None:
        if stdin is not None or capture_stdout:
            cmd = ['systemd-nspawn', '-D', nspawn, '--pipe'] + list(cmd)
        else:
            cmd = ['systemd-nspawn', '-D', nspawn] + list(cmd)
    if not silent:
        if confirm:
            print("\x1b[33;1mwill run:\x1b[m", end=" ")
        else:
            print("\x1b[32;1m$\x1b[m", end=" ")
        print(" ".join(shlex.quote(part) for part in cmd))
        if confirm:
            if not get_consent():
                return
    elif confirm:
        raise RuntimeError("confirm=True but silent=True")

    proc = subprocess.Popen(cmd,
          stdin=None if stdin is None else subprocess.PIPE,
          stdout=subprocess.PIPE if capture_stdout else None,
          cwd=cwd
    )
    if isinstance(stdin, str):
        stdin = stdin.encode('utf-8')
    stdout, _ = proc.communicate(input=stdin)
    if get_retval:
        return proc.returncode
    else:
        if proc.returncode != 0:
            raise RuntimeError(f"invocation failed: {cmd!r}")
        return stdout


def initrd_write(path, *lines, content=None, append=False):
    """
    Writes a file in the initrd.

    @param path
        must be an absolute string (starting with '/').
    @param lines
        each individual line, not ending in \\n, is encoded (if needed),
        padded with \\n, then 
    @param content
        can only be given if no lines are given.
        if bytes, it is written as-is.
        if str, it is encoded as utf-8, then written.
    """
    if path[:1] != '/':
        raise RuntimeError(f"path is not absolute: {path!r}")

    if content is not None:
        if lines:
            raise RuntimeError("'content' and 'lines' cannot both be given")
        if isinstance(content, str):
            content = content.encode('utf-8')
    else:
        def prepare_line(line):
            """ encodes to bytes if needed, and appends \\n if needed. """
            if isinstance(line, str):
                line = line.encode('utf-8')
            if not line.endswith(b'\n'):
                line = line + b'\n'
            return line
        content = b''.join(prepare_line(line) for line in lines)

    if append:
        mode = 'ab'
    else:
        mode = 'wb'

    print('\x1b[33;1m' + mode + '\x1b[m ' + path)
    with open(cfg.path.initrd + path, mode) as fileobj:
        fileobj.write(content)


def mount_tmpfs(dirname):
    """
    Creates a directory (if not exists),
    and mounts a tmpfs there (if not mounted).

    To ensure that you get a fresh tmpfs,
    call `umount()` first.
    """
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if not os.path.ismount(dirname):
        command(
            'mount',
            '-t',
            'tmpfs',
            'tmpfs',
            dirname
        )


def umount(dirname):
    """
    Unmounts the filesystem at the dirname (if mounted).
    """
    while os.path.ismount(dirname):
        command('umount', dirname)


def list_files_in_packages(packages, nspawn):
    """
    lists all files that are installed by the given debian package.
    """
    if not packages:
        return
    queue = multiprocessing.Queue()

    def subprocess():
        try:
            os.chroot(nspawn)
            os.chdir('/')
            for package in packages:
                listing_path = f'/var/lib/dpkg/info/{package}.list'
                with open(listing_path, 'rb') as listing:
                    for filename in listing:
                        if filename[-1:] != b'\n' or filename[:1] != b'/':
                            raise RuntimeError(f'bad line {filename!r}')
                        filename = filename[:-1]
                        if not os.path.isdir(filename):
                            queue.put(os.path.realpath(filename)[1:])
        except BaseException:
            traceback.print_exc()
        finally:
            queue.put(StopIteration)

    proc = multiprocessing.Process(target=subprocess, args=())
    proc.start()
    while True:
        entry = queue.get()
        if entry is StopIteration:
            break
        yield entry
    proc.join()


class FileEditor:
    """
    allows loading, modifying and writing text files.
    nicely asks for confirmation before writing.

    It also creates the parent folder, if required.

    Constructor arguments:

    @param write_to
        the filename to where the data will be written
    """
    def __init__(self, write_to, executable=False):
        self.data = None
        self.write_to = write_to
        self.executable = executable

    def load(self):
        """ loads data from the output file """
        self.load_from(self.write_to)

    def load_from(self, filename):
        """
        loads data from some file
        """
        with open(filename, 'rb') as fileobj:
            self.data = fileobj.read()

    def write(self):
        """
        Writes the data, after showing the diff that will be written and
        asking for permission.
        """
        parentdir = os.path.dirname(self.write_to)
        if not os.path.exists(parentdir):
            warn(f'creating directory {parentdir}')
            if not get_consent():
                return
            os.makedirs(parentdir)

        if os.path.exists(self.write_to):
            # the file will be overwritten
            proc = subprocess.Popen(
                ['diff', '--color', '-u', self.write_to, '-'],
                stdin=subprocess.PIPE
            )
            proc.communicate(self.data)
            if proc.returncode == 0:
                # nothing to do
                print(f'{self.write_to!r}: unchanged')
                self.ensure_x_flag(need_consent=True)
                return

            backup_to = self.write_to + '-stiefelbup'
            warn(f'{self.write_to!r}: overwriting; backing up old version to {backup_to!r}')
            if os.path.exists(backup_to):
                warn('existing backup will be overwritten')
        else:
            # the file will be newly created
            warn(f'creating file {self.write_to!r}')
            backup_to = None

        if not get_consent():
            return

        if backup_to is not None:
            os.rename(self.write_to, backup_to)

        with open(self.write_to, 'wb') as fileobj:
            fileobj.write(self.data)

        self.ensure_x_flag(need_consent=False)

    def ensure_x_flag(self, need_consent):
        if self.executable != os.access(self.write_to, os.X_OK):
            if self.executable:
                if need_consent:
                    warn(f'chmod +x {self.write_to!r}')
                    if not get_consent():
                        return
                command('chmod', '+x', self.write_to)
            else:
                if need_consent:
                    warn(f'chmod -x {self.write_to!r}')
                    if not get_consent():
                        return
                command('chmod', '-x', self.write_to)

    def edit_bash_list(self, varname, entries):
        """
        edits a bash list by modifying entries as specified.

        entries is a dictionary of {entry: action} where entry
        is any string that could be found in a bash list, while
        action is one of:
            'at-end': add at the end of the list
            'before-X': add before the entry 'X'
            'remove': remove this entry

        e.g. for
        self.data='HOOKS=(a b c d)'
        varname='HOOKS'
        entries={'f': 'at-end', 'e': 'before-d', 'a': 'remove'}
        will result in
        self.data='HOOKS=(b c e d f)
        """
        # load the bash list
        match = re.search(fr'\n{varname}=\((.*?)\)'.encode(), self.data)
        if match is None:
            raise RuntimeError(
                f'{self.write_to!r}: '
                f'cannot find {varname!r} definition'
            )
        start, end = match.span(1)
        current = shlex.split(self.data[start:end].decode())

        for entry, action in entries.items():
            if action == 'remove':
                try:
                    current.remove(entry)
                except ValueError:
                    pass
            elif action == 'at-end':
                if entry not in current:
                    current.append(entry)
            elif action.startswith('before-'):
                try:
                    current.insert(current.index(action[7:]), entry)
                except ValueError:
                    raise RuntimeError(
                        f'{self.write_to!r}: '
                        f'cannot find {action[7:]!r} in {varname!r}'
                    ) from None
            else:
                raise RuntimeError(
                    f'{self.write_to!r}: '
                    f'unknown action {action!r}'
                )

        def quote(entry):
            """
            we can't use shlex.quote because it would over-quote
            backtick expressions like `which ifrename`.
            this is not perfect but it should be good enough.
            """
            if ' ' in entry:
                return f'"{entry}"'
            else:
                return entry
        section = ' '.join(quote(entry) for entry in current).encode()
        self.data = self.data[:start] + section + self.data[end:]

    def add_or_edit_var(self, varname, value, add_prefix=''):
        """
        edits or creates a bash variable assignment such as foo="asdf"
        """
        match = re.search(fr'\n{varname}="(.*?)"'.encode(), self.data)
        if match is None:
            # doesn't exist yet
            self.data += f'{add_prefix}{varname}="{value}"\n'.encode()
        else:
            # exists already; just swap out the matched group
            start, end = match.span(1)
            self.data = self.data[:start] + value.encode() + self.data[end:]

    def set_data(self, data):
        """
        sets content directly (instead of loading it from a file)
        """
        self.data = data


def install_folder(source, dest="/"):
    """
    install the folder at 'source' to 'dest'.
    symlinks are not supported.
    consent is acquired for each step.
    """
    if not os.path.isdir(dest):
        warn(f'creating directory {dest}')
        if get_consent():
            os.makedirs(dest, exist_ok=True)
        else:
            print(f'skipping install of {source!r} to {dest!r}')
            return
        
    for entry in os.listdir(source):
        source_path = os.path.join(source, entry)
        dest_path = os.path.join(dest, entry)

        if os.path.isdir(source_path):
            # recurse
            install_folder(source_path, dest_path)
        else:
            # use the FileEditor to install the file, this will take care of
            # printing diffs and asking for permission and so on
            editor = FileEditor(dest_path, os.access(source_path, os.X_OK))
            editor.load_from(source_path)
            editor.write()


def ensure_unit_enabled(name):
    """
    Checks that the given systemd unit is enabled.
    If not, enables it (after asking for confirmation).
    """
    if command('systemctl', 'is-enabled', name, get_retval=True) != 0:
        command('systemctl', 'enable', name, confirm=True)


def download(url, timeout=20):
    """
    Downloads data from this URL, returns a bytes object
    """
    print(f"downloading {url}")
    return urllib.request.urlopen(url, timeout=timeout).read()


def download_tar(url, target_dir, timeout=20):
    """
    Downlaods tar file from the URL, and extracts it to target_dir.

    Will only accept tar files that have a subfolder that contains all entries.
    The files from that subfolder are extracted directly into target_dir.

    Returns the name of that subfolder.
    """
    tar_blob = download(url, timeout)
    tar_fileobj = io.BytesIO(tar_blob)
    tar = tarfile.open(fileobj=tar_fileobj)
    prefix = tar.getnames()[0]
    for name in tar.getnames():
        normpath = os.path.normpath(name)
        if normpath.startswith('/') or normpath.startswith('..'):
            raise RuntimeError("bad TAR file (has files outside '.')")
        if os.path.relpath(normpath, prefix).startswith('..'):
            raise RuntimeError("bad TAR file (has no common prefix)")

    # perform extraction
    os.makedirs(target_dir, exist_ok=True)
    for entry in tar:
        target = os.path.join(target_dir, os.path.relpath(entry.name, prefix))
        print(f'tar: extracting {os.path.normpath(target)}')

        if entry.isdir():
            os.makedirs(target, exist_ok=True)
        elif entry.isfile():
            with tar.extractfile(entry) as fileobj:
                blob = fileobj.read()
            with open(target, 'wb') as fileobj:
                fileobj.write(blob)
            os.chmod(target, entry.mode)
        else:
            raise RuntimeError("unsupported entry type")

    return prefix


def install_binary(rootpath, binarypath):
    """
    install the given binary into the rootpath
    under /bin/binaryname,
    including all dependent libraries
    """

    if not isinstance(rootpath, pathlib.Path):
        rootpath = pathlib.Path(rootpath)

    copy_symlink_chain(rootpath, binarypath)
    deps = command('ldd', binarypath, capture_stdout=True).decode()

    for dep in deps.split("\n"):
        dep = dep.strip()
        if not dep:
            continue

        if dep.startswith("linux-vdso.so"):
            # no need to store the vdso :)
            continue

        if '=>' in dep:
            # '\tlibreadline.so.8 => /lib64/libreadline.so.8 (0x00007f83fa5ab000)\n'
            dep_path = dep.split("=>")[1].split()[0]
        else:
            dep_path = dep.split()[0]

        copy_symlink_chain(rootpath, dep_path)


def copy_symlink_chain(rootpath, file_path):
    """
    copy a file from the current root to the given new rootpath.
    copy all symlinks on the way until we reach a real file.
    """

    file_path = pathlib.Path(file_path)
    file_path_dest = rootpath / file_path.relative_to('/')

    while True:
        if not (file_path.exists() or file_path.is_symlink()):
            raise FileNotFoundError(str(file_path))

        if file_path_dest.exists() or file_path_dest.is_symlink():
            file_path_dest.unlink()

        file_path_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, file_path_dest, follow_symlinks=False)

        if file_path.is_symlink():
            # if is symlink, try again with its destination
            file_path_ln = file_path.parent / pathlib.Path(os.readlink(file_path))
            file_path_dest = rootpath / file_path_ln.relative_to('/')
            file_path = file_path_ln

        elif file_path.exists():
            # real file, so we're done
            break

        else:
            raise Exception(f"wtf {file_path} no symlink and doesn't exist")
            # else, copy the file and that's it
