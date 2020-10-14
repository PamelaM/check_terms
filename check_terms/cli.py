"""Console script for check_terms."""
import sys
import click
import check_terms.check_terms

def get_files(file_paths):
    for path in file_paths:
        if path == '-':
            for line in sys.stdin.readlines():
                if line:
                    yield line.strip()
        else:
            yield path

@click.command()
@click.option('--verbose', default=False, help='Be verbose')
@click.option('--no-term-allowed', default=False, help="Don't ignore lines with '# term-allowed'")
@click.option('--ignore-allowed-db', default=False, help="Do not use the allowed-lines db")
@click.argument('files', nargs=-1, type=click.Path())
def main(verbose, no_term_allowed, ignore_allowed_db, files):
    """Console script for check_terms."""
    click.echo(f"Verbose: {verbose}")
    click.echo(f"no_term_allowed: {no_term_allowed}")
    click.echo(f"ignore_allowed_db: {ignore_allowed_db}")

    check_terms.VERBOSE = verbose
    check_terms.IGNORE_TERM_ALLOWED = no_term_allowed
    check_terms.IGNORE_ALLOWED_DB = ignore_allowed_db
    check_terms.check_terms.check_terms(get_files(files))

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
