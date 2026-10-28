"""Hidden-widget rendering exercises Qt's composed paint-event dispatch."""
from PIL import Image
from PySide6.QtGui import QImage, QUndoStack

from Imervue.gui.annotation_canvas import AnnotationCanvas
from Imervue.gui.annotation_models import Annotation


def test_canvas_paints_base_and_annotations_in_image_coordinates(qapp):
    canvas = AnnotationCanvas(Image.new("RGBA", (200, 100), (200, 0, 0, 255)), QUndoStack())
    canvas.resize(400, 300)
    canvas.set_annotations([
        Annotation(kind="line", points=[(20, 50), (180, 50)], color=(0, 255, 0, 255), stroke_width=5),
    ])
    image = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    try:
        canvas.render(image)
        assert image.pixelColor(0, 0).getRgb() == (30, 30, 30, 255)
        assert image.pixelColor(110, 110).getRgb() == (200, 0, 0, 255)
        assert image.pixelColor(200, 150).getRgb() == (0, 255, 0, 255)
    finally:
        canvas.close()
        canvas.deleteLater()
