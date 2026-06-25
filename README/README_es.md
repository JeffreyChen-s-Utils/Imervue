<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  Visor / revelador / estudio de pintura / animador de marionetas de imágenes acelerado por GPU, construido con PySide6 y OpenGL
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <strong>Español</strong> ·
  <a href="README_fr.md">Français</a> ·
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

## Tabla de contenidos

- [Resumen](#resumen)
- [Instalación](#instalación)
- [Uso](#uso)
- [Imervue — Visor y biblioteca de imágenes](#imervue--visor-y-biblioteca-de-imágenes)
- [Modify — Revelado no destructivo](#modify--revelado-no-destructivo)
- [Paint — Editor rasterizado con todas las funciones](#paint--editor-rasterizado-con-todas-las-funciones)
- [Puppet — Animación 2D con esqueleto](#puppet--animación-2d-con-esqueleto)
- [Desktop Pet — superposición sin marco](#desktop-pet--superposición-sin-marco)
- [Atajos de teclado y ratón](#atajos-de-teclado-y-ratón)
- [Estructura de menús](#estructura-de-menús)
- [Sistema de plugins](#sistema-de-plugins)
- [Servidor MCP](#servidor-mcp)
- [Soporte multilingüe](#soporte-multilingüe)
- [Configuración del usuario](#configuración-del-usuario)
- [Arquitectura](#arquitectura)
- [Licencia](#licencia)

---

## Resumen

Imervue es una estación de trabajo de imágenes acelerada por GPU que ofrece **cinco pestañas de nivel superior**:

| Pestaña | Función |
|---|---|
| **Imervue** | Examinar, ver, organizar, buscar y procesar por lotes tu biblioteca de imágenes |
| **Modify** | Cadena de revelado no destructiva — controles deslizantes, curvas, LUT, máscaras, retoque, multi-imagen |
| **Paint** | Estudio de pintura rasterizada con todas las funciones, con pinceles, capas, animación, herramientas de manga, E/S de PSD |
| **Puppet** | Animador 2D con esqueleto construido desde cero — mallas, deformadores, parámetros, animaciones, física |
| **Desktop Pet** | Panel de control para ejecutar cualquier rig `.puppet` como una superposición de escritorio sin marco, transparente y siempre encima |

Principios de diseño:

- **Rendimiento primero** — Renderizado acelerado por GPU con shaders modernos de GLSL y VBO
- **Soporte para colecciones grandes** — La cuadrícula virtualizada de mosaicos sólo carga las miniaturas visibles
- **Experiencia fluida** — Carga asíncrona y multihilo de imágenes con precarga
- **Revelado no destructivo** — Cada ajuste se guarda en una recipe por imagen; el archivo en disco nunca se sobrescribe hasta que exportas explícitamente
- **Extensible** — Sistema completo de plugins con hooks de ciclo de vida / menú / imagen / entrada; el servidor MCP expone herramientas de lógica pura sin Qt para asistentes de IA

---

## Instalación

### Requisitos

- Python >= 3.10
- GPU con soporte para OpenGL (también hay opción de renderizado por software como respaldo)

### Instalación desde el código fuente

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### Instalación como paquete

```bash
pip install .
```

### Dependencias

| Paquete | Propósito |
|---------|---------|
| PySide6 | Framework de GUI Qt6 |
| qt-material | Tema Material Design |
| Pillow | Procesamiento de imágenes |
| PyOpenGL | Enlaces para OpenGL |
| PyOpenGL_accelerate | Optimización de rendimiento de OpenGL |
| numpy | Operaciones con arreglos y caché de miniaturas |
| rawpy | Decodificación de imágenes RAW |
| imageio | E/S de imágenes |
| imageio-ffmpeg | Exportación de presentación a MP4 (H.264 vía ffmpeg) |
| defusedxml | Análisis seguro de XML (sidecars XMP) |

Opcionales (gestionados por funcionalidad; si no se instalan, la función se desactiva limpiamente):

| Paquete | Propósito |
|---------|---------|
| open_clip_torch + torch | Búsqueda semántica con CLIP (consultas en lenguaje natural) |
| onnxruntime | Escalado por IA con Real-ESRGAN / etiquetado automático con CLIP ONNX |
| opencv-python | Fusión HDR, costura de panoramas, apilamiento de foco, detección de rostros, pincel de saneamiento |
| sounddevice | Sincronización labial en Puppet desde el micrófono |
| mediapipe | Seguimiento facial por webcam en Puppet |

---

## Uso

### Lanzamiento básico

```bash
python -m Imervue
```

### Abrir una imagen o carpeta específica

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### Opciones de línea de comandos

| Opción | Descripción |
|--------|-------------|
| `--debug` | Activa el modo de depuración |
| `--software_opengl` | Usa renderizado OpenGL por software (define `QT_OPENGL=software` y `QT_ANGLE_PLATFORM=warp`) |
| `file` | (posicional) Archivo de imagen o carpeta que se abrirá al iniciar |

---

## Imervue — Visor y biblioteca de imágenes

La pestaña **Imervue** es la superficie de aterrizaje predeterminada. Combina el visor de imágenes con el árbol de carpetas, la barra lateral EXIF y las herramientas de biblioteca/organización.

### Visor

- **Renderizado acelerado por GPU** mediante OpenGL (shaders GLSL 1.20 con VBO)
- **Pirámide de deep zoom** — mosaicos multinivel de 512×512 con remuestreo LANCZOS, caché LRU hasta 256 mosaicos / presupuesto de 1.5 GB de VRAM, filtrado anisotrópico hasta 8×
- **Carga asíncrona** — decodificación multihilo con precarga de ±3 imágenes
- **Cuadrícula de miniaturas virtualizada** — sólo se renderizan los mosaicos visibles; el tamaño de miniatura es configurable (128 / 256 / 512 / 1024 / auto)
- **Caché en disco** — miniaturas PNG comprimidas con invalidación basada en MD5 en `%LOCALAPPDATA%/Imervue/cache/thumbnails` (o `~/.cache/imervue/thumbnails`)
- **Reproducción de animaciones** — GIF / APNG con controles de reproducir / pausar / fotograma a fotograma / velocidad

### Modos de exploración

- **Cuadrícula** (predeterminado) — cuadrícula virtualizada de mosaicos con previsualización al pasar el cursor (retraso de 500 ms)
- **Lista (detalle)** — se alterna con `Ctrl+L`; columnas: Vista previa · Etiqueta · Nombre · Resolución · Tamaño · Tipo · Modificado
- **Deep Zoom** — doble clic en un mosaico; paneo/zoom fluido en GPU con superposición de minimapa
- **Vista dividida** (`Shift+S`) — dos imágenes lado a lado
- **Lectura de doble página** (`Shift+D`, `Ctrl+Shift+D` para manga de derecha a izquierda) — lector de páginas enfrentadas
- **Espejo multimonitor** (`Ctrl+Shift+M`) — ventana en pantalla secundaria
- **Modo cine** (`Shift+Tab`) — oculta toda la interfaz
- **Diálogo de comparación** — Lado a lado / Superposición (control alfa) / Diferencia (control de ganancia) / División A|B con separador arrastrable
- **Vistas Timeline / Calendar / Map** — agrupa la biblioteca por fecha de captura, navega en un calendario, traza fotos geoetiquetadas sobre Leaflet + OpenStreetMap

### Superposiciones en pantalla

- Histograma RGB (`H`)
- OSD con F8 (nombre de archivo / tamaño / tipo), HUD de depuración con Ctrl+F8 (VRAM / caché / hilos)
- Vista de píxeles (`Shift+P`) — con zoom ≥ 400 % muestra la cuadrícula de píxeles + RGB / HEX por píxel
- Modos de color (`Shift+M`) — Normal / Escala de grises / Invertir / Sepia vía GLSL

### Navegación

- Teclas de flecha, historial estilo navegador (`Alt+←/→`), salto aleatorio (`X`)
- Navegación entre carpetas (`Ctrl+Shift+←/→`)
- Ir a imagen por índice (`Ctrl+G`)
- Búsqueda difusa (`Ctrl+F` / `/`)
- **Paleta de comandos** (`Ctrl+Shift+P`) — búsqueda difusa de todas las acciones de menú
- Bucle automático al final de la carpeta
- Pinch-zoom en trackpad + deslizamiento horizontal para navegar

### Organización

- **Marcadores** — hasta 5000 rutas
- **Calificaciones** — 0-5 estrellas (`1`–`5`) + corazón de favorito (`0`)
- **Etiquetas de color** — rojo/amarillo/verde/azul/púrpura basado en banderas (`F1`–`F5`)
- **Culling** — bandera de 3 estados compatible con otros gestores de fotos XMP-aware (`P` = elegir, `Shift+X` = rechazar, `U` = quitar bandera); filtra por estado; borrado masivo de rechazadas; el culling automático elige el fotograma más nítido de cada grupo de casi-duplicados y rechaza el resto
- **Etiquetas jerárquicas** — rutas en árbol como `animal/cat/british`; los descendientes se emparejan automáticamente
- **Tags & Albums** con filtrado multietiqueta AND/OR
- **Álbumes inteligentes** — guarda consultas basadas en reglas y reaplica con un clic; los filtros abarcan extensión, resolución y **relación de aspecto**, **tamaño de archivo**, **piso / techo** de calificación, color, culling, etiquetas (incl. **exclusión**), **cámara / objetivo**, **regex / glob de nombre de archivo** y **antigüedad del archivo**, además de **exportar / importar** a un archivo JSON portable
- **Apilamiento de pares RAW+JPEG** — colapsa capturas con el mismo nombre base en un solo mosaico; el RAW sigue accesible como hermano
- **Notas por imagen** en la barra lateral EXIF — guardado con debounce, persiste entre sesiones
- **Bandeja de preparación** — cesta entre carpetas que sobrevive a los reinicios; mover / copiar / exportar en masa
- **Gestor de archivos de doble panel** — vista con dos árboles en panel doble
- **Sesiones / Diseños de espacio de trabajo** — toma una instantánea de las pestañas / selección / filtro / geometría de docks en `.imervue-session.json`; guarda diseños con nombre para configuraciones Browse / Develop / Export
- **Macros** — graba / reproduce lotes de acciones de calificación / favorito / color / etiqueta (`Alt+M` reproduce la última macro)
- **Insignias y densidad de miniaturas** — franja de color, favorito, marcador, estrellas de calificación; relleno Compacto / Estándar / Relajado
- **Arrastrar a aplicaciones externas** — arrastra un mosaico directamente al Explorer / Chrome / Discord
- **Carpetas / imágenes recientes** rastreadas; la última carpeta se restaura automáticamente al iniciar

### Ordenación y filtrado

- Ordena por nombre / modificado / creado / tamaño / resolución (asc o desc)
- Filtra por extensión, etiqueta de color, calificación, etiqueta/álbum, estado de culling
- **Filtro avanzado** — resolución / tamaño de archivo / orientación / rango de fecha de modificación
- Diálogo de **filtro multietiqueta** con lógica booleana AND / OR

### Búsqueda

- **Búsqueda difusa de nombres** con resaltado de subcadenas
- **Encontrar imágenes similares** — pHash (DCT de 64 bits) con distancia de Hamming ajustable
- **Búsqueda en biblioteca** — índice SQLite multi-raíz con un DSL de consulta compacto: palabras clave, etiquetas (incl. negación), calificaciones, color, extensión, lugar, culling, favoritos, relación de aspecto, antigüedad, tamaño, dimensiones, cámara / objetivo, y regex / glob de nombre de archivo
- **Encontrar similares (average hash)** — pHash y dHash se complementan con un average-hash (aHash) opcional como métrica adicional de casi-duplicados
- **Búsqueda semántica (CLIP)** — consultas en lenguaje natural ("golden retriever en la nieve") vía embeddings en caché; se desactiva con gracia si `open_clip_torch` + `torch` no están instalados
- **Auto-etiquetado** — clasificación heurística con upgrade opcional CLIP ONNX

### Metadatos

- **Barra lateral EXIF** con grupos colapsables + tira en línea de 0-5 estrellas
- Diálogo **editor EXIF**
- **Editor de palabras clave** — título / autor / descripción / palabras clave, con **sugerencias de etiquetas relacionadas** derivadas de la coocurrencia de etiquetas y expansión de vocabulario controlado (una palabra clave hoja aplica automáticamente sus ancestros + sinónimos desde un vocabulario jerárquico editable)
- Diálogo de **información de imagen** (dimensiones / tamaño / fechas)
- **Sidecars XMP** (archivos `.xmp` acompañantes) — ida y vuelta de calificación / título / descripción / palabras clave / etiqueta de color para interoperabilidad con otros gestores de fotos XMP-aware (XML seguro vía `defusedxml`)
- **Editor de geoetiquetas GPS** — lee EXIF GPS existente, escribe nuevas lat/lon vía piexif (JPEG)
- **Renombrado por lotes con tokens** — plantillas con vista previa en vivo como `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Exportar metadatos a CSV / JSON** — una fila por imagen incluyendo culling / calificación / etiquetas / notas

### Herramientas adicionales (pestaña Imervue — procesamiento por lotes)

Se accede desde el menú **Tools**; organizadas en submenús agrupados por función:

- **Lote** — Conversión de formato · Eliminación EXIF · Saneador de imágenes (re-renderiza para quitar datos ocultos) · Organizador de imágenes (ordena en subcarpetas por fecha / resolución / tipo / tamaño) · Renombrado por lotes con tokens
- **IA / Heurística** — Escalado de imágenes por IA (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Encontrar imágenes duplicadas · Encontrar imágenes similares · Auto-etiquetado · Detección de rostros (cascada Haar)
- **Biblioteca y metadatos** — Búsqueda en biblioteca · Álbumes inteligentes · Etiquetas jerárquicas · Exportar metadatos · Sidecars XMP · Geoetiqueta GPS

### Integración con el sistema

- Menú contextual de Windows **Abrir con Imervue** con el clic derecho (asociación de archivos basada en registro)
- Monitorización de carpetas con `QFileSystemWatcher` (auto-refresco al cambiar)
- Sistema de notificaciones tipo toast (info / éxito / advertencia / error)
- Sistema de plugins con descargador de plugins en línea (ver [Sistema de plugins](#sistema-de-plugins))

---

## Modify — Revelado no destructivo

La pestaña **Modify** es la estación de revelado. Cada ajuste vive en una **recipe** por imagen almacenada junto al archivo — los píxeles originales en disco nunca se sobrescriben hasta que uses explícitamente **Export** o **Save As**.

### Controles deslizantes de revelado

- Balance de blancos — temperatura / tinte
- Regiones tonales — sombras / medios tonos / luces
- Exposición / contraste / saturación / vibrancia
- Recorte, rotación, volteo horizontal / vertical
- Todos los ajustes permanecen no destructivos y se almacenan en la recipe

### Curvas y LUT

- **Editor de curva tonal** — curva RGB arrastrable más R / G / B por canal con interpolación cúbica monótona
- **Aplicar LUT .cube** — carga cualquier LUT 3D de Adobe (hasta 64³), interpola trilinealmente, mezcla con un control de intensidad
- **Split Toning** — matiz + saturación de sombras / luces basado en banderas con pivote de balance

### Efectos creativos

- **Solarize** — inversión tonal estilo cuarto oscuro (umbral + mezcla)
- **Diffuse Glow / Orton** — resplandor suave de luces con enfoque difuso (cantidad / radio / umbral de luces)
- **Gradient Map** — luminancia → paleta, con un modo opcional de interpolación perceptual (OkLCH) que mantiene vivos los gradientes saturados a través del punto medio en lugar de agrisarlos
- **Ordered Dither** — cuantización por matriz de Bayer a N niveles (extremos preservados)
- **Densidad graduada (Graduated Density)** — degradado ND lineal por ángulo / dureza / desplazamiento con tinte opcional, para cielos y primeros planos
- **Ecualizador de tono (Tone Equalizer)** — exposición independiente por zona de luminancia (de sombras a luces) sobre una máscara suavizada
- **Ecualizador de detalle (Detail Equalizer)** — reponderar el contraste por banda de frecuencia (textura fina vs. contraste grueso), más allá de un único control de claridad
- **Mapeo tonal fílmico (Filmic Tone Map)** — caída de luces pura Reinhard / Hable con contraste pivoteado y restauración de saturación, para exposiciones únicas de alto contraste
- **Velvia (Velvia)** — refuerzo de saturación ponderado por luminancia que intensifica los colores apagados sin tocar las sombras
- **Negativo de película (Film Negative)** — invierte un negativo de color escaneado, descontando la base naranja de la película, con gamma de salida
- **Defringe (Defringe)** — desatura los flecos púrpura / verde de aberración cromática en bordes de alto contraste
- **Relieve (Emboss)** — relieve de luz direccional a partir de un campo de altura de luminancia
- **Coordenadas polares (Polar Coordinates)** — envuelve un fotograma en un disco o lo desenrolla (tiny-planet / inversión polar)
- **Caleidoscopio (Kaleidoscope)** — refleja una cuña angular en simetría de n pliegues
- **Vidrio esmerilado (Frosted Glass)** — dispersión local de píxeles determinista basada en semilla
- **Predefinidos de revelado** — guarda una recipe y luego aplícala por completo o fusiona solo sus ajustes activos sobre otras imágenes (conservando el recorte propio de cada imagen, etc.)

### Ajustes locales

- **Máscaras de pincel / radial / gradiente lineal** con deltas de exposición / brillo / contraste / saturación / balance de blancos por máscara + control de difuminado
- Las máscaras se mezclan de forma no destructiva a través de la cadena de revelado

### Retoque y transformación

- **Pincel de saneamiento** — puntos circulares, inpainting de OpenCV (Telea o Navier-Stokes)
- **Tampón de clonar** — Shift+clic en la fuente, blit con difuminado al destino
- **Recortar / Enderezar** — rectángulo de recorte normalizado más enderezamiento a ángulo arbitrario que recorta automáticamente al rectángulo interno más grande
- **Auto-enderezar** — detección de horizonte / vertical mediante líneas de Hough
- **Corrección de lente** — distorsión radial pura en numpy (barril / cojín), elevación de viñeta, aberración cromática por canal
- **Reducción de ruido / Enfoque** — denoise bilateral con preservación de bordes + enfoque con unsharp mask
- **Cielo / Fondo** — sustituye el cielo detectado por un gradiente o elimina el fondo (relleno transparente o blanco); upgrade opcional `rembg` / U²-Net

### Multi-imagen

- **Fusión HDR** — combina exposiciones en horquilla mediante Mertens fusion de OpenCV (con pre-alineación AlignMTB)
- **Costura panorámica** — `Stitcher` de OpenCV en modo panorama o scans, recorte automático de bordes negros
- **Apilamiento de foco** — mapa de foco por varianza Laplaciana + mezcla gaussiana con alineación ECC opcional

### Salida

- **Marca de agua superpuesta** — texto o imagen, 9 posiciones de anclaje, opacidad, escala; se aplica solo al exportar
- **Predefinidos de exportación** — flujos de un solo clic Web 1600 / Print 300 dpi / Instagram 1080
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF con control de calidad para formatos con pérdida
- **Operaciones por lotes** — renombrar, mover/copiar, rotar imágenes seleccionadas
- **PDF de hoja de contactos** — cuadrícula multipágina con leyendas (A4 / A3 / Letter / Legal)
- **Galería web HTML** — carpeta autocontenida con `index.html` + miniaturas JPEG + lightbox en línea
- **Presentación MP4** — vídeo H.264 con FPS / segundos por imagen / transiciones de fundido / disolución / deslizamiento / barrido configurables (`imageio-ffmpeg`)
- **Diseño de impresión** — hoja PDF multipágina con tamaño de página / orientación / cuadrícula / márgenes / encuadernación / marcas de corte configurables
- **Soft Proof** — carga un perfil ICC, simula la gama de destino, resalta en magenta los píxeles fuera de gama
- **Copias virtuales** — instantáneas de recipe con nombre por imagen; cambia entre estilos sin perder el original

### Editores externos

Registra programas (tu editor de imágenes / … / …) en **File > External Editors…** y lánzalos sobre la imagen actual desde **File > Open in External Editor**.

---

## Paint — Editor rasterizado con todas las funciones

La pestaña **Paint** es un estudio de pintura rasterizada con todas las funciones, integrado como su propia `QMainWindow` con menús, tira de herramientas a la izquierda, barra de opciones sensible al contexto, y columna de docks pestañeada a la derecha. Edición de documentos multipestaña — abre muchos dibujos a la vez, cada uno con su propia pila de deshacer.

### Herramientas (27)

Pincel · Borrador · Relleno · Cuentagotas · Rect / Lazo / Varita / Selección rápida · Mover · Texto · Gradiente · Desenfoque · Difuminar · Dodge · Burn · Sponge · Pluma · Tampón de clonar · Bocadillo · Rectángulo · Elipse · Línea · Polígono · Recorte · Transformar · Mano · Zoom

El trío de tonificación de cuarto oscuro — **Dodge** (aclarar), **Burn** (oscurecer) y **Sponge** (saturar / desaturar) — pinta ajustes locales de tono y croma, ponderados por el pincel y una máscara de sombras / medios tonos / luces.

Atajos de una letra: `B / E / G / I / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` para variantes de forma.

### Pinceles

Pluma / rotulador / lápiz / fluorescente / aerosol / caligrafía / acuarela / carboncillo / crayón, con controles de Tamaño / Opacidad / Dureza / Densidad / Modo de mezcla. Editor de curva de presión, captura de punta de pincel desde una selección, importar / exportar predefinidos de pincel.

### Capas

Panel de capas completo con miniaturas, alternadores de visibilidad, arrastrar para reordenar, modos de mezcla, opacidad, búsqueda, capas vectoriales, capas de 1 bit, **máscaras de capa** (añadir / desde selección / invertir / aplicar), **máscaras de recorte**, **efectos de capa** (sombra paralela / resplandor externo / trazo). Dividir capa por color, predefinidos de mapa de gradiente.

### Selección

Rect / Lazo / Varita / Selección rápida con modos **Reemplazar / Añadir / Restar / Intersecar** y difuminado. **Modo máscara rápida** (`Q`) para flujos de pintar-la-máscara. Diálogo **Trazar selección**.

### Animación y manga

- **Animación** — dock de línea de tiempo de fotogramas con instantáneas, reproducción, superposición de papel cebolla, exportación MP4 / GIF
- **Herramientas de manga** — Cortador de viñetas · Capas de trama · Estampar números de página · Líneas de velocidad (Radial / Paralela / Explosión) · Destello de acción · Herramienta de bocadillo

### Filtros y ayudas de vista

- **Filtros** — Niveles · Curvas · Posterizar · Umbral · Auto Balance de Color · Grano de Película · Mediotonos (cada uno con diálogo de vista previa en vivo)
- **Ayudas de vista** — Cuadrícula de píxeles · Ajustar a píxel · Ajustar a bordes · Papel cebolla · Guías de sangrado · Rotación de lienzo (`Ctrl+Shift+H` rota antihorario)

### Docks (10, pestañeados)

Color · Pincel · Capa · Navegador · Biblioteca de materiales · Historial · Muestrario · Referencia · Histograma · Animación. Cada dock es movible / flotante. **Settings > Workspace Layouts** guarda y recupera disposiciones con nombre.

### E/S de archivos

- Abrir / guardar **PSD** (Photoshop) con ida y vuelta completa de capas
- Exportar PNG / JPEG / WebP, además de exportación multipágina de cómic a **CBZ** o **PDF**
- Instantáneas de auto-guardado con restauración de la última

### UX para usuarios avanzados

- **Tab** alterna todos los docks para pintar sin distracciones
- `Ctrl+Tab` recorre las pestañas
- `,` / `.` recorre los tipos de pincel
- `0`-`9` establecen la opacidad del pincel en pasos del 10 %
- `Alt+[` / `Alt+]` desplazan la capa activa
- El clic derecho en el lienzo abre un menú rápido de Deshacer / Rehacer / Seleccionar todo / Deseleccionar / Ajustar / 100 %
- Asterisco de modificado por pestaña, confirmaciones tipo toast de deshacer / rehacer, mensaje de recuperación de auto-guardado al iniciar

Pulsa `E` desde Deep Zoom para enviar la imagen actual directamente a una nueva pestaña Paint.

---

## Puppet — Animación 2D con esqueleto

La pestaña **Puppet** es un sistema de animación 2D con esqueleto construido desde cero. Hace lo que Live2D hace (rigs de deformación de malla, parámetros, animaciones, física, expresiones, pose, sincronización labial, seguimiento facial por webcam) pero **sin SDK propietario**, **sin `live2d-py`**, y con un formato de archivo `.puppet` completamente abierto y documentado en `Imervue/puppet/FORMAT.md`.

> **Tutorial completo**: [`puppet_guide.md`](../puppet_guide.md) cubre el
> flujo de extremo a extremo tanto para streaming en vivo (OBS / NDI / cámara
> virtual) como para producción de animación (grabación / edición de línea de
> tiempo / exportación MP4). Versiones en chino en
> [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) y
> [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md).

### Formato de archivo

`.puppet` es un contenedor zip:

- `puppet.json` — manifiesto (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — texturas de atlas
- `motions/*.json` — pistas de fotogramas clave
- `expressions/*.json` — superposiciones de parámetros
- `physics.json` — configuración del rig de Verlet

Basado en JSON, comparable a mano, sin binarios propietarios.

### Renderizador

`QOpenGLWidget` con dibujo de triángulos texturizados por vertex-array en draw_order, modos de mezcla por drawable (normal / aditivo / multiplicar), exclusividad de pose-group, proyección ortográfica en espacio de imagen, fondo de cuadros de transparencia con GL_REPEAT, zoom con rueda + paneo con arrastre del botón medio. Optimizado para rigs grandes — March 7th (307 drawables / 2965 vertex morphs) corre a 60 FPS en CPU.

### Autoría

- **Importar PNG** → genera automáticamente una malla triangulada en cuadrícula que respeta el alfa
- Acciones de barra de herramientas **Add Rotation Deformer** (ancla + ángulo) / **Add Warp Deformer** (lattice bezier de filas × columnas)
- **Add Parameter** → establece formas clave en los extremos del control vía **Set Key** en el dock de parámetros
- **Editor de mallas** — alterna Edit Mesh para arrastrar vértices; los clics dentro de 8 px se ajustan al más cercano
- **Save As…** escribe el rig completo a un zip `.puppet`

### Runtime

- **Rig de parámetros** — cada parámetro mantiene una lista de claves mapeando un valor de control a una instantánea parcial de forma de deformer; el runtime muestrea e interpola linealmente campo a campo
- **Reproducción de motion** — dock inferior con lista de motion + Play / Pause / Stop / Loop / scrub; el muestreador de curvas respeta segmentos `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` (resolución time → param iterada con Newton); fundido de entrada / salida por motion
- **Expresiones** — pila de superposiciones de parámetros `additive` / `multiply` / `overwrite`
- **Grupos de pose** — visibilidad de drawable mutuamente excluyente (cambios de arma, variantes de forma de boca)
- **Física** — cadenas de péndulo Verlet para pelo / ropa / lazos; el parámetro de entrada mueve el ancla de la cadena, gravedad + amortiguación + resortes por partícula la devuelven al reposo
- **Vertex morphs** — mezcla lineal estilo Cubism entre rest y deltas ±extremos; numpy vectorizado por fotograma a 60 FPS
- **Claves de opacidad** — curvas alfa controladas por parámetro; permite que mallas de pose alternativa hagan fundido al activarse un parámetro de gesto

### Entrada en vivo

- Arrastre del cursor → parámetros de ángulo de cabeza
- Auto-parpadeo en curva coseno open → close → open
- Sincronización labial por micrófono vía RMS de `sounddevice` → `ParamMouthOpenY` (dep opcional)
- Seguimiento facial por webcam vía OpenCV + MediaPipe FaceMesh → yaw / pitch / roll de cabeza + apertura de ojos / boca (deps opcionales)
- Grabación de motion personalizada — captura los valores de parámetros a 30 Hz mientras mueves los controles / miras a la webcam / dejas correr la física; los hornea en un Motion de segmentos lineales listo para reproducir / repetir / guardar

### Interoperabilidad con Cubism

El **Cubism Native SDK** puede enchufarse (DLL aportado por el usuario — la Free Material License de Live2D prohíbe redistribuirlo) para convertir cualquier modelo `.moc3` en un zip `.puppet`. El convertidor ejecuta un barrido de muestreo y reconstrucción que captura tanto los deltas de vertex-morph como las transiciones de visibilidad accionadas por parámetro, así que los cambios de gesto (signo de paz / cubrirse la cara / foto …) sobreviven intactos a la conversión.

### Salida

- **Capture frame…** guarda un PNG del lienzo actual vía `glReadPixels`
- **Record…** alterna un bucle de fotogramas a 30 FPS hacia GIF / WebM / MP4 vía `imageio`
- **Cámara virtual** — expone el lienzo de puppet como webcam del sistema
- **Salida NDI** — transmite el puppet como fuente NDI en la LAN
- **Servidor de API VTube Studio** — API WebSocket opcional para clientes compatibles con VTS

### Streaming en vivo a OBS

Dos rutas soportadas. Elige A para "que funcione sin más", B si quieres
la menor latencia y la mejor calidad en una LAN rápida.

#### A. Cámara virtual (la más fácil)

El lienzo de puppet aparece como una webcam que OBS toma vía su fuente
estándar Video Capture Device.

1. `pip install pyvirtualcam`
2. Instala el driver de la plataforma:
   - **Windows**: OBS Studio 26+ trae el driver *OBS Virtual Camera*.
     Tras instalar OBS, ábrelo una vez y haz clic en **Start Virtual
     Camera** en el panel inferior derecho — eso registra el driver
     a nivel sistema para que `pyvirtualcam` pueda encontrarlo.
   - **macOS**: OBS para Mac trae una system extension de OBS Virtual
     Camera. La primera ejecución pedirá activarla en Configuración del
     Sistema → Privacidad y Seguridad.
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (instala primero `v4l2loopback-dkms`).
3. En la pestaña Puppet, abre tu rig y luego activa **Output > Virtual
   camera**. La barra de estado muestra el nombre exacto del dispositivo a elegir.
4. En OBS: **Sources > + > Video Capture Device**, elige el dispositivo
   nombrado en el paso 3 (típicamente *OBS Virtual Camera*).

Imervue limita el lado más largo de la salida de streaming a 1080 px
para que los lienzos nativos de Cubism (March 7th es 3503×7777) no
sean rechazados por el driver de cámara virtual DirectShow. Se preserva
la relación de aspecto; OBS puede escalar más si es necesario.

##### ¿Por qué el fondo es magenta? (y cómo quitarlo)

Las cámaras virtuales corren sobre **DirectShow** (Windows) / **AVFoundation**
(macOS) / **v4l2loopback** (Linux). Los tres transportes son
**sólo RGB — sin canal alfa**. La fuente *Video Capture Device* de OBS
trata lo que envíe la cámara como RGB opaco, así que el color que
Imervue ponga detrás del personaje es el que OBS muestra.

Imervue elige **magenta `#FF00FF`** como ese fondo porque
es el color estándar de la industria para chroma-key: casi nunca
aparece en tonos de piel, cabello o color de ojos, así que el umbral
de chroma-key puede ser muy amplio sin comerse al personaje.

Para quitar el magenta en OBS:

1. Clic derecho en la fuente *Video Capture Device* que añadiste → **Filtros**
2. En el panel **Effect Filters** abajo a la izquierda → **+** → **Color Key**
3. Configura:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF` (o R = 255 / G = 0 / B = 255)
   - **Similarity**: empieza en `80`, sube hacia `200–300` si todavía
     se ven bordes magenta. Más alto = eliminación más agresiva.
   - **Smoothness**: `30–50` suaviza el borde para que el corte no
     se vea duro / pixelado.
4. Cierra el diálogo. OBS adjunta el filtro a la fuente, así que
   la próxima vez que actives la cámara virtual el chroma-key
   se aplica automáticamente.

Si el personaje tiene magenta en su paleta (raro pero posible
en arte de vestuario / props), el chroma key también se comerá esos píxeles.
Cambia a la ruta NDI más abajo — NDI lleva el canal alfa
directamente así que no se necesita chroma-keying.

**Solución de problemas: sigo viendo magenta en OBS**

- Verifica que el filtro Color Key esté adjunto a la fuente **Video
  Capture Device**, no a una Scene. Los filtros sobre la fuente viajan
  con ella; los filtros sobre la Scene se aplican encima después de
  que la fuente se haya renderizado.
- Comprueba que el hex es `FF00FF` exactamente — `FF00FE` o similar no
  cazará todos los píxeles magenta.
- Sube *Similarity* a `300` si hay un halo fino de píxeles magenta
  en el contorno del personaje. Los bordes vienen de la
  interpolación GL_LINEAR contra el fondo magenta; una tolerancia
  más amplia se los come.

#### B. NDI (menor latencia, calidad profesional)

NDI (Network Device Interface de Newtek) lleva el puppet sobre
la LAN con latencia sub-50 ms y el canal alfa intacto.

1. Descarga e instala **NDI Tools** desde
   <https://ndi.video/tools/> (incluye el runtime NDI).
2. `pip install ndi-python`
3. Instala el plugin **obs-ndi** en OBS:
   <https://github.com/obs-ndi/obs-ndi/releases>
4. En la pestaña Puppet, activa **Output > NDI output**. La barra de
   estado reporta el nombre de la fuente NDI (por defecto *Imervue Puppet*).
5. En OBS: **Sources > + > NDI Source**, elige la fuente del
   paso 4.

NDI transmite a la misma resolución limitada a 1080 que la ruta A, pero
entrega RGBA — el render fuera de pantalla produce un fondo transparente
fuera del personaje, NDI envía el canal alfa
intacto, y OBS / vMix componen el puppet directamente sobre tu
escena sin ningún pase de chroma-key.

#### C. Captura de ventana (respaldo)

OBS **Sources > + > Window Capture** puede tomar la ventana de Imervue
directamente, sin dependencias extra. Menor calidad y tienes
que recortar la interfaz tú mismo, pero funciona en
máquinas bloqueadas donde no puedes instalar drivers.

### Demo

Un rig listo para usar está en [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — un personaje Cubism Live2D de 307 drawables convertido dentro del árbol. Ábrelo vía **Open Puppet…** para ver el rig aparecer centrado; haz clic en cualquiera de las 18 motions (grupo Idle + grupo Gesture) para reproducir. Los gestos cubren signo de paz, cubrirse la cara, foto, sonrojo, cara oscura, llorar, sudor, estrellas, estrella fugaz — todo gesto con nombre que define el rig.

---

## Desktop Pet — superposición sin marco

Pestaña 5 — la **Desktop Pet** coloca cualquier personaje `.puppet` sobre tu escritorio como una superposición sin marco y transparente. La pestaña en sí es el panel de control; el personaje real flota encima (o detrás) de tus otras ventanas. Todo lo que puedes hacer con un rig en la pestaña Puppet — motions, expresiones, física, drivers de idle, entrada por webcam / micrófono — funciona también aquí.

### Qué puedes hacer

| Característica | Función |
|---|---|
| Superposición sin marco | Sin cromo de ventana, sin entrada en la barra de tareas — solo el personaje en tu escritorio. |
| Fondo transparente | Lo que el personaje no cubre deja ver el escritorio a través. |
| Arrastrar para mover | Arrastra con el botón izquierdo el personaje a otro sitio. Suéltalo cerca de un borde de pantalla para **encajarlo** pegado a él. |
| Modo clic transparente | Haz que la mascota ignore tu ratón para que puedas seguir trabajando bajo ella. |
| Bloquear posición | Congela la mascota para que los arrastres accidentales no puedan moverla. |
| Siempre debajo | Coloca la mascota detrás de todas las demás ventanas — sensación de widget de escritorio en lugar de siempre encima. |
| Ocultar en pantalla completa | Se oculta automáticamente mientras otra aplicación (juego / vídeo / presentación) está en pantalla completa en el mismo monitor; vuelve cuando termina la pantalla completa. |
| Pausa al ocultarse | La mascota deja de animarse mientras es invisible — cero CPU cuando está fuera de pantalla. |
| Tamaños predefinidos | Pequeño / mediano / grande. Redimensiona alrededor del centro para que la mascota no salte a través de la pantalla. |
| Control deslizante de opacidad | Atenúa la mascota del 10 % al 100 % para que pueda ser un adorno discreto del escritorio. |
| Recuerda dónde la pusiste | Arrastra la mascota a tu esquina favorita; vuelve allí en el siguiente lanzamiento. |

### Interacciones de clic

- **Clic izquierdo sobre el cuerpo** — si el rig define un hit area (p. ej. tocar la cabeza), se reproduce el motion correspondiente. Si no, la mascota te saluda con un bocadillo.
- **Clic derecho en cualquier sitio** — abre un menú contextual con: Ocultar mascota, Drivers en vivo, Reproducir motion (lista de todos los motions del rig), Aplicar expresión, Bloquear posición, Clic transparente, Siempre debajo, Ocultar en pantalla completa, Bocadillo, Tamaño.
- **Icono de la bandeja del sistema** — clic izquierdo para alternar visibilidad, clic derecho para Mostrar/Ocultar, Clic transparente, Abrir puppet, Ocultar mascota.

### Drivers en vivo

Elige cualquier combinación desde la pestaña o el menú del clic derecho. Cada uno está desactivado por defecto — activa solo lo que quieras.

- **Auto idle** — respiración + leve deriva para que el personaje se sienta vivo.
- **Motions de idle** — recorre aleatoriamente los motions del grupo idle del rig.
- **Auto-parpadeo** — cierre cíclico natural de los ojos cada pocos segundos.
- **Seguir cabeza con arrastre** — la cabeza gira para seguir tu cursor.
- **Sincronización labial por micrófono** — la boca se abre con tu voz (necesita `sounddevice`).
- **Seguimiento por webcam** — tu cabeza / ojos / boca controlan los del puppet (necesita `opencv-python` y `mediapipe`).

### Cómo empezar

1. Cambia a la pestaña **Desktop Pet**.
2. Haz clic en **Load bundled March 7th** para usar el personaje incluido, o en **Open Puppet…** para elegir tu propio archivo `.puppet`.
3. Marca **Show pet on desktop**.
4. Arrastra el personaje a donde quieras; elige los drivers que quieras; ajusta opacidad / tamaño.
5. Haz clic derecho en cualquier momento para el menú de acción rápida, o usa el icono de la bandeja del sistema para ocultar la mascota sin tener que encontrar la pestaña.

Todo lo que ajustes — posición, drivers, opacidad, clic transparente, tamaño — se recuerda entre lanzamientos.

---

## Atajos de teclado y ratón

### Navegación (todos los modos)

| Atajo | Acción |
|----------|--------|
| Teclas de flecha | Desplazar cuadrícula / Cambiar imagen (Izq/Der en deep zoom) |
| Shift + Flecha | Desplazamiento fino (medio paso) |
| Ctrl+Shift+←/→ | Saltar a la carpeta hermana anterior / siguiente con imágenes |
| Alt+← / Alt+→ | Historial atrás / adelante |
| Ctrl+G | Ir a imagen por índice |
| X | Saltar a una imagen aleatoria |
| Home | Restablecer zoom y paneo al origen |
| Ctrl+F o / | Abrir diálogo de búsqueda difusa |
| Ctrl+Shift+P | Abrir Paleta de comandos |
| Alt+M | Reproducir la última macro sobre la selección actual |
| S | Abrir diálogo de presentación |
| Ctrl+Z | Deshacer |
| Ctrl+Shift+Z / Ctrl+Y | Rehacer |

### Deep Zoom / imagen única

| Atajo | Acción |
|----------|--------|
| F | Alternar pantalla completa |
| Shift+Tab | Alternar modo cine (ocultar toda la interfaz) |
| R / Shift+R | Rotar horario / antihorario |
| E | Abrir editor de imagen (pestaña Modify) |
| W / Shift+W | Ajustar a ancho / alto |
| H | Alternar superposición de histograma RGB |
| F8 / Ctrl+F8 | Superposición OSD / HUD de depuración |
| Shift+P | Alternar vista de píxeles (zoom ≥ 400 % muestra cuadrícula + RGB) |
| Shift+M | Recorrer modos de color (Normal / Escala de grises / Invertir / Sepia) |
| B | Alternar marcador |
| Ctrl+C / Ctrl+V | Copiar / pegar imagen al/desde portapapeles |
| 0 / 1-5 | Alternar favorito / calificación rápida |
| F1-F5 | Etiqueta de color rápida (rojo / amarillo / verde / azul / púrpura) |
| P / Shift+X / U | Culling: Elegir / Rechazar / Quitar bandera |
| Shift+S | Vista dividida |
| Shift+D / Ctrl+Shift+D | Doble página (LTR / RTL) |
| Ctrl+Shift+M | Ventana espejo multimonitor |
| Delete | Mover a la papelera (reversible) |
| Escape | Salir de deep zoom / Salir de pantalla completa |

### Reproducción de animación (GIF / APNG)

| Atajo | Acción |
|----------|--------|
| Espacio | Reproducir / Pausar |
| , (coma) / . (punto) | Fotograma anterior / siguiente |
| [ / ] | Disminuir / aumentar velocidad de reproducción |

### Cuadrícula de mosaicos

| Atajo | Acción |
|----------|--------|
| Ctrl+L | Alternar Cuadrícula ↔ Lista |
| Pasar el cursor (500 ms) | Popup de vista previa al pasar |
| Delete | Eliminar mosaicos seleccionados |
| Escape | Deseleccionar todo |

### Ratón / trackpad

| Acción | Comportamiento |
|--------|----------|
| Clic izquierdo | Seleccionar mosaico o abrir imagen |
| Arrastre izquierdo | Selección rectangular múltiple en cuadrícula |
| Pulsación larga (500 ms) | Entrar en modo de selección de mosaicos |
| Arrastre del botón medio | Paneo en deep zoom |
| Rueda de desplazamiento | Acercar/alejar o desplazar |
| Clic derecho | Menú contextual |
| Pellizco | Acercar/alejar en deep zoom |
| Deslizamiento horizontal | Imagen anterior / siguiente |

### Pestaña Paint (además de los anteriores)

| Atajo | Acción |
|----------|--------|
| B / E / G / I | Pincel / Borrador / Relleno / Cuentagotas |
| V / T / U / R | Mover / Texto / Gradiente / Selección rectangular |
| P / S / C / Z / H | Pluma / Difuminar / Clonar / Zoom / Mano |
| Q | Alternar modo máscara rápida |
| Tab | Alternar todos los docks |
| Ctrl+Tab | Recorrer pestañas Paint |
| , / . | Recorrer tipos de pincel |
| 0-9 | Opacidad de pincel en pasos del 10 % |
| Alt+[ / Alt+] | Bajar / subir un paso la capa activa |

---

## Estructura de menús

### File

- New Window
- Open Image / Open Folder
- Recent (carpetas + imágenes)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — guardar / cargar / renombrar diseños de ventana con nombre
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (atajos personalizables)
- Exit

### Tools (herramientas adicionales — organizadas en 8 submenús agrupados)

- **Lote** — Conversión de formato · Eliminación EXIF · Saneador de imágenes · Organizador de imágenes · Renombrado por lotes con tokens
- **Biblioteca y metadatos** — Búsqueda en biblioteca · Álbumes inteligentes · Encontrar similares / duplicadas · Auto-etiquetado · Etiquetas jerárquicas · Exportar metadatos · Sidecars XMP · Geoetiqueta GPS
- **Vistas** — Timeline · Calendar · Map
- **Flujo de trabajo** — Culling · Bandeja de preparación · Copias virtuales · Gestor de archivos de doble panel · Macros
- **Exportar** — PDF de hoja de contactos · Galería web · Vídeo de presentación (MP4) · Diseño de impresión
- **Revelado (no destructivo)** — Curva tonal · LUT .cube · Split Toning · Máscaras de ajuste local · Densidad graduada · Velvia · Relieve · Defringe · Negativo de película · Mapeo tonal fílmico · Ecualizador de tono / detalle · Polar · Caleidoscopio · Vidrio esmerilado · Soft Proof
- **Retoque y transformación** — Escalado de imágenes por IA · Reducción de ruido / enfoque · Pincel de saneamiento · Tampón de clonar · Detección de rostros · Cielo / Fondo · Recortar / Enderezar · Auto-enderezar · Corrección de lente
- **Multi-imagen** — Fusión HDR · Costura panorámica · Apilamiento de foco

### View / Sort / Filter / Language / Plugins / Instructions

(Menús estándar — consulta la aplicación para todas las opciones.)

### Menú contextual del clic derecho

Navegación · Acciones rápidas (revelar / copiar ruta / copiar imagen) · Transformaciones · Operaciones por lotes · Borrar · Fondo de pantalla · Comparar / Presentación · Exportar · Herramientas adicionales · Marcadores · Información de imagen · Elementos aportados por plugins.

---

## Sistema de plugins

Imervue soporta plugins de terceros. Consulta [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) para la referencia completa.

### Inicio rápido

1. Crea una carpeta dentro de `plugins/` en la raíz del proyecto
2. Define una clase que extienda `ImervuePlugin`
3. Regístrala en `__init__.py` con `plugin_class = YourPlugin`
4. Reinicia Imervue

### Hooks

| Hook | Disparador |
|------|---------|
| `on_plugin_loaded()` | Tras instanciar el plugin |
| `on_plugin_unloaded()` | Al cerrar la aplicación |
| `on_build_menu_bar(menu_bar)` | Tras construir la barra de menú predeterminada |
| `on_build_main_tabs(tabs)` | Tras añadir las cuatro pestañas integradas |
| `on_build_context_menu(menu, viewer)` | Al abrirse el menú del clic derecho |
| `on_image_loaded(path, viewer)` | Tras cargar imagen en deep zoom |
| `on_folder_opened(path, images, viewer)` | Tras abrir carpeta en cuadrícula |
| `on_image_switched(path, viewer)` | Al navegar entre imágenes |
| `on_image_deleted(paths, viewer)` | Tras eliminar imagen(es) por borrado suave |
| `on_key_press(key, modifiers, viewer)` | Al pulsar tecla (devuelve True para consumir) |
| `on_app_closing(main_window)` | Antes de cerrar la aplicación |
| `get_translations()` | Proporcionar cadenas de i18n |

### Descargador de plugins

**Plugins > Download Plugins** abre el descargador en línea. Repositorio fuente: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## Servidor MCP

Imervue trae un servidor [Model Context Protocol](https://modelcontextprotocol.io) integrado para que los asistentes de IA (Claude Code / Desktop, Cursor, Cline, …) puedan invocar a los helpers de lógica pura del proyecto sin una GUI en ejecución. Sin Qt; un comando:

```sh
python -m Imervue.mcp_server
```

### Herramientas

Herramientas seleccionadas (56 en total — lista completa en la documentación). Cada herramienta
anuncia un `outputSchema` JSON y `annotations` de solo lectura / destructivas, devuelve su
resultado como `structuredContent`, y las herramientas de larga duración transmiten
`notifications/progress`.

| Herramienta | Propósito |
|------|---------|
| `list_images` | Lista archivos de imagen en una carpeta (recursión opcional) |
| `read_image_metadata` / `read_xmp_tags` | Dimensiones, formato, EXIF, sidecar XMP (calificación, etiqueta, palabras clave) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | Análisis sin referencia: estadísticas por canal, colorido/entropía/contraste, histograma + recorte, puntuación de desenfoque |
| `image_thumbnail` / `ocr_text` / `find_similar` | Vista previa en base64, texto con Tesseract, grupos de casi-duplicados por hash perceptual (con progreso) |
| `convert_format` | Convertir entre PNG / JPEG / WebP / TIFF / BMP (+ HEIC / AVIF / JXL opcionales) |
| `apply_watermark` / `apply_frame` | Estampar una marca de agua de texto o un marco mate / Polaroid + leyenda |
| `build_collage` | Componer imágenes en un montaje en cuadrícula (con progreso) |
| `crop_image` / `resize_image` / `rotate_image` | Recorte por píxeles, redimensión que preserva el aspecto, rotación / volteo sin pérdida |
| `collection_stats` | Resumen de calificación / favorito / etiqueta de color / culling de una carpeta |
| `search_images` | Filtra una carpeta con el DSL de consultas de álbumes inteligentes (ruta / EXIF / tamaño / dimensiones) |
| `extract_gps` / `dominant_colors` | Lee coordenadas GPS de EXIF (encadena con `reverse_geocode`); paleta de colores por median-cut (rgb / hex / proporción) |
| `error_level_analysis` | Mapa de manipulación por recompresión JPEG como un PNG data URI |
| `solarize_image` / `glow_image` | Aplica una inversión tonal solarize o un resplandor difuso y guarda |
| `velvia_image` / `emboss_image` / `defringe_image` | Refuerzo de saturación Velvia, relieve de luz direccional, desaturación de flecos de borde |
| `film_negative_image` / `graduated_density_image` | Invierte un negativo escaneado; aplica un degradado lineal de densidad graduada |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Caída fílmica de luces; exposición por zona; contraste por banda |
| `colormap_image` / `false_color_image` | Recolorear la luminancia con un mapa viridis/magma/jet; escala de exposición en falso color |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Tramado Bayer ordenado; viraje dividido de sombras/luces; ordenación de píxeles por banda de brillo |
| `polar_image` / `kaleidoscope_image` | Deformación a/desde polar (tiny-planet); espejado en cuñas de caleidoscopio |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | Dispersión de vidrio esmerilado por vecino aleatorio; ecualización local CLAHE; contraste local de claridad + textura |
| `posterize_image` / `gradient_map_image` | Cuantizar los canales en bandas planas; remapear la luminancia con un degradado |
| `film_grain_image` / `dehaze_image` / `distort_image` | Grano gaussiano ajustable; desempañado por canal oscuro; deformación giro/pellizco/ondulación |
| `levels_image` / `curve_image` | Niveles de punto negro/blanco + gamma; curva de tonos (curva en S / aclarar sombras / comprimir luces) |
| `auto_color_balance_image` / `channel_mixer_image` | Balance de blancos automático (4 métodos); mezclador de canales 3×3 + conversión mono |
| `reverse_geocode` / `extract_video_frame` | GPS → ciudad sin conexión, decodificar un fotograma de vídeo a imagen fija |
| `puppet_from_png` / `puppet_inspect` | Construir un rig `.puppet` desde un PNG; abrir uno y devolver su inventario |

### Prompts

Cuatro prompts reutilizables: `caption_image`, `suggest_edits`, `analyze_composition`
(crítica de composición guiada por saliencia) y `flag_issues` (triaje de nitidez + calidad
+ recorte). Los argumentos de los prompts se pueden autocompletar vía `completion/complete`.

### Cableado

El repositorio incluye un `.mcp.json` en la raíz para auto-descubrimiento por Claude Code. Para Desktop / otros clientes, añade esto a `claude_desktop_config.json` (o equivalente):

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

Superficie completa del protocolo en la sección MCP de [docs/en/index.rst](../docs/en/index.rst).

---

## Soporte multilingüe

| Idioma | Código |
|----------|------|
| English | `English` |
| 繁體中文 (Chino tradicional) | `Traditional_Chinese` |
| 简体中文 (Chino simplificado) | `Chinese` |
| 한국어 (Coreano) | `Korean` |
| 日本語 (Japonés) | `Japanese` |

Cambia desde el menú **Language**. Reinicio requerido.

Los plugins pueden registrar idiomas enteramente nuevos vía `language_wrapper.register_language()`, o aportar traducciones vía `get_translations()`. Consulta [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## Configuración del usuario

Se almacena en `user_setting.json` en el directorio de trabajo. Entradas clave:

| Ajuste | Tipo | Descripción |
|---------|------|-------------|
| `language` | string | Código de idioma actual |
| `user_recent_folders` / `user_recent_images` | list | Recientemente abiertos |
| `user_last_folder` | string | Auto-restaurada al iniciar |
| `bookmarks` | list | Rutas de imagen marcadas (máx 5000) |
| `sort_by` / `sort_ascending` | string / bool | Método + orden de ordenación |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | Organización por imagen |
| `thumbnail_size` / `tile_padding` | int | Configuración de la cuadrícula |
| `navigation_auto_loop` | bool | Envolver al final de carpeta |
| `keyboard_shortcuts` | dict | Atajos de teclado personalizados |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | Persistencia de diseño |
| `stack_raw_jpeg_pairs` | bool | Alternador de apilamiento RAW+JPEG |
| `external_editors` | list | Editores configurados |
| `macros` / `macro_last_name` | list / string | Macros guardadas + objetivo de Alt+M |

---

## Arquitectura

```
Imervue/
├── __main__.py              # Punto de entrada de la aplicación
├── Imervue_main_window.py   # Ventana principal (QMainWindow) — monta las 4 pestañas
├── gpu_image_view/          # PESTAÑA IMERVUE — visor GPU + deep zoom
├── gui/                     # Diálogos y paneles laterales (revelado, EXIF, etc.)
├── paint/                   # PESTAÑA PAINT — editor rasterizado con todas las funciones
├── puppet/                  # PESTAÑA PUPPET — animador 2D con esqueleto
├── export/                  # Generadores de exportación (hoja de contactos, galería web, MP4)
├── image/                   # Utilidades de imagen (pirámide, gestor de mosaicos, info)
├── library/                 # Helpers de biblioteca (apilamientos RAW+JPEG, indexado)
├── macros/                  # Grabación / reproducción de macros
├── menu/                    # Definiciones de menú (file / tools / filter / …)
├── mcp_server/              # Servidor stdio Model Context Protocol
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # Integración con editores externos
├── plugin/                  # Sistema de plugins (base / manager / downloader)
├── sessions/                # Serialización del espacio de trabajo
├── system/                  # Asociación de archivos en Windows
└── user_settings/           # Configuración persistente del usuario
```

### Cadena de renderizado (pestaña Imervue)

1. `GPUImageView` extiende `QOpenGLWidget`
2. Dos programas GLSL 1.20 (quads texturizados + rectángulos de color sólido)
3. Caché LRU de texturas — límite de 256 mosaicos, presupuesto de 1.5 GB de VRAM
4. Pirámide de mosaicos multinivel construida con LANCZOS a tamaño de mosaico 512 × 512
5. Filtrado anisotrópico hasta 8× cuando el hardware lo soporta
6. Renderizado por software como respaldo si falla la compilación del shader

### Caché de miniaturas

- **Clave**: MD5 de `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
- **Formato**: PNG comprimido (`compress_level=1` — escritura rápida, huella pequeña)
- **Ubicación**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) o `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidación**: Automática al cambiar metadatos del archivo

### Renderizado de Puppet (pestaña Puppet)

- `QOpenGLWidget` con `glDrawElements` + arrays de vértices del lado cliente
- Por drawable: vértices en reposo cacheados como numpy float32; vertex morphs vectorizados; ordenamiento topológico de deformadores izado fuera del bucle por drawable
- El fondo de transparencia es una textura 2×2 con GL_REPEAT (antes de la optimización eran 100k+ quads en modo inmediato)
- El convertidor de Cubism produce curvas opacity_keys junto con los deltas de vertex-morph para que las transiciones de visibilidad accionadas por parámetro sobrevivan a la conversión `.moc3 → .puppet`

---

## Licencia

Este proyecto se distribuye bajo la [Licencia MIT](../LICENSE).

Copyright (c) 2026 JE-Chen
