import argparse
import io
import os.path as osp
import textwrap
import uuid
from pathlib import Path, PurePath
from typing import Union

import numpy as np

PREFIX_STEP_SIZE = 1024

DEFAULT_CHUNK_SIZE_BYTES = 256 * (PREFIX_STEP_SIZE ** 2)  # 256 MiB
DEFAULT_FILE_SIZE_BYTES = PREFIX_STEP_SIZE ** 2  # 1 MiB
DEFAULT_NUMBER_OF_FILES = 1
DEFAULT_OUTPUT_DIRECTORY = PurePath(".") / "out"


class Byte:
    DECIMAL_UNIT_BASE = 1000
    DECIMAL_UNIT_POWERS = {
        "K": 1,
        "M": 2,
        "G": 3,
        "T": 4,
        "P": 5,
    }

    BINARY_UNIT_BASE = 1024
    BINARY_UNIT_POWERS = {
        "Ki": 1,
        "Mi": 2,
        "Gi": 3,
        "Ti": 4,
        "Pi": 5,
    }

    BINARY_UNITS = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB", 5: "PiB"}

    def __init__(self, rep: Union[int, str]) -> None:
        if isinstance(rep, int):
            assert 0 <= rep
            value = rep
        elif isinstance(rep, str):
            value = self._str_to_int(rep=rep)
        else:
            assert False

        self._byte_count: int = value

    def __int__(self) -> int:
        return self._byte_count

    def __str__(self) -> str:
        power_count = 0
        rem = self._byte_count
        frac = 0.0
        while 1024 < rem:
            frac = (rem / 1024) % 1
            rem //= 1024
            power_count += 1

        suffix = self.BINARY_UNITS[power_count] + "B"
        if 0 < (100 * frac) % 1:
            rem = rem + frac
            out = f"{rem:.2f}{suffix}"
        else:
            out = f"{rem}{suffix}"

        return out

    @staticmethod
    def valid_units_to_string() -> str:
        decimal = ", ".join(Byte.DECIMAL_UNIT_POWERS.keys())
        binary = ", ".join(Byte.BINARY_UNIT_POWERS.keys())
        return f"Decimal units are {decimal}. Binary units are {binary}."

    @staticmethod
    def _str_to_int(rep: str) -> int:
        parts = rep.split()
        parts = [p.strip() for p in parts]
        rep = "".join(parts)

        B = rep[-1]
        if B.isalpha() and B != "B":
            raise RuntimeError(
                f"{rep} must end with decimal or binary byte units. {Byte.valid_units_to_string()}"
            )
        elif B.isnumeric():
            return int(rep)

        binary_prefix_try = rep[-3]
        if binary_prefix_try.isalpha():
            prefix = rep[-3:-1]
            base = Byte.BINARY_UNIT_BASE
            try:
                power = Byte.BINARY_UNIT_POWERS[prefix]
            except:
                raise RuntimeError(
                    f"{rep} must end with decimal or binary byte units. {Byte.valid_units_to_string()}"
                )
            coefficient = int(rep[:-3])
        else:
            prefix = rep[-2]
            base = Byte.DECIMAL_UNIT_BASE
            try:
                power = Byte.DECIMAL_UNIT_POWERS[prefix]
            except:
                raise RuntimeError(
                    f"{rep} must end with decimal or binary byte units. {Byte.valid_units_to_string()}"
                )
            coefficient = int(rep[:-2])

        return coefficient * (base ** power)


def create_files(
    number_of_files: int,
    chunk_size: int,
    byte_count_total: int,
    output_directory: PurePath,
) -> None:
    for _ in range(number_of_files):
        file_name: str = str(uuid.uuid4())
        file_path = output_directory / file_name
        with open(file_path, "wb") as f:
            create_file(
                chunk_size=chunk_size, byte_count_total_to_write=byte_count_total, f=f
            )


def create_file(
    chunk_size: int, byte_count_total_to_write: int, f: io.BufferedWriter
) -> None:
    byte_count_remaining_to_write: int = byte_count_total_to_write

    while 0 < byte_count_remaining_to_write:
        byte_count_chunk_to_write = min(byte_count_remaining_to_write, chunk_size)
        byte_count_remaining_to_write -= byte_count_chunk_to_write

        byte_chunk_data = np.random.bytes(byte_count_chunk_to_write)
        f.write(byte_chunk_data)  # type: ignore


def _main_interface() -> None:
    CHUNK_SIZE_BYTES = "chunk_size_bytes"
    NUMBER_OF_FILES = "number_of_files"
    FILE_SIZE_BYTES = "file_size_bytes"
    OUTPUT_DIRECTORY = "output_directory"

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
                1000 files , 1 MiB each: `python -m create -n=1000 -f=1024`
                   1 file  , 10 GiB     : `python -m create -f=1024`
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c",
        _arg(CHUNK_SIZE_BYTES),
        metavar="CHUNK_BYTES",
        help=f"Number of bytes per chunk to write to each file.\nDefault: {Byte(DEFAULT_CHUNK_SIZE_BYTES)}",
        type=int,
        nargs="?",
        default=DEFAULT_CHUNK_SIZE_BYTES,
    )
    parser.add_argument(
        "-f",
        _arg(FILE_SIZE_BYTES),
        metavar="FILE_BYTES",
        help=f"Number of bytes to write to each file.\nDefault: {Byte(DEFAULT_FILE_SIZE_BYTES)}",
        type=Byte,
        nargs="?",
        default=DEFAULT_FILE_SIZE_BYTES,
    )
    parser.add_argument(
        "-n",
        _arg(NUMBER_OF_FILES),
        metavar="N",
        help=f"Number of files to create.\nDefault: {DEFAULT_NUMBER_OF_FILES}",
        type=Byte,
        nargs="?",
        default=DEFAULT_NUMBER_OF_FILES,
    )
    parser.add_argument(
        "-o",
        _arg(OUTPUT_DIRECTORY),
        metavar="PATH",
        help=f"Where to create the files.\nDefault: {_to_relative_path_for_display(DEFAULT_OUTPUT_DIRECTORY)}",
        type=PurePath,
        nargs="?",
        default=DEFAULT_OUTPUT_DIRECTORY,
    )

    args = vars(parser.parse_args())

    number_of_files: int = args[NUMBER_OF_FILES]
    if number_of_files == 0:
        return
    elif number_of_files < 0:
        raise RuntimeError(f"{NUMBER_OF_FILES} must be non-negative.")

    chunk_size: Byte = args[CHUNK_SIZE_BYTES]
    if int(chunk_size) <= 0:
        raise RuntimeError(f"{CHUNK_SIZE_BYTES} must be positive.")

    byte_count_total: Byte = args[FILE_SIZE_BYTES]
    if int(byte_count_total) <= 0:
        raise RuntimeError(f"{FILE_SIZE_BYTES} must be positive.")

    output_directory: PurePath = args[OUTPUT_DIRECTORY]
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
    return osp.join(".", p)


if __name__ == "__main__":
    _main_interface()
