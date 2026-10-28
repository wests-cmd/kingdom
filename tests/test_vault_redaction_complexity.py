"""Credential redaction must remain bounded on attacker-shaped public text."""
import subprocess
import sys

import pytest

from backend.memory.portable_vault import clean_metadata, clean_text


def test_redaction_preserves_supported_secret_exclusion():
    text = ('prefix -----BEGIN RSA PRIVATE KEY-----\nprivate-material\n'
            '-----END RSA PRIVATE KEY----- suffix '
            'https://alice:credential@peer.example/path '
            'ghp_abcdefghijklmnop bearer abcdefghijklmnop\npassword = private-value')
    result = clean_text(text)
    for secret in ('private-material', 'credential', 'abcdefghijklmnop', 'private-value'):
        assert secret not in result
    assert 'prefix ' in result and ' suffix ' in result
    assert 'https://[redacted]@peer.example/path' in result
    assert clean_metadata({'api_key': 'omit', 'note': 'token: omit'}) == {'note': 'token: [redacted]'}


def test_unfinished_private_key_fails_closed_but_public_key_and_plain_urls_survive():
    assert clean_text('note -----BEGIN PRIVATE KEY-----\nsensitive') == 'note [redacted]'
    plain = '-----BEGIN PUBLIC KEY-----public-----END PUBLIC KEY----- https://peer.example:8443/path'
    assert clean_text(plain) == plain


@pytest.mark.parametrize('shape', ['url', 'pem'])
def test_adversarial_redaction_finishes_within_process_budget(shape):
    # A subprocess timeout bounds the regression even when testing old code.
    code = """
import sys
from backend.memory.portable_vault import clean_text
text = ('https://' + 'a:' * 100000 + 'no-at-sign') if sys.argv[1] == 'url' else ('-----BEGIN RSA PRIVATE KEY-----x' * 10000)
clean_text(text)
"""
    subprocess.run([sys.executable, '-c', code, shape], check=True, timeout=4,
                   capture_output=True)
