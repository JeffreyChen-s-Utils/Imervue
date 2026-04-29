"""Tests for the https-only URL guards used by the plugin and installer modules.

These modules reach the network with hardcoded https:// URLs today, but the
guard is here to ensure no future maintainer (or compromised upstream) can
slip in a file:/// or http:// URL that would bypass transport security.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.request import Request

from Imervue.plugin import pip_installer, plugin_downloader


# The non-https URLs below are intentional test inputs — the whole point of
# the test suite is to prove the guard rejects them. Inline suppression
# markers keep SonarCloud's python:S5332 ("clear-text protocol") from
# flagging the deliberate clear-text inputs.

class TestPipInstallerHttpsGuard(unittest.TestCase):
    def test_rejects_http_scheme(self):
        req = Request("http://example.com/evil.zip")  # NOSONAR
        with self.assertRaises(ValueError):
            pip_installer._https_urlopen(req, timeout=1)

    def test_rejects_file_scheme(self):
        req = Request("file:///etc/passwd")  # NOSONAR
        with self.assertRaises(ValueError):
            pip_installer._https_urlopen(req, timeout=1)

    def test_rejects_ftp_scheme(self):
        req = Request("ftp://example.com/file")  # NOSONAR
        with self.assertRaises(ValueError):
            pip_installer._https_urlopen(req, timeout=1)

    def test_allows_https_scheme(self):
        req = Request("https://example.com/ok.zip")
        with patch("Imervue.plugin.pip_installer.urlopen") as mock_open:
            mock_open.return_value = object()
            result = pip_installer._https_urlopen(req, timeout=5)
        mock_open.assert_called_once_with(req, timeout=5)
        self.assertIs(result, mock_open.return_value)


class TestPluginDownloaderHttpsGuard(unittest.TestCase):
    def test_rejects_http_scheme(self):
        req = Request("http://example.com/evil.py")  # NOSONAR
        with self.assertRaises(ValueError):
            plugin_downloader._https_urlopen(req, timeout=1)

    def test_rejects_file_scheme(self):
        req = Request("file:///tmp/evil.py")  # NOSONAR
        with self.assertRaises(ValueError):
            plugin_downloader._https_urlopen(req, timeout=1)

    def test_allows_https_scheme(self):
        req = Request("https://api.github.com/repos/x/y/contents")
        with patch("Imervue.plugin.plugin_downloader.urllib.request.urlopen") as mock_open:
            mock_open.return_value = object()
            result = plugin_downloader._https_urlopen(req, timeout=5)
        mock_open.assert_called_once_with(req, timeout=5)
        self.assertIs(result, mock_open.return_value)


if __name__ == "__main__":
    unittest.main()
