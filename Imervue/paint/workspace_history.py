"""One completed document edit shared by Paint's explicit editing commands."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def commit_document_edit(workspace: PaintWorkspace) -> None:
    """Refresh the document and commit one undo step and modified marker."""
    canvas = workspace.canvas()
    canvas.document().invalidate_composite()
    workspace._on_dispatcher_commit()  # noqa: SLF001 - shared gesture boundary
    canvas.update()
