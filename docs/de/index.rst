Imervue-Benutzerhandbuch
========================

Eine GPU-beschleunigte Bild-Workstation, die **fünf Hauptregisterkarten** bereitstellt.
Der Großteil dieses Handbuchs ist um diese fünf Abschnitte herum strukturiert.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Tab
     - Funktion
   * - **Imervue**
     - Bildbibliothek durchsuchen, anzeigen, organisieren, durchsuchen und in
       Stapeln verarbeiten. Siehe *Bilder öffnen*, *Bilder durchsuchen* und *Bilder organisieren*.
   * - **Modify**
     - Nicht-destruktive Entwicklungs-Pipeline — Schieberegler, Kurven, LUTs,
       Masken, Retusche, Multi-Bild. Siehe *Bilder bearbeiten (Modify-Tab)*.
   * - **Paint**
     - Voll ausgestattetes Raster-Mal-Studio mit Brushes, Layern, Animation,
       Manga-Werkzeugen, PSD-I/O. Siehe *Paint-Arbeitsbereich (Paint-Tab)*.
   * - **Puppet**
     - Von Grund auf neu entwickelter 2D-Rigging-Puppet-Animator — Meshes,
       Deformer, Parameter, Motions, Physik. Siehe *Puppet-Arbeitsbereich (Puppet-Tab)*.
   * - **Desktop Pet**
     - Rahmenloses, transparentes Always-on-Top-Overlay, das dieselben
       ``.puppet``-Rigs auf Ihrem Desktop mit Live-Treibern (Idle / Blink / Mic /
       Webcam / Drag-Track) laufen lässt. Siehe *Desktop-Pet-Arbeitsbereich (Desktop-Pet-Tab)*.

Die Abschnitte *Erste Schritte*, *Tastenkürzel-Referenz*, *Extra-Tools-Menü-Referenz*,
*Plugin-System*, *Kommandozeilen-Verwendung* und *MCP-Server* sind übergreifend — sie gelten
für alle fünf Tabs.

**Puppet** und **Desktop Pet** sind optional: Schalten Sie einen der beiden unter ``File`` > ``Preferences`` > **Optional tabs** aus, dann wird ab dem nächsten Start sein Tab nicht angelegt und sein Code nicht geladen, sodass Imervue schneller startet und weniger Speicher braucht. Beide sind standardmäßig an; jeder wird erst beim ersten Öffnen seines Tabs aufgebaut, der Desktop-Pet-Tab schon beim Start, wenn sein Pet beim Start erscheinen soll.

.. contents:: Inhaltsverzeichnis
   :depth: 2
   :local:

----

Erste Schritte
--------------

Wenn Sie Imervue öffnen, sehen Sie drei Bereiche:

::

   +------------+----------------------+----------+
   |  Ordner-   |                      |   EXIF-  |
   |  baum      |   Bildbetrachter     | Seiten-  |
   |            |                      |  leiste  |
   +------------+----------------------+----------+

- **Links**: Ordnerbaum. Klicken Sie auf einen Ordner, um die darin enthaltenen Bilder zu durchsuchen.
- **Mitte**: Bildanzeigebereich. Zeigt alle Bilder als Miniaturansicht-Raster an.
- **Rechts**: EXIF-Seitenleiste, beim Start zu einem schmalen Streifen eingeklappt: Klicken Sie darauf, um sie zu öffnen. Sie zeigt die Aufnahmeinformationen des geöffneten Bildes an.

Imervue schreibt das Protokoll jeder Sitzung in ``imervue.log`` neben dem Programm (in ``%LOCALAPPDATA%\Imervue`` bzw. außerhalb von Windows in ``~/.cache/imervue``, wenn dieser Ordner schreibgeschützt ist). Das Protokoll der vorherigen Sitzung bleibt als ``imervue.previous.log`` erhalten, sodass nach einem Absturz das Protokoll, das ihn erklärt, noch vorhanden ist, sobald Imervue wieder läuft — hängen Sie beim Melden eines Problems beide an.

----

Bilder öffnen
-------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Methode
     - Vorgehen
   * - Ordner öffnen
     - ``Datei`` > ``Ordner öffnen``, dann ein Verzeichnis wählen
   * - Einzelnes Bild öffnen
     - ``Datei`` > ``Datei öffnen``, dann eine Datei wählen
   * - Drag & Drop
     - Bild oder Ordner direkt ins Fenster ziehen
   * - Aus Explorer öffnen
     - Bild rechtsklicken > ``Open with Imervue`` (Dateizuordnung erforderlich)
   * - Zuletzt geöffnete Dateien
     - ``Datei`` > ``Zuletzt verwendet`` > Zuletzt verwendete Ordner / Zuletzt verwendete Bilder, um einen Ordner oder ein Bild wieder zu öffnen

Unterstützte Formate
^^^^^^^^^^^^^^^^^^^^

- **Standard**: PNG, JPEG (.jpg, .jpeg, .jpe, .jfif, .jif), BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 / CR3 / CRW (Canon), NEF / NRW (Nikon), ARW / SRF / SR2 (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus / OM System), RW2 (Panasonic), RWL (Leica), PEF (Pentax), SRW (Samsung), 3FR (Hasselblad), IIQ (Phase One), MEF (Mamiya), MOS (Leaf), ERF (Epson), MRW (Minolta), KDC / DCR (Kodak)
- **Moderne Formate**: AVIF (eingebaut); HEIC / HEIF mit dem optionalen ``pillow-heif``; JPEG XL mit dem optionalen ``pillow-jxl-plugin``
- **Weitere**: ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (das zusammengeführte Bild) — zum Ansehen; Drehen an Ort und Stelle und anderes Zurückschreiben werden abgelehnt, Änderungen gehen über Speichern unter / Export

----

Bilder durchsuchen
------------------

Miniaturansicht-Raster-Modus
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Nach dem Öffnen eines Ordners werden alle Bilder als Miniaturansichten angezeigt.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Methode
   * - Scrollen
     - Mausrad
   * - Schwenken (Pan)
     - Mittlere Maustaste gedrückt halten und ziehen
   * - In Vollansicht wechseln
     - Linksklick auf eine Miniaturansicht
   * - Miniaturansichtgröße ändern
     - Menü ``Miniaturansichtgröße`` > 128 / 256 / 512 / 1024 wählen
   * - Miniaturansichtdichte
     - ``Miniaturansichtgröße`` > ``Dichte`` > Kompakt / Standard / Locker
   * - Hover-Vorschau-Popup
     - Cursor 500 ms auf einer Miniaturansicht ruhen lassen für eine größere Vorschau
   * - Mehrere Bilder auswählen
     - Linksklicken und ziehen, um ein Auswahlrechteck aufzuziehen
   * - Mit der Tastatur zwischen Miniaturansichten wechseln
     - Pfeiltasten bewegen einen Fokusrahmen und scrollen ihn in den sichtbaren Bereich; ``Enter`` öffnet das Bild

Jede Miniaturansicht zeigt Status-Badges: einen farbigen Streifen am linken Rand (Farbetikett),
ein Herz oben links (Favorit), einen Stern oben rechts (Lesezeichen) und Bewertungssterne
unten links. Für noch ladende Miniaturansichten wird ein Spinner-Platzhalter gezeichnet.

Listenmodus (Detailansicht)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Drücken Sie ``Ctrl + L``, um zwischen Miniaturansicht-Raster und einer sortierbaren Listenansicht
mit folgenden Spalten umzuschalten: Vorschau · Etikett · Bewertung · Name · Auflösung · Größe · Typ · Geändert.
Doppelklicken Sie eine Zeile (oder drücken Sie ``Enter``), um Deep Zoom zu öffnen; ``Esc`` führt
zurück zur Liste. Miniaturansichten und Metadaten werden in einem Worker-Thread verzögert geladen,
sodass auch sehr große Ordner reaktionsfähig bleiben.

``Delete`` entfernt die markierten Zeilen und ``Ctrl + Z`` holt sie zurück, und die Tasten für Bewertung (``1`` – ``5``), Favorit (``0``), Culling (``P`` / ``Shift + X`` / ``U``) und Farbe (``F1`` – ``F5``) markieren sie, wie im Grid; alle außer ``F1`` – ``F5`` folgen den Tastenkürzel-Einstellungen.

Deep-Zoom-Modus
^^^^^^^^^^^^^^^

Klicken Sie auf eine Miniaturansicht, um in den Deep-Zoom-Modus für hochwertige Einzelbildbetrachtung zu wechseln.

Auch Panoramen weit über Pillows Sicherheitsgrenze von 179 Megapixeln öffnen sich: Die Grenze richtet sich nach dem Arbeitsspeicher (bei 16 GB etwa 1,4 Gigapixel), und solche Riesen werden nacheinander dekodiert.

Ein abgeschnittenes JPEG, PNG, TIFF, GIF oder BMP — ein abgebrochener Download oder Kopiervorgang, ein von einer defekten Speicherkarte gerettetes Foto — öffnet sich wie im Browser mit dem gelesenen Teil, statt gar nicht zu öffnen.

Speichert ein anderes Programm über ein Bild — ein externer Editor, direkt oder indem es eine Kopie darüber umbenennt —, zeigt der Viewer die neue Fassung: das in Deep Zoom geöffnete Bild innerhalb einer Sekunde nach dem letzten Schreibvorgang, Miniaturen im Grid und Zeilen der Liste innerhalb weniger Sekunden.

Ein 16-Bit-Graustufen-PNG oder -TIFF — ein Scan, eine Tiefenkarte, eine wissenschaftliche oder astronomische Aufnahme — und ein Gleitkomma-TIFF zeigen im Viewer, in Miniaturen, Vorschauen und Werkzeugen ihre echte Helligkeit statt fast weiß oder schwarz: 16-Bit-Werte werden über ihren ganzen Bereich skaliert, Gleitkommawerte von 0 bis 1 von Schwarz bis Weiß abgebildet und jeder andere Bereich gestreckt.

Bilder mit eingebettetem Farbprofil – Display P3 vom Handy, Adobe RGB von Kameras, CMYK sowie die Graustufenprofile, die Photoshop in Graustufenbilder einbettet, etwa Dot Gain 20 % oder Gray Gamma 1.8 – werden für Viewer und Thumbnails nach sRGB umgerechnet; ein Graustufenbild bleibt dabei ein Graustufenbild. Bilder ohne Profil oder mit sRGB werden unverändert gezeigt.

Dateien, die Windows als versteckt markiert — auch im Explorer und im Ordnerbaum ausgeblendet —, und Namen mit führendem Punkt, etwa die ``._foto.jpg``, die macOS auf Speicherkarten und Netzlaufwerken neben jedes Foto schreibt, erscheinen nicht in der Miniaturansicht, den Ordnersymbolen, den Ordnerlisten der Stapelwerkzeuge, überwachten Ordnern, Bibliotheksscans, der CLI und den Ordnerwerkzeugen des MCP-Servers; rekursive Scans überspringen versteckte Ordner wie ``$RECYCLE.BIN`` und ``.Trashes`` vom Mac. Ein absichtlich geöffnetes verstecktes Bild öffnet sich trotzdem.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Methode
   * - Heran-/Herauszoomen
     - Mausrad oder Touchpad-Pinch
   * - Schwenken
     - Mittlere Maustaste halten
   * - Vorheriges Bild
     - ``Pfeil links`` (oder auf Touchpad nach rechts wischen)
   * - Nächstes Bild
     - ``Pfeil rechts`` (oder auf Touchpad nach links wischen)
   * - Ordnerübergreifender Sprung
     - ``Ctrl + Shift + Links`` / ``Rechts`` zum vorherigen/nächsten Geschwisterordner mit Bildern
   * - Verlauf vor / zurück
     - ``Alt + Links`` / ``Alt + Rechts`` (browserähnlich)
   * - Zu Bildnummer springen
     - ``Ctrl + G``
   * - Zufälliges Bild
     - ``X``
   * - An Breite anpassen
     - ``W``
   * - An Höhe anpassen
     - ``Shift + W``
   * - Zoom zurücksetzen
     - ``Home``
   * - Zurück zu Miniaturansichten
     - ``Esc``
   * - Vollbild
     - ``F`` (erneut drücken zum Verlassen)
   * - Theatermodus
     - ``Shift + Tab`` blendet Menü / Status / Baum / Tabs aus für ablenkungsfreies Betrachten
   * - OSD-Info-Overlay
     - ``F8`` zeigt Dateiname / Größe / Typ; ``Ctrl + F8`` zeigt ein Debug-HUD (VRAM / Cache / Threads)
   * - Pixel-Ansicht
     - ``Shift + P`` — ab 400 % Zoom wird RGB / HEX unter dem Cursor angezeigt, dazu ein Pixelraster, sobald höchstens 40.000 Bildpixel auf dem Bildschirm sind
   * - Farbmodi
     - ``Shift + M`` wechselt zwischen Normal / Graustufen / Invertieren / Sepia (GLSL, nicht-destruktiv)

Geteilte Ansicht & Doppelseitenlesen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Zwei Bilder nebeneinander direkt im Hauptfenster anzeigen, ohne den Vergleichsdialog zu öffnen:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Aktion
     - Tastenkürzel
   * - Geteilte Ansicht (zwei Bilder)
     - ``Shift + S``
   * - Doppelseite (aktuell + nächstes)
     - ``Shift + D``
   * - Doppelseite, rechts nach links (Manga)
     - ``Ctrl + Shift + D``
   * - Zurück zum vorherigen Modus
     - ``Esc``

Im Doppelseitenmodus bewegen die Pfeiltasten jeweils zwei Bilder weiter. Die RTL-Variante
tauscht die beiden Panels, sodass Seite 1 rechts erscheint.

Multi-Monitor-Fenster
^^^^^^^^^^^^^^^^^^^^^

Drücken Sie ``Ctrl + Shift + M``, um auf Ihrem Zweitbildschirm ein rahmenloses zweites Fenster
zu öffnen, das das aktuell im Hauptbetrachter angezeigte Bild spiegelt. Das Hauptfenster
durchsucht unabhängig weiter — nützlich für Ausstellungen, Dual-Screen-Editier-Workflows oder
Kundenpräsentationen. Drücken Sie ``Ctrl + Shift + M`` erneut zum Schließen, oder ``Esc``
innerhalb des zweiten Fensters.

----

Bilder organisieren
-------------------

Bewertungen und Favoriten
^^^^^^^^^^^^^^^^^^^^^^^^^

Die Tasten bewerten das in Deep Zoom gezeigte Bild. Im Grid bewerten sie die markierten Miniaturen, sonst die mit den Pfeiltasten gewählte, sonst die unter der Maus – dieselben Fotos, die ein Farbetikett oder eine Culling-Markierung nehmen würde. Haben alle schon diese Bewertung, entfernt die Taste sie.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Taste
   * - Favorit umschalten
     - ``0``
   * - Mit 1 -- 5 Sternen bewerten
     - ``1`` ``2`` ``3`` ``4`` ``5`` (erneut drücken zum Löschen)

Farbetiketten (F1 -- F5)
^^^^^^^^^^^^^^^^^^^^^^^^

Farbkennzeichen, getrennt von der 1 -- 5-Sterne-Bewertung gespeichert. Nützlich für schnelle
Kategorisierung (z. B. rot = Ausschusskandidaten, grün = Auswahl, blau = zu retuschieren).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Taste
   * - Rot / Gelb / Grün / Blau / Lila
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (gleiche Taste erneut zum Löschen; bei einer
       Auswahl wird nur gelöscht, wenn jedes ausgewählte Bild diese Farbe schon hat)
   * - Stapelanwendung auf Auswahl
     - Mehrere Miniaturansichten auswählen, dann entsprechende F-Taste drücken
   * - Nach Farbe filtern
     - ``Filter`` > ``Nach Farbetikett`` > Farbe / Beliebiges Etikett / Kein Etikett wählen

Die Statusleiste zeigt einen farbigen Chip für das aktuelle Bild. Miniaturansichten zeigen
einen farbigen Streifen am linken Rand. Die **Listenansicht** hat eigene Spalten **Etikett**
und **Bewertung**, nach denen sortiert werden kann — Klick in eine Zelle der Sternespalte
setzt die Bewertung, ohne die Liste zu verlassen.

Lesezeichen
^^^^^^^^^^^

Häufig verwendete Bilder als Lesezeichen für schnellen späteren Zugriff speichern.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Methode
   * - Lesezeichen hinzufügen / entfernen
     - ``B`` im Deep-Zoom-Modus drücken
   * - Lesezeichen verwalten
     - ``Datei`` > ``Lesezeichen``

Tags und Alben
^^^^^^^^^^^^^^

Bilder mit Tags und Alben kategorisieren.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Methode
   * - Manager öffnen
     - ``T`` drücken oder ``Datei`` > ``Tags und Alben``
   * - Bild taggen
     - In Deep Zoom Rechtsklick > ``Tags``; für ausgewählte Miniaturansichten Rechtsklick >
       ``Stapeloperationen`` > ``Zu Tag hinzufügen``
   * - Zu Album hinzufügen
     - In Deep Zoom Rechtsklick > ``Alben``; für ausgewählte Miniaturansichten Rechtsklick >
       ``Stapeloperationen`` > ``Zu Album hinzufügen``
   * - Nach einzelnem Tag / Album filtern
     - ``Filter`` > ``Nach Tag`` / ``Nach Album``
   * - Multi-Tag-Filter (AND / OR)
     - ``Filter`` > ``Multi-Tag-Filter…`` — mehrere Tags oder Alben anhaken, Beliebig (OR) oder Alle (AND) wählen

Sortieren und Filtern
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Funktion
     - Menü
   * - Nach Name sortieren (natürliche Reihenfolge: ``img2`` vor ``img10``)
     - ``Sortieren`` > ``Nach Name``
   * - Nach Änderungsdatum sortieren
     - ``Sortieren`` > ``Nach Änderungsdatum``
   * - Nach Aufnahmedatum sortieren (EXIF-Zeit der Kamera; ohne sie das Änderungsdatum)
     - ``Sortieren`` > ``Nach Aufnahmedatum``
   * - Nach Dateigröße sortieren
     - ``Sortieren`` > ``Nach Dateigröße``
   * - Nach Auflösung sortieren
     - ``Sortieren`` > ``Nach Auflösung``
   * - Aufsteigend / Absteigend
     - ``Sortieren`` > ``Aufsteigend`` / ``Absteigend``
   * - Nach Erweiterung filtern
     - ``Filter`` > ``Nach Erweiterung`` > ``JPEG`` / ``PNG`` / ``RAW`` usw.
   * - Nach Bewertung filtern
     - ``Filter`` > ``Nach Bewertung``
   * - Nach Farbetikett filtern
     - ``Filter`` > ``Nach Farbetikett`` (Alle / Beliebiges Etikett / Kein Etikett / Rot / Gelb / Grün / Blau / Lila)
   * - Erweiterter Filter
     - ``Filter`` > ``Erweiterter Filter…`` — Auflösungsbereich, Dateigrößenbereich, Ausrichtung (Querformat / Hochformat / Quadrat), Änderungsdatumbereich
   * - Filter zurücksetzen
     - ``Filter`` > ``Filter zurücksetzen``

Anzeigemodus (Raster / Liste)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Den Bildbrowser zwischen Kachelraster und sortierbarer Detailliste umschalten:

- ``Ctrl + L`` — Raster ↔ Liste umschalten
- Menü: ``Miniaturansichtgröße`` > ``Anzeigemodus`` > Raster / Liste
- Im Listenmodus ist jede Spalte (inklusive Etikett) sortierbar; Doppelklick auf eine Zeile oder ``Enter`` öffnet Deep Zoom.

----

Bilder bearbeiten (Modify-Tab)
------------------------------

Wechseln Sie oben im Fenster zum **Modify**-Tab, um in den Bearbeitungsmodus zu gelangen.
Im Deep-Zoom-Modus öffnet auch Rechtsklick > ``Modify`` > ``Develop`` das aktuelle Bild hier;
``E`` (oder Rechtsklick > ``Modify`` > ``Annotate``) öffnet es stattdessen im separaten Annotationseditor.

::

   +--------+----------------------+------------+
   | Werk-  |                      |Eigenschaft.|
   | zeug-  |   Leinwand (malen)   | Brushes    |
   | leiste |                      | Entwickeln |
   +--------+----------------------+------------+

Anmerkungswerkzeuge (linkes Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Werkzeug
     - Symbol
     - Beschreibung
   * - Auswahl
     - |select|
     - Vorhandene Anmerkungen auswählen; ziehen zum Verschieben
   * - Rechteck
     - |rect|
     - Rechtecke zeichnen
   * - Ellipse
     - |ellipse|
     - Ellipsen oder Kreise zeichnen
   * - Linie
     - |line|
     - Gerade Linien zeichnen
   * - Pfeil
     - |arrow|
     - Pfeile zeichnen
   * - Freihand
     - |freehand|
     - Freie Form zeichnen
   * - Text
     - T
     - Text zum Bild hinzufügen
   * - Mosaik
     - |mosaic|
     - Ausgewählte Region pixeln
   * - Weichzeichnen
     - |blur|
     - Gauß-Weichzeichnung auf ausgewählte Region

.. |select| unicode:: U+2B1A
.. |rect| unicode:: U+25A2
.. |ellipse| unicode:: U+25EF
.. |line| unicode:: U+2571
.. |arrow| unicode:: U+2192
.. |freehand| unicode:: U+270E
.. |mosaic| unicode:: U+25A6
.. |blur| unicode:: U+25CC

.. tip::
   Drücken Sie im Modify-Tab ``Pfeil links`` / ``Pfeil rechts``, um zwischen Bildern zu wechseln, ohne den Editor zu verlassen.

Brush-Typen (rechtes Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Brush
     - Effekt
   * - Stift
     - Standard-dünne Linie, der gebräuchlichste Brush
   * - Marker
     - Dickere, halbtransparente Striche
   * - Bleistift
     - Dünne, leicht verblasste Linie
   * - Textmarker
     - Breit und stark transparent, wie ein echter Textmarker
   * - Spray
     - Verstreuter Punkt-Effekt
   * - Kalligrafie
     - Strichstärke variiert mit der Richtung
   * - Aquarell
     - Weicher, verblendeter Nasskanten-Effekt
   * - Kohle
     - Rauer, strukturierter Strich
   * - Wachsmalstift
     - Wachsige, kreideartige Textur

Zeichnungseigenschaften (rechtes Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Eigenschaft
     - Beschreibung
   * - Farbe
     - Auf den Farbtupfer klicken, um eine Zeichenfarbe auszuwählen
   * - Strichbreite
     - Schieberegler ziehen, um die Liniendicke anzupassen (1 -- 40)
   * - Deckkraft
     - Transparenz anpassen (0 % -- 100 %)
   * - Schrift
     - Schriftart für das Textwerkzeug wählen
   * - Schriftgröße
     - Textgröße anpassen (6 -- 200 px)

Bildanpassungen (rechtes Panel, unten)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Schieberegler
     - Funktion
   * - Belichtung
     - Gesamthelligkeit anpassen
   * - Helligkeit
     - Helle und dunkle Bereiche feinabstimmen
   * - Kontrast
     - Unterschied zwischen hell und dunkel anpassen
   * - Sättigung
     - Farbintensität anpassen
   * - Weißabgleich — Temperatur
     - Warm- / Kalttonverschiebung (blau → gelb); nützlich für Mischlicht oder Innenaufnahmen
   * - Weißabgleich — Tönung
     - Magenta- / Grünverschiebung; korrigiert Leuchtstoffstiche
   * - Lichter
     - Ausgefressene Lichter retten oder helle Bereiche weiter pushen
   * - Schatten
     - Details in dunklen Tonbereichen anheben oder stauchen
   * - Weiß
     - Nach rechts die hellsten Töne bis zum Weiß strecken; nach links Weiß zu einem Grau abdunkeln
   * - Schwarz
     - Nach links die dunkelsten Töne bis zum Schwarz drücken; nach rechts Schwarz zu einem blassen Grau anheben
   * - Dynamik (Vibrance)
     - Sättigungsbewusste Verstärkung — schützt Hauttöne und bereits gesättigte Farben

Diese Anpassungen sind **nicht-destruktiv**. Jeder Schieberegler schreibt in ein bildbezogenes
Edit-Recipe; mit ``Zurücksetzen`` jederzeit den Originalzustand wiederherstellen oder mit
``Rückgängig`` / ``Wiederholen`` unter den Schiebereglern einzelne Änderungen schrittweise
durchgehen. Recipes überleben Neustarts und können über den im Metadaten-Abschnitt
beschriebenen XMP-Sidecar-Workflow exportiert / synchronisiert werden.

Die Datei auf der Festplatte ändert sich nur auf Ihre Anweisung. **Apply Crop** und das **Speichern** von Anmerkungen schreiben das Ergebnis zurück in die Datei und behalten ihre EXIF-Daten (Kamera, Aufnahmedatum, GPS), XMP und DPI. Eine Kamera-RAW-, HEIC- oder animierte / mehrseitige Datei wird nie überschrieben: beim Zuschneiden werden Sie zum Export aufgefordert, beim Speichern von Anmerkungen nach einer neuen Datei gefragt. Die Einmal-Werkzeuge (CLAHE, HSL-Mixer, Fotorahmen, Auto-Begradigen …) speichern
ihr Ergebnis neben dem Original als ``photo_clahe.png``; ein erneuter Lauf speichert
``photo_clahe_1.png``, statt das letzte Ergebnis zu ersetzen. **Auto-Rotate by EXIF**, die Kopien von **Batch EXIF Strip** und **Split Pages…** nummerieren ihre Dateien genauso. Rezept und virtuelle Kopien eines Fotos bleiben bei ihm, wenn
Imervue es verlustfrei dreht (der Zuschnitt dreht mit) oder sein EXIF neu schreibt
(GPS-Geotag, EXIF-Editor); ein Rezept mit lokalen Masken, Ebenen, Linsenreflex oder
Gesichtstags bleibt bei der ungedrehten Fassung, bis sie zurückgedreht wird.

Speichern und rückgängig
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Schaltfläche
     - Beschreibung
   * - Speichern
     - Anmerkungen und Anpassungen in die Originaldatei schreiben
   * - Rückgängig
     - Letzte Aktion rückgängig machen
   * - Wiederherstellen
     - Rückgängig gemachte Aktion wiederherstellen
   * - Zurücksetzen
     - Alle Bildanpassungen löschen

----

Paint-Arbeitsbereich (Paint-Tab)
--------------------------------

Die dritte Hauptregisterkarte — **Paint** — ist ein voll ausgestatteter Mal-Arbeitsbereich
mit Multi-Tab-Dokumenten, Vektor- und Raster-Layern, Manga-Werkzeugen, Animationsframes
und PSD-Import/Export. Beim Wechsel über die Tab-Leiste wird das Bild, das der Viewer
gerade zeigt, auf die Leinwand geladen.

UX-Highlights — der Paint-Arbeitsbereich bietet einen voll ausgestatteten Brush-Größen-Cursor,
der mit dem Zoom skaliert, unterschiedliche Cursor-Symbole pro Werkzeug, ein
Transparenz-Schachbrettmuster unter der Leinwand, ein Drag-Drop-Highlight-Overlay, ein
Sternchen für geändert pro Tab, Toast-Bestätigungen für Undo / Redo, ein
Autosave-Statussegment in der Statusleiste und einen Autosave-Wiederherstellungsdialog beim
Start, der Snapshots aus einer vorherigen abgestürzten Sitzung anzeigt.

Power-User-Tastenkürzel: ``Tab`` schaltet alle Docks für ablenkungsfreies Malen um,
``Ctrl+Tab`` wechselt zwischen Tabs, ``,`` / ``.`` wechseln Brush-Typen, ``0–9`` setzen
die Brush-Deckkraft in 10-%-Schritten, ``Alt+[`` / ``Alt+]`` wechseln den aktiven Layer,
und Rechtsklick auf die Leinwand öffnet ein Schnellmenü mit Undo / Redo / Alles auswählen /
Auswahl aufheben / Einpassen / 100 %.

Der Farb-Dock zeigt jetzt einen "Transparent / keine Farbe"-Slot (Standard
BG = transparent), und Füllen + Zauberstab respektieren beide Alpha-Grenzen, sodass
gelöschte Pixel beim Neumalen nicht mehr ausbluten. Unter den Farb-Slots sitzt
ein Farbtonring um ein Sättigungs- / Helligkeitsdreieck: Ziehen auf dem Ring
wählt den Farbton, Ziehen im Dreieck die Abstufung; die HSB- / RGB-Regler und
das Hex-Feld folgen, und eine anderswo gesetzte Farbe verschiebt die Markierungen
des Farbrads. Das **Swatches-Dock** zeigt Ihre zuletzt verwendeten Farben oder eine
in der Auswahlliste darüber gewählte Palette: die eingebauten Standard, Pastel und
Manga oder eine eigene. **Als Palette speichern…** speichert die zuletzt verwendeten
Farben unter einem Namen, **Palette löschen** entfernt eine Ihrer eigenen (die
eingebauten bleiben erhalten), und ``Filter`` > ``An Swatches angleichen…`` malt in
genau den Farben neu, die das Dock zeigt.

::

   +------+----------------------+----------------+
   |Werk- |                      | Farbe · Brush  |
   |zeug- |   Leinwand (malen)   | Layer · Navig. |
   |leiste|                      | Material · …   |
   +------+----------------------+----------------+

Die vierzehn Docks auf der rechten Seite sind als Tabs in einer einzigen Spalte
gestapelt, sodass die Leinwand die volle sichtbare Höhe behält, und in drei Gruppen
gegliedert:

- **Zeichnen** — Farbe, Brush, Bucket, Swatches
- **Leinwand** — Layers, Navigator, Verlauf, Pages, Animation, Histogramm
- **Bibliothek** — Materialien, Stamps, Pose, Referenz

Jedes Dock lässt sich einzeln über das Menü ``Fenster`` ein- und ausblenden. Beliebigen
Dock-Titel ziehen, um neu anzuordnen oder ein Panel zu lösen; ``Einstellungen`` >
``Workspace-Layouts…`` merkt sich, welche Docks angezeigt werden (siehe *Workspace-Layouts*).

Werkzeugpalette (linke Leiste)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Werkzeug
     - Tastenkürzel
     - Zweck
   * - Brush
     - ``B``
     - Mit dem aktiven Brush-Typ malen
   * - Radierer
     - ``E``
     - Aktiven Layer alphabasiert löschen
   * - Füllen (Eimer)
     - ``G``
     - Flutfüllen mit Toleranz / zusammenhängend / alle Layer abtasten. Im
       Bucket-Dock füllt **Geschlossene Bereiche automatisch füllen** jeden
       geschlossenen Bereich der Linienzeichnung (des Referenz-Layers, sonst
       des aktiven) mit der Vordergrundfarbe; **Grundfarben auf neuem Layer**
       gibt jedem Bereich eine eigene flache Farbe — die Swatches-Farben,
       sofern das Dock welche zeigt — auf einem neuen Layer unter der
       Linienzeichnung und lässt die Linien und den Raum um die Zeichnung
       leer. Dunkle Linien auf weißem Papier funktionieren ebenso gut wie
       Linien auf Transparenz
   * - Pipette
     - ``I``
     - Vordergrundfarbe von der Leinwand aufnehmen
   * - Verschieben
     - ``V``
     - Aktiven Layer oder Auswahl verschieben
   * - Rechteck / Lasso / Zauberstab / Schnellauswahl
     - ``M`` / ``L`` / ``W``
     - Auswahlwerkzeuge mit Modi Ersetzen / Hinzufügen / Subtrahieren / Schnitt;
       beim Lasso rastet **Magnetisch** in der Optionsleiste den Umriss beim
       Loslassen an der stärksten Kante des Layers innerhalb von 10 px ein
   * - Text
     - ``T``
     - Klick öffnet den Dialog **Text hinzufügen** (Schrift / Größe / Farbe / Fett /
       Kursiv); der Text wird in die Pixel des Layers gezeichnet
   * - Gradient
     - ``U``
     - Linear- / Radial- / Winkel- / Diamantgradientfüllung, von der Vordergrund-
       zur Hintergrundfarbe oder entlang eines gespeicherten Verlaufs mit mehreren
       Farbstopps, gewählt unter **Farben** in der Optionsleiste; **Bearbeiten…**
       daneben legt diese Verläufe an, ändert und löscht sie (Name, Farbstopps mit
       Position und Deckkraft); sie bleiben zwischen Sitzungen erhalten
   * - Weichzeichnen / Verschmieren
     - ``R`` (Verschmieren)
     - Lokale Pixelmanipulation
   * - Dodge / Burn / Sponge
     -
     - Dunkelkammer-Toning, gewichtet durch den Brush — Dodge hellt die Mitteltöne
       auf und Burn dunkelt sie ab, Sponge entsättigt; keine Optionen
   * - Pen (Bezier)
     - ``P``
     - Vektorpfad mit Anker- / Griff-Bearbeitung; **Glätten** in der
       Optionsleiste legt statt gerader Linien eine einzige glatte Kurve durch
       alle angeklickten Punkte
   * - Klonstempel
     - ``S``
     - Alt+Klick legt die Quelle fest, dann ziehen, um mit Größe / Härte /
       Deckkraft des Brushs zu stempeln
   * - Sprechblase
     - ``Ctrl + B``
     - Rahmen aufziehen, um einen Comic-/Manga-Ballon zu zeichnen (ohne Schwanz)
   * - Rechteck / Ellipse / Linie / Polygon
     - ``Shift + R/E/I/P``
     - Vektorgrundformen mit Strich + Füllung
   * - Zuschneiden
     - ``C``
     - Freies Zuschneiden — Rechteck aufziehen; beim Loslassen wird die Leinwand zugeschnitten
   * - Transformieren
     - ``Ctrl + T``
     - Acht Skalier-Griffe und ein Dreh-Griff
   * - Hand
     - ``H``
     - Leinwand mit Cursor schwenken
   * - Zoom
     - ``Z``
     - Klicken zum Heranzoomen, Alt+Klick zum Herauszoomen

Brushes
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Brush
     - Effekt
   * - Bleistift
     - Dünne, leicht texturierte Graphitlinie
   * - Stift
     - Scharfe kantenglättete Linie, der Alltags-Brush
   * - Marker
     - Breite, halbtransparente Striche, die sich aufbauen
   * - Airbrush
     - Streupunkte, die sich zu einem weichen Sprühnebel aufbauen
   * - Aquarell
     - Nasse Kante mit hellerem Inneren, wie am Rand gesammeltes Pigment
   * - Sumi
     - Tusche im Kalligrafie-Stil mit Trockenpinsel-Kanten

Wachsmalstift, Textmarker und Sumi-Kalligrafie sind Brush-Presets, die auf diesen
Arten aufbauen. Jeder Brush bietet Größe / Deckkraft / Härte / Dichte / Mischmodus im
**Brush-Dock**; die obere **Optionsleiste** bietet Größe / Deckkraft / Härte.
Der Stiftdruck des Tabletts skaliert Größe und Deckkraft des Brushs über die Kurve aus
``Einstellungen`` > ``Druckkurve…`` (Punkte ziehen, per Klick hinzufügen, per Rechtsklick
entfernen oder mit Linear / Weich / Hart beginnen); eine Maus zeichnet mit vollem Druck.
**Streuung** im Brush-Dock versetzt jeden Tupfer um bis zu den eingestellten Anteil
der Brush-Größe neben den Strich, **Farbvariation** verschiebt Farbton, Sättigung und
Helligkeit jedes Tupfers, und **Stiftneigung folgen** verschmälert die Spitze quer zu
der Richtung, in die sich ein Tablett-Stift neigt, und dreht sie mit (beim Preset
Sumi-Kalligrafie ist es eingeschaltet); ein Pixel-Art-Brush behält seine quadratische
Spitze.
``Bearbeiten`` > ``Brush-Spitze erfassen…`` verwandelt eine Auswahl in eine eigene
Brush-Spitze.
Das **Materials-Dock** listet Ihre eigenen Materialien vor den eingebauten
Rasterfolien und Texturen: Bilder im Ordner ``materials`` im Programmordner von
Imervue (ein direkter Unterordner namens ``texture``, ``tone``, ``pattern``,
``brush_tip`` oder ``pose`` ordnet sie dieser Kategorie zu) sowie die von Ihnen
erfassten Brush-Spitzen. ``Bearbeiten`` > ``Auswahl als Material speichern…``
speichert den ausgewählten Teil des sichtbaren Bildes dort unter einem Namen und
einer Kategorie Ihrer Wahl (Pixel außerhalb der Auswahl werden transparent, und ein
früheres Material gleichen Namens bleibt erhalten); es erscheint sofort im Dock.

Layer
^^^^^

Der **Layer-Dock** bietet Miniaturansichten, Sichtbarkeitsschalter, Inline-Umbenennung,
Neuanordnen mit den Buttons ↑ / ↓ (oder ``Ctrl + ]`` / ``Ctrl + [``) sowie Mischmodus +
Deckkraft des aktiven Layers. Das ``Layer``-Menü ergänzt:

- **Neu / Vektor / Duplizieren / Nach unten zusammenführen** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Masken** — Maske hinzufügen / Aus Auswahl / Invertieren / Anwenden / Löschen
  (``Ctrl + Shift + M`` fügt hinzu; ``Ctrl + Alt + Shift + M`` fügt aus Auswahl hinzu)
- **Schnittmaske** — Clipping des aktiven Layers umschalten, der dann an das Alpha
  des Layers darunter geklippt wird (``Ctrl + Alt + G``)
- **Layereffekte** — Schlagschatten · Außerer Schein · Kontur; Effekte löschen
- **Referenz-Layer** — einen Layer als die Quelle anheften, mit deren Farben der
  **Füllen**-Eimer abgleicht
- **1-Bit-Layer** — den aktiven Layer in einen binären Strichzeichnungs-Layer umschalten
- **Layer nach Farbe trennen** — einen flachen Farb-Layer in einen Layer pro Farbe
  aufteilen für einfaches Neufüllen mit dem Eimer
- **Gradient Map** — Untermenü mit Presets (Sepia / Sonnenuntergang / Cyanotype …)

Auswahlen
^^^^^^^^^

Verwenden Sie die Rechteck- / Lasso- / Zauberstab- / Schnellauswahl-Werkzeuge, dann
**Auswahl umranden…** im **Bearbeiten**-Menü, um die Auswahl in der Vordergrundfarbe
zu umranden, mit Breite und Platzierung aus dem Dialog. ``Q`` schaltet **Schnellmaske-Modus** um — mit jedem Brush in Rot malen,
um die Auswahlkante zu verfeinern, dann erneut ``Q`` drücken, um zurück zur Auswahl zu konvertieren.

Animation
^^^^^^^^^

Der **Animation-Dock** verwandelt das Dokument in einen Framestreifen:

- ``+ Frame`` speichert das auf eine Ebene reduzierte Bild als neuen Frame.
- Klicken Sie eine Frame-Miniaturansicht an, um sie in den aktiven Layer zu laden.
- ``Onion Skin`` (Ansicht-Menü) überlagert den vorherigen Frame mit niedrigem Alpha.
- ``▶ Abspielen`` durchläuft die Frames mit der gewählten FPS.
- ``Exportieren…`` speichert die Frames als animiertes GIF, WebP oder PNG — der
  gewählte Dateityp bestimmt das Format, ein Name ohne Dateityp wird zum GIF — wobei
  jeder Frame einen Takt der gewählten FPS dauert. WebP wird verlustfrei geschrieben;
  GIF reduziert jeden Frame auf 255 Farben und macht kaum sichtbare Pixel transparent.

Manga-Menü
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Aktion
     - Beschreibung
   * - Panel Cutter
     - ``Ctrl + Shift + P`` — Leinwand in ein Raster aus Comic-Panels aufteilen mit konfigurierbaren Zeilen / Spalten / Rinnen / Rahmen / Rand
   * - Tone-Layer umschalten
     - Aktiven Layer in einen Screentone- (Halbton-Punkt-) Layer konvertieren
   * - Seitenzahlen stempeln
     - Seitenzahlen über Mehrseitendokumente hinzufügen
   * - Speedlines
     - Radiale / Parallele / Burst-Speedline-Generatoren
   * - Action Flash
     - Manga-Style-Explosion / Impact-Burst-Overlay
   * - Text entlang der Auswahl…
     - Legt Text entlang des Umrisses der Auswahl auf einen neuen Layer — Text, Schrift, Größe, Farbe, Fett und Kursiv kommen aus dem Dialog **Text hinzufügen**

Filter
^^^^^^

Die Filter mit nur einem Schieberegler — Tontrennung, Schwellenwert, In Halbton
konvertieren und Farbe angleichen — zeigen beim Ziehen eine Live-Vorschau auf den
mittleren 480 × 480 Pixeln des Layers in voller Größe; OK wendet den Wert auf den
ganzen Layer an. Die übrigen öffnen einen schlichten Parameter-Dialog mit OK / Abbrechen:

- **Tonwerte** — Schieberegler für Schwarzpunkt / Weißpunkt / Gamma
- **Kurven** — ein Preset (S-Kurve, Schatten anheben, Lichter komprimieren) mit einem Stärke-Schieberegler
- **Tontrennung** — Farbe in N Stufen quantisieren
- **Schwellenwert** — bei Cut-Off in reines Schwarz / Weiß konvertieren
- **Auto Color Balance** — Farbstiche per Grey-World / White-Patch neutralisieren
- **Filmkorn** — Luminanzrauschen mit anpassbarer Größe und Menge
- **In Halbton konvertieren** — Zeitungs-Punktraster
- **Farbe angleichen** — fragt nach einem Referenzbild und gibt dem Layer dann
  dessen Farbstimmung (jeder Kanal übernimmt Mittelwert und Streuung der Referenz);
  **Stärke** blendet von unverändert bis zur vollen Angleichung
- **An Swatches angleichen** — malt jedes Pixel in der nächstgelegenen Farbe des
  Swatches-Docks neu (zuerst Farben auswählen oder importieren)

Anzeigehilfen
^^^^^^^^^^^^^

- **Pixel-Raster** (``Ctrl + Shift + '``) — Ein-Pixel-Raster bei hohem Zoom überlagern
- **An Pixel / Kanten ausrichten** — An Pixel ausrichten setzt Brush-Tupfer auf ganze Pixel; An Kanten ausrichten zieht Punkte an nahe Leinwand- oder Layer-Kanten
- **Onion Skin** — überlagert den vorherigen Animations-Frame
- **Beschnittlinien** — Druck-Beschnitt- / Sicherheitszonen-Linien
- **Leinwand drehen** (``Ctrl + Shift + H``) — Ansichtsrotation ohne Rasterisierung

Datei-I/O
^^^^^^^^^

- **Neue Leinwand…** — ein neuer Tab in der gewählten Größe: ein Papier-, Manga- oder Bildschirm-Preset (A4, B5-Mangaseite, 1080p, 4K …), eines, das Sie mit **Als Preset speichern…** gespeichert haben, oder eine beliebige Breite und Höhe bis 16384 px, auf weißem oder transparentem Hintergrund (**Neuer Tab**, ``Ctrl + N``, behält den weißen Standard von 1024 × 1024 bei)
- **PSD öffnen…** (``Ctrl + O``) reduziert die Datei auf einen Layer in einem neuen Tab; **Als PSD speichern…** (``Ctrl + S``) schreibt die Layer mit ihren Mischmodi (ohne Masken oder Layereffekte)
- **Bild exportieren…** — flachlegen und als PNG, JPEG, WebP, TIFF oder BMP speichern, je nach gewähltem Dateityp (JPEG und BMP, die keine Transparenz kennen, auf Weiß). Nur **Als PSD speichern…** markiert den Tab als gespeichert; nach einem Export fragt Imervue beim Schließen weiterhin nach den ungespeicherten Änderungen des Tabs
- **Seiten exportieren → CBZ** / **→ PDF** — die Seiten eines Comic-Projekts exportieren; **Comic-Projekt speichern…** speichert den ganzen Comic, jede Seite mit ihren Layern, in einer einzigen ``.imervue-proj``-Datei, und **Comic-Projekt öffnen…** holt ihn zurück
- **Brush-Preset importieren…**, **Palette importieren…** — Brushes und Paletten aus anderen Installationen oder Anwendungen übernehmen
- **Autosave** — alle 2 Minuten wird ein Snapshot geschrieben, solange der aktive Tab ungespeicherte Änderungen hat; beim nächsten Start bietet ein Toast die Snapshots an, und **Datei > Autosave wiederherstellen** lädt den neuesten in den aktiven Tab. Die Statusleiste zeigt, wann der letzte Snapshot aufgenommen wurde, und beim Schließen von Imervue wird für Paint-Tabs mit ungespeicherten Änderungen nachgefragt.

Workspace-Layouts
^^^^^^^^^^^^^^^^^

``Einstellungen`` > ``Workspace-Layouts…`` listet die eingebauten Layouts
**Standard**, **Zeichnen**, **Comic** und **Kompakt** sowie Ihre eigenen.
**Aktuelles speichern…** speichert unter einem Namen, welche der Docks Layers /
Farbe / Brush / Navigator / Verlauf / Referenz angezeigt werden; das Anwenden
eines Layouts blendet diese Docks ein oder aus und holt das erste angezeigte nach
vorn. Werkzeugoptionen und Dock-Größen werden nicht gespeichert.

----

Puppet-Arbeitsbereich (Puppet-Tab)
----------------------------------

Die vierte Hauptregisterkarte — **Puppet** — ist ein von Grund auf neu entwickeltes
2D-Rigging-Puppet-Animationssystem: Mesh-Deformations-Rigs, Parameter, Motions, Physik,
Ausdrücke, Pose-Gruppen, Lippensynchronisation und Webcam-Tracking, **ohne proprietäres SDK**,
**ohne** ``live2d-py`` und mit einem vollständig offenen
``.puppet``-Dateiformat.

.. note::

   Das vollständige End-to-End-Tutorial — von einer frischen Installation bis zu
   einem Live-OBS-Stream oder einem gebackenen MP4 — befindet sich in
   ``puppet_guide.md`` im Repo-Wurzelverzeichnis (mit
   ``puppet_guide.zh-TW.md`` und ``puppet_guide.zh-CN.md``-Spiegeln).
   Dieser Abschnitt ist die Referenz; der Guide ist die Schritt-für-Schritt-Anleitung.

::

   +-----------+----------------------+----------------+
   | Toolbar   |                      |   Parameters-  |
   +-----------+   GL-Leinwand        |     Dock       |
   |           |                      |                |
   +-----------+----------------------+                |
   |               Motions-Dock                        |
   +---------------------------------------------------+

Die Docks rechts teilen sich einen Tab-Bereich: **Parameters** (ein Schieberegler pro Parameter), **Expressions** (jede Expression ein- oder ausschalten), **Pose** (wählen, welches Mitglied jeder Pose-Gruppe sichtbar ist — eine Gruppe zeigt ihr erstes Mitglied, bis ein anderes gewählt wird) und **Bones** (die Deformer-Hierarchie).

End-to-End-Workflow
^^^^^^^^^^^^^^^^^^^

1. **PNG importieren** — ``File`` > ``Import PNG…`` führt
   ``puppet.auto_mesh.puppet_from_png`` aus: alphabegrenztes triangulisiertes Raster,
   ein Drawable, sofort renderbar.
2. **Deformer hinzufügen** — ``Edit`` > ``Add Rotation Deformer`` (Anker + Winkel) oder
   ``Add Warp Deformer`` (Zeilen × Spalten bilineares Gitter; Vertices außerhalb der
   Grenzen werden unverändert durchgereicht).
3. **Parameter hinzufügen** — ``Edit`` > ``Add Parameter`` fügt einen Schieberegler zum rechten
   **Parameters**-Dock mit automatisch benannter ID hinzu (``Param1``, ``Param2``, …).
4. **Keys setzen** — den Schieberegler auf ein Extrem ziehen, die Form des Deformers
   im Code anpassen, **Set key** drücken. Bei neutralem und
   gegenüberliegendem Extrem wiederholen. Die Runtime interpoliert nun Deformerfelder
   zwischen benachbarten Keys, wenn der Schieberegler bewegt wird. **Set key** speichert
   nur Deformer-Formen: **Edit mesh** verschiebt die Ruhe-Vertices des Drawables
   dauerhaft, daher wird eine Mesh-Bearbeitung nicht als Key gespeichert.
5. **Speichern** — ``Save As…`` schreibt das Rig + Texturen + Motions + Ausdrücke +
   Physik in ein einzelnes ``.puppet``-Zip, das Sie teilen oder später über
   ``Open Puppet…`` öffnen können.

Ein durchgearbeitetes Beispiel ausprobieren
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Das Repository liefert ein vollständig geriggtes Demo unter
``examples/puppet/imeru.puppet`` — **Imeru**, das originale Maskottchen
von Imervue. Sie wird vollständig von ``examples/puppet/imeru/build.py``
gezeichnet und geriggt (``py -3`` erzeugt die Datei neu), sodass das Demo
keine Rechte Dritter enthält: 40 Drawables auf einer 1024 × 1336 großen
Leinwand, Kopfdrehungen aus Parallaxe-Vertex-Morphs im Live2D-Stil, auf das
Augenweiß geclippte Iriden, zweigelenkige Arme aus Rotation-Deformern und
drei Physikketten, die das Haar schwingen lassen.

Das Rig trägt jeden Cubism-Standardparameter (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …) plus
``ParamArmLA/LB/RA/RB`` für die Arme, sodass jeder Standard-Eingabetreiber
(Webcam, Blinzeln, Lippensynchronisation, Cursor-Look-At) es ohne
rigspezifische Konfiguration steuert. Acht Motions sind in der Datei
enthalten: zwei loopende Idle-Motions in der Gruppe ``Idle``, ``tap_head`` in
``TapHead`` und ``shy`` in ``TapBody`` (ein Klick auf ihren Kopf oder Körper
spielt sie ab) sowie ``greet``, ``wave``, ``surprised`` und ``sleepy`` in
``Gesture``; dazu kommen sieben Expressions (smile, happy, surprised, sad,
angry, blush, sleepy).

Öffnen Sie den Puppet-Tab, klicken Sie **Open Puppet…**, zeigen Sie auf
``imeru.puppet`` — die Figur erscheint zentriert. Ziehen Sie einen
beliebigen Parameter-Schieberegler, um ein Gelenk zu bewegen, oder klicken
Sie eine der Motions im Motions-Dock — Einzelklick bindet die Motion und
startet sofort die Wiedergabe.

**Das mitgelieferte Beispiel ausführen, Schritt für Schritt:**

1. Imervue starten. Aus dem Quellcode: ``python -m Imervue``. Aus dem
   gepackten Build: die ausführbare Datei / App-Bundle ``Imervue`` ausführen.
   Das ``examples/``-Verzeichnis ist in die Nuitka- und PyInstaller-Builds
   gebündelt; eine pip- / Wheel-Installation enthält es nicht (in einem
   Quellcode-Checkout liegen die Rigs in ``examples/puppet/``).
2. Klicken Sie oben im Fenster auf den **Puppet**-Tab.
3. **File > Examples > Imeru** (oder die **Examples ▾**-Dropdown
   in der Toolbar). Das Rig wird zentriert geladen und der
   Parameter-Dock füllt sich mit seinen Schiebereglern.
4. Im unteren **Motions**-Dock einen beliebigen Motion-Eintrag einzeln klicken
   (``idle_look``, ``wave``, ``tap_head`` …).
   Die Wiedergabe beginnt sofort; erneutes Klicken startet sie neu, die
   **Stop**-Schaltfläche des Docks stoppt die Wiedergabe, und die Wahl einer
   anderen Motion blendet zu ihr über.
5. Schalten Sie die Live-Eingabeschalter in der Toolbar um, um das Rig
   aus Ihren eigenen Eingaben zu steuern — **Drag-track head**, damit sich
   Kopf und Augen zum Cursor drehen, während er sich über die Leinwand
   bewegt, **Auto-blink** für zyklisches Augenschließen,
   **Auto idle** + **Idle motions** für Atmung + zufällige Idle-Clips,
   **Mic lip-sync** für Mundöffnung aus Mikrofon-RMS, **Webcam tracking**
   für vollständigen Kopf + Augen + Mund vom MediaPipe FaceLandmarker.
6. **Reset to rest** in der Toolbar stoppt jede Motion, schaltet jeden
   Live-Treiber ab, löscht Ausdrücke / Pose-Overrides und setzt jeden
   Parameter auf seinen Standard zurück — die kanonische
   "Von vorne anfangen"-Aktion.
7. Um später ein anderes Rig zu öffnen: **File > Open Puppet…** wählt ein
   beliebiges ``.puppet``-Zip von der Festplatte; **File > Examples ▾**
   bleibt an die mitgelieferte Liste gebunden.

``.puppet``-Dateiformat (v1)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Eine ``.puppet``-Datei ist ein Zip-Archiv:

::

   my_character.puppet
   ├── puppet.json              # erforderlich — Manifest, Drawables, Deformer, Parameter
   ├── textures/
   │   ├── face.png             # referenziert durch drawables[].texture
   │   └── body.png
   ├── motions/                 # optional
   │   ├── idle.json
   │   └── wave.json
   ├── expressions/             # optional
   │   └── smile.json
   └── physics.json             # optional

Beispiel ``puppet.json`` auf Top-Level::

   {
     "version": 1,
     "size": [2048, 2048],
     "drawables": [ ... ],
     "deformers": [ ... ],
     "parameters": [ ... ],
     "motions": ["idle", "wave"],
     "expressions": ["smile"],
     "pose": {"groups": [ ... ]},
     "physics": "physics.json"
   }

Die vollständige Spezifikation (Drawables, Deformer, Parameter, Motions, Ausdrücke,
Pose, Physik) liegt unter ``Imervue/puppet/FORMAT.md`` im Repo. Nur JSON +
PNG — kein proprietäres Binärformat, vollständig diff-fähig via git.

Das Format ist offen und maschinell prüfbar:

- Ein gespeichertes ``.puppet`` beginnt mit einem unkomprimierten ``mimetype``-Eintrag,
  der ``application/vnd.imervue.puppet+zip`` enthält, sodass ein Programm es an
  seinen ersten Bytes erkennen kann, und jede JSON-Datei nennt ihr JSON Schema in ``$schema``.
- Vier JSON Schemas (Draft 2020-12) — ``puppet``, ``motion``, ``expression``
  und ``physics`` — sind in ``docs/schemas/`` veröffentlicht; Editoren, die
  ``$schema`` folgen, prüfen eine Datei schon während der Eingabe.
- ``py -m Imervue.cli puppet-validate character.puppet`` (MCP
  ``puppet_validate``) prüft eine Datei gegen die Schemas, die Regeln des Loaders
  und die Rig-Prüfungen; ``puppet-schema`` (MCP ``puppet_schema``) gibt ein Schema aus.
- ``docs/examples/read_puppet.py`` liest ein ``.puppet`` allein mit der
  Python-Standardbibliothek, als Referenz für andere Programme; die Spezifikation und
  die Schemas stehen unter der MIT-Lizenz, sodass jedes Programm das Format lesen
  oder schreiben darf.
- Eine Datei mit einer neueren Formatversion wird unter Angabe der verwendeten Version
  abgelehnt, sodass ein älteres Imervue zum Aktualisieren auffordert, statt sie falsch
  zu lesen.

Toolbar-Referenz
^^^^^^^^^^^^^^^^

Die Toolbar enthält **Examples ▾**, die sechs Live-Schalter, **Edit mesh**,
**Record…** und **Reset to rest**. Jeder andere Eintrag unten ist ein Punkt
des Menüs **File**, **Edit**, **Live**, **Output** oder **Tools**; diese
Menüs enthalten auch die Einträge der Toolbar.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Zweck
   * - Open Puppet… / Examples ▾
     - Ein ``.puppet`` von der Festplatte laden (Menü **File**), oder eines der
       unter ``examples/puppet/`` gebündelten Rigs über **Examples ▾** wählen
       (die Toolbar-Schaltfläche, auch unter **File**)
   * - Import PNG… / Import PSD… / Import Cubism…
     - Auto-Mesh einer PNG, Layer-Aufspaltung einer PSD, oder
       Sample-and-Reconstruct eines Cubism-Rigs. Der Cubism-Picker akzeptiert
       sowohl ``.moc3`` als auch ``.model3.json``; ohne offenes Rig führt
       jeder Pfad die vollständige ``.moc3 → .puppet``-Konvertierung aus
       (vom Benutzer bereitgestelltes Cubism Native SDK). Wenn man
       ``.model3.json`` wählt, während ein Rig geladen ist, werden dessen
       reine JSON-Metadaten (Motions / Ausdrücke / Physik) stattdessen in
       das aktive Dokument zusammengeführt.
   * - Recent
     - Ein kürzlich geöffnetes Puppet schnell wieder öffnen
   * - Save As…
     - Das aktuelle Rig als ``.puppet``-Zip schreiben
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - Rig aus dem Menü **Edit** heraus authoring
   * - Drag-track head
     - Kopf und Augen drehen sich zum Cursor, während er sich über die
       Leinwand bewegt: Cursor-Offset → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Cosinus-Close→Open-Zyklus auf ``ParamEyeLOpen`` / ``ParamEyeROpen``
       etwa alle 4,5 s (Force-Write-Pfad umgeht das No-Change-Skip der
       Leinwand, sodass konkurrierende Treiber das Blinzeln nicht abwürgen)
   * - Mic lip-sync
     - Mikrofon-RMS → ``ParamMouthOpenY`` (benötigt ``sounddevice``)
   * - Lip-sync from Audio File…
     - Menü **Live**: eine WAV (8-, 16- oder 32-Bit-PCM) in eine Motion namens
       ``lipsync_<file>`` umwandeln, die ``ParamMouthOpenY`` mit der Lautstärke
       öffnet, 30-mal pro Sekunde (Keys ohne Beitrag werden verworfen), und die
       WAV als ihren Sound abspielt; sie ersetzt eine gleichnamige Motion und
       wird im Motions-Dock ausgewählt. Benötigt keine optionale Abhängigkeit
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → Kopf-Yaw / Pitch / Roll +
       Augen + Mund (benötigt ``opencv-python`` + ``mediapipe``;
       öffnet einen Live-Vorschau-Dialog mit erkannten Landmarken)
   * - Auto idle / Idle motions
     - Atemzyklus + Drift auf Standardparametern, plus optionaler Zufalls-
       Zykler durch Idle-Gruppen-Motions
   * - Edit mesh
     - Vertices der Leinwand per Click-and-Drag verfeinern
   * - Record motion
     - Nur im Menü **Output**: Parameteränderungen in eine neue ``Motion``
       aufnehmen und dem Dokument hinzufügen — Take backen, kein manuelles
       Key-Authoring
   * - Capture frame… / Record… / Export all motions…
     - Eine einzelne PNG speichern, eine GIF- / WebM- / MP4-Aufnahme umschalten,
       oder jede Motion im Rig in eine eigene Datei batch-rendern (alle über
       denselben Charakter-Only-Off-Screen-Renderpfad, der für das Streaming
       verwendet wird). Ein aufgenommener Frame behält die eigene Größe des
       Rigs (lange Seite höchstens 4096 px) auf transparentem Hintergrund;
       eine Aufnahme oder ein Batch-Export passt den Charakter in 1080 px auf
       Weiß ein, da GIF- / WebM- / MP4-Frames keinen Alphakanal tragen
   * - Output > Virtual camera / NDI output
     - Live-Streaming-Surfaces — siehe *Live-Streaming an OBS* unten
   * - Reset to rest
     - Den Motion-Player snap-stoppen, jeden Live-Treiber abschalten,
       Ausdrücke / Pose-Gruppen löschen, Parameter-Standards wiederherstellen
   * - Fit to Window
     - Menü **Tools**: das Puppet auf der Leinwand neu zentrieren + neu skalieren
   * - Repair Rig
     - Menü **Tools**: in jedem Drawable defekte und flächenlose Dreiecke
       verwerfen, doppelte Vertices mit gleicher Position und UV zusammenführen
       (eine Texturnaht bleibt getrennt), Vertices entfernen, die kein Dreieck
       nutzt — Bone-Weights und Vertex-Morphs folgen den verbleibenden
       Vertices — und die Bone-Weights jedes Vertex so anpassen, dass sie
       sich zu 1 summieren; die Statusleiste meldet, was sich geändert hat

Eigene Motions aufzeichnen
^^^^^^^^^^^^^^^^^^^^^^^^^^

Um eine eigene Aufnahme zu erfassen, statt Keyframes von Hand zu authoring:

1. **Output > Record motion** umschalten — ein Namensdialog erscheint.
2. Während der Aufnahme Schieberegler ziehen, **Webcam tracking** aktivieren,
   Physik laufen lassen, alles was Parameterwerte schreibt.
3. **Record motion** wieder abschalten — der Recorder bäckt den aufgenommenen
   30-Hz-Stream in eine ``Motion`` mit einem Linear-Segment-Track pro Parameter,
   der sich tatsächlich bewegt hat (Parameter, die flach blieben, werden verworfen).
   Die neue Motion erscheint sofort im unteren **Motions**-Dock, bereit zum
   Abspielen / Loopen / Speichern.

So gespeicherte eigene Motions wandern denselben JSON-``motions/<name>.json``-Payload
hin und zurück wie authorierte.

**Edit > Edit motion…** öffnet die Timeline der Motion, die der Player gerade
hält: einen Key oder ein Bezier-Handle ziehen, den gewählten Track mit **Ease**
und **Apply to Track** zu einem benannten Easing umformen (31 Kurven; elastic
und bounce werden zu 16 linearen Keys pro Segment) oder eine 30-Hz-Aufnahme mit
**Simplify Keys** ausdünnen, das jeden Key verwirft, der innerhalb der Toleranz
(ein Prozentsatz des Bereichs jedes Parameters) von der Linie durch seine
Nachbarn liegt.

Live-Streaming an OBS
^^^^^^^^^^^^^^^^^^^^^

Zwei Ausgabewege, beide rendern das Puppet allein (kein Schachbrett-Hintergrund,
kein Editor-Chrome) in einen Off-Screen-Framebuffer, bevor sie es an die
Streaming-Surface übergeben. Die Ausgabe wird auf 1080 px Langseite gedeckelt,
damit Cubism-Native-Leinwände (oft 3000–8000 px hoch) nicht von
DirectShow-Virtual-Camera-Treibern abgewiesen werden.

**A. Virtuelle Kamera** — erscheint als Webcam in der *Video-Capture-Geräte*-
Quellenliste von OBS. ``pip install pyvirtualcam`` plus plattformspezifischer
Treiber: OBS Studio 26+ liefert den *OBS Virtual Camera*-Treiber unter Windows /
macOS (in OBS einmal *Start Virtual Camera* klicken zum Registrieren); Linux
verwendet ``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
Der Menüschalter **Output > Virtual camera** öffnet den Stream.

DirectShow / AVFoundation / v4l2loopback sind nur RGB — kein Alphakanal — also
füllt Imervue den Bereich außerhalb des Charakters mit **Magenta #FF00FF** als
Chroma-Key. Entfernen Sie es in OBS über den Color-Key-Filter:

1. Rechtsklick auf die Video-Capture-Geräte-Quelle > **Filter**
2. **Effektfilter > + > Color Key**
3. **Key Color Type** = ``Custom Color``,
   **Custom Color** = HEX ``FF00FF``,
   **Similarity** = ``80–300``,
   **Smoothness** = ``30–50``

Der Filter klebt an der Quelle, sodass der Chroma-Key automatisch wieder
angewendet wird, sobald die virtuelle Kamera fortgesetzt wird.

**B. NDI-Ausgabe** — Sub-50-ms-LAN-Broadcast mit RGBA, sodass OBS / vMix
direkt über ihre eigenen Szenen ohne Chroma-Key-Pass komponieren. ``pip install ndi-python`` +
die `NDI Tools <https://ndi.video/tools/>`_-Runtime + das
`obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_-Plugin.
Der Menüschalter **Output > NDI output** sendet die Quelle (Standardname *Imervue Puppet*).

``ndi-python`` liefert nur eine Quelldistribution; pip baut es bei der
Installation aus C++. Windows-Benutzer benötigen Visual Studio Build Tools 2022
(mit C++-Workload), CMake im PATH und das NDI SDK von
<https://ndi.video/for-developers/ndi-sdk/> am Standardspeicherort installiert,
mit der Umgebungsvariable ``NDI_SDK_DIR`` darauf zeigend.

Siehe ``puppet_guide.md`` § 1.2 für die vollständige Schritt-für-Schritt-Anleitung
plus die Troubleshooting-Liste (Kamera zeigt Magenta, ndi-python-CMake-Fehler,
Virtual-Camera-Streckung usw.).

Optionale Abhängigkeiten
^^^^^^^^^^^^^^^^^^^^^^^^

* ``sounddevice`` — Mikrofonaufnahme für Lippensynchronisation
* ``opencv-python`` + ``mediapipe`` — Webcam-Gesichts-Tracking
* ``imageio-ffmpeg`` — MP4- / WebM-Aufnahme (bereits für Slideshow-Video geliefert)
* ``pyvirtualcam`` — Virtual-Camera-Ausgabe (siehe *Live-Streaming*)
* ``ndi-python`` — NDI-Ausgabe (siehe *Live-Streaming*)
* Vom Benutzer bereitgestellte Cubism Native SDK DLL — ``.moc3 → .puppet``-
  Konvertierung (Live2Ds Free Material License verbietet Weiterverteilung;
  Benutzer legen das SDK unter ``<cwd>/sdk/`` ab oder setzen die Umgebungsvariable
  ``CUBISM_CORE_DLL``)

Der Puppet-Tab degradiert elegant, wenn ein Python-Paket fehlt — der
entsprechende Schalter bleibt aus und der Abhängigkeits-Installer öffnet sich
und bietet an, es zu installieren; sobald es installiert ist, schaltet sich der
Schalter wieder ein. Ein Texthinweis erscheint nur, wenn das Paket vorhanden
ist, aber das Gerät oder der Treiber versagt.
``File > Install dependencies…`` installiert jedes optionale Python-Paket auf einen Schlag.

----

Desktop-Pet-Arbeitsbereich (Desktop-Pet-Tab)
--------------------------------------------

Tab 5 — das **Desktop Pet** stellt jede ``.puppet``-Figur als
rahmenloses, transparentes Overlay auf Ihrem Desktop dar. Der Tab
selbst ist ein Bedienpanel; die eigentliche Figur ist ein
separates Fenster auf oberster Ebene, das die gesamte
Puppet-Laufzeit teilt (Bewegungen, Ausdrücke, Physik,
Idle-Treiber, Mikrofon-/Webcam-Eingabe). Das Pet kann auf Klicks
reagieren, timergesteuerte Animationen ausführen, Ihrem Cursor
folgen, sich ausblenden, während eine andere App im Vollbildmodus
läuft, und eigene Zeilen sprechen, die Sie in einer JSON-Datei
verfassen.

Dieses Kapitel ist eine vollständige Referenz für den Tab. Es ist
wie folgt gegliedert:

#. **Schnellstart** — Fünf-Schritte-Weg von "Ich habe gerade
   Imervue geöffnet" zu "Auf meinem Desktop steht eine Puppe".
#. **Rig laden** — Dateiauswahl, mitgeliefertes Beispiel,
   Wiederherstellung zwischen den Starts.
#. **Das Overlay-Fenster** — alle Verhaltensweisen auf
   Fensterebene (Ziehen zum Verschieben, Randeinrastung,
   Click-Through, Ankerverriegelung, immer im Hintergrund,
   Ausblenden bei Vollbild, Pause beim Ausblenden, Deckkraft,
   Größe, Wiederherstellung auf mehreren Monitoren).
#. **Interaktionsmodell** — Trefferbereiche für Linksklicks, das
   vollständige Rechtsklick-Kontextmenü, System-Tray.
#. **Live-Treiber** — sieben Eingangstreiber (drei davon
   standardmäßig an) und ihre optionalen Abhängigkeiten.
#. **Pet-Skript** — die JSON-Datei, mit der Sie die Stimme des
   Pets durch eigene Zeilen ersetzen, Erinnerungen planen und
   pro Trefferbereich / pro Bewegung Antworten binden können.
#. **Persistenz** — was zwischen den Starts gemerkt wird, und
   das genaue Einstellungsschema.
#. **Ein neues Pet erstellen** — Verweis auf den Puppet-Tab und
   das ``.puppet``-Dateiformat.
#. **Fehlerbehebung** — häufige Überraschungen und was dagegen
   zu tun ist.

Schnellstart
^^^^^^^^^^^^

1. Wechseln Sie zum Tab **Desktop Pet**.
2. Klicken Sie auf **Load bundled Imeru**, um die
   mitgelieferte Figur zu verwenden, oder auf **Open Puppet…**,
   um Ihre eigene ``.puppet``-Datei auszuwählen.
3. Das Overlay erscheint auf Ihrem Desktop und das Kontrollkästchen
   **Show pet on desktop** wird automatisch aktiviert. (Wenn Sie
   das Pet einmal ausblenden möchten, ohne Imervue zu schließen,
   deaktivieren Sie das Kästchen oder verwenden Sie das
   System-Tray-Symbol.)
4. Ziehen Sie die Figur an die gewünschte Stelle. Loslassen in
   der Nähe eines Bildschirmrandes lässt sie bündig einrasten.
5. Wählen Sie die gewünschten **Live drivers** — Idle-Atmung,
   Blinzeln, Cursor-Verfolgung, Mikrofon-Lippensynchronisation,
   Webcam-Tracking — entweder im Workspace-Tab oder im
   Rechtsklick-Menü des Pets.

Alles, was Sie einstellen, übersteht den nächsten Start, sodass
Schritt 5 eine einmalige Entscheidung pro Rig / Persona ist.

Rig laden
^^^^^^^^^

Der Tab bietet drei Lademöglichkeiten:

* **Open Puppet…** — wählen Sie eine beliebige
  ``.puppet``-Datei von der Festplatte.
* **Load bundled Imeru** — öffnet das mitgelieferte Rig
  unter ``examples/puppet/imeru.puppet``. Der Resolver
  durchsucht zuerst ``examples_dir()`` (neben dem Programm in
  den paketierten Nuitka- / PyInstaller-Builds, das
  Repository-Root in einem Quellcode-Checkout) und greift auf
  eine Suche relativ zum aktuellen Arbeitsordner zurück.
* **Letztes Rig** — das zuvor geladene Rig wird beim
  Imervue-Start aus dem Einstellungsfeld ``last_rig_path``
  automatisch wiederhergestellt; der Desktop-Pet-Tab
  instanziiert das Overlay unsichtbar neu, sodass das Pet einen
  Klick entfernt im gleichen Zustand bereitsteht, in dem Sie es
  verlassen haben.

Ein erfolgreiches Laden aktiviert **Show pet on desktop**
automatisch, damit das Pet sofort erscheint. Der Fehlerpfad lässt
das Kontrollkästchen unverändert und schreibt die Fehlermeldung
in das Statuslabel des Tabs.

Das Overlay-Fenster
^^^^^^^^^^^^^^^^^^^

Die Figur lebt in einem Fenster oberster Ebene, getrennt vom
Imervue-Hauptfenster. Das Fenster ist rahmenlos, hat keinen
Taskleisten-Eintrag und bleibt (standardmäßig) über allen anderen
Fenstern.

.. list-table:: Fensterverhalten
   :header-rows: 1
   :widths: 28 72

   * - Verhalten
     - Detail
   * - Rahmenloses Overlay
     - Keine Fenster-Chrome, keine Minimieren-/Schließen-
       Schaltflächen, kein Taskleisten-Eintrag. Die Figur ist
       die gesamte sichtbare Oberfläche.
   * - Transparenter Hintergrund
     - Alles, was die Figur nicht abdeckt, ist vollständig
       transparent. Der Desktop / die App hinter dem Pet
       erscheint pixelgenau durch.
   * - Ziehen zum Verschieben
     - Mit der linken Maustaste irgendwo auf den Körper drücken,
       ziehen, loslassen. Das Ziehen wird nur dann als Klick
       erkannt, wenn sich der Cursor weniger als sechs Pixel
       bewegt hat — weitere Bewegung macht aus der Geste eine
       Verschiebung und der Klick-Handler wird nicht ausgelöst.
   * - Randeinrastung
     - Loslassen in der Nähe eines Bildschirmrandes
       (Standard: innerhalb von 24 px), und das Pet "klickt"
       bündig an diesem Rand. Der Schwellenwert ist von 0 (aus)
       bis 200 (sehr klebrig) konfigurierbar. Die Einrastung
       läuft unabhängig auf jeder Achse, sodass das Ziehen in
       eine Ecke gleichzeitig an beiden Rändern andockt.
   * - Überschuss-Klemmung
     - Ein Ziehen, das über einen Bildschirmrand hinausgeht,
       wird zurück nach innen geklemmt. Sie können das Pet
       nicht außerhalb des Bildschirms stranden lassen, wo Sie
       es nicht mehr greifen könnten.
   * - Click-Through-Modus
     - Wenn aktiviert, gehen alle Mausereignisse durch das Pet
       hindurch zu dem, was sich dahinter befindet. Die Figur
       ist weiterhin sichtbar, kann aber nicht gezogen,
       rechtsgeklickt oder zum Auslösen von Bewegungen
       verwendet werden. Aktivieren Sie diesen Modus, wenn das
       Pet rein dekorativ ist.
   * - Position sperren
     - Deaktiviert das Ziehen zum Verschieben, ohne den
       Click-Through zu beeinflussen. Nützlich, wenn Sie das
       Pet genau dorthin platziert haben, wo Sie es haben
       möchten, und versehentliche Ziehbewegungen es nicht
       verschieben sollen.
   * - Immer im Hintergrund
     - Schaltet das Pet von immer-oben auf immer-unten um. Das
       Pet sitzt hinter allen anderen Fenstern als
       Desktop-Widget. Deaktiviert außerdem das
       Fokus-Akzeptanz-Flag, damit ein Klick auf das Pet es
       nicht nach vorne holt.
   * - Bei Vollbild ausblenden
     - Eine 1-Hz-Hintergrundabfrage beobachtet das
       Vordergrundfenster auf dem Monitor des Pets. Wenn dieses
       Fenster ≥ 99 % des Bildschirms mit einer
       Pro-Rand-Toleranz von ≤ 4 px abdeckt (was sowohl
       echtes Vollbild als auch randlose Fenstermodus-Spiele
       erfasst), blendet sich das Pet automatisch aus. Wenn der
       Vollbildmodus endet, erscheint das Pet wieder an seiner
       vorherigen Position. Der Detektor verwendet unter
       Windows die Win32-API ``GetWindowRect``; unter macOS /
       Linux ist er ein Leerlauf (das Pet bleibt sichtbar).
   * - Pausiert beim Ausblenden
     - Der ~30 FPS Paint-Tick, der 1-Hz-Skript-Tick und die
       Vollbild-Abfrage (außer wenn das Vollbild das Pet
       ausgeblendet hat) halten bei ``hideEvent`` an und starten
       beim nächsten ``showEvent`` neu. Die Timer der
       Live-Treiber (Blinzeln, Idle, Idle-Bewegungen, Blick)
       laufen weiter.
   * - Größen-Voreinstellungen
     - Klein (200 × 300), Mittel (320 × 480), Groß (480 × 720).
       Das Pet skaliert um sein aktuelles Zentrum, sodass eine
       Größenänderung es nicht verschiebt. Die Einrastung läuft
       nach der Größenänderung erneut.
   * - Deckkraft-Schieberegler
     - 10 – 100 %. Wirkt auf Fensterebene (über
       ``setWindowOpacity``), sodass das gesamte Pet ausblendet,
       nicht nur die Textur. Die Untergrenze von 10 % existiert,
       damit Sie das Pet immer noch sehen und greifen können —
       vollständig unsichtbar könnten Sie es verlieren.
   * - Positions-Erinnerung
     - Die ``(x, y)``-Koordinaten nach der Einrastung werden
       bei jedem Loslassen gespeichert, zusammen mit dem
       Monitor, auf dem das Pet steht. Beim nächsten Start
       kehrt das Pet zu dieser Position zurück, geklemmt in
       diesen Monitor. Wenn der Monitor fehlt (Sie haben ihn
       seit dem letzten Start abgesteckt), geht das Pet auf den
       ersten Bildschirm, mit seiner gespeicherten Position in
       ihn geklemmt. Die rechte untere Ecke wird nur verwendet,
       wenn nie eine Position gespeichert wurde.

Interaktionsmodell
^^^^^^^^^^^^^^^^^^

Das Pet reagiert über drei unabhängige Kanäle auf Mauseingaben.

**Linksklick auf den Körper**

Die Klickposition wird in Puppet-Canvas-Koordinaten zurück
abgebildet (Pan / Zoom des Canvas wird rückgängig gemacht) und
durch die vorhandene ``hit_test``-Pipeline geführt. Das Ergebnis
steuert das Verhalten wie folgt:

#. Wenn eine ``HitArea`` das angeklickte Zeichnungsobjekt
   abdeckt UND diesem Bereich eine Bewegung zugeordnet ist,
   wird die Bewegung abgespielt.
#. Unabhängig davon, ob eine Bewegung abgespielt wurde, kann
   das Pet eine Sprechblase einblenden — siehe Abschnitt
   *Pet-Skript* für die Auswahlpriorität der Zeile.
#. Wenn kein Trefferbereich den Klick abdeckt, greift das Pet
   auf eine Begrüßung zurück (aus der ``greetings``-Liste des
   Skripts oder dem eingebauten Fallback).

Eine Ziehgeste unterdrückt den Klick-Handler, sodass das
Verschieben des Pets keine Sprechblase einblendet. Das Drücken
spielt eine Bewegung aus der ``Drag``-Gruppe des Rigs ab und das
Loslassen nach einem Ziehen eine aus seiner ``Land``-Gruppe,
sofern das Rig diese Gruppen hat.

**Rechtsklick an beliebiger Stelle auf dem Körper**

Öffnet ein Kontextmenü mit folgender Struktur:

* **Hide pet** — Top-Level-Aktion, die das Overlay schließt.
* **Live drivers**-Untermenü — sieben aktivierbare Umschalter
  (Auto idle, Idle motions, Auto-blink, Drag-track head, Mouse
  gaze, Mic lip-sync, Webcam tracking). Der Aktivierungszustand
  spiegelt den Zustand der Live-Treiber wider, sodass das Menü
  zeigt, was gerade läuft.
* **Play motion**-Untermenü — gefüllt aus der
  ``document.motions``-Liste des aktiven Rigs. Bei Auswahl
  eines Eintrags wird diese Bewegung abgespielt; dabei wird
  keine ``motion_lines``-Zeile gesprochen (diese antworten nur
  auf einen Klick auf einen Trefferbereich).
* **Apply expression**-Untermenü — gefüllt aus
  ``document.expressions`` des Rigs. Jeder Eintrag ist abgehakt,
  solange sein Ausdruck aktiv ist; die Auswahl fügt das
  Parameter-Overlay des Ausdrucks hinzu, eine erneute Auswahl
  entfernt es wieder.
* **Pose**-Untermenü — ein Untermenü pro Pose-Gruppe des Rigs
  (beschriftet mit dem Anzeigenamen der Gruppe, sonst mit ihrer ID),
  das die Mitglieder der Gruppe auflistet; das sichtbare Mitglied ist
  abgehakt, die Auswahl eines anderen zeigt stattdessen dieses an.
  Deaktiviert, wenn das Rig keine Pose-Gruppen hat.
* Fünf aktivierbare Top-Level-Umschalter: **Lock position**,
  **Click-through**, **Always on bottom**, **Hide on fullscreen**,
  **Speech bubble** — schneller Zugriff auf dieselben Umschalter
  im Workspace-Tab.
* **Size**-Untermenü — Klein / Mittel / Groß; die aktuelle
  Voreinstellung ist angekreuzt.

Die Bewegungs- / Ausdrucks-Untermenüs sind deaktiviert, wenn
kein Rig geladen ist.

**System-Tray-Symbol**

Ein Tray-Symbol (nur auf Plattformen mit Tray-Unterstützung
instanziiert) bietet eine vierte Oberfläche für die häufigsten
Aktionen:

* Linksklick schaltet die Sichtbarkeit des Pets um.
* Rechtsklick öffnet ein Menü mit **Show pet** (aktivierbar),
  **Click-through**, **Open puppet…**, **Hide pet**.
* Die aktivierbaren Show- / Click-through-Einträge spiegeln den
  Aktivierungszustand des Workspaces über ``sync_visibility`` /
  ``sync_click_through`` wider, sodass sie synchron bleiben,
  unabhängig davon, wo der Benutzer den entsprechenden Schalter
  umlegt.

Live-Treiber
^^^^^^^^^^^^

Jeder Live-Treiber wird beim ersten Aktivieren träge erstellt,
sodass ein ruhendes Pet null Timer- / Thread-Kosten für Treiber
verursacht, die Sie nie einschalten. Der Zustand jedes Treibers
wird gespeichert; aktivieren, Imervue schließen und neu starten
stellt das Rig mit denselben laufenden Treibern wieder her. Das
Overlay selbst erscheint beim Start nur, wenn **Show the pet when
Imervue starts** in der Window-Gruppe des Tabs angekreuzt ist.

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - Treiber
     - Was er tut
     - Optionale Abhängigkeit
   * - **Auto idle**
     - Atem + subtiles Driften auf Standardparametern
       (``ParamBreath`` usw.), damit die Figur lebendig aussieht,
       wenn sonst nichts animiert.
     - keine
   * - **Idle motions**
     - Wählt zufällig eine Bewegung aus der ``Idle``-Gruppe des
       Rigs und spielt sie ab — eine sofort beim Einschalten,
       danach alle paar Sekunden. Tritt zurück, solange eine
       Nicht-Idle-Bewegung läuft.
     - keine
   * - **Auto-blink**
     - Schließt und öffnet die Augen auf einer weichen
       Kosinuskurve etwa alle 4,5 s. Der Treiber erzwingt das
       Schreiben des Parameters, damit andere Treiber, die
       Augenöffnungswerte berühren, das Blinzeln nicht
       unterdrücken.
     - keine
   * - **Drag-track head**
     - Kopf + Augen drehen sich zum Cursor, während er sich
       über das Pet bewegt. Steuert
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - keine
   * - **Mouse gaze**
     - Augen und Kopf folgen dem Cursor überall auf dem
       Bildschirm, relativ zur Mitte des Pets (die Augen führen).
       Steuert dieselben vier Parameter.
     - keine
   * - **Mic lip-sync**
     - Die RMS-Amplitude des Mikrofons steuert
       ``ParamMouthOpenY``.
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker liest Ihre Webcam mit ~30 FPS
       und steuert Kopfpose + Augenöffnungs- + Mundöffnungs-
       Parameter. Für das Pet öffnet sich kein Vorschaufenster
       (die Kameravorschau gehört zum Puppet-Tab).
     - ``opencv-python`` + ``mediapipe``

Die beiden Treiber mit optionalen Abhängigkeiten degradieren
elegant: Wenn das benötigte Paket nicht installiert ist, springt
das Kontrollkästchen beim Umschalten zurück und das Statuslabel
des Workspaces zeigt einen Hinweis "install sounddevice" /
"install opencv-python + mediapipe".

Pet-Skript — eigene Stimme und geplante Ereignisse
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Die Sprechblase des Pets greift auf eine JSON-Datei zurück, die
Sie verfassen und über die Gruppe **Pet script** im Tab laden
können. Das Skript steuert fünf Dinge:

* **Greetings** — standardmäßige Klickzeilen, wenn nichts
  Spezifischeres passt.
* **Time-of-day greetings** — Begrüßungen für das Tageszeitband
  der lokalen Uhr (``morning`` 05–11 Uhr, ``afternoon`` 12–17 Uhr,
  ``evening`` 18–21 Uhr, ``night`` 22–04 Uhr), verwendet vor den
  einfachen Begrüßungen; ein Band ohne Zeilen fällt auf diese
  zurück.
* **Hit-area responses** — Zeilen-Buckets pro ``HitArea.id``.
* **Motion lines** — Zeilen-Buckets pro Bewegungsname,
  gesprochen, wenn ein Klick auf einen Trefferbereich diese
  Bewegung abspielt (nicht, wenn eine Bewegung aus dem
  Kontextmenü gestartet wird).
* **Scheduled chimes** — timergesteuerte Zeilen, die alle
  ``every_seconds`` monotoner Wanduhrzeit ausgelöst werden.

Schema (versioniert — zukünftige Felder sind
vorwärtskompatibel):

.. code-block:: json

   {
     "version": 1,
     "name": "Imeru — cheerful voice",
     "greetings": [
       "Hi!", "Hello hello!", "Need a break?"
     ],
     "time_of_day_greetings": {
       "morning": ["Good morning!"],
       "night": ["Still up?"]
     },
     "hit_responses": {
       "HitAreaHead": ["Hey, my head!", "Stop poking!"],
       "HitAreaBody": ["Hehe~", "Pat pat?"]
     },
     "motion_lines": {
       "wave": ["Hi!", "Hello!"],
       "curtsy": ["Cheers!"]
     },
     "scheduled": [
       {"every_seconds": 1800, "messages": ["Stretch break!"]}
     ]
   }

Laderegeln:

* Listen werden pro Bucket im Round-Robin-Verfahren abgetastet,
  damit der Benutzer nicht zweimal hintereinander dieselbe
  Zeile sieht.
* Unbekannte Top-Level-Schlüssel werden ignoriert
  (Vorwärtskompatibilität — eine zukünftige v2-Datei lädt
  weiterhin auf einer v1-Laufzeit).
* Müllige Listeneinträge (falscher Typ, fehlerhafte geplante
  Einträge, null / negative ``every_seconds``) werden
  übersprungen — eine fehlerhafte Zeile lässt nicht das
  gesamte Laden scheitern. Nur völlig nicht parsbares JSON
  löst einen Fehler aus und zeigt den Pfad im Statuslabel.
* Die Kaskade Trefferbereich / Bewegung / Begrüßung ist
  geschichtet: Ein Linksklick konsultiert zuerst
  ``hit_responses[area.id]``, dann ``motion_lines[area.motion]``,
  dann ``time_of_day_greetings``, dann ``greetings``, dann den
  eingebauten Standard-Begrüßungssatz als Untergrenze.
* Die Zeitverfolgung verwendet ``time.monotonic``, damit das
  Aufwachen eines Laptops aus dem Standby oder ein Sprung der
  Systemuhr nicht zu einer Salve aufgestauter Ereignisse
  führen kann.

**Reset to default** verwirft das Benutzerskript und kehrt zum
eingebauten Begrüßungssatz zurück; der gespeicherte Skriptpfad
wird gelöscht, damit der nächste Start ihn nicht erneut lädt.

Ein funktionierendes Beispiel liegt unter
``examples/desktop_pet/imeru.petscript.json`` — sechs
Begrüßungen, eine Zeile für jede Tageszeit, zwei
Trefferbereichs-Buckets (``Head`` / ``Body``), Zeilen für fünf
Motions (wave / greet / surprised / sleepy / shy) und eine
30-minütige Stretch-Erinnerung. Die Bucket-Namen sind Imerus
Trefferbereiche, sodass ihr Kopf und Körper auf Klicks antworten;
ein Rig, dessen Trefferbereiche die Cubism-Namen verwenden
(``HitAreaHead`` / ``HitAreaBody``), braucht Buckets unter diesen
Namen.

Persistenz
^^^^^^^^^^

Der gesamte Desktop-Pet-Zustand wird über
``user_setting_dict["desktop_pet"]`` (ein Slot in der
Standard-Imervue-Benutzereinstellungsdatei) hin und her
gespeichert. Jedes Feld hat beim Laden einen Standardwert +
Bereichs-Klemmung, sodass eine beschädigte Einstellungsdatei
den Start nicht zum Absturz bringen kann.

.. list-table:: Persistierte Felder
   :header-rows: 1
   :widths: 28 18 54

   * - Feld
     - Standard
     - Hinweise
   * - ``last_rig_path``
     - ``""``
     - Beim Start automatisch wiederhergestellt, wenn die
       Datei noch existiert.
   * - ``script_path``
     - ``""``
     - Beim Start automatisch wiederhergestellt, wenn das
       Skript noch parst; ein unlesbares Skript fällt
       stillschweigend auf Standardwerte zurück.
   * - ``position``
     - ``[-1, -1]``
     - Bildschirmkoordinate ``(x, y)`` vom letzten
       Ziehen-Loslassen. ``-1, -1`` (nie gespeichert) bedeutet
       "rechte untere Ecke verwenden". Fehlt der gespeicherte
       Monitor, wird die Position in den ersten Bildschirm
       geklemmt.
   * - ``size_preset``
     - ``"medium"``
     - Einer von ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Werte außerhalb des Bereichs werden auf ``[0.1, 1.0]``
       geklemmt; nur ein nicht numerischer Wert fällt auf den
       Standard zurück.
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - Gegenseitig ausschließend mit immer-im-Vordergrund.
   * - ``hide_on_fullscreen``
     - ``true``
     - Setzen Sie auf ``false``, um das Pet während des
       Vollbildmodus sichtbar zu halten.
   * - ``snap_threshold``
     - ``24``
     - Geklemmt auf ``[0, 200]`` px.
   * - ``drivers``
     - ``auto_idle``, ``idle_motion``, ``auto_blink``
       ``true``; die übrigen ``false``
     - Unter-Dict, indiziert nach Treiber-ID (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mouse_gaze``, ``mic_lipsync``, ``webcam_tracking``).
       Unbekannte Schlüssel werden für die
       Vorwärtskompatibilität unverändert hin und her
       gespeichert.
   * - ``show_on_launch``
     - ``false``
     - Gesetzt über **Show the pet when Imervue starts** in der
       Window-Gruppe des Tabs. Rig und Treiber werden beim Start
       in jedem Fall wiederhergestellt; das Overlay erscheint
       nur, wenn dies aktiviert ist.
   * - ``speech_enabled``
     - ``true``
     - Wenn false, erscheint die Sprechblase nie.

Das Merge-Verhalten des Einstellungs-Dicts ist eine Ebene tief:
Ältere Einstellungsdateien, denen neuere Schlüssel fehlen,
erzeugen beim Laden weiterhin ein vollständiges Zustands-Dict
(Standardwerte füllen die Lücken); neuere Schlüssel, die Sie
gespeichert haben, überleben ein Downgrade auf eine ältere
Laufzeit, die nichts davon weiß.

Ein neues Pet erstellen
^^^^^^^^^^^^^^^^^^^^^^^

Jede ``.puppet``-Datei funktioniert als Desktop-Pet-Figur — der
Desktop-Pet-Tab ist rein eine Renderer- + Interaktionshülle;
das Authoring des Rigs erfolgt im Puppet-Tab (siehe
*Puppet-Arbeitsbereich (Puppet-Tab)*).

So erstellen Sie Ihr eigenes Pet-Rig:

#. Wechseln Sie zum Puppet-Tab und importieren Sie eine
   Grafik über **File > Import PNG…** oder **File > Import PSD…**,
   oder ziehen Sie ein Cubism-Modell über
   **File > Import Cubism…** hinein.
#. Erstellen Sie Rotations- / Warp-Deformer, Parameter,
   Bewegungen, Ausdrücke und (optional) Trefferbereiche, die
   an Körperteile gebunden sind, damit der Linksklick-Handler
   des Desktop-Pets Bewegungen auslösen kann.
#. Speichern Sie das Rig über **File > Save As…** in ein
   ``.puppet``-Zip.
#. Wechseln Sie zurück zum Desktop-Pet-Tab und laden Sie die
   neue Datei über **Open Puppet…**.

Wenn Ihr Rig ``HitArea``-Einträge definiert, können Sie
Sprechblasen-Zeilen pro Trefferbereich in einer
``.petscript.json`` verfassen, deren ``hit_responses``-Schlüssel
mit den Bereichs-IDs übereinstimmen.

Integrations-Plugin
^^^^^^^^^^^^^^^^^^^

Das Plugin **Desktop Pet Integrations** (``Plugins`` > ``Download Plugins``, Kategorie
``plugins``, Name ``pet_integrations``) lässt das Pet auf die Außenwelt reagieren. Es fügt
``Plugins`` > ``Desktop Pet Integrations`` hinzu, mit einem Eintrag pro Integration und einem
Eintrag ``Settings…`` für deren Optionen; ein Eintrag lässt sich einschalten, sobald das Pet
angezeigt wurde, installiert zuerst das optionale Paket, das er braucht, und bleibt über
Neustarts hinweg aktiv. Es ist zugleich das ausgearbeitete Beispiel für ein Plugin, das das Pet
erweitert — siehe *Plugins schreiben* und ``on_pet_created``.

.. list-table::
   :header-rows: 1
   :widths: 22 56 22

   * - Integration
     - Was das Pet tut
     - Benötigt
   * - Auf OBS-Ereignisse reagieren
     - Spielt eine Bewegung aus der Gruppe ``Stream``, ``Record`` oder ``Scene`` ab, wenn Streaming
       oder Aufnahme startet oder stoppt oder die Szene wechselt. Host, Port und Passwort des
       WebSocket-Servers von OBS stellen Sie in ``Settings…`` ein
     - ``obs-websocket-py`` (wird bei der ersten Verwendung installiert); OBS mit
       eingeschaltetem WebSocket-Server
   * - Auf den Twitch-Chat reagieren
     - Tritt dem Chat eines Kanals bei und spielt die einem Schlüsselwort zugeordnete
       Bewegungsgruppe ab, sobald eine Nachricht es enthält (ohne Beachtung der
       Groß-/Kleinschreibung; Zeilen ``keyword = Group`` in ``Settings…``)
     - Ein Kanalname und ein ``oauth:``-Token
   * - Lokaler Webhook (127.0.0.1)
     - Lauscht auf ``http://127.0.0.1:9876/trigger`` (Port in ``Settings…``) auf einen JSON-POST
       ``{"group": "Wave", "speech": "Hi!"}`` — jedes der beiden Felder darf fehlen — von
       Skripten, Stream Deck oder Automatisierungswerkzeugen. Ist ein Token gesetzt, müssen
       Anfragen ``Authorization: Bearer <token>`` senden; Anfragen von einer Webseite werden
       abgelehnt
     - Nichts weiter
   * - Auf Windows-Benachrichtigungen reagieren
     - Spielt die Gruppe ``Notify`` ab und spricht den Titel der Benachrichtigung aus, wenn eine
       andere App eine Windows-Benachrichtigung anzeigt; Apps, die unter den ignorierten App-IDs
       stehen, werden übersprungen. Windows fragt beim ersten Mal nach dem Zugriff auf
       Benachrichtigungen
     - Windows; die ``winrt``-Benachrichtigungspakete (werden bei der ersten Verwendung
       installiert)

Ein Rig reagiert nur auf die Bewegungsgruppen, die es hat; eine fehlende Gruppe spielt nichts ab.

Fehlerbehebung
^^^^^^^^^^^^^^

**Das Pet erscheint in einem grauen Rechteck statt vollständig
transparent zu sein.** Das OS-Level-Attribut für durchscheinende
Hintergründe erfordert eine alpha-fähige GL-Oberfläche plus
passende Attribute auf dem eingebetteten GL-Widget. Stellen Sie
sicher, dass kein Fenstermanagement-Tool eines Drittanbieters
das Attribut ``WA_TranslucentBackground`` auf dem Overlay-Fenster
überschreibt (einige benutzerdefinierte Fenstermanager unter
Linux tun dies). Unter Windows / macOS sollte es einfach
funktionieren.

**"Load bundled Imeru" meldet, dass die Datei nicht
gefunden wurde.** Der Resolver konsultiert zuerst
``examples_dir()`` (den frozen-sicheren Speicherort, der von
paketierten Builds verwendet wird) und greift auf einen
CWD-relativen Pfad zurück. Wenn keiner das Rig enthält, zeigt
das Statuslabel den erwarteten Pfad. Überprüfen Sie das mit
Ihrer Installation gelieferte ``examples/``-Verzeichnis — bei
Source-Checkouts starten Sie Imervue aus dem Repository-Root.

**Das Pet spricht nicht, wenn es angeklickt wird.** Drei
Prüfungen:

#. Stellen Sie sicher, dass der Umschalter **Speech bubble on
   click** aktiviert ist (im Tab oder im Rechtsklick-Menü).
#. Wenn Sie ein benutzerdefiniertes Skript geladen haben,
   überprüfen Sie, ob das JSON parst — das Statuslabel des
   Tabs zeigt den Ladefehler.
#. Wenn **Click-through** aktiviert ist, geht der Klick an das
   Fenster hinter dem Pet; schalten Sie es im Tab oder im
   Tray-Menü aus. (Bei aktivierter Sprechblase erhält jeder
   Klick eine Zeile: Ein Rig ohne Trefferbereiche spielt keine
   Bewegung ab, aber der Klick begrüßt Sie trotzdem.)

**Das Kontrollkästchen Webcam-Tracking springt zurück.**
Webcam-Tracking benötigt ``opencv-python`` und ``mediapipe``,
installiert in derselben Python-Umgebung, in der Imervue läuft.
Installieren Sie mit ``pip install opencv-python mediapipe``.
Kreuzen Sie das Kontrollkästchen nach der Installation erneut an.
Das Pet öffnet kein Vorschaufenster; um zu sehen, was die Kamera
erkennt, schalten Sie **Webcam tracking** im Puppet-Tab ein, der
die Gesichtsmerkmale anzeigt.

**Das Pet blendet sich nicht automatisch während
Vollbild-Apps aus.** Der Vollbild-Detektor fragt das
Vordergrundfenster mit 1 Hz ab. Unter Windows verwendet er die
Win32-API ``GetWindowRect``; unter macOS / Linux gibt es kein
zuverlässiges plattformübergreifendes Äquivalent, und er ist
ein Leerlauf (das Pet bleibt sichtbar). Für Windows: stellen
Sie sicher, dass **Hide when other app is fullscreen**
aktiviert ist, und überprüfen Sie, ob das Vollbildfenster
tatsächlich ≥ 99 % desselben Monitors wie das Pet abdeckt.

**Die Position des Pets driftet zwischen den Starts vom
Bildschirm ab.** Dies passiert, wenn der Bildschirm, auf dem
das Pet war, beim nächsten Start nicht mehr verbunden ist
(Laptop-Dock, zweiter Monitor abgesteckt). Das Pet wechselt in
diesem Fall auf den ersten Bildschirm, mit seiner gespeicherten
Position in ihn geklemmt — ziehen Sie es an die gewünschte Stelle und
der nächste Speichervorgang überschreibt die veraltete Position.

----

Rotation und Spiegelung
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Aktion
     - Tastenkürzel
     - Menü
   * - 90° im Uhrzeigersinn drehen
     - ``R``
     - Rechtsklick > Modify > Im Uhrzeigersinn drehen
   * - 90° gegen Uhrzeigersinn drehen
     - ``Shift + R``
     - Rechtsklick > Modify > Gegen den Uhrzeigersinn drehen
   * - Horizontal spiegeln
     - --
     - Rechtsklick > Modify > Horizontal spiegeln
   * - Vertikal spiegeln
     - --
     - Rechtsklick > Modify > Vertikal spiegeln
   * - Verlustfreie Rotation
     - --
     - Rechtsklick > Verlustfreie Rotation > Verlustfrei im / gegen den Uhrzeigersinn drehen. Nur ein JPEG ist wirklich
       verlustfrei (sein Orientierungs-Tag ändert sich); PNG / BMP / TIFF / WebP /
       GIF werden dekodiert, gedreht und neu gespeichert (ein verlustbehaftetes WebP wird neu kodiert);
       Kamera-RAW, HEIC und Mehrbilddateien werden abgelehnt

----

Bilder exportieren
------------------

Einzelexport
^^^^^^^^^^^^

Ein Bild öffnen (Deep Zoom), dann Rechtsklick > ``Exportieren / Speichern unter``.

- Format wählen: PNG, JPEG, WebP, BMP, TIFF; AVIF, wenn Pillow AVIF unterstützt, HEIC und JPEG XL, wenn ``pillow-heif`` / ``pillow-jxl-plugin`` installiert ist
- Qualität anpassen (für verlustbehaftete Formate)
- Metadaten wählen: alle, alle außer dem Standort (Standard) oder keine. Kamera, Objektiv und Aufnahmedatum bleiben erhalten; die Wahl wird gespeichert, und der Batch-Export bietet dieselbe Option
- Geschätzte Dateigröße in der Vorschau
- Speicherort wählen. Der vorgeschlagene Name ist noch frei (``photo_1.png`` neben ``photo.png``); eine vorhandene Datei – vor allem das Foto selbst – wird erst nach Rückfrage ersetzt

Export-Presets
^^^^^^^^^^^^^^

Der Stapelexport (unten) hat eine **Preset**-Liste, die Größe, Format und Qualität für
gängige Ziele einträgt; bei **Custom** legen Sie die Werte selbst fest:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Preset
     - Ausgabe
   * - **Web — 1600 px JPEG**
     - Lange Kante bis 1600 px, JPEG-Qualität 85.
   * - **4K Web — 3840 px JPEG**
     - Lange Kante bis 3840 px, JPEG-Qualität 90.
   * - **Print — 300 DPI PNG**
     - Volle Auflösung, PNG, 300 dpi.
   * - **Instagram — 1080×1080 square**
     - Quadratischer Zuschnitt aus der Mitte, 1080 × 1080, JPEG-Qualität 90.
   * - **Thumbnail — 400 px JPEG**
     - Lange Kante bis 400 px, JPEG-Qualität 80.

Wasserzeichen
^^^^^^^^^^^^^

Der Stapelexport kann außerdem ein Text-Wasserzeichen auf jede exportierte Kopie zeichnen:
den Text, seine Position (eine Ecke oder die Mitte) und seine Deckkraft. Die Originaldateien
werden nie verändert.

Stapelexport
^^^^^^^^^^^^

Mehrere Bilder auswählen, dann Rechtsklick > ``Stapeloperationen`` > ``Stapelexport``.

- Einheitliche Formatkonvertierung
- Maximale Breite / Höhe setzen (automatische Seitenverhältnisskalierung)
- Qualitätskontrolle
- Echtzeit-Fortschrittsbalken
- **Render on**: die CPU oder eine dedizierte GPU, wenn das Plugin GPU Develop installiert ist (siehe unten)

GPU-Develop-Plugin
^^^^^^^^^^^^^^^^^^

Das Plugin **GPU Develop** (``Plugins`` > ``Download Plugins``, Kategorie ``plugins``, Name
``gpu_develop``) lässt den Stapelexport Develop-Rezepte auf einer dedizierten GPU rendern.
``Plugins`` > ``GPU Develop…`` installiert beim ersten Mal ``wgpu`` und nennt danach die GPU, die
es verwenden wird; der Stapelexport zeigt dann **Render on** mit dieser GPU ausgewählt (wählen Sie
**CPU**, um wie bisher zu rendern).

- Weißabgleich, Belichtung, Lichter / Schatten, Weiß / Schwarz, Helligkeit, Kontrast, Dynamik, Sättigung und die Tonwertkurve laufen auf der GPU; Drehung, Spiegelungen, der Zuschnitt und alles nach der Tonwertkurve (Split-Toning, LUT, Masken, Tonwerte und der Rest) bleiben auf der CPU
- Ein 24-MP-Foto braucht auf der GPU etwa 0,1 s statt etwa 7 s auf der CPU, Dekodieren und Speichern nicht mitgerechnet
- Verwendet wird nur eine dedizierte GPU, nie eine integrierte GPU oder ein Software-Renderer; unter Windows zuerst über Vulkan, dann über Direct3D 12
- Ein Bild, bei dem die GPU scheitert, wird auf der CPU gerendert, sodass der Export trotzdem abgeschlossen wird
- Die Ausgabe stimmt mit der des CPU-Renderers bis auf wenige Stufen bei einem kleinen Anteil der Pixel überein

GIF / Video erstellen
^^^^^^^^^^^^^^^^^^^^^

Mehrere Bilder auswählen, dann Rechtsklick > ``Stapeloperationen`` > ``GIF / Video erstellen``.

- GIF- und MP4-Ausgabe; MP4 verwendet das ffmpeg im PATH, sonst das mit der Standardabhängigkeit ``imageio-ffmpeg`` gebündelte
- Per Drag Frames neu anordnen
- Bilder pro Sekunde (FPS) festlegen
- Eigene Abmessungen
- Loop-Option: endlos wiederholen oder, wenn aus, einmal abspielen
- Vorgeschlagen wird ``output.gif`` neben dem ersten Bild, nummeriert (``output_1.gif``), wenn der Name vergeben ist; ein eingetippter, bereits vorhandener Name wird erst nach Rückfrage ersetzt

----

Animations-Wiedergabe
---------------------

Beim Öffnen von GIF-, APNG- oder animierten WebP-Dateien wird die Animation automatisch abgespielt. Eine Animation, die dekodiert mehr als
512 MB bräuchte, wird beim Abspielen Bild für Bild dekodiert; das Öffnen friert das
Fenster also nicht ein und füllt nicht den Speicher.
Ein Bild mit 10 ms oder weniger wird wie in Browsern 100 ms lang gezeigt – viele GIFs sind darauf ausgelegt.

Ein mehrseitiges TIFF – ein gescanntes Dokument – wird nicht abgespielt: Es zeigt eine Seite nach der anderen, geblättert mit ``,`` und ``.``, und die Anzeige nennt die Seitenzahl. Bilder, die keine Animation sind, laufen ebenfalls nie ab: die Vorschau, die eine Kamera in ein JPEG einbettet (MPF), die Ebenen einer PSD und das Standardbild eines APNG – das Standbild für Programme ohne APNG-Unterstützung.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``Space``
     - Abspielen / Pause
   * - ``,``
     - Vorheriger Frame
   * - ``.``
     - Nächster Frame
   * - ``]``
     - Beschleunigen
   * - ``[``
     - Verlangsamen

----

Bildvergleich
-------------

Wählen Sie im Miniaturansichten-Modus 2 oder 4 Bilder aus, dann Rechtsklick > ``Bilder vergleichen``
(oder wählen Sie sie in der Liste des Dialogs aus).

Der Dialog hat vier Tabs:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Tab
     - Zweck
   * - **Nebeneinander**
     - 2 oder 4 Bilder gleichzeitig anzeigen; jedes skaliert automatisch in seinem Bereich.
   * - **Overlay**
     - Zwei Bilder mit Alpha-Schieberegler mischen (0 → nur A, 100 → nur B). Erfordert genau 2 ausgewählte Bilder.
   * - **Differenz**
     - Pro-Pixel ``|A − B|``-Visualisierung mit Gain-Schieberegler (0,10× – 20×) zur Verstärkung feiner Unterschiede.
   * - **A | B Split**
     - Vorher-/Nachher-Split-Ansicht mit einem zieh­baren vertikalen Trenner. Trenner ziehen, um zwischen den
       beiden Bildern zu wischen; ideal für Anpassungen am Entwicklungs-Recipe oder zum Vergleichen von Exporten.
       Erfordert genau 2 ausgewählte Bilder.

Wenn die zwei Bilder unterschiedliche Größen haben, wird ``B`` mit Lanczos auf
die Abmessungen von ``A`` neu abgetastet. Sehr große Bilder werden intern auf
2048 px Langseite gedeckelt, damit Overlay / Differenz interaktiv bleiben.

.. seealso::
   Für Inline-Vergleich ohne Öffnen eines Dialogs verwenden Sie **Geteilte Ansicht**
   (``Shift + S``) oder **Doppelseitenlesen** (``Shift + D`` / ``Ctrl + Shift + D``),
   beschrieben im Abschnitt Durchsuchen.

----

Diashow
-------

Drücken Sie ``S`` oder Rechtsklick > ``Diashow``, um eine automatische Diashow zu starten.

- Einstellbares Intervall pro Bild
- Optionaler Fade-Übergang zwischen Bildern

----

Suche
-----

Drücken Sie ``Ctrl + F`` oder ``/`` und tippen Sie ein Stichwort, um Bilder im
aktuellen Ordner per Dateiname zu durchsuchen.

Die Suche verwendet **Fuzzy-Matching** mit Drei-Stufen-Ranking
(Präfix > Teilstring > Teilfolge) und **Teilstring-Hervorhebung** in den
Ergebnissen. ``Enter`` oder Doppelklick springt zu einem Bild.

Um nach **Bildnummer** statt Name zu springen, ``Ctrl + G`` für den
Gehe-zu-Dialog drücken.

----

Kopieren und Einfügen
---------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Aktion
     - Methode
   * - Bild in Zwischenablage kopieren
     - ``Ctrl + C`` im Deep-Zoom-Modus
   * - Zwischenablagenbild einfügen
     - ``Datei`` > ``Aus Zwischenablage einfügen`` öffnet es im Annotationseditor (nichts wird gespeichert);
       ``Ctrl + V`` speichert es als ``pasted_<timestamp>.png`` im aktuellen Ordner und öffnet es, oder
       öffnet einen in die Zwischenablage kopierten Dateipfad
   * - Zwischenablage automatisch überwachen
     - ``Datei`` > ``Zwischenablagenbilder automatisch annotieren`` (umschalten)

.. note::
   Wenn die automatische Überwachung aktiviert ist, öffnet sich der Annotationseditor
   jedes Mal automatisch, wenn ein neues Bild in der Zwischenablage erscheint
   (z. B. aus einem Screenshot-Tool).

----

Bilder löschen
--------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Aktion
     - Methode
   * - Aktuelles Bild löschen
     - ``Delete`` drücken
   * - Ausgewählte Bilder löschen
     - Mehrere auswählen, dann ``Delete`` oder Rechtsklick > ``Ausgewählte Bilder löschen``

Bilder werden in den System-Papierkorb verschoben und können von dort wiederhergestellt werden. Auf
einem Laufwerk ohne Papierkorb — Speicherkarte, USB-Stick oder Netzlaufwerk, wo Windows
endgültig löschen würde — bleibt die Datei: Beim Schließen listet Imervue solche Dateien
auf und fragt, ob sie endgültig gelöscht werden sollen.

Ihre Sidecars gehen mit: ``IMG.JPG.xmp``, ``IMG.JPG.annotations.json`` und
``IMG.xmp``, außer das RAW eines RAW-+-JPEG-Paars nutzt Letzteres noch. Eine
zurückgelassene Sidecar-Datei würde Bewertung und Bearbeitung an das nächste
``IMG.*`` hängen, das die Kamera unter demselben Namen schreibt.

----

Stapeloperationen
-----------------

Im Miniaturansichten-Modus mehrere Bilder auswählen, dann Rechtsklick > ``Stapeloperationen``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Funktion
     - Beschreibung
   * - Stapel-Umbenennen
     - Umbenennen mit Vorlagen: ``{name}``, ``{n}``, ``{ext}``
   * - Verschieben / Kopieren
     - Bilder in einen anderen Ordner verschieben oder kopieren
   * - Alle drehen
     - Alle ausgewählten Bilder auf einmal drehen
   * - Stapelexport
     - Format konvertieren und in großen Mengen skalieren
   * - GIF / Video erstellen
     - Die Auswahl als GIF oder MP4 animieren (siehe *GIF / Video erstellen*)
   * - Nach Ort taggen
     - Die nächstgelegene Stadt samt Land jedes geotaggten Fotos in seine XMP-Stichwörter aufnehmen
   * - Stichwörter indizieren
     - Die XMP-Stichwörter der Auswahl in die Bibliothek übernehmen
   * - Auto-Culling: unscharf
     - Die unscharfen Fotos als Reject markieren
   * - Auto-Culling: geringe Qualität
     - Das schwächste Viertel der Auswahl (Schärfe, Belichtung, Kontrast) als Reject markieren
   * - Automatisch nach EXIF drehen
     - Von jedem Foto eine aufrecht gedrehte PNG-Kopie als ``<name>_oriented.png`` speichern
   * - Zu PDF / TIFF kombinieren…
     - Die Auswahl in Ansichtsreihenfolge zu einer mehrseitigen PDF- oder TIFF-Datei zusammenfügen
   * - In datierte Ordner importieren…
     - Die Auswahl nach Aufnahmedatum (EXIF, sonst Dateidatum) in ``YYYY/MM``-Ordner kopieren;
       eine dort bereits vorhandene Datei behält ihren Namen, die neue erhält ``_1``
   * - Zu Tag hinzufügen
     - Dasselbe Tag auf alle ausgewählten Bilder anwenden
   * - Zu Album hinzufügen
     - Alle ausgewählten Bilder in ein Album legen

Verschieben oder Kopieren überschreibt nie eine gleichnamige Datei: Sie kommt als
``name_1.ext`` an. Ein in Imervue umbenanntes oder verschobenes Foto —
Stapel-Umbenennen, Token-Stapel-Umbenennen, Ordnerbaum, Verschieben / Kopieren,
Zwei-Fenster-Ansicht, Staging-Ablage, Bild-Organizer — behält Bewertung, Favorit,
Tags, Farbetikett, Titel, Beschreibung, Bibliotheksnotiz und Auswahl-Markierung
(ein umbenannter oder verschobener Ordner die aller Fotos darin). Seine Sidecars
wandern mit: ``IMG.xmp``, ``IMG.JPG.xmp`` und ``IMG.JPG.annotations.json``. Ein
``IMG.xmp``, das das RAW eines RAW-+-JPEG-Paars noch nutzt, wird kopiert statt
verschoben.

Ein Foto, das in einem anderen Programm umbenannt wird, während sein Ordner in
Imervue geöffnet ist, behält dieselben Daten; Daten, die der neue Name schon hatte,
bleiben unverändert.

----

RGB-Histogramm
--------------

Drücken Sie ``H`` im Deep-Zoom-Modus, um ein RGB-Histogramm über das Bild zu legen. Erneut drücken zum Ausblenden.

----

Als Hintergrundbild festlegen
-----------------------------

Rechtsklick im Deep-Zoom-Modus > ``Als Hintergrundbild festlegen``, um das aktuelle Bild als Desktop-Hintergrundbild zu setzen.

Unterstützt unter Windows, macOS und Linux (GNOME).

Windows färbt den Desktop schwarz und meldet trotzdem Erfolg, wenn es eine Datei nicht decodieren kann. Ein Bild, das kein JPEG, PNG oder BMP ist – Kamera-RAW, HEIC, PSD, TGA, WebP und die übrigen Formate, die Imervue öffnet –, und ein Foto, das erst aufgerichtet werden muss, werden deshalb als JPEG-Kopie dessen übergeben, was der Viewer zeigt. Die Kopie liegt in ``%LOCALAPPDATA%\Imervue\wallpaper`` (unter macOS und Linux ``~/.local/share/imervue/wallpaper``); nur die neueste wird behalten.

----

Mehrfenster
-----------

``Datei`` > ``Neues Fenster`` öffnet ein weiteres unabhängiges Imervue-Fenster. Jedes Fenster kann einen anderen Ordner durchsuchen.

Workspace-Layout-Presets
------------------------

``Datei`` > ``Workspaces…`` erfasst die aktuelle Fenstergeometrie, Dock- / Toolbar-
Anordnung, die Aufteilung zwischen Baum und Betrachter und den aktiven Wurzelordner unter einem Namen — und
lässt Sie dann zwischen gespeicherten Layouts wechseln. Der aktive Tab und die Panel-Aufteilung des Modify-Tabs
werden nicht gespeichert. Der Dialog unterstützt Aktuelles speichern,
Laden, Umbenennen und Löschen. Workspaces bleiben in ``user_setting.json``
(unter dem Schlüssel ``workspaces``) erhalten und überstehen Sitzungen hinweg.

.. tip::
   Bauen Sie einen **Browse**-Workspace mit breitem Baum neben dem Betrachter,
   und einen separaten **Focus**-Workspace mit schmal gezogenem Baum und
   geschlossenen Docks, die Sie nicht brauchen. Ein Klick bringt Ihr ganzes
   Fenster für jede Aufgabe in die richtige Form.

Touchpad-Gesten
---------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Geste
     - Aktion
   * - Pinch
     - Heran-/Herauszoomen im Deep Zoom (am Pinch-Zentrum verankert)
   * - Horizontales Wischen
     - Vorheriges / nächstes Bild

----

Dateizuordnung (Windows)
------------------------

Imervue als Bildbetrachter im Windows-Explorer registrieren:

1. ``Datei`` > ``Dateizuordnung`` > ``'Open with Imervue' registrieren``
2. Administrationsrechte sind nicht nötig: Die Registrierung schreibt in die Registry des aktuellen Benutzers.
3. Nach der Registrierung Rechtsklick auf ein beliebiges Bild im Explorer, um die ``Open with Imervue``-Option zu sehen.

Zum Entfernen: ``Datei`` > ``Dateizuordnung`` > ``Dateizuordnung entfernen``.

----

Plugin-System
-------------

Imervue unterstützt Plugins für erweiterte Funktionalität.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Aktion
     - Menü
   * - Installierte Plugins anzeigen
     - ``Plugins`` > ``Plugins verwalten``
   * - Neue Plugins herunterladen
     - ``Plugins`` > ``Plugins herunterladen``
   * - Plugin-Ordner öffnen
     - ``Plugins`` > ``Plugin-Ordner öffnen``
   * - Plugins neu laden
     - ``Plugins`` > ``Plugins neu laden``

Plugins schreiben
^^^^^^^^^^^^^^^^^

Ein Plugin ist ein Python-Paket in ``plugins/<name>/`` — in einem Quellcode-Checkout neben dem
Paket ``Imervue``, in einem paketierten Build neben der ausführbaren Datei (``Plugins`` > ``Open
Plugin Folder`` öffnet den Ordner). Seine ``__init__.py`` setzt ``plugin_class`` auf eine
Unterklasse von ``Imervue.plugin.plugin_base.ImervuePlugin``; eine einzelne ``.py``-Datei in
``plugins/`` wird ebenfalls geladen (verwendet wird ihre erste ``ImervuePlugin``-Unterklasse),
der Plugin-Downloader verteilt aber nur Pakete. Die Klassenattribute ``plugin_name``,
``plugin_version``, ``plugin_description`` und ``plugin_author`` sind optional (standardmäßig
``"Unnamed Plugin"``, ``"0.0.1"`` und leere Zeichenketten). Jedes Hauptfenster erzeugt seine
eigene Instanz jedes Plugins und übergibt sich selbst, sodass ein Hook ``self.main_window`` und
``self.viewer`` (den ``GPUImageView``) verwenden kann. Überschreiben Sie nur die Hooks, die Sie
brauchen; jeder Aufruf ist abgesichert, sodass eine Ausnahme unter dem Namen des Plugins
protokolliert wird, statt Imervue anzuhalten. Die vollständige Anleitung mit Beispielen ist
`PLUGIN_DEV_GUIDE.md <https://github.com/JeffreyChen-s-Utils/Imervue/blob/main/PLUGIN_DEV_GUIDE.md>`_.
Neben Hooks kann ein Plugin dem Stapelexport einen weiteren Renderer für Develop-Rezepte geben,
indem es in ``on_plugin_loaded()`` einen ``BackendProvider`` mit
``Imervue.image.develop_backends.register`` registriert; das Plugin GPU Develop ist das Beispiel.

Ein Dialog, der bei **OK** eine Bildtransformation ausführt, kann die Schaltflächenzeile, die
Installation optionaler Pakete, den Worker-Thread und den Toast mit dem Ergebnis von
``Imervue.plugin.tool_dialog.ToolDialogMixin`` übernehmen: Er setzt ``output_suffix`` und die
Toast-Schlüssel und gibt die Transformation aus ``_transform()`` zurück. Ein Plugin, das Code des
Hauptprogramms importiert, der erst nach älteren Versionen hinzugekommen ist, nennt die benötigte
Plugin-API-Version in einer Datei ``plugin.json`` neben seiner ``__init__.py``
(``{"min_api_version": 2}``). ``Plugins`` > ``Download Plugins`` lehnt ein solches Plugin auf einem
zu alten Imervue ab und behält eine bereits installierte Kopie, wobei die benötigte Version in der
Statuszeile steht; der Plugin-Loader überspringt es, ohne es zu importieren, und schreibt den Grund
ins Protokoll.

.. list-table::
   :header-rows: 1
   :widths: 28 40 32

   * - Hook
     - Aufgerufen, wenn
     - Argumente / Rückgabe
   * - ``register_languages()`` (Klassenmethode)
     - Auf der Plugin-Klasse, bevor jede Instanz erzeugt wird (bei jedem Laden und bei ``Reload
       Plugins``), sowie beim Start, bevor das Hauptfenster gebaut wird, wenn die gespeicherte
       Sprache keine eingebaute ist; dieser Startdurchlauf importiert jedes Plugin und führt sonst
       nichts aus
     - Keine Argumente. Rufen Sie hier ``language_wrapper.register_language(language_code,
       display_name, word_dict)`` auf; ein eingebauter Sprachcode wird abgelehnt. Der Rückgabewert
       wird ignoriert; eine Ausnahme wird protokolliert, und das Plugin wird trotzdem geladen
   * - ``on_plugin_loaded()``
     - Direkt nachdem die Instanz erzeugt wurde: während das Hauptfenster gebaut wird und erneut
       nach ``Plugins`` > ``Reload Plugins``
     - Keine Argumente; Rückgabewert wird ignoriert
   * - ``get_translations()``
     - Direkt nach ``on_plugin_loaded()``, einmal pro Laden
     - Gibt ``{language_code: {key: text}}`` zurück (Standard ``{}``). Die Zeichenketten werden in
       die Sprachtabellen übernommen; bereits vorhandene Schlüssel werden nie überschrieben, und
       unbekannte Sprachcodes werden übersprungen
   * - ``on_build_main_tabs(tabs)``
     - Einmal, während das Hauptfenster gebaut wird, nach den fünf eingebauten Tabs und vor
       ``on_build_menu_bar``; ``Reload Plugins`` führt ihn nicht erneut aus
     - ``tabs``: das oberste ``QTabWidget`` des Hauptfensters; einen Tab fügen Sie mit
       ``tabs.addTab(widget, label)`` hinzu. Rückgabewert wird ignoriert
   * - ``on_build_menu_bar(plugin_menu)``
     - Einmal, nachdem das gemeinsame ``Plugins``-Menü gebaut wurde, und erneut nach ``Reload
       Plugins``
     - ``plugin_menu``: das ``Plugins``-``QMenu`` (nicht die ``QMenuBar``). Einträge, die ein
       Plugin hier irgendwo in der Menüleiste hinzufügt, werden beim Neuladen entfernt.
       Rückgabewert wird ignoriert
   * - ``on_build_context_menu(menu, viewer)``
     - Jedes Mal, wenn das Rechtsklickmenü des Viewers gebaut wird, nach den eingebauten Einträgen
       und kurz bevor es sich öffnet
     - ``menu``: das Kontext-``QMenu``; ``viewer``: der ``GPUImageView``. Rückgabewert wird
       ignoriert
   * - ``on_folder_opened(folder_path, image_paths, viewer)``
     - Wenn der Scan eines geöffneten Ordners abgeschlossen ist
     - ``folder_path``: der Ordner; ``image_paths``: jedes Bild, das der Scan gefunden hat.
       Rückgabewert wird ignoriert
   * - ``on_image_loaded(image_path, viewer)``
     - Jedes Mal, wenn ein Bild im Deep Zoom in voller Größe angezeigt wird, egal wie es geöffnet
       wurde, und erneut, wenn es nach einer Bearbeitung neu geladen wird; nicht für die
       niedrig aufgelöste Vorschau, die angezeigt wird, während ein großes Bild dekodiert
     - ``image_path``: der Pfad des Bildes. Rückgabewert wird ignoriert
   * - ``on_image_switched(image_path, viewer)``
     - Wenn Weiter / Zurück (einschließlich des Umlaufs an beiden Enden der Liste) zu einem anderen
       Bild wechselt, sobald dessen Laden beginnt; ``on_image_loaded`` folgt, sobald es angezeigt
       wird. Das Öffnen eines Bildes aus dem Raster oder dem Filmstreifen ruft ihn nicht auf
     - ``image_path``: das neue aktuelle Bild. Rückgabewert wird ignoriert
   * - ``on_image_deleted(deleted_paths, viewer)``
     - Nachdem Bilder im Viewer — das aktuelle Bild oder die ausgewählten Miniaturansichten — oder
       im Ordnerbaum weich gelöscht (auf den Rückgängig-Stapel gelegt) wurden; nicht für eine
       Datei, die der Baum direkt in den Papierkorb schickt, weil sie nicht in der Bildliste steht
     - ``deleted_paths``: Liste der gelöschten Pfade. Rückgabewert wird ignoriert
   * - ``on_key_press(key, modifiers, viewer)``
     - Bei jedem Tastendruck, den der Viewer empfängt, vor seinen eingebauten Tasten und den
       Belegungen aus den Tastenkürzel-Einstellungen; die Plugins werden in Ladereihenfolge
       gefragt. Eine Taste, die ein Menü- oder Fenster-Tastenkürzel zuerst abfängt, erreicht den
       Viewer nie
     - ``key``: ein ``Qt.Key``-Code (int); ``modifiers``: ``Qt.KeyboardModifier``-Flags. Geben
       Sie ``True`` zurück, um die Taste zu konsumieren — spätere Plugins und die
       Standardbehandlung werden übersprungen; geben Sie ``False`` (Standard) zurück, um sie
       weiterzureichen. Eine Ausnahme zählt als ``False``
   * - ``on_pet_created(pet)``
     - Wenn der Desktop-Pet-Tab das Pet-Fenster erstellt, und direkt nachdem das Plugin geladen
       wurde (oder ``Reload Plugins`` läuft), falls das Pet bereits existiert
     - ``pet``: das Pet-Fenster. Plugins verwenden ``play_group(group)``, ``speak(line)``,
       ``speak_notification(line)``, ``speech_on``, ``setting(key, default)``,
       ``persist(**fields)``, ``add_integration(key, controller)`` /
       ``remove_integration(key)`` / ``integration(key)`` und die Signale ``hit_triggered``,
       ``moved`` und ``visibility_changed``. Rückgabewert wird ignoriert
   * - ``on_app_closing(main_window)``
     - Wenn das letzte Hauptfenster geschlossen wird, nachdem die Abfrage zu ungespeicherten
       Paint-Tabs bestätigt und die Einstellungen gespeichert wurden, kurz bevor die Plugins
       entladen werden; das Schließen eines anderen Fensters ruft ihn nicht auf
     - ``main_window``: das sich schließende ``ImervueMainWindow``. Rückgabewert wird ignoriert
   * - ``on_plugin_unloaded()``
     - Wenn das Fenster des Plugins geschlossen wird (nach ``on_app_closing`` beim letzten
       Fenster) und bevor ``Reload Plugins`` die Plugins erneut lädt; Plugins werden in
       umgekehrter Ladereihenfolge entladen
     - Keine Argumente; Rückgabewert wird ignoriert

----

Sprache
-------

Die Oberflächensprache lässt sich über das ``Sprache``-Menü umschalten:

- English
- Traditional Chinese (繁體中文)
- Simplified Chinese (简体中文)
- Korean (한국어)
- Japanese (日本語)

Nach dem Umschalten ist ein Neustart erforderlich.

Plugins können eigene Sprachen hinzufügen. **Español** wird genau so bereitgestellt:
Installiere das Plugin ``spanish_translation`` über den Plugin-Downloader, und es erscheint im
Menü ``Language`` neben den fünf eingebauten Sprachen. Ein Plugin kann auch Übersetzungen zu
einer bestehenden Sprache beisteuern; bereits vorhandene Schlüssel werden nie überschrieben,
ein Plugin kann also keine mitgelieferte Zeichenkette kaputt machen.

----

Tastenkürzel-Referenz
---------------------

Durchsuchen
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``Links`` / ``Rechts``
     - Vorheriges / nächstes Bild
   * - Pfeiltasten
     - Fokusrahmen über die Miniaturansichten bewegen
   * - ``Ctrl + Shift + Links`` / ``Rechts``
     - Zum vorherigen / nächsten Geschwisterordner mit Bildern springen
   * - ``Alt + Links`` / ``Alt + Rechts``
     - Verlauf vor / zurück (browserähnlich)
   * - ``Ctrl + G``
     - Zu Bildnummer springen
   * - ``X``
     - Zu einem zufälligen Bild springen
   * - Mausrad / Pinch
     - Heran-/Herauszoomen
   * - Horizontales Wischen
     - Vorheriges / nächstes Bild
   * - Mittelklick-Ziehen
     - Schwenken
   * - ``F``
     - Vollbild
   * - ``Shift + Tab``
     - Theatermodus (alles Chrome ausblenden)
   * - ``Ctrl + L``
     - Raster ↔ Liste (Detail) Anzeigemodus umschalten
   * - ``Shift + S``
     - Geteilte Ansicht (zwei Bilder nebeneinander)
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - Doppelseitenlesen / RTL (Manga)
   * - ``Ctrl + Shift + M``
     - Aktuelles Bild auf einem zweiten Monitor spiegeln
   * - ``Esc``
     - Zurück zu Miniaturansichten / Vollbild verlassen / Doppel- oder Listenmodus schließen
   * - ``W``
     - An Breite anpassen
   * - ``Shift + W``
     - An Höhe anpassen
   * - ``Shift + F``
     - An Fenster anpassen
   * - ``-`` / ``=``
     - Herauszoomen / hineinzoomen
   * - ``V``
     - Lesemodus: an Breite anpassen, zum Lesen scrollen, am Ende weiter zum nächsten Bild
   * - ``Home``
     - Ganzes Bild in das Fenster einpassen (im Grid: zurück nach oben)

Bearbeiten
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``E``
     - Annotationseditor öffnen
   * - ``R``
     - Im Uhrzeigersinn drehen
   * - ``Shift + R``
     - Gegen Uhrzeigersinn drehen
   * - ``Ctrl + Z``
     - Rückgängig
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Wiederherstellen
   * - ``Delete``
     - Bild löschen

Organisieren
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``0``
     - Favorit umschalten
   * - ``1`` -- ``5``
     - Bewerten (erneut drücken zum Löschen)
   * - ``F1`` -- ``F5``
     - Farbetikett: rot / gelb / grün / blau / lila (gleiche Taste zum Löschen)
   * - ``P``
     - Cull: Pick (Behaltflag)
   * - ``Shift + X``
     - Cull: Reject
   * - ``U``
     - Cull: Flag entfernen
   * - ``B``
     - Lesezeichen umschalten
   * - ``T``
     - Tags & Alben-Manager

Werkzeuge und Overlays
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``Ctrl + F`` / ``/``
     - Fuzzy-Suche mit Teilstring-Hervorhebung
   * - ``Ctrl + C``
     - Bild in Zwischenablage kopieren
   * - ``Ctrl + V``
     - Aus Zwischenablage einfügen
   * - ``H``
     - RGB-Histogramm
   * - ``F8`` / ``Ctrl + F8``
     - OSD-Info-Overlay / Debug-HUD (VRAM, Cache, Threads)
   * - ``Shift + P``
     - Pixel-Ansicht (ab 400 % zeigt RGB / HEX unter dem Cursor; das Raster, sobald ≤ 40.000 Bildpixel auf dem Bildschirm sind)
   * - ``Shift + M``
     - Farbmodi durchschalten (Normal / Graustufen / Invertieren / Sepia)
   * - ``L``
     - Lupe: ein Vergrößerungsglas, das dem Cursor folgt (auch über den Miniaturansichten)
   * - ``S``
     - Diashow
   * - ``Ctrl + Shift + P``
     - Command Palette
   * - ``Alt + M``
     - Letztes Macro auf der Auswahl wiederholen

Animierte Bilder
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``Space``
     - Abspielen / Pause
   * - ``,``
     - Vorheriger Frame
   * - ``.``
     - Nächster Frame
   * - ``[``
     - Verlangsamen
   * - ``]``
     - Beschleunigen

Paint
^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``[`` / ``]``
     - Pinselgröße um 1 px verkleinern / vergrößern
   * - ``Shift + [`` / ``Shift + ]``
     - Pinselgröße um 5 px verkleinern / vergrößern
   * - ``Ctrl + Z``
     - Rückgängig
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Wiederholen
   * - ``Ctrl + D``
     - Auswahl aufheben
   * - ``Ctrl + 0`` / ``Ctrl + 1``
     - An Fenster anpassen / Originalgröße (100 %)
   * - ``X``
     - Vorder- / Hintergrundfarbe tauschen
   * - ``D``
     - Farben auf Schwarz / Weiß zurücksetzen
   * - ``Ctrl + Tab`` / ``Ctrl + Shift + Tab``
     - Nächster / vorheriger Paint-Tab

Die Werkzeugtasten stehen unter *Werkzeugpalette (linke Leiste)*. ``Settings`` > ``Shortcuts…`` im
Paint-Tab belegt die Tasten für Werkzeuge, Pinselgröße, Layer, Rückgängig / Wiederholen, Auswahl
aufheben, Ansicht und Farben neu (``Ctrl + Y`` bleibt eine zweite Taste für Wiederholen).

----

Bibliotheks- und Metadatenverwaltung
------------------------------------

Imervue führt einen SQLite-gestützten Index unter ``%LOCALAPPDATA%/Imervue/library.db``
(Windows) bzw. ``~/.cache/imervue/library.db`` (POSIX) für ordnerübergreifende Suche,
hierarchische Tags, Smart-Alben, perzeptuelle Hashes, Notizen und Cull-Flags.
Alles unten Befindliche liegt unter ``Extra Tools``, sofern nicht anders vermerkt.
Ab der neuesten Version ist das Menü in acht funktionsgruppierte Untermenüs gegliedert —
``Batch``, ``Library & Metadata``, ``Views``, ``Workflow``, ``Export``,
``Develop (Non-Destructive)``, ``Retouch & Transform`` und ``Multi-Image`` —
sodass jeder Pfad unten als ``Extra Tools`` > ``<Untermenü>`` > ``<Werkzeug>`` angezeigt wird.

Bibliothekssuche
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` ermöglicht das Hinzufügen
eines oder mehrerer **Root-Ordner** zu einem globalen Index, der in einem Hintergrundthread
gecrawlt wird. Sobald ein Root indiziert ist, können Sie ihn nach Dateiname,
Mindestbreite / -höhe und Dateigröße durchsuchen (bis zu 2000 Treffer); ein Doppelklick
auf einen Treffer öffnet ihn. Ein erneuter Scan liest nur Dateien, die seit dem letzten Scan neu sind oder sich geändert
haben, und bei aktiviertem **Compute perceptual hash** auch früher ohne Hash indizierte
Dateien; die gelesenen Dateien werden in mehreren Threads gleichzeitig dekodiert.

Rechtsklick > ``Search by Query…`` filtert den aktuellen Ordner mit einer kompakten Abfragesprache, zum Beispiel ``kw:beach rating:>=4 type:video place:Paris``. ``place:`` nimmt eine Stadt, ein Land oder beides (``Paris``, ``France``, ``Paris, France``); ein Wert mit Leerzeichen steht in doppelten Anführungszeichen (``place:"Rio de Janeiro"``).

Smart-Alben
^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` speichert Filterregeln
(Erweiterungen, Mindestabmessungen, Farbetiketten, Bewertung, Favoriten, Cull-Status,
hierarchische Tags, Namens-Teilstring) unter einem freundlichen Namen. Erneutes Anwenden
eines Albums filtert den aktiven Ordner nach den gespeicherten Regeln.

Ähnliche-Bilder-Suche
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` führt einen 64-Bit-DCT-pHash
auf dem aktuellen Deep-Zoom-Bild (oder der ersten ausgewählten Kachel) aus und listet
nahe Treffer aus dem Index, sortiert nach Hamming-Distanz. Stellen Sie
``Max Hamming distance`` ein, um das Netz zu verbreitern oder zu straffen.

Semantische Suche (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Semantic Search`` ermöglicht das Eintippen einer natürlichsprachigen
Phrase (zum Beispiel *"golden retriever in snow"* oder *"neon street at night"*) und
gibt die Bilder des geöffneten Ordners geordnet zurück. Jedes Bild wird mit einem
CLIP-Vision-/Language-Encoder eingebettet und neben seinem Pfad gespeichert; eine
Textabfrage wird in denselben Vektorraum eingebettet und per Kosinus-Ähnlichkeit verglichen.

Embeddings werden in ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) bzw. ``~/.cache/imervue/clip_cache.npz`` (POSIX) als einzelnes kompaktes ``.npz``-Archiv gecacht. Der Dialog durchsucht den geöffneten Ordner: Er bettet nur die Bilder ein, die der Cache noch nicht hat oder die sich seitdem geändert haben (Größe oder Änderungszeit), sodass eine erneute Suche im selben Ordner sofort beginnt; die Ergebnisse stammen nur aus diesem Ordner.

.. note::
   Semantische Suche führt CLIP ViT-B/32 auf ``onnxruntime`` aus, ohne PyTorch. Wenn Sie
   sie zum ersten Mal ohne ``onnxruntime`` öffnen, bietet Imervue an, es zu installieren;
   das Modell (etwa 150 MB, int8-quantisiert) wird dann einmalig in einer festgelegten
   Revision von Hugging Face heruntergeladen und danach aus dem lokalen Cache gelesen. Es
   läuft über CUDA auf einer NVIDIA-GPU, wenn ``onnxruntime`` CUDA unterstützt, sonst auf
   der CPU; eine integrierte GPU wählt es nie. Von einem anderen Modell gecachte Embeddings
   werden neu berechnet.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` wendet heuristische Tags
unter ``auto/...`` an (``photo`` / ``document`` / ``screenshot`` / ``graphic`` /
``landscape`` / ``portrait``), abgeleitet aus Farbsättigung, Kanten und Form des Bildes, so wie der
Betrachter es anzeigt. Läuft in einem Worker-Thread mit Live-Fortschrittsbalken.

Sobald die Semantische Suche das CLIP-Modell heruntergeladen hat, vergibt Auto-Tag die
Labels stattdessen per Zero-Shot mit diesem Modell: bis zu drei aus ``photo``,
``document``, ``screenshot``, ``graphic``, ``illustration``, ``portrait``, ``landscape``,
``animal``, ``food`` und ``text``, das ähnlichste zuerst. Ein Bild, das CLIP nicht lesen
kann, erhält die heuristischen Tags, und Auto-Tag startet den Download nie selbst.

Hierarchische Tags
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` verwaltet baumstrukturierte
Tags wie ``animal/cat/british``. Wählen Sie ein Tag, um jedes Bild unter diesem Zweig
(Nachfahren inbegriffen) zu sehen. Aktuelle Auswahl mit einem Klick taggen oder enttaggen.
Hierarchische Tags leben im Bibliotheksindex und ergänzen das flache Tag-System im
Rechtsklick-Menü.

Rechtsklick > ``Stapeloperationen`` > ``Index Keywords`` (bei ausgewählten Miniaturansichten)
übernimmt die XMP-Stichwörter der Auswahl in die Bibliothek. Eine von Lightroom oder
darktable geschriebene Stichwort-Hierarchie (``lr:hierarchicalSubject``,
``Places|Taiwan|Taipei``) wird als Tag-Pfad
``Places/Taiwan/Taipei`` abgelegt; lose Stichwörter ``Places`` / ``Taiwan`` /
``Taipei``, die nur ihre Ebenen wiederholen, kommen nicht noch einmal hinzu.

Token-Stapel-Umbenennen
^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` öffnet eine Live-Vorschau-Tabelle,
in der Sie eine Vorlage wie ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` eingeben
und genau sehen, wozu jede Datei umbenannt wird. Konflikte werden hervorgehoben, damit
nichts überschrieben wird. Unterstützte Token: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``. Ein neuer Name, den gerade eine andere ausgewählte
Datei trägt, ist kein Konflikt: Neunummerieren (``002`` → ``003``, während ``003`` →
``004``) oder das Tauschen zweier Namen benennt die ganze Auswahl um. Batch Rename
verhält sich genauso.

Metadaten-Export
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` schreibt eine
Zeile pro Bild in der aktuellen Ansicht mit EXIF, Abmessungen, Farbetikett, Bewertung,
Favorit, hierarchischen Tags, Cull-Status und Notizen. Nützlich, um Cull-Entscheidungen
in eine Tabelle oder einen externen Workflow einzuspeisen.

XMP-Sidecars
^^^^^^^^^^^^

Imervue kann Adobe-XMP-Sidecar-Dateien (``photo.jpg`` ↔ ``photo.xmp``) lesen und
schreiben, sodass Bewertungen, Titel, Beschreibungen, Stichwörter und Farbetiketten
mit Adobe Bridge und anderen XMP-fähigen Foto-Managern sauber hin- und herwandern.

Beim Speichern wird in eine vorhandene Sidecar-Datei eingefügt: nur diese Felder ändern sich, dort gespeicherte Entwicklungseinstellungen, Zuschnitt und Verlauf eines RAW-Entwicklers bleiben erhalten, und eine nicht lesbare Sidecar-Datei wird nie überschrieben.

Neben ``photo.xmp`` (Lightroom, Bridge) wird auch die von darktable und digiKam
geschriebene ``photo.jpg.xmp`` gelesen und aktualisiert, wenn sie die einzige
Sidecar-Datei ist. Farbetiketten werden in Lightrooms Wörtern (``Red`` … ``Purple``)
und in Bridges (``Select``, ``Second``, ``Approved``, ``Review``, ``To Do``)
verstanden. Eine neue oder geänderte Farbe wird so exportiert, wie Lightroom sie
schreibt; eine Sidecar-Datei, die für dieselbe Farbe bereits Bridges Wort enthält,
behält dieses Wort. Ein Etikett ohne Farbe (ein eigenes) bleibt in der
Sidecar-Datei stehen.

Ein abgelehntes Foto — ``xmp:Rating`` -1 in Lightroom, Bridge und darktable —
wird als Culling-**Reject** ohne Sterne importiert, und ein Reject wird als -1
exportiert. Eine nicht abgelehnte Sidecar-Datei hebt ein Reject auf; ein Pick
bleibt unberührt.

Eine Datei ohne Sidecar wird aus dem gelesen — und importiert —, was sie selbst
einbettet: ihrem XMP-Paket (JPEG, PNG, WebP, TIFF, CR3, RW2, ORF, RAF), dann ihrem EXIF-``Rating`` /
``RatingPercent``. Dort speichert Lightroom Bewertung und Stichwörter eines JPEG,
und dort legen der Windows-Explorer und manche Kameras ihre Sterne ab. Eine
vorhandene Sidecar-Datei hat Vorrang.

``Extra Tools`` > ``Library & Metadata`` > ``XMP Sidecars`` hat zwei Schaltflächen, die für jedes
Bild in der aktuellen Ansicht gelten:

- **Export sidecars** — schreibt Bewertung / Titel / Beschreibung / Stichwörter /
  Farbetikett jedes Bildes in seinen Sidecar.
- **Import sidecars** — liest sie zurück in Imervues eigene Datensätze.

XML-Parsing verwendet ``defusedxml``, sodass fehlerhafte oder bösartige Sidecars
keine XXE- / Billion-Laughs-Angriffe auslösen können.

Die **EXIF-Seitenleiste** zeigt außerdem einen anklickbaren **Sterne-Bewertungsstreifen** —
die dort gesetzte Bewertung ist die, die der XMP-Export schreibt.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

Ein dreiwertiges Cull-Flag. Drücken Sie ``P``, um das aktuelle Bild oder
jede ausgewählte Kachel zu picken, ``Shift + X`` zum Verwerfen, ``U`` zum Entfernen
des Flags. ``Filter`` > ``By Cull State`` zeigt nur Picks, Rejects oder Ungeflaggte
an. ``Extra Tools`` > ``Workflow`` > ``Culling`` wendet den Filter über einen Dialog an und stellt
außerdem eine Schaltfläche **Delete all rejects** zur Verfügung, die die geflaggten
Dateien dauerhaft von der Festplatte entfernt.

Staging-Tray
^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` ist ein ordnerübergreifender Korb.
Beliebige Kacheln zur Schale hinzufügen (die Liste überlebt Neustarts), dann den
gesamten Inhalt der Schale in einen Zielordner mit einem Klick verschieben oder
kopieren. Nützlich, um Picks aus vielen Shoots vor dem Export zu sammeln.

Dual-Pane-Dateimanager
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` öffnet eine Zwei-Baum-
Dual-Pane-Ansicht. Wählen Sie in jedem Pane einen Ordner und verschieben / kopieren
Sie die Auswahl dazwischen, ohne Imervue zu verlassen.

Zeitleisten-Ansicht
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` gruppiert das aktuelle Bildset nach Tag,
Monat oder Jahr (datumsgruppiert). Das Datum stammt aus EXIF ``DateTimeOriginal``,
danach aus ``DateTimeDigitized``, danach aus ``DateTime`` und andernfalls aus der
Datei-Änderungszeit. Doppelklicken Sie auf ein beliebiges Bild, um es in Deep Zoom
zu öffnen.

Drag-out zu externen Apps
^^^^^^^^^^^^^^^^^^^^^^^^^

Drücken und ziehen Sie von einer **ausgewählten** Kachel, um die Datei in Explorer,
Chrome, Discord oder jede App zu droppen, die Datei-URLs akzeptiert. Die Drag-Vorschau
ist die Kachel-Miniaturansicht.

Bildbezogene Notizen
^^^^^^^^^^^^^^^^^^^^

Die EXIF-Seitenleiste enthält ein freies **Notizen**-Textfeld. Das Tippen speichert
nach einer kurzen Debounce automatisch in den Bibliotheksindex. Notizen wandern mit
dem Bildpfad mit, sodass sie Ordner-Neuscans überleben.

----

Erweiterte Entwicklung und Compositing
--------------------------------------

Tonwertkurve
^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` öffnet einen
Kurveneditor mit ziehbaren Punkten und vier Kanälen (RGB, R, G, B). Linksklick auf
eine leere Leinwand fügt einen Punkt hinzu; ziehen zum Verschieben; Rechtsklick zum
Löschen. Punkte werden mit einem monotonen kubischen Spline interpoliert und im
Recipe des Bildes gespeichert, sodass die Kurve zur Renderzeit nicht-destruktiv
angewendet wird.

.cube-LUT anwenden
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` lässt Sie eine
beliebige Adobe-``.cube``-Datei (3D bis zu 65³, 1D bis zu 65.536 Punkte) wählen. ``LUT_1D_INPUT_RANGE`` / ``LUT_3D_INPUT_RANGE``
von DaVinci Resolve legt den Eingabebereich wie ``DOMAIN_MIN`` / ``DOMAIN_MAX``
fest, und auch eine Datei mit BOM wird gelesen. Die LUT wird mit
einem ``lru_cache`` mit Schlüssel Pfad + mtime geparst, mit trilinearer Interpolation
ausgewertet und über einen Intensitäts-Schieberegler gegen das Original gemischt.
Der LUT-Pfad und die Intensität leben im Recipe.

Virtuelle Kopien
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` gibt jedem Bild benannte Recipe-
Snapshots. Schnappen Sie die aktuelle Bearbeitung, experimentieren Sie weiter, und
wechseln Sie später zu einer früheren Variante zurück. Varianten sitzen neben dem
Master-Recipe im Recipe-Store und überleben das Zurücksetzen des Masters auf Identität.

HDR-Merge
^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` kombiniert zwei oder mehr
belichtungsgereihte Aufnahmen über OpenCVs Mertens-Belichtungsfusion zu einem
einzigen Bild. Die optionale "Align exposures"-Checkbox führt zuerst
``cv2.AlignMTB`` aus, um leichtes Verwackeln auszugleichen. Die Ausgabe wird in
eine vom Benutzer gewählte Datei gespeichert — keines der Quellbilder wird berührt.

Panorama-Stitching
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` umhüllt die High-Level-
``Stitcher``-API von OpenCV. Wählen Sie **Panorama**-Modus für Landschaften /
Stadtansichten oder **Scans**-Modus für flache Dokumente und Kunstwerke. Schwarze
Kanten, die durch das Warp entstehen, können automatisch zugeschnitten werden.

Focus-Stacking
^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` verschmilzt mehrere Aufnahmen,
die bei unterschiedlichen Fokusabständen aufgenommen wurden. Für jedes Pixel wählt
der Algorithmus den Eingaberahmen mit der höchsten lokalen Schärfe (Laplacian-Varianz)
und glättet dann die Auswahlmaske mit einer Gauß-Überblendung, um Nähte zu vermeiden.
ECC-Ausrichtung ist standardmäßig aktiv für leichte Handheld-Versätze.

Healing-Brush
^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` zeigt das aktuelle
Bild mit bis zu 720 px Langseite. Linksklick fügt einen runden Spot hinzu;
Rechtsklick auf einen existierenden Spot entfernt ihn; der Radius-Schieberegler
setzt die Größe neuer Spots. Beim Anwenden füllt OpenCV-Inpainting (Telea für
Geschwindigkeit, Navier-Stokes für weicheres Verblenden) jede maskierte Region
aus umliegenden Pixeln und das Ergebnis wird in eine neue Datei gespeichert.

Objektivkorrektur
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` stellt vier reine
Numpy-Schieberegler bereit: radiale Verzerrung ``k1`` (Tonne / Kissen),
Vignetten-Anhebung und kanalweise chromatische Aberrations-Radialskalierung für
Rot und Blau. Das korrigierte Bild, so groß wie das Original, wird als neue Datei
gespeichert.

Kartenansicht
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` plottet die geotaggten Bilder des geöffneten
Ordners auf einer interaktiven Leaflet + OpenStreetMap-Karte, mit einer Markierung pro
nächstgelegener Stadt samt der Anzahl der Bilder dort (benötigt
``PySide6.QtWebEngineWidgets``). Ohne WebEngine fällt der Dialog auf eine Liste dieser
Orte mit ihrer Anzahl und ihren Koordinaten zurück, damit das Feature auf minimalen
Installationen verwendbar bleibt.

Kalenderansicht
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` zeigt ein ``QCalendarWidget``, in
dem Tage hervorgehoben werden, an denen Fotos aufgenommen wurden (EXIF
``DateTimeOriginal`` → ``DateTimeDigitized`` → ``DateTime`` → Datei-mtime).
Auswählen eines Datums listet seine Bilder; Doppelklick öffnet eines im
Hauptbetrachter.

Gesichtserkennung
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` führt OpenCVs Haar-
Frontalgesichts-Cascade auf dem aktuellen Bild aus und zeichnet jede Detektion als
Rechteck. Doppelklick auf eine Zeile in der Liste, um einen Personennamen einzugeben;
beim Speichern werden die Tags in den ``extra['face_tags']``-Blob des Recipes
geschrieben. Detection ist eine klassische Technik — die Genauigkeit reicht für
"Zeige mir die Gesichter", ersetzt aber keine moderne CNN-basierte Erkennung.
Benötigt OpenCV 4 (``pip install "opencv-python<5"``): OpenCV 5 enthält die
Haar-Cascades nicht mehr, und der Dialog weist dann darauf hin, statt zu erkennen.

Lokale Anpassungsmasken
^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` legt
Pinsel-, Radial- oder Lineargradient-Masken über das Bild. Jede Maske trägt ihre
eigenen Deltas für Belichtung, Helligkeit, Kontrast, Sättigung, Temperatur, Tönung
plus einen Feder-Schieberegler. Masken werden in ``recipe.extra['masks']`` gespeichert
und beim Laden nicht-destruktiv angewendet, sodass die zugrundeliegende Datei nie
berührt wird.

Split-Toning
^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` wendet
unterschiedliche Farbtöne auf Schatten und Lichter mit pro-Region-Sättigung und
einem Balance-Pivot an. In ``recipe.extra['split_toning']`` gespeichert und in
der Entwicklungs-Pipeline nach der Tonwertkurve angewendet.

Klonstempel
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` kopiert ein federngefedertes
Quell-Patch auf ein Ziel — das Hartkanten-Pendant zum Healing-Brush. Shift+Klick legt
die Quelle fest, ein normaler Klick stempelt, Rechtsklick macht rückgängig. Das
Ergebnis wird in eine neue Datei geschrieben, sodass das Original intakt bleibt.

Zuschneiden / Begradigen
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` kombiniert ein
normalisiertes (0..1) Zuschnitt-Rechteck mit einem Begradigungs-Winkel von bis zu ±15°.
Die Ausgabe wird auf das größte innere Rechteck zugeschnitten, sodass gedrehte Fotos
keine schwarzen Ecken haben.

Automatisches Begradigen
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` erkennt den dominanten
Horizont oder vertikale Linien per Hough-Liniendetektion und schlägt eine Rotation
vor. Ein Klick wendet die Begradigung an; Sie können den Winkel zuvor anpassen, falls
die Auto-Detektion die falsche Referenz wählt.

Rauschreduktion / Schärfen
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` wendet
eine bilaterale (kantenwahrende) Rauschreduktion gefolgt von einem Unsharp-Mask-Schärfen
an. "Nur Luminanz" lässt Farbrauschen intakt, glättet aber Körnung ohne
Chroma-Kanten zu verschmieren.

Himmel / Hintergrund
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` ersetzt erkannten Himmel
durch einen Gradient oder entfernt den Hintergrund nach transparent / weiß. Wenn ``rembg``
(U²-Net) installiert ist, kommt die Vordergrundmaske aus dem Segmentierungsnetzwerk;
andernfalls wird die heuristische HSV-Regel verwendet.

Soft-Proof
^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` lädt ein ICC-Profil,
konvertiert das Bild durch es hindurch und zurück und hebt in Magenta die Pixel hervor,
die bei diesem Round-Trip beschnitten wurden — eine schnelle Außer-Gamut-Prüfung vor
dem Druck.

Tonwert- und Kreativeffekte
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` bündelt eine Reihe von Einmal-Effekten,
die angewendet und gleich gespeichert werden. Jeder ist ein schlanker Schieberegler-Dialog
über einer reinen NumPy-Transformation (Frame & Caption zeichnet mit Pillow; dieselbe
Logik steht auch als MCP-Werkzeug bereit):

- **Graduated Density** — ein linearer Neutraldichte-Gradient, festgelegt über Winkel,
  Härte und Versatz, optional eingefärbt; dunkelt Himmel oder Vordergrund ohne
  manuelle Maske ab.
- **Tone Equalizer** — eigene Belichtung pro Luminanzzone (je ein Schieberegler von
  Schwarz bis Weiß) über einer geglätteten Maske, sodass die Anpassung den Tonwerten
  der Szene folgt.
- **Detail Equalizer** — ein Verstärkungsregler pro Frequenzband (feine Textur →
  grober Kontrast), die mehrskalige Alternative zu einem einzelnen Klarheitsregler.
- **Filmic Tone Map** — ein sanftes Abrollen der Lichter nach Reinhard oder Hable mit
  Kontrast um einen Drehpunkt und Sättigungswiederherstellung, für kontrastreiche
  Einzelbelichtungen.
- **Velvia** — eine luminanzgewichtete Sättigungsanhebung, die gedämpfte Farben
  verstärkt und bereits gesättigte Farben sowie die Schatten schont.
- **Film Negative** — ein gescanntes Farbnegativ umkehren und dabei die automatisch
  geschätzte orange Filmbasis herausrechnen, mit einem Schieberegler für das
  Ausgabe-Gamma.
- **Defringe** — violette / grüne Farbsäume durch chromatische Aberration entlang
  kontrastreicher Kanten entsättigen; flächige Farben bleiben unberührt.
- **Emboss** — ein Relief mit gerichtetem Licht aus dem Luminanz-Höhenfeld
  (Azimut / Elevation / Tiefe + Graustufen-Schalter).
- **Polar Coordinates** — das Bild zu einer Scheibe aufwickeln oder abwickeln (der
  Tiny-Planet- bzw. Polarinversions-Look).
- **Kaleidoscope** — einen Winkelsektor zu ``n``-facher Symmetrie spiegeln.
- **Frosted Glass** — eine deterministische, über einen Seed reproduzierbare lokale
  Pixelstreuung.
- **Frame & Caption** — ein Passepartout-Rand in beliebiger Farbe, ein optionaler
  breiterer unterer Streifen im Polaroid-Stil und eine darin eingebrannte
  Bildunterschrift in eigener Farbe.

GPS-Geotag
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` liest beliebige vorhandene
EXIF-GPS-Tags und lässt Sie neue Dezimalgrad-Koordinaten bearbeiten oder setzen.
Ein JPEG wird ohne Zusatzpaket direkt beschrieben: nur sein EXIF-Block ändert sich, Pixel,
übrige Tags und Vorschaubild bleiben erhalten. WebP wird genauso behandelt; andere Formate lassen sich nicht taggen.

Der **EXIF-Editor** (Schaltfläche ``Edit EXIF`` in der EXIF-Seitenleiste) ändert Beschreibung, Künstler, Copyright, Kamerahersteller / -modell und Kommentar. Ein JPEG oder WebP braucht kein Zusatzpaket, nur sein EXIF-Block wird neu geschrieben; andere Formate zeigen an, warum sie nicht bearbeitbar sind.

Web-Galerie
^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Web Gallery`` schreibt die ausgewählten Bilder (oder den ganzen
Ordner) als eigenständige Website: ``index.html`` mit Lightbox, JPEG-Miniaturansichten und Kopien
der Originale, sofern Sie **Originale in voller Größe kopieren** nicht abwählen. Seitentitel sowie
Größe und Qualität der Miniaturansichten legen Sie selbst fest. Mit kopierten Originalen braucht
die Seite keinen Server: Öffnen Sie sie direkt von der Festplatte oder legen Sie sie auf einen
beliebigen statischen Host. Ohne sie zeigen die Links zur vollen Größe auf die Bilder auf Ihrer
eigenen Festplatte.

Aktivieren Sie **Kunden-Review**, wenn Sie Feedback zur Galerie einholen möchten. Unter jedem Bild
erscheint ein Kommentarfeld; die Notizen bleiben im Browser des Prüfers, und die Schaltfläche
**Export comments** der Seite speichert sie alle in einer einzigen JSON-Datei.

Druck-Layout
^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` komponiert mehrere Bilder auf einem
mehrseitigen PDF mit konfigurierbarer Seitengröße, Ausrichtung, Raster, Rändern,
Rinne und Schnittmarken. Erfordert ``reportlab``.

----

Extra-Tools-Menü-Referenz
-------------------------

Jeder Eintrag des Menüs ``Extra Tools``, Untermenü für Untermenü, in Menüreihenfolge. Viele haben
weiter oben einen ausführlicheren Abschnitt; diese Liste ist das vollständige Verzeichnis.
Einträge, die eine neue Datei speichern, schreiben sie neben die Quelle und hängen ``_1``,
``_2`` … an, wenn der Name schon vergeben ist; mit "im Rezept gespeichert" markierte Einträge
sind nicht-destruktive Bearbeitungen der Entwicklungseinstellungen des Bildes. Plugins können
diesen Untermenüs eigene Einträge hinzufügen.

Batch — Stapelverarbeitung
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``Batch Format Conversion``
     - Konvertiert die Bilder eines Ordners (standardmäßig des aktuellen Ordners) nach PNG, JPEG,
       WebP, BMP oder TIFF oder, wenn ihre Encoder installiert sind, nach HEIC / AVIF / JXL, mit
       Optionen für Qualität, Überspringen gleicher Formate und Verschieben der Originale in den
       Papierkorb.
   * - ``Batch EXIF Strip``
     - Entfernt aus Datenschutzgründen EXIF-, GPS- und andere Metadaten aus jedem Bild eines
       Ordners und überschreibt dabei entweder die Originale oder schreibt bereinigte Kopien in
       einen Ausgabeordner.
   * - ``Image Sanitizer``
     - Rendert die Bilder eines Ordners aus den reinen Pixeln neu, entfernt dabei alle versteckten
       Daten (Metadaten, Steganografie, angehängte Bytes) und benennt jedes nach Datum +
       Zufallszeichenkette um; kann kleine Bilder außerdem auf eine Zielauflösung hochskalieren,
       wie in ``AI Image Upscale``.
   * - ``Image Organizer``
     - Sortiert die Bilder eines Ordners in Unterordner nach Datum (Jahr-Monat oder Jahr),
       Auflösung, Dateityp, Dateigröße oder einer festen Anzahl pro Ordner und kopiert oder
       verschiebt sie dabei, mit Vorschau.
   * - ``Token Batch Rename``
     - Benennt die ausgewählten Bilder (oder den ganzen Ordner) nach einer Token-Vorlage wie
       ``{name}_{counter:04}`` oder ``{date}_{camera}`` um, mit einer Live-Vorschau, die Konflikte
       markiert; Sidecars, Bewertungen und Tags wandern mit den Dateien.
   * - ``Deflicker (Time-lapse)``
     - Gleicht die Helligkeit von Frame zu Frame über die Zeitraffer-Frames des aktuellen Ordners
       aus (Ziel: gleitender oder globaler Mittelwert) und schreibt die korrigierten Kopien in
       einen Unterordner ``deflickered/``; die Originale bleiben unberührt.
   * - ``Document Binarize``
     - Macht aus einem Foto oder Scan einer Seite sauberes Schwarz auf Weiß per adaptiver
       Sauvola-Schwellwertbildung (Regler für Fenstergröße und k) und speichert ``<name>_bw.png``
       neben der Quelle.
   * - ``Otsu Threshold``
     - Wandelt das aktuelle Bild an seinem automatisch gewählten globalen Otsu-Schwellwert in
       Schwarzweiß um, mit einer Option zum Invertieren, und speichert ``<name>_otsu.png``.
   * - ``Edit Animation``
     - Kehrt das aktuelle GIF, APNG oder animierte WebP um, macht daraus einen Boomerang, ändert
       sein Tempo (0,25x bis 4x) oder optimiert es (fasst wiederholte Frames zusammen) und
       speichert ``<name>_edited.gif``.
   * - ``Optimize to Target Size``
     - Kodiert das aktuelle Bild als JPEG oder WebP mit der höchsten Qualität neu, die in ein
       Größenbudget in KB passt, und speichert ``<name>_opt.jpg`` oder ``<name>_opt.webp``.
   * - ``Meme Caption``
     - Versieht das aktuelle Bild mit klassischen Meme-Beschriftungen oben und unten (weißer Text
       in Großbuchstaben mit schwarzer Kontur, mit Zeilenumbruch) und speichert
       ``<name>_meme.png``.
   * - ``Steganography``
     - Versteckt eine Textnachricht in den niederwertigsten Bits des aktuellen Bildes, gespeichert
       als verlustfreies ``<name>_stego.png``, oder deckt eine so versteckte Nachricht auf.

Library & Metadata — Bibliothek und Metadaten
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``Library Search``
     - Verwaltet die Stammordner der Bibliothek, scannt sie in den Index (optional mit
       Perceptual Hashes) und durchsucht ihn nach Dateiname, Mindestbreite / -höhe und Dateigröße
       in KB; ein Doppelklick auf ein Ergebnis öffnet es.
   * - ``Smart Albums``
     - Speichert regelbasierte Alben (Endungen, Name, Tags, Ort, Mindestgröße und
       Mindestbewertung, Farbetikett, Cull-Zustand, Favoriten) und zeigt ihre Treffer; kann aus
       GPS-Daten ein Album pro Stadt anlegen sowie Alben importieren oder exportieren.
   * - ``Find Similar Images``
     - Findet Bibliotheksbilder, die dem aktuellen (oder ersten ausgewählten) Bild ähneln, per
       Perceptual Hash innerhalb eines gewählten Hamming-Abstands; scannen Sie Ihre Stammordner
       zuvor in ``Library Search`` mit pHash.
   * - ``Semantic Search``
     - Findet Bilder im aktuellen Ordner, die zu einer Textbeschreibung wie "Strand bei
       Sonnenuntergang" passen, mit CLIP auf ``onnxruntime`` (wird bei der ersten Nutzung zur
       Installation angeboten); das ~150 MB große Modell wird einmalig heruntergeladen.
   * - ``Find Duplicate Images``
     - Durchsucht einen Ordner (optional mit Unterordnern) nach exakten Duplikaten per Datei-Hash
       oder nach ähnlich aussehenden Bildern per Perceptual Hash; kann in jeder Gruppe alle außer
       der besten Kopie vorauswählen und die Auswahl in den Papierkorb verschieben.
   * - ``Auto-Tag Images``
     - Versieht die ausgewählten Bilder oder den ganzen Ordner mit heuristischen Inhalts-Tags
       (photo, document, screenshot, graphic, landscape, portrait) unter ``auto/`` im
       hierarchischen Tag-Baum oder mit CLIP-Labels, sobald die semantische Suche ihr Modell
       heruntergeladen hat.
   * - ``Hierarchical Tags``
     - Legt baumstrukturierte Tags wie ``animal/cat/british`` an und löscht sie, listet die Bilder
       unter einem Tag auf und versieht die ausgewählten Kacheln mit einem Tag oder entfernt ihn.
   * - ``Export Metadata (CSV / JSON)``
     - Schreibt pro Bild der aktuellen Ansicht einen Datensatz (Dateidetails, wichtige EXIF-Felder
       wie Kamera, Objektiv, Belichtung und ISO, Bewertung, Farbetikett, Tags und Notiz) in eine
       CSV- oder JSON-Datei.
   * - ``XMP Sidecars``
     - Exportiert oder importiert ``.xmp``-Sidecar-Dateien für jedes Bild der aktuellen Ansicht,
       sodass Bewertung, Titel, Beschreibung, Stichwörter und Farbetikett verlustfrei mit Adobe
       Bridge, Lightroom und anderen XMP-fähigen Werkzeugen ausgetauscht werden.
   * - ``GPS Geotag``
     - Schreibt Breiten- und Längengrad (Dezimalgrad) in die EXIF-GPS-Tags des aktuellen Bildes
       und ersetzt dabei vorhandene; nur JPEG- und WebP-Dateien.
   * - ``Thumbnail Cache``
     - Zeigt, wie viel Speicherplatz der Miniaturansicht-Cache belegt, und leert ihn.

Views — Ansichten
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``By day``
     - Unter ``Timeline View``: ersetzt die Hauptansicht durch die Bilder des aktuellen Ordners,
       gruppiert unter einer Überschrift pro Aufnahmetag (EXIF-Datum, sonst Dateidatum); ein
       Doppelklick auf ein Bild öffnet es.
   * - ``By month``
     - Unter ``Timeline View``: dieselbe Zeitleiste, gruppiert nach Aufnahmemonat.
   * - ``By year``
     - Unter ``Timeline View``: dieselbe Zeitleiste, gruppiert nach Aufnahmejahr.
   * - ``Calendar View``
     - Zeigt einen Kalender, der die Tage mit Fotos im aktuellen Ordner hervorhebt (nach
       Aufnahmedatum); ein Klick auf einen Tag listet seine Bilder auf, ein Doppelklick auf eines
       öffnet es.
   * - ``Map View``
     - Zeigt die geotaggten Bilder des aktuellen Ordners auf einer OpenStreetMap-Karte, eine
       Markierung pro nächstgelegener Stadt mit Anzahl; die Karte wird online geladen, ohne
       QtWebEngine erscheint stattdessen eine Koordinatenliste.
   * - ``Scopes & Inspector``
     - Analysiert das aktuelle Bild in Tabs: Luminanz-Waveform, RGB-Parade,
       Falschfarben-Belichtung, Fokus-Peaking, Error Level Analysis und Klon-Erkennung
       (Copy-Move).
   * - ``Tiny Planet (360°)``
     - Projiziert ein equirektangulares 360°-Panorama im Format 2:1 in einen quadratischen
       "kleinen Planeten" gewählter Größe um und speichert ``<name>_planet.png``; warnt, wenn das
       Bild nicht 2:1 ist.
   * - ``Image Statistics``
     - Zeigt Mittelwert, Minimum, Maximum, Standardabweichung und Median der R-, G-, B- und
       Luminanzkanäle des aktuellen Bildes und exportiert sein Histogramm mit 256 Stufen als CSV.
   * - ``Quality Report``
     - Listet referenzfreie Qualitätsmetriken des aktuellen Bildes auf: Farbigkeit, tonale
       Entropie, RMS-Kontrast, Kantendichte und geschätztes Rauschen.
   * - ``Test Chart``
     - Erzeugt ein Kalibriermuster (SMPTE-Farbbalken, Graustufenkeil, Verlaufsrampe, Schachbrett
       oder Vollfarbe) in gewählter Breite und Höhe und speichert es in einer Datei.
   * - ``Off``
     - Unter ``Color blindness preview``: schaltet die Vorschau der Farbsehschwäche aus.
   * - ``Protanopia (red-blind)``
     - Unter ``Color blindness preview``: zeigt das Bild im Viewer so, wie eine Person mit
       Protanopie es sieht; nur Anzeige, die Datei und ihr Rezept bleiben unberührt.
   * - ``Deuteranopia (green-blind)``
     - Unter ``Color blindness preview``: simuliert Deuteranopie, die häufigste
       Rot-Grün-Schwäche; nur Anzeige.
   * - ``Tritanopia (blue-blind)``
     - Unter ``Color blindness preview``: simuliert Tritanopie (Blau-Gelb-Schwäche); nur Anzeige.
   * - ``Achromatopsia (greyscale)``
     - Unter ``Color blindness preview``: zeigt das Bild vollständig in Graustufen, wie bei
       Achromatopsie; nur Anzeige.

Workflow — Arbeitsablauf
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``Culling``
     - Filtert den aktuellen Ordner auf Picks, Rejects oder unmarkierte Bilder, sortiert
       automatisch aus, indem es in jeder Gruppe ähnlicher Bilder das schärfste auswählt und die
       übrigen verwirft, und kann jedes Reject endgültig löschen.
   * - ``Staging Tray``
     - Ein dauerhafter, ordnerübergreifender Korb: Fügen Sie die ausgewählten Kacheln oder das
       aktuelle Bild aus beliebigen Ordnern hinzu und verschieben oder kopieren Sie dann alle in
       einen Ordner, oder zeigen Sie die Ablage als Album an.
   * - ``Reference Panel``
     - Heftet Referenzbilder an (aus Dateien, per Drag-and-drop oder aus dem aktuellen Bild
       hinzugefügt), mit großer Vorschau für den direkten Vergleich; die Liste bleibt über
       Neustarts hinweg erhalten.
   * - ``Virtual Copies``
     - Speichert benannte Schnappschüsse des Entwicklungsrezepts des aktuellen Bildes und wechselt
       zwischen ihnen, ohne die Datei zu duplizieren.
   * - ``Dual-Pane File Manager``
     - Zwei Ordnerbäume nebeneinander, um die Auswahl vom einen in den anderen zu kopieren oder zu
       verschieben oder eine Datei im Viewer zu öffnen.
   * - ``Macros``
     - Zeichnet Macros aus Bewertungs-, Favoriten-, Farbetikett- und Tag-Aktionen auf den
       ausgewählten Bildern auf, bearbeitet, bereinigt und spielt sie ab.
   * - ``Watched Folder``
     - Überwacht, solange der Dialog geöffnet ist, einen Ordner (einschließlich Unterordnern) und
       weist jedem neu eintreffenden Bild ein gewähltes Entwicklungs-Preset zu, für Tethering- oder
       Import-Workflows ohne Handarbeit.

Export
^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``Contact Sheet PDF``
     - Ordnet Miniaturansichten der ausgewählten Bilder (oder des ganzen Ordners) in einem Raster
       aus Zeilen x Spalten auf A4-, A3-, Letter- oder Legal-Seiten an, mit Rändern, optionalem
       Titel und optionalen Dateinamen-Beschriftungen.
   * - ``Web Gallery``
     - Exportiert die ausgewählten Bilder (oder den ganzen Ordner) als eigenständige HTML-Galerie
       mit Miniaturansichten und Lightbox; kann die Originale kopieren und Kommentarfelder für das
       Kunden-Review hinzufügen, die sich als JSON exportieren lassen.
   * - ``Slideshow Video``
     - Rendert die ausgewählten Bilder (oder den ganzen Ordner) zu einer MP4 mit gewählter Größe,
       Bildrate, Standzeit, Qualität und Übergang (Überblenden, Auflösen, Schieben oder Wischen).
   * - ``Print Layout``
     - Kachelt Bilder auf ein mehrseitiges PDF-Raster mit Seitengröße, Ausrichtung, Zeilen,
       Spalten, Rand, Rinne und Schnittmarken; erfordert das optionale Paket ``reportlab``.
   * - ``Collage``
     - Setzt die ausgewählten Bilder (oder den ganzen Ordner) zu einer Rastermontage mit 1 bis 12
       Spalten zusammen und speichert ``collage.png`` neben dem ersten Bild.
   * - ``ID Photo Sheet``
     - Kachelt das aktuelle Porträt in einer Passbildgröße (35 x 45 mm, 2 x 2 in, 33 x 48 mm oder
       50 x 70 mm) auf 4x6-, 5x7-, A4- oder Letter-Papier bei 300 DPI und speichert
       ``<name>_idsheet.png``.

Develop (Non-Destructive) — nicht-destruktives Entwickeln
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``Before / After Compare``
     - Zeigt das aktuelle Bild ohne und mit seinem Entwicklungsrezept in einer Ansicht, geteilt
       durch eine verschiebbare Trennlinie.
   * - ``Develop Presets…``
     - Speichert das Rezept des aktuellen Bildes als benanntes Preset und wendet es dann auf das
       aktuelle Bild oder die Auswahl an oder übernimmt nur seine aktiven Anpassungen in deren
       eigene Rezepte.
   * - ``Tone Curve``
     - Bearbeitet eine RGB-Master-Kurve sowie getrennte Rot-, Grün- und Blaukurven über einem
       Histogramm (Klicken fügt einen Punkt hinzu, Ziehen verschiebt ihn, Rechtsklick entfernt
       ihn); im Rezept gespeichert.
   * - ``Apply .cube LUT``
     - Wendet eine 3D- oder 1D-LUT im Adobe-Format ``.cube`` mit einstellbarer Intensität an; im
       Rezept gespeichert, und ``Clear`` entfernt sie.
   * - ``Split Toning``
     - Tönt Schatten und Lichter mit getrenntem Farbton und getrennter Sättigung, dazu ein
       Balance-Regler; im Rezept gespeichert.
   * - ``Local Adjustment Masks``
     - Fügt Pinsel-, Radial- und lineare Verlaufsmasken hinzu, jede mit eigenen Reglern für
       Belichtung, Helligkeit, Kontrast, Sättigung, Temperatur, Tönung, Lichter, Schatten und
       Kantenweichheit; im Rezept gespeichert.
   * - ``Layers``
     - Stapelt bis zu acht Text-, Bild- oder LUT-Overlay-Layer mit Deckkraft und den Mischmodi
       Normal, Multiplizieren, Negativ multiplizieren oder Ineinanderkopieren; im Rezept
       gespeichert.
   * - ``Levels``
     - Setzt Schwarzpunkt, Weißpunkt und Gamma; im Rezept gespeichert.
   * - ``Channel Mixer``
     - Baut jeden Ausgabekanal aus gewichteten Rot-, Grün- und Blau-Eingängen plus einem Offset
       neu auf, mit einem Monochrom-Modus für die Schwarzweiß-Umwandlung; im Rezept gespeichert.
   * - ``Gradient Map``
     - Bildet die Luminanz über einen vordefinierten Verlauf (Mono, Sepia, Cyanotype, Fire,
       Ocean, Magenta–Teal) mit einstellbarer Intensität ab, optional im perzeptuellen OkLCH
       gemischt; im Rezept gespeichert.
   * - ``Auto Color Balance``
     - Entfernt Farbstiche mit der Methode Gray World, White Patch, Auto-Levels (Perzentil) oder
       Retinex, gemischt über einen Intensitätsregler, und speichert ``<name>_balanced.png``.
   * - ``Clarity / Dehaze``
     - Wendet die Lokalkontrast-Regler Dehaze, Clarity und Texture an und speichert
       ``<name>_local.png``.
   * - ``HSL / Color Mixer``
     - Passt Farbton, Sättigung und Luminanz getrennt für acht Farbbereiche (Rot bis Magenta) an
       und speichert ``<name>_hsl.png``.
   * - ``CLAHE (Local Equalize)``
     - Verstärkt den lokalen Kontrast mit kontrastbegrenztem adaptivem Histogrammausgleich
       (Clip-Limit und Kachelanzahl) auf der Luminanz und speichert ``<name>_clahe.png``.
   * - ``Flatten Background``
     - Entfernt einen weichen Hintergrundverlauf wie Lichtverschmutzung oder ungleichmäßige
       Beleuchtung (Subtrahieren) oder Vignettierung (Dividieren) in einstellbarem Grad und
       speichert ``<name>_flat.png``.
   * - ``Frame & Caption``
     - Fügt einen farbigen Passepartout-Rand, einen optionalen unteren Streifen im Polaroid-Stil
       und eine Bildunterschrift hinzu und speichert ``<name>_framed.png``.
   * - ``Ordered Dither``
     - Reduziert jeden Kanal mit einem geordneten Bayer-Dithermuster auf 2 bis 8 Stufen für einen
       Retro-Druck-Look und speichert ``<name>_dither.png``.
   * - ``Color Map``
     - Färbt die Luminanz des Bildes über die Farbskala Viridis, Magma oder Jet um und speichert
       ``<name>_colormap.png``.
   * - ``Distort``
     - Verwirbelt das Bild, zieht es zusammen / wölbt es aus oder legt Wellen darüber, mit
       einstellbarer Stärke, und speichert ``<name>_distort.png``.
   * - ``Polar Coordinates``
     - Wickelt das Bild zu einer Scheibe auf oder rollt eine Scheibe zu einem Streifen ab,
       optional mit invertiertem Radius, und speichert ``<name>_polar.png``.
   * - ``Kaleidoscope``
     - Spiegelt einen Keil um die Mitte zu einem symmetrischen Muster mit gewählter
       Segmentanzahl und Drehung und speichert ``<name>_kaleidoscope.png``.
   * - ``Frosted Glass``
     - Streut jedes Pixel an eine zufällige nahe Position (Radius in Pixeln, reproduzierbarer
       Seed) für einen Milchglas-Look und speichert ``<name>_frosted.png``.
   * - ``Pixel Sort``
     - Sortiert Pixel nach Helligkeit entlang Zeilen oder Spalten innerhalb eines unteren / oberen
       Helligkeitsbands für einen Glitch-Look und speichert ``<name>_pixelsort.png``.
   * - ``Film Grain``
     - Fügt prozedurales Filmkorn mit Reglern für Intensität, Korngröße, Monochrom und Seed hinzu;
       im Rezept gespeichert.
   * - ``Lens Flare``
     - Fügt an einer gewählten Position einen synthetischen Blendenfleck mit Reglern für
       Intensität, Halo-Größe und Farbe hinzu; im Rezept gespeichert.
   * - ``Threshold / Posterize``
     - Wendet einen Schwarzweiß-Schwellwert (0 bis 255) an und / oder posterisiert jeden Kanal auf
       2 bis 64 Stufen; im Rezept gespeichert.
   * - ``Solarize``
     - Kehrt die Tonwerte oberhalb eines Schwellwerts für einen Solarisations-Look wie in der
       Dunkelkammer um, gemischt über einen Mix-Regler, und speichert ``<name>_solarize.png``.
   * - ``Diffuse Glow``
     - Fügt ein weiches Leuchten im Orton-Stil mit Reglern für Stärke, Radius und
       Lichter-Schwellwert hinzu und speichert ``<name>_glow.png``.
   * - ``Graduated Density``
     - Dunkelt eine Seite des Bildes entlang einer geraden Linie ab wie ein Grauverlaufsfilter
       (Winkel, Blendenstufen, Härte, Versatz, optionale Tönung) und speichert
       ``<name>_gradnd.png``.
   * - ``Velvia``
     - Verstärkt gedämpfte Farben am stärksten, wie Velvia-Diafilm, mit Reglern für Stärke und
       Schattenschutz, und speichert ``<name>_velvia.png``.
   * - ``Emboss``
     - Erzeugt ein Relief, beleuchtet aus gewähltem Azimut und gewählter Elevation, mit einem
       Tiefenregler und einer Graustufen-Option, und speichert ``<name>_emboss.png``.
   * - ``Defringe``
     - Entsättigt violette, grüne oder alle farbigen Säume entlang kontrastreicher Kanten, mit
       Reglern für Stärke und Kantenschwellwert, und speichert ``<name>_defringe.png``.
   * - ``Film Negative``
     - Kehrt ein gescanntes Farbnegativ in ein Positiv um und entfernt dabei die orange Filmbasis
       (automatisch geschätzt), mit einem Ausgabe-Gamma, und speichert ``<name>_positive.png``.
   * - ``Filmic Tone Map``
     - Rollt die Lichter mit einer filmischen Reinhard- oder Hable-Kurve ab, mit Reglern für
       Belichtung, Weißpunkt, Kontrast und Sättigung, und speichert ``<name>_filmic.png``.
   * - ``Tone Equalizer``
     - Setzt die Belichtung getrennt für Schwarz, Schatten, Mitteltöne, Lichter und Weiß, mit
       Glättung gegen Halos, und speichert ``<name>_toneeq.png``.
   * - ``Detail Equalizer``
     - Verstärkt oder senkt den Kontrast getrennt in den feinen, mittleren, groben und breiten
       Detailbändern und speichert ``<name>_detaileq.png``.
   * - ``Soft Proof``
     - Zeigt eine Vorschau des aktuellen Bildes durch ein gewähltes ICC-Ausgabeprofil, färbt
       Pixel außerhalb des Farbumfangs magenta und zählt sie; es wird nichts gespeichert.

Retouch & Transform — Retusche und Transformation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``AI Image Upscale``
     - Skaliert einen Ordner mit Bildern per Real-ESRGAN (allgemein x4, Anime x4 oder x2) oder
       per Lanczos-, Bicubic- oder Nearest-Resampling hoch; die KI-Modelle installieren
       ``onnxruntime`` bei Bedarf und werden bei der ersten Nutzung automatisch heruntergeladen
       (~65 MB).
   * - ``Noise Reduction / Sharpening``
     - Wendet kantenerhaltende Rauschreduktion (optional nur auf die Luminanz) und
       Unscharf-Maskieren-Schärfung mit Stärke und Radius an und speichert in eine gewählte Datei;
       erfordert OpenCV (``opencv-python``).
   * - ``Healing Brush``
     - Entfernt die Flecken, die Sie in einer Vorschau anklicken (Rechtsklick löscht einen Fleck),
       per Inpainting mit der Telea- oder Navier-Stokes-Methode und speichert in eine gewählte
       Datei; erfordert OpenCV.
   * - ``Clone Stamp``
     - Kopiert ein Feld mit weicher Kante von einem per Shift-Klick gesetzten Quellpunkt an jeden
       Punkt, den Sie in einer Vorschau anklicken (Rechtsklick macht rückgängig), und speichert das
       Ergebnis in eine gewählte Datei.
   * - ``Frequency Separation``
     - Teilt das aktuelle Bild bei einem gewählten Weichzeichnungsradius in ``<name>_low.png``
       (Farbe und Ton) und ``<name>_high.png`` (Textur) zur Retusche in einem anderen Programm auf;
       zusammensetzen als low + (high - 128).
   * - ``Smart Crop``
     - Schlägt Saliency-basierte Zuschnitte vor (frei, 1:1, 4:5, 3:2, 16:9), die das Motiv auf
       einen Drittelpunkt setzen, und schreibt den gewählten als nicht-destruktiven Zuschnitt ins
       Rezept.
   * - ``Portrait Auto-Retouch``
     - Glättet Hauttonbereiche, entfernt rote Augen und fügt einen abschließenden
       Schärfedurchgang hinzu, jeweils mit eigenem Regler, und speichert ``<name>_retouched.png``.
   * - ``Face Detection``
     - Erkennt Gesichter im aktuellen Bild mit der Haar-Kaskade von OpenCV und lässt Sie jedes
       benennen; die Namen werden mit dem Rezept gespeichert. Erfordert OpenCV 4
       (``opencv-python<5``).
   * - ``Sky / Background``
     - Ersetzt den Himmel durch einen Verlauf oder entfernt den Hintergrund (transparent oder
       weiß) und speichert in eine gewählte Datei; benötigt OpenCV und verwendet ``rembg`` zum
       Freistellen des Hintergrunds, wenn installiert.
   * - ``Crop / Straighten``
     - Dreht um bis zu ±15° (die leeren Ecken werden abgeschnitten) und schneidet nach normierten
       Koordinaten oder einer Seitenverhältnis-Vorgabe zu, gespeichert in eine gewählte Datei; das
       Begradigen erfordert OpenCV.
   * - ``Auto-Straighten``
     - Misst die Neigung des Horizonts oder vertikaler Linien, lässt Sie die Drehung anpassen und
       speichert das begradigte Bild in eine gewählte Datei; erfordert OpenCV.
   * - ``Lens Correction``
     - Korrigiert Tonnen- / Kissenverzeichnung, Vignettierung und rote / blaue chromatische
       Aberration mit Reglern und speichert in eine gewählte Datei.
   * - ``Scale Bar``
     - Brennt aus einem Wert in Pixeln pro Einheit und einer Einheitenbezeichnung einen
       kalibrierten Maßstabsbalken in das aktuelle Bild ein und speichert
       ``<name>_scalebar.png``.

Multi-Image — Mehrbildverarbeitung
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Eintrag
     - Funktion
   * - ``HDR Merge``
     - Verschmilzt zwei oder mehr unterschiedlich belichtete Aufnahmen per Mertens-Exposure-Fusion
       (keine Belichtungsdaten nötig), optional nach vorheriger Ausrichtung; erfordert OpenCV.
   * - ``Panorama Stitch``
     - Fügt zwei oder mehr überlappende Aufnahmen, der Reihe nach mit 20 bis 40 % Überlappung
       aufgenommen, im Panorama- oder Flachscan-Modus zusammen, optional mit Beschnitt der
       schwarzen Ränder; erfordert OpenCV.
   * - ``Focus Stacking``
     - Verrechnet eine Fokusreihe zu einem durchgehend scharfen Bild, indem aus jedem Frame die
       schärfsten Pixel übernommen werden, optional nach vorheriger Ausrichtung; erfordert OpenCV.
   * - ``Image Stack``
     - Kombiniert eine bereits ausgerichtete Serie pixelweise per Mittelwert, Median, Maximum,
       Minimum oder Sigma-Clipping-Mittelwert, für Langzeitbelichtungen, das Entfernen von
       Menschenmengen oder Sternspuren; kein OpenCV nötig.
   * - ``Anaglyph 3D``
     - Kombiniert das aktuelle Bild (linkes Auge) mit einem gewählten Bild für das rechte Auge zu
       einem Rot-Cyan-Anaglyphen (Methode Dubois, Farbe, Grau oder echt) und speichert
       ``<name>_anaglyph.png``.

----

Kommandozeilen-Verwendung
-------------------------

::

   python -m Imervue                      # Normal starten
   python -m Imervue /path/to/image       # Bestimmtes Bild öffnen
   python -m Imervue /path/to/folder      # Bestimmten Ordner öffnen
   python -m Imervue --debug              # Debug-Modus aktivieren
   python -m Imervue --software_opengl    # Software-Rendering verwenden (wenn GPU nicht unterstützt)

Headless-Batch-CLI
^^^^^^^^^^^^^^^^^^

``Imervue.cli`` führt die reinen Bildoperationen in der Shell aus, **ohne Qt zu
starten**. Damit ist es aus Skripten, CI-Schritten und von Servern ohne Display nutzbar::

   py -m Imervue.cli resize photos/ --max 1600 --out web/
   py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
   py -m Imervue.cli info *.png --json
   py -m Imervue.cli list-ops          # alle verfügbaren Unterbefehle ausgeben

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Unterbefehl
     - Zweck
   * - ``info`` / ``stats``
     - Maße und Format; referenzfreie Qualitätsmetriken (``--json`` für maschinenlesbare Ausgabe)
   * - ``convert`` / ``resize`` / ``thumbnail``
     - Formatkonvertierung (``--format`` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL,
       ``--quality``); Skalierung auf eine lange Kante (``--max``) oder exakt auf ``--width`` /
       ``--height``; Thumbnail-Box
   * - ``watermark`` / ``optimize``
     - Text-Wasserzeichen (``--text``, ``--corner``, ``--opacity``, ``--font-fraction``,
       ``--color R G B``, ``--no-shadow``); Kodierung unter einem ``--max-kb``-Budget
   * - ``dehaze`` / ``clahe`` / ``dither`` / ``distort``
     - Dunkelkanal-Dunstentfernung, adaptive Entzerrung, geordnetes Bayer-Dithering, swirl / pinch / ripple
   * - ``auto-orient`` / ``strip``
     - EXIF-Ausrichtung in die Pixel einbrennen; ohne EXIF / XMP / ICC neu speichern
   * - ``collage`` / ``anaglyph``
     - Raster-Montage (``--columns``, ``--cell-width`` / ``--cell-height``, ``--gap``,
       ``--margin``, ``--background R G B``); Rot-Cyan-3D aus einem Stereopaar (``--method``)
   * - ``preset`` / ``pipeline``
     - Gespeichertes Entwicklungs-Preset per Name anwenden; geordnete JSON-Pipeline ausführen
   * - ``list-ops``
     - Alle Unterbefehle auflisten (``--json`` für maschinenlesbare Ausgabe)

Jeder Unterbefehl dekodiert wie der Viewer: Ausgaben werden anhand der EXIF-Ausrichtung aufgerichtet und aus einem eingebetteten Farbprofil nach sRGB konvertiert; AVIF-Eingaben liest Pillow selbst, HEIC- / JPEG-XL-Eingaben werden gelesen, wenn das optionale Backend installiert ist. Eine Kamera-RAW-Datei wird wie im Viewer entwickelt statt als kleine eingebettete Vorschau gelesen; ``resize`` und ``strip`` schreiben sie als PNG. Eine unlesbare Datei wird gemeldet, die übrigen werden trotzdem verarbeitet. Eine abgeschnittene Datei wird wie im Viewer so weit gelesen, wie sie reicht. 16-Bit- und Gleitkomma-Graustufen werden wie im Viewer auf 8 Bit skaliert; ``resize`` und ``strip`` behalten die Bittiefe der Quelle.

Die Unterbefehle, die Dateien oder Ordner entgegennehmen (alle außer ``collage``, ``anaglyph`` und ``list-ops``), teilen sich ``--out`` (Ausgabeverzeichnis), ``--recursive``, ``--dry-run`` (Aktionen nur auflisten, nichts schreiben), ``--overwrite`` und ``-j`` / ``--jobs`` (parallele Worker; ``0`` nutzt alle Kerne). ``collage`` und ``anaglyph`` schreiben die eine Datei, die ``--out`` angibt. ``--version`` gibt die CLI-Version aus.

Jedes Tool des MCP-Servers (siehe `MCP-Server`_) ist ebenfalls ein Unterbefehl. Zehn davon sind die
obigen Unterbefehle (``convert_format`` ist ``convert``, ``quality_metrics`` ist ``stats``,
``build_collage`` ist ``collage`` usw.); die übrigen 48 führen den Code des MCP-Tools selbst aus:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Art
     - Unterbefehle
   * - Bearbeitungen: schreiben ``<stem>_<name>.png`` neben jede Quelle oder ``<stem>.png`` in ``--out``
     - ``frame``, ``crop``, ``rotate``, ``solarize``, ``glow``, ``velvia``, ``emboss``, ``film-negative``, ``defringe``, ``graduated-density``, ``filmic-tonemap``, ``tone-equalizer``, ``detail-equalizer``, ``colormap``, ``false-color``, ``split-toning``, ``pixel-sort``, ``polar``, ``kaleidoscope``, ``frosted-glass``, ``local-contrast``, ``posterize``, ``gradient-map``, ``film-grain``, ``levels``, ``auto-color-balance``, ``channel-mixer``, ``curve``, ``lens-correction``
   * - Andere Ausgaben
     - ``ela`` (Error-Level-Analysis-Karte als PNG), ``video-frame`` (ein Einzelbild eines Videos,
       ``--frame-index``), ``puppet-from-png`` (ein ``.puppet``-Rig, ``--cell-size``)
   * - Berichte: ein Ergebnis pro Bild, ``--json`` für maschinenlesbare Ausgabe
     - ``metadata``, ``xmp``, ``gps``, ``dominant-colors``, ``sharpness``, ``statistics``, ``histogram``, ``ocr``, ``puppet-inspect``, ``puppet-validate``
   * - Einmal ausführen und JSON ausgeben
     - ``list-images FOLDER``, ``search FOLDER --query "..."``, ``similar FOLDER``,
       ``collection-stats FOLDER``, ``reverse-geocode --latitude .. --longitude ..``,
       ``puppet-schema --name ..``

Jeder MCP-Parameter wird zu einer Option mit demselben Standardwert und denselben erlaubten Werten:
``zone_gains`` wird zu ``--zone-gains``, ein Ja/Nein-Parameter zu ``--grayscale`` / ``--no-grayscale``,
und eine Farbe oder eine Matrixzeile nimmt ihre Werte der Reihe nach entgegen (``--red 1 0 0``).
``py -m Imervue.cli <subcommand> --help`` listet sie auf::

   py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
   py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
   py -m Imervue.cli histogram a.jpg --json
   py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"

``pipeline FILE INPUTS…`` führt auf jeder Eingabe eine geordnete Kette von Operationen aus und
schreibt pro Eingabe ein PNG: ``<stem>_pipeline.png`` neben die Quelle oder ``<stem>.png`` in
``--out``. ``FILE`` ist UTF-8-JSON (eine Byte-Order-Mark ist erlaubt) und enthält entweder eine
Liste von Schritten oder ein Objekt ``{"pipeline": [...]}``. Jeder Schritt ist ein Objekt mit
einem ``"op"``, das die Operation benennt, plus deren Parametern; ein weggelassener Parameter
nimmt seinen Standardwert an, und Schlüssel, die eine Operation nicht kennt, werden ignoriert.
Eine Pipeline hat höchstens 50 Schritte; eine leere schreibt jede Eingabe so, wie sie dekodiert
wurde. Die Datei wird geprüft, bevor ein Bild gelesen wird: Eine Datei, die sich nicht lesen oder
parsen lässt, gibt ``error: …`` aus, und mehr als 50 Schritte, ein Schritt ohne ``"op"``-Namen
oder eine unbekannte Operation geben pro Problem eine Zeile ``pipeline error: step N: …`` aus; in
beiden Fällen endet der Befehl mit Exit-Code 2 und schreibt nichts. Ein Parameter vom falschen
Typ (``null``, Text, wo eine Zahl hingehört) lässt dieses Bild scheitern, was gemeldet wird, und
der Exit-Code ist 1.

.. list-table::
   :header-rows: 1
   :widths: 14 44 42

   * - Op
     - Parameter (Standardwerte)
     - Wirkung
   * - ``dehaze``
     - ``strength`` (``1.0``; auf 0 – 1 begrenzt)
     - Dunstentfernung per Dark-Channel-Prior; ``0`` lässt das Bild unverändert
   * - ``clahe``
     - ``clip`` (``2.0``; mindestens 1), ``tiles`` (``8``; mindestens 1)
     - Kontrastbegrenzter adaptiver Ausgleich der Luminanz auf einem Raster aus ``tiles`` ×
       ``tiles``
   * - ``dither``
     - ``levels`` (``2``; auf 2 – 8 begrenzt)
     - Geordnetes 4×4-Bayer-Dithering auf ``levels`` Werte pro Kanal; Alpha bleibt erhalten
   * - ``distort``
     - ``mode`` (``"swirl"``: ``swirl`` / ``pinch`` / ``ripple``), ``strength`` (``0.5``;
       auf -1 – 1 begrenzt)
     - Geometrische Verzerrung um die Mitte; bei ``pinch`` wölbt eine positive Stärke aus und eine
       negative zieht zusammen
   * - ``clarity``
     - ``amount`` (``0.5``; -1 – 1, negativ macht weicher)
     - Mitteltongewichteter lokaler Kontrast mit großem Radius
   * - ``texture``
     - ``amount`` (``0.5``; -1 – 1, negativ macht weicher)
     - Lokaler Kontrast feiner Details mit kleinem Radius
   * - ``grayscale``
     - keine
     - Luma (0.299 R + 0.587 G + 0.114 B) in alle drei Kanäle; Alpha bleibt erhalten
   * - ``invert``
     - keine
     - Invertiert R, G und B; Alpha bleibt erhalten
   * - ``watermark``
     - ``text`` (``""``: kein Wasserzeichen), ``corner`` (``"bottom-right"``: ``top-left`` /
       ``top-right`` / ``bottom-left`` / ``bottom-right`` / ``center``; jeder andere Wert zählt als
       ``bottom-right``), ``opacity`` (``0.6``; auf 0 – 1 begrenzt)
     - Weißer Text mit Schlagschatten, 3,5 % der langen Kante groß; ``--font-fraction``,
       ``--color`` und ``--no-shadow`` des Unterbefehls ``watermark`` haben keinen
       Schrittparameter

Zum Beispiel ``look.json``::

   {
     "pipeline": [
       {"op": "dehaze", "strength": 0.4},
       {"op": "clahe", "clip": 2.5, "tiles": 8},
       {"op": "clarity", "amount": 0.3},
       {"op": "watermark", "text": "(c) Me", "corner": "bottom-right", "opacity": 0.5}
     ]
   }

   py -m Imervue.cli pipeline look.json photos/ --out graded/

----

MCP-Server
----------

Imervue liefert einen eingebauten `Model Context Protocol <https://modelcontextprotocol.io>`_-
Server, der es KI-Assistenten (Claude Code, Claude Desktop, Cursor, Cline, …)
erlaubt, die Pure-Logic-Helfer des Projekts ohne laufende GUI aufzurufen. Starten Sie ihn mit::

   python -m Imervue.mcp_server

Der Server ist Qt-frei und lädt nur das, was jedes Werkzeug zum Aufrufzeitpunkt benötigt.

Verfügbare Werkzeuge
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Werkzeug
     - Zweck
   * - ``list_images``
     - Bilddateien in einem Ordner auflisten (Pfad, Größe, mtime). Mit
       ``recursive=true`` werden Unterordner durchlaufen.
   * - ``read_image_metadata``
     - Abmessungen, Format, EXIF-Tags und XMP-Felder (Sidecar, sonst eingebettet) für ein Bild.
       Fehlende Daten werden als entsprechender leerer Wert gemeldet, statt
       eine Ausnahme auszulösen.
   * - ``read_xmp_tags``
     - Schneller Pfad, der nur das XMP liest (Sidecar, sonst eingebettet) — Bewertung, Farbetikett,
       Stichwörter, Titel, Beschreibung.
   * - ``convert_format``
     - Ein Bild in ein anderes Format konvertieren. Das Zielformat wird vom
       Zielsuffix abgeleitet (``png`` / ``jpg`` / ``jpeg`` / ``webp`` / ``tiff``
       / ``bmp`` / ``avif``, dazu ``heic`` / ``jxl``, wenn das optionale Backend
       installiert ist). Das optionale ``quality`` (1–100) gilt für JPEG / WebP / AVIF / HEIC / JXL.
   * - ``puppet_from_png``
     - Ein ``.puppet``-Rig aus einer PNG mit dem Auto-Mesh des Puppet-Plugins
       erstellen. Sät den Cubism-Standard-Parameterkatalog ein, sodass das Rig
       sofort steuerbar ist.
   * - ``puppet_inspect``
     - Ein ``.puppet``-Archiv öffnen und ein strukturiertes Inventar zurückgeben:
       Drawables, Deformer, Parameter, Motions, Ausdrücke, Hit-Areas, Parts,
       Parameter-Blends und Physik-Rigs.
   * - ``puppet_validate`` / ``puppet_schema``
     - Ein ``.puppet`` gegen das v1-Format prüfen (JSON Schemas, Loader-Regeln,
       Rig-Prüfungen); eines seiner vier veröffentlichten JSON Schemas zurückgeben.
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - Per-Kanal-Mittelwert/Min/Max/Std/Median, No-Reference-Qualitätsmetriken
       (Colourfulness, Entropie, Kontrast, Kantendichte, Rauschen) und das
       256-Bin-Histogramm mit Over-/Under-Clipping-Anteilen.
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Laplacian-Varianz-Blur-Score, Tesseract-OCR-Text (graceful, wenn nicht
       vorhanden) und eine begrenzte Base64-PNG-Vorschau.
   * - ``find_similar``
     - Near-Duplicate-Bilder per Perceptual-Hash (Hamming-Schwellwert) gruppieren.
       Meldet Per-Datei-Fortschritt, wenn ein Progress-Token übergeben wird.
   * - ``apply_watermark`` / ``apply_frame``
     - Ein Text-Wasserzeichen einbrennen oder das Bild in einen Passepartout- /
       Polaroid-Rahmen mit optionaler Caption fassen.
   * - ``build_collage``
     - Mehrere Bilder zu einer Grid-Montage komponieren (konfigurierbare Spalten,
       Zellengröße, Abstand, Rand, Hintergrund). Meldet Fortschritt.
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - Pixel-Box-Crop, Resize (bei einer Kante bleibt das Seitenverhältnis erhalten,
       bei beiden entsteht genau diese Größe) und verlustfreies
       90/180/270-Rotate oder Horizontal-/Vertikal-Flip.
       Größen und Koordinaten beziehen sich auf das nach EXIF aufgerichtete Bild.
   * - ``collection_stats``
     - Ratings, Favoriten, Farbetiketten und Cull-Zustände eines Ordners
       zusammenfassen (Counts, 0–5-Sterne-Verteilung und Durchschnitt).
   * - ``reverse_geocode`` / ``extract_video_frame``
     - GPS-Koordinaten offline zur nächsten Stadt auflösen und einen Frame eines
       Videos zu einem Standbild dekodieren.
   * - ``extract_gps`` / ``dominant_colors``
     - EXIF-GPS-Breite/-Länge lesen (lässt sich mit ``reverse_geocode`` verketten);
       eine Median-Cut-Farbpalette extrahieren (RGB / Hex / Pixelanzahl).
   * - ``error_level_analysis``
     - Error-Level-Analysis-Manipulationskarte per JPEG-Neukomprimierung als PNG-Data-URI
       (bearbeitete Bereiche leuchten vor dem Hintergrund auf).
   * - ``search_images``
     - Einen Ordner mit der Abfrage-DSL der Smart Albums filtern (Endung / Name /
       Größe / Abmessungen / Seitenverhältnis / EXIF-Kamera / Objektiv / Ort).
   * - ``solarize_image`` / ``glow_image``
     - Eine Solarisations-Tonumkehr oder ein diffuses Glühen / Orton-Bloom anwenden und
       das Ergebnis speichern.
   * - ``velvia_image`` / ``emboss_image`` / ``defringe_image``
     - Luminanzgewichtete Velvia-Sättigungsverstärkung, Prägerelief mit gerichtetem
       Licht und Entsättigung violetter/grüner Farbsäume an Kanten.
   * - ``film_negative_image`` / ``graduated_density_image``
     - Ein gescanntes Farbnegativ umkehren (automatische Filmbasis) und einen linearen
       Grauverlaufsfilter anwenden.
   * - ``filmic_tonemap_image`` / ``tone_equalizer_image`` / ``detail_equalizer_image``
     - Filmisches Reinhard/Hable-Highlight-Rolloff, Belichtung pro Luminanzzone
       und Kontrast pro Frequenzband.
   * - ``colormap_image`` / ``false_color_image``
     - Die Luminanz über eine perzeptuelle Viridis-/Magma-/Jet-Farbskala umfärben oder
       auf eine Falschfarben-Belichtungsskala abbilden.
   * - ``dither_image`` / ``split_toning_image`` / ``pixel_sort_image``
     - Geordnetes (Bayer-)Dithering auf wenige Tonstufen pro Kanal, Split-Toning für
       Schatten/Lichter und Pixel-Sortierung nach Helligkeitsbändern.
   * - ``polar_image`` / ``kaleidoscope_image``
     - Zwischen rechtwinkligen und Polarkoordinaten umrechnen (Tiny Planet) oder
       das Bild in eine Anzahl von Kaleidoskop-Segmenten spiegeln.
   * - ``frosted_glass_image`` / ``clahe_image`` / ``local_contrast_image``
     - Milchglas-Streuung über zufällige Nachbarpixel, kontrastbegrenzter adaptiver
       Histogrammausgleich und Mitteltonklarheit + Feindetail-Textur.
   * - ``posterize_image`` / ``gradient_map_image``
     - Jeden Kanal auf wenige flache Stufen quantisieren oder die Luminanz über einen
       nach Intensität gemischten Schwarz-Weiß-Verlauf neu abbilden.
   * - ``film_grain_image`` / ``dehaze_image`` / ``distort_image``
     - Einstellbares Gaußsches Filmkorn, Dunstentfernung per Dark-Channel-Prior und
       geometrische Verzerrung durch Strudel / Zusammenziehen / Wellen.
   * - ``levels_image`` / ``curve_image``
     - Tonwertkorrektur mit Schwarz-/Weißpunkt und Gamma sowie ein Preset für die
       Master-Gradationskurve (S-Kurve, Schatten anheben, Lichter komprimieren).
   * - ``auto_color_balance_image`` / ``channel_mixer_image``
     - Automatischer Weißabgleich (Gray World, White Patch, Perzentil-Streckung,
       Retinex) und ein 3x3-Kanalmixer mit Monochrom-Umwandlung.
   * - ``lens_correction_image``
     - Tonnen-/Kissenverzeichnung korrigieren (k1), die Eckvignettierung aufhellen
       oder vertiefen und rote/blaue chromatische Aberration aufheben.

Jedes Werkzeug bewirbt ein JSON-``outputSchema`` und Read-only- /
Destructive-``annotations`` und gibt sein Ergebnis als ``structuredContent``
neben dem Text-Umschlag zurück (Felder aus späteren MCP-Revisionen; der Handshake meldet
``2025-03-26``), sodass Clients typisierte
Payloads ohne erneutes Parsen konsumieren. Langlaufende Werkzeuge streamen
``notifications/progress``, wenn der Aufrufer ein Progress-Token übergibt.

Prompts
^^^^^^^

Der Server stellt vier Prompts über ``prompts/list`` / ``prompts/get`` bereit:
``caption_image``, ``suggest_edits``, ``analyze_composition`` (eine
saliency-getriebene Kompositionskritik) und ``flag_issues`` (eine Schärfe- +
Qualitäts- + Clipping-Triage). ``completion/complete`` schlägt Werte für das
Argument ``style`` von ``suggest_edits`` und ``focus`` von ``analyze_composition`` vor.

Claude Code (Projekt-Ebene)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Das Repository liefert eine projektbezogene ``.mcp.json`` im Repo-Wurzelverzeichnis:

.. code-block:: json

   {
     "mcpServers": {
       "imervue": {
         "type": "stdio",
         "command": "py",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

``py`` ist der Python-Launcher von Windows; unter macOS oder Linux verwenden Sie ``python3`` oder
den Interpreter der Umgebung, in der Imervue installiert ist. Das Öffnen eines beliebigen
Unterverzeichnisses des Repos in Claude Code entdeckt diesen Server automatisch. Claude Code fragt beim ersten Mal vor dem Aktivieren von
Projekt-Servern — die Aufforderung annehmen, um ihn zu verwenden.

Claude Desktop
^^^^^^^^^^^^^^

Fügen Sie denselben Eintrag zu Ihrer Claude-Desktop-Konfiguration hinzu:

* macOS: ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\Claude\claude_desktop_config.json``

Verwenden Sie ein absolutes Arbeitsverzeichnis oder aktivieren Sie eine virtuelle
Umgebung, in der Imervue installiert ist; der ``python``-Aufruf muss sich zu einem
Interpreter auflösen, der ``import Imervue`` kann.

Protokoll-Surface
^^^^^^^^^^^^^^^^^

Der Server liest zeilenweise getrennte JSON-RPC-2.0-Nachrichten von stdin und schreibt Antworten
und Benachrichtigungen nach stdout, jeweils eine UTF-8-Zeile. Er beantwortet ``initialize`` mit
der Protokollversion ``2025-03-26``, egal welche Version der Client anfragt. Anfragen werden
nacheinander bearbeitet; ein Batch (ein JSON-Array) wird mit ``-32600`` abgelehnt.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Methode
     - Funktion
   * - ``initialize``
     - Handshake. Gibt ``protocolVersion`` ``2025-03-26``, ``serverInfo`` (``imervue``
       ``1.0.0``) und die Capabilities ``tools`` und ``prompts`` (``listChanged: false``),
       ``resources`` (``subscribe: true``, ``listChanged: true``), ``completions`` und ``logging``
       zurück.
   * - ``ping``
     - Gibt ein leeres Ergebnis zurück.
   * - ``tools/list``
     - Alle 58 Werkzeuge auf einer Seite, jedes mit ``inputSchema``, ``outputSchema`` und
       ``annotations`` (``readOnlyHint`` / ``destructiveHint`` / ``idempotentHint`` /
       ``openWorldHint``).
   * - ``tools/call``
     - Führt ``{"name", "arguments"}`` aus. Das Ergebnis ist ein ``text``-Inhaltsblock mit dem
       JSON-kodierten Rückgabewert, plus ``structuredContent``, wenn dieser ein Objekt ist. Ein
       Werkzeug, das eine Ausnahme auslöst, oder Argumente, die nicht zu seinen Parametern passen,
       ergeben ``isError: true`` und einen Text ``Error: …`` statt eines Protokollfehlers; ein
       unbekannter Werkzeugname ergibt ``-32602``.
   * - ``prompts/list``
     - Die vier Prompts mit ihren Argumenten.
   * - ``prompts/get``
     - Baut die Nachrichten von ``{"name", "arguments"}``; ``caption_image`` und
       ``analyze_composition`` betten eine PNG-Miniaturansicht als Bildnachricht ein. Ein
       unbekannter Prompt oder ein fehlender ``path`` ergibt ``-32602``.
   * - ``completion/complete``
     - Per Präfix passende Werte für ein Argument von ``ref/prompt``: ``style`` von
       ``suggest_edits`` (general, portrait, landscape, product, street, food, macro) und
       ``focus`` von ``analyze_composition`` (all, framing, balance, subject, leading_lines). Jedes
       andere Argument erhält eine leere Liste.
   * - ``resources/list``
     - Die Bilder direkt in dem Ordner, den ``IMERVUE_MCP_ROOT`` angibt (ohne versteckte Dateien
       und SVG), 100 pro Seite mit einem ``nextCursor``; leer, wenn die Variable nicht gesetzt ist.
   * - ``resources/templates/list``
     - Die zwei URI-Vorlagen aus der Tabelle unten.
   * - ``resources/read``
     - Liest eine ``imervue://image/…``-URI (siehe unten).
   * - ``resources/subscribe`` / ``resources/unsubscribe``
     - Fügt eine URI der Menge hinzu, die ``notifications/resources/updated`` erhält, oder
       entfernt sie daraus.
   * - ``logging/setLevel``
     - Setzt die niedrigste Stufe (``debug``, ``info``, ``notice``, ``warning``, ``error``,
       ``critical``, ``alert``, ``emergency``; ``info`` beim Start), die als
       ``notifications/message`` gesendet wird; jeder andere Wert ergibt ``-32602``.
   * - ``notifications/*`` vom Client
     - Werden ohne Antwort angenommen (``notifications/initialized``,
       ``notifications/cancelled``, …); ein Abbruch stoppt ein laufendes Werkzeug nicht.
   * - ``notifications/progress`` (gesendet)
     - ``{progressToken, progress, total, message}``, während ``find_similar`` oder
       ``build_collage`` läuft, wenn die ``tools/call``-Anfrage ``params._meta.progressToken``
       (eine Zeichenkette oder eine Ganzzahl) mitgeschickt hat; ``progress`` steigt nur.
   * - ``notifications/resources/updated`` (gesendet)
     - ``{uri}``, wenn sich eine Datei in ``IMERVUE_MCP_ROOT`` ändert und ihre Miniaturansicht-URI
       abonniert ist.
   * - ``notifications/resources/list_changed`` (gesendet)
     - Bei jeder Änderung in ``IMERVUE_MCP_ROOT`` (mit watchdog überwacht, nicht rekursiv), ob
       abonniert oder nicht.
   * - ``notifications/message`` (gesendet)
     - Log-Einträge ab der Stufe von ``logging/setLevel``, gesendet über ``MCPServer.emit_log``.
       Die eingebauten Werkzeuge rufen es nicht auf, der Standard-Server sendet also keine.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - URI
     - Liefert
   * - ``imervue://image/{path}``
     - Eine PNG-Miniaturansicht des Bildes — aufgerichtet, in 256 px eingepasst — als
       Base64-``blob`` mit ``mimeType`` ``image/png``. ``resources/list`` gibt URIs dieser Form
       zurück.
   * - ``imervue://image/{path}/metadata``
     - Das Ergebnis von ``read_image_metadata`` (Abmessungen, Format, EXIF, XMP) als JSON-``text``
       mit ``mimeType`` ``application/json``.

``{path}`` ist der vollständig prozentkodierte Dateipfad des Bildes, einschließlich Trennzeichen und
Laufwerks-Doppelpunkt (``C:\photos\a.jpg`` wird zu ``imervue://image/C%3A%5Cphotos%5Ca.jpg``).
Ein Lesezugriff löst den Pfad direkt auf und funktioniert daher für jede Datei, nicht nur für
solche unter ``IMERVUE_MCP_ROOT``; ein Pfad mit einem ``..``-Segment ergibt ``-32602``, eine
fehlende Datei ``-32002`` und eine URI mit einem anderen Schema ``-32602``.

Fehler verwenden die JSON-RPC-Codes ``-32700`` (eine Zeile, die kein JSON ist), ``-32600`` (kein
Anfrageobjekt oder keine ``method``), ``-32601`` (unbekannte Methode), ``-32602`` (ungültige
Parameter, unbekanntes Werkzeug oder unbekannter Prompt, ungültige Log-Stufe oder ungültiger
Cursor, nicht unterstützte Ressourcen-URI), ``-32002`` (Ressourcendatei nicht gefunden) und
``-32603`` (interner Fehler).

Die Implementierung lebt in ``Imervue/mcp_server/``:

* ``server.py`` — der JSON-RPC-Dispatcher (``MCPServer``), die stdio-Schleife (``run``) und der
  Watcher für ``IMERVUE_MCP_ROOT``.
* ``tools.py`` — die öffentliche Seite des Werkzeugsatzes: exportiert jeden Handler erneut und
  registriert die Standard-Werkzeuge (``register_default_tools``).
* ``tools_read.py`` / ``tools_edit.py`` — die Werkzeug-Handler (Auflisten, Metadaten und Analyse;
  Bearbeitungen, die in ein Ziel geschrieben werden), mit gemeinsamen Helfern in
  ``tool_support.py``.
* ``tool_defs_read.py`` / ``tool_defs_edit.py`` — Name, Beschreibung, Eingabeschema und Handler
  jedes Werkzeugs, in der Reihenfolge von ``tools/list``.
* ``tool_schemas.py`` — ``outputSchema`` und ``annotations`` jedes Werkzeugs.
* ``prompts.py`` / ``completion.py`` — die vier Prompts und die Vorschläge für
  ``completion/complete``.
* ``resources.py`` — die Ressourcen unter ``imervue://image/``.
* ``progress.py`` / ``notifications.py`` / ``logging.py`` — Fortschrittsmeldung, der gesperrte
  stdout-Writer und die Ressourcen-Abonnements sowie die Filterung nach Log-Stufe.
* ``__main__.py`` — Einstiegspunkt ``python -m Imervue.mcp_server``.

Eigene Werkzeuge können registriert werden, indem :class:`MCPServer` konstruiert,
:meth:`MCPServer.register` aufgerufen (Name, Beschreibung, Eingabeschema, Handler, optionales
Ausgabeschema und Annotations; ein doppelter Name löst ``ValueError`` aus; ein Handler mit einem
Parameter ``progress`` erhält einen Fortschrittsmelder) und jede Nachricht an
:meth:`MCPServer.handle_message` übergeben wird, das die Antwort oder bei einer Benachrichtigung
``None`` zurückgibt. :func:`run` baut immer einen eigenen Server mit den Standard-Werkzeugen, ein
eigener Satz braucht also eine eigene Schleife; setzen Sie ``server.notifier`` auf einen
``Notifier`` für den Ausgabestrom, damit Benachrichtigungen gesendet werden.
