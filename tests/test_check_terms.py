#!/usr/bin/env python

"""Tests for `check_terms` package."""

import pytest

from click.testing import CliRunner

from check_terms import check_terms
from check_terms import cli


@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


def test_content(response):
    """Sample pytest test function with the pytest fixture as an argument."""
    # from bs4 import BeautifulSoup
    # assert 'GitHub' in BeautifulSoup(response.content).title.string


def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "Verbose: False" in result.output
    assert "no_term_allowed: False" in result.output
    assert "ignore_allowed_db: False" in result.output
    help_result = runner.invoke(cli.main, ['--help'])
    print("Help Result:", help_result.output)
    assert help_result.exit_code == 0
    assert '--help' in help_result.output
    assert 'Show this message and exit.' in help_result.output
