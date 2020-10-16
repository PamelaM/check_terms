"""Console script for check_terms."""
import sys
import multiprocessing

import click

from .check_terms import check_terms


def get_filepaths_from_args(file_paths):
    get_from_stdin = False
    for path in file_paths:
        if path == '-':
            get_from_stdin = True
        else:
            yield path

    if get_from_stdin:
        for line in sys.stdin.readlines():
            if line:
                yield line.strip()


@click.command()
@click.option('--verbose', is_flag=True, help='Be verbose')
@click.option('--no-term-allowed', default=False, help="Don't ignore lines with '# term-allowed'")
@click.option('--ignore-allowed-db', default=False, help="Do not use the allowed-lines db")
@click.argument('files', nargs=-1, type=click.Path())
def main(verbose, no_term_allowed, ignore_allowed_db, files):
    """Console script for check_terms."""
    file_paths = get_filepaths_from_args(files)
    num_found = check_terms(file_paths, ignore_allowed_db, no_term_allowed, verbose)
    return 1 if num_found else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('fork')

    sys.exit(main())  # pragma: no cover
