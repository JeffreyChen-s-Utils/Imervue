"""Every Yes / No question names its default button; destructive ones go through ``confirm``.

Left to itself ``QMessageBox.question`` makes Yes the default, so a stray Enter
deleted rejected photos from disk, cleared the bookmarks or removed a tag
branch. ``dialog_rows.confirm`` asks with No as the default.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from Imervue.gui import dialog_rows

_ROOT = Path(__file__).resolve().parent.parent


def _questions_without_a_default() -> list[str]:
    found = []
    for folder in ("Imervue", "plugins"):
        for path in (_ROOT / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "question"
                        and "QMessageBox" in ast.unparse(node.func.value)
                        and len(node.args) < 5
                        and not any(k.arg == "defaultButton" for k in node.keywords)):
                    found.append(f"{path.relative_to(_ROOT).as_posix()}:{node.lineno}")
    return found


def test_every_question_names_its_default_button():
    assert _questions_without_a_default() == []


@pytest.fixture
def asked(monkeypatch):
    calls: list[tuple] = []
    answer = [QMessageBox.StandardButton.No]

    def question(parent, title, text, buttons, default):
        calls.append((parent, title, text, buttons, default))
        return answer[0]

    monkeypatch.setattr(QMessageBox, "question", question)
    return calls, answer


def test_confirm_asks_yes_or_no_with_no_as_the_default(asked):
    calls, _answer = asked
    assert dialog_rows.confirm(None, "Delete", "Delete it?") is False
    assert calls == [(None, "Delete", "Delete it?",
                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                      QMessageBox.StandardButton.No)]


def test_confirm_is_true_only_for_yes(asked):
    _calls, answer = asked
    answer[0] = QMessageBox.StandardButton.Yes
    assert dialog_rows.confirm(None, "Delete", "Delete it?") is True
    answer[0] = QMessageBox.StandardButton.Cancel
    assert dialog_rows.confirm(None, "Delete", "Delete it?") is False
