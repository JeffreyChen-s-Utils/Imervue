Guide de l'utilisateur Imervue
==============================

Station de travail d'image accélérée par GPU offrant **cinq onglets principaux**.
La majeure partie de ce guide est organisée autour de ces cinq sections.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Onglet
     - Rôle
   * - **Imervue**
     - Parcourir, visualiser, organiser, rechercher et traiter par lots votre
       bibliothèque d'images. Voir *Onglet Imervue — Visionneuse et bibliothèque d'images*.
   * - **Modify**
     - Pipeline de développement non destructif — curseurs, courbes, LUT, masques,
       retouche, multi-images. Voir *Onglet Modify — Développement non destructif*.
   * - **Paint**
     - Studio de peinture matricielle complet avec pinceaux, calques, animation,
       outils manga, E/S PSD. Voir *Espace de travail Paint (onglet Paint)*.
   * - **Puppet**
     - Animateur de marionnettes 2D riggées conçu de zéro — maillages, déformateurs,
       paramètres, mouvements, physique. Voir *Onglet Puppet — Animation 2D riggée*.
   * - **Desktop Pet**
     - Superposition sans cadre, transparente et toujours au premier plan qui
       exécute les mêmes rigs ``.puppet`` sur votre bureau avec des pilotes en
       direct (idle / clignement / micro / webcam / suivi du curseur). Voir
       *Espace de travail Desktop Pet*.

Les sections *Pour démarrer*, *Référence*, *Système de plugins* et *Serveur MCP*
qui suivent sont transversales — elles s'appliquent à l'ensemble des cinq onglets.

.. contents:: Table des matières
   :depth: 2
   :local:

----

Pour démarrer
-------------

Au lancement d'Imervue, vous découvrez trois zones :

::

   +------------+----------------------+----------+
   |  Arbre des |                      |  Barre   |
   |  dossiers  |   Visionneuse        |  EXIF    |
   |            |                      |          |
   +------------+----------------------+----------+

- **Gauche** : arbre des dossiers. Cliquez sur un dossier pour parcourir les images qu'il contient.
- **Centre** : zone d'affichage des images. Présente toutes les images sous forme de grille de vignettes.
- **Droite** : barre latérale EXIF, repliée en une fine bande au démarrage : cliquez dessus pour l'ouvrir. Elle affiche les informations de prise de vue de l'image ouverte.

Imervue écrit le journal de chaque session dans ``imervue.log`` à côté du programme (dans ``%LOCALAPPDATA%\Imervue``, ou ``~/.cache/imervue`` hors de Windows, lorsque ce dossier est en lecture seule). Le journal de la session précédente est conservé sous le nom ``imervue.previous.log``, si bien qu'après un plantage le journal qui l'explique est toujours là une fois Imervue relancé — joignez les deux lorsque vous signalez un problème.

----

Ouvrir des images
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Méthode
     - Procédure
   * - Ouvrir un dossier
     - ``Fichier`` > ``Ouvrir un dossier``, puis choisissez un répertoire
   * - Ouvrir une image
     - ``Fichier`` > ``Ouvrir un fichier``, puis choisissez un fichier
   * - Glisser-déposer
     - Faites glisser une image ou un dossier directement dans la fenêtre
   * - Ouvrir depuis l'Explorateur
     - Clic droit sur une image > ``Open with Imervue`` (association de fichiers requise)
   * - Fichiers récents
     - ``Fichier`` > ``Récents`` > Dossiers récents / Images récentes, pour rouvrir un dossier ou une image

Formats pris en charge
^^^^^^^^^^^^^^^^^^^^^^

- **Standards** : PNG, JPEG (.jpg, .jpeg, .jpe, .jfif, .jif), BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW** : CR2 / CR3 / CRW (Canon), NEF / NRW (Nikon), ARW / SRF / SR2 (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus / OM System), RW2 (Panasonic), RWL (Leica), PEF (Pentax), SRW (Samsung), 3FR (Hasselblad), IIQ (Phase One), MEF (Mamiya), MOS (Leaf), ERF (Epson), MRW (Minolta), KDC / DCR (Kodak)
- **Modernes** : AVIF (intégré) ; HEIC / HEIF avec le paquet optionnel ``pillow-heif`` ; JPEG XL avec le paquet optionnel ``pillow-jxl-plugin``
- **Autres** : ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (l'image fusionnée) — en lecture ; les faire pivoter sur place et les autres réécritures sont refusés, une modification passe par Enregistrer sous / Exporter

----

Parcourir les images
--------------------

Mode grille de vignettes
^^^^^^^^^^^^^^^^^^^^^^^^

Une fois un dossier ouvert, toutes les images s'affichent sous forme de vignettes.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Méthode
   * - Faire défiler
     - Molette de la souris
   * - Panoramique
     - Maintenir le bouton central enfoncé et faire glisser
   * - Passer en vue pleine taille
     - Clic gauche sur une vignette
   * - Modifier la taille des vignettes
     - Menu ``Taille des vignettes`` > choisir 128 / 256 / 512 / 1024
   * - Densité des vignettes
     - ``Taille des vignettes`` > ``Densité des vignettes`` > Compacte / Standard / Aérée
   * - Aperçu au survol
     - Laissez le curseur 500 ms sur une vignette pour voir un aperçu agrandi
   * - Sélectionner plusieurs images
     - Clic gauche maintenu et glisser pour tracer un rectangle de sélection
   * - Passer d'une vignette à l'autre au clavier
     - Les touches fléchées déplacent un cadre de focus et le font défiler dans la vue ; ``Enter`` ouvre l'image

Chaque vignette affiche des badges de statut : une bande colorée sur le bord gauche (étiquette de couleur),
un cœur en haut à gauche (favori), une étoile en haut à droite (signet) et des étoiles de notation
en bas à gauche. Un indicateur rotatif fait office d'espace réservé pour les vignettes en cours de chargement.

Mode liste (détails)
^^^^^^^^^^^^^^^^^^^^

Appuyez sur ``Ctrl + L`` pour basculer entre la grille de vignettes et une vue liste triable avec les colonnes :
Aperçu · Étiquette · Note · Nom · Résolution · Taille · Type · Modifié. Double-cliquez sur une ligne (ou appuyez sur ``Enter``) pour entrer
en Deep Zoom ; appuyez sur ``Esc`` pour revenir à la liste. Les vignettes et les métadonnées sont chargées paresseusement sur un fil d'exécution
de travail, afin que les très grands dossiers restent réactifs.

``Delete`` retire les lignes sélectionnées et ``Ctrl + Z`` les rétablit, et les touches de note (``1`` – ``5``), de favori (``0``), de tri (``P`` / ``Shift + X`` / ``U``) et de couleur (``F1`` – ``F5``) les marquent, comme dans la grille ; toutes sauf ``F1`` – ``F5`` suivent les réglages des raccourcis.

Mode Deep Zoom
^^^^^^^^^^^^^^

Cliquez sur une vignette pour passer en mode Deep Zoom et obtenir un affichage de haute qualité d'une seule image.

Les panoramas bien au-delà de la limite de sécurité de 179 mégapixels de Pillow s'ouvrent aussi : la limite suit la mémoire de l'ordinateur (avec 16 Go, environ 1,4 gigapixel) et ces images géantes sont décodées une à une.

Un JPEG, PNG, TIFF, GIF ou BMP tronqué — un téléchargement ou une copie interrompus, une photo récupérée sur une carte mémoire défaillante — s'ouvre avec la partie lue, comme dans un navigateur, au lieu de ne pas s'ouvrir du tout.

Quand un autre programme enregistre par-dessus une image — un éditeur externe, sur place ou en renommant une copie par-dessus —, la visionneuse affiche la nouvelle version : l'image ouverte en zoom profond moins d'une seconde après la dernière écriture, les vignettes de la grille et les lignes de la Liste en quelques secondes.

Un PNG ou TIFF en gris 16 bits — un scan, une carte de profondeur, une image scientifique ou astronomique — et un TIFF à virgule flottante montrent leur vraie luminosité dans la visionneuse, les vignettes, les aperçus et les outils, au lieu de presque blanc ou noir : les valeurs 16 bits sont mises à l'échelle sur toute leur plage, les valeurs flottantes de 0 à 1 vont du noir au blanc et toute autre plage est étirée.

Les images avec un profil colorimétrique intégré — Display P3 des téléphones, Adobe RGB des appareils, CMJN et les profils de gris que Photoshop intègre aux images en niveaux de gris, comme Dot Gain 20 % ou Gray Gamma 1.8 — sont converties en sRGB pour la visionneuse et les vignettes ; une image en niveaux de gris le reste. Les images sans profil ou en sRGB sont affichées telles quelles.

Les fichiers que Windows marque cachés — cachés aussi dans l'Explorateur et l'arborescence — et les noms commençant par un point, comme le ``._photo.jpg`` que macOS écrit à côté de chaque photo sur les cartes mémoire et lecteurs réseau, sont exclus de la grille de vignettes, des icônes de dossier, des listes des outils par lots, des dossiers surveillés, des analyses de la bibliothèque, de la CLI et des outils de dossier du serveur MCP ; les analyses récursives sautent les dossiers cachés comme ``$RECYCLE.BIN`` et le ``.Trashes`` d'un Mac. Une image cachée ouverte volontairement s'ouvre quand même.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Méthode
   * - Zoomer / dézoomer
     - Molette de la souris ou pincement sur le pavé tactile
   * - Panoramique
     - Maintenir le bouton central de la souris
   * - Image précédente
     - ``Flèche gauche`` (ou glisser vers la droite sur le pavé tactile)
   * - Image suivante
     - ``Flèche droite`` (ou glisser vers la gauche sur le pavé tactile)
   * - Saut entre dossiers
     - ``Ctrl + Shift + Gauche`` / ``Droite`` pour aller au dossier frère précédent / suivant contenant des images
   * - Historique précédent / suivant
     - ``Alt + Gauche`` / ``Alt + Droite`` (style navigateur)
   * - Aller à l'image par numéro
     - ``Ctrl + G``
   * - Image aléatoire
     - ``X``
   * - Ajuster à la largeur
     - ``W``
   * - Ajuster à la hauteur
     - ``Shift + W``
   * - Réinitialiser le zoom
     - ``Home``
   * - Revenir aux vignettes
     - ``Esc``
   * - Plein écran
     - ``F`` (appuyer à nouveau pour quitter)
   * - Mode cinéma
     - ``Shift + Tab`` masque menu / statut / arbre / onglets pour une visualisation sans distraction
   * - Superposition d'informations OSD
     - ``F8`` affiche nom de fichier / taille / type ; ``Ctrl + F8`` affiche un HUD de débogage (VRAM / cache / threads)
   * - Vue pixel
     - ``Shift + P`` — à partir de 400 % de zoom, affiche les valeurs RGB / HEX sous le curseur, plus une grille de pixels dès que 40 000 pixels de l'image au plus sont à l'écran
   * - Modes de couleur
     - ``Shift + M`` fait défiler Normal / Niveaux de gris / Inversé / Sépia (GLSL, non destructif)

Vue divisée et lecture double page
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Affichez deux images côte à côte directement dans la fenêtre principale sans ouvrir la boîte de dialogue Comparer :

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Action
     - Raccourci
   * - Vue divisée (deux images)
     - ``Shift + S``
   * - Double page (actuelle + suivante)
     - ``Shift + D``
   * - Double page, de droite à gauche (manga)
     - ``Ctrl + Shift + D``
   * - Revenir au mode précédent
     - ``Esc``

En mode double page, les flèches font avancer de deux images à la fois. La variante RTL échange les deux panneaux
afin que la page 1 apparaisse à droite.

Fenêtre multi-écrans
^^^^^^^^^^^^^^^^^^^^

Appuyez sur ``Ctrl + Shift + M`` pour ouvrir une seconde fenêtre sans cadre sur votre affichage secondaire, qui reflète
l'image actuellement présentée dans la visionneuse principale. La fenêtre principale continue de naviguer indépendamment — utile
pour les expositions, les flux de travail d'édition à deux écrans ou les présentations clients. Appuyez à nouveau sur ``Ctrl + Shift + M``
pour la fermer, ou utilisez ``Esc`` dans la seconde fenêtre.

----

Organiser les images
--------------------

Notation et favoris
^^^^^^^^^^^^^^^^^^^

Les touches notent l'image affichée en Deep Zoom. Dans la grille, elles notent les vignettes sélectionnées, sinon celle choisie aux flèches, sinon celle sous la souris : les photos que prendrait une étiquette de couleur ou un marquage de tri. Si toutes ont déjà cette note, la touche l'efface.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Touche
   * - Basculer favori
     - ``0``
   * - Noter de 1 à 5 étoiles
     - ``1`` ``2`` ``3`` ``4`` ``5`` (appuyer à nouveau pour effacer)

Étiquettes de couleur (F1 -- F5)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Marqueurs de couleur, stockés séparément de la notation 1 -- 5 étoiles. Utiles pour
une catégorisation rapide (par ex. rouge = à rejeter, vert = à conserver, bleu = à retoucher).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Touche
   * - Rouge / Jaune / Vert / Bleu / Violet
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (appuyer à nouveau pour effacer ; sur une
       sélection, n'efface que si toutes les images sélectionnées ont déjà cette couleur)
   * - Appliquer par lot à la sélection
     - Sélectionnez plusieurs vignettes, puis appuyez sur la touche F correspondante
   * - Filtrer par couleur
     - ``Filtre`` > ``Par étiquette de couleur`` > choisir une couleur / N'importe quelle étiquette / Aucune étiquette

La barre d'état affiche une pastille colorée pour l'image courante. Les vignettes affichent une bande colorée sur
le bord gauche. La **vue Liste** dispose de colonnes dédiées **Étiquette** et **Note** que vous pouvez
trier — cliquez sur n'importe quelle cellule de la colonne étoile pour définir la note sans quitter la liste.

Signets
^^^^^^^

Enregistrez les images fréquemment utilisées comme signets pour un accès rapide ultérieur.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Méthode
   * - Ajouter / supprimer un signet
     - Appuyez sur ``B`` en mode Deep Zoom
   * - Gérer les signets
     - ``Fichier`` > ``Signets``

Tags et albums
^^^^^^^^^^^^^^

Classez vos images par tags et albums.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Méthode
   * - Ouvrir le gestionnaire
     - Appuyez sur ``T`` ou ``Fichier`` > ``Tags et albums``
   * - Marquer une image
     - En Deep Zoom, clic droit > ``Tags`` ; pour les vignettes sélectionnées, clic droit >
       ``Opérations par lots`` > ``Ajouter au tag``
   * - Ajouter à un album
     - En Deep Zoom, clic droit > ``Albums`` ; pour les vignettes sélectionnées, clic droit >
       ``Opérations par lots`` > ``Ajouter à l'album``
   * - Filtrer par un seul tag / album
     - ``Filtre`` > ``Par tag`` / ``Par album``
   * - Filtre multi-tags (ET / OU)
     - ``Filtre`` > ``Filtre multi-tags…`` — cochez plusieurs tags ou albums, choisissez N'importe (OU) ou Tous (ET)

Tri et filtrage
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Fonctionnalité
     - Emplacement dans le menu
   * - Trier par nom (ordre naturel : ``img2`` avant ``img10``)
     - ``Trier`` > ``Par nom``
   * - Trier par date de modification
     - ``Trier`` > ``Par date de modification``
   * - Trier par date de prise de vue (heure EXIF de l'appareil ; à défaut, la date de modification)
     - ``Trier`` > ``Par date de prise de vue``
   * - Trier par taille de fichier
     - ``Trier`` > ``Par taille de fichier``
   * - Trier par résolution
     - ``Trier`` > ``Par résolution``
   * - Croissant / Décroissant
     - ``Trier`` > ``Croissant`` / ``Décroissant``
   * - Filtrer par extension
     - ``Filtre`` > ``Par extension`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
   * - Filtrer par note
     - ``Filtre`` > ``Par note``
   * - Filtrer par étiquette de couleur
     - ``Filtre`` > ``Par étiquette de couleur`` (Toutes / Toute étiquette / Aucune étiquette / Rouge / Jaune / Vert / Bleu / Violet)
   * - Filtre avancé
     - ``Filtre`` > ``Filtre avancé…`` — plage de résolution, plage de taille de fichier, orientation (paysage / portrait / carré), plage de dates de modification
   * - Effacer les filtres
     - ``Filtre`` > ``Effacer le filtre``

Mode de navigation (Grille / Liste)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Basculez le navigateur d'images entre la grille de vignettes et une liste détaillée triable :

- ``Ctrl + L`` — basculer Grille ↔ Liste
- Menu : ``Taille des vignettes`` > ``Mode de navigation`` > Grille / Liste
- En mode Liste, toute colonne (y compris Étiquette) est triable ; double-cliquez sur une ligne ou appuyez sur ``Enter`` pour ouvrir Deep Zoom.

----

Édition d'images (onglet Modify)
--------------------------------

Passez à l'onglet **Modify** en haut de la fenêtre pour entrer en mode édition.
En mode Deep Zoom, un clic droit > ``Modify`` > ``Develop`` ouvre aussi l'image courante dans cet onglet ;
``E`` (ou clic droit > ``Modify`` > ``Annotate``) l'ouvre plutôt dans l'éditeur d'annotation séparé.

::

   +--------+----------------------+------------+
   | Barre  |                      | Propriétés |
   | outils |   Canevas (dessiner) | Pinceaux   |
   |        |                      | Développer |
   +--------+----------------------+------------+

Outils d'annotation (panneau de gauche)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Outil
     - Icône
     - Description
   * - Sélection
     - |select|
     - Sélectionner les annotations existantes ; glisser pour déplacer
   * - Rectangle
     - |rect|
     - Tracer des rectangles
   * - Ellipse
     - |ellipse|
     - Tracer des ellipses ou des cercles
   * - Ligne
     - |line|
     - Tracer des lignes droites
   * - Flèche
     - |arrow|
     - Tracer des flèches
   * - Main levée
     - |freehand|
     - Dessin à main levée
   * - Texte
     - T
     - Ajouter du texte à l'image
   * - Mosaïque
     - |mosaic|
     - Pixeliser une région sélectionnée
   * - Flou
     - |blur|
     - Flou gaussien sur une région sélectionnée

.. |select| unicode:: U+2B1A
.. |rect| unicode:: U+25A2
.. |ellipse| unicode:: U+25EF
.. |line| unicode:: U+2571
.. |arrow| unicode:: U+2192
.. |freehand| unicode:: U+270E
.. |mosaic| unicode:: U+25A6
.. |blur| unicode:: U+25CC

.. tip::
   Appuyez sur ``Flèche gauche`` / ``Flèche droite`` dans l'onglet Modify pour passer d'une image à l'autre sans quitter l'éditeur.

Types de pinceaux (panneau de droite)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pinceau
     - Effet
   * - Stylo
     - Trait fin standard, le pinceau le plus courant
   * - Marqueur
     - Traits plus épais, semi-transparents
   * - Crayon
     - Trait fin, légèrement atténué
   * - Surligneur
     - Large et très transparent, comme un véritable surligneur
   * - Aérographe
     - Effet de points dispersés
   * - Calligraphie
     - La largeur du trait varie selon la direction
   * - Aquarelle
     - Effet doux de mélange à bords humides
   * - Fusain
     - Trait rugueux et texturé
   * - Pastel gras
     - Texture cireuse, type pastel

Propriétés de dessin (panneau de droite)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Propriété
     - Description
   * - Couleur
     - Cliquez sur l'échantillon de couleur pour choisir une couleur de dessin
   * - Épaisseur du trait
     - Faites glisser le curseur pour ajuster l'épaisseur du trait (1 -- 40)
   * - Opacité
     - Ajustez la transparence (0 % -- 100 %)
   * - Police
     - Choisissez la police pour l'outil Texte
   * - Taille de police
     - Ajustez la taille du texte (6 -- 200 px)

Ajustements d'image (panneau de droite, partie basse)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Curseur
     - Fonction
   * - Exposition
     - Ajustez la luminosité globale
   * - Luminosité
     - Affinez les zones claires et sombres
   * - Contraste
     - Ajustez l'écart entre les zones claires et sombres
   * - Saturation
     - Ajustez la vivacité des couleurs
   * - Balance des blancs — Température
     - Décalage chaud / froid (bleu → jaune) ; utile pour les éclairages mixtes ou les prises de vue en intérieur
   * - Balance des blancs — Teinte
     - Décalage magenta / vert ; corrige les dominantes fluorescentes
   * - Hautes lumières
     - Récupérez les hautes lumières brûlées ou poussez davantage les zones claires
   * - Ombres
     - Relevez ou écrasez les détails dans les zones tonales sombres
   * - Blancs
     - Poussez à droite pour étirer les tons les plus clairs jusqu'au blanc ; à gauche pour ramener le blanc à un gris
   * - Noirs
     - Poussez à gauche pour écraser les tons les plus sombres jusqu'au noir ; à droite pour relever le noir vers un gris délavé
   * - Vibrance
     - Renforcement intelligent de la saturation — protège les tons chair et les couleurs déjà saturées

Ces ajustements sont **non destructifs**. Chaque curseur écrit dans une recette d'édition stockée
par image ; appuyez sur ``Réinitialiser`` à tout moment pour restaurer l'original, ou sur ``Annuler`` / ``Rétablir``
sous les curseurs pour parcourir les modifications une à une. Les recettes survivent aux redémarrages et peuvent être exportées / synchronisées
via le flux de fichiers annexes XMP décrit dans la section Métadonnées.

Le fichier sur disque ne change que si vous le demandez. **Apply Crop** et le **Save** des annotations réécrivent le résultat dans le fichier en conservant ses EXIF (appareil, date de prise de vue, GPS), son XMP et sa résolution (DPI). Un RAW d'appareil, un HEIC ou un fichier animé / multipage n'est jamais écrasé : le recadrage vous propose d'exporter, et l'enregistrement des annotations demande un nouveau fichier. Les outils à usage unique (CLAHE, mélangeur TSL, cadre photo, redressement
automatique…) enregistrent leur résultat à côté de l'original sous
``photo_clahe.png`` ; une nouvelle exécution enregistre ``photo_clahe_1.png`` au
lieu de remplacer le dernier résultat. **Auto-Rotate by EXIF**, les copies de **Batch EXIF Strip** et **Split Pages…** numérotent leurs fichiers de la même façon. La recette et les copies virtuelles d'une photo la suivent quand Imervue la fait
pivoter sans perte (le recadrage pivote avec elle) ou réécrit son EXIF (géomarquage
GPS, éditeur EXIF) ; une recette avec des masques locaux, des calques, un reflet
d'objectif ou des étiquettes de visages reste avec la version non pivotée jusqu'à ce
qu'on la repivote.

Enregistrer et annuler
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Bouton
     - Description
   * - Enregistrer
     - Écrit les annotations et ajustements dans le fichier original
   * - Annuler
     - Annule la dernière opération
   * - Rétablir
     - Rétablit une opération annulée
   * - Réinitialiser
     - Efface tous les ajustements d'image

----

Espace de travail Paint (onglet Paint)
--------------------------------------

Le troisième onglet principal — **Paint** — est un espace de travail de peinture complet
avec documents à onglets multiples, calques vectoriels et matriciels, outils manga, images
clés d'animation, et import/export PSD. Y basculer depuis la barre d'onglets charge sur le
canevas l'image affichée par la visionneuse.

Points forts en matière d'ergonomie — l'espace de travail Paint dispose d'un curseur
de taille de pinceau complet qui s'adapte au zoom, d'icônes de curseur distinctes par outil,
d'un motif en damier de transparence sous le canevas, d'une superposition de mise en évidence
pour le glisser-déposer, d'un astérisque "modifié" par onglet, de confirmations toast pour
annuler / rétablir, d'un segment d'état d'enregistrement automatique dans la barre d'état, et
d'une invite de récupération d'enregistrement automatique au démarrage qui fait remonter les
instantanés d'une session précédente ayant planté.

Raccourcis pour utilisateurs avancés : ``Tab`` bascule tous les docks pour une peinture
sans distraction, ``Ctrl+Tab`` fait défiler les onglets, ``,`` / ``.`` font défiler les types
de pinceau, ``0–9`` règlent l'opacité du pinceau par paliers de 10 %, ``Alt+[`` / ``Alt+]``
font défiler le calque actif, et un clic droit sur le canevas ouvre un menu rapide
Annuler / Rétablir / Tout sélectionner / Désélectionner / Ajuster / 100 %.

Le dock des couleurs expose désormais un emplacement "transparent / sans couleur" (par défaut
arrière-plan = transparent), et le pot de peinture + la baguette magique respectent tous deux
les limites alpha, de sorte que les pixels effacés cessent de baver lors d'une nouvelle application.

::

   +------+----------------------+----------------+
   | Barre|                      | Couleur · Brush|
   | d'   |   Canevas (peinture) | Calque · Nav.  |
   |outils|                      | Matériaux · …  |
   +------+----------------------+----------------+

Les quatorze docks de droite sont regroupés en onglets dans une colonne unique afin que le
canevas conserve toute la hauteur visible, et répartis en trois groupes :

- **Dessin** — Couleur, Pinceau, Pot de peinture, Échantillons
- **Canevas** — Calques, Navigateur, Historique, Pages, Animation, Histogramme
- **Bibliothèque** — Matériaux, Tampons, Pose, Référence

Chaque dock peut être affiché ou masqué individuellement depuis le menu ``Fenêtre``. Faites
glisser n'importe quel titre de dock pour réorganiser ou détacher un panneau ;
``Paramètres`` > ``Dispositions d'espace de travail…`` mémorise les docks affichés (voir
*Dispositions d'espace de travail*).

Palette d'outils (bande de gauche)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Outil
     - Raccourci
     - Rôle
   * - Pinceau
     - ``B``
     - Peindre avec le type de pinceau actif
   * - Gomme
     - ``E``
     - Effacement alpha du calque actif
   * - Pot de peinture
     - ``G``
     - Remplissage avec tolérance / contigu / échantillonner tous les calques
   * - Pipette
     - ``I``
     - Sélectionner la couleur de premier plan depuis le canevas
   * - Déplacer
     - ``V``
     - Translater le calque actif ou la sélection
   * - Rectangle / Lasso / Baguette / Sélection rapide
     - ``M`` / ``L`` / ``W``
     - Outils de sélection avec modes Remplacer / Ajouter / Soustraire / Intersection
   * - Texte
     - ``T``
     - Un clic ouvre la boîte de dialogue **Ajouter du texte** (police / taille / couleur /
       gras / italique) ; le texte est dessiné dans les pixels du calque
   * - Dégradé
     - ``U``
     - Remplissage par dégradé Linéaire / Radial / Angulaire / Diamant
   * - Flou / Doigt
     - ``R`` (Doigt)
     - Manipulation locale des pixels
   * - Dodge / Burn / Sponge
     -
     - Virage de chambre noire pondéré par le pinceau — Dodge éclaircit et Burn
       assombrit les tons moyens, Sponge désature ; aucune option
   * - Plume (Bézier)
     - ``P``
     - Tracé vectoriel avec édition des ancres et poignées
   * - Tampon de duplication
     - ``S``
     - Alt+clic définit la source, puis faites glisser pour tamponner avec la taille /
       dureté / opacité du pinceau
   * - Bulle de dialogue
     - ``Ctrl + B``
     - Faites glisser un cadre pour dessiner une bulle BD / manga (dessinée sans queue)
   * - Rectangle / Ellipse / Ligne / Polygone
     - ``Shift + R/E/I/P``
     - Primitives de forme vectorielle avec contour + remplissage
   * - Recadrage
     - ``C``
     - Recadrage libre — faites glisser un rectangle ; le canevas est recadré au relâchement
   * - Transformation
     - ``Ctrl + T``
     - Huit poignées de mise à l'échelle et une poignée de rotation
   * - Main
     - ``H``
     - Panoramique du canevas par glissement du curseur
   * - Loupe
     - ``Z``
     - Clic pour zoomer, Alt+clic pour dézoomer

Pinceaux
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pinceau
     - Effet
   * - Crayon
     - Trait fin de graphite, légèrement texturé
   * - Stylo
     - Trait net avec anti-crénelage, pinceau du quotidien
   * - Marqueur
     - Traits larges et semi-transparents qui se superposent
   * - Aérographe
     - Points dispersés qui s'accumulent en une pulvérisation douce
   * - Aquarelle
     - Bord humide avec un intérieur plus clair, comme un pigment qui s'amasse sur le pourtour
   * - Sumi
     - Encre de style calligraphique avec des bords de pinceau sec

Pastel gras, Surligneur et Calligraphie sumi sont des préréglages de pinceau construits sur
ces types. Chaque pinceau expose Taille / Opacité / Dureté / Densité / Mode de fusion dans
le **dock Pinceau** ; la **barre d'options** supérieure porte Taille / Opacité / Dureté.
La pression du stylet de tablette module la taille et l'opacité du pinceau selon la courbe
définie dans ``Paramètres`` > ``Courbe de pression…`` (faites glisser un point, cliquez pour
en ajouter un, faites un clic droit pour en retirer un, ou partez de Linéaire / Douce /
Dure) ; une souris dessine à pleine pression.
Utilisez ``Édition`` > ``Capturer une pointe de pinceau…`` pour transformer une sélection en
rectangle en pointe de pinceau personnalisée.

Calques
^^^^^^^

Le **dock Calque** offre des vignettes, des bascules de visibilité, un renommage en ligne,
la réorganisation avec les boutons ↑ / ↓ (ou ``Ctrl + [`` / ``Ctrl + ]``), ainsi que le mode
de fusion + l'opacité du calque actif. Le menu ``Calque`` ajoute :

- **Nouveau / Vectoriel / Dupliquer / Fusionner avec le calque inférieur** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Masques** — Ajouter un masque / Depuis la sélection / Inverser / Appliquer / Supprimer
  (``Ctrl + Shift + M`` ajoute ; ``Ctrl + Alt + Shift + M`` ajoute depuis la sélection)
- **Masque d'écrêtage** — activer / désactiver l'écrêtage du calque actif, qui est alors
  écrêté sur l'alpha du calque inférieur (``Ctrl + Alt + G``)
- **Effets de calque** — Ombre portée · Lueur externe · Contour ; effacer les effets
- **Calque de référence** — épingler un calque comme source avec laquelle le **Pot de
  peinture** compare les couleurs
- **Calque 1-bit** — basculer le calque actif en calque d'art au trait binaire
- **Diviser le calque par couleur** — séparer un calque de couleurs plates en un calque
  par couleur pour des re-remplissages au pot faciles
- **Mappage de dégradé** — sous-menu de préréglages (sépia / coucher de soleil / cyanotype …)

Sélections
^^^^^^^^^^

Utilisez les outils rectangle / lasso / baguette / sélection rapide, puis l'entrée du menu **Édition**
**Contour de la sélection…** pour tracer le contour de la sélection dans la couleur de
premier plan, avec la Largeur et la Position choisies dans la boîte de dialogue.
``Q`` bascule le **mode masque rapide** — peignez avec n'importe quel pinceau pour affiner
le bord de la sélection en rouge, puis appuyez à nouveau sur ``Q`` pour reconvertir en
sélection rectangulaire.

Animation
^^^^^^^^^

Le **dock Animation** transforme le document en bande d'images :

- ``+ Image`` capture le dessin aplati dans une nouvelle image.
- Cliquez sur la vignette d'une image pour la charger dans le calque actif.
- ``Pelure d'oignon`` (menu Affichage) superpose l'image précédente à faible alpha.
- ``▶ Lecture`` fait défiler les images à la cadence (FPS) choisie. Les images servent à
  la prévisualisation et à la pelure d'oignon — il n'y a pas d'export d'animation
  (**Fichier > Exporter les pages** exporte les pages d'un projet BD, pas les images).

Menu Manga
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Action
     - Description
   * - Découpeur de cases
     - ``Ctrl + Shift + P`` — divise le canevas en une grille de cases BD avec lignes / colonnes / gouttière / bordure / marge configurables
   * - Basculer en calque de trame
     - Convertir le calque actif en calque de trame (points de demi-teinte)
   * - Tamponner les numéros de page
     - Ajouter des numéros de page à travers des documents multi-pages
   * - Lignes de vitesse
     - Générateurs de lignes de vitesse Radiales / Parallèles / Explosion
   * - Action flash
     - Superposition de type explosion / impact dans le style manga

Filtres
^^^^^^^

Chaque entrée du menu ``Filtre`` ouvre une simple boîte de dialogue de paramètres OK / Annuler
(sans aperçu en direct) :

- **Niveaux** — curseurs point noir / point blanc / gamma
- **Courbes** — un préréglage (courbe en S, Déboucher les ombres, Compresser les hautes lumières) avec un curseur Intensité
- **Postérisation** — quantifier la couleur en N paliers
- **Seuil** — convertir en noir / blanc pur selon un seuil
- **Balance des couleurs automatique** — neutraliser les dominantes via grey-world / white-patch
- **Grain de film** — bruit de luminance avec taille et quantité réglables
- **Convertir en demi-teintes** — trame de points de style journal

Aides à la visualisation
^^^^^^^^^^^^^^^^^^^^^^^^

- **Grille de pixels** (``Ctrl + Shift + '``) — superpose une grille d'un pixel à fort zoom
- **Aligner sur les pixels / bords** — Aligner sur les pixels pose les touches du pinceau sur des pixels entiers ; Aligner sur les bords attire les points vers les bords proches du canevas ou d'un calque
- **Pelure d'oignon** — superpose l'image d'animation précédente
- **Guides de fond perdu** — guides de fond perdu / zone sûre pour l'impression
- **Rotation du canevas** (``Ctrl + Shift + H``) — rotation de la vue sans rasterisation

E/S de fichiers
^^^^^^^^^^^^^^^

- **Ouvrir PSD…** (``Ctrl + O``) aplatit le fichier en un seul calque dans un nouvel onglet ; **Enregistrer sous PSD…** (``Ctrl + S``) écrit les calques avec leurs modes de fusion (sans masques ni effets de calque)
- **Exporter l'image…** — aplatir et enregistrer en PNG, JPEG, WebP, TIFF ou BMP, selon le type de fichier choisi (JPEG et BMP, qui ne gèrent pas la transparence, sur fond blanc). Seul **Enregistrer sous PSD…** marque l'onglet comme enregistré ; après un export, la fermeture d'Imervue demande toujours quoi faire des modifications non enregistrées de l'onglet
- **Exporter les pages → CBZ** / **→ PDF** — exporter les pages d'un projet BD
- **Importer un préréglage de pinceau…**, **Importer une palette…** — importer des pinceaux et des palettes depuis d'autres installations ou applications
- **Enregistrement automatique** — toutes les 2 minutes, tant que l'onglet actif a des modifications non enregistrées, un instantané est écrit ; au lancement suivant, un toast propose les instantanés et **Fichier > Restaurer l'enregistrement automatique** charge le plus récent dans l'onglet actif. La barre d'état indique quand le dernier instantané a été pris, et à la fermeture, Imervue demande quoi faire des onglets Paint ayant des modifications non enregistrées.

Dispositions d'espace de travail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Paramètres`` > ``Dispositions d'espace de travail…`` liste les dispositions intégrées
**Par défaut**, **Dessin**, **BD** et **Compacte**, ainsi que les vôtres. **Enregistrer
l'actuelle…** enregistre sous un nom lesquels des docks Calques / Couleur / Pinceau /
Navigateur / Historique / Référence sont affichés ; appliquer une disposition affiche ou
masque ces docks et place le premier dock affiché au premier plan. Les options d'outil et
la taille des docks ne sont pas enregistrées.

----

Espace de travail Puppet (onglet Puppet)
----------------------------------------

Le quatrième onglet principal — **Puppet** — est un système d'animation de marionnettes
2D riggées conçu de zéro : rigs par déformation de maillage, paramètres, mouvements,
physique, expressions, groupes de poses, lip-sync et suivi par webcam,
**sans SDK propriétaire**, **sans `live2d-py`**, et avec un format de fichier
``.puppet`` entièrement ouvert.

.. note::

   Le tutoriel complet de bout en bout — depuis une installation neuve jusqu'à un flux
   OBS en direct ou un MP4 cuit — se trouve dans ``puppet_guide.md`` à la racine du dépôt
   (avec les miroirs ``puppet_guide.zh-TW.md`` et ``puppet_guide.zh-CN.md``). Cette section
   est la référence ; le guide est le pas-à-pas.

::

   +-----------+----------------------+----------------+
   |  Barre    |                      |  Paramètres    |
   |  outils   |   Canevas GL         |    dock        |
   |           |                      |                |
   +-----------+----------------------+                |
   |               Dock Mouvements                     |
   +---------------------------------------------------+

Flux de travail de bout en bout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Importer un PNG** — ``Fichier`` > ``Importer PNG…`` exécute
   ``puppet.auto_mesh.puppet_from_png`` : grille triangulée bornée par l'alpha,
   un drawable, prêt à rendre.
2. **Ajouter un déformateur** — ``Édition`` > ``Ajouter un déformateur de rotation`` (ancre + angle) ou
   ``Ajouter un déformateur de déformation`` (treillis bilinéaire lignes × colonnes ; les sommets
   hors limites traversent sans changement).
3. **Ajouter un paramètre** — ``Édition`` > ``Ajouter un paramètre`` ajoute un curseur au dock
   **Paramètres** à droite, avec un identifiant nommé automatiquement (``Param1``, ``Param2``, …).
4. **Définir des clés** — faites glisser le curseur vers un extrême, modifiez la forme du déformateur
   par code, appuyez sur **Définir une clé**. Répétez au neutre et à l'extrême
   opposé. L'exécution interpolera désormais les champs du déformateur entre les clés adjacentes
   chaque fois que le curseur bouge. **Définir une clé** ne stocke que les formes des déformateurs :
   **Éditer le maillage** déplace définitivement les sommets de repos du drawable, donc une
   édition du maillage n'entre pas dans une clé.
5. **Enregistrer** — ``Enregistrer sous…`` écrit le rig + textures + mouvements + expressions
   + physique dans un seul zip ``.puppet`` que vous pouvez partager ou ouvrir plus tard via
   ``Ouvrir Puppet…``.

Essayer un exemple complet
^^^^^^^^^^^^^^^^^^^^^^^^^^

Le dépôt fournit une démo entièrement riggée à
``examples/puppet/march_7th.puppet`` — un rig Cubism Live2D de 307 drawables
converti dans l'arbre. Les textures et les morphs de sommets par paramètre sont
cuits dans le zip ``.puppet``, de sorte que la démo s'ouvre avec le
``requirements.txt`` par défaut sans redistribuer le Cubism SDK.

Le rig comporte 203 paramètres standard Cubism (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …), de sorte que
chaque pilote d'entrée standard (webcam, clignement, lip-sync, regard vers le curseur)
le pilote sans configuration par rig. Dix-huit mouvements sont livrés dans le pack :
huit mouvements d'inactivité en boucle dans le groupe ``Idle``, neuf gestes en boucle
dans le groupe ``Gesture`` et un ``tap_head`` joué une seule fois dans le groupe ``TapHead``.

Ouvrez l'onglet Puppet, cliquez sur **Ouvrir Puppet…**, pointez vers
``march_7th.puppet`` — la figure apparaît centrée. Faites glisser n'importe quel curseur
de paramètre pour piloter une articulation, ou cliquez sur l'un des mouvements dans le dock
Mouvements — un simple clic associe le mouvement et démarre immédiatement la lecture.

**Exécuter l'exemple fourni, étape par étape :**

1. Lancez Imervue. Depuis les sources : ``python -m Imervue``. Depuis la
   build empaquetée : exécutez l'exécutable / bundle d'application ``Imervue``. Le
   répertoire ``examples/`` est intégré aux builds Nuitka et PyInstaller ; une
   installation pip / wheel ne l'inclut pas (depuis une copie des sources, les rigs
   se trouvent dans ``examples/puppet/``).
2. Cliquez sur l'onglet **Puppet** en haut de la fenêtre.
3. **File > Examples > March 7th** (ou la liste déroulante
   **Examples ▾** de la barre d'outils). Le rig de 307 drawables se charge centré et
   le dock des paramètres se remplit des 203 curseurs standard Cubism.
4. Dans le dock **Mouvements** en bas, simple-clic sur n'importe quelle entrée de mouvement
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …).
   La lecture démarre immédiatement ; un nouveau clic la relance, le bouton **Stop**
   du dock arrête la lecture, et choisir un autre mouvement fait un fondu enchaîné vers lui.
5. Basculez les interrupteurs d'entrée en direct sur la barre d'outils pour piloter le rig
   depuis vos propres entrées — **Drag-track head** pour tourner la tête et les yeux
   vers le curseur quand il se déplace sur le canevas,
   **Auto-blink** pour le clignement cyclique des yeux, **Auto idle** + **Idle
   motions** pour la respiration + les clips Idle aléatoires, **Mic lip-sync** pour
   l'ouverture de la bouche depuis le RMS du microphone, **Webcam tracking** pour la
   tête + yeux + bouche complets depuis MediaPipe FaceLandmarker.
6. **Reset to rest** sur la barre d'outils arrête tous les mouvements, désactive
   tous les pilotes en direct, efface les expressions / surcharges de pose, et ramène
   chaque paramètre à sa valeur par défaut — l'action canonique de "recommencer".
7. Pour ouvrir un autre rig plus tard : **File > Open Puppet…** choisit n'importe quel
   zip ``.puppet`` sur disque ; **File > Examples ▾** reste lié à la liste fournie.

Format de fichier ``.puppet`` (v1)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Un fichier ``.puppet`` est une archive zip :

::

   my_character.puppet
   ├── puppet.json              # required — manifest, drawables, deformers, parameters
   ├── textures/
   │   ├── face.png             # referenced by drawables[].texture
   │   └── body.png
   ├── motions/                 # optional
   │   ├── idle.json
   │   └── wave.json
   ├── expressions/             # optional
   │   └── smile.json
   └── physics.json             # optional

Exemple de ``puppet.json`` de premier niveau ::

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

Le schéma complet (drawables, déformateurs, paramètres, mouvements, expressions,
pose, physique) se trouve dans ``Imervue/puppet/FORMAT.md`` du dépôt. JSON +
PNG uniquement — aucun binaire propriétaire, entièrement diffable via git.

Référence de la barre d'outils
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

La barre d'outils porte **Examples ▾**, les six bascules en direct, **Edit mesh**,
**Record…** et **Reset to rest**. Toutes les autres entrées ci-dessous sont des éléments
du menu **File**, **Edit**, **Live**, **Output** ou **Tools** ; ces menus contiennent
aussi les entrées de la barre d'outils.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Rôle
   * - Open Puppet… / Examples ▾
     - Charger un ``.puppet`` depuis le disque (menu **File**), ou choisir l'un des
       rigs fournis dans ``examples/puppet/`` depuis **Examples ▾** (le bouton de la
       barre d'outils, aussi dans **File**)
   * - Import PNG… / Import PSD… / Import Cubism…
     - Créer un maillage automatique pour un PNG, séparer un PSD par calques, ou échantillonner
       et reconstruire un rig Cubism. Le sélecteur Cubism accepte à la fois ``.moc3`` et
       ``.model3.json`` ; sans rig ouvert, l'un comme l'autre exécute la conversion
       complète ``.moc3 → .puppet`` (Cubism Native SDK fourni par l'utilisateur).
       Choisir ``.model3.json`` alors qu'un rig est chargé fusionne plutôt ses
       métadonnées JSON-only (mouvements / expressions / physique) sur le document actif.
   * - Recent
     - Rouvre rapidement une marionnette ouverte récemment
   * - Save As…
     - Écrit le rig actuel sous forme de zip ``.puppet``
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - Construit le rig depuis le menu **Edit**
   * - Drag-track head
     - La tête et les yeux se tournent vers le curseur quand il se déplace sur le
       canevas : décalage du curseur → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Cycle cosinusoïdal fermeture→ouverture sur ``ParamEyeLOpen`` / ``ParamEyeROpen``
       toutes les ~4,5 s (le chemin d'écriture forcée contourne le saut "no-change" du canevas
       afin que les pilotes concurrents ne puissent pas bloquer le clignement)
   * - Mic lip-sync
     - RMS du microphone → ``ParamMouthOpenY`` (nécessite ``sounddevice``)
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → lacet / tangage / roulis de la tête +
       yeux + bouche (nécessite ``opencv-python`` + ``mediapipe`` ;
       ouvre une boîte de dialogue d'aperçu en direct avec les points clés détectés)
   * - Auto idle / Idle motions
     - Cycle de respiration + dérive sur les paramètres standard, plus un cycleur
       aléatoire optionnel parmi les mouvements du groupe Idle
   * - Edit mesh
     - Cliquer-glisser sur les sommets du canevas pour affiner le maillage
   * - Record motion
     - Menu **Output** uniquement : capture les changements de paramètres dans un nouveau
       ``Motion`` et l'ajoute au document — cuisson à partir d'une prise, sans création
       manuelle d'images clés
   * - Capture frame… / Record… / Export all motions…
     - Enregistrer un PNG, basculer un enregistrement GIF / WebM / MP4, ou
       rendre par lots chaque mouvement du rig dans son propre fichier (le tout via
       le même chemin de rendu hors écran "personnage seul" utilisé pour le streaming).
       Une image capturée garde la taille propre du rig (côté long d'au plus
       4096 px) sur fond transparent ; un enregistrement ou un export par lots
       fait tenir le personnage dans 1080 px sur fond blanc, car les images
       GIF / WebM / MP4 n'ont pas d'alpha
   * - Output > Virtual camera / NDI output
     - Surfaces de streaming en direct — voir *Streaming en direct vers OBS* ci-dessous
   * - Reset to rest
     - Arrête net le lecteur de mouvement, désactive tous les pilotes en direct,
       efface les expressions / groupes de pose, restaure les paramètres par défaut
   * - Fit to Window
     - Menu **Tools** : recentre et redimensionne la marionnette dans le canevas

Enregistrer ses propres mouvements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pour capturer une prise personnalisée plutôt que de créer les images clés à la main :

1. Basculez **Output > Record motion** — une boîte de dialogue de nom apparaît.
2. Pendant l'enregistrement, faites glisser des curseurs, activez **Webcam tracking**, laissez la physique
   tourner, n'importe quoi qui écrive des valeurs de paramètres.
3. Désactivez **Record motion** — l'enregistreur cuit le flux capturé à 30 Hz dans un
   ``Motion`` avec une piste à segments linéaires par paramètre ayant effectivement bougé
   (les paramètres restés constants sont supprimés). Le nouveau mouvement apparaît immédiatement
   dans le dock **Mouvements** en bas, prêt à être joué / mis en boucle / enregistré.

Les mouvements personnalisés enregistrés ainsi font des allers-retours via le même fichier JSON
``motions/<name>.json`` que ceux créés à la main.

Streaming en direct vers OBS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deux chemins de sortie, les deux rendent la marionnette seule (pas de fond en damier,
pas de chrome d'éditeur) dans un framebuffer hors écran avant de la passer à la surface
de streaming. Le côté le plus long de la sortie est plafonné à 1080 px afin que les
canevas natifs Cubism (March 7th fait 3503×7777) ne soient pas rejetés par les
pilotes de caméra virtuelle DirectShow.

**A. Caméra virtuelle** — apparaît comme une webcam dans la liste de sources *Video
Capture Device* d'OBS. ``pip install pyvirtualcam`` plus le pilote de la plateforme :
OBS Studio 26+ embarque le pilote *OBS Virtual Camera* sur Windows / macOS (cliquez
sur *Start Virtual Camera* dans OBS une fois pour l'enregistrer) ; Linux utilise
``v4l2loopback-dkms`` +
``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
La bascule de menu **Output > Virtual camera** ouvre le flux.

DirectShow / AVFoundation / v4l2loopback sont uniquement RGB — pas de canal alpha —
donc Imervue remplit la zone hors du personnage avec
**magenta #FF00FF** comme clé chromatique. Retirez-la dans OBS via le
filtre Color Key :

1. Clic droit sur la source Video Capture Device > **Filters**
2. **Effect Filters > + > Color Key**
3. Définissez **Key Color Type** = ``Custom Color``,
   **Custom Color** = HEX ``FF00FF``,
   **Similarity** = ``80–300``,
   **Smoothness** = ``30–50``

Le filtre adhère à la source, donc la clé chromatique se réapplique automatiquement
chaque fois que la caméra virtuelle reprend.

**B. Sortie NDI** — diffusion LAN de moins de 50 ms transportant le RGBA, afin
qu'OBS / vMix composent directement par-dessus leurs propres scènes sans passe
de chroma key. ``pip install ndi-python`` + le runtime
`NDI Tools <https://ndi.video/tools/>`_ + le plugin
`obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_.
La bascule de menu **Output > NDI output** diffuse la source (nom par défaut
*Imervue Puppet*).

``ndi-python`` ne fournit qu'une distribution source ; pip la construit
depuis du C++ au moment de l'installation. Les utilisateurs Windows ont besoin de
Visual Studio Build Tools 2022 (avec la charge de travail C++), CMake dans le PATH,
et du NDI SDK depuis <https://ndi.video/for-developers/ndi-sdk/> installé à
l'emplacement par défaut, avec la variable d'environnement ``NDI_SDK_DIR`` pointant vers lui.

Voir ``puppet_guide.md`` § 1.2 pour la marche à suivre complète plus la liste de
dépannage (caméra affichée en magenta, échec cmake de ndi-python, étirement de la
caméra virtuelle, etc.).

Dépendances optionnelles
^^^^^^^^^^^^^^^^^^^^^^^^

* ``sounddevice`` — capture du microphone pour le lip-sync
* ``opencv-python`` + ``mediapipe`` — suivi facial par webcam
* ``imageio-ffmpeg`` — enregistrement MP4 / WebM (déjà livré pour
  la vidéo de diaporama)
* ``pyvirtualcam`` — sortie caméra virtuelle (voir *Streaming en direct*)
* ``ndi-python`` — sortie NDI (voir *Streaming en direct*)
* DLL du Cubism Native SDK fournie par l'utilisateur — conversion
  ``.moc3 → .puppet`` (la Free Material License de Live2D interdit la
  redistribution ; les utilisateurs déposent le SDK sous ``<cwd>/sdk/`` ou définissent
  la variable d'environnement ``CUBISM_CORE_DLL``)

L'onglet Puppet se dégrade gracieusement lorsqu'un paquet Python est absent — la
bascule correspondante reste désactivée et l'installateur de dépendances s'ouvre en
proposant de l'installer ; une fois le paquet installé, la bascule se réactive. Un
indice textuel n'apparaît que lorsque le paquet est présent mais que le périphérique
ou le pilote échoue. ``File > Install dependencies…`` installe par lot
chaque paquet Python optionnel en une seule fois.

----

Espace de travail Desktop Pet (onglet Desktop Pet)
--------------------------------------------------

L'onglet 5 — le **Desktop Pet** — place n'importe quel personnage
``.puppet`` sur votre bureau sous forme de superposition sans cadre
et transparente. L'onglet lui-même est un panneau de contrôle ; le
personnage proprement dit est une fenêtre de premier niveau distincte
qui partage l'intégralité du runtime Puppet (mouvements, expressions,
physique, pilotes d'inactivité, entrée micro / webcam). Le pet peut
réagir aux clics, lancer des animations pilotées par minuterie,
suivre votre curseur, se masquer pendant qu'une autre application
est en plein écran, et prononcer des répliques personnalisées que
vous écrivez dans un fichier JSON.

Ce chapitre est une référence complète de l'onglet. Il est organisé
ainsi :

#. **Démarrage rapide** — chemin en cinq étapes entre « je viens
   d'ouvrir Imervue » et « il y a un pet sur mon bureau ».
#. **Charger un rig** — sélecteur de fichier, exemple fourni,
   restauration entre les lancements.
#. **La fenêtre de superposition** — chaque comportement au niveau
   fenêtre (glisser-déplacer, accrochage aux bords, clic-traversant,
   verrouillage d'ancrage, toujours-en-dessous, masquage en plein
   écran, mise en pause à l'arrêt, opacité, taille, restauration
   multi-écran).
#. **Modèle d'interaction** — zones cliquables au clic gauche, menu
   contextuel complet du clic droit, barre d'état système.
#. **Pilotes en direct** — sept pilotes d'entrée (trois activés par
   défaut) et leurs dépendances optionnelles.
#. **Script du pet** — le fichier JSON qui vous permet de remplacer
   la voix du pet par vos propres répliques, de planifier des
   rappels et de lier les réponses par zone cliquable / par
   mouvement.
#. **Persistance** — ce qui est mémorisé entre les lancements et le
   schéma exact des réglages.
#. **Créer un nouveau pet** — pointeur vers l'onglet Puppet et le
   format de fichier ``.puppet``.
#. **Dépannage** — surprises courantes et que faire à leur sujet.

Démarrage rapide
^^^^^^^^^^^^^^^^

1. Passez à l'onglet **Desktop Pet**.
2. Cliquez sur **Load bundled March 7th** pour utiliser le
   personnage inclus, ou sur **Open Puppet…** pour choisir votre
   propre fichier ``.puppet``.
3. La superposition apparaît sur votre bureau et la case **Show pet
   on desktop** est cochée automatiquement. (Si vous voulez masquer
   le pet sans fermer Imervue, décochez la case ou utilisez l'icône
   de la barre d'état système.)
4. Glissez le personnage à l'endroit voulu. Relâchez près d'un bord
   d'écran pour l'accrocher à ras de celui-ci.
5. Choisissez les **Pilotes en direct** voulus — respiration
   d'inactivité, clignement, suivi du curseur, lip-sync micro,
   suivi webcam — depuis l'onglet de l'espace de travail ou depuis
   le menu contextuel du pet.

Tout ce que vous réglez survit au prochain lancement, donc l'étape
5 est une décision unique par rig / persona.

Charger un rig
^^^^^^^^^^^^^^

L'onglet expose trois chemins de chargement :

* **Open Puppet…** — choisissez n'importe quel fichier ``.puppet``
  sur disque.
* **Load bundled March 7th** — ouvre le rig livré sous
  ``examples/puppet/march_7th.puppet``. Le résolveur consulte
  d'abord ``examples_dir()`` (à côté du programme dans les builds
  empaquetés Nuitka / PyInstaller, la racine du dépôt dans une
  copie des sources) puis se rabat sur une recherche relative au
  dossier de travail courant.
* **Dernier rig** — le rig chargé précédemment se restaure
  automatiquement au démarrage d'Imervue depuis le champ de
  réglages ``last_rig_path`` ; l'onglet Desktop Pet ré-instancie
  la superposition de manière invisible afin que le pet ne soit
  qu'à un clic du même état que celui où vous l'avez laissé.

Un chargement réussi coche automatiquement **Show pet on desktop**
pour que le pet apparaisse immédiatement. Le chemin d'échec laisse
la case telle quelle et écrit l'erreur dans l'étiquette d'état de
l'onglet.

La fenêtre de superposition
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Le personnage vit dans une fenêtre de premier niveau distincte de
la fenêtre principale d'Imervue. La fenêtre est sans cadre, n'a
pas d'entrée dans la barre des tâches et (par défaut) reste
au-dessus de toutes les autres fenêtres.

.. list-table:: Comportements de la fenêtre
   :header-rows: 1
   :widths: 28 72

   * - Comportement
     - Détail
   * - Superposition sans cadre
     - Aucun chrome de fenêtre, aucun bouton réduire / fermer,
       aucune entrée dans la barre des tâches. Le personnage est
       l'intégralité de la surface visible.
   * - Arrière-plan transparent
     - Tout ce que le personnage ne couvre pas est entièrement
       transparent. Le bureau / l'application derrière le pet
       transparaissent pixel par pixel.
   * - Glisser-déplacer
     - Clic gauche maintenu n'importe où sur le corps, glissement,
       relâchement. Le glissement n'est reconnu comme un clic que
       si le curseur s'est déplacé de moins de six pixels — au-delà,
       le geste devient un déplacement et le gestionnaire de clic
       ne se déclenche pas.
   * - Accrochage aux bords
     - Relâchez près d'un bord d'écran (par défaut : à moins de
       24 px) et le pet « se cale » à ras de ce bord. Le seuil est
       configurable de 0 (désactivé) à 200 (très collant).
       L'accrochage s'effectue indépendamment sur chaque axe afin
       qu'un glissement dans un coin l'amarre aux deux bords à la
       fois.
   * - Limitation de débordement
     - Un glissement qui se termine au-delà d'un bord d'écran est
       ramené à l'intérieur. Vous ne pouvez pas abandonner le pet
       hors écran à un endroit où vous ne pourriez plus le saisir.
   * - Mode clic-traversant
     - Lorsqu'il est activé, chaque événement souris traverse le
       pet pour atteindre ce qui se trouve derrière lui. Le
       personnage reste visible mais il ne peut être ni glissé, ni
       cliqué-droit, ni utilisé pour déclencher des mouvements.
       Activez-le quand le pet est purement décoratif.
   * - Verrouiller la position
     - Désactive le glisser-déplacer sans affecter le
       clic-traversant. Utile quand vous avez placé le pet
       exactement où vous le souhaitez et ne voulez pas qu'un
       glissement accidentel le déplace.
   * - Toujours en dessous
     - Bascule le pet de toujours-au-dessus à toujours-en-dessous.
       Le pet se loge derrière toutes les autres fenêtres tel un
       widget de bureau. L'indicateur d'acceptation du focus est
       également désactivé afin que cliquer sur le pet ne le
       remonte pas au premier plan.
   * - Masquage en plein écran
     - Une scrutation d'arrière-plan à 1 Hz observe la fenêtre de
       premier plan sur le moniteur du pet. Lorsque cette fenêtre
       couvre ≥ 99 % de l'écran avec une tolérance par bord ≤ 4 px
       (attrapant à la fois le vrai plein écran et les jeux en
       fenêtré sans bordure), le pet se masque automatiquement.
       À la fin du plein écran, le pet réapparaît à sa position
       précédente. Le détecteur utilise l'API Win32
       ``GetWindowRect`` sous Windows ; sur macOS / Linux il
       devient un no-op silencieux (le pet reste visible).
   * - Mise en pause à l'arrêt
     - Le tick de rendu à ~30 FPS, le tick de script à 1 Hz et la
       scrutation du plein écran (sauf si c'est le plein écran qui
       a masqué le pet) s'arrêtent sur ``hideEvent`` et redémarrent
       au prochain ``showEvent``. Les minuteries des pilotes en
       direct (clignement, idle, mouvements idle, regard)
       continuent de tourner.
   * - Préréglages de taille
     - Petit (200 × 300), moyen (320 × 480), grand (480 × 720).
       Le pet se redimensionne autour de son centre actuel afin
       qu'un changement de taille ne le relocalise pas.
       L'accrochage est rejoué après le redimensionnement.
   * - Curseur d'opacité
     - 10 – 100 %. Agit au niveau fenêtre (via
       ``setWindowOpacity``) afin que tout le pet s'estompe, pas
       seulement la texture. Le plancher minimal de 10 % existe
       pour que vous puissiez toujours voir et saisir le pet —
       complètement invisible vous le ferait perdre.
   * - Mémoire de position
     - Le ``(x, y)`` post-accrochage après chaque relâchement est
       persisté, avec le moniteur sur lequel il se trouve. Au
       prochain lancement, le pet revient à cette position, bridée
       à l'intérieur de ce moniteur. Si le moniteur a disparu
       (vous l'avez débranché depuis le dernier lancement), le pet
       va sur le premier écran, sa position enregistrée y étant
       bridée. Le coin inférieur droit ne sert que si aucune
       position n'a jamais été enregistrée.

Modèle d'interaction
^^^^^^^^^^^^^^^^^^^^

Le pet répond à la souris via trois canaux indépendants.

**Clic gauche sur le corps**

La position du clic est reconvertie en coordonnées de canevas
puppet (en annulant le pan / zoom du canevas) et passe par le
pipeline ``hit_test`` existant. Le résultat dicte le comportement
comme suit :

#. Si une ``HitArea`` couvre le drawable cliqué ET que cette zone
   a un mouvement attaché, le mouvement se joue.
#. Qu'un mouvement ait été joué ou non, le pet peut afficher une
   bulle de dialogue — voir la section *Script du pet* pour la
   priorité de sélection des répliques.
#. Si aucune zone cliquable ne couvre le clic, le pet se rabat sur
   une salutation (depuis la liste ``greetings`` du script ou la
   liste de repli intégrée).

Un geste de glisser-déplacer supprime le gestionnaire de clic, donc
déplacer le pet n'affiche pas de bulle de dialogue. Appuyer joue un
mouvement du groupe ``Drag`` du rig et relâcher après un glissement
en joue un de son groupe ``Land``, lorsque le rig possède ces
groupes.

**Clic droit n'importe où sur le corps**

Ouvre un menu contextuel avec la structure suivante :

* **Hide pet** — action de haut niveau qui ferme la superposition.
* Sous-menu **Live drivers** — sept bascules à cocher (Auto idle,
  Idle motions, Auto-blink, Drag-track head, Mouse gaze, Mic
  lip-sync, Webcam tracking). L'état coché reflète l'état des
  pilotes en direct, donc le menu indique ce qui tourne actuellement.
* Sous-menu **Play motion** — peuplé depuis la liste
  ``document.motions`` du rig actif. Sélectionner une entrée joue
  ce mouvement ; il ne prononce aucune réplique ``motion_lines``
  (celles-ci ne répondent qu'à un clic sur une zone cliquable).
* Sous-menu **Apply expression** — peuplé depuis
  ``document.expressions`` du rig. Chaque entrée est cochée tant
  que son expression est active ; en sélectionner une ajoute la
  superposition de paramètres de l'expression, la sélectionner à
  nouveau la retire.
* Cinq bascules à cocher de haut niveau : **Lock position**,
  **Click-through**, **Always on bottom**, **Hide on fullscreen**,
  **Speech bubble** — accès rapide aux mêmes bascules de l'onglet
  espace de travail.
* Sous-menu **Size** — Small / Medium / Large ; le préréglage
  courant est coché.

Les sous-menus mouvement / expression sont désactivés lorsqu'aucun
rig n'est chargé.

**Icône de barre d'état système**

Une icône de barre d'état (instanciée uniquement sur les
plateformes signalant la prise en charge de la barre d'état)
fournit une quatrième surface pour les actions les plus courantes :

* Clic gauche bascule la visibilité du pet.
* Clic droit ouvre un menu avec **Show pet** (à cocher),
  **Click-through**, **Open puppet…**, **Hide pet**.
* Les éléments à cocher Show / Click-through reflètent l'état de
  l'espace de travail via ``sync_visibility`` /
  ``sync_click_through``, donc ils restent synchronisés quel que
  soit l'endroit où l'utilisateur bascule l'interrupteur
  correspondant.

Pilotes en direct
^^^^^^^^^^^^^^^^^

Chaque pilote en direct est créé paresseusement à la première
activation, donc un pet dormant ne paie aucun coût de minuterie /
thread pour les pilotes que vous n'allumez jamais. L'état de chaque
pilote est persisté ; activer, fermer Imervue puis relancer restaure
le rig avec les mêmes pilotes en marche. La superposition elle-même
n'apparaît au lancement que si **Show the pet when Imervue starts**
est coché dans le groupe Window de l'onglet.

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - Pilote
     - Ce qu'il fait
     - Dépendance optionnelle
   * - **Auto idle**
     - Respiration + dérive subtile sur les paramètres standard
       (``ParamBreath`` etc.) afin que le personnage paraisse
       vivant quand rien d'autre ne l'anime.
     - aucune
   * - **Idle motions**
     - Choisit aléatoirement un mouvement du groupe ``Idle`` du
       rig et le joue — un tout de suite à l'activation, puis
       toutes les quelques secondes. S'efface pendant qu'un
       mouvement hors Idle se joue.
     - aucune
   * - **Auto-blink**
     - Ferme et rouvre les yeux selon une courbe cosinus douce
       toutes les ~4,5 s. Le pilote force l'écriture du paramètre
       afin que les autres pilotes qui touchent aux valeurs
       d'ouverture des yeux ne suppriment pas le clignement.
     - aucune
   * - **Drag-track head**
     - La tête + les yeux tournent vers le curseur pendant qu'il
       se déplace sur le pet. Pilote
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - aucune
   * - **Mouse gaze**
     - Les yeux et la tête suivent le curseur n'importe où à
       l'écran, par rapport au centre du pet (les yeux mènent).
       Pilote les mêmes quatre paramètres.
     - aucune
   * - **Mic lip-sync**
     - L'amplitude RMS du micro pilote ``ParamMouthOpenY``. La
       bouche s'ouvre proportionnellement au volume de votre voix,
       si bien que le personnage semble parler quand vous parlez.
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker lit votre webcam à ~30 FPS et
       pilote la pose de la tête + l'ouverture des yeux + les
       paramètres d'ouverture de la bouche. Aucune fenêtre
       d'aperçu ne s'ouvre pour le pet (l'aperçu de la caméra
       appartient à l'onglet Puppet).
     - ``opencv-python`` + ``mediapipe``

Les deux pilotes à dépendance optionnelle se dégradent gracieusement :
si le paquet requis n'est pas installé, basculer la case la fait
rebondir à l'état désactivé et l'étiquette d'état de l'espace de
travail affiche un indice « install sounddevice » / « install
opencv-python + mediapipe ».

Script du pet — voix personnalisée et événements planifiés
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

La bulle de dialogue du pet puise dans un fichier JSON que vous
pouvez écrire et charger depuis le groupe **Pet script** de
l'onglet. Le script régit cinq choses :

* **Greetings** — répliques par défaut au clic quand rien de plus
  spécifique ne correspond.
* **Time-of-day greetings** — salutations selon la tranche de
  l'horloge locale (``morning`` 05–11 h, ``afternoon`` 12–17 h,
  ``evening`` 18–21 h, ``night`` 22–04 h), utilisées avant les
  salutations simples ; une tranche sans répliques se rabat sur
  celles-ci.
* **Hit-area responses** — paniers de répliques par ``HitArea.id``.
* **Motion lines** — paniers de répliques par nom de mouvement,
  prononcés quand un clic sur une zone cliquable joue ce mouvement
  (pas quand un mouvement est lancé depuis le menu contextuel).
* **Scheduled chimes** — répliques pilotées par minuterie qui se
  déclenchent toutes les ``every_seconds`` de temps horloge
  monotone.

Schéma (versionné — les futurs champs sont compatibles ascendants) :

.. code-block:: json

   {
     "version": 1,
     "name": "March 7th — playful voice",
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

Règles de chargement :

* Les listes sont échantillonnées en tourniquet par panier afin
  que l'utilisateur ne voie pas deux fois la même réplique d'affilée.
* Les clés de niveau supérieur inconnues sont ignorées (compatibilité
  ascendante — un futur fichier v2 se charge encore sur un runtime
  v1).
* Les entrées de liste invalides (mauvais type, entrées planifiées
  malformées, ``every_seconds`` nul / négatif) sont ignorées — une
  ligne défectueuse ne fait pas échouer tout le chargement. Seul
  un JSON franchement non analysable lève une erreur et fait
  remonter le chemin dans l'étiquette d'état.
* La cascade zone cliquable / mouvement / salutation est en
  couches : un clic gauche consulte ``hit_responses[area.id]``
  d'abord, puis ``motion_lines[area.motion]``, puis
  ``time_of_day_greetings``, puis ``greetings``, puis le jeu de
  salutations par défaut intégré comme plancher.
* Le suivi du temps utilise ``time.monotonic`` afin que mettre le
  portable en veille ou faire bondir l'horloge système ne puisse
  pas déclencher en rafale des événements en file.

**Reset to default** abandonne le script utilisateur et revient au
jeu de salutations intégré ; le chemin de script persisté est
effacé afin que le prochain lancement ne le recharge pas.

Un exemple fonctionnel se trouve à
``examples/desktop_pet/march_7th.petscript.json`` — six
salutations, deux paniers de zones cliquables (tête / corps),
trois lignes de mouvement (wave / curtsy / cheer) et un rappel
d'étirement de 30 minutes. Les répliques tête / corps répondent
aux clics sur un rig dont les zones cliquables s'appellent
``HitAreaHead`` / ``HitAreaBody`` (la convention de Cubism) ; le
rig March 7th livré n'en définit aucune, donc un clic dessus
choisit plutôt une salutation.

Persistance
^^^^^^^^^^^

Tout l'état Desktop Pet fait des allers-retours via
``user_setting_dict["desktop_pet"]`` (un emplacement du fichier
de réglages utilisateur standard d'Imervue). Chaque champ a une
valeur par défaut + un bridage de plage au chargement afin qu'un
fichier de réglages corrompu ne puisse pas faire planter le
démarrage.

.. list-table:: Champs persistés
   :header-rows: 1
   :widths: 28 18 54

   * - Champ
     - Défaut
     - Notes
   * - ``last_rig_path``
     - ``""``
     - Restauré automatiquement au lancement si le fichier existe
       encore.
   * - ``script_path``
     - ``""``
     - Restauré automatiquement au lancement si le script s'analyse
       encore ; un script illisible revient silencieusement aux
       valeurs par défaut.
   * - ``position``
     - ``[-1, -1]``
     - ``(x, y)`` en coordonnées écran du dernier relâchement de
       glissement. ``-1, -1`` (jamais enregistré) signifie
       « utiliser le coin inférieur droit ». Quand le moniteur
       enregistré a disparu, la position est bridée dans le
       premier écran.
   * - ``size_preset``
     - ``"medium"``
     - L'une de ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Les valeurs hors plage sont bridées à ``[0.1, 1.0]`` ;
       seule une valeur non numérique revient au défaut.
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - Mutuellement exclusif avec toujours-au-dessus.
   * - ``hide_on_fullscreen``
     - ``true``
     - Mettez ``false`` pour garder le pet visible pendant le
       plein écran.
   * - ``snap_threshold``
     - ``24``
     - Bridé à ``[0, 200]`` px.
   * - ``drivers``
     - ``auto_idle``, ``idle_motion``, ``auto_blink``
       ``true`` ; les autres ``false``
     - Sous-dict indexé par id de pilote (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mouse_gaze``, ``mic_lipsync``, ``webcam_tracking``).
       Les clés inconnues font un aller-retour intactes pour la
       compatibilité ascendante.
   * - ``show_on_launch``
     - ``false``
     - Réglé par **Show the pet when Imervue starts** dans le
       groupe Window de l'onglet. Le rig et les pilotes sont
       restaurés au lancement dans tous les cas ; la superposition
       n'apparaît que si ce réglage est activé.
   * - ``speech_enabled``
     - ``true``
     - Quand c'est faux, la bulle de dialogue ne s'affiche jamais.

La fusion du dict de réglages se fait sur un niveau de
profondeur : des fichiers de réglages plus anciens auxquels
manquent des clés plus récentes produisent malgré tout un dict
d'état complet au chargement (les valeurs par défaut comblent les
lacunes) ; les clés plus récentes que vous avez sauvegardées
survivent à un retour vers un runtime plus ancien qui ne les
connaît pas.

Créer un nouveau pet
^^^^^^^^^^^^^^^^^^^^

N'importe quel fichier ``.puppet`` fonctionne comme un personnage
Desktop Pet — l'onglet Desktop Pet est purement un moteur de rendu
+ coquille d'interaction ; la création de rig se fait dans l'onglet
Puppet (voir *Espace de travail Puppet (onglet Puppet)*).

Pour créer votre propre rig de pet :

#. Passez à l'onglet Puppet et importez une œuvre via
   **File > Import PNG…** ou **File > Import PSD…**, ou tirez un
   modèle Cubism via **File > Import Cubism…**.
#. Créez des déformateurs de rotation / warp, des paramètres, des
   mouvements, des expressions et (optionnellement) des zones
   cliquables liées à des parties du corps afin que le gestionnaire
   de clic gauche du Desktop Pet puisse déclencher des mouvements.
#. Enregistrez le rig via **File > Save As…** dans un zip
   ``.puppet``.
#. Revenez à l'onglet Desktop Pet et chargez le nouveau fichier
   via **Open Puppet…**.

Si votre rig définit des entrées ``HitArea``, vous pouvez écrire
des répliques de bulle par zone cliquable dans un
``.petscript.json`` dont les clés ``hit_responses`` correspondent
aux ids de zone.

Dépannage
^^^^^^^^^

**Le pet apparaît dans un rectangle gris au lieu d'être entièrement
transparent.** L'attribut d'arrière-plan translucide au niveau OS
requiert une surface GL consciente du canal alpha plus les
attributs correspondants sur le widget GL embarqué. Assurez-vous
qu'aucun outil tiers de gestion de fenêtres ne contourne l'attribut
``WA_TranslucentBackground`` sur la fenêtre de superposition
(certains gestionnaires de fenêtres personnalisés sous Linux le
font). Sous Windows / macOS cela devrait « juste fonctionner ».

**« Load bundled March 7th » signale que le fichier est introuvable.**
Le résolveur consulte d'abord ``examples_dir()`` (l'emplacement sûr
en mode gelé utilisé par les builds empaquetés) puis se rabat sur
un chemin relatif au CWD. Si aucun ne contient le rig, l'étiquette
d'état fait remonter le chemin attendu. Vérifiez que le répertoire
``examples/`` a bien été livré avec votre installation — pour les
checkouts source, lancez Imervue depuis la racine du dépôt.

**Le pet ne parle pas quand on clique.** Trois vérifications :

#. Assurez-vous que la bascule **Speech bubble on click** est
   activée (dans l'onglet ou le menu contextuel).
#. Si vous avez chargé un script personnalisé, vérifiez que le JSON
   s'analyse — l'étiquette d'état de l'onglet affiche l'erreur de
   chargement.
#. Si **Click-through** est activé, le clic va à la fenêtre
   derrière le pet ; désactivez-le dans l'onglet ou le menu de la
   barre d'état. (Avec la parole activée, chaque clic obtient une
   réplique : un rig sans zones cliquables ne joue aucun mouvement,
   mais le clic vous salue quand même.)

**La case du suivi webcam rebondit à l'état désactivé.** Le suivi
webcam a besoin de ``opencv-python`` et ``mediapipe`` installés
dans le même environnement Python que celui dans lequel tourne
Imervue. Installez avec ``pip install opencv-python mediapipe``.
Après installation, cochez à nouveau la case. Le pet n'ouvre
aucune fenêtre d'aperçu ; pour voir ce que la caméra détecte,
activez **Webcam tracking** dans l'onglet Puppet, qui affiche les
points caractéristiques du visage.

**Le pet ne se masque pas automatiquement pendant les applications
plein écran.** Le détecteur de plein écran scrute la fenêtre de
premier plan à 1 Hz. Sous Windows il utilise l'API Win32
``GetWindowRect`` ; sur macOS / Linux il n'a pas d'équivalent
multi-plateforme fiable et devient un no-op silencieux (le pet
reste visible). Pour Windows : assurez-vous que **Hide when other
app is fullscreen** est coché et vérifiez que la fenêtre plein
écran couvre bien ≥ 99 % du même moniteur que celui du pet.

**La position du pet dérive hors écran entre les lancements.** Cela
arrive quand l'écran sur lequel se trouvait le pet n'est plus
connecté au prochain lancement (station d'accueil portable,
second moniteur débranché). Le pet va alors sur le premier écran,
sa position enregistrée y étant bridée — glissez-le où
vous le voulez et la prochaine sauvegarde écrasera la position
obsolète.

----

Rotation et retournement
------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Action
     - Raccourci
     - Menu
   * - Rotation 90 ° horaire
     - ``R``
     - Clic droit > Modify > Rotate Clockwise
   * - Rotation 90 ° antihoraire
     - ``Shift + R``
     - Clic droit > Modify > Rotate Counter-clockwise
   * - Retournement horizontal
     - --
     - Clic droit > Modify > Flip Horizontal
   * - Retournement vertical
     - --
     - Clic droit > Modify > Flip Vertical
   * - Rotation sans perte
     - --
     - Clic droit > Lossless Rotate > Lossless Rotate CW / CCW. Seul un JPEG est vraiment
       sans perte (sa balise d'orientation change) ; PNG / BMP / TIFF / WebP /
       GIF sont décodés, tournés et réenregistrés (un WebP avec perte est réencodé) ;
       les RAW d'appareil, HEIC et fichiers multi-images sont refusés

----

Exporter des images
-------------------

Export individuel
^^^^^^^^^^^^^^^^^

Ouvrez une image (Deep Zoom), puis clic droit > ``Exporter / Enregistrer sous``.

- Choisissez le format : PNG, JPEG, WebP, BMP, TIFF ; AVIF si Pillow prend en charge l'AVIF, HEIC et JPEG XL si ``pillow-heif`` / ``pillow-jxl-plugin`` est installé
- Ajustez la qualité (pour les formats avec perte)
- Choisissez les métadonnées à conserver : toutes, toutes sauf la localisation (par défaut) ou aucune. L'appareil, l'objectif et la date de prise de vue sont conservés ; le choix est mémorisé et l'export par lot propose la même option
- Aperçu de la taille de fichier estimée
- Choisissez un emplacement d'enregistrement. Le nom proposé est encore libre (``photo_1.png`` à côté de ``photo.png``) ; un fichier existant — surtout la photo elle-même — n'est remplacé qu'après confirmation

Préréglages d'export
^^^^^^^^^^^^^^^^^^^^

L'export par lots (ci-dessous) propose une liste **Preset** qui remplit la taille, le format et la
qualité pour les cibles courantes ; avec **Custom**, c'est vous qui les choisissez :

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Préréglage
     - Sortie
   * - **Web — 1600 px JPEG**
     - Côté long jusqu'à 1600 px, JPEG qualité 85.
   * - **4K Web — 3840 px JPEG**
     - Côté long jusqu'à 3840 px, JPEG qualité 90.
   * - **Print — 300 DPI PNG**
     - Pleine résolution, PNG, 300 dpi.
   * - **Instagram — 1080×1080 square**
     - Recadrage carré centré, 1080 × 1080, JPEG qualité 90.
   * - **Thumbnail — 400 px JPEG**
     - Côté long jusqu'à 400 px, JPEG qualité 80.

Filigrane
^^^^^^^^^

L'export par lots peut aussi dessiner un filigrane texte sur chaque copie exportée : le texte,
sa position (un coin ou le centre) et son opacité. Les fichiers d'origine ne sont jamais modifiés.

Export par lots
^^^^^^^^^^^^^^^

Sélectionnez plusieurs images, puis clic droit > ``Opérations par lots`` > ``Export par lots``.

- Conversion de format uniforme
- Définir largeur / hauteur maximales (mise à l'échelle automatique du ratio d'aspect)
- Contrôle de la qualité
- Barre de progression en temps réel

Créer un GIF / une vidéo
^^^^^^^^^^^^^^^^^^^^^^^^

Sélectionnez plusieurs images, puis clic droit > ``Opérations par lots`` > ``Créer GIF / Vidéo``.

- Sortie GIF et MP4 ; le MP4 utilise le ffmpeg du PATH, sinon celui fourni avec la dépendance par défaut ``imageio-ffmpeg``
- Glisser pour réordonner les images
- Définir les images par seconde (FPS)
- Dimensions personnalisées
- Option de boucle : boucler indéfiniment ou, si elle est désactivée, lire une seule fois
- Le fichier proposé est ``output.gif`` à côté de la première image, numéroté (``output_1.gif``) si ce nom est pris ; un nom saisi qui existe déjà n'est remplacé qu'après confirmation

----

Lecture d'animations
--------------------

À l'ouverture de fichiers GIF, APNG ou WebP animés, l'animation se lit automatiquement. Une animation qui occuperait
plus de 512 Mo une fois décodée est décodée image par image pendant la lecture : l'ouvrir
ne fige pas la fenêtre et ne remplit pas la mémoire.
Une image de 10 ms ou moins s'affiche 100 ms, comme dans les navigateurs : beaucoup de GIF comptent dessus.

Un TIFF multipage — un document numérisé — n'est pas lu comme une animation : il affiche une page à la fois, tournée avec ``,`` et ``.``, et l'indicateur donne le numéro de page. Les images qui ne sont pas une animation ne défilent jamais non plus : l'aperçu qu'un appareil photo intègre à un JPEG (MPF), les calques d'un PSD et l'image par défaut d'un APNG, l'image fixe destinée aux programmes qui ne gèrent pas l'APNG.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``Space``
     - Lecture / Pause
   * - ``,``
     - Image précédente
   * - ``.``
     - Image suivante
   * - ``]``
     - Accélérer
   * - ``[``
     - Ralentir

----

Comparaison d'images
--------------------

En mode vignettes, sélectionnez 2 ou 4 images, puis clic droit > ``Comparer les images`` (ou
choisissez-les dans la liste de la boîte de dialogue).

La boîte de dialogue comprend quatre onglets :

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Onglet
     - Rôle
   * - **Côte à côte**
     - Afficher 2 ou 4 images simultanément ; chacune se met automatiquement à l'échelle dans son volet.
   * - **Superposition**
     - Mélanger deux images avec un curseur alpha (0 → A uniquement, 100 → B uniquement). Nécessite exactement 2 sélectionnées.
   * - **Différence**
     - Visualisation par pixel ``|A − B|`` avec un curseur de gain (0,10× – 20×) pour amplifier les variations subtiles.
   * - **A | B Split**
     - Vue avant / après avec un séparateur vertical déplaçable. Faites glisser la poignée pour balayer entre les deux
       images ; idéal pour montrer des ajustements de recette de développement ou comparer des exports. Nécessite exactement 2 sélectionnées.

Lorsque les deux images ont des dimensions différentes, ``B`` est rééchantillonné aux dimensions de ``A`` avec Lanczos. Les très grandes
images sont plafonnées à 2048 px sur le côté long en interne afin que superposition / différence restent interactives.

.. seealso::
   Pour une comparaison en ligne sans ouvrir de boîte de dialogue, utilisez **Vue divisée** (``Shift + S``) ou
   **Lecture double page** (``Shift + D`` / ``Ctrl + Shift + D``) décrites dans la section Navigation.

----

Diaporama
---------

Appuyez sur ``S`` ou clic droit > ``Diaporama`` pour démarrer un diaporama automatique.

- Intervalle par image ajustable
- Transition en fondu optionnelle entre les images

----

Recherche
---------

Appuyez sur ``Ctrl + F`` ou ``/`` et saisissez un mot-clé pour rechercher des images dans le dossier courant par nom de fichier.

La recherche utilise une **correspondance approximative** avec un classement à trois niveaux (préfixe > sous-chaîne > sous-séquence) et
un **surlignage de sous-chaîne** dans les résultats. Appuyez sur ``Enter`` ou double-cliquez pour sauter à une image.

Pour sauter par **index d'image** plutôt que par nom, appuyez sur ``Ctrl + G`` pour la boîte de dialogue "Aller à".

----

Copier-coller
-------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Action
     - Méthode
   * - Copier l'image dans le presse-papiers
     - ``Ctrl + C`` en mode Deep Zoom
   * - Coller l'image du presse-papiers
     - ``Fichier`` > ``Coller depuis le presse-papiers`` l'ouvre dans l'éditeur d'annotation (rien n'est enregistré) ;
       ``Ctrl + V`` l'enregistre sous ``pasted_<timestamp>.png`` dans le dossier courant et l'ouvre, ou
       ouvre un chemin de fichier copié dans le presse-papiers
   * - Surveiller automatiquement le presse-papiers
     - ``Fichier`` > ``Annoter automatiquement les images du presse-papiers`` (bascule)

.. note::
   Lorsque la surveillance automatique est activée, à chaque fois qu'une nouvelle image apparaît dans le presse-papiers (par ex. depuis un outil de capture d'écran), l'éditeur d'annotation s'ouvre automatiquement.

----

Supprimer des images
--------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Action
     - Méthode
   * - Supprimer l'image courante
     - Appuyez sur ``Delete``
   * - Supprimer les images sélectionnées
     - Sélectionner plusieurs, puis ``Delete`` ou clic droit > ``Supprimer les images sélectionnées``

Les images sont déplacées vers la Corbeille du système et peuvent y être récupérées. Sur un
lecteur sans corbeille — carte mémoire, clé USB ou partage réseau, où Windows les
supprimerait définitivement — le fichier est conservé : à la fermeture, Imervue liste ces
fichiers et demande s'il faut les supprimer définitivement.

Leurs sidecars les suivent : ``IMG.JPG.xmp``, ``IMG.JPG.annotations.json`` et
``IMG.xmp``, sauf si le RAW d'une paire RAW + JPEG utilise encore ce dernier. Un
sidecar laissé derrière collerait sa note et ses retouches au prochain ``IMG.*``
que l'appareil écrit sous le même nom.

----

Opérations par lots
-------------------

En mode vignettes, sélectionnez plusieurs images, puis clic droit > ``Opérations par lots`` :

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Fonctionnalité
     - Description
   * - Renommer par lots
     - Renommer à l'aide de modèles : ``{name}``, ``{n}``, ``{ext}``
   * - Déplacer / Copier
     - Déplacer ou copier les images vers un autre dossier
   * - Tout faire pivoter
     - Faire pivoter toutes les images sélectionnées en une fois
   * - Export par lots
     - Convertir le format et redimensionner en masse
   * - Créer GIF / Vidéo
     - Animer la sélection en GIF ou en MP4 (voir *Créer un GIF / une vidéo*)
   * - Taguer par lieu
     - Ajouter aux mots-clés XMP de chaque photo géolocalisée la ville et le pays les plus proches
   * - Indexer les mots-clés
     - Ajouter à la bibliothèque les mots-clés XMP de la sélection
   * - Tri automatique : photos floues
     - Marquer les photos floues comme rejetées
   * - Tri automatique : faible qualité
     - Marquer comme rejeté le quart le plus faible de la sélection (netteté, exposition, contraste)
   * - Rotation automatique selon l'EXIF
     - Enregistrer une copie PNG redressée de chaque photo sous ``<name>_oriented.png``
   * - Combiner en PDF / TIFF…
     - Réunir la sélection, dans l'ordre d'affichage, en un seul PDF ou TIFF multipage
   * - Importer dans des dossiers datés…
     - Copier la sélection dans des dossiers ``YYYY/MM`` selon la date de prise de vue (EXIF, sinon la date
       du fichier) ; un fichier déjà présent garde son nom et le nouveau venu reçoit ``_1``
   * - Ajouter au tag
     - Appliquer le même tag à toutes les images sélectionnées
   * - Ajouter à un album
     - Placer toutes les images sélectionnées dans un album

Déplacer ou copier n'écrase jamais un fichier du même nom : il arrive sous
``name_1.ext``. Une photo renommée ou déplacée dans Imervue — renommage par lots,
renommage par jetons, arborescence, Déplacer / Copier, double volet, bac de
préparation, organisateur d'images — garde sa note, son favori, ses tags, son
étiquette de couleur, son titre, sa description, sa note de bibliothèque et son
marquage de tri (un dossier renommé ou déplacé, ceux de toutes ses photos). Ses
sidecars la suivent : ``IMG.xmp``, ``IMG.JPG.xmp`` et
``IMG.JPG.annotations.json``. Un ``IMG.xmp`` encore utilisé par le RAW d'une
paire RAW + JPEG est copié plutôt que déplacé.

Une photo renommée dans un autre programme pendant que son dossier est ouvert dans
Imervue garde les mêmes données ; celles que le nouveau nom avait déjà restent
telles quelles.

----

Histogramme RGB
---------------

Appuyez sur ``H`` en mode Deep Zoom pour superposer un histogramme RGB sur l'image. Appuyez à nouveau pour masquer.

----

Définir comme fond d'écran
--------------------------

Clic droit en mode Deep Zoom > ``Définir comme fond d'écran`` pour définir l'image courante comme fond d'écran du bureau.

Pris en charge sur Windows, macOS et Linux (GNOME).

Windows rend le bureau noir, tout en signalant un succès, quand il reçoit un fichier qu'il ne sait pas décoder. Une image qui n'est ni JPEG, ni PNG, ni BMP — RAW d'appareil photo, HEIC, PSD, TGA, WebP et les autres formats qu'ouvre Imervue — ainsi qu'une photo à redresser sont donc transmises sous forme de copie JPEG de ce qu'affiche la visionneuse. La copie est conservée dans ``%LOCALAPPDATA%\Imervue\wallpaper`` (``~/.local/share/imervue/wallpaper`` sous macOS et Linux) ; seule la plus récente est gardée.

----

Multi-fenêtres
--------------

``Fichier`` > ``Nouvelle fenêtre`` ouvre une autre fenêtre Imervue indépendante. Chaque fenêtre peut parcourir un dossier différent.

Préréglages de disposition d'espace de travail
----------------------------------------------

``Fichier`` > ``Espaces de travail…`` capture la géométrie courante de la fenêtre, la disposition
des docks / barres d'outils, la séparation arbre / visionneuse et le dossier racine actif sous un nom — puis
vous laisse basculer entre les dispositions enregistrées. L'onglet actif et la séparation des panneaux de l'onglet Modify ne sont pas
enregistrés. La boîte de dialogue prend en charge Enregistrer l'actuel, Charger, Renommer
et Supprimer. Les espaces de travail sont conservés dans ``user_setting.json`` (sous la clé
``workspaces``) et survivent aux sessions.

.. tip::
   Construisez un espace de travail **Browse** avec un arbre large à côté de la visionneuse, et un
   espace de travail **Focus** distinct avec l'arbre resserré et les docks inutiles
   fermés. Un clic place toute votre fenêtre dans la forme adéquate pour chaque tâche.

Gestes du pavé tactile
----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Geste
     - Action
   * - Pincement
     - Zoom avant / arrière en Deep Zoom (ancré au centre du pincement)
   * - Glissement horizontal
     - Image précédente / suivante

----

Association de fichiers (Windows)
---------------------------------

Enregistrez Imervue comme visionneuse d'images dans l'Explorateur Windows :

1. ``Fichier`` > ``Association de fichiers`` > ``Enregistrer 'Open with Imervue'``
2. Aucun droit administrateur n'est nécessaire : l'enregistrement écrit dans le registre de l'utilisateur courant.
3. Après l'enregistrement, clic droit sur n'importe quelle image dans l'Explorateur pour voir l'option ``Open with Imervue``.

Pour retirer : ``Fichier`` > ``Association de fichiers`` > ``Supprimer l'association de fichiers``.

----

Système de plugins
------------------

Imervue prend en charge les plugins pour des fonctionnalités étendues.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Action
     - Emplacement dans le menu
   * - Voir les plugins installés
     - ``Plugins`` > ``Gérer les plugins``
   * - Télécharger de nouveaux plugins
     - ``Plugins`` > ``Télécharger des plugins``
   * - Ouvrir le dossier des plugins
     - ``Plugins`` > ``Ouvrir le dossier des plugins``
   * - Recharger les plugins
     - ``Plugins`` > ``Recharger les plugins``

----

Langue
------

Changez la langue de l'interface depuis le menu ``Langue`` :

- Anglais
- Chinois traditionnel (繁體中文)
- Chinois simplifié (简体中文)
- Coréen (한국어)
- Japonais (日本語)

Un redémarrage est nécessaire après le changement.

Les plugins peuvent ajouter leurs propres langues. **Español** est proposé exactement
ainsi : installez le plugin ``spanish_translation`` depuis le téléchargeur de plugins et il
apparaît dans le menu ``Language`` aux côtés des cinq langues intégrées. Un plugin peut aussi
compléter les traductions d'une langue existante ; les clés déjà présentes ne sont jamais
écrasées, un plugin ne peut donc pas casser une chaîne livrée.

----

Référence des raccourcis clavier
--------------------------------

Navigation
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``Gauche`` / ``Droite``
     - Image précédente / suivante
   * - Touches fléchées
     - Déplacer le cadre de focus d'une vignette à l'autre
   * - ``Ctrl + Shift + Gauche`` / ``Droite``
     - Aller au dossier frère précédent / suivant contenant des images
   * - ``Alt + Gauche`` / ``Alt + Droite``
     - Historique précédent / suivant (style navigateur)
   * - ``Ctrl + G``
     - Aller à l'image par numéro
   * - ``X``
     - Sauter à une image aléatoire
   * - Molette / Pincement
     - Zoomer / dézoomer
   * - Glissement horizontal
     - Image précédente / suivante
   * - Glisser-clic central
     - Panoramique
   * - ``F``
     - Plein écran
   * - ``Shift + Tab``
     - Mode cinéma (masquer toute l'interface)
   * - ``Ctrl + L``
     - Basculer Grille ↔ Liste (détails)
   * - ``Shift + S``
     - Vue divisée (deux images côte à côte)
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - Lecture double page / RTL (manga)
   * - ``Ctrl + Shift + M``
     - Miroir de l'image courante sur un second écran
   * - ``Esc``
     - Revenir aux vignettes / quitter le plein écran / fermer le mode double page ou liste
   * - ``W``
     - Ajuster à la largeur
   * - ``Shift + W``
     - Ajuster à la hauteur
   * - ``Shift + F``
     - Ajuster à la fenêtre
   * - ``-`` / ``=``
     - Zoom arrière / avant
   * - ``V``
     - Mode lecture : ajuster à la largeur, faire défiler pour lire, passer à l'image suivante à la fin
   * - ``Home``
     - Ajuster l'image entière à la fenêtre (dans la grille : retour en haut)

Édition
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``E``
     - Ouvrir l'éditeur d'annotation
   * - ``R``
     - Rotation horaire
   * - ``Shift + R``
     - Rotation antihoraire
   * - ``Ctrl + Z``
     - Annuler
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Rétablir
   * - ``Delete``
     - Supprimer l'image

Organisation
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``0``
     - Basculer favori
   * - ``1`` -- ``5``
     - Noter (appuyer à nouveau pour effacer)
   * - ``F1`` -- ``F5``
     - Étiquette de couleur : rouge / jaune / vert / bleu / violet (appuyer sur la même touche pour effacer)
   * - ``P``
     - Tri : Sélectionner (à conserver)
   * - ``Shift + X``
     - Tri : Rejeter
   * - ``U``
     - Tri : Retirer le marquage
   * - ``B``
     - Basculer le signet
   * - ``T``
     - Gestionnaire de tags et albums

Outils et superpositions
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``Ctrl + F`` / ``/``
     - Recherche approximative avec surlignage des sous-chaînes
   * - ``Ctrl + C``
     - Copier l'image dans le presse-papiers
   * - ``Ctrl + V``
     - Coller depuis le presse-papiers
   * - ``H``
     - Histogramme RGB
   * - ``F8`` / ``Ctrl + F8``
     - Superposition d'infos OSD / HUD de débogage (VRAM, cache, threads)
   * - ``Shift + P``
     - Vue pixel (à partir de 400 % affiche le RGB / HEX sous le curseur ; la grille dès que ≤ 40 000 pixels de l'image sont à l'écran)
   * - ``Shift + M``
     - Faire défiler les modes de couleur (Normal / Niveaux de gris / Inversé / Sépia)
   * - ``L``
     - Loupe : une zone agrandie qui suit le curseur (également sur les vignettes)
   * - ``S``
     - Diaporama
   * - ``Ctrl + Shift + P``
     - Palette de commandes
   * - ``Alt + M``
     - Rejouer la dernière macro sur la sélection

Images animées
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``Space``
     - Lecture / Pause
   * - ``,``
     - Image précédente
   * - ``.``
     - Image suivante
   * - ``[``
     - Ralentir
   * - ``]``
     - Accélérer

----

Bibliothèque et gestion des métadonnées
---------------------------------------

Imervue maintient un index basé sur SQLite à ``%LOCALAPPDATA%/Imervue/library.db``
(Windows) ou ``~/.cache/imervue/library.db`` (POSIX) pour la recherche inter-dossiers,
les tags hiérarchiques, les albums intelligents, les empreintes perceptuelles, les notes et les indicateurs de tri.
Tout ce qui suit se trouve sous ``Extra Tools`` sauf mention contraire. Depuis la dernière version,
le menu est organisé en huit sous-menus groupés par fonction —
``Batch``, ``Library & Metadata``, ``Views``, ``Workflow``, ``Export``,
``Develop (Non-Destructive)``, ``Retouch & Transform`` et ``Multi-Image`` —
de sorte que chaque chemin ci-dessous est indiqué comme ``Extra Tools`` > ``<sous-menu>`` > ``<outil>``.

Recherche dans la bibliothèque
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` vous permet d'ajouter un ou plusieurs **dossiers racine**
à un index global parcouru en arrière-plan. Une fois une racine indexée, vous pouvez y chercher
par nom de fichier, largeur / hauteur minimales et taille de fichier (jusqu'à 2000 résultats) ;
double-cliquez sur un résultat pour l'ouvrir.

Clic droit > ``Search by Query…`` filtre le dossier courant avec un langage de requête compact, par exemple ``kw:beach rating:>=4 type:video place:Paris``. ``place:`` accepte une ville, un pays ou les deux (``Paris``, ``France``, ``Paris, France``) ; une valeur avec des espaces se met entre guillemets doubles (``place:"Rio de Janeiro"``).

Albums intelligents
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` persiste des règles de filtre (extensions, dimensions
minimales, étiquettes de couleur, note, favoris, état de tri, tags hiérarchiques,
sous-chaîne de nom) sous un nom convivial. Réappliquer un album filtre le dossier
actif selon les règles enregistrées.

Recherche d'images similaires
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` exécute un pHash DCT 64 bits sur
l'image Deep Zoom courante (ou la première vignette sélectionnée) et liste les correspondances proches
de l'index triées par distance de Hamming. Ajustez la valeur ``Max Hamming distance`` pour
élargir ou resserrer la maille.

Recherche sémantique (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Semantic Search`` vous permet de taper une phrase en langage naturel
(par exemple *"golden retriever in snow"* ou *"neon street at night"*) et
renvoie, classées, les images du dossier ouvert. Chaque image est encodée avec un
encodeur vision/langage CLIP et stockée à côté de son chemin ; une requête textuelle est
encodée dans le même espace vectoriel et comparée par similarité cosinus.

Les encodages sont mis en cache dans ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) ou ``~/.cache/imervue/clip_cache.npz`` (POSIX) sous forme d'une seule archive ``.npz`` compacte. La boîte de dialogue cherche dans le dossier ouvert : elle n'encode que les images absentes du cache ou modifiées depuis (taille ou date de modification), si bien qu'une nouvelle recherche dans le même dossier démarre aussitôt, et les résultats ne viennent que de ce dossier.

.. note::
   La recherche sémantique nécessite les paquets optionnels ``open_clip_torch`` et ``torch``.
   S'ils ne sont pas installés, l'entrée du menu explique ce qui manque et les autres fonctionnalités
   continuent de fonctionner.

Tag automatique
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` applique des tags heuristiques sous
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``graphic`` / ``landscape`` /
``portrait``), déduits de la saturation des couleurs, des contours et de la forme de l'image telle
que la visionneuse l'affiche. S'exécute sur un thread de travail avec une barre de progression en direct.

Tags hiérarchiques
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gère les tags structurés en arbre comme
``animal/cat/british``. Sélectionnez un tag pour voir chaque image sous cette branche
(descendants inclus). Marquez ou démarquez la sélection courante d'un clic.
Les tags hiérarchiques vivent dans l'index de la bibliothèque et sont complémentaires du système
de tags plat dans le menu contextuel.

Clic droit > ``Opérations par lots`` > ``Index Keywords`` (vignettes sélectionnées) ajoute
à la bibliothèque les mots-clés XMP de la sélection. Une hiérarchie de mots-clés écrite par Lightroom ou darktable
(``lr:hierarchicalSubject``, ``Places|Taiwan|Taipei``) est rangée sous le chemin de
tag ``Places/Taiwan/Taipei``, et les mots-clés isolés ``Places`` / ``Taiwan`` /
``Taipei`` qui ne font que répéter ses niveaux ne sont pas ajoutés une seconde fois.

Renommage par lots avec jetons
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` ouvre un tableau avec aperçu en direct dans lequel vous
saisissez un modèle comme ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` et voyez
exactement comment chaque fichier sera renommé. Les conflits sont mis en évidence afin que
rien ne soit écrasé. Jetons pris en charge : ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``. Un nouveau nom que porte actuellement un autre
fichier sélectionné n'est pas un conflit : renuméroter (``002`` → ``003`` pendant que
``003`` → ``004``) ou échanger deux noms renomme toute la sélection. Batch Rename fait
de même.

Export des métadonnées
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` écrit une ligne par image dans
la vue courante couvrant EXIF, dimensions, étiquette de couleur, note, favori,
tags hiérarchiques, état de tri et notes. Utile pour injecter les décisions de tri
dans un tableur ou un flux de travail externe.

Fichiers annexes XMP
^^^^^^^^^^^^^^^^^^^^

Imervue peut lire et écrire des fichiers annexes Adobe XMP (``photo.jpg`` ↔
``photo.xmp``) afin que les notes, titres, descriptions, mots-clés et étiquettes de
couleur fassent l'aller-retour proprement avec Adobe Bridge et d'autres gestionnaires
de photos compatibles XMP.

L'enregistrement fusionne avec le sidecar existant : seuls ces champs changent, les réglages de développement, le recadrage et l'historique d'un autre logiciel y sont conservés, et un sidecar illisible n'est jamais écrasé.

Outre ``photo.xmp`` (Lightroom, Bridge), le ``photo.jpg.xmp`` qu'écrivent
darktable et digiKam est lu et mis à jour lorsqu'il est le seul sidecar. Les
étiquettes de couleur sont comprises dans les mots de Lightroom (``Red`` …
``Purple``) et de Bridge (``Select``, ``Second``, ``Approved``, ``Review``,
``To Do``). Une couleur nouvelle ou modifiée est exportée comme Lightroom l'écrit ;
un sidecar qui contient déjà le mot de Bridge pour la même couleur garde ce mot.
Une étiquette sans couleur (personnalisée) reste dans le sidecar.

Une photo rejetée — ``xmp:Rating`` -1 dans Lightroom, Bridge et darktable — est
importée comme **Reject** du tri, sans étoiles, et un Reject est exporté en -1.
Un sidecar non rejeté lève un Reject ; un Pick reste tel quel.

Un fichier sans sidecar est lu — et importé — depuis ce qu'il embarque lui-même :
son paquet XMP (JPEG, PNG, WebP, TIFF, CR3, RW2, ORF, RAF), puis son ``Rating`` / ``RatingPercent``
EXIF. C'est là que Lightroom garde la note et les mots-clés d'un JPEG, et que
l'Explorateur Windows et certains appareils gardent leurs étoiles. Un sidecar,
s'il existe, l'emporte.

``Extra Tools`` > ``Library & Metadata`` > ``XMP Sidecars`` comporte deux boutons qui s'appliquent
à toutes les images de la vue courante :

- **Export sidecars** — écrit la note / le titre / la description / les mots-clés /
  l'étiquette de couleur de chaque image dans son fichier annexe.
- **Import sidecars** — les relit dans les enregistrements propres à Imervue.

L'analyse XML utilise ``defusedxml`` afin que des fichiers annexes malformés ou malveillants
ne puissent pas déclencher d'attaques XXE / billion-laughs.

La **barre latérale EXIF** expose également une **bande de notation par étoiles** cliquable —
la note qu'elle définit est ce que l'export XMP écrira.

Tri (Sélectionner / Rejeter)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Un indicateur de tri à trois états. Appuyez sur ``P`` pour sélectionner l'image
courante ou chaque vignette sélectionnée, ``Shift + X`` pour rejeter, ``U`` pour retirer le marquage. ``Filtre`` >
``Par état de tri`` n'affiche que les sélections, les rejets ou les non marqués. ``Extra Tools`` >
``Workflow`` > ``Culling`` applique le filtre via une boîte de dialogue et expose également un bouton **Delete all
rejects** qui supprime définitivement du disque les fichiers marqués.

Plateau de mise à disposition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` est un panier inter-dossiers. Ajoutez n'importe quel
ensemble de vignettes au plateau (la liste survit aux redémarrages), puis déplacez ou copiez tout le
plateau dans un dossier de destination en un clic. Utile pour rassembler des sélections de plusieurs
prises avant l'export.

Gestionnaire de fichiers à deux volets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` ouvre une vue à deux arbres
en deux volets. Choisissez un dossier dans chaque volet et déplacez/copiez la sélection
entre eux sans quitter Imervue.

Vue chronologique
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` regroupe l'ensemble d'images courant par jour,
mois ou année (groupé par date). La date est tirée de l'EXIF ``DateTimeOriginal``, puis de
``DateTimeDigitized``, puis de ``DateTime``, et sinon de l'heure de modification du fichier.
Double-cliquez sur une image pour l'ouvrir en Deep Zoom.

Glisser-déposer vers des applications externes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Appuyez et faites glisser depuis une vignette **sélectionnée** pour déposer le fichier dans Explorer,
Chrome, Discord ou toute application qui accepte les URL de fichiers. L'aperçu du glissement est la
vignette.

Notes par image
^^^^^^^^^^^^^^^

La barre latérale EXIF comprend une zone de texte libre **Notes**. La saisie est enregistrée
automatiquement dans l'index de la bibliothèque après un court délai. Les notes voyagent avec le chemin
de l'image, elles survivent donc aux ré-analyses de dossier.

----

Développement avancé et composition
-----------------------------------

Courbe tonale
^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` ouvre un éditeur de courbe à points déplaçables avec
quatre canaux (RGB, R, V, B). Clic gauche sur le canevas vide pour ajouter un point ;
glisser pour déplacer ; clic droit pour supprimer. Les points sont interpolés avec une
spline cubique monotone et stockés sur la recette de l'image, de sorte que la courbe s'applique
de manière non destructive au moment du rendu.

Appliquer un LUT .cube
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` vous permet de choisir n'importe quel fichier Adobe ``.cube``
(3D jusqu'à 65³, 1D jusqu'à 65 536 points). ``LUT_1D_INPUT_RANGE`` / ``LUT_3D_INPUT_RANGE``
de DaVinci Resolve fixe le domaine d'entrée comme ``DOMAIN_MIN`` / ``DOMAIN_MAX``,
et un fichier enregistré avec un BOM se charge aussi. Le LUT est analysé avec un ``lru_cache`` clé par
chemin + mtime, évalué par interpolation trilinéaire, et mélangé à l'original
via un curseur d'intensité. Le chemin du LUT et l'intensité vivent sur
la recette.

Copies virtuelles
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` donne à chaque image des instantanés
de recette nommés. Capturez l'édition courante, continuez à expérimenter, et revenez à
n'importe quelle variante antérieure plus tard. Les variantes se trouvent à côté de la recette
maître dans le magasin de recettes et survivent à la réinitialisation du maître à l'identité.

Fusion HDR
^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` combine deux expositions bracketées ou plus
en une seule image via la fusion d'exposition Mertens d'OpenCV. La case optionnelle
"Align exposures" exécute d'abord ``cv2.AlignMTB`` pour compenser un éventuel tremblement
à main levée. La sortie est enregistrée dans un fichier choisi par l'utilisateur — elle ne
touche à aucune image source.

Assemblage panoramique
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` enveloppe l'API de haut niveau
``Stitcher`` d'OpenCV. Choisissez le mode **Panorama** pour les paysages / panoramas urbains ou
le mode **Scans** pour les documents plats et les œuvres d'art. Les bords noirs produits par le
warp peuvent être recadrés automatiquement.

Empilement de focus
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` fusionne plusieurs prises à différentes
distances de mise au point. Pour chaque pixel, l'algorithme choisit la trame d'entrée qui présente la
plus haute netteté locale (variance laplacienne), puis lisse le masque de sélection avec un fondu
gaussien pour éviter les coutures. L'alignement ECC est activé par défaut pour les légers
décalages à main levée.

Pinceau de correction
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` affiche l'image courante jusqu'à
720 px sur le côté le plus long. Clic gauche pour ajouter un spot circulaire ; clic droit sur un
spot existant pour le retirer ; le curseur de rayon règle la taille des nouveaux spots. À l'application,
l'inpainting d'OpenCV (Telea pour la vitesse, Navier-Stokes pour un mélange plus doux)
remplit chaque région masquée à partir des pixels environnants et le résultat est enregistré
dans un nouveau fichier.

Correction d'objectif
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` expose quatre curseurs purement numpy :
distorsion radiale ``k1`` (en barillet / coussinet), correction du vignettage et
échelle radiale d'aberration chromatique par canal pour le rouge et le bleu. L'image
corrigée, de la même taille que l'original, est enregistrée dans un nouveau fichier.

Vue carte
^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` trace les images géolocalisées du dossier ouvert
sur une carte interactive Leaflet + OpenStreetMap, avec un marqueur par ville la plus proche
et le nombre de photos qui s'y trouvent (nécessite ``PySide6.QtWebEngineWidgets``). Sans
WebEngine, la boîte de dialogue se rabat sur une liste de ces lieux avec leur nombre de
photos et leurs coordonnées, afin que la fonctionnalité reste utilisable sur des
installations minimales.

Vue calendrier
^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` affiche un ``QCalendarWidget`` avec les jours
surlignés lorsque des photos ont été prises ce jour-là (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → ``DateTime`` → mtime du fichier). Sélectionner une date liste
ses images ; double-cliquez pour en ouvrir une dans la visionneuse principale.

Détection de visages
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` exécute la cascade de Haar pour visages
frontaux d'OpenCV sur l'image courante et dessine chaque détection comme un rectangle.
Double-cliquez sur une ligne de la liste pour saisir un nom de personne ; à l'enregistrement, les tags
sont écrits dans le blob ``extra['face_tags']`` de la recette. La détection est une
technique classique — la précision est adéquate pour "montre-moi les visages" mais
n'est pas un substitut à la reconnaissance moderne basée sur CNN.
Nécessite OpenCV 4 (``pip install "opencv-python<5"``) : OpenCV 5 a supprimé les cascades
de Haar, et le dialogue le signale alors au lieu de détecter.

Masques d'ajustement local
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` superpose des masques au pinceau,
radiaux ou en dégradé linéaire sur l'image. Chaque masque porte ses propres deltas d'exposition,
luminosité, contraste, saturation, température, teinte plus un curseur de contour progressif.
Les masques sont enregistrés dans ``recipe.extra['masks']`` et appliqués
de manière non destructive au chargement, de sorte que le fichier sous-jacent n'est jamais touché.

Virage partiel
^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` applique des teintes distinctes aux ombres et
aux hautes lumières avec une saturation par région et un pivot d'équilibre. Stocké sur
``recipe.extra['split_toning']`` et appliqué après la courbe tonale dans le
pipeline de développement.

Tampon de duplication
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` copie un patch source à bord adouci sur
une destination — le complément à bord dur du pinceau de correction. Shift+clic
définit la source, un clic normal tamponne, clic droit annule. Le résultat est
écrit dans un nouveau fichier afin que l'original reste intact.

Recadrage / Redressement
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` combine un rectangle de recadrage
normalisé (0..1) avec un angle de redressement allant jusqu'à ±15°. La sortie est
recadrée automatiquement au plus grand rectangle intérieur, afin que les photos ayant subi une rotation
n'aient pas de coins noirs.

Redressement automatique
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` détecte l'horizon ou les lignes
verticales dominantes via la détection de lignes de Hough et propose une rotation. Un
clic applique le redressement ; vous pouvez d'abord ajuster l'angle si la
détection automatique choisit la mauvaise référence.

Réduction du bruit / Accentuation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` applique un débruitage
bilatéral (préservant les bords) suivi d'une accentuation par masque flou.
"Luminance only" conserve le bruit de couleur intact mais aplatit le grain sans
brouiller les bords chromatiques.

Ciel / Arrière-plan
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` remplace le ciel détecté par un
dégradé ou supprime l'arrière-plan vers transparent / blanc. Lorsque
``rembg`` (U²-Net) est installé, le masque du premier plan provient du
réseau de segmentation ; sinon la règle HSV heuristique est utilisée.

Épreuvage écran
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` charge un profil ICC, convertit l'
image à travers lui puis en retour, et met en évidence en magenta les pixels qui ont clippé
durant l'aller-retour — une vérification rapide de hors gamut avant l'impression.

Effets tonaux et créatifs
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` rassemble un ensemble d'effets
ponctuels de type appliquer-et-enregistrer, chacun étant une fine boîte de
dialogue à curseurs au-dessus d'une transformation pure-NumPy (Frame & Caption
dessine avec Pillow ; la même logique est aussi exposée comme outil MCP) :

- **Graduated Density** — un dégradé de densité neutre linéaire défini par angle,
  dureté et décalage, éventuellement teinté ; assombrit un ciel ou un premier plan
  sans masque manuel.
- **Tone Equalizer** — exposition indépendante par zone de luminance (un curseur
  pour chaque plage, des noirs → aux blancs) sur un masque lissé, de sorte que
  l'ajustement suit les tons de la scène.
- **Detail Equalizer** — un curseur de gain par bande de fréquence (texture fine →
  contraste grossier), l'alternative multi-échelle à un simple curseur de clarté.
- **Filmic Tone Map** — une atténuation des hautes lumières Reinhard ou Hable avec
  contraste pivoté et restauration de la saturation, pour les prises uniques à fort
  contraste.
- **Velvia** — un boost de saturation pondéré par la luminance qui intensifie les
  couleurs ternes tout en épargnant celles déjà saturées et les ombres.
- **Film Negative** — inverse un négatif couleur numérisé en éliminant la base
  orange du film estimée automatiquement, avec un curseur de gamma de sortie.
- **Defringe** — désature les franges d'aberration chromatique violettes/vertes le
  long des bords à fort contraste, en laissant intacte la couleur uniforme.
- **Emboss** — un relief en lumière directionnelle à partir du champ de hauteur de
  luminance (azimut / élévation / profondeur + une bascule niveaux de gris).
- **Polar Coordinates** — enroule l'image en disque ou la déroule (l'effet planète
  miniature / inversion polaire).
- **Kaleidoscope** — réfléchit un secteur angulaire en symétrie d'ordre ``n``.
- **Frosted Glass** — une dispersion locale de pixels déterministe et reproductible
  par graine.
- **Frame & Caption** — une bordure passe-partout de n'importe quelle couleur, un
  bandeau inférieur plus épais façon Polaroid en option et une légende incrustée
  dans ce bandeau, dans sa propre couleur.

Géolocalisation GPS
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lit les tags GPS EXIF existants et
vous laisse modifier ou définir de nouvelles coordonnées en degrés décimaux. Un JPEG est écrit
sur place sans paquet supplémentaire : seul son bloc EXIF change, les pixels, les autres tags et
la vignette restent intacts. Un WebP est traité de la même façon ; les autres formats ne peuvent pas être géotagués.

L'**éditeur EXIF** (bouton ``Edit EXIF`` de la barre latérale EXIF) modifie la description, l'artiste, le copyright, la marque / le modèle de l'appareil et le commentaire. Un JPEG ou un WebP ne nécessite aucun paquet supplémentaire et seul son bloc EXIF est réécrit ; les autres formats indiquent pourquoi ils ne sont pas modifiables.

Galerie web
^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Web Gallery`` enregistre les images sélectionnées (ou tout le
dossier) sous forme de site autonome : ``index.html`` avec une lightbox, des vignettes JPEG et des
copies des originaux, sauf si vous décochez **Copier les originaux en pleine taille**. Vous
choisissez le titre de la page ainsi que la taille et la qualité des vignettes. Avec les originaux
copiés, la page n'a besoin d'aucun serveur : ouvrez-la depuis le disque ou déposez-la sur n'importe
quel hébergement statique. Sans eux, ses liens vers les images en pleine taille pointent vers les
photos de votre propre disque.

Cochez **Revue client** pour soumettre la galerie à l'avis de vos clients. Chaque image reçoit une
zone de commentaire ; les notes restent dans le navigateur du relecteur, et le bouton
**Export comments** de la page les enregistre toutes dans un seul fichier JSON.

Mise en page d'impression
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` compose plusieurs images sur un PDF
multi-pages avec taille de page, orientation, grille, marges, gouttière et traits de
coupe configurables. Nécessite ``reportlab``.

----

Utilisation en ligne de commande
--------------------------------

::

   imervue                        # Launch normally
   imervue /path/to/image         # Open a specific image
   imervue /path/to/folder        # Open a specific folder
   imervue --debug                # Enable debug mode
   imervue --software_opengl      # Use software rendering (when GPU is unsupported)

CLI de traitement par lots sans interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Imervue.cli`` exécute les opérations d'image pures depuis un shell **sans démarrer
Qt**, ce qui le rend utilisable depuis des scripts, des étapes de CI et des serveurs sans
affichage::

   py -m Imervue.cli resize photos/ --max 1600 --out web/
   py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
   py -m Imervue.cli info *.png --json
   py -m Imervue.cli list-ops          # affiche toutes les sous-commandes disponibles

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Sous-commande
     - Rôle
   * - ``info`` / ``stats``
     - Dimensions et format ; métriques de qualité sans référence (``--json`` pour une sortie exploitable par machine)
   * - ``convert`` / ``resize`` / ``thumbnail``
     - Conversion de format (``--format`` / ``--quality``), redimensionnement au grand côté maximal, boîte de vignette
   * - ``watermark`` / ``optimize``
     - Filigrane texte (``--text`` / ``--corner`` / ``--opacity``) ; encoder sous un budget ``--max-kb``
   * - ``dehaze`` / ``clahe`` / ``dither`` / ``distort``
     - Défloutage par canal sombre, égalisation adaptative, tramage Bayer ordonné, swirl / pinch / ripple
   * - ``auto-orient`` / ``strip``
     - Appliquer l'orientation EXIF aux pixels ; réenregistrer sans EXIF / XMP / ICC
   * - ``collage`` / ``anaglyph``
     - Montage en grille (``--columns``) ; 3D rouge-cyan à partir d'une paire stéréo (``--method``)
   * - ``preset`` / ``pipeline``
     - Appliquer un préréglage de développement enregistré par son nom ; exécuter un pipeline JSON ordonné
   * - ``list-ops``
     - Lister toutes les sous-commandes (``--json`` pour une sortie exploitable par machine)

Chaque sous-commande décode comme la visionneuse : les sorties sont redressées selon l'orientation EXIF et converties en sRGB depuis le profil couleur intégré, les entrées AVIF sont lues par Pillow lui-même, et les entrées HEIC / JPEG XL lorsque leur backend optionnel est installé. Un RAW d'appareil photo est développé comme dans la visionneuse au lieu d'être lu comme sa petite vignette intégrée ; ``resize`` et ``strip`` l'écrivent en PNG. Un fichier illisible est signalé et les autres sont tout de même traités. Un fichier tronqué est lu aussi loin qu'il va, comme dans la visionneuse. Les niveaux de gris 16 bits et à virgule flottante sont ramenés à 8 bits comme dans la visionneuse ; ``resize`` et ``strip`` gardent la profondeur de bits de la source.

Les sous-commandes qui prennent des fichiers ou des dossiers (toutes sauf ``collage``, ``anaglyph`` et ``list-ops``) partagent ``--out`` (répertoire de sortie), ``--recursive``, ``--dry-run`` (lister les actions sans rien écrire), ``--overwrite`` et ``-j`` / ``--jobs`` (workers parallèles ; ``0`` utilise tous les cœurs). ``collage`` et ``anaglyph`` écrivent l'unique fichier désigné par ``--out``. ``--version`` affiche la version de la CLI.

----

Serveur MCP
-----------

Imervue intègre un serveur `Model Context Protocol <https://modelcontextprotocol.io>`_
qui permet aux assistants IA (Claude Code, Claude Desktop, Cursor,
Cline, …) d'appeler les fonctions auxiliaires de logique pure du projet sans
interface graphique en cours d'exécution. Démarrez-le avec ::

   python -m Imervue.mcp_server

Le serveur n'a pas besoin de Qt et ne charge que ce dont chaque outil a besoin au moment
de l'appel.

Outils disponibles
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Outil
     - Rôle
   * - ``list_images``
     - Liste les fichiers image d'un dossier (chemin, taille, mtime). Passez
       ``recursive=true`` pour parcourir les sous-dossiers.
   * - ``read_image_metadata``
     - Dimensions, format, tags EXIF et champs XMP (sidecar, sinon embarqués) pour une
       image. Les données manquantes sont rapportées comme la valeur vide appropriée
       plutôt que de lever une exception.
   * - ``read_xmp_tags``
     - Chemin rapide qui ne lit que le XMP (sidecar, sinon embarqué) — note, étiquette
       de couleur, mots-clés, titre, description.
   * - ``convert_format``
     - Convertit une image vers un autre format. Le format de destination est
       déduit du suffixe de destination (``png`` / ``jpg`` /
       ``jpeg`` / ``webp`` / ``tiff`` / ``bmp`` / ``avif``, plus ``heic`` /
       ``jxl`` lorsque leur backend optionnel est installé). L'option
       ``quality`` (1–100) s'applique à JPEG / WebP / AVIF / HEIC / JXL.
   * - ``puppet_from_png``
     - Construit un rig ``.puppet`` à partir d'un PNG en utilisant l'auto-mesh
       du plugin Puppet. Ensemence le catalogue de paramètres standard Cubism afin
       que le rig soit immédiatement pilotable.
   * - ``puppet_inspect``
     - Ouvre une archive ``.puppet`` et renvoie un inventaire structuré :
       drawables, déformateurs, paramètres, mouvements, expressions, zones de
       contact, parties, mélanges de paramètres et rigs physiques.
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - Moyenne/min/max/écart-type/médiane par canal, métriques de qualité sans
       référence (colorimétrie, entropie, contraste, densité de bords, bruit),
       et l'histogramme à 256 classes avec fractions d'écrêtage sur/sous-exposé.
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Score de flou par variance laplacienne, texte OCR Tesseract (dégradation
       propre en son absence), et un aperçu PNG base64 borné.
   * - ``find_similar``
     - Regroupe les images quasi-doublons par hachage perceptuel (seuil de
       Hamming). Rapporte la progression par fichier lorsqu'un jeton de
       progression est fourni.
   * - ``apply_watermark`` / ``apply_frame``
     - Incruster un filigrane texte, ou encadrer l'image dans un passe-partout /
       cadre Polaroid avec une légende optionnelle.
   * - ``build_collage``
     - Compose plusieurs images en une mosaïque en grille (colonnes, taille de
       cellule, espacement, marge, arrière-plan configurables). Rapporte la progression.
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - Recadrage en boîte de pixels, redimensionnement (un seul côté conserve le rapport
       d'aspect, les deux donnent une taille exacte), et
       rotation 90/180/270 sans perte ou retournement horizontal/vertical.
       Les tailles et coordonnées se rapportent à l'image redressée selon l'EXIF.
   * - ``collection_stats``
     - Synthétise les notes, favoris, étiquettes de couleur et états de tri d'un
       dossier (comptes, distribution 0–5 étoiles et moyenne).
   * - ``reverse_geocode`` / ``extract_video_frame``
     - Résout des coordonnées GPS vers la ville la plus proche hors ligne, et
       décode une image d'une vidéo en photo fixe.
   * - ``extract_gps`` / ``dominant_colors``
     - Lit la latitude/longitude GPS de l'EXIF (s'enchaîne avec ``reverse_geocode``) ;
       extrait une palette de couleurs par coupe médiane (rgb / hex / nombre de pixels).
   * - ``error_level_analysis``
     - Carte de falsification par Error-Level-Analysis (recompression JPEG) sous forme
       d'URI de données PNG (les zones retouchées ressortent sur le fond).
   * - ``search_images``
     - Filtre un dossier avec le DSL de requêtes des albums intelligents (extension / nom /
       taille / dimensions / rapport d'aspect / appareil EXIF / objectif / lieu).
   * - ``solarize_image`` / ``glow_image``
     - Applique une inversion tonale de solarisation ou une lueur diffuse / un bloom Orton,
       puis enregistre le résultat.
   * - ``velvia_image`` / ``emboss_image`` / ``defringe_image``
     - Renforcement de saturation Velvia pondéré par la luminance, relief en estampage à
       lumière directionnelle, et désaturation des franges violettes/vertes sur les bords.
   * - ``film_negative_image`` / ``graduated_density_image``
     - Inverse un négatif couleur numérisé (base du film automatique) et applique un
       dégradé linéaire de densité neutre graduée.
   * - ``filmic_tonemap_image`` / ``tone_equalizer_image`` / ``detail_equalizer_image``
     - Atténuation filmique des hautes lumières Reinhard/Hable, exposition par zone de
       luminance et contraste par bande de fréquences.
   * - ``colormap_image`` / ``false_color_image``
     - Recolore la luminance à travers une palette perceptuelle viridis/magma/jet, ou la
       projette sur une échelle d'exposition en fausses couleurs.
   * - ``dither_image`` / ``split_toning_image`` / ``pixel_sort_image``
     - Tramage ordonné (Bayer) sur quelques tons par canal, virage partiel ombres/hautes
       lumières, et tri de pixels par bandes de luminosité.
   * - ``polar_image`` / ``kaleidoscope_image``
     - Passe des coordonnées rectangulaires aux coordonnées polaires et inversement
       (petite planète), ou reflète le cadre en un nombre de secteurs de kaléidoscope.
   * - ``frosted_glass_image`` / ``clahe_image`` / ``local_contrast_image``
     - Diffusion en verre dépoli par voisins aléatoires, égalisation adaptative
       d'histogramme à contraste limité, et clarté des tons moyens + texture de détail fin.
   * - ``posterize_image`` / ``gradient_map_image``
     - Quantifie chaque canal en quelques aplats, ou remappe la luminance à travers un
       dégradé du noir au blanc mélangé selon l'intensité.
   * - ``film_grain_image`` / ``dehaze_image`` / ``distort_image``
     - Grain argentique gaussien réglable, suppression du voile par dark channel prior,
       et distorsion géométrique tourbillon / pincement / ondulation.
   * - ``levels_image`` / ``curve_image``
     - Niveaux point noir/blanc et gamma, et un préréglage de courbe tonale principale
       (courbe en S, déboucher les ombres, compresser les hautes lumières).
   * - ``auto_color_balance_image`` / ``channel_mixer_image``
     - Balance des blancs automatique (gray-world, white-patch, étirement par centile,
       retinex) et un mélangeur de canaux 3x3 avec conversion monochrome.
   * - ``lens_correction_image``
     - Corrige la distorsion en barillet/coussinet (k1), éclaircit ou accentue le
       vignetage des coins, et annule l'aberration chromatique rouge/bleu.

Chaque outil annonce un ``outputSchema`` JSON et des ``annotations`` lecture seule /
destructrices, et retourne son résultat sous forme de ``structuredContent`` aux côtés
de l'enveloppe texte (selon MCP 2025-11-25), afin que les clients consomment des charges
typées sans réanalyse. Les outils de longue durée diffusent ``notifications/progress``
lorsque l'appelant fournit un jeton de progression.

Prompts
^^^^^^^

Le serveur expose quatre prompts via ``prompts/list`` / ``prompts/get`` :
``caption_image``, ``suggest_edits``, ``analyze_composition`` (une critique de
composition pilotée par la saillance) et ``flag_issues`` (un triage netteté
+ qualité + écrêtage). ``completion/complete`` suggère des valeurs pour le ``style``
de ``suggest_edits`` et le ``focus`` de ``analyze_composition``.

Claude Code (niveau projet)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Le dépôt fournit un ``.mcp.json`` au niveau projet à la racine du dépôt :

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

L'ouverture de n'importe quel sous-répertoire du dépôt dans Claude Code détecte
automatiquement ce serveur. Claude Code demande confirmation avant d'activer les
serveurs de projet la première fois — acceptez l'invite pour l'utiliser.

Claude Desktop
^^^^^^^^^^^^^^

Ajoutez la même entrée à votre configuration Claude Desktop :

* macOS : ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows : ``%APPDATA%\Claude\claude_desktop_config.json``

Utilisez un répertoire de travail absolu ou activez un virtualenv dans lequel
Imervue est installé ; l'invocation ``python`` doit se résoudre vers un
interpréteur capable d'exécuter ``import Imervue``.

Surface du protocole
^^^^^^^^^^^^^^^^^^^^

Le serveur implémente le transport JSON-RPC 2.0 stdio de MCP
version ``2025-03-26`` :

* ``initialize`` — poignée de main ; annonce ``capabilities.tools``.
* ``tools/list`` — énumère les outils enregistrés avec leurs
  définitions d'entrée JSON-Schema.
* ``tools/call`` — invoque un outil avec ``{"name", "arguments"}`` ;
  les résultats reviennent dans le tableau ``content``.
* ``notifications/*`` — silencieusement acceptés (pas de réponse).

L'implémentation se trouve dans ``Imervue/mcp_server/`` :

* ``server.py`` — boucle de protocole + registre des outils.
* ``tools.py`` — fonctions de gestion et définitions d'outils par défaut.
* ``__main__.py`` — point d'entrée ``python -m Imervue.mcp_server``.

Des outils personnalisés peuvent être enregistrés en construisant :class:`MCPServer`
manuellement, en appelant :meth:`MCPServer.register`, et en alimentant les
messages via :meth:`MCPServer.handle_message` (ou en pilotant la boucle stdio
avec l'aide intégrée :func:`run`).
