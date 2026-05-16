Imervue-Benutzerhandbuch
========================

Eine GPU-beschleunigte Bild-Workstation, die **vier Hauptregisterkarten** bereitstellt.
Der Großteil dieses Handbuchs ist um diese vier Abschnitte herum strukturiert.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Tab
     - Funktion
   * - **Imervue**
     - Bildbibliothek durchsuchen, anzeigen, organisieren, durchsuchen und in
       Stapeln verarbeiten. Siehe *Imervue-Tab — Bildbetrachter und Bibliothek*.
   * - **Modify**
     - Nicht-destruktive Entwicklungs-Pipeline — Schieberegler, Kurven, LUTs,
       Masken, Retusche, Multi-Bild. Siehe *Modify-Tab — Nicht-destruktive Entwicklung*.
   * - **Paint**
     - Voll ausgestattetes Raster-Mal-Studio mit Brushes, Layern, Animation,
       Manga-Werkzeugen, PSD-I/O. Siehe *Paint-Tab — Voll ausgestatteter Raster-Editor*.
   * - **Puppet**
     - Von Grund auf neu entwickelter 2D-Rigging-Puppet-Animator — Meshes,
       Deformer, Parameter, Motions, Physik. Siehe *Puppet-Tab — 2D-Rigging-Animation*.

Die nachfolgenden Abschnitte *Erste Schritte*, *Referenz*, *Plugin-System* und
*MCP-Server* sind übergreifend — sie gelten für alle vier Tabs.

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
- **Rechts**: EXIF-Seitenleiste. Zeigt die Aufnahmeinformationen für das ausgewählte Bild an.

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
     - ``Datei`` > ``Bild öffnen``, dann eine Datei wählen
   * - Drag & Drop
     - Bild oder Ordner direkt ins Fenster ziehen
   * - Aus Explorer öffnen
     - Bild rechtsklicken > ``Open with Imervue`` (Dateizuordnung erforderlich)
   * - Zuletzt geöffnete Dateien
     - ``Datei`` > ``Zuletzt verwendet``, kürzlich besuchten Ordner schnell wieder öffnen

Unterstützte Formate
^^^^^^^^^^^^^^^^^^^^

- **Standard**: PNG, JPEG, BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 (Canon), NEF (Nikon), ARW (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus)

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
   * - Mit Tastatur schwenken
     - Pfeiltasten; ``Shift`` halten für Feinbewegung

Jede Miniaturansicht zeigt Status-Badges: einen farbigen Streifen am linken Rand (Farbetikett),
ein Herz oben links (Favorit), einen Stern oben rechts (Lesezeichen) und Bewertungssterne
unten links. Für noch ladende Miniaturansichten wird ein Spinner-Platzhalter gezeichnet.

Listenmodus (Detailansicht)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Drücken Sie ``Ctrl + L``, um zwischen Miniaturansicht-Raster und einer sortierbaren Listenansicht
mit folgenden Spalten umzuschalten: Vorschau · Etikett · Name · Auflösung · Größe · Typ · Geändert.
Doppelklicken Sie eine Zeile (oder drücken Sie ``Enter``), um Deep Zoom zu öffnen; ``Esc`` führt
zurück zur Liste. Miniaturansichten und Metadaten werden in einem Worker-Thread verzögert geladen,
sodass auch sehr große Ordner reaktionsfähig bleiben.

Deep-Zoom-Modus
^^^^^^^^^^^^^^^

Klicken Sie auf eine Miniaturansicht, um in den Deep-Zoom-Modus für hochwertige Einzelbildbetrachtung zu wechseln.

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
     - ``Shift + P`` — bei ≥ 400 % Zoom wird ein Pixelraster eingeblendet und RGB / HEX unter dem Cursor angezeigt
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

Im Deep-Zoom-Modus können Sie Bilder schnell bewerten:

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

Unabhängige Farbkennzeichen, getrennt von der 1 -- 5-Sterne-Bewertung. Nützlich für schnelle
Kategorisierung (z. B. rot = Ausschusskandidaten, grün = Auswahl, blau = zu retuschieren).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Taste
   * - Rot / Gelb / Grün / Blau / Lila
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (gleiche Taste erneut zum Löschen)
   * - Stapelanwendung auf Auswahl
     - Mehrere Miniaturansichten auswählen, dann entsprechende F-Taste drücken
   * - Nach Farbe filtern
     - ``Filter`` > ``Nach Farbetikett`` > Farbe / Beliebiges Etikett / Kein Etikett wählen

Die Statusleiste zeigt einen farbigen Chip für das aktuelle Bild. Miniaturansichten zeigen
einen farbigen Streifen am linken Rand. Die **Listenansicht** hat eigene Spalten **Etikett**
und **Sternebewertung**, nach denen sortiert werden kann — Klick in eine Zelle der Sternespalte
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
     - Rechtsklick auf Bild > ``Zu Tag hinzufügen``
   * - Zu Album hinzufügen
     - Rechtsklick auf Bild > ``Zu Album hinzufügen``
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
   * - Nach Name sortieren
     - ``Sortieren`` > ``Nach Name``
   * - Nach Änderungsdatum sortieren
     - ``Sortieren`` > ``Nach Änderungsdatum``
   * - Nach Dateigröße sortieren
     - ``Sortieren`` > ``Nach Dateigröße``
   * - Nach Auflösung sortieren
     - ``Sortieren`` > ``Nach Auflösung``
   * - Aufsteigend / Absteigend
     - ``Sortieren`` > ``Aufsteigend`` / ``Absteigend``
   * - Nach Erweiterung filtern
     - ``Filter`` > ``JPEG`` / ``PNG`` / ``RAW`` usw.
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
Sie können auch ``E`` drücken oder im Deep-Zoom-Modus per Rechtsklick > ``Modify`` einsteigen.

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
   * - Schatten
     - Details in dunklen Tonbereichen anheben oder stauchen
   * - Mitteltöne
     - Mittlere Tonwerte anpassen, ohne Schwarz und Weiß zu beeinflussen
   * - Lichter
     - Ausgefressene Lichter retten oder helle Bereiche weiter pushen
   * - Dynamik (Vibrance)
     - Sättigungsbewusste Verstärkung — schützt Hauttöne und bereits gesättigte Farben

Diese Anpassungen sind **nicht-destruktiv**. Jeder Schieberegler schreibt in ein bildbezogenes
Edit-Recipe; mit ``Zurücksetzen`` jederzeit den Originalzustand wiederherstellen oder mit
``Ctrl + Z`` einzelne Änderungen schrittweise rückgängig machen. Recipes überleben Neustarts
und können über den im Metadaten-Abschnitt beschriebenen XMP-Sidecar-Workflow exportiert /
synchronisiert werden.

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
und PSD-Import/Export. Über die Tab-Leiste wechseln oder ``E`` aus dem Deep-Zoom-Modus
drücken, um das aktuelle Bild direkt in einen neuen Paint-Tab zu senden.

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
gelöschte Pixel beim Neumalen nicht mehr ausbluten.

::

   +------+----------------------+----------------+
   |Werk- |                      | Farbe · Brush  |
   |zeug- |   Leinwand (malen)   | Layer · Navig. |
   |leiste|                      | Material · …   |
   +------+----------------------+----------------+

Die rechten Docks (Farbe, Brush, Layer, Navigator, Materialbibliothek, Verlauf,
Swatch, Referenz, Histogramm, Animation) sind in einer einzigen Spalte gestapelt,
sodass die Leinwand die volle sichtbare Höhe behält. Beliebigen Dock-Titel ziehen,
um neu anzuordnen oder ein Panel zu lösen, dann das Ergebnis über
``Einstellungen`` > ``Workspace-Layouts…`` speichern.

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
     - Flutfüllen mit Toleranz / zusammenhängend / alle Layer abtasten
   * - Pipette
     - ``I``
     - Vordergrundfarbe von der Leinwand aufnehmen
   * - Verschieben
     - ``V``
     - Aktiven Layer oder Auswahl verschieben
   * - Rechteck / Lasso / Zauberstab / Schnellauswahl
     - ``M`` / ``L`` / ``W``
     - Auswahlwerkzeuge mit Modi Ersetzen / Hinzufügen / Subtrahieren / Schnitt
   * - Text
     - ``T``
     - Inline-Texteditor mit Schrift / Größe / Fett / Kursiv
   * - Gradient
     - ``U``
     - Linear- / Radial- / Winkel- / Diamantgradientfüllung
   * - Weichzeichnen / Verschmieren
     - ``R``
     - Lokale Pixelmanipulation
   * - Pen (Bezier)
     - ``P``
     - Vektorpfad mit Anker- / Griff-Bearbeitung
   * - Klonstempel
     - ``S``
     - Shift+Klick legt Quelle fest, Klick stempelt mit Feder
   * - Sprechblase
     - ``Ctrl + B``
     - Comic-/Manga-Ballon mit automatischem Schwanz
   * - Rechteck / Ellipse / Linie / Polygon
     - ``Shift + R/E/I/P``
     - Vektorgrundformen mit Strich + Füllung
   * - Zuschneiden
     - ``C``
     - Interaktives Zuschneiden mit Seitenverhältnis-Presets
   * - Transformieren
     - ``Ctrl + T``
     - Frei / Skalieren / Drehen / Schräg ziehen
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
   * - Stift
     - Scharfe kantenglättete Linie, der Alltags-Brush
   * - Marker / Textmarker
     - Breite, halbtransparente Striche, die sich aufbauen
   * - Bleistift
     - Dünne, leicht texturierte Graphitlinie
   * - Spray
     - Streupunkte gesteuert durch Dichte und Fluss
   * - Kalligrafie
     - Strichbreite variiert mit Strichrichtung
   * - Aquarell
     - Nasskanten-Auslaufen und sanftes Verblenden
   * - Kohle / Wachsmalstift
     - Raue, strukturierte Striche mit Druck-Neigung

Jeder Brush bietet Größe / Deckkraft / Härte / Dichte / Mischmodus im **Brush-Dock**
und in der oberen **Optionsleiste**. ``Einstellungen`` > ``Drucksensitivitätskurve…``
um Tablett-Druck auf Breite oder Deckkraft umzubilden, und
``Bearbeiten`` > ``Brush-Spitze erfassen…`` um eine Auswahl in eine eigene
Brush-Spitze zu verwandeln.

Layer
^^^^^

Der **Layer-Dock** bietet Miniaturansichten, Sichtbarkeitsschalter, Inline-Umbenennung,
Ziehen zum Neuanordnen sowie Mischmodus + Deckkraft des aktiven Layers. Das ``Layer``-Menü
ergänzt:

- **Neu / Vektor / Duplizieren / Nach unten zusammenführen** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Masken** — Maske hinzufügen / Aus Auswahl / Invertieren / Anwenden / Löschen
  (``Ctrl + Shift + M`` fügt hinzu; ``Ctrl + Alt + Shift + M`` fügt aus Auswahl hinzu)
- **Schnittmaske** — den Layer darüber an das aktuelle Alpha klippen
  (``Ctrl + Alt + G``)
- **Layereffekte** — Schlagschatten · Außerer Schein · Kontur; Effekte löschen
- **Referenz-Layer** — einen Layer als Pipettenquelle anheften
- **1-Bit-Layer** — den aktiven Layer in einen binären Strichzeichnungs-Layer umschalten
- **Layer nach Farbe trennen** — einen flachen Farb-Layer in einen Layer pro Farbe
  aufteilen für einfaches Neufüllen mit dem Eimer
- **Gradient Map** — Untermenü mit Presets (Sepia / Sonnenuntergang / Cyanotype …)

Auswahlen
^^^^^^^^^

Verwenden Sie die Rechteck- / Lasso- / Zauberstab- / Schnellauswahl-Werkzeuge, dann
**Auswahl umranden…** im **Bearbeiten**-Menü, um die Auswahl mit dem aktuellen Brush
zu umranden. ``Q`` schaltet **Schnellmaske-Modus** um — mit jedem Brush in Rot malen,
um die Auswahlkante zu verfeinern, dann erneut ``Q`` drücken, um zurück zur Auswahl zu konvertieren.

Animation
^^^^^^^^^

Der **Animation-Dock** verwandelt das Dokument in einen Framestreifen:

- ``Frame hinzufügen`` speichert den aktuellen Layer-Status als neues Keyframe.
- Klicken Sie eine Frame-Miniaturansicht an, um dorthin zu springen.
- ``Onion Skin`` (Ansicht-Menü) überlagert benachbarte Frames mit niedrigem Alpha.
- Den Streifen über **Datei > Seiten exportieren** exportieren (CBZ für Comic-Reader,
  PDF für Druck) oder **Animation exportieren** für MP4 / GIF.

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
   * - Sprechblasen-Werkzeug
     - Ballon ziehen, Schwanz auf den Sprecher richten

Filter
^^^^^^

``Filter`` öffnet einen Live-Vorschau-Dialog für jeden Effekt:

- **Tonwerte** — Schwarz / Gamma / Weiß-Schieberegler, pro Kanal
- **Kurven** — ziehbare Punkte (RGB / R / G / B) mit monotoner kubischer Interpolation
- **Tontrennung** — Farbe in N Stufen quantisieren
- **Schwellenwert** — bei Cut-Off in reines Schwarz / Weiß konvertieren
- **Auto Color Balance** — Farbstiche per Grey-World / White-Patch neutralisieren
- **Filmkorn** — Luminanzrauschen mit anpassbarer Größe und Menge
- **In Halbton konvertieren** — Zeitungs-Punktraster

Anzeigehilfen
^^^^^^^^^^^^^

- **Pixel-Raster** (``Ctrl + Shift + '``) — Ein-Pixel-Raster bei hohem Zoom überlagern
- **An Pixel / Kanten ausrichten** — Sub-Pixel-Platzierung auf ganzzahlige Koordinaten beschneiden
- **Onion Skin** — Animation-Nachbar-Overlay
- **Beschnittlinien** — Druck-Beschnitt- / Sicherheitszonen-Linien
- **Leinwand drehen** (``Ctrl + Shift + H``) — Ansichtsrotation ohne Rasterisierung

Datei-I/O
^^^^^^^^^

- **PSD öffnen…** (``Ctrl + O``) und **Als PSD speichern…** (``Ctrl + S``) — Photoshop-Layer-Round-Trip mit Masken, Mischmodi und Layereffekten
- **Bild exportieren…** — flachlegen und als PNG / JPEG / WebP / BMP / TIFF speichern
- **Seiten exportieren → CBZ** / **→ PDF** — Mehrframe-Dokumentexport für Comics
- **Brush-Presets importieren / exportieren**, **Palette importieren** — Ressourcen zwischen Installationen teilen
- **Autosave-Snapshots** — periodische Hintergrund-Snapshots mit Wiederherstellen-Neuestes über das Datei-Menü

Workspace-Layouts
^^^^^^^^^^^^^^^^^

``Einstellungen`` > ``Workspace-Layouts…`` speichert die Dock-Anordnung,
Werkzeugoptionen und aktiven Panels unter einem Namen und wechselt dann
mit einem Klick zwischen ihnen — zum Beispiel ein "Zeichnen"-Layout mit
prominenten Brush + Farb-Docks und ein "Compositing"-Layout mit erweiterten
Layer + Verlauf-Docks.

----

Puppet-Arbeitsbereich (Puppet-Tab)
----------------------------------

Die vierte Hauptregisterkarte — **Puppet** — ist ein von Grund auf neu entwickeltes
2D-Rigging-Puppet-Animationssystem. Es leistet, was Live2D leistet (Mesh-Deformations-Rigs,
Parameter, Motions, Physik, Ausdrücke, Pose-Gruppen, Lippensynchronisation, Webcam-Tracking),
aber **ohne proprietäres SDK**, **ohne `live2d-py`**, und mit einem vollständig offenen
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

End-to-End-Workflow
^^^^^^^^^^^^^^^^^^^

1. **PNG importieren** — Toolbar ``Import PNG…`` führt
   ``puppet.auto_mesh.puppet_from_png`` aus: alphabegrenztes triangulisiertes Raster,
   ein Drawable, sofort renderbar.
2. **Deformer hinzufügen** — ``Add Rotation Deformer`` (Anker + Winkel) oder
   ``Add Warp Deformer`` (Zeilen × Spalten Bezier-Gitter; Vertices außerhalb der
   Grenzen werden unverändert durchgereicht).
3. **Parameter hinzufügen** — ``Add Parameter`` fügt einen Schieberegler zum rechten
   **Parameters**-Dock mit automatisch benannter ID hinzu (``Param1``, ``Param2``, …).
4. **Keys setzen** — den Schieberegler auf ein Extrem ziehen, die Form des Deformers
   im Code oder per Mesh-Bearbeitung anpassen, **Set key** drücken. Bei neutralem und
   gegenüberliegendem Extrem wiederholen. Die Runtime interpoliert nun Deformerfelder
   zwischen benachbarten Keys, wenn der Schieberegler bewegt wird.
5. **Speichern** — ``Save As…`` schreibt das Rig + Texturen + Motions + Ausdrücke +
   Physik in ein einzelnes ``.puppet``-Zip, das Sie teilen oder später über
   ``Open Puppet…`` öffnen können.

Ein durchgearbeitetes Beispiel ausprobieren
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Das Repository liefert ein vollständig geriggtes Demo unter
``examples/puppet/march_7th.puppet`` — ein 307-Drawable-Cubism-Live2D-Rig,
das im Baum konvertiert wurde. Texturen und Per-Parameter-Vertex-Morphs sind
in das ``.puppet``-Zip eingebrannt, sodass das Demo mit der Standard-
``requirements.txt`` öffnet, ohne das Cubism SDK weiterverteilen zu müssen.

Das Rig trägt 203 Cubism-Standardparameter (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …), sodass jeder
Standard-Eingabetreiber (Webcam, Blinzeln, Lippensynchronisation, Cursor-Look-At)
es ohne rigspezifische Konfiguration steuert. Neun loopende Motions sind im
Bundle enthalten — vom Autor konvertierte Cubism-Idle-Loops plus Referenz-
Gesten-Loops in den Gruppen ``Idle`` und ``TapHead``.

Öffnen Sie den Puppet-Tab, klicken Sie **Open Puppet…**, zeigen Sie auf
``march_7th.puppet`` — die Figur erscheint zentriert. Ziehen Sie einen
beliebigen Parameter-Schieberegler, um ein Gelenk zu bewegen, oder klicken
Sie eine der Motions im Motions-Dock — Einzelklick bindet die Motion und
startet sofort die Wiedergabe.

**Das mitgelieferte Beispiel ausführen, Schritt für Schritt:**

1. Imervue starten. Aus dem Quellcode: ``python -m Imervue``. Aus dem
   gepackten Build: die ausführbare Datei / App-Bundle ``Imervue`` ausführen.
   Das ``examples/``-Verzeichnis ist sowohl in das Wheel als auch in die
   Nuitka-EXE gebündelt, sodass das Rig auf der Festplatte vorhanden ist,
   wo immer Sie installiert haben.
2. Klicken Sie oben im Fenster auf den **Puppet**-Tab.
3. Toolbar → **File > Examples > March 7Th** (oder die **Examples ▾**-Dropdown
   in der Toolbar). Das 307-Drawable-Rig wird zentriert geladen und der
   Parameter-Dock füllt sich mit den 203 Cubism-Standard-Schiebereglern.
4. Im unteren **Motions**-Dock einen beliebigen Motion-Eintrag einzeln klicken
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …).
   Die Wiedergabe beginnt sofort; erneut klicken zum Stoppen, oder eine
   andere Motion wählen, um zu ihr überzublenden.
5. Schalten Sie die Live-Eingabeschalter in der Toolbar um, um das Rig
   aus Ihren eigenen Eingaben zu steuern — **Drag-track head** für
   Cursor-Look-At, **Auto-blink** für zyklisches Augenschließen,
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

Das vollständige Schema (Drawables, Deformer, Parameter, Motions, Ausdrücke,
Pose, Physik) liegt unter ``Imervue/puppet/FORMAT.md`` im Repo. Nur JSON +
PNG — kein proprietäres Binärformat, vollständig diff-fähig via git.

Toolbar-Referenz
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Aktion
     - Zweck
   * - Open Puppet… / Examples ▾
     - Ein ``.puppet`` von der Festplatte laden, oder eines der unter
       ``examples/puppet/`` gebündelten Rigs direkt aus der Toolbar wählen
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
     - Rig aus der Toolbar heraus authoring
   * - Drag-track head
     - Cursor-Offset → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Cosinus-Close→Open-Zyklus auf ``ParamEyeLOpen`` / ``ParamEyeROpen``
       etwa alle 4,5 s (Force-Write-Pfad umgeht das No-Change-Skip der
       Leinwand, sodass konkurrierende Treiber das Blinzeln nicht abwürgen)
   * - Mic lip-sync
     - Mikrofon-RMS → ``ParamMouthOpenY`` (benötigt ``sounddevice``)
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
     - Parameteränderungen in eine neue ``Motion`` aufnehmen und dem Dokument
       hinzufügen — Take backen, kein manuelles Key-Authoring
   * - Capture frame… / Record… / Export all motions…
     - Eine einzelne PNG speichern, eine GIF- / WebM- / MP4-Aufnahme umschalten,
       oder jede Motion im Rig in eine eigene Datei batch-rendern (alle über
       denselben Charakter-Only-Off-Screen-Renderpfad, der für das Streaming
       verwendet wird)
   * - Output > Virtual camera / NDI output
     - Live-Streaming-Surfaces — siehe *Live-Streaming an OBS* oben
   * - Reset to rest
     - Den Motion-Player snap-stoppen, jeden Live-Treiber abschalten,
       Ausdrücke / Pose-Gruppen löschen, Parameter-Standards wiederherstellen
   * - Fit to Window
     - Das Puppet auf der Leinwand neu zentrieren + neu skalieren

Eigene Motions aufzeichnen
^^^^^^^^^^^^^^^^^^^^^^^^^^

Um eine eigene Aufnahme zu erfassen, statt Keyframes von Hand zu authoring:

1. **Record motion** in der Toolbar umschalten — ein Namensdialog erscheint.
2. Während der Aufnahme Schieberegler ziehen, **Webcam tracking** aktivieren,
   Physik laufen lassen, alles was Parameterwerte schreibt.
3. **Record motion** wieder abschalten — der Recorder bäckt den aufgenommenen
   30-Hz-Stream in eine ``Motion`` mit einem Linear-Segment-Track pro Parameter,
   der sich tatsächlich bewegt hat (Parameter, die flach blieben, werden verworfen).
   Die neue Motion erscheint sofort im unteren **Motions**-Dock, bereit zum
   Abspielen / Loopen / Speichern.

So gespeicherte eigene Motions wandern denselben JSON-``motions/<name>.json``-Payload
hin und zurück wie authorierte.

Live-Streaming an OBS
^^^^^^^^^^^^^^^^^^^^^

Zwei Ausgabewege, beide rendern das Puppet allein (kein Schachbrett-Hintergrund,
kein Editor-Chrome) in einen Off-Screen-Framebuffer, bevor sie es an die
Streaming-Surface übergeben. Die Ausgabe wird auf 1080 px Langseite gedeckelt,
damit Cubism-Native-Leinwände (March 7th ist 3503×7777) nicht von
DirectShow-Virtual-Camera-Treibern abgewiesen werden.

**A. Virtuelle Kamera** — erscheint als Webcam in der *Video-Capture-Geräte*-
Quellenliste von OBS. ``pip install pyvirtualcam`` plus plattformspezifischer
Treiber: OBS Studio 26+ liefert den *OBS Virtual Camera*-Treiber unter Windows /
macOS (in OBS einmal *Start Virtual Camera* klicken zum Registrieren); Linux
verwendet ``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
Toolbar **Output > Virtual camera** öffnet den Stream.

DirectShow / AVFoundation / v4l2loopback sind nur RGB — kein Alphakanal — also
füllt Imervue den Bereich außerhalb des Charakters mit **Magenta `#FF00FF`** als
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
Toolbar **Output > NDI output** sendet die Quelle (Standardname *Imervue Puppet*).

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

Das Plugin degradiert elegant, wenn eines davon fehlt — der entsprechende
Toolbar-Schalter springt zurück und zeigt einen "install <package>"-Hinweis.
``File > Install dependencies…`` installiert jedes optionale Python-Paket auf einen Schlag.

----

Desktop-Pet-Arbeitsbereich (Desktop-Pet-Tab)
--------------------------------------------

Tab 5 — der **Desktop Pet** führt jedes ``.puppet``-Rig als rahmenloses,
transparentes, immer-im-Vordergrund liegendes Overlay auf Ihrem Desktop aus.
Der In-App-Tab ist das Bedienpanel; die eigentliche Figur lebt in einem
separaten Top-Level-Fenster, das die Puppet-Runtime teilt (gleiche
:class:`PuppetCanvas`, gleiche Parameter- / Motion- / Physik-Pipeline,
gleiche Live-Eingabetreiber).

Fensterverhalten
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Funktion
     - Hinweise
   * - Rahmenloses Overlay
     - Keine Fenster-Chrome, kein Taskleisten-Eintrag; liegt über jedem
       anderen Fenster via ``Qt.WindowStaysOnTopHint``.
   * - Transparenter Hintergrund
     - ``WA_TranslucentBackground`` + ein alphafähiges GL-Surface-Format
       + ``glClearColor(0,0,0,0)`` — jeder Pixel, den das Puppet nicht
       zeichnet, lässt den Desktop durchscheinen.
   * - Ziehen zum Verschieben
     - Linksziehen auf der Figur zum Repositionieren. Wird innerhalb der
       konfigurierbaren Snap-Schwelle (Standard 24 px) zu einem
       Bildschirmrand losgelassen, **rastet** sie bündig daran ein.
       Schnelles Ziehen über die Grenze hinaus wird zurückgeklemmt,
       damit das Pet nie außerhalb des Bildschirms verloren geht.
   * - Click-Through-Umschaltung
     - Optionaler ``Qt.WindowTransparentForInput``-Modus — jeder Klick
       geht durch zum Desktop / zur App hinter dem Pet.
   * - Anker-Sperre
     - Ein-Klick-Sperre der Pet-Position, damit versehentliche Ziehbewegungen
       es nicht verschieben können.
   * - Immer im Hintergrund
     - Umschalten von ``WindowStaysOnTopHint`` auf
       ``WindowStaysOnBottomHint``, damit das Pet hinter jedem Fenster
       als Desktop-Widget sitzt (kombiniert mit
       ``WindowDoesNotAcceptFocus``).
   * - Vollbild-Ausblenden
     - Ein 1-Hz-Poller überwacht das aktive Fenster über die Win32-API
       ``GetWindowRect`` (Windows) und blendet das Pet automatisch aus,
       solange eine andere App Vollbild auf dem Pet-Monitor hält.
   * - Pausiert bei Ausblendung
     - Der 33-ms-Paint-Tick stoppt, solange das Overlay ausgeblendet ist,
       sodass ein ruhendes Pet null CPU verbraucht. Setzt bei ``showEvent``
       fort.
   * - Größen-Voreinstellungen
     - Klein (200×300) / Mittel (320×480) / Groß (480×720); mittig
       verankert, damit das Pet beim Vergrößern nicht über den Bildschirm
       springt.
   * - Deckkraft-Schieberegler
     - Fensterweite Deckkraft 0.1 – 1.0 via ``setWindowOpacity`` — das
       ``WA_TranslucentBackground``-Compositing plus Pro-Fenster-Alpha
       ergibt eine sanfte Ausblendung statt nur Abdunkelung der
       Puppet-Pixel.
   * - Positionspersistenz
     - Das nach dem Snap gemessene ``(x, y)`` nach jedem Ziehende wird in
       ``user_setting_dict["desktop_pet"]["position"]`` geschrieben. Beim
       nächsten Start kehrt das Pet zu dieser Bildschirmposition zurück;
       bei Multi-Monitor-Trennung wird auf die untere rechte Ecke des
       Primärbildschirms zurückgefallen.

Interaktion
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Aktion
     - Verhalten
   * - **Linksklick auf den Körper**
     - Bildet den Klick über die inverse Pan- / Zoom-Matrix in
       Puppet-Canvas-Koordinaten ab, führt den bestehenden
       :func:`hit_test` gegen die :class:`HitArea`-Einträge des
       Dokuments aus und spielt die verknüpfte Motion, falls eine das
       getroffene Drawable abdeckt. Fällt auf eine Round-Robin-Begrüßung
       in der Sprechblase zurück, wenn nichts passt.
   * - **Rechtsklick an beliebiger Stelle**
     - Öffnet ein Kontextmenü mit: Pet ausblenden, **Live drivers**-
       Untermenü (6 abhakbare Schalter), **Play motion**-Untermenü
       (befüllt aus ``document.motions``), **Apply expression**-Untermenü
       (befüllt aus ``document.expressions``), Position sperren,
       Click-Through, Immer im Hintergrund, Vollbild-Ausblenden,
       Sprechblasen-Umschaltung und ein **Size**-Untermenü.
   * - **Sprechblase**
     - Rahmenloses / transparentes / immer-im-Vordergrund-Widget mit
       abgerundetem Körper + Schwanz. Erscheint beim Klick über dem Pet,
       hält ~4 s und blendet über 400 ms aus. Verankert an der Geometrie
       des Pets, sodass das Ziehen des Pets die Blase mitnimmt.
   * - **System-Tray**
     - Anzeigen / Ausblenden (abhakbar), Click-Through, Open puppet…,
       Pet ausblenden. Linksklick schaltet die Sichtbarkeit um;
       Rechtsklick öffnet das Menü. Spiegelt den Check-State des
       Arbeitsbereichs via ``sync_visibility`` / ``sync_click_through``.

Live-Treiber (Lazy-Init)
^^^^^^^^^^^^^^^^^^^^^^^^

Jeder Treiber wird beim ersten Aktivieren instanziiert, damit ein ruhendes
Pet keinerlei Timer- / Thread-Kosten verursacht:

* **Auto idle** — Atmung + Drift auf Standardparametern
  (``ParamBreath`` …) via :class:`IdleDriver`.
* **Idle motions** — zufällige Rotation durch Motions der
  ``Idle``-Gruppe via :class:`IdleMotionCycler` + dem mitgelieferten
  :class:`MotionPlayer`.
* **Auto-blink** — Kosinus-Schließ-Öffnungs-Zyklus alle ~4,5 s auf
  ``ParamEyeLOpen`` / ``ParamEyeROpen`` via
  ``InputEngine.set_blink_enabled``.
* **Drag-track head** — Cursor-Versatz → ``ParamAngleX/Y`` +
  ``ParamEyeBallX/Y`` via ``InputEngine.set_drag_enabled``.
* **Mic lip-sync** — Mikrofon-RMS → ``ParamMouthOpenY`` via
  ``InputEngine.set_lipsync_enabled`` (benötigt ``sounddevice``).
* **Webcam tracking** — MediaPipe FaceLandmarker → Kopf + Augen +
  Mund via :class:`WebcamTracker` (benötigt ``opencv-python`` +
  ``mediapipe``).

Persistenz
^^^^^^^^^^

:mod:`Imervue.desktop_pet.settings` legt sich über
``user_setting_dict["desktop_pet"]`` mit:

* Defaults für jeden Schlüssel + Bereichs-Clamping beim Laden, sodass eine
  beschädigte Settings-Datei den Start nicht zum Absturz bringen kann.
* Ein-Ebenen-Merge — ältere Settings-Dateien, denen neue Schlüssel fehlen,
  ergeben trotzdem einen vollständigen State-Dict.
* Vorwärtskompatibilität für den ``drivers``-Sub-Dict — unbekannte
  Treiber-Schlüssel werden unverändert mit-gespeichert, sodass eine
  künftige Version, die einen neuen Treiber hinzufügt, bestehende
  Dateien sauber lesen kann.

Jede benutzerveränderbare Eigenschaft (Position, Größe, Deckkraft,
Click-Through, Anker, Im-Hintergrund, Vollbild-Ausblenden, Sprechblase,
Snap-Schwelle, jeder Treiber, zuletzt geladenes Rig, Beim-Start-Anzeigen)
läuft über diesen Helper, sodass das Pet beim nächsten Start in denselben
Zustand zurückkehrt.

Implementierung
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Datei
     - Rolle
   * - ``Imervue/desktop_pet/pet_window.py``
     - Top-Level-Overlay — rahmenlos / immer-im-Vordergrund /
       ``WA_TranslucentBackground``. Hostet
       ``PuppetCanvas(pet_mode=True)``, besitzt Ziehen-zum-Verschieben,
       Hit-Detect, Kontextmenü, Sprechblasen-Integration,
       Vollbild-Detektor-Verkabelung, Treiber und
       Persistenz-Write-Through.
   * - ``Imervue/desktop_pet/edge_snap.py``
     - Reine-Python-Snap-Mathematik (kein Qt) für unit-testbares
       Ecken- / Kantendocking + Overshoot-Clamp.
   * - ``Imervue/desktop_pet/settings.py``
     - Persistenz-Helper — Load / Save / Update / Clamp.
   * - ``Imervue/desktop_pet/speech_bubble.py``
     - Rahmenloses Rounded-Bubble-Overlay mit Anker-zu-Rect-Positionierung
       + Fade-Animation.
   * - ``Imervue/desktop_pet/fullscreen_detector.py``
     - 1-Hz-Poll-Schleife, die das Rect des Vordergrundfensters liest
       (Win32-ctypes auf Windows; No-Op-Fallback anderswo) und
       ``state_changed(bool)`` emittiert.
   * - ``Imervue/desktop_pet/pet_workspace.py``
     - Der Bedienpanel-Tab. Erstellt das Overlay lazy, exponiert jeden
       Toggle / Schieberegler / Combo als Checkbox oder Spinbox,
       persistiert das zuletzt geladene Rig + das
       Beim-Start-Anzeigen-Verhalten.
   * - ``Imervue/desktop_pet/tray_icon.py``
     - System-Tray-Helper — single-instance pro Sitzung, synchronisiert
       sich mit dem Check-State des Arbeitsbereichs.

``PuppetCanvas.__init__(pet_mode=True)`` umgeht den
Transparenz-Schachbrett-Hintergrund und das Auswahl-Overlay des Editors;
der Rest des Render-Pfads (Mesh-VBOs, Motion-Player, Physik, Ausdrücke,
Pose-Gruppen) ist identisch mit dem Puppet-Tab.

Jeder UI-String wird über
``language_wrapper.language_word_dict.get(...)`` mit Schlüsseln geleitet,
die in allen fünf Basis-Sprachpaketen definiert sind (English, 繁體中文,
简体中文, 日本語, 한국어).

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
     - Rechtsklick > Modify > CW drehen
   * - 90° gegen Uhrzeigersinn drehen
     - ``Shift + R``
     - Rechtsklick > Modify > CCW drehen
   * - Horizontal spiegeln
     - --
     - Rechtsklick > Modify > Horizontal spiegeln
   * - Vertikal spiegeln
     - --
     - Rechtsklick > Modify > Vertikal spiegeln
   * - Verlustfreie Rotation (JPEG)
     - --
     - Rechtsklick > Verlustfreie Rotation

----

Bilder exportieren
------------------

Einzelexport
^^^^^^^^^^^^

Rechtsklick auf ein Bild > ``Exportieren / Speichern unter``.

- Format wählen: PNG, JPEG, WebP, BMP, TIFF
- Qualität anpassen (für verlustbehaftete Formate)
- Geschätzte Dateigröße in der Vorschau
- Speicherort wählen

Export-Presets
^^^^^^^^^^^^^^

Für die üblichen Lieferziele, die Sie nicht jedes Mal neu einstellen wollen,
verwenden Sie ``Datei`` > ``Mit Preset exportieren``. Ein Klick wendet die
richtige Resize-, Format- und Qualitäts-Pipeline an:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Preset
     - Pipeline
   * - **Web 1600**
     - Lange Kante auf 1600 px anpassen, JPEG-Qualität 85, sRGB; für Blog- / Forum-Uploads, bei denen visuelle Qualität wichtiger ist als Pixelanzahl.
   * - **Print 300 dpi**
     - TIFF in voller Auflösung / hochwertiges JPEG mit 300-dpi-Metadaten, farbverwaltete Ausgabe für Labors und Druckereien.
   * - **Instagram 1080**
     - Quadratischer (1080 × 1080) oder Hochformat-Zuschnitt (1080 × 1350) mit innen erhaltenem Original-Seitenverhältnis, JPEG-Qualität 90.

Presets lassen sich mit dem Wasserzeichen-Overlay (unten) kombinieren — Wasserzeichen
einmal aktivieren und jede Preset-Ausgabe trägt es.

Wasserzeichen-Overlay
^^^^^^^^^^^^^^^^^^^^^

``Datei`` > ``Wasserzeichen…`` öffnet einen nicht-destruktiven Overlay-Konfigurator.
Einstellungen werden nur beim Export angewendet — die Originalpixel auf der Festplatte
werden nie berührt.

- **Modus**: Text oder Bild. Bildwasserzeichen unterstützen PNG mit Alpha.
- **Position**: 9-Anker-Raster (Ecken, Kanten, Mitte).
- **Deckkraft**: 0 – 100 %.
- **Skalierung**: Prozent der exportierten Langseite; das Wasserzeichen skaliert
  sich automatisch neu, wenn Sie für verschiedene Presets neu skalieren.

Stapelexport
^^^^^^^^^^^^

Mehrere Bilder auswählen, dann Rechtsklick > ``Stapelexport``.

- Einheitliche Formatkonvertierung
- Maximale Breite / Höhe setzen (automatische Seitenverhältnisskalierung)
- Qualitätskontrolle
- Echtzeit-Fortschrittsbalken

GIF / Video erstellen
^^^^^^^^^^^^^^^^^^^^^

Mehrere Bilder auswählen, dann Rechtsklick > ``GIF / Video erstellen``.

- GIF- und MP4-Ausgabe
- Per Drag Frames neu anordnen
- Bilder pro Sekunde (FPS) festlegen
- Eigene Abmessungen
- Loop-Option

----

Animations-Wiedergabe
---------------------

Beim Öffnen von GIF-, APNG- oder animierten WebP-Dateien wird die Animation automatisch abgespielt.

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

Wählen Sie im Miniaturansichten-Modus 2 -- 4 Bilder aus, dann Rechtsklick > ``Bilder vergleichen``.

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
     - ``Datei`` > ``Aus Zwischenablage einfügen``, oder ``Ctrl + V``
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
     - Mehrere auswählen, dann ``Delete`` oder Rechtsklick > ``Ausgewählte löschen``

Bilder werden in den System-Papierkorb verschoben und können von dort wiederhergestellt werden.

----

Stapeloperationen
-----------------

Im Miniaturansichten-Modus mehrere Bilder auswählen, dann Rechtsklick:

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
   * - Zu Tag hinzufügen
     - Dasselbe Tag auf alle ausgewählten Bilder anwenden
   * - Zu Album hinzufügen
     - Alle ausgewählten Bilder in ein Album legen

----

RGB-Histogramm
--------------

Drücken Sie ``H`` im Deep-Zoom-Modus, um ein RGB-Histogramm über das Bild zu legen. Erneut drücken zum Ausblenden.

----

Als Hintergrundbild festlegen
-----------------------------

Rechtsklick im Deep-Zoom-Modus > ``Als Hintergrundbild festlegen``, um das aktuelle Bild als Desktop-Hintergrundbild zu setzen.

Unterstützt unter Windows, macOS und Linux (GNOME).

----

Mehrfenster
-----------

``Datei`` > ``Neues Fenster`` öffnet ein weiteres unabhängiges Imervue-Fenster. Jedes Fenster kann einen anderen Ordner durchsuchen.

Workspace-Layout-Presets
------------------------

``Datei`` > ``Workspaces…`` erfasst die aktuelle Fenstergeometrie, Dock- / Toolbar-
Anordnung, Splittergrößen und den aktiven Wurzelordner unter einem Namen — und
lässt Sie dann zwischen gespeicherten Layouts wechseln, ähnlich wie andere
XMP-fähige Foto-Manager *Library* / *Develop* / *Export* oder Adobe Bridge
*Metadata* / *Filmstrip* wechseln. Der Dialog unterstützt Aktuelles speichern,
Laden, Umbenennen und Löschen. Workspaces bleiben in ``user_settings.json``
(unter dem Schlüssel ``workspaces``) erhalten und überstehen Sitzungen hinweg.

.. tip::
   Bauen Sie einen **Browse**-Workspace mit Baum und Miniaturansichten-Raster
   sichtbar, und einen separaten **Develop**-Workspace mit maximiertem
   Entwicklungs-Panel und eingeklapptem Baum. Ein Klick bringt Ihr ganzes
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
2. Administrationsrechte sind erforderlich.
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
     - Schwenken im Miniaturansicht-Modus
   * - ``Shift + Pfeil``
     - Fein-Schwenken
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
   * - ``Home``
     - Zoom zurücksetzen

Bearbeiten
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Taste
     - Aktion
   * - ``E``
     - Modify-Tab öffnen
   * - ``R``
     - Im Uhrzeigersinn drehen
   * - ``Shift + R``
     - Gegen Uhrzeigersinn drehen
   * - ``Ctrl + Z``
     - Rückgängig
   * - ``Ctrl + Shift + Z``
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
     - Pixel-Ansicht (≥ 400 % zeigt Pixelraster und RGB-Wert unter Cursor)
   * - ``Shift + M``
     - Farbmodi durchschalten (Normal / Graustufen / Invertieren / Sepia)
   * - ``S``
     - Diashow

Animation
^^^^^^^^^

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
gecrawlt wird. Sobald ein Root indiziert ist, können Sie ihn nach Erweiterung,
Mindestbreite/-höhe, Größenbereich oder Namens-Teilstring abfragen und die Ergebnisse
als virtuelles Album in den Betrachter laden.

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
nahe Treffer aus dem Index, sortiert nach Hamming-Distanz. Stellen Sie ``Max distance``
ein, um das Netz zu verbreitern oder zu straffen.

Semantische Suche (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Semantic Search`` ermöglicht das Eintippen einer natürlichsprachigen
Phrase (zum Beispiel *"golden retriever in snow"* oder *"neon street at night"*) und
gibt geordnete Bilder aus der indizierten Bibliothek zurück. Jedes Bild wird mit einem
CLIP-Vision-/Language-Encoder eingebettet und neben seinem Pfad gespeichert; eine
Textabfrage wird in denselben Vektorraum eingebettet und per Kosinus-Ähnlichkeit verglichen.

Embeddings werden in ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) bzw.
``~/.cache/imervue/clip_cache.npz`` (POSIX) als einzelne kompakte ``.npz``-Archiv gecacht,
sodass der nächste Start das erneute Encoding überspringt. Nur die Pfade, die Sie gescannt
haben, sind abfragbar — verwenden Sie ``Scan Folder…`` im Dialog, um den Index zu erweitern.

.. note::
   Semantische Suche erfordert die optionalen Pakete ``open_clip_torch`` und ``torch``.
   Wenn sie nicht installiert sind, erklärt der Menüeintrag, was fehlt, und andere
   Funktionen funktionieren weiter.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` wendet heuristische Tags
unter ``auto/...`` an (``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``). Wenn ``onnxruntime`` und ein CLIP-Modell unter
``models/clip_vit_b32.onnx`` verfügbar sind, werden auch CLIP-basierte Inhaltslabels
hinzugefügt. Läuft in einem Worker-Thread mit Live-Fortschrittsbalken.

Hierarchische Tags
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` verwaltet baumstrukturierte
Tags wie ``animal/cat/british``. Wählen Sie ein Tag, um jedes Bild unter diesem Zweig
(Nachfahren inbegriffen) zu sehen. Aktuelle Auswahl mit einem Klick taggen oder enttaggen.
Hierarchische Tags leben im Bibliotheksindex und ergänzen das flache Tag-System im
Rechtsklick-Menü.

Token-Stapel-Umbenennen
^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` öffnet eine Live-Vorschau-Tabelle,
in der Sie eine Vorlage wie ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` eingeben
und genau sehen, wozu jede Datei umbenannt wird. Konflikte werden hervorgehoben, damit
nichts überschrieben wird. Unterstützte Token: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``.

Metadaten-Export
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` schreibt eine
Zeile pro Bild in der aktuellen Ansicht mit EXIF, Abmessungen, Farbetikett, Bewertung,
Favorit, hierarchischen Tags, Cull-Status und Notizen. Nützlich, um Cull-Entscheidungen
in eine Tabelle oder einen externen Workflow einzuspeisen.

XMP-Sidecar (Interop mit anderen XMP-fähigen Foto-Managern)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue kann Adobe-XMP-Sidecar-Dateien (``photo.jpg`` ↔ ``photo.xmp``) lesen und
schreiben, sodass Bewertungen, Titel, Beschreibungen, Stichwörter und Farbetiketten
mit anderen XMP-fähigen Foto-Managern, Bridge und anderen XMP-fähigen Tools sauber
hin- und herwandern.

- **XMP für aktuelles Bild importieren** — zieht Bewertung / Titel / Stichwörter /
  Farbetikett aus dem Sidecar in die interne Datenbank.
- **XMP für aktuelles Bild exportieren** — schreibt die aktuelle Bewertung / Titel /
  Stichwörter / Farbetikett in einen Sidecar neben dem Bild.
- **Stapelimport / -export** — wendet dieselbe Operation auf die aktive Auswahl
  oder den gesamten Ordner an.

XML-Parsing verwendet ``defusedxml``, sodass fehlerhafte oder bösartige Sidecars
keine XXE- / Billion-Laughs-Angriffe auslösen können. Wenn ``defusedxml`` nicht
installiert ist, werden die XMP-Menüeinträge ausgeblendet und keine Sidecars geschrieben.

Die **EXIF-Seitenleiste** zeigt außerdem einen anklickbaren **Sterne-Bewertungsstreifen** —
die dort gesetzte Bewertung ist die, die der XMP-Export schreibt.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

Dreiwertiges Flag-basiertes Cull-Flag. Drücken Sie ``P``, um das aktuelle Bild oder
jede ausgewählte Kachel zu picken, ``Shift + X`` zum Verwerfen, ``U`` zum Entfernen
des Flags. ``Filter`` > ``By Cull State`` zeigt nur Picks, Rejects oder Ungeflaggte
an. ``Extra Tools`` > ``Culling`` wendet den Filter über einen Dialog an und stellt
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
Monat oder Jahr (datumsgruppiert). Das Datum wird aus EXIF ``DateTimeOriginal``
genommen, wenn vorhanden, andernfalls aus der Datei-Änderungszeit. Doppelklicken
Sie auf ein beliebiges Bild, um es in Deep Zoom zu öffnen.

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
beliebige Adobe-``.cube``-Datei (1D oder 3D, bis zu 64³) wählen. Die LUT wird mit
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
Rot und Blau. Das korrigierte Bild wird als neue Datei gespeichert — die
Objektivkorrektur ist nicht Teil des Recipes, weil sich die Ausgabeform ändern kann.

Kartenansicht
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` plottet jedes geotaggte Bild der aktuellen
Bibliothek auf einer interaktiven Leaflet + OpenStreetMap-Karte (benötigt
``PySide6.QtWebEngineWidgets``). Ohne WebEngine fällt der Dialog auf eine einfache
Liste von ``(path, lat, lon)``-Einträgen zurück, damit das Feature auf minimalen
Installationen verwendbar bleibt.

Kalenderansicht
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` zeigt ein ``QCalendarWidget``, in
dem Tage hervorgehoben werden, an denen Fotos aufgenommen wurden (EXIF
``DateTimeOriginal`` → ``DateTimeDigitized`` → Datei-mtime). Auswählen eines
Datums listet seine Bilder; Doppelklick öffnet eines im Hauptbetrachter.

Gesichtserkennung
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` führt OpenCVs Haar-
Frontalgesichts-Cascade auf dem aktuellen Bild aus und zeichnet jede Detektion als
Rechteck. Doppelklick auf eine Zeile in der Liste, um einen Personennamen einzugeben;
beim Speichern werden die Tags in den ``extra['face_tags']``-Blob des Recipes
geschrieben. Detection ist eine klassische Technik — die Genauigkeit reicht für
"Zeige mir die Gesichter", ersetzt aber keine moderne CNN-basierte Erkennung.

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
normalisiertes (0..1) Zuschnitt-Rechteck mit einem beliebigen Begradigungs-Winkel.
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

GPS-Geotag
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` liest beliebige vorhandene
EXIF-GPS-Tags und lässt Sie neue Dezimalgrad-Koordinaten bearbeiten oder setzen.
Erfordert die Installation von ``piexif``; schreibt direkt in JPEG.

Druck-Layout
^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` komponiert mehrere Bilder auf einem
mehrseitigen PDF mit konfigurierbarer Seitengröße, Ausrichtung, Raster, Rändern,
Rinne und Schnittmarken. Erfordert ``reportlab``.

----

Kommandozeilen-Verwendung
-------------------------

::

   imervue                        # Normal starten
   imervue /path/to/image         # Bestimmtes Bild öffnen
   imervue /path/to/folder        # Bestimmten Ordner öffnen
   imervue --debug                # Debug-Modus aktivieren
   imervue --software_opengl      # Software-Rendering verwenden (wenn GPU nicht unterstützt)

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
     - Abmessungen, Format, EXIF-Tags und XMP-Sidecar-Felder für ein Bild.
       Fehlende Daten werden als entsprechender leerer Wert gemeldet, statt
       eine Ausnahme auszulösen.
   * - ``read_xmp_tags``
     - Schneller Pfad, der nur den XMP-Sidecar liest — Bewertung, Farbetikett,
       Stichwörter, Titel, Beschreibung.
   * - ``convert_format``
     - Ein Bild in ein anderes Format konvertieren. Das Zielformat wird vom
       Zielsuffix abgeleitet (``png`` / ``jpg`` / ``jpeg`` / ``webp`` / ``tiff``
       / ``bmp``). Das optionale ``quality`` (1–100) gilt für JPEG/WebP.
   * - ``puppet_from_png``
     - Ein ``.puppet``-Rig aus einer PNG mit dem Auto-Mesh des Puppet-Plugins
       erstellen. Sät den Cubism-Standard-Parameterkatalog ein, sodass das Rig
       sofort steuerbar ist.
   * - ``puppet_inspect``
     - Ein ``.puppet``-Archiv öffnen und ein strukturiertes Inventar zurückgeben:
       Drawables, Deformer, Parameter, Motions, Ausdrücke, Hit-Areas, Parts,
       Parameter-Blends und Physik-Rigs.

Alle Werkzeuge geben JSON-serialisierte Payloads im MCP-``content`` /
``text``-Umschlag zurück; strukturierte Payloads können clientseitig aus dem
``text``-Feld zurückgeparst werden.

Claude Code (Projekt-Ebene)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Das Repository liefert eine projektbezogene ``.mcp.json`` im Repo-Wurzelverzeichnis:

.. code-block:: json

   {
     "mcpServers": {
       "imervue": {
         "type": "stdio",
         "command": "python",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

Das Öffnen eines beliebigen Unterverzeichnisses des Repos in Claude Code entdeckt
diesen Server automatisch. Claude Code fragt beim ersten Mal vor dem Aktivieren von
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

Der Server implementiert den stdio-JSON-RPC-2.0-Transport von MCP
Version ``2025-03-26``:

* ``initialize`` — Handshake; bewirbt ``capabilities.tools``.
* ``tools/list`` — die registrierten Werkzeuge mit ihren
  JSON-Schema-Eingabedefinitionen aufzählen.
* ``tools/call`` — ein Werkzeug mit ``{"name", "arguments"}`` aufrufen;
  Ergebnisse kommen im ``content``-Array zurück.
* ``notifications/*`` — werden stillschweigend akzeptiert (keine Antwort).

Die Implementierung lebt in ``Imervue/mcp_server/``:

* ``server.py`` — Protokollschleife + Werkzeugregister.
* ``tools.py`` — Handler-Funktionen und die Standard-Werkzeugdefinitionen.
* ``__main__.py`` — Einstiegspunkt ``python -m Imervue.mcp_server``.

Eigene Werkzeuge können registriert werden, indem :class:`MCPServer` manuell
konstruiert wird, :meth:`MCPServer.register` aufgerufen wird und Nachrichten
durch :meth:`MCPServer.handle_message` geschickt werden (oder die stdio-Schleife
mit dem eingebauten :func:`run`-Helper betrieben wird).
