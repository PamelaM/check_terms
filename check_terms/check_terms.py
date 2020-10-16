#!/usr/bin/env python3

import functools
import subprocess
import os
import logging
import multiprocessing

import time
from collections import defaultdict

from multiprocessing_logging import install_mp_handler

from .block_db import load_blocked_db, should_block
from .utils import ProgressTracker


IGNORE_TERM_ALLOWED = False
IGNORE_ALLOWED_DB = False

class AllowedDB:
    def __init__(self, db_file_name):
        self.db_file_name = db_file_name
        self.db = defaultdict(lambda : defaultdict(set))
        if os.path.exists(db_file_name):
            logging.info(f"Reading allowed db {db_file_name}")
            with open(db_file_name) as f:
                try:
                    line = None
                    for line in f:
                        line = line.strip()
                        if line.startswith("PROBLEM:"):
                            line = line.replace("PROBLEM:", '', 1).strip()
                        if line:
                            self.add_line_to_db(line)
                except Exception as e:
                    logging.error(e)
                    logging.error(repr(line))
                    raise
        else:
            logging.error(f"Allowed db file {db_file_name} not found")

        num_lines = len(self.db)
        files = set(file_path for file_paths in self.db.values() for file_path in file_paths)
        num_files = len(files)
        logging.info(f"Found {num_lines} allowed lines across {num_files} files")

    def add_line_to_db(self, line):
        file_path, line_no, line_text = self._split_line(line)
        self.db[line_text][file_path].add(int(line_no))

    def find_line_in_db(self, line):
        file_path, line_no, line_text = self._split_line(line)
        return int(line_no) in self.db.get(line_text, {}).get(file_path, set())

    def _split_line(self, line):
        return  line.rstrip().split(":", 2)


def get_cmd_output(cmd):
    try:
        start = time.time()
        logging.debug(f"COMMAND: {cmd}")
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

        n_lines = n_errors = 0
        if result.stdout:
            for line in result.stdout.decode("utf-8").splitlines():
                n_lines += 1
                yield line.strip()

        if result.stderr:
            for line in result.stderr.decode("utf-8").splitlines():
                line = line.strip()
                if line:
                    n_errors += 1
                    logging.debug(line[:150])
        elapsed = time.time() - start
        if elapsed > 5.0:
            logging.debug("LONG RUNNING:", f"{elapsed:4.2f} seconds", cmd)
    except subprocess.TimeoutExpired as e:
        logging.debug("TIMEOUT EXPIRED:", str(e), cmd)
        return
    except BaseException as e:
        logging.error(f"ERROR: {e}, {cmd}")
        raise


def check_path(terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern, path):
    # -- Use array rather than yield because this data gets passed via multiprocessing mechanisms
    found_lines = []
    line_skip_pat = '^egrep: |^Binary file |term-allowed|"image/png":'
    if no_term_allowed:
        line_skip_pat = line_skip_pat.replace("term-allowed|", '', 1)
    dir_suffix = "/*" if os.path.isdir(path) else ""
    cmd = f"egrep -iHn '{terms_pattern}' '{path}'{dir_suffix} | egrep -v '{line_skip_pat}'"
    for line in get_cmd_output(cmd):
        if not line:
            continue
        if len(line) > 1000:
            logging.warning(f"LINE TOO LONG: {len(line)} {line[:100]}")
            continue

        if should_block(line, exclusion_patterns, non_excluded_pattern):
            logging.debug(f"BLOCKED: {line[:100]}")
            found_lines.append(line)
        else:
            logging.debug(f"NOT BLOCKED: {line[:100]}")
    return found_lines


def find_term_lines(paths, terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern):
    with multiprocessing.Pool(None) as pool:
        check_path_partial = functools.partial(check_path, terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern)
        for found_lines in pool.imap_unordered(check_path_partial, paths, chunksize=1):
            yield None
            yield from found_lines

def find_term_lines_with_progress(paths, terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern):
    progress = ProgressTracker("paths", "lines")
    for line in find_term_lines(paths, terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern):
        if line == None:
            progress.increment("paths")
        else:
            progress.increment("lines")
            yield line
        progress.message()
    progress.end()

def check_terms(file_paths, ignore_allowed_db, no_term_allowed, verbose=False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format='%(process)5d  %(relativeCreated)7d  %(levelname)6s: %(message)s',
    )
    install_mp_handler()
    terms_pattern, exclusion_patterns, non_excluded_pattern = load_blocked_db(".check_terms.cfg")
    line_skip_pat = '^egrep: |^Binary file |term-allowed|"image/png":'
    if no_term_allowed:
        line_skip_pat = line_skip_pat.replace("term-allowed|", '', 1)

    allowed_db = AllowedDB(".check_terms-allowed.txt")
    num_found = 0
    for line in find_term_lines_with_progress(file_paths, terms_pattern, no_term_allowed, exclusion_patterns, non_excluded_pattern):
        if ignore_allowed_db or not allowed_db.find_line_in_db(line):
            print("PROBLEM:", line)
            num_found += 1
    return num_found


