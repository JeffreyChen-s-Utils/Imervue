Guide de l'utilisateur Imervue
==============================

Station de travail d'image accélérée par GPU offrant **quatre onglets principaux**.
La majeure partie de ce guide est organisée autour de ces quatre sections.

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
       outils manga, E/S PSD. Voir *Onglet Paint — Éditeur matriciel complet*.
   * - **Puppet**
     - Animateur de marionnettes 2D riggées conçu de zéro — maillages, déformateurs,
       paramètres, mouvements, physique. Voir *Onglet Puppet — Animation 2D riggée*.

Les sections *Pour démarrer*, *Référence*, *Système de plugins* et *Serveur MCP*
qui suivent sont transversales — elles s'appliquent à l'ensemble des quatre onglets.

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
- **Droite** : barre latérale EXIF. Affiche les informations de prise de vue de l'image sélectionnée.

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
     - ``Fichier`` > ``Ouvrir une image``, puis choisissez un fichier
   * - Glisser-déposer
     - Faites glisser une image ou un dossier directement dans la fenêtre
   * - Ouvrir depuis l'Explorateur
     - Clic droit sur une image > ``Open with Imervue`` (association de fichiers requise)
   * - Fichiers récents
     - ``Fichier`` > ``Récents``, pour rouvrir rapidement un dossier précédemment visité

Formats pris en charge
^^^^^^^^^^^^^^^^^^^^^^

- **Standards** : PNG, JPEG, BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW** : CR2 (Canon), NEF (Nikon), ARW (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus)

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
   * - Panoramique au clavier
     - Touches fléchées ; ``Shift`` pour un mouvement fin

Chaque vignette affiche des badges de statut : une bande colorée sur le bord gauche (étiquette de couleur),
un cœur en haut à gauche (favori), une étoile en haut à droite (signet) et des étoiles de notation
en bas à gauche. Un indicateur rotatif fait office d'espace réservé pour les vignettes en cours de chargement.

Mode liste (détails)
^^^^^^^^^^^^^^^^^^^^

Appuyez sur ``Ctrl + L`` pour basculer entre la grille de vignettes et une vue liste triable avec les colonnes :
Aperçu · Étiquette · Nom · Résolution · Taille · Type · Modifié. Double-cliquez sur une ligne (ou appuyez sur ``Enter``) pour entrer
en Deep Zoom ; appuyez sur ``Esc`` pour revenir à la liste. Les vignettes et les métadonnées sont chargées paresseusement sur un fil d'exécution
de travail, afin que les très grands dossiers restent réactifs.

Mode Deep Zoom
^^^^^^^^^^^^^^

Cliquez sur une vignette pour passer en mode Deep Zoom et obtenir un affichage de haute qualité d'une seule image.

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
     - ``Shift + P`` — à ≥ 400 % de zoom, superpose une grille de pixels et affiche les valeurs RGB / HEX sous le curseur
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

En mode Deep Zoom, vous pouvez noter rapidement les images :

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

Marqueurs de couleur indépendants, stockés séparément de la notation 1 -- 5 étoiles. Utiles pour
une catégorisation rapide (par ex. rouge = à rejeter, vert = à conserver, bleu = à retoucher).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Touche
   * - Rouge / Jaune / Vert / Bleu / Violet
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (appuyer à nouveau pour effacer)
   * - Appliquer par lot à la sélection
     - Sélectionnez plusieurs vignettes, puis appuyez sur la touche F correspondante
   * - Filtrer par couleur
     - ``Filtre`` > ``Par étiquette de couleur`` > choisir une couleur / N'importe quelle étiquette / Aucune étiquette

La barre d'état affiche une pastille colorée pour l'image courante. Les vignettes affichent une bande colorée sur
le bord gauche. La **vue Liste** dispose de colonnes dédiées **Étiquette** et **Notation** que vous pouvez
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
     - Clic droit sur l'image > ``Ajouter au tag``
   * - Ajouter à un album
     - Clic droit sur l'image > ``Ajouter à l'album``
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
   * - Trier par nom
     - ``Trier`` > ``Par nom``
   * - Trier par date de modification
     - ``Trier`` > ``Par date de modification``
   * - Trier par taille de fichier
     - ``Trier`` > ``Par taille de fichier``
   * - Trier par résolution
     - ``Trier`` > ``Par résolution``
   * - Croissant / Décroissant
     - ``Trier`` > ``Croissant`` / ``Décroissant``
   * - Filtrer par extension
     - ``Filtre`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
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
Vous pouvez également appuyer sur ``E`` ou faire un clic droit > ``Modify`` en mode Deep Zoom.

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
   * - Ombres
     - Relevez ou écrasez les détails dans les zones tonales sombres
   * - Tons moyens
     - Ajustez la plage tonale médiane sans affecter les noirs et les blancs
   * - Hautes lumières
     - Récupérez les hautes lumières brûlées ou poussez davantage les zones claires
   * - Vibrance
     - Renforcement intelligent de la saturation — protège les tons chair et les couleurs déjà saturées

Ces ajustements sont **non destructifs**. Chaque curseur écrit dans une recette d'édition stockée
par image ; appuyez sur ``Réinitialiser`` à tout moment pour restaurer l'original, ou sur ``Ctrl + Z`` pour reculer
parmi les modifications individuelles. Les recettes survivent aux redémarrages et peuvent être exportées / synchronisées
via le flux de fichiers annexes XMP décrit dans la section Métadonnées.

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
clés d'animation, et import/export PSD. Basculez-y depuis la barre d'onglets ou appuyez sur ``E``
depuis le mode Deep Zoom pour envoyer l'image courante directement dans un nouvel onglet Paint.

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
   | Outils|                     | Couleur · Brush|
   | Bar  |   Canevas (peinture) | Calque · Nav.  |
   |      |                      | Matériaux · …  |
   +------+----------------------+----------------+

Les docks de droite (Couleur, Pinceau, Calque, Navigateur, Bibliothèque de matériaux,
Historique, Échantillons, Référence, Histogramme, Animation) sont regroupés en onglets dans
une colonne unique afin que le canevas conserve toute la hauteur visible. Faites glisser
n'importe quel titre de dock pour réorganiser ou détacher un panneau, puis enregistrez le
résultat via ``Paramètres`` > ``Dispositions d'espace de travail…``.

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
     - Éditeur de texte en ligne avec police / taille / gras / italique
   * - Dégradé
     - ``U``
     - Remplissage par dégradé Linéaire / Radial / Angulaire / Diamant
   * - Flou / Doigt
     - ``R``
     - Manipulation locale des pixels
   * - Plume (Bézier)
     - ``P``
     - Tracé vectoriel avec édition des ancres et poignées
   * - Tampon de duplication
     - ``S``
     - Shift+clic définit la source, clic tamponne avec adoucissement
   * - Bulle de dialogue
     - ``Ctrl + B``
     - Bulle BD / manga avec queue automatique
   * - Rectangle / Ellipse / Ligne / Polygone
     - ``Shift + R/E/I/P``
     - Primitives de forme vectorielle avec contour + remplissage
   * - Recadrage
     - ``C``
     - Recadrage interactif avec préréglages de format
   * - Transformation
     - ``Ctrl + T``
     - Poignées de transformation libre / mise à l'échelle / rotation / inclinaison
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
   * - Stylo
     - Trait net avec anti-crénelage, pinceau du quotidien
   * - Marqueur / Surligneur
     - Traits larges et semi-transparents qui se superposent
   * - Crayon
     - Trait fin de graphite, légèrement texturé
   * - Aérographe
     - Points dispersés pilotés par la densité et le flux
   * - Calligraphie
     - La largeur varie selon la direction du trait
   * - Aquarelle
     - Diffusion à bords humides et fusion douce
   * - Fusain / Pastel gras
     - Traits texturés et rugueux avec inclinaison sensible à la pression

Chaque pinceau expose Taille / Opacité / Dureté / Densité / Mode de fusion dans
le **dock Pinceau** et la **barre d'options** supérieure. Utilisez ``Paramètres`` >
``Courbe de pression…`` pour remapper la pression de la tablette vers la largeur ou l'opacité, et
``Édition`` > ``Capturer une pointe de pinceau…`` pour transformer une sélection en rectangle en pointe
de pinceau personnalisée.

Calques
^^^^^^^

Le **dock Calque** offre des vignettes, des bascules de visibilité, un renommage en ligne,
un glisser-déposer pour réorganiser, ainsi que le mode de fusion + l'opacité du calque actif. Le
menu ``Calque`` ajoute :

- **Nouveau / Vectoriel / Dupliquer / Fusionner avec le calque inférieur** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Masques** — Ajouter un masque / Depuis la sélection / Inverser / Appliquer / Supprimer
  (``Ctrl + Shift + M`` ajoute ; ``Ctrl + Alt + Shift + M`` ajoute depuis la sélection)
- **Masque d'écrêtage** — découper le calque au-dessus sur l'alpha courant
  (``Ctrl + Alt + G``)
- **Effets de calque** — Ombre portée · Lueur externe · Contour ; effacer les effets
- **Calque de référence** — épingler un calque comme source de la pipette
- **Calque 1-bit** — basculer le calque actif en calque d'art au trait binaire
- **Diviser le calque par couleur** — séparer un calque de couleurs plates en un calque
  par couleur pour des re-remplissages au pot faciles
- **Mappage de dégradé** — sous-menu de préréglages (sépia / coucher de soleil / cyanotype …)

Sélections
^^^^^^^^^^

Utilisez les outils rectangle / lasso / baguette / sélection rapide, puis l'entrée du menu **Édition**
**Contour de la sélection…** pour tracer la sélection avec le pinceau actif.
``Q`` bascule le **mode masque rapide** — peignez avec n'importe quel pinceau pour affiner
le bord de la sélection en rouge, puis appuyez à nouveau sur ``Q`` pour reconvertir en
sélection rectangulaire.

Animation
^^^^^^^^^

Le **dock Animation** transforme le document en bande d'images :

- ``Ajouter une image`` capture l'état courant des calques dans une nouvelle image clé.
- Cliquez sur la vignette d'une image pour y sauter.
- ``Pelure d'oignon`` (menu Affichage) superpose les images voisines à faible alpha.
- Exportez la bande via **Fichier > Exporter les pages** (CBZ pour les lecteurs de BD,
  PDF pour l'impression) ou **Exporter l'animation** pour MP4 / GIF.

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
   * - Outil bulle de dialogue
     - Faites glisser une bulle, déposez la queue vers le locuteur

Filtres
^^^^^^^

``Filtre`` ouvre une boîte de dialogue avec aperçu en direct pour chaque effet :

- **Niveaux** — curseurs noir / gamma / blanc, par canal
- **Courbes** — points déplaçables (RGB / R / V / B) avec interpolation cubique monotone
- **Postérisation** — quantifier la couleur en N paliers
- **Seuil** — convertir en noir / blanc pur selon un seuil
- **Balance des couleurs automatique** — neutraliser les dominantes via grey-world / white-patch
- **Grain de film** — bruit de luminance avec taille et quantité réglables
- **Convertir en demi-teintes** — trame de points de style journal

Aides à la visualisation
^^^^^^^^^^^^^^^^^^^^^^^^

- **Grille de pixels** (``Ctrl + Shift + '``) — superpose une grille d'un pixel à fort zoom
- **Aligner sur les pixels / bords** — placement sous-pixel ramené à des coordonnées entières
- **Pelure d'oignon** — superposition des images voisines d'animation
- **Guides de fond perdu** — guides de fond perdu / zone sûre pour l'impression
- **Rotation du canevas** (``Ctrl + Shift + H``) — rotation de la vue sans rasterisation

E/S de fichiers
^^^^^^^^^^^^^^^

- **Ouvrir PSD…** (``Ctrl + O``) et **Enregistrer sous PSD…** (``Ctrl + S``) — aller-retour Photoshop multicalque avec masques, modes de fusion et effets de calque
- **Exporter l'image…** — aplatir et enregistrer en PNG / JPEG / WebP / BMP / TIFF
- **Exporter les pages → CBZ** / **→ PDF** — export de documents multi-images pour BD
- **Importer / exporter les préréglages de pinceau**, **Importer une palette** — partager les ressources entre installations
- **Instantanés d'enregistrement automatique** — instantanés périodiques en arrière-plan avec restauration du dernier depuis le menu Fichier

Dispositions d'espace de travail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Paramètres`` > ``Dispositions d'espace de travail…`` enregistre la disposition des docks,
l'état des options d'outil et les panneaux actifs sous un nom, puis bascule entre eux en un
clic — par exemple, une disposition "Dessin" avec les docks Pinceau + Couleur en évidence
et une disposition "Composition" avec les docks Calque + Historique développés.

----

Espace de travail Puppet (onglet Puppet)
----------------------------------------

Le quatrième onglet principal — **Puppet** — est un système d'animation de marionnettes
2D riggées conçu de zéro. Il fait ce que fait Live2D (rigs par déformation de maillage,
paramètres, mouvements, physique, expressions, groupes de poses, lip-sync, suivi par
webcam) mais **sans SDK propriétaire**, **sans `live2d-py`**, et avec un format de fichier
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

1. **Importer un PNG** — depuis la barre d'outils, ``Importer PNG…`` exécute
   ``puppet.auto_mesh.puppet_from_png`` : grille triangulée bornée par l'alpha,
   un drawable, prêt à rendre.
2. **Ajouter un déformateur** — ``Ajouter un déformateur de rotation`` (ancre + angle) ou
   ``Ajouter un déformateur de déformation`` (treillis Bézier lignes × colonnes ; les sommets
   hors limites traversent sans changement).
3. **Ajouter un paramètre** — ``Ajouter un paramètre`` ajoute un curseur au dock
   **Paramètres** à droite, avec un identifiant nommé automatiquement (``Param1``, ``Param2``, …).
4. **Définir des clés** — faites glisser le curseur vers un extrême, modifiez la forme du déformateur
   par code ou via l'édition du maillage, appuyez sur **Définir une clé**. Répétez au neutre et à l'extrême
   opposé. L'exécution interpolera désormais les champs du déformateur entre les clés adjacentes
   chaque fois que le curseur bouge.
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
le pilote sans configuration par rig. Neuf mouvements en boucle sont livrés
dans le pack — boucles d'inactivité Cubism converties par l'auteur, plus des boucles
de gestes de référence dans les groupes ``Idle`` et ``TapHead``.

Ouvrez l'onglet Puppet, cliquez sur **Ouvrir Puppet…**, pointez vers
``march_7th.puppet`` — la figure apparaît centrée. Faites glisser n'importe quel curseur
de paramètre pour piloter une articulation, ou cliquez sur l'un des mouvements dans le dock
Mouvements — un simple clic associe le mouvement et démarre immédiatement la lecture.

**Exécuter l'exemple fourni, étape par étape :**

1. Lancez Imervue. Depuis les sources : ``python -m Imervue``. Depuis la
   build empaquetée : exécutez l'exécutable / bundle d'application ``Imervue``. Le
   répertoire ``examples/`` est intégré à la fois dans le wheel et l'EXE Nuitka,
   donc le rig est présent sur le disque là où vous l'avez installé.
2. Cliquez sur l'onglet **Puppet** en haut de la fenêtre.
3. Barre d'outils → **File > Examples > March 7Th** (ou la liste déroulante
   **Examples ▾** de la barre d'outils). Le rig de 307 drawables se charge centré et
   le dock des paramètres se remplit des 203 curseurs standard Cubism.
4. Dans le dock **Mouvements** en bas, simple-clic sur n'importe quelle entrée de mouvement
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …).
   La lecture démarre immédiatement ; cliquez à nouveau pour arrêter, ou choisissez
   un autre mouvement pour faire un fondu enchaîné vers lui.
5. Basculez les interrupteurs d'entrée en direct sur la barre d'outils pour piloter le rig
   depuis vos propres entrées — **Drag-track head** pour le regard vers le curseur,
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

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Rôle
   * - Open Puppet… / Examples ▾
     - Charger un ``.puppet`` depuis le disque, ou choisir l'un des rigs
       fournis dans ``examples/puppet/`` directement depuis la barre d'outils
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
     - Construit le rig depuis la barre d'outils
   * - Drag-track head
     - Décalage du curseur → ``ParamAngleX`` / ``ParamAngleY`` +
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
     - Capture les changements de paramètres dans un nouveau ``Motion`` et l'ajoute au
       document — cuisson à partir d'une prise, sans création manuelle d'images clés
   * - Capture frame… / Record… / Export all motions…
     - Enregistrer un PNG, basculer un enregistrement GIF / WebM / MP4, ou
       rendre par lots chaque mouvement du rig dans son propre fichier (le tout via
       le même chemin de rendu hors écran "personnage seul" utilisé pour le streaming)
   * - Output > Virtual camera / NDI output
     - Surfaces de streaming en direct — voir *Streaming en direct vers OBS* ci-dessus
   * - Reset to rest
     - Arrête net le lecteur de mouvement, désactive tous les pilotes en direct,
       efface les expressions / groupes de pose, restaure les paramètres par défaut
   * - Fit to Window
     - Recentre et redimensionne la marionnette dans le canevas

Enregistrer ses propres mouvements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pour capturer une prise personnalisée plutôt que de créer les images clés à la main :

1. Basculez **Record motion** dans la barre d'outils — une boîte de dialogue de nom apparaît.
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
La barre d'outils **Output > Virtual camera** ouvre le flux.

DirectShow / AVFoundation / v4l2loopback sont uniquement RGB — pas de canal alpha —
donc Imervue remplit la zone hors du personnage avec
**magenta `#FF00FF`** comme clé chromatique. Retirez-la dans OBS via le
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
La barre d'outils **Output > NDI output** diffuse la source (nom par défaut
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

Le plugin se dégrade gracieusement lorsque l'une de ces dépendances est absente — la
bascule correspondante dans la barre d'outils revient automatiquement et affiche un
indice "install <package>". ``File > Install dependencies…`` installe par lot
chaque paquet Python optionnel en une seule fois.

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
     - Clic droit > Modify > Rotate CW
   * - Rotation 90 ° antihoraire
     - ``Shift + R``
     - Clic droit > Modify > Rotate CCW
   * - Retournement horizontal
     - --
     - Clic droit > Modify > Flip Horizontal
   * - Retournement vertical
     - --
     - Clic droit > Modify > Flip Vertical
   * - Rotation sans perte (JPEG)
     - --
     - Clic droit > Lossless Rotate

----

Exporter des images
-------------------

Export individuel
^^^^^^^^^^^^^^^^^

Clic droit sur une image > ``Exporter / Enregistrer sous``.

- Choisissez le format : PNG, JPEG, WebP, BMP, TIFF
- Ajustez la qualité (pour les formats avec perte)
- Aperçu de la taille de fichier estimée
- Choisissez un emplacement d'enregistrement

Préréglages d'export
^^^^^^^^^^^^^^^^^^^^

Pour les cibles de livraison courantes que vous ne souhaitez pas re-régler à chaque fois, utilisez
``Fichier`` > ``Exporter avec préréglage``. Un clic applique le bon pipeline de redimensionnement, format
et qualité :

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Préréglage
     - Pipeline
   * - **Web 1600**
     - Ajuste le côté le plus long à 1600 px, JPEG qualité 85, sRGB ; pour les téléversements sur blog / forum où la qualité visuelle compte plus que le nombre de pixels.
   * - **Print 300 dpi**
     - TIFF pleine résolution / JPEG haute qualité avec métadonnées 300 dpi, sortie gérée en couleur pour les labos et imprimeurs.
   * - **Instagram 1080**
     - Recadrage carré (1080 × 1080) ou portrait (1080 × 1350), ratio d'aspect original préservé à l'intérieur, JPEG qualité 90.

Les préréglages se composent avec la superposition filigrane (ci-dessous) — activez le filigrane une fois et
chaque sortie de préréglage le contient.

Superposition de filigrane
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Fichier`` > ``Filigrane…`` ouvre un configurateur de superposition non destructif. Les paramètres
s'appliquent uniquement à l'export — les pixels originaux sur le disque ne sont jamais touchés.

- **Mode** : texte ou image. Les filigranes image prennent en charge le PNG avec alpha.
- **Position** : grille à 9 ancres (coins, bords, centre).
- **Opacité** : 0 – 100 %.
- **Échelle** : pourcentage du côté long exporté ; le filigrane se redimensionne automatiquement
  lorsque vous redimensionnez pour différents préréglages.

Export par lots
^^^^^^^^^^^^^^^

Sélectionnez plusieurs images, puis clic droit > ``Export par lots``.

- Conversion de format uniforme
- Définir largeur / hauteur maximales (mise à l'échelle automatique du ratio d'aspect)
- Contrôle de la qualité
- Barre de progression en temps réel

Créer un GIF / une vidéo
^^^^^^^^^^^^^^^^^^^^^^^^

Sélectionnez plusieurs images, puis clic droit > ``Créer GIF / Vidéo``.

- Sortie GIF et MP4
- Glisser pour réordonner les images
- Définir les images par seconde (FPS)
- Dimensions personnalisées
- Option de boucle

----

Lecture d'animations
--------------------

À l'ouverture de fichiers GIF, APNG ou WebP animés, l'animation se lit automatiquement.

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

En mode vignettes, sélectionnez 2 -- 4 images, puis clic droit > ``Comparer les images``.

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
     - ``Fichier`` > ``Coller depuis le presse-papiers``, ou ``Ctrl + V``
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
     - Sélectionner plusieurs, puis ``Delete`` ou clic droit > ``Supprimer la sélection``

Les images sont déplacées vers la Corbeille du système et peuvent y être récupérées.

----

Opérations par lots
-------------------

En mode vignettes, sélectionnez plusieurs images puis clic droit :

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
   * - Ajouter au tag
     - Appliquer le même tag à toutes les images sélectionnées
   * - Ajouter à un album
     - Placer toutes les images sélectionnées dans un album

----

Histogramme RGB
---------------

Appuyez sur ``H`` en mode Deep Zoom pour superposer un histogramme RGB sur l'image. Appuyez à nouveau pour masquer.

----

Définir comme fond d'écran
--------------------------

Clic droit en mode Deep Zoom > ``Définir comme fond d'écran`` pour définir l'image courante comme fond d'écran du bureau.

Pris en charge sur Windows, macOS et Linux (GNOME).

----

Multi-fenêtres
--------------

``Fichier`` > ``Nouvelle fenêtre`` ouvre une autre fenêtre Imervue indépendante. Chaque fenêtre peut parcourir un dossier différent.

Préréglages de disposition d'espace de travail
----------------------------------------------

``Fichier`` > ``Espaces de travail…`` capture la géométrie courante de la fenêtre, la disposition
des docks / barres d'outils, les tailles des séparateurs et le dossier racine actif sous un nom — puis
vous laisse basculer entre les dispositions enregistrées comme d'autres gestionnaires de photos
compatibles XMP basculent entre *Library* / *Develop* / *Export*, ou comme Adobe Bridge bascule entre
*Metadata* / *Filmstrip*. La boîte de dialogue prend en charge Enregistrer l'actuel, Charger, Renommer
et Supprimer. Les espaces de travail sont conservés dans ``user_settings.json`` (sous la clé
``workspaces``) et survivent aux sessions.

.. tip::
   Construisez un espace de travail **Browse** avec l'arbre et la grille de vignettes visibles, et un
   espace de travail **Develop** distinct avec le panneau de développement maximisé et l'arbre
   réduit. Un clic place toute votre fenêtre dans la forme adéquate pour chaque tâche.

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
2. Privilèges administrateur requis.
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
     - Panoramique en mode vignettes
   * - ``Shift + Flèche``
     - Panoramique fin
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
   * - ``Home``
     - Réinitialiser le zoom

Édition
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Touche
     - Action
   * - ``E``
     - Ouvrir l'onglet Modify
   * - ``R``
     - Rotation horaire
   * - ``Shift + R``
     - Rotation antihoraire
   * - ``Ctrl + Z``
     - Annuler
   * - ``Ctrl + Shift + Z``
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
     - Vue pixel (≥ 400 % affiche la grille de pixels et la valeur RGB sous le curseur)
   * - ``Shift + M``
     - Faire défiler les modes de couleur (Normal / Niveaux de gris / Inversé / Sépia)
   * - ``S``
     - Diaporama

Animation
^^^^^^^^^

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
à un index global parcouru en arrière-plan. Une fois une racine indexée, vous pouvez l'interroger
par extension, largeur/hauteur minimale, plage de taille ou sous-chaîne de nom, et déposer
les résultats dans la visionneuse comme album virtuel.

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
de l'index triées par distance de Hamming. Ajustez la valeur ``Max distance`` pour
élargir ou resserrer la maille.

Recherche sémantique (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Semantic Search`` vous permet de taper une phrase en langage naturel
(par exemple *"golden retriever in snow"* ou *"neon street at night"*) et
renvoie des images classées depuis la bibliothèque indexée. Chaque image est encodée avec un
encodeur vision/langage CLIP et stockée à côté de son chemin ; une requête textuelle est
encodée dans le même espace vectoriel et comparée par similarité cosinus.

Les encodages sont mis en cache dans ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) ou
``~/.cache/imervue/clip_cache.npz`` (POSIX) sous forme d'une seule archive ``.npz`` compacte
afin que le prochain lancement saute le ré-encodage. Seuls les chemins que vous avez analysés sont
interrogeables — utilisez ``Scan Folder…`` dans la boîte de dialogue pour étendre l'index.

.. note::
   La recherche sémantique nécessite les paquets optionnels ``open_clip_torch`` et ``torch``.
   S'ils ne sont pas installés, l'entrée du menu explique ce qui manque et les autres fonctionnalités
   continuent de fonctionner.

Tag automatique
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` applique des tags heuristiques sous
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``). Si ``onnxruntime`` et un modèle CLIP à
``models/clip_vit_b32.onnx`` sont disponibles, il ajoute également des étiquettes de contenu
basées sur CLIP. S'exécute sur un thread de travail avec une barre de progression en direct.

Tags hiérarchiques
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gère les tags structurés en arbre comme
``animal/cat/british``. Sélectionnez un tag pour voir chaque image sous cette branche
(descendants inclus). Marquez ou démarquez la sélection courante d'un clic.
Les tags hiérarchiques vivent dans l'index de la bibliothèque et sont complémentaires du système
de tags plat dans le menu contextuel.

Renommage par lots avec jetons
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` ouvre un tableau avec aperçu en direct dans lequel vous
saisissez un modèle comme ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` et voyez
exactement comment chaque fichier sera renommé. Les conflits sont mis en évidence afin que
rien ne soit écrasé. Jetons pris en charge : ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``.

Export des métadonnées
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` écrit une ligne par image dans
la vue courante couvrant EXIF, dimensions, étiquette de couleur, note, favori,
tags hiérarchiques, état de tri et notes. Utile pour injecter les décisions de tri
dans un tableur ou un flux de travail externe.

Fichier annexe XMP (interopérabilité avec gestionnaires de photos XMP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue peut lire et écrire des fichiers annexes Adobe XMP (``photo.jpg`` ↔
``photo.xmp``) afin que les notes, titres, descriptions, mots-clés et étiquettes de
couleur fassent l'aller-retour proprement avec d'autres gestionnaires de photos compatibles
XMP, d'autres gestionnaires de photos compatibles XMP, Bridge et autres outils XMP.

- **Importer XMP pour l'image courante** — tire la note / le titre / les mots-clés /
  l'étiquette de couleur depuis le fichier annexe vers la base de données interne.
- **Exporter XMP pour l'image courante** — écrit la note / le titre / les
  mots-clés / l'étiquette de couleur courants dans un fichier annexe à côté de l'image.
- **Import / export par lots** — applique la même opération à la sélection active
  ou à tout le dossier.

L'analyse XML utilise ``defusedxml`` afin que des fichiers annexes malformés ou malveillants
ne puissent pas déclencher d'attaques XXE / billion-laughs. Si ``defusedxml`` n'est pas installé,
les entrées de menu XMP sont masquées et aucun fichier annexe n'est écrit.

La **barre latérale EXIF** expose également une **bande de notation par étoiles** cliquable —
la note qu'elle définit est ce que l'export XMP écrira.

Tri (Sélectionner / Rejeter)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Indicateur de tri à trois états basé sur un marquage. Appuyez sur ``P`` pour sélectionner l'image
courante ou chaque vignette sélectionnée, ``Shift + X`` pour rejeter, ``U`` pour retirer le marquage. ``Filtre`` >
``Par état de tri`` n'affiche que les sélections, les rejets ou les non marqués. ``Extra Tools`` >
``Culling`` applique le filtre via une boîte de dialogue et expose également un bouton **Delete all
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
mois ou année (groupé par date). La date est tirée de l'EXIF
``DateTimeOriginal`` lorsqu'elle est présente, sinon de l'heure de modification du fichier.
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
(1D ou 3D, jusqu'à 64³). Le LUT est analysé avec un ``lru_cache`` clé par
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
corrigée est enregistrée dans un nouveau fichier — la correction d'objectif ne fait pas partie
de la recette car la forme de sortie peut changer.

Vue carte
^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` trace chaque image géolocalisée de la bibliothèque
courante sur une carte interactive Leaflet + OpenStreetMap (nécessite
``PySide6.QtWebEngineWidgets``). Sans WebEngine, la boîte de dialogue se rabat
sur une simple liste d'entrées ``(path, lat, lon)`` afin que la fonctionnalité reste
utilisable sur des installations minimales.

Vue calendrier
^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` affiche un ``QCalendarWidget`` avec les jours
surlignés lorsque des photos ont été prises ce jour-là (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → mtime du fichier). Sélectionner une date liste ses images ;
double-cliquez pour en ouvrir une dans la visionneuse principale.

Détection de visages
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` exécute la cascade de Haar pour visages
frontaux d'OpenCV sur l'image courante et dessine chaque détection comme un rectangle.
Double-cliquez sur une ligne de la liste pour saisir un nom de personne ; à l'enregistrement, les tags
sont écrits dans le blob ``extra['face_tags']`` de la recette. La détection est une
technique classique — la précision est adéquate pour "montre-moi les visages" mais
n'est pas un substitut à la reconnaissance moderne basée sur CNN.

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
normalisé (0..1) avec un angle de redressement arbitraire. La sortie est
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

Géolocalisation GPS
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lit les tags GPS EXIF existants et
vous laisse modifier ou définir de nouvelles coordonnées en degrés décimaux. Nécessite l'installation
de ``piexif`` ; écrit dans le JPEG sur place.

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
     - Dimensions, format, tags EXIF et champs du fichier annexe XMP pour une
       image. Les données manquantes sont rapportées comme la valeur vide appropriée
       plutôt que de lever une exception.
   * - ``read_xmp_tags``
     - Chemin rapide qui ne lit que le fichier annexe XMP — note, étiquette
       de couleur, mots-clés, titre, description.
   * - ``convert_format``
     - Convertit une image vers un autre format. Le format de destination est
       déduit du suffixe de destination (``png`` / ``jpg`` /
       ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``). L'option
       ``quality`` (1–100) s'applique à JPEG/WebP.
   * - ``puppet_from_png``
     - Construit un rig ``.puppet`` à partir d'un PNG en utilisant l'auto-mesh
       du plugin Puppet. Ensemence le catalogue de paramètres standard Cubism afin
       que le rig soit immédiatement pilotable.
   * - ``puppet_inspect``
     - Ouvre une archive ``.puppet`` et renvoie un inventaire structuré :
       drawables, déformateurs, paramètres, mouvements, expressions, zones de
       contact, parties, mélanges de paramètres et rigs physiques.

Tous les outils renvoient des charges utiles sérialisées en JSON dans l'enveloppe
``content`` / ``text`` de MCP ; les charges structurées peuvent être analysées
depuis le champ ``text`` côté client.

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
