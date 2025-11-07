"""Create random files."""

from __future__ import annotations

import argparse
import os
import re
import textwrap
import uuid
from dataclasses import dataclass, field
from enum import Enum, EnumMeta
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import io

PREFIX_STEP_SIZE = 1024

DEFAULT_CHUNK_SIZE_BYTES = 256 * (PREFIX_STEP_SIZE**2)  # 256 MiB
DEFAULT_FILE_SIZE_BYTES = PREFIX_STEP_SIZE**2  # 1 MiB
DEFAULT_NUMBER_OF_FILES = 1
DEFAULT_OUTPUT_DIRECTORY = PurePath("out")


BYTE_RE = re.compile(r"^((?:[0-9]*.)?[0-9]+)([KMGTP]i?)?B$")


_decimal_prefix_length: int = 1
_binary_prefix_length: int = 2
_string_representation_group_count: int = 2


def d(_v: str, /) -> str:
    """Quick dedent.strip."""
    return textwrap.dedent(_v).strip()


class _UnitMeta(EnumMeta):
    """Metaclass for unit Enums."""

    def __call__(cls, value: str | int) -> Enum:
        return cls[value]

    def __getitem__(cls, value: str | int) -> Enum:
        is_int = isinstance(value, int)
        for member in cls._member_map_.values():
            mv = member.value
            if (is_int and mv.power == value) or (not is_int and mv.prefix == value):
                return member
        raise KeyError


@dataclass(frozen=True)
class _Unit:
    prefix: str


@dataclass(frozen=True)
class ByteUnit(_Unit):
    """Base unit definition."""

    power: int
    base: int = field(kw_only=True)
    byte_count: int = field(init=False)

    def __post_init__(self, *_: ..., **__: ...) -> None:
        """Populate the byte_count field."""
        object.__setattr__(self, "byte_count", self.base**self.power)

    def to_str(self, _b: int, /, places: int = 3) -> str:
        """Convert byte count _b, with this prefix, to a human-readable string."""
        power_count = 0
        rem = _b
        frac = 0.0
        while rem > self.base:
            frac = (rem / self.base) % 1
            rem //= self.base
            power_count += 1

        if (10**places * frac) % 1 > 0:
            rem = rem + frac
            out = f"{rem:.{places}f}{self.prefix}B"
        else:
            out = f"{rem}{self.prefix}B"

        return out


BYTE = ByteUnit("B", 0, base=1)


@dataclass(frozen=True)
class DecimalByteUnit(ByteUnit):
    """Decimal unit definition, base 1000."""

    base: int = field(init=False, default=1000)

    def __post_init__(self, *args: ..., **kwargs: ...) -> None:
        """Passthrough."""
        super().__post_init__(*args, **kwargs)


@dataclass(frozen=True)
class BinaryByteUnit(ByteUnit):
    """Binary unit definition, base 1024."""

    base: int = field(init=False, default=1024)

    def __post_init__(self, *args: ..., **kwargs: ...) -> None:
        """Passthrough."""
        super().__post_init__(*args, **kwargs)


class BytePrefix(Enum, metaclass=_UnitMeta):
    """Unit prefix enumeration."""

    def __new__(cls, data: ByteUnit) -> Self:
        """Create new object.

        Syntactic sugar to make _UnitMeta happy.
        """
        obj = object.__new__(cls)
        obj._value_ = data
        return obj

    def __init__(self, data: ByteUnit) -> None:
        """Initialize new object.

        Syntactic sugar to make static type checker happy, so we can reuse the
        same base 1 byte definition.
        """
        for key in data.__annotations__:
            value = getattr(data, key)
            object.__setattr__(self, key, value)

    @classmethod
    def from_str(cls, _v: str, /) -> Self:
        """Convert a string to a prefix instance."""
        if len(_v) == _decimal_prefix_length:
            prefix = DecimalBytePrefix(_v)
        elif len(_v) == _binary_prefix_length:
            prefix = BinaryBytePrefix(_v)
        else:
            raise ValueError
        return prefix  # type: ignore[reportReturnType]


class DecimalBytePrefix(BytePrefix):
    """Decimal prefixes."""

    B = BYTE
    K = DecimalByteUnit("K", 1)
    M = DecimalByteUnit("M", 2)
    G = DecimalByteUnit("G", 3)
    T = DecimalByteUnit("T", 4)
    P = DecimalByteUnit("P", 5)


class BinaryBytePrefix(BytePrefix):
    """Decimal prefixes."""

    B = BYTE
    Ki = BinaryByteUnit("Ki", 1)
    Mi = BinaryByteUnit("Mi", 2)
    Gi = BinaryByteUnit("Gi", 3)
    Ti = BinaryByteUnit("Ti", 4)
    Pi = BinaryByteUnit("Pi", 5)


@dataclass(frozen=True)
class Byte:
    """Class representing a quantity of bytes."""

    byte_count: int
    prefix: BytePrefix = field(default=BinaryBytePrefix.B)

    def __str__(self) -> str:
        """Return human-readable string."""
        return self.prefix.value.to_str(self.byte_count)

    def __int__(self) -> int:
        """Return number of bytes."""
        return self.byte_count

    def to_prefix(self, prefix: BytePrefix) -> Byte:
        """Convert to the supplied prefix."""
        return Byte(self.byte_count, prefix)

    @classmethod
    def from_str(cls, _v: str, /) -> Self:
        """Create from supplied string representation."""
        match = BYTE_RE.fullmatch(_v)
        if match is None:
            raise ValueError

        groups = match.groups()
        if len(groups) != _string_representation_group_count:
            raise ValueError

        mantissa = float(groups[0])
        if mantissa < 0:
            raise ValueError

        prefix = BytePrefix.from_str(groups[1])
        byte_count = round(mantissa * prefix.value.byte_count)
        return cls(byte_count, prefix)

    @classmethod
    def decimal_from_byte_count(cls, _v: int, /) -> Self:
        """Create a DecimalBytePrefix Byte instance from a byte count."""
        return cls._from_byte_count(DecimalBytePrefix, DecimalByteUnit.base, _v)

    @classmethod
    def binary_from_byte_count(cls, _v: int, /) -> Self:
        """Create a BinaryBytePrefix Byte instance from a byte count."""
        return cls._from_byte_count(BinaryBytePrefix, BinaryByteUnit.base, _v)

    @classmethod
    def _from_byte_count(cls, _t: type[BytePrefix], _base: int, _v: int, /) -> Self:
        power_count = 0
        rem = float(_v)
        while rem > _base:
            rem /= _base
            power_count += 1
        return cls(_v, _t(power_count))


def create_files(
    number_of_files: int,
    chunk_size: int,
    byte_count_total: int,
    output_directory: PurePath,
) -> None:
    """Create many randomly named files with random bytes.

    - number_of_files: how many files to create
    - chunk_size: how many bytes to write at once
    - total_byte_count: how many total bytes to write per file
    - output_directory: where to create
    """
    for _ in range(number_of_files):
        file_name: str = str(uuid.uuid4())
        file_path = output_directory / file_name
        with Path(file_path).open("wb") as f:
            write_bytes(
                chunk_size=chunk_size,
                total_byte_count=byte_count_total,
                f=f,
            )


def write_bytes(
    chunk_size: int,
    total_byte_count: int,
    f: io.BufferedWriter,
) -> None:
    """Create a file filled with random bytes.

    - chunk_size: how many bytes to write at once
    - total_byte_count: how many total bytes to write
    - f: where to write
    """
    remaining_byte_count: int = total_byte_count
    while remaining_byte_count > 0:
        chunk_byte_count = min(remaining_byte_count, chunk_size)
        remaining_byte_count -= chunk_byte_count

        chunk_bytes = os.urandom(chunk_byte_count)
        f.write(chunk_bytes)


def _main_interface() -> None:
    _chunk_size_bytes_arg = "chunk_size_bytes"
    _number_of_files_arg = "number_of_files"
    _file_size_bytes_arg = "file_size_bytes"
    _output_directory_arg = "output_directory"

    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Utility to rapidly create files containing random data. Writes files
            using chunks to ensure memory efficiency. To increase speed, use a
            larger value of `--chunk_size_bytes` than the default. One chunk is
            written at a time, so one chunk must fit into available memory on
            your machine or the program will fail.

            Potential use cases include:
                - Internet/network transfer speed testing
                - Disk I/O speed testing

            Examples:
                1000 files , 1  MiB each: `python -m create -n=1000 -f=1MiB`
                   1 file  , 10 GiB     : `python -m create -f=10GiB`
            """,
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    default_chunk_size_bytes = Byte.binary_from_byte_count(DEFAULT_CHUNK_SIZE_BYTES)
    parser.add_argument(
        "-c",
        _arg(_chunk_size_bytes_arg),
        metavar="CHUNK_BYTES",
        help=d(
            f"""
            Number of bytes per chunk to write to each file.
            Default: {default_chunk_size_bytes}
            """,
        ),
        type=Byte.from_str,
        nargs="?",
        default=default_chunk_size_bytes,
    )

    default_file_size_bytes = Byte.binary_from_byte_count(DEFAULT_FILE_SIZE_BYTES)
    parser.add_argument(
        "-f",
        _arg(_file_size_bytes_arg),
        metavar="FILE_BYTES",
        help=d(
            f"""
            Number of bytes to write to each file.
            Default: {default_file_size_bytes}
            """,
        ),
        type=Byte.from_str,
        nargs="?",
        default=default_file_size_bytes,
    )
    parser.add_argument(
        "-n",
        _arg(_number_of_files_arg),
        metavar="N",
        help=d(
            f"""
            Number of files to create.
            Default: {DEFAULT_NUMBER_OF_FILES}
            """,
        ),
        type=int,
        nargs="?",
        default=DEFAULT_NUMBER_OF_FILES,
    )
    parser.add_argument(
        "-o",
        _arg(_output_directory_arg),
        metavar="PATH",
        help=d(
            f"""
            Where to create the files.
            Default: {_to_relative_path_for_display(DEFAULT_OUTPUT_DIRECTORY)}
            """,
        ),
        type=PurePath,
        nargs="?",
        default=DEFAULT_OUTPUT_DIRECTORY,
    )

    args = vars(parser.parse_args())

    number_of_files: int = args[_number_of_files_arg]
    if number_of_files == 0:
        return
    if number_of_files < 0:
        msg = f"{_number_of_files_arg} must be non-negative."
        raise ValueError(msg)

    chunk_size: Byte = args[_chunk_size_bytes_arg]
    if int(chunk_size) <= 0:
        msg = f"{_chunk_size_bytes_arg} must be positive."
        raise ValueError(msg)

    byte_count_total: Byte = args[_file_size_bytes_arg]
    if int(byte_count_total) <= 0:
        msg = f"{_file_size_bytes_arg} must be positive."
        raise ValueError(msg)

    output_directory: PurePath = args[_output_directory_arg]
    Path(output_directory).mkdir(parents=True, exist_ok=True)

    create_files(
        number_of_files=number_of_files,
        chunk_size=int(chunk_size),
        byte_count_total=int(byte_count_total),
        output_directory=output_directory,
    )


def _arg(s: str) -> str:
    return "--" + s


def _to_relative_path_for_display(p: PurePath) -> str:
    return str(PurePath() / p)


if __name__ == "__main__":
    _main_interface()
