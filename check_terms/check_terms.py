#!/usr/bin/env python3


from collections import defaultdict
import subprocess
import os
import re
import time
import multiprocessing

DEFAULT_TERMS = """
master
slave
white?list
black?list
grandfather
dummy
stupid
"""
#sub :! subnet, substr, sub?set, subclass, subtest, submit, subscribe, subject, sub?process, mitsubishi, subcategory, subtotal, subpremise, submarket, subplot

message_lock = multiprocessing.Lock()

VERBOSE = False
IGNORE_TERM_ALLOWED = False
IGNORE_ALLOWED_DB = False

def message(*msg):
    global message_lock
    if VERBOSE:
        with message_lock:
            print(os.getpid(), *msg, file=sys.stderr, end='\n', flush=True)

class BlockedDB:
    def __init__(self, file_path):
        self.file_path = file_path
        self.terms_pattern = None
        self.terms = set()
        self.exclusion_patterns = []

        if not os.path.exists(file_path):
            message("Creating blocked db config file {}, using defaults".format(file_path))
            with open(file_path, 'w') as f:
                for term in DEFAULT_TERMS.strip().split('\n'):
                    print(term.strip(), file=f, end='\n')
        else:
            message("Reading existing blocked db config file {}".format(file_path))

        non_exclusion_terms = set()

        for term, exclusions in self._read_blocked_db(file_path):
            self.terms.add(term)
            if exclusions:
                check_pat = re.compile("(?=({}.*))".format(term), re.IGNORECASE)
                exclusions_re = ".*|".join(sorted(exclusions))
                exclusions_pat = re.compile("(?=({}.*))".format(exclusions_re), re.IGNORECASE)
                self.exclusion_patterns.append((check_pat, exclusions_pat))
            else:
                non_exclusion_terms.add(term)

        self.terms_pattern = "|".join(sorted(self.terms))
        if non_exclusion_terms:
            self.non_excluded_pat = re.compile("|".join(sorted(non_exclusion_terms)), re.IGNORECASE)
        else:
            self.non_excluded_pat = None

        message("Search Terms:", self.terms)
        message("Search Terms Pattern:", self.terms_pattern)
        message("Search Terms Without Exclusions:", non_exclusion_terms)
        message("Exclusions Patterns:", self.exclusion_patterns)

    def _read_blocked_db(self, file_path):
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                elif ' :! ' in line:
                    term, exclusions = line.split(" :! ", 1)
                    term = term.strip()
                    exclusions = set(exclusion.strip() for exclusion in exclusions.strip().split(',') if exclusion.strip())
                else:
                    term = line
                    exclusions = set()

                yield term, exclusions


    def should_block(self, line):
        # -- If there are no exclusion patterns, then the egrep command found a blockable match
        if not self.exclusion_patterns:
            return True

        # -- If there are exclusion patterns, check if any of the patterns without exclusions
        # match this line - if any do, this is also a blockable match
        if self.non_excluded_pat and self.non_excluded_pat.search(line):
            return True

        for check_pat, exclusions_pat in self.exclusion_patterns:
            found = [m.group(1) for m in check_pat.finditer(line)]
            if found:
                # -- Line term found
                excluded = [m.group(1) for m in exclusions_pat.finditer(line)]
                if found != excluded:
                    # -- All matches are NOT also exclusions, so this is a 'should block' line
                    return True
        return False


class AllowedDB:
    def __init__(self, db_file_name):
        self.db_file_name = db_file_name
        self.db = defaultdict(lambda : defaultdict(set))
        if os.path.exists(db_file_name):
            message("Reading allowed db {}".format(db_file_name))
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
                    message(e)
                    message(repr(line))
                    raise
        else:
            message("Allowed db file {} not found".format(db_file_name))

        num_lines = len(self.db)
        files = set(file_path for file_paths in self.db.values() for file_path in file_paths)
        num_files = len(files)
        message("Found {} allowed lines across {} files".format(num_lines, num_files))

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
                    #message(line[:150])
        elapsed = time.time() - start
        if elapsed > 5.0:
            message("LONG RUNNING:", "{:4.2f} seconds".format(elapsed), cmd)
    except subprocess.TimeoutExpired as e:
        message("TIMEOUT EXPIRED:", str(e), cmd)
        return
    except BaseException as e:
        message("ERROR:", str(e), cmd)
        raise


blocked_db = None

def check_path(path):
    # -- blocked_db is a global so that it's set up once before the worker nodes starts
    global blocked_db

    # -- Use array rather than yield because this data gets passed via multiprocessing mechanisms
    found_lines = []
    line_skip_pat = '^egrep: |^Binary file |term-allowed|"image/png":'
    if IGNORE_TERM_ALLOWED:
        line_skip_pat = line_skip_pat.replace("term-allowed|", '', 1)
    dir_suffix = "/*" if os.path.isdir(path) else ""
    cmd = "egrep -iHn '{}' '{}'{} | egrep -v '{}'".format(blocked_db.terms_pattern, path, dir_suffix, line_skip_pat)
    for line in get_cmd_output(cmd):
        if not line:
            continue
        if len(line) > 1000:
            message("LINE TOO LONG:",len(line), line[:100])
            continue

        if blocked_db.should_block(line):
            found_lines.append(line)
        else:
            pass # message("NOT BLOCKED:", line[:100])
    return found_lines


def find_term_lines(paths):
    import multiprocessing
    import time

    start_time = time.time()
    next_time = start_time + 1.0
    n_complete_since_last = 0
    tot_complete = 0
    tot_lines = 0

    def _progress_message(force=False):
        nonlocal next_time, n_complete_since_last, tot_lines
        if (force and n_complete_since_last) or time.time() >= next_time:
            secs = time.time()-start_time
            ave = tot_complete / secs
            message("Secs: {secs:6.1f},  Completed Since: {n_complete_since_last:3},  Total Completed: {tot_complete:5},  Ave Completed/Second: {ave:5.2f},  Total lines found: {tot_lines:6}".format(**locals()))
            next_time = time.time() + 1.0
            n_complete_since_last = 0

    with multiprocessing.Pool(4) as pool:

        for found_lines in pool.imap_unordered(check_path, paths, chunksize=1):
            tot_complete += 1
            n_complete_since_last += 1
            for line in found_lines:
                tot_lines += 1
                yield line
            _progress_message()

        _progress_message(force=True)


def check_terms(file_paths):
    global blocked_db

    blocked_db = BlockedDB(".check_terms.cfg")
    allowed_db = AllowedDB(".check_terms-allowed.txt")
    num_found = 0
    for line in find_term_lines(file_paths):
        if IGNORE_ALLOWED_DB or not allowed_db.find_line_in_db(line):
            print("PROBLEM:", line)
            num_found += 1
    return num_found


