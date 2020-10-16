
import os
import re
import logging

DEFAULT_TERMS = """
master
slave
white?list
black?list
grandfather
dummy
stupid
"""

def _parse_block_db_config(lines):
    for line in lines:
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

def _build_block_db(block_db_config):
    terms = set()
    non_exclusion_terms = set()
    exclusion_patterns = []

    for term, exclusions in block_db_config:
        terms.add(term)
        if exclusions:
            check_pat = re.compile(f"(?=({term}.*))", re.IGNORECASE)
            exclusions_re = ".*|".join(sorted(exclusions))
            exclusions_pat = re.compile(f"(?=({exclusions_re}.*))", re.IGNORECASE)
            exclusion_patterns.append((check_pat, exclusions_pat))
        else:
            non_exclusion_terms.add(term)

    terms_pattern = "|".join(sorted(terms))
    if non_exclusion_terms:
        non_excluded_pattern = re.compile("|".join(sorted(non_exclusion_terms)), re.IGNORECASE)
    else:
        non_excluded_pattern = None

    logging.info(f"Search Terms: {terms}")
    logging.info(f"Search Terms Pattern: {terms_pattern}")
    logging.info(f"Search Terms Without Exclusions: {non_exclusion_terms}")
    logging.info(f"Exclusions Patterns: {exclusion_patterns}")
    logging.info(f"Non-Excluded-Path Patterns: {non_excluded_pattern}")

    return terms_pattern, exclusion_patterns, non_excluded_pattern


def load_blocked_db(file_path):
    if not os.path.exists(file_path):
        logging.warning(f"Creating blocked db config file {file_path}, using defaults")
        with open(file_path, 'w') as f:
            for term in DEFAULT_TERMS.strip().split('\n'):
                print(term.strip(), file=f, end='\n')
    else:
        logging.info(f"Reading existing blocked db config file {file_path}")

    with open(file_path, 'r') as f:
        terms_pattern, exclusion_patterns, non_excluded_pattern = _build_block_db(
            _parse_block_db_config(f.readlines())
        )
    return terms_pattern, exclusion_patterns, non_excluded_pattern


def should_block(line, exclusion_patterns, non_excluded_pattern):
    # -- If there are no exclusion patterns, then the egrep command found a blockable match
    if not exclusion_patterns:
        return True

    # -- If there are exclusion patterns, check if any of the patterns without exclusions
    # match this line - if any do, this is also a blockable match
    if non_excluded_pattern and non_excluded_pattern.search(line):
        return True

    for check_pat, exclusions_pat in exclusion_patterns:
        found = [m.group(1) for m in check_pat.finditer(line)]
        if found:
            # -- Line term found
            excluded = [m.group(1) for m in exclusions_pat.finditer(line)]
            if found != excluded:
                # -- All matches are NOT also exclusions, so this is a 'should block' line
                return True
    return False
