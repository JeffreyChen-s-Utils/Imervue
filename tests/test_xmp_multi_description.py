"""XMP load must merge fields across multiple rdf:Description nodes.

XMP legally splits properties across one Description per schema; reading only the
first node dropped fields (e.g. rating in one, keywords in another).
"""
from __future__ import annotations

from Imervue.image.xmp_sidecar import load

_MULTI = """<?xml version="1.0"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
          xmlns:xmp="http://ns.adobe.com/xap/1.0/"
          xmlns:dc="http://purl.org/dc/elements/1.1/">
  <rdf:Description xmp:Rating="4"/>
  <rdf:Description>
   <dc:subject><rdf:Bag><rdf:li>sunset</rdf:li><rdf:li>beach</rdf:li></rdf:Bag></dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""

_SINGLE = """<?xml version="1.0"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
          xmlns:xmp="http://ns.adobe.com/xap/1.0/">
  <rdf:Description xmp:Rating="3" xmp:Label="Red"/>
 </rdf:RDF>
</x:xmpmeta>
"""


def test_load_merges_fields_across_descriptions(tmp_path):
    (tmp_path / "photo.xmp").write_text(_MULTI, encoding="utf-8")
    data = load(str(tmp_path / "photo.jpg"))
    assert data.rating == 4                       # from the first Description
    assert data.keywords == ["sunset", "beach"]   # from the second -- kept


def test_load_single_description_unaffected(tmp_path):
    (tmp_path / "p.xmp").write_text(_SINGLE, encoding="utf-8")
    data = load(str(tmp_path / "p.jpg"))
    assert data.rating == 3
    assert data.color_label == "Red"
