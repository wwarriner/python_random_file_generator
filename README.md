# Random File Generator

Generates randomly named files with bitwise random content using Python.

Utility to rapidly create files containing random data. Writes files using chunks to ensure memory efficiency. To increase speed, use a larger value of `--chunk_size_bytes` than the default. One chunk is written at a time, so one chunk must fit into available memory on your machine or the program will fail.

Potential use cases include:
    - Internet/network transfer speed testing
    - Disk I/O speed testing

Examples:
    - 1000 files , 1 MiB each: `python -m create -n=1000 -f=1024`
    - 1 file, 10 GiB: `python -m create -f=1024`
