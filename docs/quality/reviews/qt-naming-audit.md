# Qt callback naming audit

All fifteen scoped python:S100 findings are confirmed false positives. Each flagged method is the concrete consumer's effective implementation of an existing PySide6 Qt method with the same exact name. Renaming only these methods to snake_case would stop overriding the Qt API and leave the inherited Qt implementation selected.

Scope is the fifteen naming findings in .audit/sonar-50186aa8.json. No source files or remote issue states were changed. The separate S5863 test assertion finding is outside this classification.

Independent inspection used installed PySide6 6.11.2. It imported each concrete consumer class, checked the effective method source path, found its defining mixin in the real MRO, and required a later PySide6 base to expose the same callable name. Each callable was also matched to its exact method declaration in the installed PySide6 .pyi file. QCoreApplication.instance() was None before and after. No application, widget, GL surface or window was constructed.

| Issue key | Source and method | Effective owner and consumer | Installed Qt API |
|---|---|---|---|
| AaGEIrKcz3Xv8cTrKEKU | Imervue/puppet/canvas_frame.py::initializeGL | PuppetCanvasFrameMixin in PuppetCanvas | PySide6.QtOpenGLWidgets.QOpenGLWidget.initializeGL |
| AaGEIrKcz3Xv8cTrKEKV | Imervue/puppet/canvas_frame.py::resizeGL | PuppetCanvasFrameMixin in PuppetCanvas | PySide6.QtOpenGLWidgets.QOpenGLWidget.resizeGL |
| AaGEIrKcz3Xv8cTrKEKW | Imervue/puppet/canvas_frame.py::paintGL | PuppetCanvasFrameMixin in PuppetCanvas | PySide6.QtOpenGLWidgets.QOpenGLWidget.paintGL |
| AaGEIrKmz3Xv8cTrKEKb | Imervue/puppet/canvas_physics.py::showEvent | PuppetCanvasPhysicsMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.showEvent |
| AaGEIrKmz3Xv8cTrKEKc | Imervue/puppet/canvas_physics.py::hideEvent | PuppetCanvasPhysicsMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.hideEvent |
| AaGEIrKhz3Xv8cTrKEKX | Imervue/puppet/canvas_pointer.py::mousePressEvent | PuppetCanvasPointerMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.mousePressEvent |
| AaGEIrKhz3Xv8cTrKEKY | Imervue/puppet/canvas_pointer.py::mouseMoveEvent | PuppetCanvasPointerMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.mouseMoveEvent |
| AaGEIrKhz3Xv8cTrKEKZ | Imervue/puppet/canvas_pointer.py::mouseReleaseEvent | PuppetCanvasPointerMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.mouseReleaseEvent |
| AaGEIrKkz3Xv8cTrKEKa | Imervue/puppet/canvas_view.py::wheelEvent | PuppetCanvasViewMixin in PuppetCanvas | PySide6.QtWidgets.QWidget.wheelEvent |
| AaGEDsxXvbUJfy7MTI-7 | Imervue/gui/image_list_cells.py::headerData | ImageListCellsMixin in ImageListModel | PySide6.QtCore.QAbstractItemModel.headerData |
| AaGEDs0bvbUJfy7MTI-9 | Imervue/gui/image_list_context.py::contextMenuEvent | ImageListContextMixin in ImageListView | PySide6.QtWidgets.QAbstractScrollArea.contextMenuEvent |
| AaGEDs0YvbUJfy7MTI-8 | Imervue/gui/image_list_keyboard.py::keyPressEvent | ImageListKeyboardMixin in ImageListView | PySide6.QtWidgets.QAbstractItemView.keyPressEvent |
| AaGD0g9tMUpo3FyXzYB1 | Imervue/gui/annotation_input.py::contextMenuEvent | AnnotationInputMixin in AnnotationCanvas | PySide6.QtWidgets.QWidget.contextMenuEvent |
| AaGD0g9tMUpo3FyXzYB2 | Imervue/gui/annotation_input.py::keyPressEvent | AnnotationInputMixin in AnnotationCanvas | PySide6.QtWidgets.QWidget.keyPressEvent |
| AaGD0g7aMUpo3FyXzYB0 | Imervue/gui/annotation_viewport.py::paintEvent | AnnotationViewportMixin in AnnotationCanvas | PySide6.QtWidgets.QWidget.paintEvent |

## Callback contracts

- initializeGL, resizeGL and paintGL are QOpenGLWidget lifecycle/rendering hooks. Their spellings are the Qt virtual method names, not project naming choices.
- showEvent and hideEvent receive Qt visibility events. The physics mixin delegates to the superclass and then synchronizes its timer.
- mousePressEvent, mouseMoveEvent, mouseReleaseEvent and wheelEvent receive Qt pointer/wheel events. The canvas uses them for pan, drag, hit testing and zoom.
- headerData is the model API used by Qt views to request headers. ImageListModel resolves its implementation from ImageListCellsMixin before the Qt model bases.
- contextMenuEvent, keyPressEvent and paintEvent are QWidget/view event handlers. The concrete image-list and annotation consumers resolve their flagged mixin implementations before the Qt bases.

## Installed declaration evidence

The declarations below are from D:/Codes/Imervue/.venv/Lib/site-packages/PySide6. Installed extension descriptors exposed the matching names but no docstrings, so the audit checked the shipped declarations rather than inventing signatures.

- QtOpenGLWidgets.pyi:54 contains `def initializeGL(self, /) -> None: ...`.
- QtOpenGLWidgets.pyi:66 contains `def resizeGL(self, w: int, h: int, /) -> None: ...`.
- QtOpenGLWidgets.pyi:63 contains `def paintGL(self, /) -> None: ...`.
- QtWidgets.pyi:9053 contains `def showEvent(self, event: PySide6.QtGui.QShowEvent, /) -> None: ...`.
- QtWidgets.pyi:8833 contains `def hideEvent(self, event: PySide6.QtGui.QHideEvent, /) -> None: ...`.
- QtWidgets.pyi:8903 contains `def mousePressEvent(self, event: PySide6.QtGui.QMouseEvent, /) -> None: ...`.
- QtWidgets.pyi:8902 contains `def mouseMoveEvent(self, event: PySide6.QtGui.QMouseEvent, /) -> None: ...`.
- QtWidgets.pyi:8904 contains `def mouseReleaseEvent(self, event: PySide6.QtGui.QMouseEvent, /) -> None: ...`.
- QtWidgets.pyi:9089 contains `def wheelEvent(self, event: PySide6.QtGui.QWheelEvent, /) -> None: ...`.
- QtCore.pyi:226 contains `def headerData(self, section: int, orientation: PySide6.QtCore.Qt.Orientation, /, role: int = ...) -> typing.Any: ...`.
- QtWidgets.pyi:345 contains `def contextMenuEvent(self, arg__1: PySide6.QtGui.QContextMenuEvent, /) -> None: ...`.
- QtWidgets.pyi:243 contains `def keyPressEvent(self, event: PySide6.QtGui.QKeyEvent, /) -> None: ...`.
- QtWidgets.pyi:8782 contains `def contextMenuEvent(self, event: PySide6.QtGui.QContextMenuEvent, /) -> None: ...`.
- QtWidgets.pyi:8857 contains `def keyPressEvent(self, event: PySide6.QtGui.QKeyEvent, /) -> None: ...`.
- QtWidgets.pyi:8917 contains `def paintEvent(self, event: PySide6.QtGui.QPaintEvent, /) -> None: ...`.

## Limits

This audit proves naming and override identity for these issue keys. It does not verify native event dispatch, visual rendering, resource lifetime or overall correctness. No blanket rule or path exclusion is justified by this result. Classify only the listed issue keys; new findings require their own source and API check.

Prove It Works shaped the decision by requiring the installed Qt API, shipped declarations and actual consumer MRO instead of relying on camelCase spelling or a source comment.
