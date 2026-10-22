"""Git's clean filter without the asset-cache side effect of ``git lfs clean``.

Registered render checkouts already contain usable assets whose LFS cache may
have been pruned. Comparing those files must not silently recreate that cache.
The process protocol keeps one Python process alive for the whole comparison.
Smudging deliberately preserves pointers, as registered sync hydrates explicitly.
"""

import hashlib
import re
import sys


_POINTER = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\n"
    rb"(?:ext-[^\n]+\n)*oid sha256:[0-9a-f]{64}\nsize [0-9]+\n?\Z"
)


def pointer_for_chunks(chunks):
    digest = hashlib.sha256()
    size = 0
    prefix = bytearray()
    for chunk in chunks:
        digest.update(chunk)
        size += len(chunk)
        if len(prefix) < 1024:
            prefix.extend(chunk[:1024 - len(prefix)])
    if size <= 1024 and _POINTER.fullmatch(bytes(prefix)):
        return bytes(prefix)
    return (f"version https://git-lfs.github.com/spec/v1\n"
            f"oid sha256:{digest.hexdigest()}\nsize {size}\n").encode("ascii")


def _read_packet(stream):
    header = stream.read(4)
    if not header:
        raise EOFError
    if len(header) != 4:
        raise ValueError("Incomplete Git filter packet")
    size = int(header, 16)
    if size == 0:
        return None
    if size < 4:
        raise ValueError("Unsupported Git filter packet")
    result = stream.read(size - 4)
    if len(result) != size - 4:
        raise ValueError("Incomplete Git filter payload")
    return result


def _packets(stream):
    while True:
        packet = _read_packet(stream)
        if packet is None:
            return
        yield packet


def _write_packets(stream, chunks):
    for chunk in chunks:
        for offset in range(0, len(chunk), 65516):
            data = chunk[offset:offset + 65516]
            stream.write(f"{len(data) + 4:04x}".encode("ascii") + data)
    stream.write(b"0000")


def process_filter(source, output):
    if list(_packets(source)) != [b"git-filter-client\n", b"version=2\n"]:
        raise ValueError("Unsupported Git filter handshake")
    _write_packets(output, [b"git-filter-server\n", b"version=2\n"])
    output.flush()
    list(_packets(source))
    _write_packets(output, [b"capability=clean\n", b"capability=smudge\n"])
    output.flush()
    while True:
        try:
            headers = list(_packets(source))
        except EOFError:
            return
        command = next((line for line in headers if line.startswith(b"command=")), b"")
        if command == b"command=clean\n":
            content = [pointer_for_chunks(_packets(source))]
        elif command == b"command=smudge\n":
            # Registered sync sets GIT_LFS_SKIP_SMUDGE: retain pointer content.
            content = list(_packets(source))
        else:
            raise ValueError("Unsupported Git filter operation")
        _write_packets(output, [b"status=success\n"])
        _write_packets(output, content)
        _write_packets(output, [])
        output.flush()


if __name__ == "__main__":
    if "--process" in sys.argv:
        process_filter(sys.stdin.buffer, sys.stdout.buffer)
    else:
        sys.stdout.buffer.write(pointer_for_chunks(iter(lambda: sys.stdin.buffer.read(1024 * 1024), b"")))
