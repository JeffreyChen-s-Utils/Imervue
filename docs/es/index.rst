Guía del Usuario de Imervue
===========================

Una estación de trabajo de imágenes con aceleración GPU que incluye **cinco pestañas
de nivel superior**. La mayor parte de esta guía está organizada en torno a esas cinco
secciones.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Pestaña
     - Función
   * - **Imervue**
     - Examinar, visualizar, organizar, buscar y procesar por lotes su biblioteca
       de imágenes. Consulte *Pestaña Imervue — Visor y biblioteca de imágenes*.
   * - **Modify**
     - Pipeline de revelado no destructivo — controles deslizantes, curvas, LUTs,
       máscaras, retoque, multi-imagen. Consulte *Pestaña Modify — Revelado no destructivo*.
   * - **Paint**
     - Estudio completo de pintura raster con pinceles, capas, animación,
       herramientas de manga e I/O de PSD. Consulte *Pestaña Paint — Editor raster completo*.
   * - **Puppet**
     - Animador de marionetas 2D con rig construido desde cero — mallas, deformadores,
       parámetros, movimientos, físicas. Consulte *Pestaña Puppet — Animación 2D con rig*.
   * - **Desktop Pet**
     - Superposición sin marco, transparente y siempre encima que ejecuta los mismos
       rigs ``.puppet`` en su escritorio con drivers en vivo (reposo / parpadeo /
       micrófono / cámara web / seguimiento del cursor). Consulte *Espacio de trabajo
       Desktop Pet*.

Las secciones *Primeros pasos*, *Referencia*, *Sistema de plugins* y *Servidor MCP* que
siguen son transversales y se aplican a las cinco pestañas.

.. contents:: Tabla de contenidos
   :depth: 2
   :local:

----

Primeros pasos
--------------

Cuando abra Imervue, verá tres áreas:

::

   +------------+----------------------+----------+
   |  Árbol de  |                      |  Barra   |
   |  carpetas  |   Visor de imágenes  |  EXIF    |
   |            |                      |          |
   +------------+----------------------+----------+

- **Izquierda**: Árbol de carpetas. Haga clic en una carpeta para examinar las imágenes que contiene.
- **Centro**: Área de visualización. Muestra todas las imágenes como una cuadrícula de miniaturas.
- **Derecha**: Barra lateral EXIF. Muestra la información de captura de la imagen seleccionada.

----

Abrir imágenes
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Método
     - Procedimiento
   * - Abrir carpeta
     - ``File`` > ``Open Folder``, después elija un directorio
   * - Abrir una sola imagen
     - ``File`` > ``Open Image``, después elija un archivo
   * - Arrastrar y soltar
     - Arrastre una imagen o carpeta directamente a la ventana
   * - Abrir desde el Explorador
     - Clic derecho en una imagen > ``Open with Imervue`` (requiere asociación de archivos)
   * - Archivos recientes
     - ``File`` > ``Recent``, vuelva a abrir rápidamente una carpeta visitada anteriormente

Formatos compatibles
^^^^^^^^^^^^^^^^^^^^

- **Estándar**: PNG, JPEG (.jpg, .jpeg, .jpe, .jfif, .jif), BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 / CR3 / CRW (Canon), NEF / NRW (Nikon), ARW / SRF / SR2 (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus / OM System), RW2 (Panasonic), RWL (Leica), PEF (Pentax), SRW (Samsung), 3FR (Hasselblad), IIQ (Phase One), MEF (Mamiya), MOS (Leaf), ERF (Epson), MRW (Minolta), KDC / DCR (Kodak)
- **Modernos**: AVIF (integrado); HEIC / HEIF con el opcional ``pillow-heif``; JPEG XL con el opcional ``pillow-jxl-plugin``
- **Otros**: ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (la imagen combinada) — para ver; girar uno en su sitio y otras reescrituras se rechazan, así que una edición sale por Guardar como / Exportar

----

Explorar imágenes
-----------------

Modo cuadrícula de miniaturas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Tras abrir una carpeta, todas las imágenes se muestran como miniaturas.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Método
   * - Desplazarse
     - Rueda del ratón
   * - Encuadre (pan)
     - Mantenga pulsado el botón central del ratón y arrastre
   * - Entrar en vista a tamaño completo
     - Clic izquierdo en cualquier miniatura
   * - Cambiar el tamaño de las miniaturas
     - Menú ``Thumbnail Size`` > elija 128 / 256 / 512 / 1024
   * - Densidad de miniaturas
     - ``Thumbnail Size`` > ``Thumbnail Density`` > Compact / Standard / Relaxed
   * - Vista previa al pasar el cursor
     - Deje el cursor sobre una miniatura durante 500 ms para ver una vista previa ampliada
   * - Seleccionar varias imágenes
     - Clic izquierdo y arrastrar para dibujar un rectángulo de selección
   * - Moverse entre miniaturas con el teclado
     - Las teclas de flecha mueven un recuadro de foco y lo desplazan a la vista; ``Enter`` abre la imagen

Cada miniatura muestra distintivos de estado: una franja de color en el borde izquierdo
(etiqueta de color), un corazón en la esquina superior izquierda (favorito), una estrella
en la esquina superior derecha (marcador) y estrellas de valoración en la esquina inferior
izquierda. Se dibuja un marcador giratorio para las miniaturas que aún se están cargando.

Modo lista (detalle)
^^^^^^^^^^^^^^^^^^^^

Pulse ``Ctrl + L`` para alternar entre la cuadrícula de miniaturas y una vista de lista
ordenable con estas columnas: Vista previa · Etiqueta · Nombre · Resolución · Tamaño · Tipo
· Modificado. Haga doble clic en una fila (o pulse ``Enter``) para entrar en Deep Zoom; pulse
``Esc`` para volver a la lista. Las miniaturas y los metadatos se cargan de forma diferida en
un hilo de trabajo, de modo que las carpetas muy grandes mantienen la capacidad de respuesta.

``Delete`` quita las filas seleccionadas y ``Ctrl + Z`` las recupera, y las teclas de valoración (``0`` – ``5``), selección (``P`` / ``Shift + X`` / ``U``) y color (``F1`` – ``F5``) las marcan, como en la cuadrícula; las teclas siguen la configuración de atajos.

Modo Deep Zoom
^^^^^^^^^^^^^^

Haga clic en una miniatura para entrar en el modo Deep Zoom y ver imágenes individuales en
alta calidad.

También se abren panoramas muy por encima del límite de seguridad de 179 megapíxeles de Pillow: el límite depende de la memoria del equipo (con 16 GB, unos 1,3 gigapíxeles) y esas imágenes gigantes se decodifican de una en una.

Un JPEG, PNG, TIFF, GIF o BMP incompleto — una descarga o copia interrumpida, una foto recuperada de una tarjeta de memoria dañada — se abre con la parte que se pudo leer, como en un navegador, en lugar de no abrirse.

Cuando otro programa guarda sobre una imagen — un editor externo, directamente o renombrando una copia encima —, el visor muestra la versión nueva: la imagen abierta en zoom profundo en menos de un segundo tras la última escritura, las miniaturas de la cuadrícula y las filas de la Lista en pocos segundos.

Un PNG o TIFF en gris de 16 bits — un escaneo, un mapa de profundidad, una toma científica o astronómica — y un TIFF de coma flotante muestran su brillo real en el visor, las miniaturas, las vistas previas y las herramientas, en lugar de casi blanco o negro: los valores de 16 bits se escalan en todo su rango, los valores de coma flotante de 0 a 1 van de negro a blanco y cualquier otro rango se estira.

Las imágenes con un perfil de color incrustado — Display P3 de móviles, Adobe RGB de cámaras, CMYK y los perfiles de grises que Photoshop incrusta en las imágenes en escala de grises, como Dot Gain 20% o Gray Gamma 1.8 — se convierten a sRGB en el visor y las miniaturas; una imagen en escala de grises sigue siéndolo. Las imágenes sin perfil o en sRGB se muestran tal cual.

Los archivos que Windows marca como ocultos — también ocultos en el Explorador y en el árbol de carpetas — y los nombres que empiezan por punto, como el ``._foto.jpg`` que macOS escribe junto a cada foto en tarjetas de memoria y unidades de red, quedan fuera de la cuadrícula de miniaturas, los iconos de carpeta, las listas de las herramientas por lotes, las carpetas vigiladas, los escaneos de la biblioteca, la CLI y las herramientas de carpeta del servidor MCP; los escaneos recursivos se saltan carpetas ocultas como ``$RECYCLE.BIN`` y la ``.Trashes`` de un Mac. Una imagen oculta abierta a propósito se abre igualmente.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Método
   * - Acercar/alejar
     - Rueda del ratón o pellizco en el touchpad
   * - Encuadre
     - Mantenga pulsado el botón central del ratón
   * - Imagen anterior
     - ``Left Arrow`` (o deslizar a la derecha en el touchpad)
   * - Imagen siguiente
     - ``Right Arrow`` (o deslizar a la izquierda en el touchpad)
   * - Salto entre carpetas
     - ``Ctrl + Shift + Left`` / ``Right`` a la carpeta hermana anterior/siguiente con imágenes
   * - Historial atrás/adelante
     - ``Alt + Left`` / ``Alt + Right`` (estilo navegador)
   * - Saltar a imagen por número
     - ``Ctrl + G``
   * - Imagen aleatoria
     - ``X``
   * - Ajustar al ancho
     - ``W``
   * - Ajustar al alto
     - ``Shift + W``
   * - Restablecer zoom
     - ``Home``
   * - Volver a miniaturas
     - ``Esc``
   * - Pantalla completa
     - ``F`` (pulse de nuevo para salir)
   * - Modo cine
     - ``Shift + Tab`` oculta menú / estado / árbol / pestañas para una visualización sin distracciones
   * - Información OSD superpuesta
     - ``F8`` muestra nombre/tamaño/tipo; ``Ctrl + F8`` muestra un HUD de depuración (VRAM / caché / hilos)
   * - Vista de píxeles
     - ``Shift + P`` — con zoom ≥ 400 % superpone una cuadrícula de píxeles y muestra RGB / HEX bajo el cursor
   * - Modos de color
     - ``Shift + M`` alterna Normal / Escala de grises / Invertir / Sepia (GLSL, no destructivo)

Vista dividida y lectura a doble página
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Muestre dos imágenes una al lado de la otra directamente en la ventana principal sin abrir
el diálogo Compare:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Acción
     - Atajo
   * - Vista dividida (dos imágenes)
     - ``Shift + S``
   * - Doble página (actual + siguiente)
     - ``Shift + D``
   * - Doble página, derecha a izquierda (manga)
     - ``Ctrl + Shift + D``
   * - Volver al modo anterior
     - ``Esc``

En el modo de doble página, las teclas de flecha avanzan dos imágenes a la vez. La variante
RTL intercambia los dos paneles para que la página 1 aparezca a la derecha.

Ventana multi-monitor
^^^^^^^^^^^^^^^^^^^^^

Pulse ``Ctrl + Shift + M`` para abrir una segunda ventana sin marco en la pantalla
secundaria que refleja la imagen mostrada en el visor principal. La ventana principal
sigue navegando de forma independiente — útil para exposiciones, flujos de trabajo de
edición en doble pantalla o presentaciones a clientes. Pulse ``Ctrl + Shift + M`` de nuevo
para cerrar, o use ``Esc`` dentro de la segunda ventana.

----

Organizar imágenes
------------------

Valoración y favoritos
^^^^^^^^^^^^^^^^^^^^^^

Las teclas valoran la imagen mostrada en Deep Zoom. En la cuadrícula valoran las miniaturas seleccionadas, si no la elegida con las flechas, si no la que está bajo el ratón: las mismas fotos que tomaría una etiqueta de color o una marca de selección. Si todas tienen ya esa valoración, la tecla la borra.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Tecla
   * - Alternar favorito
     - ``0``
   * - Valorar 1 -- 5 estrellas
     - ``1`` ``2`` ``3`` ``4`` ``5`` (pulse de nuevo para borrar)

Etiquetas de color (F1 -- F5)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Indicadores de color independientes basados en banderas, almacenados por separado de la
valoración de 1 -- 5 estrellas. Útiles para una categorización rápida (p. ej. rojo = candidatos
a descartar, verde = seleccionados, azul = pendientes de retoque).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Tecla
   * - Rojo / Amarillo / Verde / Azul / Púrpura
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (pulse la misma tecla de nuevo para borrar)
   * - Aplicar a la selección en lote
     - Seleccione varias miniaturas y pulse la tecla F correspondiente
   * - Filtrar por color
     - ``Filter`` > ``By Color Label`` > elija un color / cualquier etiqueta / sin etiqueta

La barra de estado muestra un chip de color para la imagen actual. Las miniaturas muestran
una franja de color en el borde izquierdo. La **vista de lista** tiene columnas dedicadas
**Label** y **Star Rating** que se pueden ordenar — haga clic en cualquier celda de la columna
de estrellas para establecer la valoración sin salir de la lista.

Marcadores
^^^^^^^^^^

Guarde las imágenes usadas con frecuencia como marcadores para acceder rápidamente más tarde.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Método
   * - Añadir / quitar marcador
     - Pulse ``B`` en el modo Deep Zoom
   * - Gestionar marcadores
     - ``File`` > ``Bookmarks``

Etiquetas y álbumes
^^^^^^^^^^^^^^^^^^^

Categorice sus imágenes con etiquetas y álbumes.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Método
   * - Abrir el gestor
     - Pulse ``T`` o ``File`` > ``Tags & Albums``
   * - Etiquetar una imagen
     - Clic derecho en la imagen > ``Add to Tag``
   * - Añadir a un álbum
     - Clic derecho en la imagen > ``Add to Album``
   * - Filtrar por una sola etiqueta / álbum
     - ``Filter`` > ``By Tag`` / ``By Album``
   * - Filtro multi-etiqueta (AND / OR)
     - ``Filter`` > ``Multi-Tag Filter…`` — marque varias etiquetas o álbumes, elija Any (OR) o All (AND)

Ordenación y filtrado
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Función
     - Ubicación en el menú
   * - Ordenar por nombre (orden natural: ``img2`` antes que ``img10``)
     - ``Sort`` > ``By Name``
   * - Ordenar por fecha de modificación
     - ``Sort`` > ``By Modified Date``
   * - Ordenar por fecha de captura (la hora EXIF de la cámara; sin ella, la fecha de modificación)
     - ``Sort`` > ``By Date Taken``
   * - Ordenar por tamaño de archivo
     - ``Sort`` > ``By File Size``
   * - Ordenar por resolución
     - ``Sort`` > ``By Resolution``
   * - Ascendente / Descendente
     - ``Sort`` > ``Ascending`` / ``Descending``
   * - Filtrar por extensión
     - ``Filter`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
   * - Filtrar por valoración
     - ``Filter`` > ``By Rating``
   * - Filtrar por etiqueta de color
     - ``Filter`` > ``By Color Label`` (All / Any label / No label / Red / Yellow / Green / Blue / Purple)
   * - Filtro avanzado
     - ``Filter`` > ``Advanced Filter…`` — rango de resolución, rango de tamaño de archivo, orientación (horizontal / vertical / cuadrada), rango de fecha de modificación
   * - Limpiar filtros
     - ``Filter`` > ``Clear Filter``

Modo de navegación (Cuadrícula / Lista)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cambie el explorador de imágenes entre la cuadrícula de mosaicos y una lista de detalle ordenable:

- ``Ctrl + L`` — alternar Cuadrícula ↔ Lista
- Menú: ``Thumbnail Size`` > ``Browse Mode`` > Grid / List
- En el modo Lista, cualquier columna (incluida Label) es ordenable; doble clic en una fila o pulse ``Enter`` para abrir Deep Zoom.

----

Editar imágenes (Pestaña Modify)
--------------------------------

Cambie a la pestaña **Modify** en la parte superior de la ventana para entrar en el modo
de edición. En el modo Deep Zoom, clic derecho > ``Modify`` > ``Develop`` también abre aquí la
imagen actual; ``E`` (o clic derecho > ``Modify`` > ``Annotate``), en cambio, la abre en el
editor de anotaciones independiente.

::

   +--------+----------------------+------------+
   | Banda  |                      | Propiedades|
   | de     |  Lienzo (dibujar)    | Pinceles   |
   | herr.  |                      | Revelado   |
   +--------+----------------------+------------+

Herramientas de anotación (Panel izquierdo)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Herramienta
     - Icono
     - Descripción
   * - Seleccionar
     - |select|
     - Selecciona anotaciones existentes; arrastrar para mover
   * - Rectángulo
     - |rect|
     - Dibuja rectángulos
   * - Elipse
     - |ellipse|
     - Dibuja elipses o círculos
   * - Línea
     - |line|
     - Dibuja líneas rectas
   * - Flecha
     - |arrow|
     - Dibuja flechas
   * - Mano alzada
     - |freehand|
     - Dibujo de forma libre
   * - Texto
     - T
     - Añade texto a la imagen
   * - Mosaico
     - |mosaic|
     - Pixelar una región seleccionada
   * - Desenfoque
     - |blur|
     - Desenfoque gaussiano de una región seleccionada

.. |select| unicode:: U+2B1A
.. |rect| unicode:: U+25A2
.. |ellipse| unicode:: U+25EF
.. |line| unicode:: U+2571
.. |arrow| unicode:: U+2192
.. |freehand| unicode:: U+270E
.. |mosaic| unicode:: U+25A6
.. |blur| unicode:: U+25CC

.. tip::
   Pulse ``Left Arrow`` / ``Right Arrow`` mientras esté en la pestaña Modify para cambiar entre imágenes sin salir del editor.

Tipos de pincel (Panel derecho)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pincel
     - Efecto
   * - Pluma
     - Línea fina estándar, el pincel más común
   * - Marcador
     - Trazos más gruesos y semitransparentes
   * - Lápiz
     - Línea fina, ligeramente difuminada
   * - Resaltador
     - Ancho y muy transparente, como un resaltador real
   * - Aerosol
     - Efecto de puntos dispersos
   * - Caligrafía
     - El grosor del trazo varía según la dirección
   * - Acuarela
     - Efecto suave de bordes húmedos y mezcla
   * - Carboncillo
     - Trazo rugoso y texturizado
   * - Cera
     - Textura cerosa, tipo crayón

Propiedades de dibujo (Panel derecho)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Propiedad
     - Descripción
   * - Color
     - Haga clic en la muestra de color para elegir un color de dibujo
   * - Grosor del trazo
     - Arrastre el deslizador para ajustar el grosor de la línea (1 -- 40)
   * - Opacidad
     - Ajuste la transparencia (0 % -- 100 %)
   * - Fuente
     - Elija la fuente para la herramienta de texto
   * - Tamaño de fuente
     - Ajuste el tamaño del texto (6 -- 200 px)

Ajustes de imagen (Panel derecho, inferior)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Deslizador
     - Función
   * - Exposición
     - Ajusta el brillo general
   * - Brillo
     - Afina las zonas claras y oscuras
   * - Contraste
     - Ajusta la diferencia entre luces y sombras
   * - Saturación
     - Ajusta la intensidad del color
   * - Balance de blancos — Temperatura
     - Desplazamiento cálido/frío (azul → amarillo); útil para luces mixtas o tomas en interiores
   * - Balance de blancos — Tinte
     - Desplazamiento magenta/verde; corrige dominantes fluorescentes
   * - Luces
     - Recupera luces quemadas o intensifica las zonas brillantes
   * - Sombras
     - Levanta o aplasta el detalle en zonas tonales oscuras
   * - Blancos
     - Hacia la derecha, lleva los tonos más claros hasta el blanco; hacia la izquierda, apaga el blanco hasta un gris
   * - Negros
     - Hacia la izquierda, hunde los tonos más oscuros hasta el negro; hacia la derecha, levanta el negro hasta un gris lavado
   * - Intensidad
     - Refuerzo consciente de la saturación — protege los tonos de piel y los colores ya saturados

Estos ajustes son **no destructivos**. Cada deslizador escribe en una receta de edición
almacenada por imagen; pulse ``Reset`` en cualquier momento para restaurar el original, o
``Undo`` / ``Redo`` bajo los deslizadores para avanzar o retroceder por los cambios individuales.
Las recetas sobreviven a los reinicios y se pueden exportar / sincronizar mediante el flujo de
archivos secundarios XMP descrito en la sección Metadatos.

El archivo en disco solo cambia cuando lo pides. **Apply Crop** y el **Save** de anotaciones escriben el resultado sobre el archivo y conservan su EXIF (cámara, fecha de captura, GPS), XMP y DPI. Un RAW de cámara, un HEIC o un archivo animado / de varias páginas nunca se sobrescribe: el recorte te pide exportar y el guardado de anotaciones te pide un archivo nuevo. Las herramientas de un solo paso (CLAHE, mezclador HSL, marco de foto, enderezado
automático…) guardan el resultado junto al original como ``photo_clahe.png``;
volver a ejecutarlas guarda ``photo_clahe_1.png`` en vez de reemplazar el último
resultado. **Auto-Rotate by EXIF**, las copias de **Batch EXIF Strip** y **Split Pages…** numeran sus archivos de la misma manera. La receta y las copias virtuales de una foto la acompañan cuando Imervue la gira
sin pérdida (el recorte gira con ella) o reescribe su EXIF (geoetiquetado GPS,
editor EXIF); una receta con máscaras locales, capas, destello de lente o etiquetas
de rostros se queda con la versión sin girar hasta que se vuelve a girar.

Guardar y deshacer
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Botón
     - Descripción
   * - Save
     - Escribe las anotaciones y ajustes en el archivo original
   * - Undo
     - Deshace la última operación
   * - Redo
     - Rehace una operación deshecha
   * - Reset
     - Borra todos los ajustes de la imagen

----

Espacio de trabajo Paint (Pestaña Paint)
----------------------------------------

La tercera pestaña de nivel superior — **Paint** — es un espacio de trabajo de pintura
con todas las funciones, con documentos en múltiples pestañas, capas vectoriales y raster,
herramientas de manga, fotogramas de animación e importación/exportación de PSD. Al cambiar
a ella desde la barra de pestañas, la imagen que muestra el visor se carga en el lienzo.

Aspectos destacados de la experiencia de usuario — el espacio de trabajo Paint incluye un
cursor de tamaño de pincel con todas las funciones que se escala con el zoom, iconos de cursor
distintos por herramienta, un patrón de cuadrícula de transparencia bajo el lienzo, una capa
de resaltado para arrastrar y soltar, un asterisco de modificación por pestaña, confirmaciones
toast de deshacer/rehacer, un segmento de estado de autoguardado en la barra de estado, y un
aviso de recuperación de autoguardado al iniciar que recupera instantáneas de una sesión
anterior caída.

Atajos para usuarios avanzados: ``Tab`` alterna todos los docks para pintar sin distracciones,
``Ctrl+Tab`` recorre las pestañas, ``,`` / ``.`` recorren los tipos de pincel, ``0–9`` ajustan
la opacidad del pincel en pasos del 10 %, ``Alt+[`` / ``Alt+]`` recorren la capa activa, y
hacer clic derecho en el lienzo abre un menú rápido de Deshacer / Rehacer / Seleccionar todo
/ Deseleccionar / Ajustar / 100 %.

El dock de color ahora expone una ranura "transparente / sin color" (BG por defecto =
transparente), y tanto el relleno como la varita mágica respetan los límites alfa, de modo
que los píxeles borrados dejan de filtrarse en un repintado.

::

   +------+----------------------+----------------+
   | Bar  |                      | Color · Pincel |
   | de   |   Lienzo (pintar)    | Capa · Naveg.  |
   | herr.|                      | Material · …   |
   +------+----------------------+----------------+

Los catorce docks del lado derecho están organizados como pestañas en una sola columna,
de modo que el lienzo mantiene la altura visible completa, y se agrupan en tres bloques:

- **Dibujo** — Color, Brush, Bucket, Swatches
- **Lienzo** — Layers, Navigator, History, Pages, Animation, Histogram
- **Biblioteca** — Materials, Stamps, Pose, Reference

Cada dock se puede mostrar u ocultar por separado desde el menú ``Window``. Arrastre el
título de cualquier dock para reorganizarlo o flotar un panel, después guarde el resultado
mediante ``Settings`` > ``Workspace Layouts…``.

Paleta de herramientas (Banda izquierda)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Herramienta
     - Atajo
     - Propósito
   * - Pincel
     - ``B``
     - Pintar con el tipo de pincel activo
   * - Borrador
     - ``E``
     - Borrado alfa de la capa activa
   * - Relleno (cubo)
     - ``G``
     - Relleno por inundación con tolerancia / contiguo / muestrear todas las capas
   * - Cuentagotas
     - ``I``
     - Toma el color de primer plano del lienzo
   * - Mover
     - ``V``
     - Traslada la capa o selección activa
   * - Rect / Lazo / Varita / Selección rápida
     - ``M`` / ``L`` / ``W``
     - Herramientas de selección con modos Replace / Add / Subtract / Intersect
   * - Texto
     - ``T``
     - Editor de texto en línea con fuente / tamaño / negrita / cursiva
   * - Degradado
     - ``U``
     - Relleno con degradado lineal / radial / angular / diamante
   * - Desenfoque / Difuminar
     - ``R``
     - Manipulación local de píxeles
   * - Dodge / Burn / Sponge
     -
     - Tonificación de cuarto oscuro — aclara, oscurece o satura /
       desatura localmente, ponderado por el pincel y una máscara de rango tonal
   * - Pluma (Bezier)
     - ``P``
     - Ruta vectorial con edición de anclas / manejadores
   * - Sello de clonar
     - ``S``
     - Shift+clic establece la fuente, clic estampa con difuminado
   * - Bocadillo
     - ``Ctrl + B``
     - Bocadillo de cómic / manga con cola automática
   * - Rectángulo / Elipse / Línea / Polígono
     - ``Shift + R/E/I/P``
     - Primitivas de forma vectorial con trazo + relleno
   * - Recortar
     - ``C``
     - Recorte interactivo con presets de relación de aspecto
   * - Transformar
     - ``Ctrl + T``
     - Manejadores de transformación libre / escala / rotación / sesgo
   * - Mano
     - ``H``
     - Encuadre del lienzo arrastrando con el cursor
   * - Zoom
     - ``Z``
     - Clic para acercar, Alt-clic para alejar

Pinceles
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pincel
     - Efecto
   * - Pluma
     - Línea con suavizado nítido, el pincel del día a día
   * - Marcador / Resaltador
     - Trazos anchos y semitransparentes que se acumulan
   * - Lápiz
     - Línea fina de grafito ligeramente texturizada
   * - Aerosol
     - Puntos dispersos controlados por densidad y flujo
   * - Caligrafía
     - El ancho varía con la dirección del trazo
   * - Acuarela
     - Sangrado de bordes húmedos y mezcla suave
   * - Carboncillo / Cera
     - Trazos rugosos texturizados con inclinación por presión

Cada pincel expone Size / Opacity / Hardness / Density / Blend-mode en el **dock Brush** y
en la **barra Options** superior. Use ``Settings`` > ``Pressure Curve…`` para remapear la
presión de la tableta al ancho o a la opacidad, y ``Edit`` > ``Capture Brush Tip…`` para
convertir una selección de marquesina en una punta de pincel personalizada.

Capas
^^^^^

El **dock Layer** ofrece miniaturas, alternancia de visibilidad, renombrado en línea,
arrastrar para reordenar, y el modo de fusión y opacidad de la capa activa. El menú
``Layer`` añade:

- **New / Vector / Duplicate / Merge Down** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Máscaras** — Add Mask / From Selection / Invert / Apply / Delete
  (``Ctrl + Shift + M`` añade; ``Ctrl + Alt + Shift + M`` añade desde selección)
- **Máscara de recorte** — recorta la capa de arriba al alfa actual
  (``Ctrl + Alt + G``)
- **Efectos de capa** — Drop Shadow · Outer Glow · Stroke; limpiar efectos
- **Capa de referencia** — fija una capa como fuente del cuentagotas
- **Capa de 1 bit** — alterna la capa activa a una capa de line-art binaria
- **Dividir capa por color** — divide una capa de color plano en una capa por color para
  facilitar el rellenado con el cubo
- **Mapa de degradado** — submenú de presets (sepia / atardecer / cianotipia …)

Selecciones
^^^^^^^^^^^

Use las herramientas rect / lazo / varita / selección rápida, después el menú **Edit** >
**Stroke Selection…** para delinear la marquesina con el pincel actual. ``Q`` alterna el
**Modo de máscara rápida** — pinte con cualquier pincel para refinar el borde de la
selección en rojo, después pulse ``Q`` de nuevo para convertirla de vuelta en una marquesina.

Animación
^^^^^^^^^

El **dock Animation** convierte el documento en una tira de fotogramas:

- ``Add Frame`` captura el estado actual de las capas en un nuevo fotograma clave.
- Haga clic en la miniatura de un fotograma para saltar a él.
- ``Onion Skin`` (menú View) superpone los fotogramas vecinos con baja opacidad.
- Exporte la tira mediante **File > Export pages** (CBZ para lectores de cómics,
  PDF para impresión) o **Animation Export** para MP4 / GIF.

Menú Manga
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Acción
     - Descripción
   * - Cortador de paneles
     - ``Ctrl + Shift + P`` — divide el lienzo en una cuadrícula de paneles de cómic con filas / columnas / canalón / borde / margen configurables
   * - Alternar capa de tono
     - Convierte la capa activa en una capa de trama (puntos de semitono)
   * - Estampar números de página
     - Añade números de página en documentos de varias páginas
   * - Líneas cinéticas
     - Generadores de líneas cinéticas radiales / paralelas / explosivas
   * - Acción / impacto
     - Superposición de explosión / impacto estilo manga
   * - Herramienta de bocadillo
     - Arrastra un bocadillo, suelta la cola hacia el hablante

Filtros
^^^^^^^

``Filter`` abre un diálogo con vista previa en vivo para cada efecto:

- **Niveles** — deslizadores de negro / gamma / blanco, por canal
- **Curvas** — puntos arrastrables (RGB / R / G / B) con interpolación cúbica monótona
- **Posterizar** — cuantiza el color en N pasos
- **Umbral** — convierte a blanco / negro puros en un punto de corte
- **Auto Color Balance** — neutraliza dominantes mediante grey-world / white-patch
- **Grano de película** — ruido de luminancia con tamaño y cantidad ajustables
- **Convertir a semitonos** — pantalla de puntos al estilo periódico

Ayudas de visualización
^^^^^^^^^^^^^^^^^^^^^^^

- **Cuadrícula de píxeles** (``Ctrl + Shift + '``) — superpone una cuadrícula de un píxel con alto zoom
- **Ajustar a píxel / bordes** — posicionamiento sub-píxel forzado a coordenadas enteras
- **Onion Skin** — superposición de fotogramas vecinos para animación
- **Guías de sangrado** — guías de sangrado y zona segura para impresión
- **Rotar lienzo** (``Ctrl + Shift + H``) — rotación de vista sin rasterizar

Entrada/Salida de archivos
^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Open PSD…** (``Ctrl + O``) y **Save as PSD…** (``Ctrl + S``) — ida y vuelta a archivos
  Photoshop con capas, máscaras, modos de fusión y efectos de capa
- **Export image…** — aplana y guarda como PNG / JPEG / WebP / BMP / TIFF
- **Export pages → CBZ** / **→ PDF** — exportación de documentos multi-fotograma para cómics
- **Importar / Exportar presets de pincel**, **Importar paleta** — compartir recursos entre instalaciones
- **Instantáneas de autoguardado** — instantáneas periódicas en segundo plano con restauración de la última desde el menú File

Diseños de espacio de trabajo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Settings`` > ``Workspace Layouts…`` guarda la disposición de los docks, el estado de las
opciones de herramienta y los paneles activos bajo un nombre, después alterna entre ellos con
un solo clic — por ejemplo, un diseño "Dibujo" con los docks Brush + Color destacados y un
diseño "Composición" con los docks Layer + History expandidos.

----

Espacio de trabajo Puppet (Pestaña Puppet)
------------------------------------------

La cuarta pestaña de nivel superior — **Puppet** — es un sistema de animación 2D con rig de
marionetas construido desde cero. Hace lo que hace Live2D (rigs con deformación de malla,
parámetros, movimientos, físicas, expresiones, grupos de poses, lip-sync, seguimiento por
webcam) pero **sin SDK propietario**, **sin `live2d-py`**, y con un formato de archivo
``.puppet`` totalmente abierto.

.. note::

   El tutorial completo de principio a fin — desde una instalación nueva hasta una
   retransmisión en directo por OBS o un MP4 renderizado — vive en ``puppet_guide.md`` en
   la raíz del repositorio (con espejos ``puppet_guide.zh-TW.md`` y
   ``puppet_guide.zh-CN.md``). Esta sección es la referencia; la guía es el recorrido paso
   a paso.

::

   +-----------+----------------------+----------------+
   |  Barra de |                      |  Dock de       |
   |  herr.    |   Lienzo GL          |  parámetros    |
   |           |                      |                |
   +-----------+----------------------+                |
   |             Dock de movimientos                   |
   +---------------------------------------------------+

Flujo de trabajo de principio a fin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Importar un PNG** — el botón ``Import PNG…`` de la barra de herramientas ejecuta
   ``puppet.auto_mesh.puppet_from_png``: cuadrícula triangulada limitada por alfa, un
   drawable, lista para renderizar.
2. **Añadir un deformador** — ``Add Rotation Deformer`` (ancla + ángulo) o
   ``Add Warp Deformer`` (rejilla Bezier de filas × columnas; los vértices fuera de los
   límites pasan sin cambios).
3. **Añadir un parámetro** — ``Add Parameter`` añade un deslizador al dock derecho
   **Parameters** con id autonombrado (``Param1``, ``Param2``, …).
4. **Establecer claves** — arrastre el deslizador a un extremo, edite la forma del deformador
   en código o mediante edición de malla, pulse **Set key**. Repita en neutro y en el extremo
   opuesto. El runtime ahora interpola linealmente los campos del deformador entre claves
   adyacentes cada vez que se mueve el deslizador.
5. **Guardar** — ``Save As…`` escribe el rig + texturas + movimientos + expresiones + físicas
   en un único zip ``.puppet`` que puede compartir o abrir más tarde mediante
   ``Open Puppet…``.

Pruebe un ejemplo completo
^^^^^^^^^^^^^^^^^^^^^^^^^^

El repositorio incluye una demo totalmente riggeada en
``examples/puppet/march_7th.puppet`` — un rig Cubism Live2D de 307 drawables convertido
en el propio árbol del proyecto. Las texturas y morfos de vértices por parámetro están
horneados en el zip ``.puppet``, de modo que la demo se abre con el ``requirements.txt``
por defecto sin redistribuir el SDK de Cubism.

El rig lleva 203 parámetros estándar de Cubism (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …), por lo que todos los
drivers de entrada estándar (webcam, parpadeo, lip-sync, mirada al cursor) lo controlan
sin configuración por rig. El bundle incluye dieciocho movimientos: ocho movimientos
idle en bucle en el grupo ``Idle``, nueve gestos en bucle en el grupo ``Gesture`` y un
``tap_head`` de una sola reproducción en el grupo ``TapHead``.

Abra la pestaña Puppet, haga clic en **Open Puppet…**, apunte a
``march_7th.puppet`` — la figura aparece centrada. Arrastre cualquier deslizador de
parámetro para controlar una articulación, o haga clic en uno de los movimientos del dock
Motions — un solo clic enlaza el movimiento e inicia la reproducción inmediatamente.

**Ejecutar el ejemplo incluido, paso a paso:**

1. Inicie Imervue. Desde el código fuente: ``python -m Imervue``. Desde la versión
   empaquetada: ejecute el ejecutable / bundle de aplicación ``Imervue``. El directorio
   ``examples/`` se empaqueta tanto en el wheel como en el EXE de Nuitka, de modo que el
   rig está en disco dondequiera que lo haya instalado.
2. Haga clic en la pestaña **Puppet** en la parte superior de la ventana.
3. Barra de herramientas → **File > Examples > March 7th** (o el desplegable
   **Examples ▾** de la barra de herramientas). El rig de 307 drawables se carga centrado
   y el dock de parámetros se llena con los 203 deslizadores estándar de Cubism.
4. En el dock **Motions** inferior, haga un solo clic en cualquier entrada de movimiento
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …). La reproducción empieza
   inmediatamente; haga clic de nuevo para detener, o elija un movimiento distinto para
   hacer un cross-fade hacia él.
5. Active los interruptores de entrada en vivo en la barra de herramientas para controlar
   el rig desde sus propias entradas — **Drag-track head** para la mirada al cursor,
   **Auto-blink** para el ciclo de cerrar/abrir ojos, **Auto idle** + **Idle motions**
   para respiración + clips Idle aleatorios, **Mic lip-sync** para apertura de boca a partir
   del RMS del micrófono, **Webcam tracking** para cabeza + ojos + boca completos desde
   MediaPipe FaceLandmarker.
6. **Reset to rest** en la barra de herramientas detiene todos los movimientos, desactiva
   todos los drivers en vivo, limpia las expresiones / overrides de pose, y devuelve cada
   parámetro a su valor por defecto — la acción canónica de "empezar de nuevo".
7. Para abrir un rig diferente más tarde: **File > Open Puppet…** elige cualquier zip
   ``.puppet`` del disco; **File > Examples ▾** sigue enlazado a la lista incluida.

Formato de archivo ``.puppet`` (v1)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Un archivo ``.puppet`` es un archivo zip:

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

Ejemplo de ``puppet.json`` de nivel superior::

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

El esquema completo (drawables, deformers, parameters, motions, expressions, pose, physics)
vive en ``Imervue/puppet/FORMAT.md`` en el repositorio. Sólo JSON + PNG — sin binario
propietario, totalmente diffable a través de git.

Referencia de la barra de herramientas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Propósito
   * - Open Puppet… / Examples ▾
     - Cargar un ``.puppet`` desde disco, o elegir uno de los rigs incluidos en
       ``examples/puppet/`` directamente desde la barra de herramientas
   * - Import PNG… / Import PSD… / Import Cubism…
     - Auto-malla un PNG, divide en capas un PSD, o muestrea-y-reconstruye un rig
       Cubism. El selector de Cubism acepta tanto ``.moc3`` como ``.model3.json``;
       sin un rig abierto, ambas rutas ejecutan la conversión completa
       ``.moc3 → .puppet`` (SDK Native de Cubism proporcionado por el usuario).
       Elegir ``.model3.json`` mientras un rig está cargado fusiona sus metadatos
       solo-JSON (motions / expressions / physics) en el documento activo en su lugar.
   * - Recent
     - Reabrir rápidamente una marioneta abierta recientemente
   * - Save As…
     - Escribir el rig actual como un zip ``.puppet``
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - Crear el rig desde la barra de herramientas
   * - Drag-track head
     - Offset del cursor → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Ciclo coseno cerrar→abrir en ``ParamEyeLOpen`` / ``ParamEyeROpen``
       cada ~4.5 s (la ruta de escritura forzada salta el omisor sin-cambio del lienzo
       para que los drivers en competencia no puedan detener el parpadeo)
   * - Mic lip-sync
     - RMS del micrófono → ``ParamMouthOpenY`` (requiere ``sounddevice``)
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → yaw / pitch / roll de cabeza +
       ojos + boca (requiere ``opencv-python`` + ``mediapipe``;
       abre un diálogo de vista previa en vivo con los puntos detectados)
   * - Auto idle / Idle motions
     - Ciclo de respiración + deriva en parámetros estándar, más cicleador aleatorio
       opcional a través de movimientos del grupo Idle
   * - Edit mesh
     - Arrastra-y-suelta vértices del lienzo para refinar la malla
   * - Record motion
     - Captura los cambios de parámetros en un nuevo ``Motion`` y lo añade al
       documento — hornear-desde-toma, sin autoría manual de claves
   * - Capture frame… / Record… / Export all motions…
     - Guarda un único PNG, alterna una grabación GIF / WebM / MP4, o renderiza por lotes
       cada movimiento del rig a su propio archivo (todo mediante la misma ruta de render
       off-screen sólo-personaje usada para streaming)
   * - Output > Virtual camera / NDI output
     - Superficies de streaming en vivo — consulte *Streaming en vivo a OBS* más abajo
   * - Reset to rest
     - Detiene en seco el reproductor de movimiento, desactiva cada driver en vivo,
       limpia expresiones / grupos de pose, restaura los valores por defecto de los parámetros
   * - Fit to Window
     - Re-centra y re-escala la marioneta en el lienzo

Grabar sus propios movimientos
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Para capturar una toma personalizada en lugar de crear fotogramas clave a mano:

1. Active **Record motion** en la barra de herramientas — aparece un diálogo de nombre.
2. Mientras graba, arrastre deslizadores, active **Webcam tracking**, deje correr la física
   — cualquier cosa que escriba valores de parámetros.
3. Desactive **Record motion** — el grabador hornea el flujo capturado a 30 Hz en un
   ``Motion`` con una pista de segmento lineal por parámetro que realmente se movió (los
   parámetros que se mantuvieron planos se descartan). El nuevo movimiento aparece en el
   dock **Motions** inferior inmediatamente, listo para reproducir / hacer bucle / guardar.

Los movimientos personalizados guardados de esta forma hacen ida y vuelta a través del mismo
payload JSON ``motions/<name>.json`` que los creados a mano.

Streaming en vivo a OBS
^^^^^^^^^^^^^^^^^^^^^^^

Dos rutas de salida, ambas renderizando la marioneta sola (sin fondo de damero, sin chrome
del editor) en un framebuffer off-screen antes de entregarlo a la superficie de streaming.
El lado más largo de la salida está limitado a 1080 px para que los lienzos nativos de
Cubism (March 7th es 3503×7777) no sean rechazados por los drivers de cámara virtual
DirectShow.

**A. Cámara virtual** — aparece como una webcam en la lista de fuentes *Video Capture
Device* de OBS. ``pip install pyvirtualcam`` más el driver de la plataforma:
OBS Studio 26+ incluye el driver *OBS Virtual Camera* en Windows / macOS (haga clic una vez
en *Start Virtual Camera* en OBS para registrarlo); Linux usa ``v4l2loopback-dkms`` +
``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
La barra de herramientas **Output > Virtual camera** abre el flujo.

DirectShow / AVFoundation / v4l2loopback son sólo-RGB — sin canal alfa — por lo que Imervue
rellena el área fuera del personaje con **magenta #FF00FF** como croma. Elimínelo en OBS
mediante el filtro Color Key:

1. Clic derecho en la fuente Video Capture Device > **Filters**
2. **Effect Filters > + > Color Key**
3. Establezca **Key Color Type** = ``Custom Color``,
   **Custom Color** = HEX ``FF00FF``,
   **Similarity** = ``80–300``,
   **Smoothness** = ``30–50``

El filtro se adhiere a la fuente, de modo que el croma se vuelve a aplicar automáticamente
cada vez que la cámara virtual se reanuda.

**B. Salida NDI** — emisión LAN sub-50 ms que transporta RGBA, de modo que OBS / vMix
componen directamente sobre sus propias escenas sin pasada de croma. ``pip install ndi-python``
+ el runtime de `NDI Tools <https://ndi.video/tools/>`_ + el plugin
`obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_.
La barra de herramientas **Output > NDI output** emite la fuente (nombre por defecto
*Imervue Puppet*).

``ndi-python`` se distribuye sólo como source distribution; pip lo construye desde C++ en
tiempo de instalación. Los usuarios de Windows necesitan Visual Studio Build Tools 2022
(con el workload de C++), CMake en PATH, y el NDI SDK de
<https://ndi.video/for-developers/ndi-sdk/> instalado en la ubicación por defecto con la
variable de entorno ``NDI_SDK_DIR`` apuntando a él.

Consulte ``puppet_guide.md`` § 1.2 para los pasos completos más la lista de solución de
problemas (la cámara muestra magenta, fallo de cmake en ndi-python, estiramiento de la
cámara virtual, etc.).

Dependencias opcionales
^^^^^^^^^^^^^^^^^^^^^^^

* ``sounddevice`` — captura de micrófono para lip-sync
* ``opencv-python`` + ``mediapipe`` — seguimiento facial por webcam
* ``imageio-ffmpeg`` — grabación MP4 / WebM (ya incluido para Slideshow Video)
* ``pyvirtualcam`` — salida de cámara virtual (consulte *Streaming en vivo*)
* ``ndi-python`` — salida NDI (consulte *Streaming en vivo*)
* DLL Cubism Native SDK proporcionada por el usuario — conversión
  ``.moc3 → .puppet`` (la Free Material License de Live2D prohíbe la
  redistribución; los usuarios colocan el SDK bajo ``<cwd>/sdk/`` o establecen
  la variable de entorno ``CUBISM_CORE_DLL``)

El plugin se degrada con elegancia cuando alguna de estas falta — el conmutador correspondiente
en la barra de herramientas se desactiva y muestra una pista "install <package>".
``File > Install dependencies…`` instala por lotes todos los paquetes opcionales de Python
de una sola vez.

----

Espacio de trabajo Desktop Pet (Pestaña Desktop Pet)
----------------------------------------------------

La pestaña 5 — **Desktop Pet** — coloca cualquier personaje ``.puppet``
en su escritorio como una superposición sin marco y transparente. La
pestaña en sí es un panel de control; el personaje real es una ventana
de nivel superior separada que comparte todo el runtime de Puppet
(movimientos, expresiones, físicas, drivers de reposo, entrada de
micrófono / cámara web). La mascota puede reaccionar a clics, ejecutar
animaciones disparadas por temporizador, seguir el cursor, ocultarse
mientras otra aplicación está en pantalla completa y decir frases
personalizadas que usted defina en un archivo JSON.

Este capítulo es una referencia completa de la pestaña. Está organizado
así:

#. **Inicio rápido** — recorrido de cinco pasos desde "acabo de abrir
   Imervue" hasta "hay una marioneta en mi escritorio".
#. **Cargar un rig** — selector de archivos, ejemplo incluido,
   restauración entre arranques.
#. **La ventana de superposición** — todos los comportamientos a nivel
   de ventana (arrastrar para mover, acople a borde, clic-pasante,
   bloqueo de ancla, siempre detrás, ocultar en pantalla completa,
   pausa al ocultar, opacidad, tamaño, restauración multimonitor).
#. **Modelo de interacción** — zonas de impacto para clic izquierdo,
   menú contextual completo del clic derecho, bandeja del sistema.
#. **Drivers en vivo** — seis drivers de entrada opcionales y sus
   dependencias opcionales.
#. **Script de la mascota** — el archivo JSON que le permite reemplazar
   la voz de la mascota con sus propias frases, programar recordatorios
   y enlazar respuestas por zona de impacto / por movimiento.
#. **Persistencia** — qué se recuerda entre arranques y el esquema
   exacto de configuración.
#. **Crear una nueva mascota** — puntero a la pestaña Puppet + el
   formato del archivo ``.puppet``.
#. **Solución de problemas** — sorpresas comunes y qué hacer con ellas.

Inicio rápido
^^^^^^^^^^^^^

1. Cambie a la pestaña **Desktop Pet**.
2. Haga clic en **Load bundled March 7th** para usar el personaje
   incluido, o en **Open Puppet…** para elegir su propio archivo
   ``.puppet``.
3. La superposición aparece en el escritorio y la casilla **Show pet on
   desktop** se marca automáticamente. (Si en algún momento desea
   ocultar la mascota sin cerrar Imervue, desmarque la casilla o use
   el icono de la bandeja del sistema.)
4. Arrastre el personaje al lugar donde lo quiera. Suelte cerca de un
   borde de la pantalla para acoplarlo a ras.
5. Elija los **Live drivers** que desee — respiración en reposo,
   parpadeo, seguimiento del cursor, lip-sync por micrófono,
   seguimiento por cámara web — desde la pestaña del espacio de trabajo
   o desde el menú contextual de la mascota.

Todo lo que configure se conserva en el siguiente arranque, así que el
paso 5 es una decisión única por rig / persona.

Cargar un rig
^^^^^^^^^^^^^

La pestaña expone tres rutas de carga:

* **Open Puppet…** — elija cualquier archivo ``.puppet`` del disco.
* **Load bundled March 7th** — abre el rig incluido en
  ``examples/puppet/march_7th.puppet``. El resolutor consulta primero
  ``examples_dir()`` (seguro para entornos congelados con compilaciones
  empaquetadas con Nuitka / instaladas con pip) y, como alternativa,
  busca una ruta relativa a la raíz del repositorio para que el botón
  funcione en ambos modos de ejecución.
* **Último rig** — el rig cargado previamente se restaura automáticamente
  al iniciar Imervue desde el campo de configuración ``last_rig_path``;
  la pestaña Desktop Pet vuelve a instanciar la superposición de forma
  invisible para que la mascota esté a un clic del mismo estado en el
  que la dejó.

Una carga exitosa marca automáticamente **Show pet on desktop** para
que la mascota aparezca inmediatamente. La ruta de fallo deja la
casilla intacta y escribe el error en la etiqueta de estado de la
pestaña.

La ventana de superposición
^^^^^^^^^^^^^^^^^^^^^^^^^^^

El personaje vive en una ventana de nivel superior separada de la
ventana principal de Imervue. La ventana no tiene marco, no aparece
en la barra de tareas y (por defecto) permanece por encima de todas
las demás ventanas.

.. list-table:: Comportamientos de la ventana
   :header-rows: 1
   :widths: 28 72

   * - Comportamiento
     - Detalle
   * - Superposición sin marco
     - Sin chrome de ventana, sin botones de minimizar / cerrar, sin
       entrada en la barra de tareas. El personaje es toda la
       superficie visible.
   * - Fondo transparente
     - Todo lo que el personaje no cubra es totalmente transparente.
       El escritorio / aplicación detrás de la mascota se ve con
       precisión píxel a píxel.
   * - Arrastrar para mover
     - Pulse el botón izquierdo en cualquier punto del cuerpo,
       arrastre y suelte. El gesto se reconoce como clic solo si el
       cursor se movió menos de seis píxeles — moverse más convierte
       el gesto en un movimiento y el manejador de clic no se dispara.
   * - Acople a borde
     - Suelte cerca de un borde de la pantalla (por defecto: a menos
       de 24 px) y la mascota se "encaja" a ras contra ese borde. El
       umbral es configurable de 0 (desactivado) a 200 (muy pegajoso).
       El acople actúa de forma independiente en cada eje, así que
       arrastrar a una esquina la encaja contra ambos bordes a la vez.
   * - Limitación de desbordamiento
     - Un arrastre que termina más allá del borde de la pantalla se
       reajusta al interior. No se puede dejar la mascota fuera de
       pantalla donde no podría volver a agarrarla.
   * - Modo clic-pasante
     - Cuando está activo, todos los eventos de ratón pasan a través
       de la mascota a lo que haya detrás. El personaje sigue siendo
       visible pero no se puede arrastrar, hacer clic derecho ni usar
       para disparar movimientos. Actívelo cuando la mascota sea
       puramente decorativa.
   * - Bloquear posición
     - Desactiva el arrastrar para mover sin afectar al clic-pasante.
       Útil cuando ha colocado la mascota exactamente donde la quiere
       y no desea que arrastres accidentales la muevan.
   * - Siempre debajo
     - Cambia la mascota de siempre-encima a siempre-debajo. La
       mascota queda detrás del resto de ventanas como un widget de
       escritorio. También desactiva la marca de aceptar foco, así
       que hacer clic en la mascota no la trae al frente.
   * - Ocultar en pantalla completa
     - Un sondeo en segundo plano a 1 Hz observa la ventana en primer
       plano del monitor de la mascota. Cuando esa ventana cubre
       ≥ 99 % de la pantalla con una tolerancia por borde ≤ 4 px
       (detectando tanto pantalla completa real como juegos en
       ventana sin bordes), la mascota se oculta automáticamente.
       Cuando la pantalla completa termina, la mascota reaparece en
       su posición anterior. El detector usa la API Win32
       ``GetWindowRect`` en Windows; en macOS / Linux es no-op de
       forma elegante (la mascota permanece visible).
   * - Pausa al ocultar
     - El tick de pintado a ~30 FPS y el tick de script a 1 Hz se
       detienen en ``hideEvent``, así que una mascota oculta cuesta
       cero CPU. Se reanudan en el siguiente ``showEvent``.
   * - Presets de tamaño
     - Pequeño (200 × 300), mediano (320 × 480), grande (480 × 720).
       La mascota se redimensiona alrededor de su centro actual, así
       que un cambio de tamaño no la reubica. El acople se reejecuta
       después del redimensionado.
   * - Deslizador de opacidad
     - 10 – 100 %. Actúa a nivel de ventana (mediante
       ``setWindowOpacity``), así que toda la mascota se atenúa, no
       solo la textura. El mínimo del 10 % existe para que siempre
       pueda ver y agarrar la mascota — totalmente invisible le
       permitiría perderla.
   * - Memoria de posición
     - Se persiste el ``(x, y)`` posterior al acople tras cada
       liberación. En el siguiente arranque la mascota vuelve a esa
       coordenada de pantalla. Si la posición guardada ya no cae
       dentro de ninguna pantalla conectada (ha desconectado un
       monitor desde el último arranque), la mascota recurre a la
       esquina inferior derecha de la pantalla principal.

Modelo de interacción
^^^^^^^^^^^^^^^^^^^^^

La mascota responde a la entrada del ratón mediante tres canales
independientes.

**Clic izquierdo sobre el cuerpo**

La posición del clic se mapea de vuelta a coordenadas del lienzo de
la marioneta (deshaciendo el desplazamiento / zoom del lienzo) y se
pasa por el pipeline existente de ``hit_test``. El resultado dirige
el comportamiento de la siguiente forma:

#. Si un ``HitArea`` cubre el drawable clicado Y esa zona tiene un
   movimiento asociado, se reproduce el movimiento.
#. Independientemente de si se reprodujo un movimiento, la mascota
   puede mostrar un bocadillo de diálogo — véase la sección *Script
   de la mascota* para la prioridad de selección de frases.
#. Si ninguna zona de impacto cubre el clic, la mascota recurre a un
   saludo (de la lista ``greetings`` del script o del fallback
   incorporado).

Un gesto de arrastrar para mover suprime el manejador de clic, así
que mover la mascota no dispara un movimiento / habla.

**Clic derecho en cualquier lugar del cuerpo**

Abre un menú contextual con la siguiente estructura:

* **Hide pet** — acción de nivel superior que cierra la superposición.
* Submenú **Live drivers** — seis conmutadores marcables (Auto idle,
  Idle motions, Auto-blink, Drag-track head, Mic lip-sync, Webcam
  tracking). El estado de marcado refleja el estado del driver en
  vivo, así que el menú muestra lo que está corriendo actualmente.
* Submenú **Play motion** — poblado a partir de la lista
  ``document.motions`` del rig activo. Seleccionar una entrada
  reproduce ese movimiento (y puede disparar la voz de la mascota
  si el script enlaza una frase a él).
* Submenú **Apply expression** — poblado a partir de
  ``document.expressions`` del rig. Seleccionar conmuta la
  superposición de parámetros de la expresión.
* Cinco conmutadores marcables de nivel superior: **Lock position**,
  **Click-through**, **Always on bottom**, **Hide on fullscreen**,
  **Speech bubble** — acceso rápido a los mismos conmutadores de la
  pestaña del espacio de trabajo.
* Submenú **Size** — Pequeño / Mediano / Grande; el preset actual
  aparece marcado.

Los submenús de movimiento / expresión están desactivados cuando no
hay ningún rig cargado.

**Icono de la bandeja del sistema**

Un icono de bandeja (instanciado solo en plataformas que reportan
soporte de bandeja) ofrece una cuarta superficie para las acciones
más comunes:

* Clic izquierdo alterna la visibilidad de la mascota.
* Clic derecho abre un menú con **Show pet** (marcable),
  **Click-through**, **Open puppet…**, **Hide pet**.
* Los elementos marcables Show / Click-through reflejan el estado
  de marcado del espacio de trabajo mediante ``sync_visibility`` /
  ``sync_click_through``, así que permanecen sincronizados sin
  importar dónde el usuario active el conmutador correspondiente.

Drivers en vivo
^^^^^^^^^^^^^^^

Cada driver en vivo se crea de forma perezosa en la primera
activación, así que una mascota inactiva no paga ningún coste de
temporizador / hilo por los drivers que nunca encienda. El estado de
cada driver se persiste; activar uno, cerrar Imervue y reiniciar
reabre la mascota con los mismos drivers en marcha.

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - Driver
     - Qué hace
     - Dependencia opcional
   * - **Auto idle**
     - Respiración + deriva sutil sobre parámetros estándar
       (``ParamBreath`` etc.) para que el personaje parezca vivo
       cuando nada más se está animando.
     - ninguna
   * - **Idle motions**
     - Elige aleatoriamente un movimiento del grupo ``Idle`` del rig
       cada pocos segundos y lo reproduce. Se detiene si ya hay un
       movimiento en curso.
     - ninguna
   * - **Auto-blink**
     - Cierra y reabre los ojos en una curva coseno suave cada
       ~4,5 s. El driver fuerza la escritura del parámetro para que
       otros drivers que toquen los valores de apertura de ojos no
       supriman el parpadeo.
     - ninguna
   * - **Drag-track head**
     - La cabeza + los ojos giran hacia la posición global del cursor
       incluso cuando el cursor está fuera de la mascota. Mueve
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - ninguna
   * - **Mic lip-sync**
     - La amplitud RMS del micrófono mueve ``ParamMouthOpenY``. El
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker lee su cámara web a ~30 FPS y mueve
       los parámetros de pose de cabeza + apertura de ojos + apertura
       de boca. Abre una pequeña ventana de vista previa en vivo
       para que pueda verificar que la cámara ve su cara.
     - ``opencv-python`` + ``mediapipe``

Los dos drivers con dependencia opcional se degradan con elegancia:
si el paquete requerido no está instalado, al marcar la casilla esta
vuelve a desmarcarse y la etiqueta de estado del espacio de trabajo
muestra una pista "install sounddevice" / "install opencv-python +
mediapipe".

Script de la mascota — voz personalizada y eventos programados
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

El bocadillo de diálogo de la mascota se nutre de un archivo JSON
que usted puede escribir y cargar desde el grupo **Pet script** de la
pestaña. El script gobierna cuatro cosas:

* **Saludos** — frases de clic por defecto cuando no coincide nada
  más específico.
* **Respuestas por zona de impacto** — depósitos de frases por
  ``HitArea.id``.
* **Frases de movimiento** — depósitos de frases por nombre de
  movimiento, disparados cuando la mascota inicia ese movimiento (ya
  sea desde una zona de impacto o desde el menú contextual).
* **Recordatorios programados** — frases dirigidas por temporizador
  que se disparan cada ``every_seconds`` de tiempo monotónico de
  reloj.

Esquema (versionado — los campos futuros son compatibles hacia
adelante):

.. code-block:: json

   {
     "version": 1,
     "name": "March 7th — playful voice",
     "greetings": [
       "Hi!", "Hello hello!", "Need a break?"
     ],
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

Reglas de carga:

* Las listas se muestrean en orden cíclico por depósito para que el
  usuario no vea la misma frase dos veces seguidas.
* Las claves de nivel superior desconocidas se ignoran (compatibilidad
  hacia adelante — un futuro archivo v2 sigue cargándose en un runtime
  v1).
* Las entradas de lista basura (tipo incorrecto, entradas programadas
  malformadas, ``every_seconds`` cero / negativo) se omiten — una
  fila mala no hace fallar toda la carga. Solo el JSON
  completamente inanalizable lanza un error y muestra la ruta en la
  etiqueta de estado.
* La cascada de zona de impacto / movimiento / saludo es por capas:
  un clic izquierdo consulta primero ``hit_responses[area.id]``,
  luego ``motion_lines[area.motion]``, luego ``greetings`` y, como
  base, el conjunto de saludo por defecto incorporado.
* El seguimiento del tiempo usa ``time.monotonic``, así que suspender
  el portátil o saltar el reloj del sistema no puede disparar en
  ráfaga eventos en cola.

**Reset to default** descarta el script del usuario y vuelve al
conjunto de saludo incorporado; la ruta del script persistida se
borra para que el siguiente arranque no la recargue.

Un ejemplo funcional se encuentra en
``examples/desktop_pet/march_7th.petscript.json`` — seis saludos, dos
depósitos por zona de impacto (cabeza / cuerpo), tres frases de
movimiento (wave / curtsy / cheer) y un recordatorio de estiramiento
de 30 minutos. Las frases de cabeza / cuerpo responden a los clics
sobre un rig cuyas zonas de impacto se llaman ``HitAreaHead`` /
``HitAreaBody`` (la convención de Cubism); el rig incluido de
March 7th no define ninguna, así que un clic sobre él elige un
saludo en su lugar.

Persistencia
^^^^^^^^^^^^

Todo el estado de Desktop Pet va y vuelve a través de
``user_setting_dict["desktop_pet"]`` (una ranura en el archivo
estándar de configuración de usuario de Imervue). Cada campo tiene
un valor por defecto + limitación de rango al cargar, así que un
archivo de configuración corrupto no puede hacer fallar el arranque.

.. list-table:: Campos persistidos
   :header-rows: 1
   :widths: 28 18 54

   * - Campo
     - Valor por defecto
     - Notas
   * - ``last_rig_path``
     - ``""``
     - Se restaura automáticamente al arrancar si el archivo todavía
       existe.
   * - ``script_path``
     - ``""``
     - Se restaura automáticamente al arrancar si el script aún se
       analiza; un script ilegible vuelve a los valores por defecto
       de forma silenciosa.
   * - ``position``
     - ``[-1, -1]``
     - Coordenada de pantalla ``(x, y)`` de la última liberación del
       arrastre. ``-1, -1`` significa "usar la esquina inferior
       derecha de la pantalla principal". La desconexión multimonitor
       entre sesiones recurre al mismo fallback.
   * - ``size_preset``
     - ``"medium"``
     - Uno de ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Limitado a ``[0.1, 1.0]``. Los valores fuera de rango vuelven
       al valor por defecto.
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - Mutuamente excluyente con siempre-encima.
   * - ``hide_on_fullscreen``
     - ``true``
     - Establezca ``false`` para mantener la mascota visible durante
       la pantalla completa.
   * - ``snap_threshold``
     - ``24``
     - Limitado a ``[0, 200]`` px.
   * - ``drivers``
     - todos ``false``
     - Subdiccionario indexado por id de driver (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mic_lipsync``, ``webcam_tracking``). Las claves desconocidas
       circulan intactas para compatibilidad hacia adelante.
   * - ``show_on_launch``
     - ``false``
     - Muestra automáticamente la superposición cuando Imervue
       arranca.
   * - ``speech_enabled``
     - ``true``
     - Cuando es falso, el bocadillo de diálogo nunca aparece.

El comportamiento de fusión del diccionario de configuración es de
un nivel de profundidad: los archivos de configuración antiguos a
los que les faltan claves más nuevas siguen produciendo un
diccionario de estado completo al cargar (los valores por defecto
rellenan los huecos); las claves más nuevas que ya guardó sobreviven
a una vuelta atrás a un runtime más antiguo que no las conoce.

Crear una nueva mascota
^^^^^^^^^^^^^^^^^^^^^^^

Cualquier archivo ``.puppet`` funciona como personaje de Desktop
Pet — la pestaña Desktop Pet es puramente un renderizador + capa de
interacción; la autoría de rigs ocurre en la pestaña Puppet (véase
*Espacio de trabajo Puppet (Pestaña Puppet)*).

Para crear su propio rig de mascota:

#. Cambie a la pestaña Puppet e importe un arte vía
   **File > Import PNG…** o **File > Import PSD…**, o traiga un
   modelo Cubism vía **File > Import Cubism…**.
#. Cree deformadores de rotación / warp, parámetros, movimientos,
   expresiones y (opcionalmente) zonas de impacto ligadas a partes
   del cuerpo para que el manejador de clic izquierdo de Desktop Pet
   pueda disparar movimientos.
#. Guarde el rig vía **File > Save As…** en un zip ``.puppet``.
#. Vuelva a la pestaña Desktop Pet y cargue el nuevo archivo vía
   **Open Puppet…**.

Si su rig define entradas ``HitArea``, puede escribir frases de
bocadillo por zona de impacto en un ``.petscript.json`` cuyas
claves ``hit_responses`` coincidan con los ids de las zonas.

Solución de problemas
^^^^^^^^^^^^^^^^^^^^^

**La mascota aparece dentro de un rectángulo gris en lugar de ser
totalmente transparente.** El atributo de fondo translúcido a nivel
del SO requiere una superficie GL consciente de alfa más atributos
coincidentes en el widget GL embebido. Asegúrese de que ninguna
herramienta de gestión de ventanas de terceros esté sobrescribiendo
el atributo ``WA_TranslucentBackground`` en la ventana de
superposición (algunos gestores de ventanas personalizados en Linux
hacen esto). En Windows / macOS debería "simplemente funcionar".

**"Load bundled March 7th" indica que el archivo no se encuentra.**
El resolutor consulta primero ``examples_dir()`` (la ubicación segura
para entornos congelados utilizada por las compilaciones empaquetadas)
y recurre a una ruta relativa al CWD. Si ninguna contiene el rig, la
etiqueta de estado muestra la ruta esperada. Verifique el directorio
``examples/`` que se incluye con su instalación — para checkouts del
código fuente, lance Imervue desde la raíz del repositorio.

**La mascota no habla al hacer clic.** Tres comprobaciones:

#. Asegúrese de que el conmutador **Speech bubble on click** esté
   activo (en la pestaña o en el menú contextual).
#. Si cargó un script personalizado, verifique que el JSON se
   analiza — la etiqueta de estado de la pestaña muestra el error
   de carga.
#. Si un clic en una zona de impacto no hizo nada, probablemente la
   zona no tiene un movimiento coincidente Y el script no tiene una
   entrada ``hit_responses`` para ese id de zona. Bien enlace un
   movimiento a la zona en la pestaña Puppet, bien añada el id de
   la zona a ``hit_responses`` del script.

**La casilla de seguimiento por cámara web se desmarca sola.** El
seguimiento por cámara web necesita ``opencv-python`` y ``mediapipe``
instalados en el mismo entorno Python en el que se está ejecutando
Imervue. Instálelos con ``pip install opencv-python mediapipe``.
Después de la instalación, al marcar la casilla debería aparecer una
pequeña ventana de vista previa mostrando los puntos faciales
detectados.

**La mascota no se oculta automáticamente durante aplicaciones en
pantalla completa.** El detector de pantalla completa sondea la
ventana en primer plano a 1 Hz. En Windows usa la API Win32
``GetWindowRect``; en macOS / Linux no tiene un equivalente
multiplataforma fiable y es no-op (la mascota permanece visible).
Para Windows: asegúrese de que **Hide when other app is fullscreen**
esté marcado y verifique que la ventana en pantalla completa
realmente cubre ≥ 99 % del mismo monitor que la mascota.

**La posición de la mascota se va fuera de la pantalla entre
arranques.** Esto pasa cuando la pantalla en la que estaba la mascota
ya no está conectada en el siguiente arranque (dock del portátil,
segundo monitor desconectado). La mascota recurre automáticamente a
la esquina inferior derecha de la pantalla principal en este caso —
arrástrela a donde la quiera y el siguiente guardado sobrescribirá
la posición obsoleta.

----

Rotación y volteo
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Acción
     - Atajo
     - Menú
   * - Rotar 90 ° en sentido horario
     - ``R``
     - Clic derecho > Modify > Rotate CW
   * - Rotar 90 ° en sentido antihorario
     - ``Shift + R``
     - Clic derecho > Modify > Rotate CCW
   * - Voltear horizontalmente
     - --
     - Clic derecho > Modify > Flip Horizontal
   * - Voltear verticalmente
     - --
     - Clic derecho > Modify > Flip Vertical
   * - Rotación sin pérdida (JPEG)
     - --
     - Clic derecho > Lossless Rotate

----

Exportar imágenes
-----------------

Exportación individual
^^^^^^^^^^^^^^^^^^^^^^

Abra una imagen (Deep Zoom), después clic derecho > ``Export / Save As``.

- Elija el formato: PNG, JPEG, WebP, BMP, TIFF, AVIF; también HEIC y JPEG XL si ``pillow-heif`` / ``pillow-jxl-plugin`` está instalado
- Ajuste la calidad (para formatos con pérdida)
- Elija qué metadatos conservar: todos, todos salvo la ubicación (predeterminado) o ninguno. Se conservan cámara, objetivo y fecha de captura; la elección se recuerda y la exportación por lotes ofrece la misma opción
- Vista previa del tamaño estimado del archivo
- Elija una ubicación de guardado. El nombre propuesto es uno aún libre (``photo_1.png`` junto a ``photo.png``); un archivo existente —sobre todo la propia foto— solo se reemplaza tras confirmarlo

Presets de exportación
^^^^^^^^^^^^^^^^^^^^^^

La exportación por lotes (más abajo) tiene una lista **Preset** que rellena el tamaño, el formato
y la calidad para los destinos habituales; con **Custom** los elige usted:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Preset
     - Salida
   * - **Web — 1600 px JPEG**
     - Lado largo de hasta 1600 px, JPEG calidad 85.
   * - **4K Web — 3840 px JPEG**
     - Lado largo de hasta 3840 px, JPEG calidad 90.
   * - **Print — 300 DPI PNG**
     - Resolución completa, PNG, 300 dpi.
   * - **Instagram — 1080×1080 square**
     - Recorte cuadrado centrado, 1080 × 1080, JPEG calidad 90.
   * - **Thumbnail — 400 px JPEG**
     - Lado largo de hasta 400 px, JPEG calidad 80.

Marca de agua
^^^^^^^^^^^^^

La exportación por lotes también puede dibujar una marca de agua de texto en cada copia exportada:
el texto, su posición (una esquina o el centro) y su opacidad. Los archivos originales nunca se
modifican.

Exportación por lotes
^^^^^^^^^^^^^^^^^^^^^

Seleccione varias imágenes, después clic derecho > ``Batch Operations`` > ``Batch Export``.

- Conversión uniforme de formato
- Establece el ancho / alto máximo (escalado de aspecto automático)
- Control de calidad
- Barra de progreso en tiempo real

Crear GIF / Vídeo
^^^^^^^^^^^^^^^^^

Seleccione varias imágenes, después clic derecho > ``Batch Operations`` > ``Create GIF / Video``.

- Salida GIF y MP4
- Arrastrar para reordenar fotogramas
- Establecer fotogramas por segundo (FPS)
- Dimensiones personalizadas
- Opción de bucle: repetir sin fin o, si está desactivada, reproducir una vez
- Se propone ``output.gif`` junto al primer fotograma, numerado (``output_1.gif``) si ese nombre está ocupado; un nombre escrito que ya existe solo se reemplaza tras confirmarlo

----

Reproducción de animaciones
---------------------------

Al abrir archivos GIF, APNG o WebP animado, la animación se reproduce automáticamente. Una animación que decodificada
ocuparía más de 512 MB se decodifica fotograma a fotograma mientras se reproduce, así
que abrirla no congela la ventana ni llena la memoria.
Un fotograma de 10 ms o menos se muestra 100 ms, como en los navegadores: muchos GIF cuentan con ello.

Un TIFF de varias páginas — un documento escaneado — no se reproduce: muestra una página cada vez, que se pasa con ``,`` y ``.``, y la indicación muestra el número de página. Tampoco se reproducen los fotogramas que no son una animación: la vista previa que la cámara incrusta en un JPEG (MPF), las capas de un PSD y la imagen predeterminada de un APNG, la imagen fija para programas sin soporte de APNG.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``Space``
     - Reproducir / Pausa
   * - ``,``
     - Fotograma anterior
   * - ``.``
     - Fotograma siguiente
   * - ``]``
     - Acelerar
   * - ``[``
     - Ralentizar

----

Comparación de imágenes
-----------------------

En el modo miniaturas, seleccione 2 -- 4 imágenes, después clic derecho > ``Compare Images``.

El diálogo tiene cuatro pestañas:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pestaña
     - Propósito
   * - **Side-by-side**
     - Muestra 2 o 4 imágenes simultáneamente; cada una se autoescala en su panel.
   * - **Overlay**
     - Mezcla dos imágenes con un deslizador alfa (0 → sólo A, 100 → sólo B). Requiere exactamente 2 seleccionadas.
   * - **Difference**
     - Visualización por píxel ``|A − B|`` con un deslizador de ganancia (0.10× – 20×) para amplificar cambios sutiles.
   * - **A | B Split**
     - Vista dividida antes/después con un divisor vertical arrastrable. Arrastre el manejador para barrer entre
       las dos imágenes; ideal para mostrar ajustes de receta de revelado o comparar exportaciones. Requiere exactamente 2 seleccionadas.

Cuando las dos imágenes tienen tamaños diferentes, ``B`` se reescala a las dimensiones de
``A`` con Lanczos. Las imágenes muy grandes se limitan internamente a 2048 px en el lado largo,
para que la superposición / diferencia se mantengan interactivas.

.. seealso::
   Para una comparación en línea sin abrir un diálogo, use **Split View** (``Shift + S``) o
   **Dual-Page Reading** (``Shift + D`` / ``Ctrl + Shift + D``) descritos en la sección
   Examinar.

----

Presentación de diapositivas
----------------------------

Pulse ``S`` o clic derecho > ``Slideshow`` para iniciar una presentación automática.

- Intervalo ajustable por imagen
- Transición opcional con fundido entre imágenes

----

Búsqueda
--------

Pulse ``Ctrl + F`` o ``/`` y escriba una palabra clave para buscar imágenes en la carpeta
actual por nombre de archivo.

La búsqueda usa **emparejamiento difuso** con un rango de tres niveles (prefijo > subcadena
> subsecuencia) y **resaltado de subcadena** en los resultados. Pulse ``Enter`` o haga doble
clic para saltar a una imagen.

Para saltar por **índice de imagen** en lugar de por nombre, pulse ``Ctrl + G`` para el
diálogo Go-to.

----

Copiar y pegar
--------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Acción
     - Método
   * - Copiar imagen al portapapeles
     - ``Ctrl + C`` en el modo Deep Zoom
   * - Pegar imagen del portapapeles
     - ``File`` > ``Paste from Clipboard``, o ``Ctrl + V``
   * - Monitorización automática del portapapeles
     - ``File`` > ``Auto-annotate Clipboard Images`` (conmutador)

.. note::
   Cuando la monitorización automática está activada, cada vez que aparece una nueva imagen en el portapapeles (p. ej. desde una herramienta de captura de pantalla), el editor de anotaciones se abre automáticamente.

----

Eliminar imágenes
-----------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Acción
     - Método
   * - Eliminar la imagen actual
     - Pulse ``Delete``
   * - Eliminar las imágenes seleccionadas
     - Seleccione varias, después ``Delete`` o clic derecho > ``Delete Selected``

Las imágenes se mueven a la Papelera de reciclaje / Papelera del sistema y se pueden recuperar
desde allí. En una unidad sin papelera (tarjeta de memoria, memoria USB o
unidad de red, donde Windows la borraría para siempre) el archivo se conserva: al cerrar,
Imervue enumera esos archivos y pregunta si borrarlos definitivamente.

Sus sidecars van con ellas: ``IMG.JPG.xmp``, ``IMG.JPG.annotations.json`` e
``IMG.xmp``, salvo que el RAW de un par RAW + JPEG todavía use este último. Un
sidecar abandonado pegaría su valoración y sus ediciones al siguiente ``IMG.*``
que la cámara escriba con el mismo nombre.

----

Operaciones por lotes
---------------------

En el modo miniaturas, seleccione varias imágenes, después clic derecho > ``Batch Operations``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Función
     - Descripción
   * - Renombrado por lotes
     - Renombrar usando plantillas: ``{name}``, ``{n}``, ``{ext}``
   * - Mover / Copiar
     - Mover o copiar imágenes a otra carpeta
   * - Rotar todas
     - Rotar todas las imágenes seleccionadas a la vez
   * - Exportación por lotes
     - Convertir formato y redimensionar en bloque
   * - Crear GIF / Vídeo
     - Animar la selección como GIF o MP4 (consulte *Crear GIF / Vídeo*)
   * - Etiquetar por ubicación
     - Añadir a las palabras clave XMP de cada foto con geotag la ciudad y el país más cercanos
   * - Indexar palabras clave
     - Añadir a la biblioteca las palabras clave XMP de la selección
   * - Descarte automático: borrosas
     - Marcar las fotos borrosas como Reject
   * - Descarte automático: baja calidad
     - Marcar como Reject el cuarto más flojo de la selección (nitidez, exposición, contraste)
   * - Rotación automática por EXIF
     - Guardar una copia PNG enderezada de cada foto como ``<name>_oriented.png``
   * - Combinar en PDF / TIFF…
     - Reunir la selección, en el orden de la vista, en un único PDF o TIFF de varias páginas
   * - Importar a carpetas por fecha…
     - Copiar la selección en carpetas ``YYYY/MM`` según la fecha de captura (EXIF o, si no, la
       fecha del archivo); un archivo que ya esté allí conserva su nombre y el recién llegado recibe ``_1``
   * - Añadir a etiqueta
     - Aplica la misma etiqueta a todas las imágenes seleccionadas
   * - Añadir a álbum
     - Coloca todas las imágenes seleccionadas en un álbum

Mover o copiar nunca sobrescribe un archivo con el mismo nombre: llega como
``name_1.ext``. Una foto renombrada o movida en Imervue — renombrado por lotes,
renombrado por tokens, árbol de carpetas, Mover / Copiar, doble panel, bandeja de
preparación, organizador de imágenes — conserva su valoración, favorito,
etiquetas, etiqueta de color, título, descripción, nota de la biblioteca y marca
de selección (una carpeta renombrada o movida, las de todas sus fotos). Sus
sidecars la acompañan: ``IMG.xmp``, ``IMG.JPG.xmp`` e
``IMG.JPG.annotations.json``. Un ``IMG.xmp`` que todavía usa el RAW de un par
RAW + JPEG se copia en lugar de moverse.

Una foto renombrada en otro programa mientras su carpeta está abierta en Imervue
conserva los mismos datos; los datos que ya tenía el nombre nuevo se dejan como
están.

----

Histograma RGB
--------------

Pulse ``H`` en el modo Deep Zoom para superponer un histograma RGB sobre la imagen. Pulse de
nuevo para ocultarlo.

----

Establecer como fondo de pantalla
---------------------------------

Clic derecho en el modo Deep Zoom > ``Set as Wallpaper`` para establecer la imagen actual
como fondo de escritorio.

Compatible con Windows, macOS y Linux (GNOME).

Windows deja el escritorio en negro, e informa de que todo fue bien, cuando recibe un archivo que no puede decodificar. Por eso, una imagen que no es JPEG, PNG ni BMP —un RAW de cámara, HEIC, PSD, TGA, WebP y los demás formatos que abre Imervue— y una foto que hay que enderezar se entregan como una copia JPEG de lo que muestra el visor. La copia se guarda en ``%LOCALAPPDATA%\Imervue\wallpaper`` (``~/.local/share/imervue/wallpaper`` en macOS y Linux); solo se conserva la más reciente.

----

Multi-ventana
-------------

``File`` > ``New Window`` abre otra ventana independiente de Imervue. Cada ventana puede
explorar una carpeta diferente.

Presets de diseño de espacio de trabajo
---------------------------------------

``File`` > ``Workspaces…`` captura la geometría actual de la ventana, la disposición de docks
/ barras de herramientas, los tamaños de los divisores y la carpeta raíz activa bajo un nombre
— después le permite alternar entre diseños guardados de la misma forma que otros gestores de
fotos compatibles con XMP cambian entre *Library* / *Develop* / *Export*, o Adobe Bridge cambia
entre *Metadata* / *Filmstrip*. El diálogo admite Save Current, Load, Rename y Delete. Los
espacios de trabajo persisten en ``user_settings.json`` (bajo la clave ``workspaces``) y
sobreviven entre sesiones.

.. tip::
   Construya un espacio de trabajo **Browse** con el árbol y la cuadrícula de miniaturas
   visibles, y un espacio de trabajo **Develop** separado con el panel de revelado maximizado
   y el árbol contraído. Un solo clic mueve toda su ventana a la forma adecuada para cada tarea.

Gestos del touchpad
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Gesto
     - Acción
   * - Pellizco
     - Acercar / alejar en Deep Zoom (anclado en el centro del pellizco)
   * - Deslizar horizontalmente
     - Imagen anterior / siguiente

----

Asociación de archivos (Windows)
--------------------------------

Registrar Imervue como visor de imágenes en el Explorador de Windows:

1. ``File`` > ``File Association`` > ``Register 'Open with Imervue'``
2. Se requieren privilegios de administrador.
3. Tras el registro, clic derecho en cualquier imagen en el Explorador para ver la opción ``Open with Imervue``.

Para eliminar: ``File`` > ``File Association`` > ``Remove file association``.

----

Sistema de plugins
------------------

Imervue admite plugins para funcionalidad extendida.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Acción
     - Ubicación en el menú
   * - Ver plugins instalados
     - ``Plugins`` > ``Manage Plugins``
   * - Descargar nuevos plugins
     - ``Plugins`` > ``Download Plugins``
   * - Abrir la carpeta de plugins
     - ``Plugins`` > ``Open Plugin Folder``
   * - Recargar plugins
     - ``Plugins`` > ``Reload Plugins``

----

Idioma
------

Cambie el idioma de la interfaz desde el menú ``Language``:

- Inglés
- Chino tradicional (繁體中文)
- Chino simplificado (简体中文)
- Coreano (한국어)
- Japonés (日本語)

Se requiere reiniciar tras el cambio.

Los plugins pueden añadir idiomas propios. **Español** se distribuye exactamente así:
instala el plugin ``spanish_translation`` desde el descargador de plugins y aparecerá en el
menú ``Language`` junto a los cinco idiomas integrados. Un plugin también puede aportar
traducciones a un idioma existente; las claves que ya existen nunca se sobrescriben, así que
un plugin no puede romper una cadena de fábrica.

----

Referencia de atajos de teclado
-------------------------------

Navegación
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``Left`` / ``Right``
     - Imagen anterior / siguiente
   * - Teclas de flecha
     - Mover el recuadro de foco por las miniaturas
   * - ``Ctrl + Shift + Left`` / ``Right``
     - Saltar a la carpeta hermana anterior / siguiente con imágenes
   * - ``Alt + Left`` / ``Alt + Right``
     - Historial atrás / adelante (estilo navegador)
   * - ``Ctrl + G``
     - Saltar a imagen por número
   * - ``X``
     - Saltar a una imagen aleatoria
   * - Rueda del ratón / Pellizco
     - Acercar / alejar
   * - Deslizar horizontalmente
     - Imagen anterior / siguiente
   * - Clic central + arrastrar
     - Encuadre
   * - ``F``
     - Pantalla completa
   * - ``Shift + Tab``
     - Modo cine (ocultar todo el chrome)
   * - ``Ctrl + L``
     - Alternar modo Cuadrícula ↔ Lista (detalle)
   * - ``Shift + S``
     - Vista dividida (dos imágenes una al lado de la otra)
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - Lectura a doble página / RTL (manga)
   * - ``Ctrl + Shift + M``
     - Reflejar la imagen actual en un segundo monitor
   * - ``Esc``
     - Volver a miniaturas / salir de pantalla completa / cerrar modo doble o lista
   * - ``W``
     - Ajustar al ancho
   * - ``Shift + W``
     - Ajustar al alto
   * - ``Shift + F``
     - Ajustar a la ventana
   * - ``-`` / ``=``
     - Alejar / acercar el zoom
   * - ``V``
     - Modo lectura: ajustar al ancho, desplazarse para leer, pasar a la siguiente imagen al llegar al final
   * - ``Home``
     - Ajustar la imagen entera a la ventana (en la cuadrícula: volver arriba)

Edición
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``E``
     - Abrir el editor de anotaciones
   * - ``R``
     - Rotar en sentido horario
   * - ``Shift + R``
     - Rotar en sentido antihorario
   * - ``Ctrl + Z``
     - Deshacer
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Rehacer
   * - ``Delete``
     - Eliminar imagen

Organización
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``0``
     - Alternar favorito
   * - ``1`` -- ``5``
     - Valorar (pulse de nuevo para borrar)
   * - ``F1`` -- ``F5``
     - Etiqueta de color: rojo / amarillo / verde / azul / púrpura (misma tecla para borrar)
   * - ``P``
     - Cull: Pick (marcar para conservar)
   * - ``Shift + X``
     - Cull: Reject
   * - ``U``
     - Cull: Unflag
   * - ``B``
     - Alternar marcador
   * - ``T``
     - Gestor de etiquetas y álbumes

Herramientas y superposiciones
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``Ctrl + F`` / ``/``
     - Búsqueda difusa con resaltado de subcadena
   * - ``Ctrl + C``
     - Copiar imagen al portapapeles
   * - ``Ctrl + V``
     - Pegar desde el portapapeles
   * - ``H``
     - Histograma RGB
   * - ``F8`` / ``Ctrl + F8``
     - Información OSD superpuesta / HUD de depuración (VRAM, caché, hilos)
   * - ``Shift + P``
     - Vista de píxeles (≥ 400 % muestra cuadrícula de píxeles y valor RGB bajo el cursor)
   * - ``Shift + M``
     - Recorrer los modos de color (Normal / Escala de grises / Invertir / Sepia)
   * - ``L``
     - Lupa: una lente de aumento que sigue al cursor (también sobre las miniaturas)
   * - ``S``
     - Presentación
   * - ``Ctrl + Shift + P``
     - Paleta de comandos
   * - ``Alt + M``
     - Reproducir la última macro sobre la selección

Imágenes animadas
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``Space``
     - Reproducir / Pausa
   * - ``,``
     - Fotograma anterior
   * - ``.``
     - Fotograma siguiente
   * - ``[``
     - Ralentizar
   * - ``]``
     - Acelerar

----

Biblioteca y gestión de metadatos
---------------------------------

Imervue mantiene un índice respaldado por SQLite en ``%LOCALAPPDATA%/Imervue/library.db``
(Windows) o ``~/.cache/imervue/library.db`` (POSIX) para búsqueda entre carpetas, etiquetas
jerárquicas, álbumes inteligentes, hashes perceptuales, notas y marcadores de descarte.
Todo lo siguiente vive bajo ``Extra Tools`` salvo que se indique. A partir de la última
versión, el menú está organizado en ocho submenús agrupados por función —
``Batch``, ``Library & Metadata``, ``Views``, ``Workflow``, ``Export``,
``Develop (Non-Destructive)``, ``Retouch & Transform``, y ``Multi-Image`` —
por lo que cada ruta a continuación se muestra como
``Extra Tools`` > ``<submenú>`` > ``<herramienta>``.

Búsqueda en la biblioteca
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` le permite añadir una o más
**carpetas raíz** a un índice global que se rastrea en un hilo en segundo plano. Una vez que
una raíz está indexada puede buscar en ella por nombre de archivo, ancho / alto mínimo y tamaño
de archivo (hasta 2000 resultados); haga doble clic en un resultado para abrirlo.

Clic derecho > ``Search by Query…`` filtra la carpeta actual con un lenguaje de consulta compacto, por ejemplo ``kw:beach rating:>=4 type:video place:Paris``. ``place:`` admite una ciudad, un país o ambos (``Paris``, ``France``, ``Paris, France``); un valor con espacios va entre comillas dobles (``place:"Rio de Janeiro"``).

Álbumes inteligentes
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` persiste reglas de filtro
(extensiones, dimensiones mínimas, etiquetas de color, valoración, favoritos, estado de
descarte, etiquetas jerárquicas, subcadena de nombre) bajo un nombre amigable. Reaplicar un
álbum filtra la carpeta activa por las reglas guardadas.

Búsqueda de imágenes similares
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` ejecuta un pHash DCT de 64
bits sobre la imagen actual en deep-zoom (o sobre el primer mosaico seleccionado) y lista las
coincidencias cercanas del índice ordenadas por distancia de Hamming. Ajuste el spin
``Max distance`` para ampliar o restringir el ámbito.

Búsqueda semántica (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Semantic Search`` le permite escribir una frase en lenguaje natural (por
ejemplo *"golden retriever en la nieve"* o *"calle de neón por la noche"*) y devuelve, clasificadas,
las imágenes de la carpeta abierta. Cada imagen se incrusta con un encoder visual/lingüístico
CLIP y se almacena junto a su ruta; una consulta de texto se incrusta en el mismo espacio
vectorial y se compara por similitud coseno.

Las incrustaciones se almacenan en caché en ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) o ``~/.cache/imervue/clip_cache.npz`` (POSIX) como un único archivo ``.npz`` compacto. El diálogo busca en la carpeta abierta: solo incrusta las imágenes que la caché aún no tiene o que cambiaron desde entonces (tamaño o fecha de modificación), así que buscar otra vez en la misma carpeta empieza al instante, y los resultados vienen solo de esa carpeta.

.. note::
   Semantic Search requiere los paquetes opcionales ``open_clip_torch`` y ``torch``. Si no
   están instalados, la entrada del menú explica qué falta y otras funciones siguen
   funcionando.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` aplica etiquetas heurísticas
bajo ``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` / ``portrait``),
deducidas de la saturación del color, los bordes y la forma de la imagen tal como la muestra el
visor. Se ejecuta en un hilo de trabajo con una barra de progreso en vivo.

Etiquetas jerárquicas
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gestiona etiquetas con
estructura de árbol como ``animal/cat/british``. Seleccione una etiqueta para ver todas las
imágenes bajo esa rama (descendientes incluidos). Etiquete o desetiquete la selección actual
con un clic. Las etiquetas jerárquicas viven en el índice de la biblioteca y son
complementarias al sistema de etiquetas planas del menú contextual.

``Index Keywords`` del menú contextual añade a la biblioteca las palabras clave XMP de
la selección. Una jerarquía de palabras clave escrita por Lightroom o darktable
(``lr:hierarchicalSubject``, ``Places|Taiwan|Taipei``) se archiva como la ruta de
etiqueta ``Places/Taiwan/Taipei``, y las palabras sueltas ``Places`` / ``Taiwan`` /
``Taipei`` que solo repiten sus niveles no se añaden otra vez.

Renombrado por lotes con tokens
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` abre una tabla con vista previa en vivo
donde escribe una plantilla como ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` y ve
exactamente cómo se renombrará cada archivo. Los conflictos se resaltan para que nada se
sobrescriba. Tokens admitidos: ``{name} {ext} {counter[:NN]} {date[:fmt]} {width} {height}
{wxh} {size_kb} {camera} {year} {month} {day} {hour} {minute}``. Un nombre nuevo que ahora tiene otro archivo
seleccionado no es un conflicto: renumerar (``002`` → ``003`` mientras ``003`` →
``004``) o intercambiar dos nombres renombra toda la selección. Batch Rename hace lo
mismo.

Exportación de metadatos
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` escribe una fila
por imagen en la vista actual cubriendo EXIF, dimensiones, etiqueta de color, valoración,
favorito, etiquetas jerárquicas, estado de descarte y notas. Útil para alimentar decisiones
de descarte en una hoja de cálculo o en un flujo de trabajo externo.

Archivos secundarios XMP (interoperabilidad con otros gestores con soporte XMP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue puede leer y escribir archivos secundarios Adobe XMP (``photo.jpg`` ↔ ``photo.xmp``)
para que valoraciones, títulos, descripciones, palabras clave y etiquetas de color hagan ida
y vuelta limpiamente con otros gestores de fotos con soporte XMP, Bridge, y otras
herramientas con soporte XMP.

Al guardar se fusiona con el sidecar existente: solo cambian estos campos, así que los ajustes de revelado, el recorte y el historial de otro programa se conservan, y un sidecar ilegible nunca se sobrescribe.

Además de ``photo.xmp`` (Lightroom, Bridge), se lee y actualiza el
``photo.jpg.xmp`` que escriben darktable y digiKam cuando es el único sidecar.
Las etiquetas de color se entienden con las palabras de Lightroom (``Red`` …
``Purple``) y las de Bridge (``Select``, ``Second``, ``Approved``, ``Review``,
``To Do``), y se exportan como las escribe Lightroom; una etiqueta sin color (una
personalizada) se deja en el sidecar.

Una foto rechazada — ``xmp:Rating`` -1 en Lightroom, Bridge y darktable — se
importa como **Reject** de la selección sin estrellas, y un Reject se exporta como
-1. Un sidecar no rechazado quita un Reject; un Pick no cambia.

Un archivo sin sidecar se lee — y se importa — desde lo que él mismo incrusta: su
paquete XMP (JPEG, PNG, WebP, TIFF, CR3, RW2, ORF, RAF) y luego su ``Rating`` / ``RatingPercent``
EXIF. Ahí guarda Lightroom la valoración y las palabras clave de un JPEG, y ahí
guardan sus estrellas el Explorador de Windows y algunas cámaras. Si hay sidecar,
manda el sidecar.

``Extra Tools`` > ``Library & Metadata`` > ``XMP Sidecars`` tiene dos botones que se aplican a
todas las imágenes de la vista actual:

- **Export sidecars** — escribe la valoración / título / descripción / palabras clave /
  etiqueta de color de cada imagen en su archivo secundario.
- **Import sidecars** — los vuelve a leer en los registros propios de Imervue.

El parseo XML usa ``defusedxml`` para que los archivos secundarios mal formados o maliciosos
no puedan disparar ataques XXE / billion-laughs.

La **barra lateral EXIF** también expone una **tira de valoración por estrellas** clicable —
la valoración que establece es la que escribirá la exportación XMP.

Descarte (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^^

Marcador de descarte de tres estados basado en banderas. Pulse ``P`` para marcar la imagen
actual o cada mosaico seleccionado, ``Shift + X`` para rechazar, ``U`` para quitar la marca.
``Filter`` > ``By Cull State`` muestra sólo picks, rejects o sin marcar. ``Extra Tools`` >
``Culling`` aplica el filtro mediante un diálogo y también expone un botón **Delete all
rejects** que elimina permanentemente del disco los archivos marcados.

Bandeja de preparación
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` es una cesta entre carpetas. Añada cualquier
conjunto de mosaicos a la bandeja (la lista sobrevive a los reinicios), después mueva o copie
toda la bandeja a una carpeta de destino con un clic. Útil para reunir selecciones de varias
sesiones antes de exportar.

Gestor de archivos de doble panel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` abre una vista de doble panel con
dos árboles. Elija una carpeta en cada panel y mueva/copie la selección entre ellos sin salir
de Imervue.

Vista de línea de tiempo
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` agrupa el conjunto de imágenes actual por día,
mes o año (agrupado por fecha). La fecha se toma de EXIF ``DateTimeOriginal`` cuando está
presente, en caso contrario de la fecha de modificación del archivo. Haga doble clic en
cualquier imagen para abrirla en Deep Zoom.

Arrastrar fuera a aplicaciones externas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pulse y arrastre desde un mosaico **seleccionado** para soltar el archivo en el Explorador,
Chrome, Discord o cualquier aplicación que acepte URLs de archivos. La vista previa del
arrastre es la miniatura del mosaico.

Notas por imagen
^^^^^^^^^^^^^^^^

La barra lateral EXIF incluye una caja **Notes** de texto libre. Al escribir se autoguarda en
el índice de la biblioteca tras un breve debounce. Las notas viajan con la ruta de la imagen,
de modo que sobreviven a los re-escaneos de carpetas.

----

Revelado y composición avanzados
--------------------------------

Curva tonal
^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` abre un editor de curvas con
puntos arrastrables y cuatro canales (RGB, R, G, B). Clic izquierdo en lienzo vacío para
añadir un punto; arrastre para mover; clic derecho para eliminar. Los puntos se interpolan
con un spline cúbico monótono y se almacenan en la receta de la imagen, de modo que la curva
se aplica no destructivamente en tiempo de render.

Aplicar LUT .cube
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` le permite elegir
cualquier archivo Adobe ``.cube`` (1D o 3D, hasta 64³). ``LUT_1D_INPUT_RANGE`` /
``LUT_3D_INPUT_RANGE`` de DaVinci Resolve fija el rango de entrada igual que
``DOMAIN_MIN`` / ``DOMAIN_MAX``, y también se lee un archivo guardado con BOM. La LUT se parsea con un ``lru_cache``
clave por ruta + mtime, se evalúa con interpolación trilineal, y se mezcla contra el original
mediante un deslizador de intensidad. La ruta de la LUT y la intensidad viven en la receta.

Copias virtuales
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` da a cada imagen instantáneas con nombre
de recetas. Capture la edición actual, siga experimentando, y vuelva a cualquier variante
anterior más tarde. Las variantes se sitúan junto a la receta maestra en el almacén de
recetas y sobreviven al restablecimiento de la maestra a la identidad.

Fusión HDR
^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` combina dos o más exposiciones embracketadas
en una sola imagen mediante la fusión de exposiciones Mertens de OpenCV. La casilla opcional
"Align exposures" ejecuta primero ``cv2.AlignMTB`` para compensar el temblor de cámara en mano.
La salida se guarda en un archivo elegido por el usuario — no toca ninguna imagen de origen.

Costura de panorama
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` envuelve la API de alto nivel
``Stitcher`` de OpenCV. Elija el modo **Panorama** para paisajes / urbanismos o el modo
**Scans** para documentos planos y obras de arte. Los bordes negros producidos por el warp
pueden recortarse automáticamente.

Apilado de foco
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` fusiona varias tomas hechas a
distancias de enfoque diferentes. Por cada píxel, el algoritmo elige el fotograma de entrada
que tenga la mayor nitidez local (varianza Laplaciana), después suaviza la máscara de
selección con una mezcla gaussiana para evitar costuras. La alineación ECC está activada por
defecto para pequeños desplazamientos en mano.

Pincel corrector
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` muestra la imagen actual a un
lado largo de hasta 720 px. Clic izquierdo añade un punto circular; clic derecho sobre un
punto existente lo quita; el deslizador de radio establece el tamaño del nuevo punto. Al
aplicar, el inpainting de OpenCV (Telea por velocidad, Navier-Stokes por mezcla más suave)
rellena cada región enmascarada desde los píxeles circundantes y el resultado se guarda en
un archivo nuevo.

Corrección de lente
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` expone cuatro deslizadores
puros en numpy: distorsión radial ``k1`` (barril / cojín), levantamiento de viñeteado, y
escala radial de aberración cromática por canal para rojo y azul. La imagen corregida se
guarda como un archivo nuevo — la corrección de lente no es parte de la receta porque la
forma de la salida puede cambiar.

Vista de mapa
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` traza todas las imágenes con geotag de la
biblioteca actual en un mapa Leaflet + OpenStreetMap interactivo (requiere
``PySide6.QtWebEngineWidgets``). Sin WebEngine, el diálogo recurre a una lista simple de
entradas ``(path, lat, lon)`` para que la función siga siendo usable en instalaciones
mínimas.

Vista de calendario
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` muestra un ``QCalendarWidget`` con los días
resaltados cuando se tomaron fotos ese día (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → mtime del archivo). Seleccionar una fecha lista sus imágenes; doble
clic para abrir una en el visor principal.

Detección de rostros
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` ejecuta el cascade Haar frontal
de rostros de OpenCV sobre la imagen actual y dibuja cada detección como un rectángulo. Haga
doble clic en una fila de la lista para escribir el nombre de una persona; al guardar, las
etiquetas se escriben en el blob ``extra['face_tags']`` de la receta. La detección es una
técnica clásica — la precisión es adecuada para "muéstrame las caras" pero no es un
reemplazo del reconocimiento moderno basado en CNN.
Requiere OpenCV 4 (``pip install "opencv-python<5"``): OpenCV 5 eliminó los cascades
Haar, y en ese caso el diálogo lo indica en lugar de detectar.

Máscaras de ajuste local
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` superpone
máscaras de pincel, radiales o de degradado lineal sobre la imagen. Cada máscara lleva sus
propios deltas de exposición, brillo, contraste, saturación, temperatura y tinte más un
deslizador de difuminado. Las máscaras se guardan en ``recipe.extra['masks']`` y se aplican
no destructivamente en tiempo de carga, de modo que el archivo subyacente nunca se toca.

Tono dividido
^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` aplica tonos distintos a
las sombras y las luces con saturación por región y un pivote de balance. Almacenado en
``recipe.extra['split_toning']`` y aplicado después de la curva tonal en el pipeline de
revelado.

Sello de clonar
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` copia un parche fuente difuminado
sobre un destino — el complemento de borde duro al pincel corrector. Shift+clic establece la
fuente, un clic normal estampa, clic derecho deshace. El resultado se escribe en un archivo
nuevo, de modo que el original queda intacto.

Recortar / Enderezar
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` combina un rectángulo de
recorte normalizado (0..1) con un ángulo de enderezamiento arbitrario. La salida se
recorta automáticamente al rectángulo interior más grande, de modo que las fotos rotadas no
tienen esquinas negras.

Enderezamiento automático
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` detecta el horizonte dominante
o las líneas verticales mediante la detección de líneas de Hough y propone una rotación. Un
clic aplica el enderezamiento; puede ajustar el ángulo primero si la auto-detección elige la
referencia equivocada.

Reducción de ruido / Enfoque
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` aplica un
denoise bilateral (con preservación de bordes) seguido de un enfoque de máscara de desenfoque.
"Luminance only" mantiene intacto el ruido de color pero aplana el grano sin emborronar los
bordes de croma.

Cielo / Fondo
^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` reemplaza el cielo detectado
con un degradado o elimina el fondo a transparente / blanco. Cuando ``rembg`` (U²-Net) está
instalado, la máscara de primer plano viene de la red de segmentación; si no, se usa la regla
HSV heurística.

Soft Proof
^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` carga un perfil ICC, convierte
la imagen a través de él y de vuelta, y resalta los píxeles que se recortaron durante el ida
y vuelta en magenta — una comprobación rápida de fuera de gamut antes de imprimir.

Efectos tonales y creativos
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` reúne un conjunto de efectos de
aplicar-y-guardar de un solo paso, cada uno un fino diálogo de controles deslizantes
sobre una transformación en NumPy puro (la misma lógica también se expone como
herramienta MCP):

- **Graduated Density** — un degradado de densidad neutra lineal definido por ángulo,
  dureza y desplazamiento, opcionalmente teñido; oscurece un cielo o un primer plano sin
  una máscara manual.
- **Tone Equalizer** — exposición independiente por zona de luminancia (un control
  deslizante para cada uno de negros → blancos) sobre una máscara suavizada, de modo que
  el ajuste sigue los tonos de la escena.
- **Detail Equalizer** — un control deslizante de ganancia por banda de frecuencia
  (textura fina → contraste grueso), la alternativa multiescala a un único control de
  claridad.
- **Filmic Tone Map** — una caída de luces Reinhard o Hable con contraste pivoteado y
  una restauración de saturación, para exposiciones únicas de alto contraste.
- **Velvia** — un refuerzo de saturación ponderado por luminancia que intensifica los
  colores apagados sin tocar los ya saturados ni las sombras.
- **Film Negative** — invierte un negativo de color escaneado, descontando la base
  naranja de la película estimada automáticamente, con un control de gamma de salida.
- **Defringe** — desatura los flecos púrpura/verde de aberración cromática a lo largo de
  los bordes de alto contraste, dejando intacto el color plano.
- **Emboss** — un relieve de luz direccional a partir del campo de altura de luminancia
  (azimut / elevación / profundidad + un conmutador de escala de grises).
- **Polar Coordinates** — envuelve el fotograma en un disco o lo desenrolla (el aspecto
  tiny-planet / de inversión polar).
- **Kaleidoscope** — refleja una cuña angular en simetría de ``n`` pliegues.
- **Frosted Glass** — una dispersión local de píxeles determinista y reproducible por
  semilla.
- **Frame & Caption** — un borde mate de cualquier color, una franja inferior opcional
  más gruesa estilo Polaroid y una leyenda incrustada en ella con su propio color.

Geoetiqueta GPS
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lee cualquier etiqueta GPS existente
de EXIF y le permite editar o establecer nuevas coordenadas en grados decimales. Un JPEG se
escribe in situ sin paquetes extra: solo cambia su bloque EXIF, así que los píxeles, las demás
etiquetas y la miniatura quedan igual. Un WebP se trata igual; los demás formatos no se pueden etiquetar.

El **editor EXIF** (botón ``Edit EXIF`` de la barra lateral EXIF) cambia la descripción, el artista, el copyright, la marca / modelo de la cámara y el comentario. Un JPEG o WebP no necesita paquetes extra y solo se reescribe su bloque EXIF; los demás formatos explican por qué no se pueden editar.

Galería web
^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Web Gallery`` guarda las imágenes seleccionadas (o toda la
carpeta) como un sitio autocontenido: ``index.html`` con lightbox, miniaturas JPEG y copias de los
originales, salvo que desmarque **Copiar los originales a tamaño completo**. Puede elegir el título
de la página y el tamaño y la calidad de las miniaturas. La página no necesita servidor: ábrala
desde el disco o súbala a cualquier alojamiento estático.

Marque **Revisión del cliente** para enviar la galería y recoger opiniones. Cada imagen recibe un
cuadro de comentario; las notas se quedan en el navegador del revisor y el botón
**Export comments** de la página las guarda todas en un único archivo JSON.

Diseño de impresión
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` compone varias imágenes en un PDF de varias
páginas con tamaño de página, orientación, cuadrícula, márgenes, canalón y marcas de recorte
configurables. Requiere ``reportlab``.

----

Uso desde la línea de comandos
------------------------------

::

   imervue                        # Launch normally
   imervue /path/to/image         # Open a specific image
   imervue /path/to/folder        # Open a specific folder
   imervue --debug                # Enable debug mode
   imervue --software_opengl      # Use software rendering (when GPU is unsupported)

CLI por lotes sin interfaz
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Imervue.cli`` ejecuta las operaciones de imagen puras desde el shell **sin arrancar
Qt**, lo que lo hace utilizable desde scripts, pasos de CI y servidores sin pantalla::

   py -m Imervue.cli resize photos/ --max 1600 --out web/
   py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
   py -m Imervue.cli info *.png --json
   py -m Imervue.cli list-ops          # imprime todos los subcomandos disponibles

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Subcomando
     - Propósito
   * - ``info`` / ``stats``
     - Dimensiones y formato; métricas de calidad sin referencia (``--json`` para salida legible por máquina)
   * - ``convert`` / ``resize`` / ``thumbnail``
     - Conversión de formato (``--format`` / ``--quality``), redimensionado por lado largo máximo, caja de miniatura
   * - ``watermark`` / ``optimize``
     - Marca de agua de texto (``--text`` / ``--corner`` / ``--opacity``); codificar bajo un presupuesto ``--max-kb``
   * - ``dehaze`` / ``clahe`` / ``dither`` / ``distort``
     - Eliminación de neblina por canal oscuro, ecualización adaptativa, tramado Bayer ordenado, swirl / pinch / ripple
   * - ``auto-orient`` / ``strip``
     - Fijar la orientación EXIF en los píxeles; volver a guardar sin EXIF / XMP / ICC
   * - ``collage`` / ``anaglyph``
     - Montaje en cuadrícula (``--columns``); 3D rojo-cian a partir de un par estéreo (``--method``)
   * - ``preset`` / ``pipeline``
     - Aplicar un preajuste de revelado guardado por nombre; ejecutar una cadena JSON ordenada de operaciones
   * - ``list-ops``
     - Listar todos los subcomandos (``--json`` para salida legible por máquina)

Cada subcomando decodifica como el visor: las salidas se enderezan según la orientación EXIF y se convierten a sRGB desde el perfil de color incrustado, las entradas AVIF las lee el propio Pillow, y las HEIC / JPEG XL se leen cuando su backend opcional está instalado. Un RAW de cámara se revela como en el visor en lugar de leerse como su pequeña vista previa incrustada; ``resize`` y ``strip`` lo escriben como PNG. Un archivo ilegible se informa y el resto se procesa igualmente. Un archivo incompleto se lee hasta donde llega, como en el visor. Los grises de 16 bits y de coma flotante se escalan a 8 bits como en el visor; ``resize`` y ``strip`` conservan la profundidad de bits del original.

Los subcomandos que reciben archivos o carpetas (todos salvo ``collage``, ``anaglyph`` y ``list-ops``) comparten ``--out`` (directorio de salida), ``--recursive``, ``--dry-run`` (listar acciones sin escribir nada), ``--overwrite`` y ``-j`` / ``--jobs`` (workers en paralelo; ``0`` usa todos los núcleos). ``collage`` y ``anaglyph`` escriben el único archivo que indica ``--out``. ``--version`` muestra la versión de la CLI.

----

Servidor MCP
------------

Imervue incluye un servidor `Model Context Protocol <https://modelcontextprotocol.io>`_
integrado que permite a los asistentes de IA (Claude Code, Claude Desktop, Cursor, Cline, …)
llamar a los ayudantes de lógica pura del proyecto sin una GUI en ejecución. Inícielo con::

   python -m Imervue.mcp_server

El servidor es independiente de Qt y sólo carga lo que cada herramienta necesita en el momento
de la llamada.

Herramientas disponibles
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Herramienta
     - Propósito
   * - ``list_images``
     - Lista los archivos de imagen de una carpeta (ruta, tamaño, mtime). Pase
       ``recursive=true`` para recorrer subcarpetas.
   * - ``read_image_metadata``
     - Dimensiones, formato, etiquetas EXIF y campos XMP (sidecar o, si no, incrustados) para una
       imagen. Los datos que falten se reportan como el valor vacío apropiado en lugar
       de lanzar una excepción.
   * - ``read_xmp_tags``
     - Ruta rápida que sólo lee el XMP (sidecar o, si no, incrustado) — valoración, etiqueta de color,
       palabras clave, título, descripción.
   * - ``convert_format``
     - Convierte una imagen a otro formato. El formato de destino se infiere del sufijo
       de destino (``png`` / ``jpg`` / ``jpeg`` / ``webp`` / ``tiff`` / ``bmp`` / ``avif``, y
       ``heic`` / ``jxl`` cuando su backend opcional está instalado). El parámetro
       opcional ``quality`` (1–100) se aplica a JPEG / WebP / AVIF / HEIC / JXL.
   * - ``puppet_from_png``
     - Construye un rig ``.puppet`` desde un PNG usando el auto-mesh del plugin puppet.
       Siembra el catálogo de parámetros estándar de Cubism para que el rig sea
       inmediatamente controlable.
   * - ``puppet_inspect``
     - Abre un archivo ``.puppet`` y devuelve un inventario estructurado: drawables,
       deformers, parameters, motions, expressions, hit areas, parts, mezclas de parámetros
       y rigs físicos.
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - Media/mín/máx/desv/mediana por canal, métricas de calidad sin referencia
       (colorido, entropía, contraste, densidad de bordes, ruido) y el histograma de
       256 contenedores con fracciones de recorte por exceso/defecto.
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Puntuación de desenfoque por varianza Laplaciana, texto OCR de Tesseract (degrada
       con gracia cuando no está) y una vista previa PNG en base64 acotada.
   * - ``find_similar``
     - Agrupa imágenes casi-duplicadas por hash perceptual (umbral de Hamming). Reporta
       el progreso por archivo cuando se proporciona un token de progreso.
   * - ``apply_watermark`` / ``apply_frame``
     - Estampa una marca de agua de texto, o envuelve la imagen en un marco mate /
       Polaroid con una leyenda opcional.
   * - ``build_collage``
     - Compone varias imágenes en un montaje en cuadrícula (columnas, tamaño de celda,
       separación, margen y fondo configurables). Reporta el progreso.
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - Recorte por caja de píxeles, redimensión (con un lado se conserva la relación de
       aspecto, con ambos se obtiene un tamaño exacto) y rotación
       sin pérdida de 90/180/270 o volteo horizontal/vertical.
       Los tamaños y las coordenadas se refieren a la imagen enderezada según EXIF.
   * - ``collection_stats``
     - Resume las calificaciones, favoritos, etiquetas de color y estados de culling de
       una carpeta (conteos, distribución de 0–5 estrellas y promedio).
   * - ``reverse_geocode`` / ``extract_video_frame``
     - Resuelve coordenadas GPS a la ciudad más cercana sin conexión, y decodifica un
       fotograma de un vídeo a una imagen fija.
   * - ``extract_gps`` / ``dominant_colors``
     - Lee la latitud/longitud GPS del EXIF (se encadena con ``reverse_geocode``);
       extrae una paleta de colores por corte de mediana (rgb / hex / número de píxeles).
   * - ``error_level_analysis``
     - Mapa de manipulación por Error-Level-Analysis mediante recompresión JPEG, como URI
       de datos PNG (las regiones editadas destacan sobre el fondo).
   * - ``search_images``
     - Filtra una carpeta con el DSL de consultas de los álbumes inteligentes (extensión /
       nombre / tamaño / dimensiones / relación de aspecto / cámara EXIF / objetivo / lugar).
   * - ``solarize_image`` / ``glow_image``
     - Aplica una inversión tonal de solarizado o un resplandor difuso / bloom Orton y
       guarda el resultado.
   * - ``velvia_image`` / ``emboss_image`` / ``defringe_image``
     - Refuerzo de saturación Velvia ponderado por luminancia, efecto de relieve con luz
       direccional y desaturación de franjas moradas/verdes en los bordes.
   * - ``film_negative_image`` / ``graduated_density_image``
     - Invierte un negativo en color escaneado (base de película automática) y aplica un
       degradado lineal de densidad neutra graduada.
   * - ``filmic_tonemap_image`` / ``tone_equalizer_image`` / ``detail_equalizer_image``
     - Caída suave de altas luces fílmica Reinhard/Hable, exposición por zona de luminancia
       y contraste por banda de frecuencia.
   * - ``colormap_image`` / ``false_color_image``
     - Recolorea la luminancia con un mapa perceptual viridis/magma/jet, o la asigna a una
       escala de exposición en falso color.
   * - ``dither_image`` / ``split_toning_image`` / ``pixel_sort_image``
     - Tramado ordenado (Bayer) a pocos tonos por canal, virado partido de sombras/altas
       luces y ordenación de píxeles por bandas de brillo.
   * - ``polar_image`` / ``kaleidoscope_image``
     - Transforma entre coordenadas rectangulares y polares (tiny planet), o refleja el
       encuadre en varias cuñas de caleidoscopio.
   * - ``frosted_glass_image`` / ``clahe_image`` / ``local_contrast_image``
     - Dispersión de vidrio esmerilado con vecinos aleatorios, ecualización adaptativa del
       histograma con contraste limitado, y claridad de medios tonos + textura de detalle fino.
   * - ``posterize_image`` / ``gradient_map_image``
     - Cuantiza cada canal a unas pocas bandas planas, o reasigna la luminancia mediante un
       degradado de negro a blanco mezclado según la intensidad.
   * - ``film_grain_image`` / ``dehaze_image`` / ``distort_image``
     - Grano de película gaussiano ajustable, eliminación de neblina por dark channel prior,
       y distorsión geométrica de remolino / pellizco / ondulación.
   * - ``levels_image`` / ``curve_image``
     - Niveles de punto negro/blanco y gamma, y un preajuste de curva tonal maestra
       (curva en S, levantar sombras, comprimir altas luces).
   * - ``auto_color_balance_image`` / ``channel_mixer_image``
     - Balance de blancos automático (gray-world, white-patch, estiramiento por percentil,
       retinex) y un mezclador de canales 3x3 con conversión a monocromo.
   * - ``lens_correction_image``
     - Corrige la distorsión de barril/cojín (k1), aclara u oscurece el viñeteado de las
       esquinas y anula la aberración cromática roja/azul.

Cada herramienta anuncia un ``outputSchema`` JSON y ``annotations`` de solo lectura /
destructivas, y devuelve su resultado como ``structuredContent`` junto al sobre de texto
(según MCP 2025-11-25), de modo que los clientes consumen payloads tipados sin volver a
parsearlos. Las herramientas de larga duración transmiten ``notifications/progress`` cuando
quien las invoca pasa un token de progreso.

Prompts
^^^^^^^

El servidor expone cuatro prompts vía ``prompts/list`` / ``prompts/get``:
``caption_image``, ``suggest_edits``, ``analyze_composition`` (una crítica de composición
guiada por saliencia) y ``flag_issues`` (un triaje de nitidez + calidad + recorte).
``completion/complete`` sugiere valores para el ``style`` de ``suggest_edits`` y el ``focus`` de
``analyze_composition``.

Claude Code (a nivel de proyecto)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

El repositorio incluye un ``.mcp.json`` a nivel de proyecto en la raíz del repo:

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

Abrir cualquier subdirectorio del repositorio en Claude Code auto-descubre este servidor.
Claude Code pregunta antes de activar los servidores de proyecto la primera vez — acepte
el aviso para usarlo.

Claude Desktop
^^^^^^^^^^^^^^

Añada la misma entrada a su configuración de Claude Desktop:

* macOS: ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\Claude\claude_desktop_config.json``

Use un directorio de trabajo absoluto o active un virtualenv en el que Imervue esté
instalado; la invocación ``python`` debe resolverse a un intérprete que pueda
``import Imervue``.

Superficie del protocolo
^^^^^^^^^^^^^^^^^^^^^^^^

El servidor implementa el transporte stdio JSON-RPC 2.0 de MCP versión ``2025-03-26``:

* ``initialize`` — handshake; anuncia ``capabilities.tools``.
* ``tools/list`` — enumera las herramientas registradas con sus definiciones de entrada
  JSON-Schema.
* ``tools/call`` — invoca una herramienta con ``{"name", "arguments"}``;
  los resultados vuelven dentro del array ``content``.
* ``notifications/*`` — aceptadas silenciosamente (sin respuesta).

La implementación vive en ``Imervue/mcp_server/``:

* ``server.py`` — bucle de protocolo + registro de herramientas.
* ``tools.py`` — funciones manejadoras y las definiciones de herramientas por defecto.
* ``__main__.py`` — punto de entrada ``python -m Imervue.mcp_server``.

Se pueden registrar herramientas personalizadas construyendo :class:`MCPServer`
manualmente, llamando a :meth:`MCPServer.register`, y alimentando mensajes a través de
:meth:`MCPServer.handle_message` (o conduciendo el bucle stdio con el ayudante :func:`run`
integrado).
