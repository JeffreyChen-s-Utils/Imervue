"""Mark a file or folder hidden the way Explorer does, for tests of hidden-file skipping."""
import ctypes
import sys

import pytest

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows' hidden attribute")

_FILE_ATTRIBUTE_HIDDEN = 0x2


def hide(path) -> None:
    """Give *path* Windows' hidden attribute (call only under ``windows_only``)."""
    if not ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_HIDDEN):
        raise ctypes.WinError()
