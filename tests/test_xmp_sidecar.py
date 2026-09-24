"""Tests for XMP sidecar read/write (XMP-aware photo manager interop)."""
from __future__ import annotations

from pathlib import Path

import pytest

# xmp_sidecar depends on defusedxml for safe XML parsing; skip the whole
# module when the optional dependency is not installed in this environment.
pytest.importorskip("defusedxml")


@pytest.fixture
def xmp():
    from Imervue.image import xmp_sidecar
    return xmp_sidecar


@pytest.fixture
def image_path(tmp_path: Path) -> str:
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"fake-jpeg")
    return str(p)


class TestSidecarPath:
    def test_replaces_extension(self, xmp, tmp_path):
        assert xmp.sidecar_path_for(tmp_path / "foo.jpg").name == "foo.xmp"

    def test_has_sidecar_false(self, xmp, image_path):
        assert xmp.has_sidecar(image_path) is False

    def test_has_sidecar_true_after_write(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=3))
        assert xmp.has_sidecar(image_path) is True


class TestDarktableAndDigikamNaming:
    """darktable and digiKam write photo.jpg.xmp, which Imervue never looked for."""

    def test_an_appended_sidecar_is_read(self, xmp, image_path):
        Path(image_path + ".xmp").write_text(_DARKTABLE_SIDECAR, encoding="utf-8")
        assert xmp.has_sidecar(image_path)
        loaded = xmp.load(image_path)
        assert (loaded.rating, loaded.keywords) == (4, ["street", "night"])

    def test_saving_merges_into_the_appended_sidecar(self, xmp, image_path):
        appended = Path(image_path + ".xmp")
        appended.write_text(_DARKTABLE_SIDECAR, encoding="utf-8")
        assert xmp.save(image_path, xmp.XmpData(rating=2, keywords=["street"])) == appended
        assert not Path(image_path).with_suffix(".xmp").exists()
        (desc,) = _descriptions(appended)
        assert desc.find("{http://darktable.sf.net/}history") is not None
        assert xmp.load(image_path).rating == 2

    def test_the_adobe_name_wins_when_both_exist(self, xmp, image_path):
        Path(image_path + ".xmp").write_text(_DARKTABLE_SIDECAR, encoding="utf-8")
        xmp.save(image_path, xmp.XmpData(rating=1))   # no photo.xmp yet: goes to photo.jpg.xmp
        adobe = Path(image_path).with_suffix(".xmp")
        adobe.write_text(_LIGHTROOM_SIDECAR, encoding="utf-8")
        assert xmp.sidecar_path_for(image_path) == adobe
        assert xmp.load(image_path).rating == 3

    def test_a_new_sidecar_uses_the_adobe_name(self, xmp, image_path):
        assert xmp.save(image_path, xmp.XmpData(rating=5)).name == "photo.xmp"
        assert not Path(image_path + ".xmp").exists()


class TestLabelColor:
    @pytest.mark.parametrize(("label", "color"), [
        ("Red", "red"), ("yellow", "yellow"), (" GREEN ", "green"),     # Lightroom
        ("Select", "red"), ("Second", "yellow"), ("Approved", "green"),  # Bridge
        ("Review", "blue"), ("To Do", "purple"),
        ("", None), ("Needs retouch", None), ("Rot", None),
    ])
    def test_maps_lightroom_and_bridge_words(self, xmp, label, color):
        assert xmp.label_color(label) == color


class TestRoundTrip:
    def test_save_then_load_preserves_fields(self, xmp, image_path):
        data = xmp.XmpData(
            rating=4,
            title="Golden Hour",
            description="Sunset over the lake.",
            keywords=["landscape", "sunset"],
            color_label="red",
        )
        xmp.save(image_path, data)
        loaded = xmp.load(image_path)
        assert loaded.rating == 4
        assert loaded.title == "Golden Hour"
        assert loaded.description == "Sunset over the lake."
        assert loaded.keywords == ["landscape", "sunset"]
        assert loaded.color_label == "red"

    def test_creator_round_trips(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(creator="Ansel Adams"))
        assert xmp.load(image_path).creator == "Ansel Adams"

    def test_missing_sidecar_returns_empty(self, xmp, image_path):
        loaded = xmp.load(image_path)
        assert loaded.is_empty()

    def test_empty_data_removes_existing_sidecar(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=2))
        assert xmp.has_sidecar(image_path)
        xmp.save(image_path, xmp.XmpData())
        assert xmp.has_sidecar(image_path) is False

    def test_rating_clamped_to_five(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=99))
        # 99 serialised as-is, loader clamps on parse
        loaded = xmp.load(image_path)
        assert loaded.rating == 5

    def test_rating_accepts_reject(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=-1))
        loaded = xmp.load(image_path)
        assert loaded.rating == -1

    def test_malformed_xml_returns_empty(self, xmp, image_path):
        sidecar = xmp.sidecar_path_for(image_path)
        sidecar.write_text("<not valid xml", encoding="utf-8")
        assert xmp.load(image_path).is_empty()

    def test_sidecar_with_dtd_entity_returns_empty(self, xmp, image_path):
        """defusedxml rejects DTD/entity declarations (XXE / billion-laughs
        defence) with a DefusedXmlException — a ValueError subclass. The
        loader must treat it as a bad file and degrade to empty, not raise
        into keyword-index / smart-album callers."""
        sidecar = xmp.sidecar_path_for(image_path)
        sidecar.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE x [<!ENTITY e "value">]>\n'
            "<x>&e;</x>\n",
            encoding="utf-8",
        )
        # Must not raise:
        assert xmp.load(image_path).is_empty()


class TestSettingsIntegration:
    def test_export_for_includes_rating_and_tags(self, xmp, image_path):
        from Imervue.user_settings.tags import add_tag
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict["image_ratings"] = {image_path: 5}
        user_setting_dict["image_titles"] = {image_path: "Hero"}
        add_tag("travel", image_path)
        add_tag("japan", image_path)

        xmp.export_for(image_path)
        loaded = xmp.load(image_path)
        assert loaded.rating == 5
        assert loaded.title == "Hero"
        assert set(loaded.keywords) == {"travel", "japan"}

    def test_export_preserves_external_creator(self, xmp, image_path):
        """Imervue doesn't track dc:creator; exporting settings must not
        wipe a creator an external editor wrote into the sidecar."""
        xmp.save(image_path, xmp.XmpData(creator="Ansel Adams", rating=2))
        xmp.export_for(image_path)   # settings know nothing about creator
        assert xmp.load(image_path).creator == "Ansel Adams"

    def test_export_does_not_delete_creator_only_sidecar(self, xmp, image_path):
        """A sidecar carrying only a creator must survive an export from
        otherwise-empty settings, not be unlinked as 'empty'."""
        xmp.save(image_path, xmp.XmpData(creator="Jane"))
        assert xmp.has_sidecar(image_path)
        xmp.export_for(image_path)
        assert xmp.has_sidecar(image_path)
        assert xmp.load(image_path).creator == "Jane"

    def test_import_for_restores_rating_and_tags(self, xmp, image_path):
        from Imervue.user_settings.tags import get_tags_for_image
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        xmp.save(image_path, xmp.XmpData(
            rating=3,
            title="Imported",
            keywords=["alpha", "beta"],
            color_label="blue",
        ))
        xmp.import_for(image_path)

        assert user_setting_dict["image_ratings"][image_path] == 3
        assert user_setting_dict["image_titles"][image_path] == "Imported"
        assert set(get_tags_for_image(image_path)) == {"alpha", "beta"}

    @pytest.mark.parametrize("label", ["Red", "Select"])
    def test_import_understands_lightroom_and_bridge_labels(self, xmp, image_path, label):
        """Lightroom's "Red" and Bridge's "Select" were rejected, clearing the label."""
        from Imervue.user_settings.color_labels import get_color_label
        xmp.save(image_path, xmp.XmpData(color_label=label))
        xmp.import_for(image_path)
        assert get_color_label(image_path) == "red"

    def test_import_of_a_label_without_a_colour_clears_it(self, xmp, image_path):
        from Imervue.user_settings.color_labels import get_color_label, set_color_label
        set_color_label(image_path, "blue")
        xmp.save(image_path, xmp.XmpData(color_label="Needs retouch"))
        xmp.import_for(image_path)
        assert get_color_label(image_path) is None

    def test_export_writes_the_label_as_lightroom_names_it(self, xmp, image_path):
        from Imervue.user_settings.color_labels import set_color_label
        set_color_label(image_path, "green")
        xmp.export_for(image_path)
        assert xmp.load(image_path).color_label == "Green"

    @pytest.mark.parametrize(("existing", "color", "written"), [
        ("Approved", "green", "Approved"),    # Bridge's word for the same colour stays
        ("Approved", "red", "Red"),           # another colour replaces it
        ("Approved", None, ""),               # cleared in Imervue
        ("Needs retouch", None, "Needs retouch"),   # a label Imervue can't show is kept
        ("Needs retouch", "blue", "Blue"),
    ])
    def test_export_keeps_the_sidecars_wording_where_it_can(
            self, xmp, image_path, existing, color, written):
        from Imervue.user_settings.color_labels import set_color_label
        xmp.save(image_path, xmp.XmpData(rating=1, color_label=existing))
        set_color_label(image_path, color)
        xmp.export_for(image_path)
        assert xmp.load(image_path).color_label == written

    def test_a_rejected_sidecar_becomes_a_cull_reject(self, xmp, image_path):
        """Lightroom's reject (xmp:Rating -1) was stored as a -1 star rating nothing shows."""
        from Imervue.library import image_index
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["image_ratings"] = {image_path: 4}
        xmp.save(image_path, xmp.XmpData(rating=-1))
        xmp.import_for(image_path)
        assert image_index.get_cull_state(image_path) == image_index.CULL_REJECT
        assert image_path not in user_setting_dict["image_ratings"]

    @pytest.mark.parametrize(("state", "after"), [("reject", "unflagged"), ("pick", "pick")])
    def test_a_sidecar_not_rejected_lifts_only_a_reject(self, xmp, image_path, state, after):
        from Imervue.library import image_index
        image_index.set_cull_state(image_path, state)
        xmp.save(image_path, xmp.XmpData(rating=3))
        xmp.import_for(image_path)
        assert image_index.get_cull_state(image_path) == after

    def test_a_reject_is_exported_as_rating_minus_one(self, xmp, image_path):
        from Imervue.library import image_index
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["image_ratings"] = {image_path: 2}
        image_index.set_cull_state(image_path, image_index.CULL_REJECT)
        xmp.export_for(image_path)
        assert xmp.load(image_path).rating == -1

    def test_no_library_is_created_for_an_export_or_a_plain_import(self, xmp, image_path, tmp_path):
        from Imervue.library import image_index
        image_index.close()
        image_index.set_db_path(tmp_path / "none" / "library.db")
        xmp.save(image_path, xmp.XmpData(rating=3))
        xmp.import_for(image_path)
        xmp.export_for(image_path)
        assert not (tmp_path / "none").exists()

    def test_import_empty_rating_clears_existing(self, xmp, image_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict["image_ratings"] = {image_path: 4}
        xmp.save(image_path, xmp.XmpData(title="No rating"))
        xmp.import_for(image_path)
        assert image_path not in user_setting_dict.get("image_ratings", {})


class TestXmpData:
    def test_is_empty_default(self, xmp):
        assert xmp.XmpData().is_empty()

    def test_is_empty_false_with_rating(self, xmp):
        assert xmp.XmpData(rating=1).is_empty() is False

    def test_is_empty_false_with_keywords(self, xmp):
        assert xmp.XmpData(keywords=["x"]).is_empty() is False


_LIGHTROOM_SIDECAR = """<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    xmlns:tiff="http://ns.adobe.com/tiff/1.0/"
   xmp:Rating="3" tiff:Make="Canon"
   crs:Exposure2012="+0.65" crs:HasCrop="True">
   <crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012>
   <dc:subject><rdf:Bag><rdf:li>old</rdf:li></rdf:Bag></dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
_DARKTABLE_SIDECAR = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:darktable="http://darktable.sf.net/"
   xmp:Rating="4" darktable:xmp_version="5" darktable:history_end="1">
   <darktable:colorlabels><rdf:Seq><rdf:li>0</rdf:li></rdf:Seq></darktable:colorlabels>
   <darktable:history><rdf:Seq><rdf:li darktable:operation="exposure"/></rdf:Seq></darktable:history>
   <dc:subject><rdf:Bag><rdf:li>street</rdf:li><rdf:li>night</rdf:li></rdf:Bag></dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
_CRS = "{http://ns.adobe.com/camera-raw-settings/1.0/}"
_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"


def _write_sidecar(image_path, text):
    from Imervue.image.xmp_sidecar import sidecar_path_for
    path = sidecar_path_for(image_path)
    path.write_text(text, encoding="utf-8")
    return path


def _descriptions(path):
    from defusedxml import ElementTree
    return list(ElementTree.parse(str(path)).getroot().iter(f"{_RDF}Description"))


class TestSaveMergesIntoAnExistingSidecar:
    """save() rebuilt the file from Imervue's six fields, wiping a raw developer's edits."""

    def test_raw_developer_settings_survive(self, xmp, image_path):
        path = _write_sidecar(image_path, _LIGHTROOM_SIDECAR)
        xmp.save(image_path, xmp.XmpData(rating=5, keywords=["Taipei"]))
        (desc,) = _descriptions(path)
        assert desc.get(f"{_CRS}Exposure2012") == "+0.65"
        assert desc.get(f"{_CRS}HasCrop") == "True"
        assert desc.get("{http://ns.adobe.com/tiff/1.0/}Make") == "Canon"
        curve = desc.find(f"{_CRS}ToneCurvePV2012/{_RDF}Seq")
        assert [li.text for li in curve] == ["0, 0", "255, 255"]
        assert xmp.load(image_path).rating == 5
        assert xmp.load(image_path).keywords == ["Taipei"]

    def test_the_files_own_prefixes_are_kept(self, xmp, image_path):
        path = _write_sidecar(image_path, _LIGHTROOM_SIDECAR)
        xmp.save(image_path, xmp.XmpData(rating=1))
        text = path.read_text(encoding="utf-8")
        assert "crs:Exposure2012" in text and "ns0:" not in text

    def test_element_form_fields_are_replaced_not_duplicated(self, xmp, image_path):
        path = _write_sidecar(image_path, """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"><xmp:Rating>2</xmp:Rating>
   <xmp:Label>Blue</xmp:Label></rdf:Description>
  <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:title><rdf:Alt><rdf:li>old title</rdf:li></rdf:Alt></dc:title></rdf:Description>
 </rdf:RDF></x:xmpmeta>""")
        xmp.save(image_path, xmp.XmpData(rating=4, title="new"))
        text = path.read_text(encoding="utf-8")
        assert text.count("Rating") == 1 and "Blue" not in text and "old title" not in text
        loaded = xmp.load(image_path)
        assert (loaded.rating, loaded.title, loaded.color_label) == (4, "new", "")

    def test_clearing_imervue_fields_keeps_a_sidecar_with_other_data(self, xmp, image_path):
        path = _write_sidecar(image_path, _LIGHTROOM_SIDECAR)
        xmp.save(image_path, xmp.XmpData())
        assert path.is_file()
        (desc,) = _descriptions(path)
        assert desc.get(f"{_CRS}Exposure2012") == "+0.65"
        assert xmp.load(image_path).is_empty()

    def test_a_sidecar_left_empty_is_removed(self, xmp, image_path):
        path = _write_sidecar(image_path, """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="2"/>
 </rdf:RDF></x:xmpmeta>""")
        xmp.save(image_path, xmp.XmpData())
        assert not path.exists()

    def test_a_sidecar_without_description_gets_one(self, xmp, image_path):
        _write_sidecar(image_path, '<x:xmpmeta xmlns:x="adobe:ns:meta/"/>')
        xmp.save(image_path, xmp.XmpData(rating=3))
        assert xmp.load(image_path).rating == 3

    @pytest.mark.parametrize("text", ["<not xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'])
    def test_an_unreadable_sidecar_is_not_overwritten(self, xmp, image_path, text):
        path = _write_sidecar(image_path, text)
        with pytest.raises(xmp.UnreadableSidecarError):
            xmp.save(image_path, xmp.XmpData(rating=5))
        assert path.read_text(encoding="utf-8") == text
        assert issubclass(xmp.UnreadableSidecarError, OSError)


_PACKET = (b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
           b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
           b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" '
           b'xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
           b'xmp:Rating="4" xmp:Label="Red"><dc:subject><rdf:Bag><rdf:li>Taipei</rdf:li>'
           b'</rdf:Bag></dc:subject></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')


class TestEmbeddedMetadata:
    """Lightroom writes a JPEG's rating into the file, never a sidecar; Imervue read sidecars only."""

    @staticmethod
    def _image(tmp_path, name="photo.jpg", *, packet=_PACKET, exif=None):
        from PIL import Image
        path = tmp_path / name
        kwargs = {}
        if packet is not None and name.endswith(".tif"):
            kwargs["tiffinfo"] = {700: packet}         # Pillow's TIFF writer takes XMP as tag 700
        elif packet is not None:
            kwargs["xmp"] = packet
        if exif is not None:
            kwargs["exif"] = exif
        Image.new("RGB", (8, 8)).save(path, **kwargs)
        return str(path)

    @pytest.mark.parametrize("name", ["photo.jpg", "photo.webp", "photo.tif"])
    def test_the_packet_inside_the_file_is_read(self, xmp, tmp_path, name):
        loaded = xmp.load(self._image(tmp_path, name))
        assert (loaded.rating, loaded.keywords, loaded.color_label) == (4, ["Taipei"], "Red")

    def test_a_png_packet_is_read(self, xmp, tmp_path):
        from PIL import Image, PngImagePlugin
        info = PngImagePlugin.PngInfo()
        info.add_itxt("XML:com.adobe.xmp", _PACKET.decode("utf-8"))
        path = tmp_path / "photo.png"
        Image.new("RGB", (8, 8)).save(path, pnginfo=info)
        assert xmp.load(str(path)).keywords == ["Taipei"]

    def test_a_sidecar_wins_over_the_packet(self, xmp, tmp_path):
        image = self._image(tmp_path)
        xmp.save(image, xmp.XmpData(rating=1))
        assert xmp.load(image).rating == 1

    @pytest.mark.parametrize(("tag", "value", "stars"), [
        (0x4746, 3, 3),          # Rating, as Windows Explorer and some cameras write it
        (0x4749, 50, 3),         # RatingPercent only
        (0x4746, 9, 5),          # out of range: clamped
    ])
    def test_an_exif_rating_fills_in(self, xmp, tmp_path, tag, value, stars):
        from PIL import Image
        exif = Image.Exif()
        exif[tag] = value
        assert xmp.load(self._image(tmp_path, packet=None, exif=exif)).rating == stars

    def test_the_packets_rating_beats_the_exif_one(self, xmp, tmp_path):
        from PIL import Image
        exif = Image.Exif()
        exif[0x4746] = 1
        assert xmp.load(self._image(tmp_path, exif=exif)).rating == 4

    def test_a_malformed_packet_still_lets_the_exif_rating_through(self, xmp, tmp_path):
        from PIL import Image
        exif = Image.Exif()
        exif[0x4746] = 2
        loaded = xmp.load(self._image(tmp_path, packet=b"<not xml", exif=exif))
        assert (loaded.rating, loaded.keywords) == (2, [])

    @pytest.mark.parametrize("content", [b"", b"not an image at all"])
    def test_an_unreadable_file_gives_nothing(self, xmp, tmp_path, content):
        path = tmp_path / "broken.jpg"
        path.write_bytes(content)
        assert xmp.load(str(path)).is_empty()

    def test_a_plain_file_gives_nothing(self, xmp, tmp_path):
        assert xmp.load(self._image(tmp_path, packet=None)).is_empty()


def test_a_hierarchy_is_read_and_a_save_keeps_it(xmp, image_path):
    """Imervue reads lr:hierarchicalSubject and never rewrites another editor's list."""
    path = xmp.sidecar_path_for(image_path)
    path.write_text("""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
   <lr:hierarchicalSubject><rdf:Bag><rdf:li>Places|Taiwan</rdf:li></rdf:Bag></lr:hierarchicalSubject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>""", encoding="utf-8")
    loaded = xmp.load(image_path)
    assert loaded.hierarchical_keywords == ["Places|Taiwan"] and not loaded.is_empty()
    xmp.save(image_path, xmp.XmpData(rating=2))
    assert xmp.load(image_path).hierarchical_keywords == ["Places|Taiwan"]
    assert "lr:hierarchicalSubject" in path.read_text(encoding="utf-8")
