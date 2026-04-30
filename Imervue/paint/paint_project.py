"""Multi-page comic project — bundle of PaintDocuments + manager.

A :class:`PaintProject` is the manga / comic-book layer above the
single-page :class:`PaintDocument`. It owns an ordered list of
:class:`ProjectPage` entries (one PaintDocument each plus a display
name) plus an active-page pointer so the workspace can show one
page at a time and jump between them via the page navigator.

This module is the in-memory data model + verbs. The save / load
NPZ-bundle format lives in :mod:`paint_project_io` so the file
surface area stays focused.

Page operations:

* :meth:`PaintProject.add_page`     — insert a new page after the
                                       active one (or at end)
* :meth:`PaintProject.remove_page`  — drop a page by index, refuses
                                       to drop the last
* :meth:`PaintProject.move_page`    — re-order pages
* :meth:`PaintProject.set_active_page` — pointer move
* :meth:`PaintProject.rename_page`  — change a page's display name

The project itself has a name + author metadata field so the
in-comic title and credit survive a round-trip.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.paint.document import PaintDocument

MAX_PAGES = 1024


@dataclass
class ProjectPage:
    """One page in a :class:`PaintProject`."""

    document: PaintDocument
    name: str = "Page"

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("page name must be non-empty")


@dataclass
class PaintProject:
    """Multi-page project holding a list of :class:`ProjectPage`."""

    name: str = "Untitled Project"
    author: str = ""
    pages: list[ProjectPage] = field(default_factory=list)
    active_page_index: int = 0

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("project name must be non-empty")
        if self.pages:
            self.active_page_index = max(
                0, min(int(self.active_page_index), len(self.pages) - 1),
            )
        else:
            self.active_page_index = 0

    # ---- page accessors -------------------------------------------------

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def active_page(self) -> ProjectPage | None:
        if not self.pages:
            return None
        return self.pages[self.active_page_index]

    def page_at(self, index: int) -> ProjectPage:
        if not 0 <= index < len(self.pages):
            raise IndexError(f"page index {index} out of range")
        return self.pages[index]

    # ---- page mutations -------------------------------------------------

    def add_page(
        self, page: ProjectPage, *, after_active: bool = True,
    ) -> int:
        """Add a page; return the index it landed at."""
        if len(self.pages) >= MAX_PAGES:
            raise ValueError(
                f"project already at {MAX_PAGES} pages (cap)",
            )
        insert_at = (
            self.active_page_index + 1
            if after_active and self.pages
            else len(self.pages)
        )
        insert_at = min(insert_at, len(self.pages))
        self.pages.insert(insert_at, page)
        self.active_page_index = insert_at
        return insert_at

    def remove_page(self, index: int) -> bool:
        """Drop the page at ``index``. Refuses to drop the last page —
        a project always has at least one page."""
        if not 0 <= index < len(self.pages):
            return False
        if len(self.pages) <= 1:
            return False
        del self.pages[index]
        self.active_page_index = max(
            0, min(self.active_page_index, len(self.pages) - 1),
        )
        return True

    def move_page(self, src: int, dst: int) -> bool:
        if not 0 <= src < len(self.pages):
            return False
        if not 0 <= dst < len(self.pages):
            return False
        if src == dst:
            return False
        page = self.pages.pop(src)
        self.pages.insert(dst, page)
        # Keep the active page pointing at the same content — adjust
        # if our active index just got shifted by the rearrange.
        if self.active_page_index == src:
            self.active_page_index = dst
        elif src < self.active_page_index <= dst:
            self.active_page_index -= 1
        elif dst <= self.active_page_index < src:
            self.active_page_index += 1
        return True

    def set_active_page(self, index: int) -> None:
        if not 0 <= index < len(self.pages):
            raise IndexError(f"page index {index} out of range")
        self.active_page_index = index

    def rename_page(self, index: int, new_name: str) -> bool:
        if not 0 <= index < len(self.pages):
            return False
        if not str(new_name).strip():
            raise ValueError("page name must be non-empty")
        if self.pages[index].name == new_name:
            return False
        self.pages[index].name = new_name
        return True
