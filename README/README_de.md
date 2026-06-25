<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  GPU-beschleunigter Bildbetrachter / Entwickler / Paint-Studio / Puppet-Animator, gebaut mit PySide6 und OpenGL
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <strong>Deutsch</strong> ·
  <a href="README_pt-BR.md">Português (BR)</a> ·
  <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <a href="https://imervue.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/imervue/badge/?version=latest" alt="Documentation Status"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Installation](#installation)
- [Verwendung](#verwendung)
- [Imervue — Bildbetrachter & Bibliothek](#imervue--bildbetrachter--bibliothek)
- [Modify — Nicht-destruktive Entwicklung](#modify--nicht-destruktive-entwicklung)
- [Paint — Vollwertiger Raster-Editor](#paint--vollwertiger-raster-editor)
- [Puppet — 2D-Rigged-Animation](#puppet--2d-rigged-animation)
- [Desktop Pet — rahmenloses Overlay](#desktop-pet--rahmenloses-overlay)
- [Tastatur- und Maus-Shortcuts](#tastatur--und-maus-shortcuts)
- [Menüstruktur](#menüstruktur)
- [Plugin-System](#plugin-system)
- [MCP-Server](#mcp-server)
- [Mehrsprachigkeitsunterstützung](#mehrsprachigkeitsunterstützung)
- [Benutzereinstellungen](#benutzereinstellungen)
- [Architektur](#architektur)
- [Lizenz](#lizenz)

---

## Überblick

Imervue ist eine GPU-beschleunigte Bildworkstation, die **fünf Top-Level-Tabs** mitbringt:

| Tab | Funktion |
|---|---|
| **Imervue** | Durchsuchen, Anzeigen, Organisieren, Suchen und Stapelverarbeiten Ihrer Bildbibliothek |
| **Modify** | Nicht-destruktive Entwicklungspipeline — Slider, Kurven, LUTs, Masken, Retusche, Mehrbildoperationen |
| **Paint** | Vollwertiges Raster-Paint-Studio mit Brushes, Layern, Animation, Manga-Tools, PSD-I/O |
| **Puppet** | Von Grund auf entwickelter 2D-Rigged-Puppet-Animator — Meshes, Deformer, Parameter, Motions, Physik |
| **Desktop Pet** | Rahmenloses, transparentes Always-on-Top-Overlay, das jedes `.puppet`-Rig als Desktop-Begleiter laufen lässt |

Designprinzipien:

- **Performance zuerst** — GPU-beschleunigtes Rendering mit modernen GLSL-Shadern und VBO
- **Unterstützung großer Sammlungen** — Virtualisiertes Tile-Grid lädt nur sichtbare Thumbnails
- **Flüssige Erfahrung** — Asynchrones, mehrthreadiges Bildladen mit Prefetching
- **Nicht-destruktive Entwicklung** — Jede Anpassung lebt in einem Rezept pro Bild; die Datei auf der Festplatte wird erst überschrieben, wenn Sie explizit exportieren
- **Erweiterbar** — Vollständiges Plugin-System mit Lifecycle- / Menü- / Bild- / Input-Hooks; der MCP-Server stellt Qt-freie Pure-Logic-Tools für KI-Assistenten bereit

---

## Installation

### Voraussetzungen

- Python >= 3.10
- GPU mit OpenGL-Unterstützung (Software-Rendering-Fallback verfügbar)

### Installation aus dem Quellcode

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### Installation als Paket

```bash
pip install .
```

### Abhängigkeiten

| Paket | Zweck |
|---------|---------|
| PySide6 | Qt6-GUI-Framework |
| qt-material | Material-Design-Theme |
| Pillow | Bildverarbeitung |
| PyOpenGL | OpenGL-Bindings |
| PyOpenGL_accelerate | OpenGL-Performance-Optimierung |
| numpy | Array-Operationen und Thumbnail-Cache |
| rawpy | RAW-Bilddekodierung |
| imageio | Bild-I/O |
| imageio-ffmpeg | Slideshow-MP4-Export (H.264 via ffmpeg) |
| defusedxml | Sicheres XML-Parsing (XMP-Sidecars) |

Optional (Feature-Gated; weglassen, um das Feature sauber zu deaktivieren):

| Paket | Zweck |
|---------|---------|
| open_clip_torch + torch | CLIP-Semantiksuche (Bildabfragen in natürlicher Sprache) |
| onnxruntime | Real-ESRGAN AI-Upscale / CLIP-ONNX-Auto-Tag |
| opencv-python | HDR-Merge, Panorama-Stitch, Focus-Stacking, Gesichtserkennung, Healing-Brush |
| sounddevice | Puppet-Lip-Sync per Mikrofon |
| mediapipe | Puppet-Webcam-Gesichtserkennung |

---

## Verwendung

### Einfacher Start

```bash
python -m Imervue
```

### Ein bestimmtes Bild oder einen Ordner öffnen

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### Kommandozeilen-Optionen

| Option | Beschreibung |
|--------|-------------|
| `--debug` | Debug-Modus aktivieren |
| `--software_opengl` | Software-OpenGL-Rendering verwenden (setzt `QT_OPENGL=software` und `QT_ANGLE_PLATFORM=warp`) |
| `file` | (Positionsargument) Beim Start zu öffnende Bilddatei oder Ordner |

---

## Imervue — Bildbetrachter & Bibliothek

Der **Imervue**-Tab ist die Standard-Landing-Surface. Er kombiniert den Bildbetrachter mit Ordnerbaum, EXIF-Sidebar und Bibliotheks-/Organisationstools.

### Viewer

- **GPU-beschleunigtes Rendering** via OpenGL (GLSL-1.20-Shader mit VBO)
- **Deep-Zoom-Pyramide** — mehrstufige Tiles mit 512×512 und LANCZOS-Resampling, LRU-Cache bis zu 256 Tiles / 1,5 GB VRAM-Budget, anisotrope Filterung bis 8×
- **Asynchrones Laden** — Mehrthreadiges Dekodieren mit ±3 Bildern Prefetch
- **Virtualisiertes Thumbnail-Grid** — Nur sichtbare Tiles werden gerendert; Thumbnail-Größe konfigurierbar (128 / 256 / 512 / 1024 / auto)
- **Festplatten-Cache** — Komprimierte PNG-Thumbnails mit MD5-basierter Invalidierung unter `%LOCALAPPDATA%/Imervue/cache/thumbnails` (oder `~/.cache/imervue/thumbnails`)
- **Animations-Wiedergabe** — GIF / APNG mit Play / Pause / Einzelbild-Schritt / Geschwindigkeitssteuerung

### Browse-Modi

- **Grid** (Standard) — Virtualisiertes Tile-Grid mit Hover-Preview-Popup (500 ms Verzögerung)
- **Liste (Detail)** — Umschalten mit `Ctrl+L`; Spalten: Preview · Label · Name · Auflösung · Größe · Typ · Geändert
- **Deep Zoom** — Doppelklick auf ein Tile; weiches GPU-Pan/Zoom mit Minimap-Overlay
- **Split View** (`Shift+S`) — Zwei Bilder nebeneinander
- **Dual-Page-Reading** (`Shift+D`, `Ctrl+Shift+D` für Right-to-Left-Manga) — Doppelseiten-Reader
- **Multi-Monitor-Mirror** (`Ctrl+Shift+M`) — Sekundär-Display-Fenster
- **Theater Mode** (`Shift+Tab`) — Versteckt alle Chrome-Elemente
- **Compare-Dialog** — Side-by-Side / Overlay (Alpha-Slider) / Difference (Gain-Slider) / A|B-Split mit ziehbarem Teiler
- **Timeline- / Calendar- / Map**-Ansichten — Bibliothek nach Aufnahmedatum gruppieren, im Kalender browsen, geotaggte Aufnahmen auf Leaflet + OpenStreetMap anzeigen

### On-Screen-Overlays

- RGB-Histogramm (`H`)
- F8-OSD (Dateiname / Größe / Typ), Ctrl+F8 Debug-HUD (VRAM / Cache / Threads)
- Pixel View (`Shift+P`) — ≥ 400 % Zoom zeigt Pixelraster + Per-Pixel-RGB / HEX
- Color Modes (`Shift+M`) — Normal / Grayscale / Invert / Sepia via GLSL

### Navigation

- Pfeiltasten, Browser-artige History (`Alt+←/→`), Random-Jump (`X`)
- Cross-Folder-Navigation (`Ctrl+Shift+←/→`)
- Go-to-Image-by-Index (`Ctrl+G`)
- Fuzzy-Suche (`Ctrl+F` / `/`)
- **Command Palette** (`Ctrl+Shift+P`) — Fuzzy-Suche über alle Menüaktionen
- Auto-Loop am Ende von Ordnern
- Touchpad-Pinch-Zoom + Horizontal-Swipe zum Navigieren

### Organisation

- **Bookmarks** — Bis zu 5000 Pfade
- **Ratings** — 0–5 Sterne (`1`–`5`) + Favoriten-Herz (`0`)
- **Color Labels** — Flag-basiert rot/gelb/grün/blau/lila (`F1`–`F5`)
- **Culling** — Wie andere XMP-bewusste Foto-Manager 3-Zustands-Flag (`P` = Pick, `Shift+X` = Reject, `U` = Unflag); Filter nach Zustand; Bulk-Delete-Rejects; Auto-Cull wählt das schärfste Bild pro Near-Duplicate-Gruppe und verwirft den Rest
- **Hierarchische Tags** — Baumpfade wie `animal/cat/british`; Nachkommen werden automatisch gematcht
- **Tags & Albums** mit Multi-Tag-AND/OR-Filterung
- **Smart Albums** — Regelbasierte Abfragen speichern und mit einem Klick erneut anwenden; die Filter umfassen Endung, Auflösung & **Seitenverhältnis**, **Dateigröße**, Rating-**Unter- / Obergrenze**, Farbe, Cull, Tags (inkl. **Ausschluss**), **Kamera / Objektiv**, **Dateiname-Regex / -Glob** und **Dateialter**, plus **Export / Import** in eine portable JSON-Datei
- **Stack RAW+JPEG-Paare** — Aufnahmen mit gleichem Stamm in ein Tile zusammenfassen; RAW bleibt als Geschwister erreichbar
- **Per-Image-Notes** in der EXIF-Sidebar — Entprelltes Speichern, sitzungsübergreifend persistent
- **Staging Tray** — Ordnerübergreifender Korb, der Neustarts überlebt; Bulk-Move / Copy / Export
- **Dual-Pane File Manager** — Zweispaltige Doppelbaumansicht
- **Sessions / Workspace Layouts** — Snapshots von Tabs / Auswahl / Filter / Dock-Geometrie in `.imervue-session.json`; benannte Layouts für Browse-/Develop-/Export-Arrangements speichern
- **Macros** — Stapel von Rating- / Favorit- / Color- / Tag-Aktionen aufzeichnen / abspielen (`Alt+M` spielt das letzte Macro ab)
- **Thumbnail-Badges + Dichte** — Farbstreifen, Favorit, Bookmark, Rating-Sterne; Compact- / Standard- / Relaxed-Padding
- **Drag-out zu externen Apps** — Tile direkt in Explorer / Chrome / Discord ziehen
- **Recent Folders / Images** werden verfolgt; letzter Ordner wird beim Start automatisch wiederhergestellt

### Sortieren & Filtern

- Sortieren nach Name / Geändert / Erstellt / Größe / Auflösung (auf- oder absteigend)
- Filter nach Endung, Color Label, Rating, Tag/Album, Cull-Zustand
- **Erweiterter Filter** — Auflösung / Dateigröße / Orientierung / Modified-Date-Range
- **Multi-Tag-Filter**-Dialog mit boolescher AND-/OR-Logik

### Suche

- **Fuzzy-Dateinamensuche** mit Substring-Highlighting
- **Find Similar Images** — pHash (64-Bit DCT) mit einstellbarer Hamming-Distanz
- **Library Search** — SQLite-Multi-Root-Index mit einer kompakten Query-DSL: Keywords, Tags (inkl. Negation), Ratings, Farbe, Endung, Ort, Cull, Favoriten, Seitenverhältnis, Alter, Größe, Maße, Kamera / Objektiv sowie Dateiname-Regex / -Glob
- **Find Similar (Average Hash)** — pHash und dHash werden durch einen optionalen Average-Hash (aHash) zu einer komplementären Near-Duplicate-Metrik verbunden
- **Semantic Search (CLIP)** — Natural-Language-Queries („Golden Retriever im Schnee") über gecachte Embeddings; deaktiviert sich elegant, wenn `open_clip_torch` + `torch` nicht installiert sind
- **Auto-Tag** — Heuristische Klassifikation mit optionalem CLIP-ONNX-Upgrade

### Metadaten

- **EXIF-Sidebar** mit aufklappbaren Gruppen + Inline-0-5-Sterne-Strip
- **EXIF-Editor**-Dialog
- **Keyword-Editor** — Title / Creator / Description / Keywords, mit **Vorschlägen verwandter Tags** aus der Tag-Ko-Okkurrenz und Controlled-Vocabulary-Erweiterung (ein Blatt-Keyword wendet automatisch seine Vorfahren + Synonyme aus einem editierbaren hierarchischen Vokabular an)
- **Image-Info**-Dialog (Maße / Größe / Datums)
- **XMP-Sidecars** (`.xmp`-Companions) — Rating / Title / Description / Keywords / Color Label, bidirektionales Roundtrip zu anderen XMP-bewussten Foto-Managern (sicheres XML via `defusedxml`)
- **GPS-Geotag-Editor** — vorhandene EXIF-GPS lesen, neue Lat/Lon via piexif schreiben (JPEG)
- **Token Batch Rename** — Live-Preview-Templates wie `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata CSV / JSON** — eine Zeile pro Bild inkl. Cull / Rating / Tags / Notes

### Extra Tools (Imervue-Tab — Batch-Processing)

Aufrufbar im **Tools**-Menü; in funktionsgruppierte Untermenüs organisiert:

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer (Re-Render, um versteckte Daten zu entfernen) · Image Organizer (in Unterordner nach Datum / Auflösung / Typ / Größe sortieren) · Token Batch Rename
- **AI / Heuristic** — AI Image Upscale (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Find Duplicate Images · Find Similar Images · Auto-Tag · Face Detection (Haar Cascade)
- **Library & Metadata** — Library Search · Smart Albums · Hierarchical Tags · Export Metadata · XMP Sidecars · GPS Geotag

### Systemintegration

- Windows-Rechtsklick-Kontextmenü **Open with Imervue** (registry-basierte Dateiverknüpfung)
- Ordnerüberwachung mit `QFileSystemWatcher` (Auto-Refresh bei Änderung)
- Toast-Benachrichtigungssystem (info / success / warning / error)
- Plugin-System mit Online-Plugin-Downloader (siehe [Plugin-System](#plugin-system))

---

## Modify — Nicht-destruktive Entwicklung

Der **Modify**-Tab ist die Entwicklungsworkstation. Jede Anpassung lebt in einem **Rezept** pro Bild, das neben der Datei abgelegt wird — die Originalpixel auf der Festplatte werden erst überschrieben, wenn Sie explizit **Exportieren** oder **Speichern unter** verwenden.

### Entwicklungs-Slider

- Weißabgleich — Temperatur / Tint
- Tonale Bereiche — Schatten / Mitten / Lichter
- Belichtung / Kontrast / Sättigung / Vibrance
- Crop, Rotation, Horizontal-/Vertikal-Flip
- Alle Bearbeitungen bleiben nicht-destruktiv und gehen durch den Rezeptspeicher

### Kurven & LUTs

- **Tone-Curve-Editor** — ziehbare RGB-Kurve plus per-Kanal R / G / B mit monotone-cubic Interpolation
- **Apply .cube LUT** — beliebige Adobe-3D-LUT laden (bis 64³), trilinear interpolieren, mit Intensitäts-Slider mischen
- **Split Toning** — Flag-basiert Schatten- / Lichter-Hue + Sättigung mit Balance-Pivot

### Kreative Effekte

- **Solarize** — Tonumkehr im Dunkelkammer-Stil (Schwellwert + Mix)
- **Diffuse Glow / Orton** — Weichzeichner-Highlight-Bloom (Stärke / Radius / Highlight-Schwellwert)
- **Gradient Map** — Luminanz → Palette, mit optionalem perzeptuellem (OkLCH) Interpolationsmodus, der gesättigte Verläufe durch den Mittelpunkt hindurch lebendig hält, statt sie auszugrauen
- **Ordered Dither** — Bayer-Matrix-Quantisierung auf N Stufen (Extreme bleiben erhalten)
- **Graduated Density (Graduated Density)** — linearer ND-Verlauf nach Winkel / Härte / Offset mit optionaler Tönung, für Himmel und Vordergründe
- **Tone Equalizer (Tone Equalizer)** — unabhängige Belichtung pro Luminanzzone (Schatten bis Lichter) über eine geglättete Maske
- **Detail Equalizer (Detail Equalizer)** — Kontrast pro Frequenzband neu gewichten (feine Textur vs. grober Kontrast), über einen einzelnen Clarity-Slider hinaus
- **Filmic Tone Map (Filmic Tone Map)** — reines Reinhard- / Hable-Highlight-Rolloff mit gepivotetem Kontrast und Sättigungswiederherstellung, für kontrastreiche Einzelbelichtungen
- **Velvia (Velvia)** — luminanzgewichteter Sättigungsboost, der gedämpfte Farben verstärkt und dabei die Schatten schont
- **Film Negative (Film Negative)** — ein gescanntes Farbnegativ invertieren, die orangefarbene Filmbasis herausrechnen, mit Ausgabe-Gamma
- **Defringe (Defringe)** — violette / grüne Farbsaum-Säume chromatischer Aberration an kontrastreichen Kanten entsättigen
- **Emboss (Emboss)** — Relief aus gerichtetem Licht über einem Luminanz-Höhenfeld
- **Polar Coordinates (Polar Coordinates)** — ein Bild in eine Scheibe wickeln oder es abrollen (Tiny-Planet / Polar-Inversion)
- **Kaleidoscope (Kaleidoscope)** — einen Winkel-Keil in n-fache Symmetrie spiegeln
- **Frosted Glass (Frosted Glass)** — deterministisches seed-basiertes lokales Pixel-Streuen
- **Develop-Presets** — ein Rezept speichern und es dann komplett anwenden oder nur seine aktiven Anpassungen auf andere Bilder mergen (wobei der eigene Crop usw. jedes Bildes erhalten bleibt)

### Lokale Anpassungen

- **Brush- / Radial- / Linear-Gradient-Masken** mit pro-Maske Belichtungs- / Helligkeits- / Kontrast- / Sättigungs- / Weißabgleich-Deltas + Feder-Slider
- Masken mischen nicht-destruktiv durch die Entwicklungspipeline

### Retusche & Transformation

- **Healing Brush** — kreisförmige Spots, OpenCV-Inpainting (Telea oder Navier-Stokes)
- **Clone Stamp** — Shift+Klick auf Quelle, gefeatherter Blit zum Ziel
- **Crop / Straighten** — normalisiertes Crop-Rechteck plus Straighten unter beliebigem Winkel, das automatisch auf das größte innere Rechteck zuschneidet
- **Auto-Straighten** — Hough-Line-Horizont- / Vertikal-Detektion
- **Lens Correction** — Pure-numpy radiale Verzerrung (Barrel / Pincushion), Vignettierungsausgleich, per-Kanal chromatische Aberration
- **Noise Reduction / Sharpening** — Kantenerhaltende bilaterale Rauschunterdrückung + Unsharp-Mask-Schärfung
- **Sky / Background** — Erkannten Himmel durch Verlauf ersetzen oder Hintergrund entfernen (transparent oder weiß gefüllt); optionales `rembg` / U²-Net-Upgrade

### Mehrbildoperationen

- **HDR Merge** — Belichtungsreihen via OpenCV-Mertens-Fusion kombinieren (mit AlignMTB-Pre-Alignment)
- **Panorama Stitch** — OpenCV `Stitcher` im Panorama- oder Scans-Modus, Auto-Crop schwarzer Ränder
- **Focus Stacking** — Laplacian-Varianz-Fokuskarte + Gaussian-Blend mit optionaler ECC-Ausrichtung

### Ausgabe

- **Watermark-Overlay** — Text oder Bild, 9 Anker-Positionen, Opazität, Skalierung; nur beim Export angewendet
- **Export-Presets** — Web 1600 / Print 300 dpi / Instagram 1080 Ein-Klick-Pipelines
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF mit Qualitäts-Slider für verlustbehaftete Formate
- **Batch-Operationen** — Umbenennen, Verschieben/Kopieren, ausgewählte Bilder drehen
- **Contact Sheet PDF** — mehrseitiges Grid mit Untertiteln (A4 / A3 / Letter / Legal)
- **Web Gallery HTML** — eigenständiger Ordner mit `index.html` + JPEG-Thumbs + Inline-Lightbox
- **Slideshow MP4** — H.264-Video mit konfigurierbarer FPS / Halten pro Bild / Fade- / Dissolve- / Slide- / Wipe-Übergängen (`imageio-ffmpeg`)
- **Print Layout** — mehrseitige PDF mit konfigurierbarer Seitengröße / Orientierung / Grid / Margins / Gutter / Schnittmarken
- **Soft Proof** — ICC-Profil laden, Zielfarbraum simulieren, Out-of-Gamut-Pixel in Magenta markieren
- **Virtual Copies** — benannte Rezept-Snapshots pro Bild; zwischen Looks wechseln, ohne das Master zu verlieren

### Externe Editoren

Programme (Ihr Bildeditor / … / …) unter **File > External Editors…** registrieren und über **File > Open in External Editor** mit dem aktuellen Bild starten.

---

## Paint — Vollwertiger Raster-Editor

Der **Paint**-Tab ist ein vollwertiges Raster-Paint-Studio, das als eigenes `QMainWindow` eingebettet ist, mit Menüs, linker Tool-Leiste, kontextsensitiver Options-Bar und einer getabbten rechten Dock-Spalte. Multi-Tab-Dokumentbearbeitung — viele Zeichnungen gleichzeitig öffnen, jede mit eigenem Undo-Stack.

### Tools (27)

Brush · Eraser · Fill · Eyedropper · Rect / Lasso / Wand / Quick Select · Move · Text · Gradient · Blur · Smudge · Dodge · Burn · Sponge · Pen · Clone Stamp · Speech Bubble · Rectangle · Ellipse · Line · Polygon · Crop · Transform · Hand · Zoom

Das Dunkelkammer-Toning-Trio — **Dodge** (Aufhellen), **Burn** (Abdunkeln) und **Sponge** (Sättigen / Entsättigen) — malt lokale Tonwert- und Chroma-Anpassungen, gewichtet durch den Brush und eine Schatten- / Mitten- / Lichter-Maske.

Einzelbuchstaben-Shortcuts: `B / E / G / I / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` für Shape-Varianten.

### Brushes

Pen / Marker / Pencil / Highlighter / Spray / Calligraphy / Watercolor / Charcoal / Crayon, mit Steuerungen für Size / Opacity / Hardness / Density / Blend-Mode. Druckkurven-Editor, Brush-Tip-Aufnahme aus einer Auswahl, Import / Export von Brush-Presets.

### Layers

Vollwertiges Layer-Panel mit Thumbnails, Sichtbarkeits-Toggles, Drag-to-Reorder, Blend-Modes, Opazität, Suche, Vektor-Layern, 1-bit-Layern, **Layer-Masken** (hinzufügen / aus Auswahl / invertieren / anwenden), **Clipping-Masken**, **Layer-Effekten** (Schlagschatten / Outer Glow / Stroke). Layer-nach-Farbe-Aufteilen, Gradient-Map-Presets.

### Auswahl

Rect / Lasso / Wand / Quick-Select mit **Replace / Add / Subtract / Intersect**-Modi und Feather. **Quick Mask Mode** (`Q`) für Paint-the-Mask-Workflows. **Stroke Selection**-Dialog.

### Animation & Manga

- **Animation** — Frame-Timeline-Dock mit Snapshots, Wiedergabe, Onion-Skin-Overlay, MP4- / GIF-Export
- **Manga-Tools** — Panel Cutter · Tone Layers · Stamp Page Numbers · Speedlines (Radial / Parallel / Burst) · Action Flash · Speech-Bubble-Tool

### Filter & Ansichts-Hilfen

- **Filter** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone (jeweils mit Live-Preview-Dialog)
- **Ansichts-Hilfen** — Pixel Grid · Snap to Pixel · Snap to Edges · Onion Skin · Bleed Guides · Canvas Rotation (`Ctrl+Shift+H` dreht CCW)

### Docks (10, getabbed)

Color · Brush · Layer · Navigator · Material Library · History · Swatch · Reference · Histogram · Animation. Jedes Dock ist verschiebbar / floatbar. **Settings > Workspace Layouts** speichert und ruft benannte Anordnungen ab.

### Datei-I/O

- **PSD** (Photoshop) öffnen / speichern mit vollem Layer-Roundtrip
- Export nach PNG / JPEG / WebP, plus mehrseitiger Comic-Export nach **CBZ** oder **PDF**
- Autosave-Snapshots mit Restore-Latest

### Power-User-UX

- **Tab** schaltet alle Docks für ablenkungsfreies Malen ein/aus
- `Ctrl+Tab` zykliert Tabs
- `,` / `.` zykliert Brush-Arten
- `0`-`9` setzen Brush-Opazität in 10-%-Schritten
- `Alt+[` / `Alt+]` schalten den aktiven Layer schrittweise um
- Rechtsklick auf das Canvas öffnet ein Quick-Menü mit Undo / Redo / Select All / Deselect / Fit / 100 %
- Pro-Tab-Modified-Asterisk, Undo- / Redo-Toast-Bestätigungen, Autosave-Recovery-Prompt beim Start

`E` aus Deep Zoom sendet das aktuelle Bild direkt in einen neuen Paint-Tab.

---

## Puppet — 2D-Rigged-Animation

Der **Puppet**-Tab ist ein von Grund auf entwickeltes 2D-Rigged-Puppet-Animationssystem. Es leistet, was Live2D leistet (Mesh-Deformations-Rigs, Parameter, Motions, Physik, Expressions, Pose, Lip-Sync, Webcam-Face-Tracking), aber **ohne proprietäres SDK**, **ohne `live2d-py`** und mit einem vollständig offenen `.puppet`-Dateiformat, dokumentiert in `Imervue/puppet/FORMAT.md`.

> **Vollständige Anleitung**: [`puppet_guide.md`](../puppet_guide.md) deckt den
> End-to-End-Flow sowohl für Live-Streaming (OBS / NDI / virtuelle Kamera)
> als auch für die Animationsproduktion (Aufnahme / Timeline-Editing / MP4-
> Export) ab. Chinesische Versionen unter
> [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) und
> [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md).

### Dateiformat

`.puppet` ist ein Zip-Container:

- `puppet.json` — Manifest (Drawables, Deformer, Parameter, Motions, Pose-Gruppen, Parts, Hit-Areas)
- `textures/*.png` — Atlas-Texturen
- `motions/*.json` — Keyframe-Tracks
- `expressions/*.json` — Parameter-Overlays
- `physics.json` — Verlet-Rig-Konfiguration

JSON-basiert, menschenlesbar diff-bar, kein proprietäres Binärformat.

### Renderer

`QOpenGLWidget` mit Vertex-Array-Textured-Triangle-Drawing in draw_order, Per-Drawable-Blend-Modes (normal / additive / multiply), Pose-Group-Exklusivität, Ortho-Projektion im Image-Space, GL_REPEAT-gekacheltem Transparency-Checker-Backdrop, Wheel-Zoom + Middle-Drag-Pan. Optimiert für große Rigs — March 7th (307 Drawables / 2965 Vertex-Morphs) läuft mit 60 FPS auf der CPU.

### Authoring

- **Import PNG** → automatische Generierung eines triangulierten Grid-Meshes, das Alpha respektiert
- **Add Rotation Deformer** (Anker + Winkel) / **Add Warp Deformer** (Rows × Cols Bezier-Lattice) Toolbar-Aktionen
- **Add Parameter** → Key-Forms an Slider-Extremen via **Set Key** im Parameter-Dock setzen
- **Mesh-Editor** — Edit Mesh umschalten, um Vertices zu ziehen; Klicks innerhalb 8 px snappen auf den nächsten
- **Save As…** schreibt das gesamte Rig in ein `.puppet`-Zip

### Runtime

- **Parameter-Rig** — jeder Parameter hält eine Key-Liste, die einen Slider-Wert auf einen partiellen Deformer-Form-Snapshot abbildet; Runtime sampelt und Per-Field-Lerp
- **Motion-Playback** — Bottom-Dock mit Motion-Liste + Play / Pause / Stop / Loop / Scrub; der Curve-Sampler unterstützt `linear`-, `stepped`-, `inverse-stepped`-, `cubic-bezier`-Segmente (Newton-iteriertes Time → Param Solve); Per-Motion Fade-In / Fade-Out
- **Expressions** — Stack von `additive`- / `multiply`- / `overwrite`-Parameter-Overlays
- **Pose-Gruppen** — sich gegenseitig ausschließende Drawable-Sichtbarkeit (Waffenwechsel, Mouth-Shape-Varianten)
- **Physik** — Verlet-Pendel-Ketten für Haare / Stoff / Bänder; Input-Parameter bewegt Ketten-Anker, Schwerkraft + Dämpfung + Per-Partikel-Federn ziehen zur Ruhelage
- **Vertex-Morphs** — Cubism-style lineare Mischung zwischen Rest und ±Extrem-Deltas; vektorisiertes numpy pro Frame bei 60 FPS
- **Opacity-Keys** — parametergetriebene Alpha-Kurven; lassen Alternate-Pose-Meshes ein- / ausblenden, wenn ein Gesture-Parameter feuert

### Live-Input

- Cursor-Drag → Head-Angle-Parameter
- Auto-Blink auf einer Cosinus-Open → Close → Open-Kurve
- Mic-Lip-Sync via `sounddevice` RMS → `ParamMouthOpenY` (optionale Dep)
- Webcam-Face-Tracking via OpenCV + MediaPipe FaceMesh → Head Yaw / Pitch / Roll + Eye / Mouth Open (optionale Deps)
- Custom-Motion-Recording — erfasst Parameterwerte mit 30 Hz, während Sie Slider wackeln / der Webcam ins Gesicht schauen / Physik laufen lassen; backt in eine Linear-Segment-Motion, die zum Abspielen / Loopen / Speichern bereit ist

### Cubism-Interop

Das **Cubism Native SDK** kann eingehängt werden (vom Benutzer beigesteuerte DLL — Live2Ds Free Material License verbietet die Weiterverteilung), um beliebige `.moc3`-Modelle in ein `.puppet`-Zip zu konvertieren. Der Konverter führt einen Sample-and-Reconstruct-Sweep aus, der sowohl Vertex-Morph-Deltas als auch parametergetriebene Sichtbarkeitsübergänge erfasst, sodass Gesture-Toggles (Peace-Sign / Face Cover / Foto …) die Konvertierung unversehrt überstehen.

### Ausgabe

- **Capture frame…** speichert ein PNG des aktuellen Canvas via `glReadPixels`
- **Record…** schaltet eine 30-FPS-Frame-Loop ein, die via `imageio` als GIF / WebM / MP4 schreibt
- **Virtual camera** — stellt das Puppet-Canvas als System-Webcam bereit
- **NDI output** — sendet das Puppet als NDI-Quelle im LAN
- **VTube Studio API server** — opt-in WebSocket-API für VTS-kompatible Clients

### Live-Streaming zu OBS

Zwei unterstützte Wege. Wählen Sie A für „funktioniert einfach", B,
wenn Sie die niedrigste Latenz und beste Qualität in einem schnellen LAN
wollen.

#### A. Virtuelle Kamera (am einfachsten)

Das Puppet-Canvas erscheint als Webcam, die OBS über seine Standard-Video-Capture-Device-Quelle aufnimmt.

1. `pip install pyvirtualcam`
2. Plattform-Treiber installieren:
   - **Windows**: OBS Studio 26+ liefert den *OBS Virtual Camera*-Treiber
     mit. Nach der OBS-Installation einmal öffnen und im Panel rechts unten
     auf **Start Virtual Camera** klicken — das registriert den Treiber
     systemweit, damit `pyvirtualcam` ihn finden kann.
   - **macOS**: OBS for Mac liefert eine OBS-Virtual-Camera-System-
     Extension. Beim ersten Lauf werden Sie aufgefordert, sie unter
     Systemeinstellungen → Datenschutz & Sicherheit zu aktivieren.
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (zuerst `v4l2loopback-dkms` installieren).
3. Im Puppet-Tab Ihr Rig öffnen, dann **Output > Virtual
   camera** umschalten. Die Statusleiste zeigt den exakten Gerätenamen zum
   Auswählen.
4. In OBS: **Sources > + > Video Capture Device**, das in Schritt 3
   benannte Gerät auswählen (typischerweise *OBS Virtual Camera*).

Imervue cappt die längste Seite des Streaming-Outputs bei 1080 px, damit
Cubism-native Canvases (March 7th ist 3503×7777) nicht vom DirectShow-
Virtual-Camera-Treiber abgelehnt werden. Das Seitenverhältnis bleibt
erhalten; OBS kann bei Bedarf weiter skalieren.

##### Warum ist der Hintergrund Magenta? (und wie entferne ich ihn)

Virtuelle Kameras laufen über **DirectShow** (Windows) / **AVFoundation**
(macOS) / **v4l2loopback** (Linux). Alle drei Transports sind **nur RGB —
ohne Alpha-Kanal**. OBS' *Video Capture Device*-Quelle behandelt alles,
was die Kamera sendet, als opakes RGB, also wird in OBS genau die Farbe
angezeigt, die Imervue hinter den Charakter setzt.

Imervue wählt **Magenta `#FF00FF`** als diesen Hintergrund, weil es die
branchenübliche Chroma-Key-Farbe ist: Sie kommt in Hauttönen, Haaren oder
Augenfarben praktisch nie vor, daher kann der Chroma-Key-Schwellwert weit
offen sein, ohne in den Charakter zu schneiden.

So entfernen Sie das Magenta in OBS:

1. Rechtsklick auf die hinzugefügte *Video Capture Device*-Quelle → **Filter**
2. Im **Effect Filters**-Panel unten links → **+** → **Color Key**
3. Konfigurieren:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF` (oder R = 255 / G = 0 / B = 255)
   - **Similarity**: bei `80` beginnen, in Richtung `200–300` erhöhen,
     falls noch Magenta-Kanten sichtbar sind. Höher = aggressivere
     Entfernung.
   - **Smoothness**: `30–50` weicht die Kante auf, damit der Schnitt
     nicht hart / verpixelt wirkt.
4. Dialog schließen. OBS hängt den Filter an die Quelle, sodass beim
   nächsten Aktivieren der Virtual Camera der Chroma-Key automatisch
   angewendet wird.

Wenn der Charakter Magenta in seiner Palette hat (unüblich, aber bei
Kostüm- / Prop-Art möglich), wird der Chroma-Key diese Pixel auch
verschlucken. Wechseln Sie auf den NDI-Pfad unten — NDI trägt den Alpha-
Kanal direkt, sodass kein Chroma-Keying nötig ist.

**Troubleshooting: Ich sehe in OBS immer noch Magenta**

- Prüfen Sie, dass der Color-Key-Filter an der **Video Capture
  Device**-Quelle hängt, nicht an einer Scene. Filter an der Quelle
  reisen mit; Filter an der Scene wirken oben drauf, nachdem die Quelle
  gerendert wurde.
- Prüfen Sie, dass das HEX exakt `FF00FF` ist — `FF00FE` o.ä. erwischt
  nicht alle Magenta-Pixel.
- Drehen Sie *Similarity* auf `300` hoch, falls ein dünner Magenta-Halo
  an der Charakter-Kontur sichtbar ist. Die Kanten kommen von GL_LINEAR-
  Interpolation gegen den Magenta-Backdrop; eine breitere Similarity-
  Toleranz verschluckt sie.

#### B. NDI (niedrigste Latenz, professionell)

NDI (Newteks Network Device Interface) überträgt das Puppet mit unter
50 ms Latenz im LAN inklusive Alpha-Kanal.

1. **NDI Tools** von <https://ndi.video/tools/> herunterladen und
   installieren (enthält die NDI-Runtime).
2. `pip install ndi-python`
3. Das **obs-ndi**-Plugin in OBS installieren:
   <https://github.com/obs-ndi/obs-ndi/releases>
4. Im Puppet-Tab **Output > NDI output** umschalten. Die Statusleiste
   meldet den NDI-Quellennamen (Default *Imervue Puppet*).
5. In OBS: **Sources > + > NDI Source**, die Quelle aus Schritt 4
   auswählen.

NDI sendet bei derselben 1080-gecappten Auflösung wie Pfad A, liefert
aber RGBA — der Off-Screen-Render erzeugt einen transparenten Hintergrund
außerhalb des Charakters, NDI überträgt den Alpha-Kanal unverändert, und
OBS / vMix komponieren das Puppet direkt über Ihre Scene, ganz ohne
Chroma-Key-Pass.

#### C. Window Capture (Fallback)

OBS **Sources > + > Window Capture** kann das Imervue-Fenster direkt
greifen, ohne zusätzliche Abhängigkeiten. Geringere Qualität, und Sie
müssen das Chrome selbst wegcroppen, aber es funktioniert auf gesperrten
Maschinen, auf denen Sie keine Treiber installieren dürfen.

### Demo

Ein einsatzbereites Rig liegt unter [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — ein 307-Drawable-Cubism-Live2D-Charakter, in-tree konvertiert. Via **Open Puppet…** öffnen, dann erscheint das Rig zentriert; klicken Sie auf eine der 18 Motions (Idle-Group + Gesture-Group), um sie abzuspielen. Die Gestures umfassen Peace-Sign, Face Cover, Foto, Erröten, Dark Face, Weinen, Schwitzen, Sterne, Sternschnuppe — jede benannte Gesture, die das Rig definiert.

---

## Desktop Pet — rahmenloses Overlay

Tab 5 — das **Desktop Pet** setzt jeden `.puppet`-Charakter als rahmenloses, transparentes Overlay auf Ihren Desktop. Der Tab selbst ist das Bedienpanel; die eigentliche Figur schwebt über (oder hinter) Ihren anderen Fenstern. Alles, was Sie mit einem Rig im Puppet-Tab tun können — Motions, Expressions, Physik, Idle-Driver, Webcam- / Mic-Input — funktioniert auch hier.

### Was Sie tun können

| Feature | Funktion |
|---|---|
| Rahmenloses Overlay | Kein Window-Chrome, kein Taskbar-Eintrag — nur die Figur auf Ihrem Desktop. |
| Transparenter Hintergrund | Alles, was die Figur nicht überdeckt, zeigt den Desktop durch. |
| Drag to Move | Ziehen Sie die Figur per Linksklick an eine neue Stelle. Loslassen in der Nähe einer Bildschirmkante lässt sie bündig daran **einrasten**. |
| Click-Through-Modus | Das Pet ignoriert Ihre Maus, sodass Sie darunter weiterarbeiten können. |
| Position sperren | Friert das Pet ein, damit es durch versehentliches Ziehen nicht verrutscht. |
| Always on Bottom | Setzt das Pet hinter jedes andere Fenster — Desktop-Widget-Feeling statt Always-on-Top. |
| Hide on Fullscreen | Versteckt sich automatisch, während eine andere App (Spiel / Video / Präsentation) auf demselben Monitor im Vollbild läuft; kommt zurück, sobald der Vollbild endet. |
| Pause beim Verstecken | Das Pet hört auf zu animieren, solange es unsichtbar ist — null CPU, wenn es nicht am Bildschirm ist. |
| Größenvoreinstellungen | Klein / mittel / groß. Skaliert um den Mittelpunkt, sodass das Pet nicht über den Bildschirm springt. |
| Opacity-Slider | Blendet das Pet zwischen 10 % und 100 %, sodass es eine dezente Desktop-Verzierung sein kann. |
| Merkt sich seine Position | Ziehen Sie das Pet in Ihre Lieblingsecke; beim nächsten Start kehrt es dorthin zurück. |

### Klick-Interaktionen

- **Linksklick auf den Körper** — definiert das Rig eine Hit Area (z. B. Kopf antippen), wird die passende Motion abgespielt. Andernfalls begrüßt Sie das Pet mit einer Sprechblase.
- **Rechtsklick an beliebiger Stelle** — öffnet ein Kontextmenü mit: Pet verstecken, Live-Driver, Motion abspielen (Liste aller Motions des Rigs), Expression anwenden, Position sperren, Click-Through, Always on Bottom, Hide on Fullscreen, Sprechblase, Größe.
- **System-Tray-Symbol** — Linksklick toggelt die Sichtbarkeit, Rechtsklick zeigt Anzeigen/Verstecken, Click-Through, Open Puppet, Pet verstecken.

### Live-Driver

Wählen Sie eine beliebige Kombination aus dem Tab oder dem Rechtsklick-Menü. Jeder ist standardmäßig aus — schalten Sie nur ein, was Sie möchten.

- **Auto-Idle** — Atem + dezenter Drift, damit der Charakter lebendig wirkt.
- **Idle-Motions** — zykelt zufällig durch die Motions der Idle-Group des Rigs.
- **Auto-Blink** — natürliches zyklisches Augenschließen alle paar Sekunden.
- **Drag-Track-Head** — der Kopf folgt Ihrem Cursor.
- **Mic-Lip-Sync** — der Mund öffnet sich mit Ihrer Stimme (benötigt `sounddevice`).
- **Webcam-Tracking** — Ihr Kopf / Ihre Augen / Ihr Mund steuern die der Puppet (benötigt `opencv-python` und `mediapipe`).

### So starten Sie

1. Wechseln Sie in den **Desktop Pet**-Tab.
2. Klicken Sie auf **Load bundled March 7th**, um den mitgelieferten Charakter zu nutzen, oder auf **Open Puppet…**, um Ihre eigene `.puppet`-Datei zu wählen.
3. Aktivieren Sie **Show pet on desktop**.
4. Ziehen Sie die Figur dorthin, wo Sie sie haben möchten; wählen Sie die gewünschten Driver; passen Sie Opazität / Größe an.
5. Rechtsklicken Sie jederzeit für das Schnellaktions-Menü, oder nutzen Sie das System-Tray-Symbol, um das Pet zu verstecken, ohne den Tab zu suchen.

Alles, was Sie einstellen — Position, Driver, Opazität, Click-Through, Größe — wird zwischen den Starts gespeichert.

---

## Tastatur- und Maus-Shortcuts

### Navigation (alle Modi)

| Shortcut | Aktion |
|----------|--------|
| Pfeiltasten | Grid scrollen / Bilder wechseln (Links/Rechts in Deep Zoom) |
| Shift + Pfeil | Feines Scrollen (halber Schritt) |
| Ctrl+Shift+←/→ | Zum vorherigen / nächsten Geschwisterordner mit Bildern springen |
| Alt+← / Alt+→ | History zurück / vor |
| Ctrl+G | Zu Bild per Index springen |
| X | Zu einem zufälligen Bild springen |
| Home | Zoom und Pan auf Ursprung zurücksetzen |
| Ctrl+F oder / | Fuzzy-Such-Dialog öffnen |
| Ctrl+Shift+P | Command Palette öffnen |
| Alt+M | Letztes Macro auf aktueller Auswahl wiederholen |
| S | Slideshow-Dialog öffnen |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |

### Deep Zoom / Einzelbild

| Shortcut | Aktion |
|----------|--------|
| F | Vollbild umschalten |
| Shift+Tab | Theater-Modus umschalten (Chrome verbergen) |
| R / Shift+R | Drehen CW / CCW |
| E | Bildeditor öffnen (Modify-Tab) |
| W / Shift+W | An Breite / Höhe anpassen |
| H | RGB-Histogramm-Overlay umschalten |
| F8 / Ctrl+F8 | OSD-Overlay / Debug-HUD |
| Shift+P | Pixel View umschalten (≥ 400 % Zoom zeigt Grid + RGB) |
| Shift+M | Color-Modes zyklieren (Normal / Grayscale / Invert / Sepia) |
| B | Bookmark umschalten |
| Ctrl+C / Ctrl+V | Bild in / aus Zwischenablage kopieren / einfügen |
| 0 / 1-5 | Favorit umschalten / Quick-Rating |
| F1-F5 | Quick-Color-Label (rot / gelb / grün / blau / lila) |
| P / Shift+X / U | Cull: Pick / Reject / Unflag |
| Shift+S | Split View |
| Shift+D / Ctrl+Shift+D | Dual-Page (LTR / RTL) |
| Ctrl+Shift+M | Multi-Monitor-Mirror-Fenster |
| Delete | In Papierkorb verschieben (rückgängig machbar) |
| Escape | Deep Zoom verlassen / Vollbild verlassen |

### Animations-Wiedergabe (GIF / APNG)

| Shortcut | Aktion |
|----------|--------|
| Leertaste | Play / Pause |
| , (Komma) / . (Punkt) | Vorheriger / nächster Frame |
| [ / ] | Wiedergabegeschwindigkeit senken / erhöhen |

### Tile-Grid

| Shortcut | Aktion |
|----------|--------|
| Ctrl+L | Grid ↔ Liste umschalten |
| Hover (500 ms) | Hover-Preview-Popup |
| Delete | Ausgewählte Tiles löschen |
| Escape | Alle abwählen |

### Maus / Touchpad

| Aktion | Verhalten |
|--------|----------|
| Linksklick | Tile auswählen oder Bild öffnen |
| Linksdrag | Rechteck-Mehrfachauswahl im Grid |
| Long Press (500 ms) | Tile-Selektionsmodus betreten |
| Mitteldrag | Pan in Deep Zoom |
| Scrollrad | Zoomen oder Scrollen |
| Rechtsklick | Kontextmenü |
| Pinch | Zoomen in Deep Zoom |
| Horizontaler Swipe | Voriges / nächstes Bild |

### Paint-Tab (zusätzlich zu obigem)

| Shortcut | Aktion |
|----------|--------|
| B / E / G / I | Brush / Eraser / Fill / Eyedropper |
| V / T / U / R | Move / Text / Gradient / Rechteck-Auswahl |
| P / S / C / Z / H | Pen / Smudge / Clone / Zoom / Hand |
| Q | Quick Mask Mode umschalten |
| Tab | Alle Docks umschalten |
| Ctrl+Tab | Paint-Tabs zyklieren |
| , / . | Brush-Arten zyklieren |
| 0-9 | Brush-Opazität in 10-%-Schritten |
| Alt+[ / Alt+] | Aktiven Layer ab- / aufwärts schalten |

---

## Menüstruktur

### File

- New Window
- Open Image / Open Folder
- Recent (Ordner + Bilder)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — benannte Fenster-Layouts speichern / laden / umbenennen
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (anpassbare Bindings)
- Exit

### Tools (Extra-Tools — in 8 gruppierte Untermenüs organisiert)

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer · Image Organizer · Token Batch Rename
- **Library & Metadata** — Library Search · Smart Albums · Find Similar / Duplicate · Auto-Tag · Hierarchical Tags · Export Metadata · XMP Sidecars · GPS Geotag
- **Views** — Timeline · Calendar · Map
- **Workflow** — Culling · Staging Tray · Virtual Copies · Dual-Pane File Manager · Macros
- **Export** — Contact Sheet PDF · Web Gallery · Slideshow Video (MP4) · Print Layout
- **Develop (Non-Destructive)** — Tone Curve · .cube LUT · Split Toning · Local Adjustment Masks · Graduated Density · Velvia · Emboss · Defringe · Film Negative · Filmic Tone Map · Tone / Detail Equalizer · Polar · Kaleidoscope · Frosted Glass · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Noise Reduction / Sharpening · Healing Brush · Clone Stamp · Face Detection · Sky / Background · Crop / Straighten · Auto-Straighten · Lens Correction
- **Multi-Image** — HDR Merge · Panorama Stitch · Focus Stacking

### View / Sort / Filter / Language / Plugins / Instructions

(Standardmenüs — siehe in-App für die kompletten Optionen.)

### Rechtsklick-Kontextmenü

Navigation · Quick-Actions (Reveal / Pfad kopieren / Bild kopieren) · Transformationen · Batch-Ops · Delete · Wallpaper · Compare / Slideshow · Export · Extra-Tools · Bookmarks · Image-Info · Plugin-beigesteuerte Einträge.

---

## Plugin-System

Imervue unterstützt Third-Party-Plugins. Siehe [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) für die vollständige Referenz.

### Schnellstart

1. Einen Ordner innerhalb von `plugins/` im Projekt-Root erstellen
2. Eine Klasse definieren, die von `ImervuePlugin` erbt
3. In `__init__.py` mit `plugin_class = YourPlugin` registrieren
4. Imervue neu starten

### Hooks

| Hook | Trigger |
|------|---------|
| `on_plugin_loaded()` | Nachdem das Plugin instanziiert wurde |
| `on_plugin_unloaded()` | Beim App-Shutdown |
| `on_build_menu_bar(menu_bar)` | Nachdem die Standard-Menüleiste gebaut wurde |
| `on_build_main_tabs(tabs)` | Nachdem die vier eingebauten Tabs hinzugefügt wurden |
| `on_build_context_menu(menu, viewer)` | Beim Öffnen des Rechtsklickmenüs |
| `on_image_loaded(path, viewer)` | Nachdem ein Bild im Deep Zoom geladen wurde |
| `on_folder_opened(path, images, viewer)` | Nachdem ein Ordner im Grid geöffnet wurde |
| `on_image_switched(path, viewer)` | Beim Navigieren zwischen Bildern |
| `on_image_deleted(paths, viewer)` | Nachdem Bilder soft gelöscht wurden |
| `on_key_press(key, modifiers, viewer)` | Bei Tastendruck (True zurückgeben, um zu konsumieren) |
| `on_app_closing(main_window)` | Bevor die Anwendung schließt |
| `get_translations()` | Stellt i18n-Strings bereit |

### Plugin-Downloader

**Plugins > Download Plugins** öffnet den Online-Downloader. Source-Repo: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## MCP-Server

Imervue liefert einen eingebauten [Model Context Protocol](https://modelcontextprotocol.io)-Server mit, sodass KI-Assistenten (Claude Code / Desktop, Cursor, Cline, …) ohne laufende GUI in die Pure-Logic-Helfer des Projekts aufrufen können. Qt-frei; ein Kommando:

```sh
python -m Imervue.mcp_server
```

### Tools

Ausgewählte Tools (46 insgesamt — vollständige Liste in der Doku). Jedes Tool
bewirbt ein JSON-`outputSchema` sowie Read-only- / Destructive-`annotations`,
gibt sein Ergebnis als `structuredContent` zurück, und langlaufende Tools streamen
`notifications/progress`.

| Tool | Zweck |
|------|---------|
| `list_images` | Bilddateien in einem Ordner auflisten (rekursiv optional) |
| `read_image_metadata` / `read_xmp_tags` | Dimensionen, Format, EXIF, XMP-Sidecar (Rating, Label, Keywords) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | No-Reference-Analyse: Per-Kanal-Statistiken, Colourfulness/Entropie/Kontrast, Histogramm + Clipping, Blur-Score |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64-Vorschau, Tesseract-Text, Perceptual-Hash-Near-Duplicate-Gruppen (mit Fortschritt) |
| `convert_format` | Zwischen PNG / JPEG / WebP / TIFF / BMP konvertieren (+ optional HEIC / AVIF / JXL) |
| `apply_watermark` / `apply_frame` | Ein Text-Wasserzeichen oder einen Passepartout- / Polaroid-Rahmen + Caption einbrennen |
| `build_collage` | Bilder zu einer Grid-Montage komponieren (mit Fortschritt) |
| `crop_image` / `resize_image` / `rotate_image` | Pixel-Crop, seitenverhältniserhaltendes Resize, verlustfreies Rotate / Flip |
| `collection_stats` | Ordner-Zusammenfassung von Rating / Favorit / Color-Label / Cull |
| `search_images` | Einen Ordner mit der Smart-Album-Query-DSL filtern (Pfad / EXIF / Größe / Maße) |
| `extract_gps` / `dominant_colors` | EXIF-GPS-Koordinaten lesen (verkettet in `reverse_geocode`); Median-Cut-Farbpalette (rgb / hex / Anteil) |
| `error_level_analysis` | JPEG-Rekompressions-Manipulationskarte als PNG-Data-URI |
| `solarize_image` / `glow_image` | Eine Solarisations-Tonumkehr oder einen Diffuse-Glow-Bloom anwenden und speichern |
| `velvia_image` / `emboss_image` / `defringe_image` | Velvia-Sättigungsboost, Relief aus gerichtetem Licht, Entsättigung von Kanten-Farbsäumen |
| `film_negative_image` / `graduated_density_image` | Ein gescanntes Negativ invertieren; einen linearen Graduated-Density-Verlauf anwenden |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Filmic-Highlight-Rolloff; Belichtung pro Zone; Kontrast pro Band |
| `colormap_image` / `false_color_image` | Luminanz über eine viridis/magma/jet-Farbpalette neu einfärben; Falschfarben-Belichtungsskala |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Geordnetes Bayer-Dithering; Split-Toning von Schatten/Lichtern; Pixel-Sortierung nach Helligkeitsband |
| `polar_image` / `kaleidoscope_image` | Verzerrung zu/von Polarkoordinaten (Tiny-Planet); Spiegelung in Kaleidoskop-Segmente |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | Frosted-Glass-Streuung mit Zufallsnachbarn; CLAHE-Lokalausgleich; Clarity + Textur als Lokalkontrast |
| `reverse_geocode` / `extract_video_frame` | Offline-GPS → Stadt, ein Videoframe zu einem Standbild dekodieren |
| `puppet_from_png` / `puppet_inspect` | Ein `.puppet`-Rig aus einem PNG bauen; eines öffnen und sein Inventar zurückgeben |

### Prompts

Vier wiederverwendbare Prompts: `caption_image`, `suggest_edits`, `analyze_composition`
(saliency-getriebene Kompositionskritik) und `flag_issues` (Schärfe- + Qualitäts- +
Clipping-Triage). Prompt-Argumente sind via `completion/complete` vervollständigbar.

### Verdrahtung

Das Repository liefert eine `.mcp.json` im Root für Claude-Code-Auto-Discovery. Für Desktop / andere Clients fügen Sie dies zu `claude_desktop_config.json` (oder äquivalent) hinzu:

```json
{
  "mcpServers": {
    "imervue": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "Imervue.mcp_server"]
    }
  }
}
```

Vollständige Protokoll-Oberfläche im MCP-Abschnitt von [docs/en/index.rst](../docs/en/index.rst).

---

## Mehrsprachigkeitsunterstützung

| Sprache | Code |
|----------|------|
| English | `English` |
| 繁體中文 (Traditional Chinese) | `Traditional_Chinese` |
| 简体中文 (Simplified Chinese) | `Chinese` |
| 한국어 (Korean) | `Korean` |
| 日本語 (Japanese) | `Japanese` |

Über das **Language**-Menü umschalten. Neustart erforderlich.

Plugins können vollständig neue Sprachen via `language_wrapper.register_language()` registrieren oder Übersetzungen via `get_translations()` beisteuern. Siehe [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## Benutzereinstellungen

Gespeichert in `user_setting.json` im Arbeitsverzeichnis. Schlüsseleinträge:

| Setting | Typ | Beschreibung |
|---------|------|-------------|
| `language` | string | Aktueller Sprachcode |
| `user_recent_folders` / `user_recent_images` | list | Zuletzt geöffnet |
| `user_last_folder` | string | Beim Start automatisch wiederhergestellt |
| `bookmarks` | list | Gebookmarkte Bildpfade (max. 5000) |
| `sort_by` / `sort_ascending` | string / bool | Sortiermethode + Reihenfolge |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | Per-Image-Organisation |
| `thumbnail_size` / `tile_padding` | int | Grid-Konfiguration |
| `navigation_auto_loop` | bool | Am Ordnerende umbrechen |
| `keyboard_shortcuts` | dict | Custom-Key-Bindings |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | Layout-Persistenz |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG-Stack-Toggle |
| `external_editors` | list | Konfigurierte Editoren |
| `macros` / `macro_last_name` | list / string | Gespeicherte Macros + Alt+M-Target |

---

## Architektur

```
Imervue/
├── __main__.py              # Anwendungs-Einstiegspunkt
├── Imervue_main_window.py   # Hauptfenster (QMainWindow) — mountet die 4 Tabs
├── gpu_image_view/          # IMERVUE TAB — GPU-Viewer + Deep Zoom
├── gui/                     # Dialoge und Seitenpanels (Develop, EXIF usw.)
├── paint/                   # PAINT TAB — vollwertiger Raster-Editor
├── puppet/                  # PUPPET TAB — 2D-Rigged-Puppet-Animator
├── export/                  # Export-Generatoren (Contact Sheet, Web Gallery, MP4)
├── image/                   # Bild-Utilities (Pyramide, Tile-Manager, Info)
├── library/                 # Library-Helfer (RAW+JPEG-Stacks, Indexing)
├── macros/                  # Macro-Aufnahme / -Wiedergabe
├── menu/                    # Menü-Definitionen (file / tools / filter / …)
├── mcp_server/              # Model-Context-Protocol-stdio-Server
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # Externe-Editor-Integration
├── plugin/                  # Plugin-System (Base / Manager / Downloader)
├── sessions/                # Workspace-Serialisierung
├── system/                  # Windows-Dateiverknüpfung
└── user_settings/           # Persistente User-Config
```

### Rendering-Pipeline (Imervue-Tab)

1. `GPUImageView` erbt von `QOpenGLWidget`
2. Zwei GLSL-1.20-Programme (textured Quads + Solid-Color-Rechtecke)
3. LRU-Texture-Cache — 256-Tile-Limit, 1,5 GB VRAM-Budget
4. Multi-Level-Tile-Pyramide gebaut mit LANCZOS bei 512 × 512 Tile-Größe
5. Anisotrope Filterung bis zu 8×, wenn die Hardware es unterstützt
6. Software-Rendering-Fallback bei fehlgeschlagener Shader-Kompilation

### Thumbnail-Cache

- **Key**: MD5 von `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
- **Format**: Komprimiertes PNG (`compress_level=1` — schneller Write, kleiner Footprint)
- **Location**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) oder `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidierung**: Automatisch bei Änderung der Datei-Metadaten

### Puppet-Rendering (Puppet-Tab)

- `QOpenGLWidget` mit `glDrawElements` + clientseitigen Vertex-Arrays
- Pro Drawable: Rest-Vertices als float32-numpy gecached; Vertex-Morphs vektorisiert; topologischer Deformer-Sort aus der Per-Drawable-Loop herausgehoben
- Transparency-Backdrop ist eine 2×2 GL_REPEAT-gekachelte Textur (vor der Optimierung waren es 100k+ Immediate-Mode-Quads)
- Cubism-Converter produziert opacity_keys-Kurven neben Vertex-Morph-Deltas, sodass parametergetriebene Sichtbarkeitsübergänge die `.moc3 → .puppet`-Konvertierung überleben

---

## Lizenz

Dieses Projekt ist unter der [MIT License](../LICENSE) lizenziert.

Copyright (c) 2026 JE-Chen
