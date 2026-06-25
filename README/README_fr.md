<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  Visualiseur d'images / développeur / studio de peinture / animateur de marionnettes accéléré par GPU, construit avec PySide6 et OpenGL
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <strong>Français</strong> ·
  <a href="README_de.md">Deutsch</a> ·
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

## Table des matières

- [Aperçu](#aperçu)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Imervue — Visualiseur d'images et photothèque](#imervue--visualiseur-dimages-et-photothèque)
- [Modify — Développement non destructif](#modify--développement-non-destructif)
- [Paint — Éditeur raster complet](#paint--éditeur-raster-complet)
- [Puppet — Animation 2D avec squelette](#puppet--animation-2d-avec-squelette)
- [Desktop Pet — superposition sans cadre](#desktop-pet--superposition-sans-cadre)
- [Raccourcis clavier et souris](#raccourcis-clavier-et-souris)
- [Structure des menus](#structure-des-menus)
- [Système de plugins](#système-de-plugins)
- [Serveur MCP](#serveur-mcp)
- [Prise en charge multilingue](#prise-en-charge-multilingue)
- [Paramètres utilisateur](#paramètres-utilisateur)
- [Architecture](#architecture)
- [Licence](#licence)

---

## Aperçu

Imervue est une station de travail image accélérée par GPU qui propose **cinq onglets principaux** :

| Onglet | Rôle |
|---|---|
| **Imervue** | Parcourir, visualiser, organiser, rechercher et traiter en lot votre photothèque |
| **Modify** | Pipeline de développement non destructif — curseurs, courbes, LUT, masques, retouche, multi-image |
| **Paint** | Studio de peinture raster complet avec pinceaux, calques, animation, outils manga, E/S PSD |
| **Puppet** | Animateur de marionnettes 2D avec squelette conçu de zéro — maillages, déformeurs, paramètres, mouvements, physique |
| **Desktop Pet** | Superposition de bureau sans cadre, transparente et toujours au premier plan qui exécute n'importe quel rig `.puppet` — glisser-déposer / accrochage aux bords / clic traversant / réduction en plein écran / pilotes en direct / bulle de dialogue / icône de barre d'état système |

Principes de conception :

- **Performance avant tout** — Rendu accéléré par GPU avec des shaders GLSL modernes et des VBO
- **Prise en charge de grandes collections** — Grille de tuiles virtualisée qui ne charge que les vignettes visibles
- **Expérience fluide** — Chargement d'image asynchrone et multithread avec préchargement
- **Développement non destructif** — Chaque ajustement vit dans une recette par image ; le fichier sur disque n'est jamais écrasé tant que vous n'avez pas explicitement exporté
- **Extensible** — Système de plugins complet avec hooks de cycle de vie / menu / image / entrée ; le serveur MCP expose aux assistants IA des outils de logique pure sans dépendance Qt

---

## Installation

### Prérequis

- Python >= 3.10
- GPU compatible OpenGL (un rendu logiciel de secours est disponible)

### Installation depuis les sources

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### Installation comme paquet

```bash
pip install .
```

### Dépendances

| Paquet | Rôle |
|---------|---------|
| PySide6 | Framework GUI Qt6 |
| qt-material | Thème Material Design |
| Pillow | Traitement d'images |
| PyOpenGL | Bindings OpenGL |
| PyOpenGL_accelerate | Optimisation des performances OpenGL |
| numpy | Opérations sur tableaux et cache de vignettes |
| rawpy | Décodage d'images RAW |
| imageio | E/S d'images |
| imageio-ffmpeg | Export MP4 du diaporama (H.264 via ffmpeg) |
| defusedxml | Analyse XML sécurisée (fichiers annexes XMP) |

Optionnel (sous condition ; ne pas installer désactive proprement la fonctionnalité) :

| Paquet | Rôle |
|---------|---------|
| open_clip_torch + torch | Recherche sémantique CLIP (requêtes en langage naturel) |
| onnxruntime | Agrandissement IA Real-ESRGAN / auto-étiquetage CLIP ONNX |
| opencv-python | Fusion HDR, assemblage panoramique, focus stacking, détection de visages, pinceau correcteur |
| sounddevice | Synchronisation labiale via micro pour Puppet |
| mediapipe | Suivi facial par webcam pour Puppet |

---

## Utilisation

### Lancement de base

```bash
python -m Imervue
```

### Ouvrir une image ou un dossier précis

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### Options en ligne de commande

| Option | Description |
|--------|-------------|
| `--debug` | Active le mode débogage |
| `--software_opengl` | Utilise le rendu OpenGL logiciel (définit `QT_OPENGL=software` et `QT_ANGLE_PLATFORM=warp`) |
| `file` | (positionnel) Fichier image ou dossier à ouvrir au démarrage |

---

## Imervue — Visualiseur d'images et photothèque

L'onglet **Imervue** est la surface d'accueil par défaut. Il associe le visualiseur d'images à l'arborescence des dossiers, à la barre latérale EXIF et aux outils d'organisation de la photothèque.

### Visualiseur

- **Rendu accéléré par GPU** via OpenGL (shaders GLSL 1.20 avec VBO)
- **Pyramide deep-zoom** — tuiles multi-niveaux 512×512 avec rééchantillonnage LANCZOS, cache LRU jusqu'à 256 tuiles / budget VRAM de 1,5 Go, filtrage anisotrope jusqu'à 8×
- **Chargement asynchrone** — décodage multithread avec préchargement de ±3 images
- **Grille de vignettes virtualisée** — seules les tuiles visibles sont rendues ; taille de vignette configurable (128 / 256 / 512 / 1024 / auto)
- **Cache disque** — vignettes PNG compressées avec invalidation basée sur MD5 sous `%LOCALAPPDATA%/Imervue/cache/thumbnails` (ou `~/.cache/imervue/thumbnails`)
- **Lecture d'animations** — GIF / APNG avec lecture / pause / défilement image par image / contrôle de vitesse

### Modes de navigation

- **Grille** (par défaut) — grille de tuiles virtualisée avec aperçu au survol (délai de 500 ms)
- **Liste (détail)** — bascule avec `Ctrl+L` ; colonnes : Aperçu · Étiquette · Nom · Résolution · Taille · Type · Modifié
- **Deep Zoom** — double-cliquez sur une tuile ; panoramique / zoom GPU fluide avec mini-carte
- **Vue divisée** (`Shift+S`) — deux images côte à côte
- **Lecture en double page** (`Shift+D`, `Ctrl+Shift+D` pour les mangas de droite à gauche) — lecteur en pages en regard
- **Miroir multi-écrans** (`Ctrl+Shift+M`) — fenêtre pour écran secondaire
- **Mode théâtre** (`Shift+Tab`) — masque toute l'interface
- **Boîte de dialogue Comparer** — Côte à côte / Superposition (curseur alpha) / Différence (curseur de gain) / Séparation A|B avec diviseur déplaçable
- Vues **Timeline / Calendar / Map** — regrouper la photothèque par date de capture, parcourir sur un calendrier, placer les clichés géolocalisés sur Leaflet + OpenStreetMap

### Surimpressions à l'écran

- Histogramme RGB (`H`)
- F8 OSD (nom de fichier / taille / type), Ctrl+F8 HUD de débogage (VRAM / cache / threads)
- Vue pixel (`Shift+P`) — zoom ≥ 400 % affichant la grille de pixels + RGB / HEX par pixel
- Modes de couleur (`Shift+M`) — Normal / Niveaux de gris / Inversé / Sépia via GLSL

### Navigation

- Touches fléchées, historique de type navigateur (`Alt+←/→`), saut aléatoire (`X`)
- Navigation inter-dossiers (`Ctrl+Shift+←/→`)
- Aller à l'image par index (`Ctrl+G`)
- Recherche floue (`Ctrl+F` / `/`)
- **Palette de commandes** (`Ctrl+Shift+P`) — recherche floue de toutes les actions de menu
- Bouclage automatique en fin de dossier
- Zoom par pincement sur trackpad + balayage horizontal pour naviguer

### Organisation

- **Marque-pages** — jusqu'à 5000 chemins
- **Notes** — 0-5 étoiles (`1`–`5`) + cœur favori (`0`)
- **Étiquettes de couleur** — drapeaux rouge/jaune/vert/bleu/violet (`F1`–`F5`)
- **Tri (Culling)** — drapeau à 3 états compatible avec d'autres gestionnaires photo XMP (`P` = garder, `Shift+X` = rejeter, `U` = retirer) ; filtre par état ; suppression groupée des rejetés ; le tri automatique garde l'image la plus nette de chaque groupe de quasi-doublons et rejette le reste
- **Étiquettes hiérarchiques** — arborescences telles que `animal/cat/british` ; les descendants sont automatiquement reconnus
- **Tags & Albums** avec filtrage multi-étiquettes AND/OR
- **Albums intelligents** — enregistrer des requêtes basées sur des règles et les réappliquer en un clic ; les filtres couvrent l'extension, la résolution et le **rapport d'aspect**, la **taille de fichier**, la note **plancher / plafond**, la couleur, le tri, les étiquettes (y compris l'**exclusion**), le **boîtier / objectif**, le **regex / glob de nom de fichier** et l'**ancienneté du fichier**, plus l'**export / import** vers un fichier JSON portable
- **Empilement des paires RAW+JPEG** — regrouper les captures de même base en une seule tuile ; le RAW reste accessible comme frère
- **Notes par image** dans la barre latérale EXIF — sauvegarde temporisée, persistante entre sessions
- **Plateau de travail** — panier inter-dossiers qui survit aux redémarrages ; déplacement / copie / export en masse
- **Gestionnaire de fichiers à deux volets** — vue à deux arborescences
- **Sessions / Mises en page d'espace de travail** — capture des onglets / sélection / filtre / géométrie des docks dans `.imervue-session.json` ; enregistrement de mises en page nommées pour les arrangements Browse / Develop / Export
- **Macros** — enregistrement / relecture de lots d'actions de note / favori / couleur / étiquette (`Alt+M` relance la dernière macro)
- **Badges de vignette + densité** — bandeau de couleur, favori, marque-page, étoiles de note ; espacement Compact / Standard / Relaxed
- **Glisser-déposer vers des applications externes** — faire glisser une tuile directement dans Explorer / Chrome / Discord
- **Dossiers / images récents** suivis ; le dernier dossier est restauré automatiquement au démarrage

### Tri et filtrage

- Tri par nom / modifié / créé / taille / résolution (croissant ou décroissant)
- Filtrage par extension, étiquette de couleur, note, étiquette/album, état de tri
- **Filtre avancé** — plage de résolution / taille de fichier / orientation / date de modification
- Boîte de dialogue **Filtre multi-étiquettes** avec logique booléenne AND / OR

### Recherche

- **Recherche floue par nom de fichier** avec mise en surbrillance des sous-chaînes
- **Trouver des images similaires** — pHash (DCT 64 bits) avec distance de Hamming ajustable
- **Recherche dans la photothèque** — index SQLite multi-racines avec un DSL de requête compact : mots-clés, étiquettes (y compris la négation), notes, couleur, extension, lieu, tri, favoris, rapport d'aspect, ancienneté, taille, dimensions, boîtier / objectif, et regex / glob de nom de fichier
- **Trouver des similaires (hachage moyen)** — pHash et dHash sont complétés par un hachage moyen (aHash) optionnel pour une métrique de quasi-doublon complémentaire
- **Recherche sémantique (CLIP)** — requêtes en langage naturel (« golden retriever dans la neige ») via des embeddings mis en cache ; indisponible proprement lorsque `open_clip_torch` + `torch` ne sont pas installés
- **Auto-Tag** — classification heuristique avec mise à niveau CLIP ONNX optionnelle

### Métadonnées

- **Barre latérale EXIF** avec groupes repliables + bande de notation 0-5 étoiles intégrée
- Boîte de dialogue **Éditeur EXIF**
- **Éditeur de mots-clés** — titre / créateur / description / mots-clés, avec **suggestions d'étiquettes liées** issues de la cooccurrence des étiquettes et expansion de vocabulaire contrôlé (un mot-clé feuille applique automatiquement ses ancêtres + synonymes depuis un vocabulaire hiérarchique éditable)
- Boîte de dialogue **Informations sur l'image** (dimensions / taille / dates)
- **Fichiers annexes XMP** (compagnons `.xmp`) — aller-retour de la note / titre / description / mots-clés / étiquette de couleur pour l'interopérabilité avec d'autres gestionnaires photo XMP (XML sécurisé via `defusedxml`)
- **Éditeur de géotag GPS** — lecture des coordonnées EXIF GPS existantes, écriture de nouvelles latitudes/longitudes via piexif (JPEG)
- **Renommage par lot avec jetons** — modèles avec aperçu en direct comme `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Exporter les métadonnées CSV / JSON** — une ligne par image avec tri / note / étiquettes / notes

### Outils supplémentaires (onglet Imervue — traitement par lots)

Accessibles depuis le menu **Tools** ; organisés en sous-menus groupés par fonction :

- **Batch** — Conversion de format · Suppression EXIF · Image Sanitizer (re-rendu pour effacer les données cachées) · Image Organizer (tri en sous-dossiers par date / résolution / type / taille) · Renommage par lot avec jetons
- **AI / Heuristique** — Agrandissement d'image IA (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Trouver les doublons · Trouver des images similaires · Auto-Tag · Détection de visages (cascade Haar)
- **Photothèque et métadonnées** — Recherche dans la photothèque · Albums intelligents · Étiquettes hiérarchiques · Export des métadonnées · Fichiers annexes XMP · Géotag GPS

### Intégration système

- Menu contextuel **Ouvrir avec Imervue** au clic droit sous Windows (association de fichiers via le registre)
- Surveillance des dossiers via `QFileSystemWatcher` (rafraîchissement automatique au changement)
- Système de notifications toast (info / succès / avertissement / erreur)
- Système de plugins avec téléchargeur en ligne (voir [Système de plugins](#système-de-plugins))

---

## Modify — Développement non destructif

L'onglet **Modify** est la station de développement. Chaque ajustement vit dans une **recette** par image stockée à côté du fichier — les pixels d'origine sur disque ne sont jamais écrasés tant que vous n'avez pas explicitement choisi **Export** ou **Save As**.

### Curseurs de développement

- Balance des blancs — température / teinte
- Régions tonales — ombres / tons moyens / hautes lumières
- Exposition / contraste / saturation / vibrance
- Recadrage, rotation, retournement horizontal / vertical
- Toutes les modifications restent non destructives et passent par le magasin de recettes

### Courbes et LUT

- **Éditeur de courbe tonale** — courbe RGB déplaçable plus canaux R / G / B individuels avec interpolation cubique monotone
- **Appliquer un LUT .cube** — charger n'importe quel LUT 3D Adobe (jusqu'à 64³), interpolation trilinéaire, mélange via curseur d'intensité
- **Split Toning** — teinte + saturation par drapeau pour les ombres / hautes lumières avec pivot d'équilibre

### Effets créatifs

- **Solarize** — inversion tonale de style chambre noire (seuil + mix)
- **Diffuse Glow / Orton** — bloom de hautes lumières en flou diffus (intensité / rayon / seuil de hautes lumières)
- **Gradient Map** — luminance → palette, avec un mode d'interpolation perceptuel (OkLCH) optionnel qui conserve la vivacité des dégradés saturés jusqu'au point médian au lieu de les griser
- **Ordered Dither** — quantification par matrice de Bayer sur N niveaux (extrêmes préservés)
- **Graduated Density** — dégradé ND linéaire par angle/dureté/décalage avec teinte optionnelle, pour les ciels et les premiers plans
- **Tone Equalizer** — exposition indépendante par zone de luminance (des ombres aux hautes lumières) sur un masque lissé
- **Detail Equalizer** — repondération du contraste par bande de fréquence (texture fine vs contraste grossier), au-delà d'un simple curseur de clarté
- **Filmic Tone Map** — atténuation pure des hautes lumières Reinhard/Hable avec contraste pivoté et restauration de la saturation, pour les prises uniques à fort contraste
- **Velvia** — boost de saturation pondéré par la luminance qui intensifie les couleurs ternes tout en épargnant les ombres
- **Film Negative** — inverser un négatif couleur numérisé en éliminant la base orange du film, avec gamma de sortie
- **Defringe** — désaturer les franges d'aberration chromatique violettes/vertes sur les bords à fort contraste
- **Emboss** — relief en lumière directionnelle à partir d'un champ de hauteur de luminance
- **Polar Coordinates** — enrouler une image en disque ou la dérouler (planète miniature / inversion polaire)
- **Kaleidoscope** — réfléchir un secteur angulaire en symétrie d'ordre n
- **Frosted Glass** — dispersion locale de pixels déterministe à graine fixe
- **Préréglages de développement** — enregistrer une recette, puis l'appliquer en bloc ou n'en fusionner que les ajustements actifs sur d'autres images (en conservant le recadrage propre à chaque image, etc.)

### Ajustements locaux

- **Masques par pinceau / radial / dégradé linéaire** avec deltas d'exposition / luminosité / contraste / saturation / balance des blancs par masque + curseur de feather
- Les masques se fondent de manière non destructive dans le pipeline de développement

### Retouche et transformation

- **Pinceau correcteur** — points circulaires, inpainting OpenCV (Telea ou Navier-Stokes)
- **Tampon de clonage** — Shift+clic pour la source, application avec feather à la destination
- **Recadrage / Redressement** — rectangle de recadrage normalisé plus redressement à angle arbitraire qui recadre automatiquement au plus grand rectangle interne
- **Redressement automatique** — détection d'horizon / verticale par lignes de Hough
- **Correction d'objectif** — distorsion radiale en pure numpy (barillet / coussinet), récupération de vignettage, correction d'aberration chromatique par canal
- **Réduction de bruit / Accentuation** — débruitage bilatéral préservant les bords + accentuation par masque flou
- **Ciel / Arrière-plan** — remplacer le ciel détecté par un dégradé ou supprimer l'arrière-plan (transparent ou rempli en blanc) ; mise à niveau optionnelle `rembg` / U²-Net

### Multi-image

- **Fusion HDR** — combiner des expositions bracketées via la fusion Mertens d'OpenCV (avec pré-alignement AlignMTB)
- **Assemblage panoramique** — `Stitcher` OpenCV en mode panorama ou scans, recadrage automatique des bordures noires
- **Focus Stacking** — carte de focus par variance laplacienne + mélange gaussien avec alignement ECC optionnel

### Sortie

- **Filigrane superposé** — texte ou image, 9 positions d'ancrage, opacité, échelle ; appliqué uniquement à l'export
- **Préréglages d'export** — pipelines en un clic Web 1600 / Print 300 dpi / Instagram 1080
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF avec curseur de qualité pour les formats avec perte
- **Opérations par lots** — renommer, déplacer/copier, faire pivoter les images sélectionnées
- **PDF planche-contact** — grille multi-pages avec légendes (A4 / A3 / Letter / Legal)
- **Galerie web HTML** — dossier autonome avec `index.html` + miniatures JPEG + lightbox en ligne
- **Diaporama MP4** — vidéo H.264 avec FPS / temps d'affichage par image / transitions par fondu / dissolution / glissement / balayage configurables (`imageio-ffmpeg`)
- **Mise en page d'impression** — feuille PDF multi-pages avec taille de page / orientation / grille / marges / gouttière / traits de coupe configurables
- **Soft Proof** — charger un profil ICC, simuler le gamut de destination, mettre en évidence les pixels hors gamut en magenta
- **Copies virtuelles** — instantanés de recette nommés par image ; basculer entre les styles sans perdre le master

### Éditeurs externes

Enregistrez les programmes (votre éditeur d'image / … ) sous **File > External Editors…** et lancez-les sur l'image actuelle via **File > Open in External Editor**.

---

## Paint — Éditeur raster complet

L'onglet **Paint** est un studio de peinture raster complet intégré comme `QMainWindow` autonome avec menus, barre d'outils à gauche, barre d'options contextuelle, et une colonne de docks à onglets à droite. Édition multi-document — ouvrez plusieurs dessins à la fois, chacun avec sa propre pile d'annulation.

### Outils (27)

Pinceau · Gomme · Remplissage · Pipette · Rect / Lasso / Baguette / Sélection rapide · Déplacer · Texte · Dégradé · Flou · Doigt · Dodge · Burn · Sponge · Stylo · Tampon de clonage · Bulle de dialogue · Rectangle · Ellipse · Ligne · Polygone · Recadrage · Transformer · Main · Zoom

Le trio de virage de chambre noire — **Dodge** (éclaircir), **Burn** (assombrir) et **Sponge** (saturer / désaturer) — peint des ajustements locaux de tonalité et de chrominance, pondérés par le pinceau et un masque ombres / tons moyens / hautes lumières.

Raccourcis à une lettre : `B / E / G / I / V / T / U / R / P / S / C / Z / H` ; `Shift+R/E/I/P` pour les variantes de forme.

### Pinceaux

Stylo / marqueur / crayon / surligneur / aérosol / calligraphie / aquarelle / fusain / crayon de couleur, avec contrôles Taille / Opacité / Dureté / Densité / Mode de fusion. Éditeur de courbe de pression, capture de pointe de pinceau depuis une sélection, import / export de préréglages de pinceaux.

### Calques

Panneau de calques complet avec miniatures, bascules de visibilité, glisser-déposer pour réordonner, modes de fusion, opacité, recherche, calques vectoriels, calques 1 bit, **masques de calque** (ajouter / depuis la sélection / inverser / appliquer), **masques d'écrêtage**, **effets de calque** (ombre portée / lueur externe / contour). Division de calque par couleur, préréglages de gradient map.

### Sélection

Rect / Lasso / Baguette / Sélection rapide avec modes **Remplacer / Ajouter / Soustraire / Intersecter** et Feather. **Mode masque rapide** (`Q`) pour les flux de travail « peindre le masque ». Boîte de dialogue **Contourer la sélection**.

### Animation et manga

- **Animation** — dock de timeline d'images avec instantanés, lecture, pelure d'oignon, export MP4 / GIF
- **Outils manga** — Découpe de cases · Calques de tonalité · Tampon de numéros de page · Lignes de vitesse (Radial / Parallèle / Burst) · Action Flash · Outil bulle de dialogue

### Filtres et aides à la vue

- **Filtres** — Niveaux · Courbes · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone (chacun avec une boîte de dialogue à aperçu en direct)
- **Aides à la vue** — Grille de pixels · Aligner sur le pixel · Aligner sur les bords · Pelure d'oignon · Guides de fond perdu · Rotation du canevas (`Ctrl+Shift+H` tourne dans le sens antihoraire)

### Docks (10, à onglets)

Couleur · Pinceau · Calque · Navigateur · Bibliothèque de matériaux · Historique · Nuancier · Référence · Histogramme · Animation. Chaque dock est déplaçable / flottant. **Settings > Workspace Layouts** enregistre et rappelle des arrangements nommés.

### E/S de fichiers

- Ouverture / sauvegarde **PSD** (Photoshop) avec aller-retour complet des calques
- Export PNG / JPEG / WebP, plus export bande dessinée multi-pages en **CBZ** ou **PDF**
- Instantanés de sauvegarde automatique avec restauration du plus récent

### UX pour utilisateurs avancés

- **Tab** bascule tous les docks pour peindre sans distraction
- `Ctrl+Tab` parcourt les onglets
- `,` / `.` parcourt les types de pinceaux
- `0`-`9` définit l'opacité du pinceau par pas de 10 %
- `Alt+[` / `Alt+]` déplacent le calque actif
- Clic droit sur le canevas ouvre un menu rapide Undo / Redo / Tout sélectionner / Désélectionner / Ajuster / 100 %
- Astérisque de modification par onglet, toasts de confirmation pour annuler / refaire, invite de récupération de sauvegarde automatique au lancement

Appuyez sur `E` depuis Deep Zoom pour envoyer l'image actuelle directement dans un nouvel onglet Paint.

---

## Puppet — Animation 2D avec squelette

L'onglet **Puppet** est un système d'animation de marionnettes 2D avec squelette conçu de zéro. Il fait ce que fait Live2D (rigs de déformation par maillage, paramètres, mouvements, physique, expressions, postures, synchronisation labiale, suivi facial par webcam) mais **sans SDK propriétaire**, **sans `live2d-py`**, et avec un format de fichier `.puppet` totalement ouvert documenté dans `Imervue/puppet/FORMAT.md`.

> **Tutoriel complet** : [`puppet_guide.md`](../puppet_guide.md) couvre le
> flux de bout en bout à la fois pour la diffusion en direct (OBS / NDI / caméra
> virtuelle) et la production d'animation (enregistrement / édition de timeline / export
> MP4). Versions chinoises sur
> [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) et
> [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md).

### Format de fichier

`.puppet` est un conteneur zip :

- `puppet.json` — manifeste (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — textures d'atlas
- `motions/*.json` — pistes de keyframes
- `expressions/*.json` — superpositions de paramètres
- `physics.json` — configuration physique Verlet

Basé sur JSON, lisible et diffable par un humain, sans binaire propriétaire.

### Moteur de rendu

`QOpenGLWidget` avec dessin de triangles texturés en vertex-array dans l'ordre draw_order, modes de fusion par drawable (normal / additif / multiplicatif), exclusivité des pose-groups, projection orthogonale dans l'espace image, fond en damier de transparence tilé via GL_REPEAT, zoom à la molette + panoramique par bouton du milieu. Optimisé pour les grands rigs — March 7th (307 drawables / 2965 vertex morphs) tourne à 60 FPS sur CPU.

### Création

- **Importer un PNG** → générer automatiquement un maillage triangulé respectant l'alpha
- Actions de barre d'outils **Add Rotation Deformer** (ancre + angle) / **Add Warp Deformer** (lattice bezier rows × cols)
- **Add Parameter** → définir des formes-clés aux extrêmes du curseur via **Set Key** dans le dock des paramètres
- **Éditeur de maillage** — basculer Edit Mesh pour déplacer les sommets ; les clics à moins de 8 px se collent au plus proche
- **Save As…** écrit l'ensemble du rig dans un zip `.puppet`

### Exécution

- **Rig de paramètres** — chaque paramètre conserve une liste de clés mappant une valeur de curseur à un instantané partiel de forme de déformeur ; l'exécution échantillonne et interpole linéairement par champ
- **Lecture de mouvements** — dock inférieur avec liste de mouvements + Play / Pause / Stop / Loop / scrub ; l'échantillonneur de courbes honore les segments `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` (résolution time → param par itération de Newton) ; fondu d'entrée / sortie par mouvement
- **Expressions** — pile de superpositions de paramètres `additive` / `multiply` / `overwrite`
- **Pose groups** — visibilité de drawables mutuellement exclusive (changement d'arme, variantes de forme de bouche)
- **Physique** — chaînes pendulaires de Verlet pour cheveux / vêtements / rubans ; le paramètre d'entrée déplace l'ancre de la chaîne, la gravité + l'amortissement + les ressorts par particule ramènent au repos
- **Vertex morphs** — mélange linéaire style Cubism entre rest et deltas ±extreme ; numpy vectorisé par image à 60 FPS
- **Opacity keys** — courbes alpha pilotées par paramètres ; permettent à des maillages de pose alternatifs d'apparaître/disparaître en fondu lorsqu'un paramètre de geste se déclenche

### Entrée en direct

- Glisser du curseur → paramètres d'angle de tête
- Clignement automatique sur une courbe cosinus ouvrir → fermer → ouvrir
- Synchronisation labiale au micro via RMS `sounddevice` → `ParamMouthOpenY` (dépendance optionnelle)
- Suivi facial par webcam via OpenCV + MediaPipe FaceMesh → tête yaw / pitch / roll + ouverture des yeux / bouche (dépendances optionnelles)
- Enregistrement de mouvements personnalisés — capture les valeurs de paramètres à 30 Hz pendant que vous bougez des curseurs / faites face à la webcam / laissez la physique tourner ; cuit le tout en un Motion à segments linéaires prêt à jouer / boucler / sauvegarder

### Interopérabilité Cubism

Le **Cubism Native SDK** peut être branché (DLL fournie par l'utilisateur — la Free Material License de Live2D interdit la redistribution) pour convertir n'importe quel modèle `.moc3` en zip `.puppet`. Le convertisseur exécute un balayage sample-and-reconstruct qui capture à la fois les deltas de vertex-morph et les transitions de visibilité pilotées par paramètre, de sorte que les bascules de geste (signe de paix / main devant le visage / photo …) survivent intactes à la conversion.

### Sortie

- **Capture frame…** enregistre un PNG du canevas actuel via `glReadPixels`
- **Record…** active une boucle de 30 FPS qui écrit en GIF / WebM / MP4 via `imageio`
- **Caméra virtuelle** — expose le canevas du puppet comme webcam système
- **Sortie NDI** — diffuse le puppet comme source NDI sur le LAN
- **Serveur API VTube Studio** — API WebSocket optionnelle pour les clients compatibles VTS

### Diffusion en direct vers OBS

Deux chemins pris en charge. Choisissez A pour « ça marche tout de suite », B si vous voulez la latence la plus faible et la meilleure qualité sur un LAN rapide.

#### A. Caméra virtuelle (le plus simple)

Le canevas du puppet apparaît comme une webcam qu'OBS capte via sa source Video Capture Device standard.

1. `pip install pyvirtualcam`
2. Installez le pilote selon la plateforme :
   - **Windows** : OBS Studio 26+ embarque le pilote *OBS Virtual Camera*. Après avoir installé OBS, ouvrez-le une fois et cliquez sur **Start Virtual Camera** dans le panneau en bas à droite — cela enregistre le pilote au niveau système afin que `pyvirtualcam` puisse le trouver.
   - **macOS** : OBS pour Mac inclut une extension système OBS Virtual Camera. La première exécution invitera à l'activer dans Réglages Système → Confidentialité et sécurité.
   - **Linux** : `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (installez d'abord `v4l2loopback-dkms`).
3. Dans l'onglet Puppet, ouvrez votre rig, puis activez **Output > Virtual camera**. La barre d'état affiche le nom exact du périphérique à choisir.
4. Dans OBS : **Sources > + > Video Capture Device**, choisissez le périphérique nommé à l'étape 3 (généralement *OBS Virtual Camera*).

Imervue plafonne le plus grand côté de la sortie en streaming à 1080 px afin que les canevas natifs Cubism (March 7th fait 3503×7777) ne soient pas rejetés par le pilote de caméra virtuelle DirectShow. Le rapport d'aspect est préservé ; OBS peut redimensionner davantage si nécessaire.

##### Pourquoi le fond est-il magenta ? (et comment l'enlever)

Les caméras virtuelles passent par **DirectShow** (Windows) / **AVFoundation** (macOS) / **v4l2loopback** (Linux). Les trois transports sont **RGB uniquement — pas de canal alpha**. La source *Video Capture Device* d'OBS traite ce que la caméra envoie comme du RGB opaque, donc la couleur qu'Imervue place derrière le personnage est ce qu'OBS affichera.

Imervue choisit le **magenta `#FF00FF`** comme arrière-plan parce que c'est la couleur de chroma-key standard de l'industrie : elle n'apparaît presque jamais dans les tons de peau, les cheveux ou les couleurs des yeux, donc le seuil de chroma-key peut être ouvert largement sans entamer le personnage.

Pour supprimer le magenta dans OBS :

1. Clic droit sur la source *Video Capture Device* ajoutée → **Filtres**
2. Dans le panneau **Filtres d'effet** en bas à gauche → **+** → **Color Key**
3. Configurez :
   - **Key Color Type** : `Custom Color`
   - **Custom Color** : HEX `FF00FF` (ou R = 255 / G = 0 / B = 255)
   - **Similarity** : commencez à `80`, montez vers `200–300` si des bords magenta apparaissent encore. Plus élevé = suppression plus agressive.
   - **Smoothness** : `30–50` adoucit le bord pour que la coupe ne paraisse pas dure / pixelisée.
4. Fermez la boîte de dialogue. OBS attache le filtre à la source, donc la prochaine fois que vous activerez la caméra virtuelle, le chroma-key sera automatiquement appliqué.

Si le personnage a du magenta dans sa palette (inhabituel mais possible sur des costumes / accessoires), le chroma key mangera aussi ces pixels. Passez au chemin NDI ci-dessous — NDI transporte directement le canal alpha donc aucun chroma-keying n'est nécessaire.

**Dépannage : je vois encore du magenta dans OBS**

- Vérifiez que le filtre Color Key est attaché à la source **Video Capture Device**, et non à une scène. Les filtres sur la source voyagent avec elle ; les filtres sur la scène s'appliquent par-dessus après le rendu de la source.
- Vérifiez que le hex est exactement `FF00FF` — `FF00FE` ou similaire ne capturera pas tous les pixels magenta.
- Poussez *Similarity* jusqu'à `300` s'il reste un mince halo de pixels magenta au contour du personnage. Les bords proviennent de l'interpolation GL_LINEAR contre l'arrière-plan magenta ; une tolérance de similarity plus large les mange.

#### B. NDI (latence la plus faible, qualité pro)

NDI (Network Device Interface de Newtek) transporte le puppet sur le LAN avec une latence inférieure à 50 ms et le canal alpha intact.

1. Téléchargez et installez **NDI Tools** depuis <https://ndi.video/tools/> (inclut le runtime NDI).
2. `pip install ndi-python`
3. Installez le plugin **obs-ndi** dans OBS : <https://github.com/obs-ndi/obs-ndi/releases>
4. Dans l'onglet Puppet, activez **Output > NDI output**. La barre d'état rapporte le nom de la source NDI (par défaut *Imervue Puppet*).
5. Dans OBS : **Sources > + > NDI Source**, choisissez la source de l'étape 4.

NDI diffuse à la même résolution plafonnée à 1080 que le chemin A, mais livre du RGBA — le rendu hors écran produit un arrière-plan transparent en dehors du personnage, NDI expédie le canal alpha intact, et OBS / vMix composent le puppet directement par-dessus votre scène sans aucune passe de chroma-key.

#### C. Capture de fenêtre (solution de secours)

OBS **Sources > + > Window Capture** peut capter la fenêtre Imervue directement, aucune dépendance supplémentaire requise. Qualité moindre et vous devez recadrer l'interface vous-même, mais cela fonctionne sur des machines verrouillées où vous ne pouvez pas installer de pilotes.

### Démo

Un rig prêt à l'emploi se trouve à [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — un personnage Cubism Live2D à 307 drawables converti dans le dépôt. Ouvrez via **Open Puppet…** pour voir le rig apparaître centré ; cliquez sur l'un des 18 mouvements (groupe Idle + groupe Gesture) pour le jouer. Les gestes couvrent le signe de paix, main devant le visage, photo, rougeur, visage sombre, pleurs, sueur, étoiles, étoile filante — chaque geste nommé que le rig définit.

---

## Desktop Pet — superposition sans cadre

Onglet 5 — le **Desktop Pet** place n'importe quel personnage `.puppet` sur votre bureau sous forme de superposition sans cadre et transparente. L'onglet lui-même sert de panneau de contrôle ; le personnage flotte au-dessus (ou derrière) de vos autres fenêtres. Tout ce que vous pouvez faire avec un rig dans l'onglet Puppet — mouvements, expressions, physique, pilotes idle, entrée webcam / micro — fonctionne aussi ici.

### Ce que vous pouvez faire

| Fonctionnalité | Rôle |
|---|---|
| Superposition sans cadre | Pas de chrome de fenêtre, pas d'entrée dans la barre des tâches — juste le personnage sur votre bureau. |
| Arrière-plan transparent | Tout ce que le personnage ne couvre pas laisse voir le bureau au travers. |
| Glisser pour déplacer | Clic-gauche maintenu pour déplacer le personnage. Relâcher près d'un bord d'écran l'**accroche** à ras de celui-ci. |
| Mode clic traversant | Faites ignorer la souris au pet pour continuer à travailler en dessous. |
| Verrouiller la position | Figez le pet afin qu'aucun glissement accidentel ne puisse le déplacer. |
| Toujours en arrière-plan | Placez le pet derrière toutes les autres fenêtres — sensation de widget de bureau plutôt que toujours au premier plan. |
| Masquer en plein écran | Auto-masquage lorsqu'une autre application (jeu / vidéo / présentation) est en plein écran sur le même moniteur ; réapparaît à la fin du plein écran. |
| Pause quand masqué | Le pet cesse d'animer tant qu'il est invisible — zéro CPU hors écran. |
| Tailles préréglées | Petit / moyen / grand. Redimensionnement autour du centre afin que le pet ne saute pas à travers l'écran. |
| Curseur d'opacité | Fondu du pet de 10 % à 100 % pour en faire un ornement de bureau discret. |
| Mémorise sa position | Glissez le pet dans votre coin préféré ; il y retournera au prochain lancement. |

### Interactions au clic

- **Clic-gauche sur le corps** — si le rig définit une zone de contact (par exemple toucher la tête), le mouvement correspondant se joue. Sinon, le pet vous salue dans une bulle de dialogue.
- **Clic-droit n'importe où** — ouvre un menu contextuel avec : Masquer le pet, Pilotes en direct, Jouer un mouvement (liste de tous les mouvements du rig), Appliquer une expression, Verrouiller la position, Clic traversant, Toujours en arrière-plan, Masquer en plein écran, Bulle de dialogue, Taille.
- **Icône de barre d'état système** — clic-gauche pour basculer la visibilité, clic-droit pour Afficher/Masquer, Clic traversant, Ouvrir un puppet, Masquer le pet.

### Pilotes en direct

Choisissez n'importe quelle combinaison depuis l'onglet ou le menu clic-droit. Chacun est désactivé par défaut — n'activez que ce que vous voulez.

- **Auto idle** — respiration + légère dérive pour que le personnage semble vivant.
- **Mouvements idle** — cycle aléatoire à travers les mouvements du groupe idle du rig.
- **Auto-clignement** — fermeture cyclique naturelle des yeux toutes les quelques secondes.
- **Suivi de tête par glissement** — la tête se tourne pour suivre votre curseur.
- **Synchronisation labiale au micro** — la bouche s'ouvre avec votre voix (nécessite `sounddevice`).
- **Suivi par webcam** — votre tête / yeux / bouche pilotent ceux du puppet (nécessite `opencv-python` et `mediapipe`).

### Comment démarrer

1. Passez à l'onglet **Desktop Pet**.
2. Cliquez sur **Load bundled March 7th** pour utiliser le personnage inclus, ou sur **Open Puppet…** pour choisir votre propre fichier `.puppet`.
3. Cochez **Show pet on desktop**.
4. Glissez le personnage là où vous le souhaitez ; choisissez les pilotes voulus ; ajustez l'opacité / la taille.
5. Faites un clic-droit à tout moment pour le menu d'actions rapides, ou utilisez l'icône de la barre d'état système pour masquer le pet sans retrouver l'onglet.

Tout ce que vous réglez — position, pilotes, opacité, clic traversant, taille — est mémorisé entre les lancements.

---

## Raccourcis clavier et souris

### Navigation (tous les modes)

| Raccourci | Action |
|----------|--------|
| Touches fléchées | Défilement de la grille / Changer d'image (Gauche/Droite en deep zoom) |
| Shift + Flèche | Défilement fin (demi-pas) |
| Ctrl+Shift+←/→ | Aller au dossier frère précédent / suivant contenant des images |
| Alt+← / Alt+→ | Historique précédent / suivant |
| Ctrl+G | Aller à l'image par index |
| X | Sauter à une image aléatoire |
| Home | Réinitialiser le zoom et le panoramique à l'origine |
| Ctrl+F ou / | Ouvrir la boîte de dialogue de recherche floue |
| Ctrl+Shift+P | Ouvrir la palette de commandes |
| Alt+M | Rejouer la dernière macro sur la sélection actuelle |
| S | Ouvrir la boîte de dialogue diaporama |
| Ctrl+Z | Annuler |
| Ctrl+Shift+Z / Ctrl+Y | Refaire |

### Deep Zoom / image unique

| Raccourci | Action |
|----------|--------|
| F | Basculer en plein écran |
| Shift+Tab | Basculer le mode théâtre (masquer toute l'interface) |
| R / Shift+R | Rotation horaire / antihoraire |
| E | Ouvrir l'éditeur d'image (onglet Modify) |
| W / Shift+W | Adapter à la largeur / hauteur |
| H | Basculer la superposition d'histogramme RGB |
| F8 / Ctrl+F8 | Superposition OSD / HUD de débogage |
| Shift+P | Basculer la vue pixel (zoom ≥ 400 % affiche la grille + RGB) |
| Shift+M | Cycler les modes de couleur (Normal / Niveaux de gris / Inversé / Sépia) |
| B | Basculer le marque-page |
| Ctrl+C / Ctrl+V | Copier / coller l'image depuis/vers le presse-papiers |
| 0 / 1-5 | Basculer favori / note rapide |
| F1-F5 | Étiquette de couleur rapide (rouge / jaune / vert / bleu / violet) |
| P / Shift+X / U | Tri : Garder / Rejeter / Retirer |
| Shift+S | Vue divisée |
| Shift+D / Ctrl+Shift+D | Double page (LTR / RTL) |
| Ctrl+Shift+M | Fenêtre miroir multi-écrans |
| Delete | Déplacer vers la corbeille (annulable) |
| Escape | Quitter le deep zoom / Quitter le plein écran |

### Lecture d'animation (GIF / APNG)

| Raccourci | Action |
|----------|--------|
| Espace | Lecture / Pause |
| , (virgule) / . (point) | Image précédente / suivante |
| [ / ] | Diminuer / augmenter la vitesse de lecture |

### Grille de tuiles

| Raccourci | Action |
|----------|--------|
| Ctrl+L | Basculer Grille ↔ Liste |
| Survol (500 ms) | Aperçu au survol |
| Delete | Supprimer les tuiles sélectionnées |
| Escape | Tout désélectionner |

### Souris / trackpad

| Action | Comportement |
|--------|----------|
| Clic gauche | Sélectionner la tuile ou ouvrir l'image |
| Glisser gauche | Multi-sélection rectangulaire dans la grille |
| Appui long (500 ms) | Entrer en mode sélection de tuiles |
| Glisser milieu | Panoramique en deep zoom |
| Molette | Zoom avant/arrière ou défilement |
| Clic droit | Menu contextuel |
| Pincement | Zoom avant/arrière en deep zoom |
| Balayage horizontal | Image précédente / suivante |

### Onglet Paint (en plus de ce qui précède)

| Raccourci | Action |
|----------|--------|
| B / E / G / I | Pinceau / Gomme / Remplissage / Pipette |
| V / T / U / R | Déplacer / Texte / Dégradé / Sélection rectangulaire |
| P / S / C / Z / H | Stylo / Doigt / Clone / Zoom / Main |
| Q | Basculer le mode masque rapide |
| Tab | Basculer tous les docks |
| Ctrl+Tab | Cycler les onglets Paint |
| , / . | Cycler les types de pinceaux |
| 0-9 | Opacité du pinceau par pas de 10 % |
| Alt+[ / Alt+] | Descendre / monter le calque actif |

---

## Structure des menus

### File

- New Window
- Open Image / Open Folder
- Recent (dossiers + images)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — enregistrer / charger / renommer des mises en page de fenêtre nommées
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (raccourcis personnalisables)
- Exit

### Tools (outils supplémentaires — organisés en 8 sous-menus groupés)

- **Batch** — Conversion de format · Suppression EXIF · Image Sanitizer · Image Organizer · Renommage par lot avec jetons
- **Photothèque et métadonnées** — Recherche dans la photothèque · Albums intelligents · Trouver les similaires / doublons · Auto-Tag · Étiquettes hiérarchiques · Export des métadonnées · Fichiers annexes XMP · Géotag GPS
- **Vues** — Timeline · Calendar · Map
- **Workflow** — Tri · Plateau de travail · Copies virtuelles · Gestionnaire de fichiers à deux volets · Macros
- **Export** — PDF planche-contact · Galerie web · Diaporama vidéo (MP4) · Mise en page d'impression
- **Develop (non destructif)** — Courbe tonale · LUT .cube · Split Toning · Masques d'ajustement local · Graduated Density · Velvia · Emboss · Defringe · Film Negative · Filmic Tone Map · Tone / Detail Equalizer · Polar · Kaleidoscope · Frosted Glass · Soft Proof
- **Retouche et transformation** — Agrandissement d'image IA · Réduction de bruit / Accentuation · Pinceau correcteur · Tampon de clonage · Détection de visages · Ciel / Arrière-plan · Recadrage / Redressement · Redressement automatique · Correction d'objectif
- **Multi-Image** — Fusion HDR · Assemblage panoramique · Focus Stacking

### View / Sort / Filter / Language / Plugins / Instructions

(Menus standards — voir l'application pour la liste complète des options.)

### Menu contextuel au clic droit

Navigation · Actions rapides (révéler / copier le chemin / copier l'image) · Transformations · Opérations par lots · Suppression · Fond d'écran · Comparer / Diaporama · Export · Outils supplémentaires · Marque-pages · Informations sur l'image · Éléments contribués par les plugins.

---

## Système de plugins

Imervue prend en charge les plugins tiers. Voir [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) pour la référence complète.

### Démarrage rapide

1. Créez un dossier dans `plugins/` à la racine du projet
2. Définissez une classe qui hérite de `ImervuePlugin`
3. Enregistrez-la dans `__init__.py` avec `plugin_class = YourPlugin`
4. Redémarrez Imervue

### Hooks

| Hook | Déclenchement |
|------|---------|
| `on_plugin_loaded()` | Après l'instanciation du plugin |
| `on_plugin_unloaded()` | À la fermeture de l'application |
| `on_build_menu_bar(menu_bar)` | Après construction de la barre de menus par défaut |
| `on_build_main_tabs(tabs)` | Après ajout des quatre onglets intégrés |
| `on_build_context_menu(menu, viewer)` | À l'ouverture du menu clic droit |
| `on_image_loaded(path, viewer)` | Après chargement d'une image en deep zoom |
| `on_folder_opened(path, images, viewer)` | Après ouverture d'un dossier dans la grille |
| `on_image_switched(path, viewer)` | Lors du changement d'image |
| `on_image_deleted(paths, viewer)` | Après suppression douce d'image(s) |
| `on_key_press(key, modifiers, viewer)` | Lors d'un appui touche (retourne True pour consommer) |
| `on_app_closing(main_window)` | Avant la fermeture de l'application |
| `get_translations()` | Fournir des chaînes i18n |

### Téléchargeur de plugins

**Plugins > Download Plugins** ouvre le téléchargeur en ligne. Dépôt source : [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## Serveur MCP

Imervue embarque un serveur [Model Context Protocol](https://modelcontextprotocol.io) intégré afin que les assistants IA (Claude Code / Desktop, Cursor, Cline, …) puissent appeler les helpers de logique pure du projet sans GUI en cours d'exécution. Sans Qt ; une seule commande :

```sh
python -m Imervue.mcp_server
```

### Outils

Outils sélectionnés (51 au total — liste complète dans la documentation). Chaque outil
annonce un `outputSchema` JSON et des `annotations` lecture seule / destructrices, retourne
son résultat sous forme de `structuredContent`, et les outils de longue durée diffusent
`notifications/progress`.

| Outil | Rôle |
|------|---------|
| `list_images` | Lister les fichiers image d'un dossier (récursif optionnel) |
| `read_image_metadata` / `read_xmp_tags` | Dimensions, format, EXIF, fichier annexe XMP (note, étiquette, mots-clés) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | Analyse sans référence : statistiques par canal, colorimétrie/entropie/contraste, histogramme + écrêtage, score de flou |
| `image_thumbnail` / `ocr_text` / `find_similar` | Aperçu base64, texte Tesseract, groupes de quasi-doublons par hachage perceptuel (avec progression) |
| `convert_format` | Convertir entre PNG / JPEG / WebP / TIFF / BMP (+ HEIC / AVIF / JXL optionnels) |
| `apply_watermark` / `apply_frame` | Incruster un filigrane texte ou un cadre passe-partout / Polaroid + légende |
| `build_collage` | Composer des images en une mosaïque en grille (avec progression) |
| `crop_image` / `resize_image` / `rotate_image` | Recadrage en pixels, redimensionnement préservant le rapport, rotation / retournement sans perte |
| `collection_stats` | Synthèse note / favori / étiquette de couleur / tri d'un dossier |
| `search_images` | Filtrer un dossier avec le DSL de requête des albums intelligents (chemin / EXIF / taille / dimensions) |
| `extract_gps` / `dominant_colors` | Lire les coordonnées GPS EXIF (chaîné dans `reverse_geocode`) ; palette de couleurs median-cut (rgb / hex / part) |
| `error_level_analysis` | Carte de falsification par recompression JPEG sous forme de data URI PNG |
| `solarize_image` / `glow_image` | Appliquer une inversion tonale de solarisation ou un bloom diffuse-glow et enregistrer |
| `velvia_image` / `emboss_image` / `defringe_image` | Boost de saturation Velvia, relief en lumière directionnelle, désaturation des franges de bord |
| `film_negative_image` / `graduated_density_image` | Inverser un négatif numérisé ; appliquer un dégradé de densité gradué linéaire |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Atténuation filmic des hautes lumières ; exposition par zone ; contraste par bande |
| `colormap_image` / `false_color_image` | Recoloriser la luminance via une palette viridis/magma/jet ; échelle d'exposition en fausses couleurs |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Tramage Bayer ordonné ; virage partiel ombres/hautes lumières ; tri de pixels par bande de luminosité |
| `polar_image` / `kaleidoscope_image` | Distorsion vers/depuis le polaire (tiny-planet) ; miroir en quartiers de kaléidoscope |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | Diffusion verre dépoli par voisin aléatoire ; égalisation locale CLAHE ; contraste local clarté + texture |
| `posterize_image` / `gradient_map_image` | Quantifier les canaux en paliers ; remapper la luminance via un dégradé |
| `film_grain_image` / `dehaze_image` / `distort_image` | Grain gaussien réglable ; suppression de brume par canal sombre ; distorsion tourbillon/pincement/ondulation |
| `reverse_geocode` / `extract_video_frame` | GPS hors ligne → ville, décodage d'une image vidéo en photo |
| `puppet_from_png` / `puppet_inspect` | Construire un rig `.puppet` à partir d'un PNG ; en ouvrir un et retourner son inventaire |

### Prompts

Quatre prompts réutilisables : `caption_image`, `suggest_edits`, `analyze_composition`
(critique de composition pilotée par la saillance) et `flag_issues` (triage netteté + qualité
+ écrêtage). Les arguments des prompts peuvent être complétés via `completion/complete`.

### Câblage

Le dépôt embarque un `.mcp.json` à la racine pour l'auto-découverte par Claude Code. Pour Desktop / autres clients, ajoutez ceci à `claude_desktop_config.json` (ou équivalent) :

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

Surface complète du protocole dans la section MCP de [docs/en/index.rst](../docs/en/index.rst).

---

## Prise en charge multilingue

| Langue | Code |
|----------|------|
| English | `English` |
| 繁體中文 (chinois traditionnel) | `Traditional_Chinese` |
| 简体中文 (chinois simplifié) | `Chinese` |
| 한국어 (coréen) | `Korean` |
| 日本語 (japonais) | `Japanese` |

Changement via le menu **Language**. Redémarrage requis.

Les plugins peuvent enregistrer de toutes nouvelles langues via `language_wrapper.register_language()`, ou contribuer des traductions via `get_translations()`. Voir [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## Paramètres utilisateur

Stockés dans `user_setting.json` dans le répertoire de travail. Entrées clés :

| Paramètre | Type | Description |
|---------|------|-------------|
| `language` | string | Code de langue actuel |
| `user_recent_folders` / `user_recent_images` | list | Récemment ouverts |
| `user_last_folder` | string | Restauré automatiquement au démarrage |
| `bookmarks` | list | Chemins d'images marquées (max 5000) |
| `sort_by` / `sort_ascending` | string / bool | Méthode de tri + ordre |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | Organisation par image |
| `thumbnail_size` / `tile_padding` | int | Configuration de la grille |
| `navigation_auto_loop` | bool | Boucle en fin de dossier |
| `keyboard_shortcuts` | dict | Raccourcis clavier personnalisés |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | Persistance de la mise en page |
| `stack_raw_jpeg_pairs` | bool | Bascule d'empilement RAW+JPEG |
| `external_editors` | list | Éditeurs configurés |
| `macros` / `macro_last_name` | list / string | Macros enregistrées + cible de Alt+M |

---

## Architecture

```
Imervue/
├── __main__.py              # Point d'entrée de l'application
├── Imervue_main_window.py   # Fenêtre principale (QMainWindow) — monte les 4 onglets
├── gpu_image_view/          # ONGLET IMERVUE — visualiseur GPU + deep zoom
├── gui/                     # Boîtes de dialogue et panneaux latéraux (développement, EXIF, etc.)
├── paint/                   # ONGLET PAINT — éditeur raster complet
├── puppet/                  # ONGLET PUPPET — animateur de marionnettes 2D
├── export/                  # Générateurs d'export (planche-contact, galerie web, MP4)
├── image/                   # Utilitaires d'image (pyramide, gestionnaire de tuiles, infos)
├── library/                 # Helpers de photothèque (empilement RAW+JPEG, indexation)
├── macros/                  # Enregistrement / relecture de macros
├── menu/                    # Définitions de menus (fichier / outils / filtre / …)
├── mcp_server/              # Serveur stdio Model Context Protocol
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # Intégration d'éditeurs externes
├── plugin/                  # Système de plugins (base / manager / downloader)
├── sessions/                # Sérialisation d'espace de travail
├── system/                  # Association de fichiers Windows
└── user_settings/           # Configuration utilisateur persistante
```

### Pipeline de rendu (onglet Imervue)

1. `GPUImageView` étend `QOpenGLWidget`
2. Deux programmes GLSL 1.20 (quads texturés + rectangles de couleur unie)
3. Cache de textures LRU — limite de 256 tuiles, budget VRAM de 1,5 Go
4. Pyramide de tuiles multi-niveaux construite avec LANCZOS à une taille de tuile de 512 × 512
5. Filtrage anisotrope jusqu'à 8× lorsque le matériel le permet
6. Repli sur rendu logiciel si la compilation des shaders échoue

### Cache de vignettes

- **Clé** : MD5 de `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
- **Format** : PNG compressé (`compress_level=1` — écriture rapide, faible empreinte)
- **Emplacement** : `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) ou `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidation** : Automatique lors du changement des métadonnées de fichier

### Rendu Puppet (onglet Puppet)

- `QOpenGLWidget` avec `glDrawElements` + tableaux de sommets côté client
- Par drawable : sommets au repos mis en cache en numpy float32 ; vertex morphs vectorisés ; tri topologique des déformeurs hissé hors de la boucle par drawable
- Le fond de transparence est une texture 2×2 tilée via GL_REPEAT (auparavant 100k+ quads en mode immédiat avant optimisation)
- Le convertisseur Cubism produit des courbes opacity_keys aux côtés des deltas de vertex-morph afin que les transitions de visibilité pilotées par paramètres survivent à la conversion `.moc3 → .puppet`

---

## Licence

Ce projet est publié sous la [licence MIT](../LICENSE).

Copyright (c) 2026 JE-Chen
