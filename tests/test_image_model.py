"""Tests for ImageModel."""
from Imervue.gpu_image_view.images.image_model import ImageModel


class TestImageModel:
    def test_init_empty(self):
        m = ImageModel()
        assert m.images == []
        assert m.deleted_history == []

    def test_set_images(self):
        m = ImageModel()
        paths = ["/a.png", "/b.png", "/c.png"]
        m.set_images(paths)
        assert m.images == paths
        # Should be a copy, not same reference
        assert m.images is not paths

    def test_delete_single(self):
        m = ImageModel()
        m.set_images(["/a.png", "/b.png", "/c.png"])
        deleted = m.delete_images(["/b.png"])
        assert m.images == ["/a.png", "/c.png"]
        assert len(deleted) == 1
        assert deleted[0] == ("/b.png", 1)

    def test_delete_multiple(self):
        m = ImageModel()
        m.set_images(["/a.png", "/b.png", "/c.png", "/d.png"])
        deleted = m.delete_images(["/a.png", "/c.png"])
        assert m.images == ["/b.png", "/d.png"]
        assert len(deleted) == 2

    def test_delete_nonexistent(self):
        m = ImageModel()
        m.set_images(["/a.png"])
        deleted = m.delete_images(["/z.png"])
        assert m.images == ["/a.png"]
        assert deleted == []

    def test_restore_images(self):
        m = ImageModel()
        m.set_images(["/a.png", "/b.png", "/c.png"])
        deleted = m.delete_images(["/b.png"])
        assert m.images == ["/a.png", "/c.png"]
        m.restore_images(deleted)
        assert m.images == ["/a.png", "/b.png", "/c.png"]

    def test_restore_multiple_preserves_order(self):
        m = ImageModel()
        m.set_images(["/a.png", "/b.png", "/c.png", "/d.png"])
        deleted = m.delete_images(["/a.png", "/c.png"])
        m.restore_images(deleted)
        assert m.images == ["/a.png", "/b.png", "/c.png", "/d.png"]
