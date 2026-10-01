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
       de imágenes. Consulte *Abrir imágenes*, *Explorar imágenes* y *Organizar imágenes*.
   * - **Modify**
     - Pipeline de revelado no destructivo — controles deslizantes, curvas, LUTs,
       máscaras, retoque, multi-imagen. Consulte *Editar imágenes (Pestaña Modify)*.
   * - **Paint**
     - Estudio completo de pintura raster con pinceles, capas, animación,
       herramientas de manga e I/O de PSD. Consulte *Espacio de trabajo Paint (Pestaña Paint)*.
   * - **Puppet**
     - Animador de marionetas 2D con rig construido desde cero — mallas, deformadores,
       parámetros, movimientos, físicas. Consulte *Espacio de trabajo Puppet (Pestaña Puppet)*.
   * - **Desktop Pet**
     - Superposición sin marco, transparente y siempre encima que ejecuta los mismos
       rigs ``.puppet`` en su escritorio con drivers en vivo (reposo / parpadeo /
       micrófono / cámara web / seguimiento del cursor). Consulte *Espacio de trabajo
       Desktop Pet (Pestaña Desktop Pet)*.

Las secciones *Primeros pasos*, *Referencia de atajos de teclado*, *Referencia del menú Extra
Tools*, *Sistema de plugins*, *Uso desde la línea de comandos* y *Servidor MCP* son
transversales y se aplican a las cinco pestañas.

**Puppet** y **Desktop Pet** son opcionales: desactiva cualquiera de los dos en ``File`` > ``Preferences`` > **Optional tabs** y, desde el siguiente inicio, su pestaña no se añade y su código no se carga, así que Imervue arranca más rápido y usa menos memoria. Ambos vienen activados; cada uno se construye la primera vez que abres su pestaña, y la de Desktop Pet al iniciar cuando su mascota está configurada para mostrarse al arrancar.

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
- **Derecha**: Barra lateral EXIF, plegada en una franja estrecha al iniciar: haga clic en ella para abrirla. Muestra la información de captura de la imagen abierta.

Imervue escribe un registro de cada sesión en ``imervue.log`` junto al programa (en ``%LOCALAPPDATA%\Imervue``, o en ``~/.cache/imervue`` fuera de Windows, cuando esa carpeta es de solo lectura). El registro de la sesión anterior se conserva como ``imervue.previous.log``, así que tras una caída el registro que la explica sigue ahí cuando Imervue vuelve a ejecutarse — adjunte ambos al informar de un problema.

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
     - ``File`` > ``Open File``, después elija un archivo
   * - Arrastrar y soltar
     - Arrastre una imagen o carpeta directamente a la ventana
   * - Abrir desde el Explorador
     - Clic derecho en una imagen > ``Open with Imervue`` (requiere asociación de archivos)
   * - Archivos recientes
     - ``File`` > ``Recent`` > Recent Folders / Recent Images, para volver a abrir una carpeta o una imagen

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
ordenable con estas columnas: Vista previa · Etiqueta · Valoración · Nombre · Resolución · Tamaño · Tipo
· Modificado. Haga doble clic en una fila (o pulse ``Enter``) para entrar en Deep Zoom; pulse
``Esc`` para volver a la lista. Las miniaturas y los metadatos se cargan de forma diferida en
un hilo de trabajo, de modo que las carpetas muy grandes mantienen la capacidad de respuesta.

``Delete`` quita las filas seleccionadas y ``Ctrl + Z`` las recupera, y las teclas de valoración (``1`` – ``5``), favorito (``0``), selección (``P`` / ``Shift + X`` / ``U``) y color (``F1`` – ``F5``) las marcan, como en la cuadrícula; todas salvo ``F1`` – ``F5`` siguen la configuración de atajos.

Modo Deep Zoom
^^^^^^^^^^^^^^

Haga clic en una miniatura para entrar en el modo Deep Zoom y ver imágenes individuales en
alta calidad.

También se abren panoramas muy por encima del límite de seguridad de 179 megapíxeles de Pillow: el límite depende de la memoria del equipo (con 16 GB, unos 1,4 gigapíxeles) y esas imágenes gigantes se decodifican de una en una.

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
     - ``Shift + P`` — desde un zoom de 400 % muestra RGB / HEX bajo el cursor, más una cuadrícula de píxeles cuando no hay más de 40.000 píxeles de la imagen en pantalla
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

Indicadores de color, almacenados por separado de la
valoración de 1 -- 5 estrellas. Útiles para una categorización rápida (p. ej. rojo = candidatos
a descartar, verde = seleccionados, azul = pendientes de retoque).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Tecla
   * - Rojo / Amarillo / Verde / Azul / Púrpura
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (pulse la misma tecla de nuevo para borrar; en
       una selección solo borra cuando todas las imágenes seleccionadas ya tienen ese color)
   * - Aplicar a la selección en lote
     - Seleccione varias miniaturas y pulse la tecla F correspondiente
   * - Filtrar por color
     - ``Filter`` > ``By Color Label`` > elija un color / cualquier etiqueta / sin etiqueta

La barra de estado muestra un chip de color para la imagen actual. Las miniaturas muestran
una franja de color en el borde izquierdo. La **vista de lista** tiene columnas dedicadas
**Label** y **Rating** que se pueden ordenar — haga clic en cualquier celda de la columna
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
     - En Deep Zoom, clic derecho > ``Tags``; para las miniaturas seleccionadas, clic derecho >
       ``Batch Operations`` > ``Add to Tag``
   * - Añadir a un álbum
     - En Deep Zoom, clic derecho > ``Albums``; para las miniaturas seleccionadas, clic derecho >
       ``Batch Operations`` > ``Add to Album``
   * - Filtrar por una sola etiqueta / álbum
     - ``Filter`` > ``By Tag`` / ``By Album``
   * - Filtro multi-etiqueta (AND / OR)
     - ``Filter`` > ``Multi-Tag Filter…`` — marque varias etiquetas o álbumes, elija Any (OR) o All (AND)
   * - Limpiar
     - **Clean Up…** en el gestor olvida las entradas de los archivos que ya no existen y fusiona los
       nombres que solo difieren en mayúsculas y minúsculas (el que tiene más imágenes conserva su
       grafía), después de que confirme los recuentos. Se rechaza crear o renombrar una etiqueta o un
       álbum con un nombre que solo difiere de otro en mayúsculas y minúsculas o en espacios, al igual
       que un nombre con una tabulación o un salto de línea

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
     - ``Filter`` > ``By Extension`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
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
que los píxeles borrados dejan de filtrarse en un repintado. Bajo las ranuras de
color hay un anillo de tono alrededor de un triángulo de saturación / brillo:
arrastrar sobre el anillo elige el tono y dentro del triángulo, la saturación y el
brillo; los controles deslizantes HSB / RGB y el campo hexadecimal se actualizan a
la par, y un color fijado en otro lugar mueve los marcadores de la rueda. El
**dock Swatches** muestra sus colores recientes, o una paleta elegida en la lista
desplegable de encima: las integradas Standard, Pastel y Manga, o una propia.
**Save as Palette…** guarda los colores recientes con un nombre, **Delete Palette**
elimina una de las suyas (las integradas se conservan) y ``Filter`` >
``Match Swatches…`` vuelve a pintar con los colores que muestre el dock.

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
título de cualquier dock para reorganizarlo o flotar un panel; ``Settings`` >
``Workspace Layouts…`` recuerda qué docks se muestran (véase *Diseños de espacio de trabajo*).

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
     - Relleno por inundación con tolerancia / contiguo / muestrear todas las capas.
       En el dock Bucket, **Auto-fill closed regions** rellena cada región
       cerrada del dibujo lineal (la capa de referencia o, si no hay, la
       activa) con el color de primer plano; **Base colours on a new layer**
       da a cada región su propio color plano — los colores del dock Swatches
       cuando muestra alguno — en una capa nueva bajo el dibujo lineal, y
       deja vacíos las líneas y el espacio alrededor del dibujo. Las líneas
       oscuras sobre papel blanco funcionan tan bien como las líneas sobre
       transparencia
   * - Cuentagotas
     - ``I``
     - Toma el color de primer plano del lienzo
   * - Mover
     - ``V``
     - Traslada la capa o selección activa
   * - Rect / Lazo / Varita / Selección rápida
     - ``M`` / ``L`` / ``W``
     - Herramientas de selección con modos Replace / Add / Subtract / Intersect;
       en el Lazo, **Magnetic** en la barra Options ajusta el contorno al borde
       más fuerte de la capa a menos de 10 px al soltar
   * - Texto
     - ``T``
     - El clic abre el diálogo **Add Text** (fuente / tamaño / color / negrita /
       cursiva); el texto se dibuja en los píxeles de la capa
   * - Degradado
     - ``U``
     - Relleno con degradado lineal / radial / angular / diamante, del color de
       primer plano al de fondo o a lo largo de un degradado guardado de varias
       paradas elegido en **Colours** en la barra Options; **Edit…** a su lado
       crea, cambia y elimina esos degradados (nombre, paradas de color con
       posición y opacidad), que se conservan entre sesiones
   * - Desenfoque / Difuminar
     - ``R`` (Difuminar)
     - Manipulación local de píxeles
   * - Dodge / Burn / Sponge
     -
     - Tonificación de cuarto oscuro ponderada por el pincel — Dodge aclara y Burn
       oscurece los medios tonos, Sponge desatura; sin opciones
   * - Pluma (Bezier)
     - ``P``
     - Ruta vectorial con edición de anclas / manejadores; **Smooth** en la
       barra Options traza una sola curva suave que pasa por cada punto
       pulsado en lugar de líneas rectas
   * - Sello de clonar
     - ``S``
     - Alt+clic establece la fuente; después arrastre para estampar con el tamaño /
       la dureza / la opacidad del pincel
   * - Bocadillo
     - ``Ctrl + B``
     - Arrastre un recuadro para dibujar un bocadillo de cómic / manga (se dibuja sin cola)
   * - Rectángulo / Elipse / Línea / Polígono
     - ``Shift + R/E/I/P``
     - Primitivas de forma vectorial con trazo + relleno
   * - Recortar
     - ``C``
     - Recorte libre — arrastre un rectángulo; el lienzo se recorta al soltar
   * - Transformar
     - ``Ctrl + T``
     - Ocho manejadores de escala y un manejador de rotación
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
   * - Lápiz
     - Línea fina de grafito ligeramente texturizada
   * - Pluma
     - Línea con suavizado nítido, el pincel del día a día
   * - Marcador
     - Trazos anchos y semitransparentes que se acumulan
   * - Aerógrafo
     - Puntos dispersos que se acumulan en una pulverización suave
   * - Acuarela
     - Borde húmedo con un interior más claro, como pigmento acumulado en el contorno
   * - Sumi
     - Tinta de estilo caligráfico con bordes de pincel seco

Cera, Resaltador y Caligrafía sumi son presets de pincel basados en estos tipos. Cada
pincel expone Size / Opacity / Hardness / Density / Blend-mode en el **dock Brush**; la
**barra Options** superior lleva Size / Opacity / Hardness. La presión del lápiz de la
tableta escala el tamaño y la opacidad del pincel según la curva definida en
``Settings`` > ``Pressure Curve…`` (arrastre un punto, haga clic para añadir uno, haga
clic derecho para quitar uno, o parta de Linear / Soft / Hard); un ratón dibuja a plena
presión. En el dock Brush, **Scatter** aparta cada toque del trazo hasta la fracción
indicada del tamaño del pincel, **Colour jitter** altera el tono, la saturación y el
brillo de cada toque, y **Follow pen tilt** estrecha la punta en sentido transversal a
la dirección en que se inclina el lápiz de la tableta y la gira para seguirla (el preset
Caligrafía sumi lo tiene activado); un pincel de pixel art conserva su punta cuadrada.
Use ``Edit`` >
``Capture Brush Tip…`` para convertir una selección de marquesina en una punta de pincel
personalizada.
El **dock Materials** muestra sus propios materiales antes de las tramas y texturas
integradas: las imágenes de la carpeta ``materials`` dentro de la carpeta del programa
de Imervue (una carpeta de primer nivel llamada ``texture``, ``tone``, ``pattern``,
``brush_tip`` o ``pose`` las clasifica en esa categoría) y las puntas de pincel que haya
capturado. ``Edit`` > ``Save Selection as Material…`` guarda allí la parte seleccionada
de la imagen visible con el nombre y la categoría que elija (los píxeles fuera de la
selección se vuelven transparentes, y un material anterior con el mismo nombre se
conserva); el nuevo material aparece en el dock de inmediato.

Capas
^^^^^

El **dock Layer** ofrece miniaturas, alternancia de visibilidad, renombrado en línea,
reordenación con los botones ↑ / ↓ (o ``Ctrl + ]`` / ``Ctrl + [``), y el modo de fusión y
opacidad de la capa activa. El menú ``Layer`` añade:

- **New / Vector / Duplicate / Merge Down** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Máscaras** — Add Mask / From Selection / Invert / Apply / Delete
  (``Ctrl + Shift + M`` añade; ``Ctrl + Alt + Shift + M`` añade desde selección)
- **Máscara de recorte** — activa o desactiva el recorte en la capa activa, recortándola
  al alfa de la capa inferior (``Ctrl + Alt + G``)
- **Efectos de capa** — Drop Shadow · Outer Glow · Stroke; limpiar efectos
- **Capa de referencia** — fija una capa como la fuente con cuyos colores compara el cubo
  de **Relleno**
- **Capa de 1 bit** — alterna la capa activa a una capa de line-art binaria
- **Dividir capa por color** — divide una capa de color plano en una capa por color para
  facilitar el rellenado con el cubo
- **Mapa de degradado** — submenú de presets (sepia / atardecer / cianotipia …)

Selecciones
^^^^^^^^^^^

Use las herramientas rect / lazo / varita / selección rápida, después el menú **Edit** >
**Stroke Selection…** para delinear la marquesina con el color de primer plano, usando el
ancho (Width) y la posición (Placement) del diálogo. ``Q`` alterna el
**Modo de máscara rápida** — pinte con cualquier pincel para refinar el borde de la
selección en rojo, después pulse ``Q`` de nuevo para convertirla de vuelta en una marquesina.

Animación
^^^^^^^^^

El **dock Animation** convierte el documento en una tira de fotogramas:

- ``+ Frame`` captura la imagen aplanada en un nuevo fotograma.
- Haga clic en la miniatura de un fotograma para cargarlo en la capa activa.
- ``Onion Skin`` (menú View) superpone el fotograma anterior con baja opacidad.
- ``▶ Play`` recorre los fotogramas a los FPS elegidos.
- ``Export…`` guarda los fotogramas como GIF animado, WebP o PNG — el tipo de archivo
  que elija determina el formato y un nombre sin extensión se convierte en GIF — y
  cada fotograma dura un tick de los FPS elegidos. WebP se escribe sin pérdida; GIF
  reduce cada fotograma a 255 colores y vuelve transparentes los píxeles apenas visibles.

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
   * - Texto a lo largo de la selección…
     - Coloca texto a lo largo del contorno de la selección, en una capa nueva — el texto, la fuente, el tamaño, el color, la negrita y la cursiva vienen del diálogo **Add Text**

Filtros
^^^^^^^

Los filtros con un solo deslizador — Posterizar, Umbral, Convertir a semitonos e
Igualar color — muestran una vista previa en vivo mientras arrastra, sobre los
480 × 480 píxeles centrales de la capa a tamaño completo; OK aplica el valor a toda
la capa. Los demás abren un diálogo de parámetros simple OK / Cancel:

- **Niveles** — deslizadores de punto negro / punto blanco / gamma
- **Curvas** — un preset (curva en S, levantar sombras, comprimir luces) con un deslizador de intensidad
- **Posterizar** — cuantiza el color en N pasos
- **Umbral** — convierte a blanco / negro puros en un punto de corte
- **Auto Color Balance** — neutraliza dominantes mediante grey-world / white-patch
- **Grano de película** — ruido de luminancia con tamaño y cantidad ajustables
- **Convertir a semitonos** — pantalla de puntos al estilo periódico
- **Igualar color** — pide una imagen de referencia y luego da a la capa el ambiente
  de color de esa imagen (cada canal adopta la media y la dispersión de la referencia);
  **Intensidad** mezcla desde sin cambios hasta la igualación completa
- **Igualar muestras** — vuelve a pintar cada píxel con el color más cercano del dock
  Swatches (elige o importa colores primero)

Ayudas de visualización
^^^^^^^^^^^^^^^^^^^^^^^

- **Cuadrícula de píxeles** (``Ctrl + Shift + '``) — superpone una cuadrícula de un píxel con alto zoom
- **Ajustar a píxel / bordes** — Ajustar a píxel coloca los toques del pincel en píxeles enteros; Ajustar a bordes atrae los puntos a los bordes cercanos del lienzo o de la capa
- **Onion Skin** — superpone el fotograma de animación anterior
- **Guías de sangrado** — guías de sangrado y zona segura para impresión
- **Rotar lienzo** (``Ctrl + Shift + H``) — rotación de vista sin rasterizar

Entrada/Salida de archivos
^^^^^^^^^^^^^^^^^^^^^^^^^^

- **New Canvas…** — una pestaña nueva del tamaño que elija: un preset de papel, manga o pantalla (A4, página de manga B5, 1080p, 4K …), uno que haya guardado con **Save as Preset…**, o cualquier ancho y alto de hasta 16384 px, sobre fondo blanco o transparente (**New Tab**, ``Ctrl + N``, mantiene el predeterminado blanco de 1024 × 1024)
- **Open PSD…** (``Ctrl + O``) aplana el archivo en una sola capa en una pestaña nueva;
  **Save as PSD…** (``Ctrl + S``) escribe las capas con sus modos de fusión (sin máscaras
  ni efectos de capa)
- **Export image…** — aplana y guarda como PNG, JPEG, WebP, TIFF o BMP, según el tipo de archivo elegido (JPEG y BMP, que no admiten transparencia, sobre fondo blanco). Solo **Save as PSD…** marca la pestaña como guardada; tras una exportación, al cerrar Imervue se sigue preguntando por los cambios sin guardar de la pestaña
- **Export pages → CBZ** / **→ PDF** — exporta las páginas de un proyecto de cómic; **Save Comic Project…** guarda el cómic entero, cada página con sus capas, en un solo archivo ``.imervue-proj``, y **Open Comic Project…** lo recupera
- **Import brush preset…**, **Import palette…** — trae pinceles y paletas de otras instalaciones o aplicaciones
- **Autoguardado** — cada 2 minutos, mientras la pestaña activa tenga ediciones sin guardar, se escribe una instantánea; en el siguiente inicio un toast ofrece las instantáneas y **File > Restore Autosave** carga la más reciente en la pestaña activa. La barra de estado muestra cuándo se tomó la última instantánea, y al cerrar Imervue se pregunta por las pestañas Paint con cambios sin guardar.

Diseños de espacio de trabajo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Settings`` > ``Workspace Layouts…`` enumera los diseños integrados **Default**,
**Drawing**, **Comic** y **Compact** además de los suyos. **Save current…** guarda bajo un
nombre cuáles de los docks Layers / Color / Brush / Navigator / History / Reference se
muestran; aplicar un diseño muestra u oculta esos docks y trae al frente el primero que se
muestra. No se guardan las opciones de herramienta ni los tamaños de los docks.

----

Espacio de trabajo Puppet (Pestaña Puppet)
------------------------------------------

La cuarta pestaña de nivel superior — **Puppet** — es un sistema de animación 2D con rig de
marionetas construido desde cero: rigs con deformación de malla, parámetros, movimientos,
físicas, expresiones, grupos de poses, lip-sync y seguimiento por webcam,
**sin SDK propietario**, **sin** ``live2d-py``, y con un formato de archivo
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

Los paneles de la derecha comparten un área con pestañas: **Parameters** (un control deslizante por parámetro), **Expressions** (activar o desactivar cada expresión), **Pose** (elegir qué miembro de cada grupo de pose se muestra; un grupo muestra su primer miembro hasta que se elige otro) y **Bones** (la jerarquía de deformadores).

Flujo de trabajo de principio a fin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Importar un PNG** — ``File`` > ``Import PNG…`` ejecuta
   ``puppet.auto_mesh.puppet_from_png``: cuadrícula triangulada limitada por alfa, un
   drawable, lista para renderizar.
2. **Añadir un deformador** — ``Edit`` > ``Add Rotation Deformer`` (ancla + ángulo) o
   ``Add Warp Deformer`` (rejilla bilineal de filas × columnas; los vértices fuera de los
   límites pasan sin cambios).
3. **Añadir un parámetro** — ``Edit`` > ``Add Parameter`` añade un deslizador al dock derecho
   **Parameters** con id autonombrado (``Param1``, ``Param2``, …).
4. **Establecer claves** — arrastre el deslizador a un extremo, edite la forma del deformador
   en código, pulse **Set key**. Repita en neutro y en el extremo
   opuesto. El runtime ahora interpola linealmente los campos del deformador entre claves
   adyacentes cada vez que se mueve el deslizador. **Set key** solo guarda formas de
   deformador: **Edit mesh** mueve los vértices de reposo del drawable de forma definitiva,
   así que una edición de malla no se guarda como clave.
5. **Guardar** — ``Save As…`` escribe el rig + texturas + movimientos + expresiones + físicas
   en un único zip ``.puppet`` que puede compartir o abrir más tarde mediante
   ``Open Puppet…``.

Pruebe un ejemplo completo
^^^^^^^^^^^^^^^^^^^^^^^^^^

El repositorio incluye una demo totalmente riggeada en
``examples/puppet/imeru.puppet`` — **Imeru**, la mascota original de
Imervue. Está dibujada y riggeada enteramente por
``examples/puppet/imeru/build.py`` (``py -3`` reconstruye el archivo), de modo que
la demo no conlleva derechos de terceros: 40 drawables sobre un lienzo de 1024 × 1336,
giros de cabeza hechos con morfos de vértices de paralaje al estilo Live2D, iris
recortados al blanco de los ojos, brazos de dos articulaciones construidos con
deformadores de rotación y tres cadenas de física que balancean el pelo.

El rig lleva todos los parámetros estándar de Cubism (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …) más
``ParamArmLA/LB/RA/RB`` para los brazos, por lo que todos los drivers de entrada
estándar (webcam, parpadeo, lip-sync, mirada al cursor) lo controlan sin configuración
por rig. El archivo incluye ocho movimientos: dos movimientos idle en bucle en el grupo
``Idle``, ``tap_head`` en ``TapHead`` y ``shy`` en ``TapBody`` (hacer clic en su
cabeza o su cuerpo los reproduce), y ``greet``, ``wave``, ``surprised`` y ``sleepy``
en ``Gesture``; los acompañan siete expresiones (smile, happy, surprised, sad, angry,
blush, sleepy).

Abra la pestaña Puppet, haga clic en **Open Puppet…**, apunte a
``imeru.puppet`` — la figura aparece centrada. Arrastre cualquier deslizador de
parámetro para controlar una articulación, o haga clic en uno de los movimientos del dock
Motions — un solo clic enlaza el movimiento e inicia la reproducción inmediatamente.

**Ejecutar el ejemplo incluido, paso a paso:**

1. Inicie Imervue. Desde el código fuente: ``python -m Imervue``. Desde la versión
   empaquetada: ejecute el ejecutable / bundle de aplicación ``Imervue``. El directorio
   ``examples/`` se empaqueta en las compilaciones de Nuitka y PyInstaller; una instalación
   con pip / wheel no lo incluye (desde una copia del código fuente los rigs están en
   ``examples/puppet/``).
2. Haga clic en la pestaña **Puppet** en la parte superior de la ventana.
3. **File > Examples > Imeru** (o el desplegable
   **Examples ▾** de la barra de herramientas). El rig se carga centrado
   y el dock de parámetros se llena con sus deslizadores.
4. En el dock **Motions** inferior, haga un solo clic en cualquier entrada de movimiento
   (``idle_look``, ``wave``, ``tap_head`` …). La reproducción empieza
   inmediatamente; un nuevo clic la reinicia, el botón **Stop** del dock detiene la
   reproducción, y elegir un movimiento distinto hace un cross-fade hacia él.
5. Active los interruptores de entrada en vivo en la barra de herramientas para controlar
   el rig desde sus propias entradas — **Drag-track head** para girar la cabeza y los ojos
   hacia el cursor mientras se mueve sobre el lienzo,
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

La especificación completa (drawables, deformers, parameters, motions, expressions, pose, physics)
vive en ``Imervue/puppet/FORMAT.md`` en el repositorio. Sólo JSON + PNG — sin binario
propietario, totalmente diffable a través de git.

El formato es abierto y verificable por máquina:

- Un ``.puppet`` guardado empieza con una entrada ``mimetype`` sin comprimir que contiene
  ``application/vnd.imervue.puppet+zip``, de modo que un programa puede reconocerlo por sus
  primeros bytes, y cada archivo JSON indica su JSON Schema en ``$schema``.
- Cuatro JSON Schemas (draft 2020-12) — ``puppet``, ``motion``, ``expression`` y
  ``physics`` — se publican en ``docs/schemas/``; los editores que siguen ``$schema``
  comprueban un archivo mientras se escribe.
- ``py -m Imervue.cli puppet-validate character.puppet`` (MCP ``puppet_validate``) comprueba
  un archivo frente a los esquemas, las reglas del cargador y las comprobaciones del rig;
  ``puppet-schema`` (MCP ``puppet_schema``) imprime un esquema.
- ``docs/examples/read_puppet.py`` lee un ``.puppet`` sólo con la biblioteca estándar de
  Python, como referencia para otros programas; la especificación y los esquemas tienen
  licencia MIT, así que cualquier programa puede leer o escribir el formato.
- Un archivo de una versión de formato más reciente se rechaza indicando la versión que usa,
  de modo que un Imervue más antiguo pide actualizar en lugar de leerlo mal.

Referencia de la barra de herramientas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

La barra de herramientas lleva **Examples ▾**, los seis conmutadores en vivo, **Edit mesh**,
**Record…** y **Reset to rest**. Todas las demás entradas de abajo son elementos de los
menús **File**, **Edit**, **Live**, **Output** o **Tools**; esos menús también contienen
las entradas de la barra de herramientas.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Acción
     - Propósito
   * - Open Puppet… / Examples ▾
     - Cargar un ``.puppet`` desde disco (menú **File**), o elegir uno de los rigs
       incluidos en ``examples/puppet/`` desde **Examples ▾** (el botón de la barra de
       herramientas, también en **File**)
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
     - Crear el rig desde el menú **Edit**
   * - Drag-track head
     - La cabeza y los ojos se giran hacia el cursor mientras se mueve sobre el
       lienzo: offset del cursor → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Ciclo coseno cerrar→abrir en ``ParamEyeLOpen`` / ``ParamEyeROpen``
       cada ~4.5 s (la ruta de escritura forzada salta el omisor sin-cambio del lienzo
       para que los drivers en competencia no puedan detener el parpadeo)
   * - Mic lip-sync
     - RMS del micrófono → ``ParamMouthOpenY`` (requiere ``sounddevice``)
   * - Lip-sync from Audio File…
     - Menú **Live**: convierte un WAV (PCM de 8, 16 o 32 bits) en un movimiento
       llamado ``lipsync_<file>`` que abre ``ParamMouthOpenY`` según el volumen,
       30 veces por segundo (se descartan las claves que no aportan nada), y
       reproduce el WAV como su sonido; reemplaza un movimiento con ese nombre y
       queda seleccionado en el dock **Motions**. No necesita ninguna dependencia
       opcional
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
     - Solo en el menú **Output**: captura los cambios de parámetros en un nuevo
       ``Motion`` y lo añade al documento — hornear-desde-toma, sin autoría manual
       de claves
   * - Capture frame… / Record… / Export all motions…
     - Guarda un único PNG, alterna una grabación GIF / WebM / MP4, o renderiza por lotes
       cada movimiento del rig a su propio archivo (todo mediante la misma ruta de render
       off-screen sólo-personaje usada para streaming).
       Un fotograma capturado conserva el tamaño propio del rig (lado largo de 4096 px
       como máximo) sobre fondo transparente; una grabación o exportación por lotes
       encaja el personaje en 1080 px sobre blanco, ya que los fotogramas GIF / WebM / MP4
       no llevan alfa
   * - Output > Virtual camera / NDI output
     - Superficies de streaming en vivo — consulte *Streaming en vivo a OBS* más abajo
   * - Reset to rest
     - Detiene en seco el reproductor de movimiento, desactiva cada driver en vivo,
       limpia expresiones / grupos de pose, restaura los valores por defecto de los parámetros
   * - Fit to Window
     - Menú **Tools**: re-centra y re-escala la marioneta en el lienzo
   * - Repair Rig
     - Menú **Tools**: en cada drawable, descarta los triángulos rotos y de
       área nula, fusiona los vértices duplicados que comparten posición y UV
       (una costura de textura sigue separada), elimina los vértices que ningún
       triángulo usa — los pesos de hueso y los vertex morphs siguen a los
       vértices que se conservan — y hace que los pesos de hueso de cada vértice
       sumen 1; la barra de estado indica qué ha cambiado

Grabar sus propios movimientos
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Para capturar una toma personalizada en lugar de crear fotogramas clave a mano:

1. Active **Output > Record motion** — aparece un diálogo de nombre.
2. Mientras graba, arrastre deslizadores, active **Webcam tracking**, deje correr la física
   — cualquier cosa que escriba valores de parámetros.
3. Desactive **Record motion** — el grabador hornea el flujo capturado a 30 Hz en un
   ``Motion`` con una pista de segmento lineal por parámetro que realmente se movió (los
   parámetros que se mantuvieron planos se descartan). El nuevo movimiento aparece en el
   dock **Motions** inferior inmediatamente, listo para reproducir / hacer bucle / guardar.

Los movimientos personalizados guardados de esta forma hacen ida y vuelta a través del mismo
payload JSON ``motions/<name>.json`` que los creados a mano.

**Edit > Edit motion…** abre la línea de tiempo del movimiento que tiene el
reproductor: arrastre una clave o un manejador bezier, remodele la pista elegida
según un easing con nombre con **Ease** y **Apply to Track** (31 curvas; elastic
y bounce se convierten en 16 claves lineales por segmento), o aligere una toma de
30 Hz con **Simplify Keys**, que descarta cada clave que queda dentro de la
tolerancia (un porcentaje del rango de cada parámetro) de la recta que pasa por
sus vecinas.

Streaming en vivo a OBS
^^^^^^^^^^^^^^^^^^^^^^^

Dos rutas de salida, ambas renderizando la marioneta sola (sin fondo de damero, sin chrome
del editor) en un framebuffer off-screen antes de entregarlo a la superficie de streaming.
El lado más largo de la salida está limitado a 1080 px para que los lienzos nativos de
Cubism (a menudo de 3000–8000 px de alto) no sean rechazados por los drivers de cámara virtual
DirectShow.

**A. Cámara virtual** — aparece como una webcam en la lista de fuentes *Video Capture
Device* de OBS. ``pip install pyvirtualcam`` más el driver de la plataforma:
OBS Studio 26+ incluye el driver *OBS Virtual Camera* en Windows / macOS (haga clic una vez
en *Start Virtual Camera* en OBS para registrarlo); Linux usa ``v4l2loopback-dkms`` +
``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
El conmutador del menú **Output > Virtual camera** abre el flujo.

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
El conmutador del menú **Output > NDI output** emite la fuente (nombre por defecto
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

La pestaña Puppet se degrada con elegancia cuando falta un paquete de Python — el conmutador
correspondiente sigue desactivado y se abre el instalador de dependencias, que ofrece
instalarlo; una vez instalado, el conmutador vuelve a activarse. Una pista de texto aparece
solo cuando el paquete está presente pero falla el dispositivo o el driver.
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
#. **Drivers en vivo** — siete drivers de entrada (tres activados por
   defecto) y sus dependencias opcionales.
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
2. Haga clic en **Load bundled Imeru** para usar el personaje
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
* **Load bundled Imeru** — abre el rig incluido en
  ``examples/puppet/imeru.puppet``. El resolutor consulta primero
  ``examples_dir()`` (junto al programa en las compilaciones
  empaquetadas con Nuitka / PyInstaller, la raíz del repositorio en una
  copia del código fuente) y, como alternativa, busca una ruta relativa
  a la carpeta de trabajo actual.
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
     - El tick de pintado a ~30 FPS, el tick de script a 1 Hz y el
       sondeo de pantalla completa (salvo que sea la pantalla completa
       lo que ocultó la mascota) se detienen en ``hideEvent`` y se
       reanudan en el siguiente ``showEvent``. Los temporizadores de
       los drivers en vivo (parpadeo, idle, motions de idle, mirada)
       siguen funcionando.
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
       liberación, junto con el monitor en que está. En el siguiente
       arranque la mascota vuelve a esa posición, ajustada al interior
       de ese monitor. Si el monitor ya no está (lo ha desconectado
       desde el último arranque), la mascota va a la primera pantalla
       con su posición guardada ajustada a ella. La esquina inferior
       derecha solo se usa cuando nunca se guardó una posición.

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
que mover la mascota no hace aparecer un bocadillo. Al pulsar se
reproduce un movimiento del grupo ``Drag`` del rig y al soltar tras un
arrastre se reproduce uno de su grupo ``Land``, cuando el rig tiene
esos grupos.

**Clic derecho en cualquier lugar del cuerpo**

Abre un menú contextual con la siguiente estructura:

* **Hide pet** — acción de nivel superior que cierra la superposición.
* Submenú **Live drivers** — siete conmutadores marcables (Auto idle,
  Idle motions, Auto-blink, Drag-track head, Mouse gaze, Mic
  lip-sync, Webcam tracking). El estado de marcado refleja el estado
  del driver en vivo, así que el menú muestra lo que está corriendo
  actualmente.
* Submenú **Play motion** — poblado a partir de la lista
  ``document.motions`` del rig activo. Seleccionar una entrada
  reproduce ese movimiento; no dice ninguna frase de
  ``motion_lines`` (esas responden solo a un clic en una zona de
  impacto).
* Submenú **Apply expression** — poblado a partir de
  ``document.expressions`` del rig. Cada entrada aparece marcada
  mientras su expresión está activa; seleccionar una añade la
  superposición de parámetros de la expresión y seleccionarla de
  nuevo la quita.
* Submenú **Pose** — un submenú por cada grupo de pose del rig
  (rotulado con el nombre visible del grupo o, si no tiene, con su id)
  que lista los miembros del grupo; el miembro visible aparece marcado
  y seleccionar otro lo muestra en su lugar. Desactivado cuando el rig
  no tiene grupos de pose.
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
restaura el rig con los mismos drivers en marcha. La superposición
en sí aparece al arrancar solo cuando **Show the pet when Imervue
starts** está marcado en el grupo Window de la pestaña.

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
       y lo reproduce — uno en cuanto se activa, luego cada pocos
       segundos. Se aparta mientras se reproduce un movimiento que no
       es de Idle.
     - ninguna
   * - **Auto-blink**
     - Cierra y reabre los ojos en una curva coseno suave cada
       ~4,5 s. El driver fuerza la escritura del parámetro para que
       otros drivers que toquen los valores de apertura de ojos no
       supriman el parpadeo.
     - ninguna
   * - **Drag-track head**
     - La cabeza + los ojos giran hacia el cursor mientras se mueve
       sobre la mascota. Mueve
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - ninguna
   * - **Mouse gaze**
     - Los ojos y la cabeza siguen el cursor por toda la pantalla,
       respecto al centro de la mascota (los ojos van por delante).
       Mueve los mismos cuatro parámetros.
     - ninguna
   * - **Mic lip-sync**
     - La amplitud RMS del micrófono mueve ``ParamMouthOpenY``. La
       boca se abre en proporción al volumen de su voz, así que el
       personaje parece hablar cuando usted habla.
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker lee su cámara web a ~30 FPS y mueve
       los parámetros de pose de cabeza + apertura de ojos + apertura
       de boca. No se abre ninguna ventana de vista previa para la
       mascota (la vista previa de la cámara pertenece a la pestaña
       Puppet).
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
pestaña. El script gobierna cinco cosas:

* **Saludos** — frases de clic por defecto cuando no coincide nada
  más específico.
* **Saludos según la hora** — saludos para la franja del reloj local
  (``morning`` 05–11 h, ``afternoon`` 12–17 h, ``evening``
  18–21 h, ``night`` 22–04 h), usados antes que los saludos simples;
  una franja sin frases recurre a ellos.
* **Respuestas por zona de impacto** — depósitos de frases por
  ``HitArea.id``.
* **Frases de movimiento** — depósitos de frases por nombre de
  movimiento, dichas cuando un clic en una zona de impacto reproduce
  ese movimiento (no cuando un movimiento se inicia desde el menú
  contextual).
* **Recordatorios programados** — frases dirigidas por temporizador
  que se disparan cada ``every_seconds`` de tiempo monotónico de
  reloj.

Esquema (versionado — los campos futuros son compatibles hacia
adelante):

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
  luego ``motion_lines[area.motion]``, luego
  ``time_of_day_greetings``, luego ``greetings`` y, como base, el
  conjunto de saludo por defecto incorporado.
* El seguimiento del tiempo usa ``time.monotonic``, así que suspender
  el portátil o saltar el reloj del sistema no puede disparar en
  ráfaga eventos en cola.

**Reset to default** descarta el script del usuario y vuelve al
conjunto de saludo incorporado; la ruta del script persistida se
borra para que el siguiente arranque no la recargue.

Un ejemplo funcional se encuentra en
``examples/desktop_pet/imeru.petscript.json`` — seis saludos, una
frase para cada momento del día, dos depósitos por zona de impacto
(``Head`` / ``Body``), frases para cinco movimientos (wave / greet /
surprised / sleepy / shy) y un recordatorio de estiramiento de 30
minutos. Los nombres de los depósitos son las zonas de impacto de
Imeru, así que su cabeza y su cuerpo responden a los clics; un rig
cuyas zonas de impacto usan los nombres de Cubism
(``HitAreaHead`` / ``HitAreaBody``) necesita depósitos con esos nombres.

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
       arrastre. ``-1, -1`` (nunca guardada) significa "usar la
       esquina inferior derecha". Cuando el monitor guardado ya no
       está, la posición se ajusta al interior de la primera pantalla.
   * - ``size_preset``
     - ``"medium"``
     - Uno de ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Los valores fuera de rango se limitan a ``[0.1, 1.0]``; solo
       un valor no numérico vuelve al valor por defecto.
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
     - ``auto_idle``, ``idle_motion``, ``auto_blink``
       ``true``; el resto ``false``
     - Subdiccionario indexado por id de driver (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mouse_gaze``, ``mic_lipsync``, ``webcam_tracking``). Las
       claves desconocidas circulan intactas para compatibilidad
       hacia adelante.
   * - ``show_on_launch``
     - ``false``
     - Lo establece **Show the pet when Imervue starts** en el grupo
       Window de la pestaña. El rig y los drivers se restauran al
       arrancar en cualquier caso; la superposición solo aparece
       cuando está activado.
   * - ``speech_enabled``
     - ``true``
     - Cuando es falso, el bocadillo de diálogo nunca aparece.
   * - ``hotkeys_enabled``
     - ``false``
     - Lo establece **Enable global hotkeys (needs pynput)** en el
       grupo Global hotkeys de la pestaña.
   * - ``hotkeys``
     - ``{}``
     - Sustituciones ``{action: key}`` de los valores por defecto
       ``ctrl+shift+p`` (mostrar / ocultar), ``ctrl+shift+l``
       (bloquear), ``ctrl+shift+t`` (clic transparente) y
       ``ctrl+shift+space`` (hablar ahora), establecidas por los
       campos de tecla del grupo Global hotkeys. Allí se rechaza una
       tecla que ya usa otra acción; las teclas guardadas que
       comparten dos acciones se indican en la línea de estado al
       abrir la pestaña.

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

Plugin de integraciones
^^^^^^^^^^^^^^^^^^^^^^^

El plugin **Desktop Pet Integrations** (``Plugins`` > ``Download Plugins``, categoría
``plugins``, nombre ``pet_integrations``) permite que la mascota reaccione al mundo exterior.
Añade ``Plugins`` > ``Desktop Pet Integrations`` con una entrada por integración y una entrada
``Settings…`` para sus opciones; una entrada puede activarse una vez que se ha mostrado la
mascota, instala primero el paquete opcional que necesita y sigue activada entre reinicios.
También es el ejemplo práctico de un plugin que amplía la mascota — véase *Escribir plugins* y
``on_pet_created``.

.. list-table::
   :header-rows: 1
   :widths: 22 56 22

   * - Integración
     - Qué hace la mascota
     - Necesita
   * - Reaccionar a eventos de OBS
     - Reproduce un movimiento del grupo ``Stream``, ``Record`` o ``Scene`` cuando empieza o
       termina la transmisión o la grabación, o cuando cambia la escena. Configure el host, el
       puerto y la contraseña del servidor WebSocket de OBS en ``Settings…``
     - ``obs-websocket-py`` (se instala en el primer uso); OBS con su servidor WebSocket activado
   * - Reaccionar al chat de Twitch
     - Se une al chat de un canal y reproduce el grupo de movimientos asignado a una palabra clave
       cada vez que un mensaje la contiene (sin distinguir mayúsculas de minúsculas; líneas
       ``keyword = Group`` en ``Settings…``). ``=hi`` solo coincide con un mensaje que sea
       exactamente "hi", ``!dance*`` con uno que empiece por "!dance", ``/go+al/`` es una
       expresión regular; gana la primera línea que coincida
     - Un nombre de canal y un token ``oauth:``
   * - Webhook local (127.0.0.1)
     - Escucha en ``http://127.0.0.1:9876/trigger`` (puerto en ``Settings…``) un POST JSON
       ``{"group": "Wave", "speech": "Hi!"}`` — cualquiera de los dos campos puede omitirse —
       enviado desde scripts, Stream Deck o herramientas de automatización. Con un token
       configurado, las solicitudes deben enviar ``Authorization: Bearer <token>``; las
       solicitudes procedentes de una página web se rechazan
     - Nada adicional
   * - Reaccionar a notificaciones de Windows
     - Reproduce el grupo ``Notify`` y dice el título de la notificación cuando otra aplicación
       muestra una notificación de Windows; se omiten las aplicaciones indicadas en los ids de
       aplicación ignorados. Windows pide acceso a las notificaciones la primera vez
     - Windows; los paquetes de notificaciones ``winrt`` (se instalan en el primer uso)

Un rig solo reacciona a los grupos de movimientos que tiene; un grupo que falta no reproduce
nada.

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

**"Load bundled Imeru" indica que el archivo no se encuentra.**
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
#. Si **Click-through** está activo, el clic va a la ventana que hay
   detrás de la mascota; desactívelo en la pestaña o en el menú de la
   bandeja. (Con el bocadillo activo, cada clic recibe una frase: un
   rig sin zonas de impacto no reproduce ningún movimiento, pero el
   clic igualmente le saluda.)

**La casilla de seguimiento por cámara web se desmarca sola.** El
seguimiento por cámara web necesita ``opencv-python`` y ``mediapipe``
instalados en el mismo entorno Python en el que se está ejecutando
Imervue. Instálelos con ``pip install opencv-python mediapipe``.
Después de la instalación, vuelva a marcar la casilla. La mascota no
abre ninguna ventana de vista previa; para ver lo que detecta la
cámara, active **Webcam tracking** en la pestaña Puppet, que muestra
los puntos faciales.

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
segundo monitor desconectado). En este caso la mascota pasa a la
primera pantalla con su posición guardada ajustada a ella —
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
     - Clic derecho > Modify > Rotate Clockwise
   * - Rotar 90 ° en sentido antihorario
     - ``Shift + R``
     - Clic derecho > Modify > Rotate Counter-clockwise
   * - Voltear horizontalmente
     - --
     - Clic derecho > Modify > Flip Horizontal
   * - Voltear verticalmente
     - --
     - Clic derecho > Modify > Flip Vertical
   * - Rotación sin pérdida
     - --
     - Clic derecho > Lossless Rotate > Lossless Rotate CW / CCW. Solo un JPEG es realmente
       sin pérdida (cambia su etiqueta de orientación); PNG / BMP / TIFF / WebP /
       GIF se decodifican, se giran y se vuelven a guardar (un WebP con pérdida se recodifica);
       los RAW de cámara, HEIC y los archivos de varios fotogramas se rechazan

----

Exportar imágenes
-----------------

Exportación individual
^^^^^^^^^^^^^^^^^^^^^^

Abra una imagen (Deep Zoom), después clic derecho > ``Export / Save As``.

- Elija el formato: PNG, JPEG, WebP, BMP, TIFF; AVIF cuando Pillow admite AVIF, HEIC y JPEG XL si ``pillow-heif`` / ``pillow-jxl-plugin`` está instalado
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
- **Procesar en**: la CPU o, si el plugin GPU Develop está instalado, una GPU dedicada (véase abajo)

Plugin GPU Develop
^^^^^^^^^^^^^^^^^^

El plugin **GPU Develop** (``Plugins`` > ``Download Plugins``, categoría ``plugins``, nombre
``gpu_develop``) permite que la exportación por lotes procese las recetas de revelado en una GPU
dedicada. ``Plugins`` > ``GPU Develop…`` instala ``wgpu`` la primera vez y después indica la GPU
que va a usar; a partir de entonces la exportación por lotes muestra **Procesar en** con esa GPU
elegida (elija **CPU** para procesar como antes).

- El balance de blancos, la exposición, las luces / sombras, los blancos / negros, el brillo, el contraste, la vibrancia, la saturación y la curva tonal se ejecutan en la GPU; la rotación, los volteos, el recorte y todo lo que viene después de la curva tonal (Split Toning, LUT, máscaras, niveles y el resto) se quedan en la CPU
- Una foto de 24 MP tarda unos 0,1 s en la GPU en lugar de unos 7 s en la CPU, sin contar la decodificación ni el guardado
- Solo se usa una GPU dedicada, nunca una GPU integrada ni un renderizador por software; en Windows, primero mediante Vulkan y después mediante Direct3D 12
- Una imagen con la que falla la GPU se procesa en la CPU, de modo que la exportación se completa igualmente
- El resultado coincide con el del renderizador de CPU con una diferencia de unos pocos niveles como máximo en una pequeña parte de los píxeles

Crear GIF / Vídeo
^^^^^^^^^^^^^^^^^

Seleccione varias imágenes, después clic derecho > ``Batch Operations`` > ``Create GIF / Video``.

- Salida GIF y MP4; el MP4 usa el ffmpeg del PATH o, si no lo hay, el que incluye la dependencia por defecto ``imageio-ffmpeg``
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

En el modo miniaturas, seleccione 2 o 4 imágenes, después clic derecho > ``Compare Images`` (o
elíjalas en la lista del diálogo).

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
     - ``File`` > ``Paste from Clipboard`` la abre en el editor de anotaciones (no se guarda nada);
       ``Ctrl + V`` la guarda como ``pasted_<timestamp>.png`` en la carpeta actual y la abre, o
       abre una ruta de archivo copiada al portapapeles
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
     - Seleccione varias, después ``Delete`` o clic derecho > ``Delete Selected Images``

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
/ barras de herramientas, la división entre árbol y visor y la carpeta raíz activa bajo un nombre
— después le permite alternar entre diseños guardados. La pestaña activa y la división de paneles de la pestaña Modify no se guardan. El diálogo admite Save Current, Load, Rename y Delete. Los
espacios de trabajo persisten en ``user_setting.json`` (bajo la clave ``workspaces``) y
sobreviven entre sesiones.

.. tip::
   Construya un espacio de trabajo **Browse** con un árbol ancho junto al visor, y un
   espacio de trabajo **Focus** separado con el árbol arrastrado hasta quedar estrecho y
   cerrados los docks que no necesite. Un solo clic mueve toda su ventana a la forma adecuada para cada tarea.

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
2. No se necesitan derechos de administrador: el registro escribe en el registro de Windows del usuario actual.
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

Escribir plugins
^^^^^^^^^^^^^^^^

Un plugin es un paquete de Python en ``plugins/<name>/`` — junto al paquete ``Imervue`` en una
copia del código fuente, junto al ejecutable en una compilación empaquetada (``Plugins`` > ``Open
Plugin Folder`` la abre). Su ``__init__.py`` asigna a ``plugin_class`` una subclase de
``Imervue.plugin.plugin_base.ImervuePlugin``; un único archivo ``.py`` en ``plugins/`` también se
carga (se usa su primera subclase de ``ImervuePlugin``), pero el descargador de plugins solo
distribuye paquetes. Los atributos de clase ``plugin_name``, ``plugin_version``,
``plugin_description`` y ``plugin_author`` son opcionales (``"Unnamed Plugin"``, ``"0.0.1"`` y
cadenas vacías por defecto). Cada ventana principal crea su propia instancia de cada plugin y se
pasa a sí misma, de modo que un hook puede usar ``self.main_window`` y ``self.viewer`` (el
``GPUImageView``). Sobrescriba solo los hooks que necesite; cada llamada está envuelta, así que
una excepción se registra con el nombre del plugin en lugar de detener Imervue. La guía completa,
con ejemplos, es
`PLUGIN_DEV_GUIDE.md <https://github.com/JeffreyChen-s-Utils/Imervue/blob/main/PLUGIN_DEV_GUIDE.md>`_.
Además de los hooks, un plugin puede dar a la exportación por lotes otro renderizador para las
recetas de revelado registrando un ``BackendProvider`` con
``Imervue.image.develop_backends.register`` en ``on_plugin_loaded()``; el plugin GPU Develop es
el ejemplo.

Un diálogo que aplica una transformación de imagen al pulsar **OK** puede tomar de
``Imervue.plugin.tool_dialog.ToolDialogMixin`` la fila de botones, la instalación de paquetes
opcionales, el hilo de trabajo y el toast con el resultado: el diálogo define ``output_suffix`` y
las claves del toast, y devuelve la transformación desde ``_transform()``. Un plugin que importa
código del programa principal añadido después de versiones más antiguas indica la versión de la API
de plugins que necesita en un archivo ``plugin.json`` junto a su ``__init__.py``
(``{"min_api_version": 2}``). ``Plugins`` > ``Download Plugins`` rechaza un plugin así en un
Imervue demasiado antiguo y conserva cualquier copia ya instalada, con la versión que necesita en
la línea de estado; el cargador de plugins lo omite sin importarlo y deja el motivo en el registro.

.. list-table::
   :header-rows: 1
   :widths: 28 40 32

   * - Hook
     - Cuándo se llama
     - Argumentos / retorno
   * - ``register_languages()`` (método de clase)
     - Sobre la clase del plugin antes de crear cada instancia (en cada carga y en ``Reload
       Plugins``), y al arrancar, antes de construir la ventana principal, cuando el idioma
       guardado no es uno integrado; esa pasada de arranque importa todos los plugins y no ejecuta
       nada más
     - Sin argumentos. Llame aquí a ``language_wrapper.register_language(language_code,
       display_name, word_dict)``; un código de idioma integrado se rechaza. El valor de retorno se
       ignora; una excepción se registra y el plugin se carga igualmente
   * - ``on_plugin_loaded()``
     - Justo después de crear la instancia: mientras se construye la ventana principal, y de
       nuevo tras ``Plugins`` > ``Reload Plugins``
     - Sin argumentos; el valor de retorno se ignora
   * - ``get_translations()``
     - Justo después de ``on_plugin_loaded()``, una vez por carga
     - Devuelve ``{language_code: {key: text}}`` (por defecto ``{}``). Las cadenas se fusionan en
       las tablas de idioma; las claves que ya existen nunca se sobrescriben y los códigos de
       idioma desconocidos se omiten
   * - ``on_build_main_tabs(tabs)``
     - Una vez mientras se construye la ventana principal, tras las cinco pestañas integradas y
       antes de ``on_build_menu_bar``; ``Reload Plugins`` no lo vuelve a ejecutar
     - ``tabs``: el ``QTabWidget`` de nivel superior de la ventana principal; añada una pestaña con
       ``tabs.addTab(widget, label)``. El valor de retorno se ignora
   * - ``on_build_menu_bar(plugin_menu)``
     - Una vez tras construir el menú ``Plugins`` compartido, y de nuevo tras ``Reload Plugins``
     - ``plugin_menu``: el ``QMenu`` ``Plugins`` (no la ``QMenuBar``). Las entradas que un plugin
       añada aquí en cualquier parte de la barra de menús se eliminan al recargar. El valor de
       retorno se ignora
   * - ``on_build_context_menu(menu, viewer)``
     - Cada vez que se construye el menú del clic derecho del visor, tras las entradas integradas y
       justo antes de abrirse
     - ``menu``: el ``QMenu`` contextual; ``viewer``: el ``GPUImageView``. El valor de retorno se
       ignora
   * - ``on_folder_opened(folder_path, image_paths, viewer)``
     - Cuando termina el escaneo de una carpeta abierta
     - ``folder_path``: la carpeta; ``image_paths``: todas las imágenes que encontró el escaneo. El
       valor de retorno se ignora
   * - ``on_image_loaded(image_path, viewer)``
     - Cada vez que una imagen se muestra a tamaño completo en deep zoom, se haya abierto como se
       haya abierto, y de nuevo cuando se recarga tras una edición; no para la vista previa de baja
       resolución que se muestra mientras se decodifica una imagen grande
     - ``image_path``: la ruta de la imagen. El valor de retorno se ignora
   * - ``on_image_switched(image_path, viewer)``
     - Cuando siguiente / anterior (incluido el salto circular en cualquiera de los extremos de la
       lista) pasa a otra imagen, en cuanto empieza su carga; ``on_image_loaded`` le sigue cuando se
       muestra. Abrir una imagen desde la cuadrícula o la tira de película no lo llama
     - ``image_path``: la nueva imagen actual. El valor de retorno se ignora
   * - ``on_image_deleted(deleted_paths, viewer)``
     - Tras eliminar imágenes por borrado suave (puestas en la pila de deshacer) desde el visor —
       la imagen actual o las miniaturas seleccionadas — o desde el árbol de carpetas; no para un
       archivo que el árbol envía directamente a la Papelera de reciclaje porque no está en la lista
       de imágenes
     - ``deleted_paths``: lista de las rutas eliminadas. El valor de retorno se ignora
   * - ``on_key_press(key, modifiers, viewer)``
     - En cada pulsación de tecla que recibe el visor, antes de sus teclas integradas y de las
       asignaciones de Shortcut Settings; se consulta a los plugins en orden de carga. Una tecla que
       un atajo de menú o de ventana capta primero nunca llega al visor
     - ``key``: un código ``Qt.Key`` (int); ``modifiers``: indicadores ``Qt.KeyboardModifier``.
       Devuelva ``True`` para consumir la tecla — se omiten los plugins posteriores y el manejo
       predeterminado; devuelva ``False`` (el valor por defecto) para dejarla pasar. Una excepción
       cuenta como ``False``
   * - ``on_pet_created(pet)``
     - Cuando la pestaña Desktop Pet crea la ventana de la mascota, y justo después de cargar el
       plugin (o de ejecutar ``Reload Plugins``) si la mascota ya existe
     - ``pet``: la ventana de la mascota. Los plugins usan ``play_group(group)``, ``speak(line)``,
       ``speak_notification(line)``, ``speech_on``, ``setting(key, default)``,
       ``persist(**fields)``, ``add_integration(key, controller)`` /
       ``remove_integration(key)`` / ``integration(key)`` y las señales ``hit_triggered``,
       ``moved`` y ``visibility_changed``. El valor de retorno se ignora
   * - ``on_app_closing(main_window)``
     - Cuando se cierra la última ventana principal, tras aceptarse el aviso de pestañas sin guardar
       de Paint y guardarse los ajustes, justo antes de descargar los plugins; cerrar otra ventana
       no lo llama
     - ``main_window``: la ``ImervueMainWindow`` que se cierra. El valor de retorno se ignora
   * - ``on_plugin_unloaded()``
     - Cuando se cierra la ventana del plugin (tras ``on_app_closing`` para la última ventana), y
       antes de que ``Reload Plugins`` vuelva a cargar los plugins; los plugins se descargan en
       orden inverso al de carga
     - Sin argumentos; el valor de retorno se ignora

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
     - Vista de píxeles (desde 400 % muestra RGB / HEX bajo el cursor; la cuadrícula cuando hay ≤ 40.000 píxeles de la imagen en pantalla)
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

Paint
^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``[`` / ``]``
     - Reducir / aumentar el tamaño del pincel en 1 px
   * - ``Shift + [`` / ``Shift + ]``
     - Reducir / aumentar el tamaño del pincel en 5 px
   * - ``Ctrl + Z``
     - Deshacer
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Rehacer
   * - ``Ctrl + D``
     - Deseleccionar
   * - ``Ctrl + 0`` / ``Ctrl + 1``
     - Ajustar a la ventana / Tamaño real (100 %)
   * - ``X``
     - Intercambiar los colores de primer plano / fondo
   * - ``D``
     - Restablecer los colores a negro / blanco
   * - ``Ctrl + Tab`` / ``Ctrl + Shift + Tab``
     - Pestaña Paint siguiente / anterior

Las teclas de herramientas se enumeran en *Paleta de herramientas (Banda izquierda)*.
``Settings`` > ``Shortcuts…`` en la pestaña Paint reasigna las teclas de herramientas, tamaño de
pincel, capas, deshacer / rehacer, deseleccionar, vista y color (``Ctrl + Y`` se mantiene como
segunda tecla de Rehacer).

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
de archivo (hasta 2000 resultados); haga doble clic en un resultado para abrirlo. Un nuevo escaneo solo lee los archivos nuevos o modificados desde el anterior y, con
**Compute perceptual hash** marcado, los indexados antes sin hash; los archivos que lee se
decodifican en varios hilos a la vez.

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
``Max Hamming distance`` para ampliar o restringir el ámbito.

Búsqueda semántica (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Semantic Search`` le permite escribir una frase en lenguaje natural (por
ejemplo *"golden retriever en la nieve"* o *"calle de neón por la noche"*) y devuelve, clasificadas,
las imágenes de la carpeta abierta. Cada imagen se incrusta con un encoder visual/lingüístico
CLIP y se almacena junto a su ruta; una consulta de texto se incrusta en el mismo espacio
vectorial y se compara por similitud coseno.

Las incrustaciones se almacenan en caché en ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) o ``~/.cache/imervue/clip_cache.npz`` (POSIX) como un único archivo ``.npz`` compacto. El diálogo busca en la carpeta abierta: solo incrusta las imágenes que la caché aún no tiene o que cambiaron desde entonces (tamaño o fecha de modificación), así que buscar otra vez en la misma carpeta empieza al instante, y los resultados vienen solo de esa carpeta.

.. note::
   Semantic Search ejecuta CLIP ViT-B/32 sobre ``onnxruntime``, sin PyTorch. La primera
   vez que lo abre sin ``onnxruntime``, Imervue ofrece instalarlo; después, el modelo
   (unos 150 MB, cuantizado a int8) se descarga una sola vez desde Hugging Face en una
   revisión fijada y a partir de entonces se lee de la caché local. Se ejecuta en una GPU
   NVIDIA mediante CUDA cuando ``onnxruntime`` la admite y, si no, en la CPU; nunca elige
   una GPU integrada. Las incrustaciones almacenadas en caché por un modelo distinto se
   vuelven a calcular.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` aplica etiquetas heurísticas
bajo ``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``graphic`` / ``landscape`` /
``portrait``),
deducidas de la saturación del color, los bordes y la forma de la imagen tal como la muestra el
visor. Se ejecuta en un hilo de trabajo con una barra de progreso en vivo.

Una vez que Semantic Search ha descargado el modelo CLIP, Auto-Tag pasa a etiquetar cada
imagen en modo zero-shot con ese modelo: hasta tres entre ``photo``, ``document``,
``screenshot``, ``graphic``, ``illustration``, ``portrait``, ``landscape``, ``animal``,
``food`` y ``text``, la más cercana primero. Una imagen que CLIP no puede leer recibe las
etiquetas heurísticas, y Auto-Tag nunca inicia la descarga por sí mismo.

Etiquetas jerárquicas
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gestiona etiquetas con
estructura de árbol como ``animal/cat/british``. Seleccione una etiqueta para ver todas las
imágenes bajo esa rama (descendientes incluidos). Etiquete o desetiquete la selección actual
con un clic. Las etiquetas jerárquicas viven en el índice de la biblioteca y son
complementarias al sistema de etiquetas planas del menú contextual.

Clic derecho > ``Batch Operations`` > ``Index Keywords`` (con miniaturas seleccionadas) añade a
la biblioteca las palabras clave XMP de la selección. Una jerarquía de palabras clave escrita por Lightroom o darktable
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

Archivos secundarios XMP
^^^^^^^^^^^^^^^^^^^^^^^^

Imervue puede leer y escribir archivos secundarios Adobe XMP (``photo.jpg`` ↔ ``photo.xmp``)
para que valoraciones, títulos, descripciones, palabras clave y etiquetas de color hagan ida
y vuelta limpiamente con Adobe Bridge y otros gestores de fotos con soporte XMP.

Al guardar se fusiona con el sidecar existente: solo cambian estos campos, así que los ajustes de revelado, el recorte y el historial de otro programa se conservan, y un sidecar ilegible nunca se sobrescribe.

Además de ``photo.xmp`` (Lightroom, Bridge), se lee y actualiza el
``photo.jpg.xmp`` que escriben darktable y digiKam cuando es el único sidecar.
Las etiquetas de color se entienden con las palabras de Lightroom (``Red`` …
``Purple``) y las de Bridge (``Select``, ``Second``, ``Approved``, ``Review``,
``To Do``). Un color nuevo o cambiado se exporta como lo escribe Lightroom; un
sidecar que ya tiene la palabra de Bridge para ese mismo color conserva esa palabra.
Una etiqueta sin color (una personalizada) se deja en el sidecar.

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

Un marcador de descarte de tres estados. Pulse ``P`` para marcar la imagen
actual o cada mosaico seleccionado, ``Shift + X`` para rechazar, ``U`` para quitar la marca.
``Filter`` > ``By Cull State`` muestra sólo picks, rejects o sin marcar. ``Extra Tools`` >
``Workflow`` > ``Culling`` aplica el filtro mediante un diálogo y también expone un botón **Delete all
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
mes o año (agrupado por fecha). La fecha se toma de EXIF ``DateTimeOriginal``, después de
``DateTimeDigitized``, después de ``DateTime`` y, si no, de la fecha de modificación del
archivo. Haga doble clic en cualquier imagen para abrirla en Deep Zoom.

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
cualquier archivo Adobe ``.cube`` (3D hasta 65³, 1D hasta 65.536 puntos). ``LUT_1D_INPUT_RANGE`` /
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
escala radial de aberración cromática por canal para rojo y azul. La imagen corregida, del
mismo tamaño que la original, se guarda como un archivo nuevo.

Vista de mapa
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` traza las imágenes con geotag de la carpeta
abierta en un mapa Leaflet + OpenStreetMap interactivo, con un marcador por ciudad más
cercana y el número de imágenes que hay allí (requiere ``PySide6.QtWebEngineWidgets``).
Sin WebEngine, el diálogo recurre a una lista de esos lugares con sus recuentos y
coordenadas, para que la función siga siendo usable en instalaciones mínimas.

Vista de calendario
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` muestra un ``QCalendarWidget`` con los días
resaltados cuando se tomaron fotos ese día (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → ``DateTime`` → mtime del archivo). Seleccionar una fecha lista sus
imágenes; doble clic para abrir una en el visor principal.

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
recorte normalizado (0..1) con un ángulo de enderezamiento de hasta ±15°. La salida se
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
sobre una transformación en NumPy puro (Frame & Caption dibuja con Pillow; la misma
lógica también se expone como herramienta MCP):

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

El **editor EXIF** (botón ``Edit EXIF`` de la barra lateral EXIF) cambia la descripción, el artista, el copyright, la marca / modelo de la cámara y el comentario. Un JPEG o WebP no necesita paquetes extra y solo se reescribe su bloque EXIF; los demás formatos explican por qué no se pueden editar. **Describe**, junto a la descripción, pide a un modelo de visión de su propio equipo un texto alternativo de una frase y lo coloca en el campo para que lo edite antes de **Save**: necesita `Ollama <https://ollama.com>`__ en ejecución en ``localhost:11434`` con un modelo de visión (``ollama pull llava``) y, cuando ninguno responde, el diálogo lo indica y deja el campo como estaba. La imagen solo se envía a ese servidor local.

Galería web
^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Web Gallery`` guarda las imágenes seleccionadas (o toda la
carpeta) como un sitio autocontenido: ``index.html`` con lightbox, miniaturas JPEG y copias de los
originales, salvo que desmarque **Copiar los originales a tamaño completo**. Puede elegir el título
de la página y el tamaño y la calidad de las miniaturas. Con los originales copiados, la página
no necesita servidor: ábrala desde el disco o súbala a cualquier alojamiento estático. Sin ellos,
sus enlaces a tamaño completo apuntan a las imágenes de su propio disco.

Marque **Revisión del cliente** para enviar la galería y recoger opiniones. Cada imagen recibe un
cuadro de comentario; las notas se quedan en el navegador del revisor y el botón
**Export comments** de la página las guarda todas en un único archivo JSON.

Diseño de impresión
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` compone varias imágenes en un PDF de varias
páginas con tamaño de página, orientación, cuadrícula, márgenes, canalón y marcas de recorte
configurables. Requiere ``reportlab``.

----

Referencia del menú Extra Tools
-------------------------------

Todas las entradas del menú ``Extra Tools``, submenú por submenú, en el orden del menú. Muchas
tienen una sección más completa más arriba; esta lista es el inventario completo. Las entradas que
guardan un archivo nuevo lo escriben junto al original y añaden ``_1``, ``_2`` … cuando el nombre
ya está ocupado; las entradas marcadas como "guardado en la receta" son ediciones no destructivas
de los ajustes de revelado de la imagen. Los plugins pueden añadir sus propias entradas a estos
submenús.

Lote (Batch)
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``Batch Format Conversion``
     - Convierte las imágenes de una carpeta (por defecto la carpeta actual) a PNG, JPEG, WebP, BMP
       o TIFF, o a HEIC / AVIF / JXL cuando sus codificadores están instalados, con opciones de
       calidad, omitir el mismo formato y enviar los originales a la papelera.
   * - ``Batch EXIF Strip``
     - Elimina EXIF, GPS y otros metadatos de todas las imágenes de una carpeta por privacidad,
       sobrescribiendo los originales o escribiendo copias limpias en una carpeta de salida.
   * - ``Image Sanitizer``
     - Vuelve a renderizar las imágenes de una carpeta a partir de los píxeles en bruto, eliminando
       todos los datos ocultos (metadatos, esteganografía, bytes sobrantes al final) y renombrando
       cada una como fecha + cadena aleatoria; también puede ampliar las imágenes pequeñas a una
       resolución objetivo, como en ``AI Image Upscale``.
   * - ``Image Organizer``
     - Ordena las imágenes de una carpeta en subcarpetas por fecha (año-mes o año), resolución,
       tipo de archivo, tamaño de archivo o un número fijo por carpeta, copiándolas o moviéndolas,
       con vista previa.
   * - ``Token Batch Rename``
     - Renombra las imágenes seleccionadas (o toda la carpeta) a partir de una plantilla de tokens
       como ``{name}_{counter:04}`` o ``{date}_{camera}``, con una vista previa en vivo que señala
       los conflictos; los sidecars, las valoraciones y las etiquetas acompañan a los archivos.
   * - ``Deflicker (Time-lapse)``
     - Iguala el brillo de un fotograma a otro en los fotogramas de time-lapse de la carpeta actual
       (objetivo de media móvil o de media global) y escribe las copias corregidas en una subcarpeta
       ``deflickered/``, sin tocar los originales.
   * - ``Document Binarize``
     - Convierte una foto o un escaneo de una página en negro sobre blanco limpio con umbralización
       adaptativa de Sauvola (controles de tamaño de ventana y k), guardando ``<name>_bw.png`` junto
       al original.
   * - ``Otsu Threshold``
     - Convierte la imagen actual a blanco y negro con su umbral global de Otsu elegido
       automáticamente, con opción de invertir, guardando ``<name>_otsu.png``.
   * - ``Edit Animation``
     - Invierte, hace un boomerang, cambia el ritmo (de 0,25x a 4x) u optimiza (fusiona los
       fotogramas repetidos de) el GIF, APNG o WebP animado actual, guardando
       ``<name>_edited.gif``.
   * - ``Optimize to Target Size``
     - Vuelve a codificar la imagen actual como JPEG o WebP con la calidad más alta que cabe en un
       presupuesto de tamaño en KB, guardando ``<name>_opt.jpg`` o ``<name>_opt.webp``.
   * - ``Meme Caption``
     - Añade a la imagen actual las clásicas leyendas de meme arriba y abajo (texto blanco en
       mayúsculas con contorno negro, con ajuste de línea), guardando ``<name>_meme.png``.
   * - ``Steganography``
     - Oculta un mensaje de texto en los bits menos significativos de la imagen actual, guardada
       como un ``<name>_stego.png`` sin pérdida, o revela un mensaje oculto de ese modo.

Biblioteca y metadatos (Library & Metadata)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``Library Search``
     - Gestiona las carpetas raíz de la biblioteca, las escanea en el índice (opcionalmente con
       hashes perceptuales) y busca en él por nombre de archivo, ancho / alto mínimo y tamaño de
       archivo en KB; haga doble clic en un resultado para abrirlo.
   * - ``Smart Albums``
     - Guarda álbumes basados en reglas (extensiones, nombre, etiquetas, lugar, tamaño y valoración
       mínimos, etiqueta de color, estado de descarte, favoritos) y muestra sus coincidencias; puede
       crear un álbum por ciudad a partir de los datos GPS, e importar o exportar álbumes.
   * - ``Find Similar Images``
     - Busca en la biblioteca imágenes que se parecen a la imagen actual (o a la primera
       seleccionada) por hash perceptual dentro de una distancia de Hamming elegida; escanee antes
       sus raíces con pHash en ``Library Search``.
   * - ``Semantic Search``
     - Busca imágenes de la carpeta actual que coinciden con una descripción de texto como "playa
       al atardecer" usando CLIP sobre ``onnxruntime`` (se ofrece su instalación en el primer uso);
       el modelo de ~150 MB se descarga una sola vez.
   * - ``Find Duplicate Images``
     - Escanea una carpeta (opcionalmente con subcarpetas) en busca de duplicados exactos por hash
       de archivo o de imágenes parecidas por hash perceptual; puede preseleccionar todas salvo la
       mejor copia de cada grupo y mover la selección a la Papelera de reciclaje.
   * - ``Auto-Tag Images``
     - Etiqueta las imágenes seleccionadas, o toda la carpeta, con etiquetas heurísticas de
       contenido (foto, documento, captura de pantalla, gráfico, horizontal, vertical) bajo
       ``auto/`` en el árbol de etiquetas jerárquicas, o con etiquetas CLIP una vez que la búsqueda
       semántica ha descargado su modelo.
   * - ``Hierarchical Tags``
     - Crea y elimina etiquetas con estructura de árbol como ``animal/cat/british``, enumera las
       imágenes bajo una etiqueta y etiqueta o desetiqueta los mosaicos seleccionados.
   * - ``Export Metadata (CSV / JSON)``
     - Escribe un registro por imagen de la vista actual (datos del archivo, campos EXIF clave como
       cámara, objetivo, exposición e ISO, valoración, etiqueta de color, etiquetas y nota) en un
       archivo CSV o JSON.
   * - ``XMP Sidecars``
     - Exporta o importa archivos sidecar ``.xmp`` para cada imagen de la vista actual, de modo que
       la valoración, el título, la descripción, las palabras clave y la etiqueta de color van y
       vuelven con Adobe Bridge, Lightroom y otras herramientas compatibles con XMP.
   * - ``GPS Geotag``
     - Escribe una latitud y una longitud (grados decimales) en las etiquetas GPS EXIF de la imagen
       actual, sustituyendo las que ya hubiera; solo archivos JPEG y WebP.
   * - ``Geotag from GPX Track``
     - Empareja las imágenes seleccionadas (o toda la vista) con una traza ``.gpx`` según su hora
       de captura EXIF: indique cuánto se desviaba el reloj de la cámara respecto de UTC y a qué
       distancia de un punto de la traza puede estar una foto (y si se interpola entre puntos),
       vea cuántas caen sobre la traza y luego escriba sus posiciones en las etiquetas GPS EXIF;
       solo archivos JPEG y WebP.
   * - ``Edit Capture Time``
     - Desplaza la hora de captura EXIF de las imágenes seleccionadas (o de toda la vista) en
       días, horas, minutos y segundos, o según cuándo se tomó realmente la primera foto,
       reescribiendo DateTimeOriginal, DateTimeDigitized y DateTime; las fotos sin hora de captura
       EXIF no se modifican, y solo se pueden reescribir JPEG y WebP.
   * - ``Thumbnail Cache``
     - Muestra cuánto espacio en disco ocupa la caché de miniaturas y la vacía.

Vistas (Views)
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``By day``
     - En ``Timeline View``: sustituye la vista principal por las imágenes de la carpeta actual
       agrupadas bajo un encabezado por día de captura (fecha EXIF, o si no la fecha del archivo);
       haga doble clic en una imagen para abrirla.
   * - ``By month``
     - En ``Timeline View``: la misma línea de tiempo, agrupada por mes de captura.
   * - ``By year``
     - En ``Timeline View``: la misma línea de tiempo, agrupada por año de captura.
   * - ``Calendar View``
     - Muestra un calendario que resalta los días con fotos en la carpeta actual (por fecha de
       captura); haga clic en un día para listar sus imágenes y doble clic en una para abrirla.
   * - ``Map View``
     - Sitúa las imágenes geoetiquetadas de la carpeta actual en un mapa de OpenStreetMap, un
       marcador por ciudad más cercana con un recuento; el mapa se carga en línea y, sin
       QtWebEngine, recurre a una lista de coordenadas.
   * - ``Scopes & Inspector``
     - Analiza la imagen actual en pestañas: forma de onda de luminancia, desfile RGB, exposición
       en falso color, focus peaking, Error Level Analysis y detección de clonado (copiar-mover).
   * - ``Tiny Planet (360°)``
     - Reproyecta un panorama equirrectangular de 360° en proporción 2:1 en un "pequeño planeta"
       cuadrado del tamaño elegido, guardando ``<name>_planet.png``; avisa cuando la imagen no es
       2:1.
   * - ``Image Statistics``
     - Muestra la media, el mínimo, el máximo, la desviación estándar y la mediana de los canales
       R, G, B y de luminancia de la imagen actual, y exporta su histograma de 256 niveles como CSV.
   * - ``Quality Report``
     - Enumera métricas de calidad sin referencia de la imagen actual: colorido, entropía tonal,
       contraste RMS, densidad de bordes y ruido estimado.
   * - ``Test Chart``
     - Genera un patrón de calibración (barras de color SMPTE, cuña de grises, rampa de degradado,
       tablero de ajedrez o color sólido) con el ancho y el alto elegidos y lo guarda en un archivo.
   * - ``Off``
     - En ``Color blindness preview``: desactiva la vista previa de deficiencia de la visión del
       color.
   * - ``Protanopia (red-blind)``
     - En ``Color blindness preview``: muestra la imagen en el visor como la ve una persona con
       protanopía; solo visualización, el archivo y su receta no se tocan.
   * - ``Deuteranopia (green-blind)``
     - En ``Color blindness preview``: simula la deuteranopía, la deficiencia rojo-verde más
       común; solo visualización.
   * - ``Tritanopia (blue-blind)``
     - En ``Color blindness preview``: simula la tritanopía (deficiencia azul-amarillo); solo
       visualización.
   * - ``Achromatopsia (greyscale)``
     - En ``Color blindness preview``: muestra la imagen totalmente en escala de grises, como con
       acromatopsia; solo visualización.

Flujo de trabajo (Workflow)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``Culling``
     - Filtra la carpeta actual por imágenes elegidas, rechazadas o sin marcar, hace un descarte
       automático eligiendo la imagen más nítida de cada grupo de imágenes parecidas y rechazando el
       resto, y puede eliminar permanentemente todas las rechazadas.
   * - ``Staging Tray``
     - Una cesta persistente entre carpetas: añada los mosaicos seleccionados o la imagen actual
       desde cualquier carpeta, y luego muévalos o cópielos todos a una carpeta, o muestre la
       bandeja como un álbum.
   * - ``Reference Panel``
     - Fija imágenes de referencia (añadidas desde archivos, arrastrando y soltando o desde la
       imagen actual) con una vista previa grande para compararlas lado a lado; la lista se conserva
       entre reinicios.
   * - ``Virtual Copies``
     - Guarda instantáneas con nombre de la receta de revelado de la imagen actual y cambia entre
       ellas sin duplicar el archivo.
   * - ``Dual-Pane File Manager``
     - Dos árboles de carpetas lado a lado para copiar o mover la selección de uno a otro, o abrir
       un archivo en el visor.
   * - ``Macros``
     - Graba, edita, depura y reproduce macros de acciones de valoración, favorito, etiqueta de
       color y etiqueta sobre las imágenes seleccionadas.
   * - ``Watched Folder``
     - Mientras el diálogo está abierto, vigila una carpeta (incluidas las subcarpetas) y asigna un
       predefinido de revelado elegido a cada imagen nueva que llega, para flujos de captura
       conectada o de importación sin intervención.

Exportar (Export)
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``Contact Sheet PDF``
     - Dispone las miniaturas de las imágenes seleccionadas (o de toda la carpeta) en una
       cuadrícula de filas x columnas sobre páginas A4, A3, Letter o Legal, con márgenes, un título
       opcional y leyendas opcionales con el nombre de archivo. El cuadro **Diseño** aplica un
       predefinido — Default (4 × 5, 10 mm, con leyendas), Compact (6 × 8, 5 mm, sin leyendas),
       Proof (5 × 6, 8 mm, con leyendas), Editorial (2 × 3, 18 mm, con leyendas) o Index (8 × 10,
       4 mm, sin leyendas), en columnas × filas — y editar a mano cualquiera de esos valores lo
       deja en Custom.
   * - ``Web Gallery``
     - Exporta las imágenes seleccionadas (o toda la carpeta) como una galería HTML autocontenida
       con miniaturas y lightbox; puede copiar los originales y añadir cuadros de comentarios de
       revisión del cliente que se exportan como JSON.
   * - ``Slideshow Video``
     - Renderiza las imágenes seleccionadas (o toda la carpeta) en un MP4 con el tamaño, la
       frecuencia de fotogramas, el tiempo de permanencia, la calidad y la transición (fundido,
       disolución, deslizamiento o barrido) elegidos.
   * - ``Print Layout``
     - Dispone imágenes en una cuadrícula de PDF de varias páginas con tamaño de página,
       orientación, filas, columnas, margen, canalón y marcas de recorte; requiere el paquete
       opcional ``reportlab``.
   * - ``Collage``
     - Compone las imágenes seleccionadas (o toda la carpeta) en un montaje en cuadrícula de 1 a 12
       columnas, guardando ``collage.png`` junto a la primera imagen.
   * - ``ID Photo Sheet``
     - Repite el retrato actual a un tamaño de documento de identidad (35 x 45 mm, 2 x 2 in,
       33 x 48 mm o 50 x 70 mm) en papel 4x6, 5x7, A4 o Letter a 300 DPI, guardando
       ``<name>_idsheet.png``.

Revelado no destructivo (Develop, Non-Destructive)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``Before / After Compare``
     - Muestra la imagen actual sin y con su receta de revelado en una sola vista, dividida por un
       separador arrastrable.
   * - ``Develop Presets…``
     - Guarda la receta de la imagen actual como un predefinido con nombre y luego lo aplica a la
       imagen actual o a la selección, o fusiona solo sus ajustes activos en las recetas de cada
       una.
   * - ``Tone Curve``
     - Edita una curva RGB maestra y curvas roja, verde y azul independientes sobre un histograma
       (clic para añadir, arrastrar para mover, clic derecho para quitar un punto); guardado en la
       receta.
   * - ``Apply .cube LUT``
     - Aplica una LUT 3D o 1D ``.cube`` de Adobe con una intensidad ajustable; guardado en la
       receta, y ``Clear`` la quita.
   * - ``Split Toning``
     - Tiñe sombras y luces con matiz y saturación independientes, más un control de balance;
       guardado en la receta.
   * - ``Local Adjustment Masks``
     - Añade máscaras de pincel, radiales y de degradado lineal, cada una con su propia exposición,
       brillo, contraste, saturación, temperatura, tinte, luces, sombras y difuminado; guardado en
       la receta.
   * - ``Layers``
     - Apila hasta ocho capas superpuestas de texto, imagen o LUT con opacidad y fusión normal,
       multiplicar, trama o superponer; guardado en la receta.
   * - ``Levels``
     - Establece el punto negro, el punto blanco y la gamma; guardado en la receta.
   * - ``Channel Mixer``
     - Reconstruye cada canal de salida a partir de las entradas roja, verde y azul ponderadas más
       un desplazamiento, con un modo monocromo para la conversión a blanco y negro; guardado en la
       receta.
   * - ``Gradient Map``
     - Asigna la luminancia a través de un degradado predefinido (Mono, Sepia, Cyanotype, Fire,
       Ocean, Magenta–Teal) con una intensidad ajustable, opcionalmente mezclado en OkLCH
       perceptual; guardado en la receta.
   * - ``Auto Color Balance``
     - Elimina las dominantes de color con el método gray-world, white-patch, niveles automáticos
       (percentil) o Retinex, mezclado mediante un control de intensidad, guardando
       ``<name>_balanced.png``.
   * - ``Clarity / Dehaze``
     - Aplica los controles de contraste local Dehaze, Clarity y Texture, guardando
       ``<name>_local.png``.
   * - ``HSL / Color Mixer``
     - Ajusta el matiz, la saturación y la luminancia por separado para ocho bandas de color (del
       rojo al magenta), guardando ``<name>_hsl.png``.
   * - ``CLAHE (Local Equalize)``
     - Refuerza el contraste local con ecualización adaptativa de histograma con contraste limitado
       (límite de recorte y número de teselas) sobre la luminancia, guardando
       ``<name>_clahe.png``.
   * - ``Flatten Background``
     - Elimina un degradado de fondo suave como la contaminación lumínica o una iluminación
       desigual (restar), o el viñeteado (dividir), con un grado ajustable, guardando
       ``<name>_flat.png``.
   * - ``Frame & Caption``
     - Añade un borde mate de color, una franja inferior opcional estilo Polaroid y una leyenda,
       guardando ``<name>_framed.png``.
   * - ``Ordered Dither``
     - Reduce cada canal a entre 2 y 8 niveles con un patrón de tramado ordenado de Bayer para un
       aspecto de impresión retro, guardando ``<name>_dither.png``.
   * - ``Color Map``
     - Vuelve a colorear la luminancia de la imagen con el mapa de color viridis, magma o jet,
       guardando ``<name>_colormap.png``.
   * - ``Distort``
     - Aplica un remolino, un pellizco / abombamiento u ondulaciones a la imagen con una intensidad
       ajustable, guardando ``<name>_distort.png``.
   * - ``Polar Coordinates``
     - Envuelve la imagen en un disco, o desenrolla un disco en una franja, invirtiendo
       opcionalmente el radio, guardando ``<name>_polar.png``.
   * - ``Kaleidoscope``
     - Refleja una cuña alrededor del centro en un patrón simétrico con el número de segmentos y la
       rotación elegidos, guardando ``<name>_kaleidoscope.png``.
   * - ``Frosted Glass``
     - Dispersa cada píxel a una posición cercana aleatoria (radio en píxeles, semilla
       reproducible) para un aspecto de vidrio texturizado, guardando ``<name>_frosted.png``.
   * - ``Pixel Sort``
     - Ordena los píxeles por brillo a lo largo de filas o columnas dentro de una banda de brillo
       inferior / superior para un aspecto glitch, guardando ``<name>_pixelsort.png``.
   * - ``Film Grain``
     - Añade grano de película procedural con controles de intensidad, tamaño de grano, monocromo
       y semilla; guardado en la receta.
   * - ``Lens Flare``
     - Añade un destello de lente sintético en la posición elegida con controles de intensidad,
       tamaño del halo y color; guardado en la receta.
   * - ``Threshold / Posterize``
     - Aplica un umbral de blanco y negro (de 0 a 255) y / o posteriza cada canal a entre 2 y 64
       niveles; guardado en la receta.
   * - ``Solarize``
     - Invierte los tonos por encima de un umbral para un aspecto de solarización de cuarto
       oscuro, mezclado mediante un control de mezcla, guardando ``<name>_solarize.png``.
   * - ``Diffuse Glow``
     - Añade un resplandor suave estilo Orton con controles de cantidad, radio y umbral de luces,
       guardando ``<name>_glow.png``.
   * - ``Graduated Density``
     - Oscurece un lado del encuadre a lo largo de una línea recta como un filtro ND degradado
       (ángulo, pasos, dureza, desplazamiento, tinte opcional), guardando ``<name>_gradnd.png``.
   * - ``Velvia``
     - Refuerza sobre todo los colores apagados, como la película de diapositivas Velvia, con
       controles de intensidad y de protección de sombras, guardando ``<name>_velvia.png``.
   * - ``Emboss``
     - Renderiza un relieve iluminado desde un acimut y una elevación elegidos, con un control de
       profundidad y una opción de escala de grises, guardando ``<name>_emboss.png``.
   * - ``Defringe``
     - Desatura los flecos púrpura, verdes o de cualquier color a lo largo de los bordes de alto
       contraste, con controles de cantidad y umbral de borde, guardando ``<name>_defringe.png``.
   * - ``Film Negative``
     - Invierte un negativo de color escaneado en un positivo, eliminando la base naranja de la
       película (estimada automáticamente), con una gamma de salida, guardando
       ``<name>_positive.png``.
   * - ``Filmic Tone Map``
     - Suaviza la caída de las luces con una curva fílmica Reinhard o Hable, con controles de
       exposición, punto blanco, contraste y saturación, guardando ``<name>_filmic.png``.
   * - ``Tone Equalizer``
     - Ajusta la exposición por separado para negros, sombras, medios tonos, luces y blancos, con
       suavizado para evitar halos, guardando ``<name>_toneeq.png``.
   * - ``Detail Equalizer``
     - Refuerza o reduce el contraste por separado en las bandas de detalle fina, media, gruesa y
       amplia, guardando ``<name>_detaileq.png``.
   * - ``Soft Proof``
     - Previsualiza la imagen actual a través de un perfil ICC de salida elegido, pintando en
       magenta los píxeles fuera de gama y contándolos; no se guarda nada.

Retoque y transformación (Retouch & Transform)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``AI Image Upscale``
     - Amplía una carpeta de imágenes con Real-ESRGAN (general x4, anime x4 o x2) o con remuestreo
       Lanczos, Bicubic o Nearest; los modelos de IA instalan ``onnxruntime`` bajo demanda y se
       descargan automáticamente en el primer uso (~65 MB).
   * - ``Noise Reduction / Sharpening``
     - Aplica una reducción de ruido que preserva los bordes (opcionalmente solo de luminancia) y
       un enfoque unsharp-mask con cantidad y radio, guardando en el archivo elegido; requiere
       OpenCV (``opencv-python``).
   * - ``Healing Brush``
     - Elimina los puntos en los que hace clic sobre una vista previa (el clic derecho borra un
       punto) mediante inpainting con el método Telea o Navier-Stokes, guardando en el archivo
       elegido; requiere OpenCV.
   * - ``Clone Stamp``
     - Copia un parche de bordes suaves desde un punto de origen marcado con Shift+clic a cada
       punto en el que hace clic sobre una vista previa (el clic derecho deshace), guardando el
       resultado en el archivo elegido.
   * - ``Frequency Separation``
     - Divide la imagen actual con el radio de desenfoque elegido en ``<name>_low.png`` (color y
       tono) y ``<name>_high.png`` (textura) para retocarlas en otro programa; se recombinan como
       low + (high - 128).
   * - ``Smart Crop``
     - Sugiere recortes basados en la saliencia (libre, 1:1, 4:5, 3:2, 16:9) que sitúan el sujeto
       en un punto de la regla de los tercios, y escribe el elegido en la receta como un recorte no
       destructivo.
   * - ``Portrait Auto-Retouch``
     - Suaviza las zonas de tono de piel, elimina los ojos rojos y añade una pasada final de
       enfoque, cada uno con su propio control, guardando ``<name>_retouched.png``.
   * - ``Face Detection``
     - Detecta rostros en la imagen actual con la cascada Haar de OpenCV y permite poner nombre a
       cada uno; los nombres se guardan con la receta. Requiere OpenCV 4 (``opencv-python<5``).
   * - ``Sky / Background``
     - Sustituye el cielo por un degradado, o elimina el fondo dejándolo transparente o blanco,
       guardando en el archivo elegido; necesita OpenCV y usa ``rembg`` para recortar el fondo
       cuando está instalado.
   * - ``Crop / Straighten``
     - Gira hasta ±15° (recortando las esquinas vacías) y recorta por coordenadas normalizadas o
       por un predefinido de relación de aspecto, guardando en el archivo elegido; el enderezado
       requiere OpenCV.
   * - ``Auto-Straighten``
     - Mide la inclinación del horizonte o de las líneas verticales, permite ajustar la rotación y
       guarda la imagen enderezada en el archivo elegido; requiere OpenCV.
   * - ``Lens Correction``
     - Corrige la distorsión de barril / cojín, el viñeteado y la aberración cromática roja / azul
       con controles deslizantes, guardando en el archivo elegido.
   * - ``Scale Bar``
     - Graba en la imagen actual una barra de escala calibrada a partir de un valor de píxeles por
       unidad y una etiqueta de unidad, guardando ``<name>_scalebar.png``.

Multi-imagen (Multi-Image)
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - Función
   * - ``HDR Merge``
     - Fusiona dos o más tomas con exposiciones distintas mediante la fusión de exposición de
       Mertens (no hacen falta datos de exposición), alineándolas antes opcionalmente; requiere
       OpenCV.
   * - ``Panorama Stitch``
     - Cose dos o más tomas superpuestas, tomadas en orden con un solapamiento del 20 al 40 %, en
       modo panorama o de escaneo plano, recortando opcionalmente los bordes negros; requiere OpenCV.
   * - ``Focus Stacking``
     - Combina una horquilla de enfoque en una sola imagen enfocada de principio a fin conservando
       los píxeles más nítidos de cada fotograma, alineándolos antes opcionalmente; requiere OpenCV.
   * - ``Image Stack``
     - Combina píxel a píxel una ráfaga ya alineada por media, mediana, máximo, mínimo o media con
       recorte sigma, para exposiciones largas, eliminación de multitudes o trazas de estrellas; no
       necesita OpenCV.
   * - ``Anaglyph 3D``
     - Combina la imagen actual (ojo izquierdo) con una imagen elegida para el ojo derecho en un
       anaglifo rojo-cian (método Dubois, color, gris o verdadero), guardando
       ``<name>_anaglyph.png``.

----

Uso desde la línea de comandos
------------------------------

::

   python -m Imervue                      # Launch normally
   python -m Imervue /path/to/image       # Open a specific image
   python -m Imervue /path/to/folder      # Open a specific folder
   python -m Imervue --debug              # Enable debug mode
   python -m Imervue --software_opengl    # Use software rendering (when GPU is unsupported)

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
     - Conversión de formato (``--format`` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL, ``--quality``); redimensionado a un lado largo (``--max``) o a un ``--width`` / ``--height`` exacto; caja de miniatura
   * - ``watermark`` / ``optimize``
     - Marca de agua de texto (``--text``, ``--corner``, ``--opacity``, ``--font-fraction``, ``--color R G B``, ``--no-shadow``); codificar bajo un presupuesto ``--max-kb``
   * - ``dehaze`` / ``clahe`` / ``dither`` / ``distort``
     - Eliminación de neblina por canal oscuro, ecualización adaptativa, tramado Bayer ordenado, swirl / pinch / ripple
   * - ``auto-orient`` / ``strip``
     - Fijar la orientación EXIF en los píxeles; volver a guardar sin EXIF / XMP / ICC
   * - ``collage`` / ``anaglyph``
     - Montaje en cuadrícula (``--columns``, ``--cell-width`` / ``--cell-height``, ``--gap``, ``--margin``, ``--background R G B``); 3D rojo-cian a partir de un par estéreo (``--method``)
   * - ``preset`` / ``pipeline``
     - Aplicar un preajuste de revelado guardado por nombre; ejecutar una cadena JSON ordenada de operaciones
   * - ``list-ops``
     - Listar todos los subcomandos (``--json`` para salida legible por máquina)

Cada subcomando decodifica como el visor: las salidas se enderezan según la orientación EXIF y se convierten a sRGB desde el perfil de color incrustado, las entradas AVIF las lee el propio Pillow, y las HEIC / JPEG XL se leen cuando su backend opcional está instalado. Un RAW de cámara se revela como en el visor en lugar de leerse como su pequeña vista previa incrustada; ``resize`` y ``strip`` lo escriben como PNG. Un archivo ilegible se informa y el resto se procesa igualmente. Un archivo incompleto se lee hasta donde llega, como en el visor. Los grises de 16 bits y de coma flotante se escalan a 8 bits como en el visor; ``resize`` y ``strip`` conservan la profundidad de bits del original.

Los subcomandos que reciben archivos o carpetas (todos salvo ``collage``, ``anaglyph`` y ``list-ops``) comparten ``--out`` (directorio de salida), ``--recursive``, ``--dry-run`` (listar acciones sin escribir nada), ``--overwrite`` y ``-j`` / ``--jobs`` (workers en paralelo; ``0`` usa todos los núcleos). ``collage`` y ``anaglyph`` escriben el único archivo que indica ``--out``. ``--version`` muestra la versión de la CLI.

Cada herramienta del servidor MCP (véase `Servidor MCP`_) es también un subcomando. Diez de ellas son los subcomandos anteriores (``convert_format`` es ``convert``, ``quality_metrics`` es ``stats``, ``build_collage`` es ``collage``, etc.); las otras 48 ejecutan el código propio de la herramienta MCP:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tipo
     - Subcomandos
   * - Ediciones: escriben ``<stem>_<name>.png`` junto a cada origen, o ``<stem>.png`` en ``--out``
     - ``frame``, ``crop``, ``rotate``, ``solarize``, ``glow``, ``velvia``, ``emboss``, ``film-negative``, ``defringe``, ``graduated-density``, ``filmic-tonemap``, ``tone-equalizer``, ``detail-equalizer``, ``colormap``, ``false-color``, ``split-toning``, ``pixel-sort``, ``polar``, ``kaleidoscope``, ``frosted-glass``, ``local-contrast``, ``posterize``, ``gradient-map``, ``film-grain``, ``levels``, ``auto-color-balance``, ``channel-mixer``, ``curve``, ``lens-correction``
   * - Otras salidas
     - ``ela`` (mapa de Error Level Analysis como PNG), ``video-frame`` (un fotograma de un vídeo, ``--frame-index``), ``puppet-from-png`` (un rig ``.puppet``, ``--cell-size``)
   * - Informes: un resultado por imagen, ``--json`` para salida legible por máquina
     - ``metadata``, ``xmp``, ``gps``, ``dominant-colors``, ``sharpness``, ``statistics``, ``histogram``, ``ocr``, ``puppet-inspect``, ``puppet-validate``
   * - Se ejecutan una vez e imprimen JSON
     - ``list-images FOLDER``, ``search FOLDER --query "..."``, ``similar FOLDER``, ``collection-stats FOLDER``, ``reverse-geocode --latitude .. --longitude ..``, ``puppet-schema --name ..``

Cada parámetro MCP se convierte en una opción con el mismo valor predeterminado y los mismos valores permitidos: ``zone_gains`` es ``--zone-gains``, un parámetro sí/no es ``--grayscale`` / ``--no-grayscale``, y un color o una fila de matriz recibe sus valores en orden (``--red 1 0 0``). ``py -m Imervue.cli <subcommand> --help`` los enumera::

   py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
   py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
   py -m Imervue.cli histogram a.jpg --json
   py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"

``pipeline FILE INPUTS…`` ejecuta una cadena ordenada de operaciones sobre cada entrada y escribe
un PNG por entrada: ``<stem>_pipeline.png`` junto al original, o ``<stem>.png`` en ``--out``.
``FILE`` es JSON en UTF-8 (se admite una marca de orden de bytes) que contiene una lista de pasos o
un objeto ``{"pipeline": [...]}``. Cada paso es un objeto con un ``"op"`` que nombra la operación
más los parámetros de esa operación; un parámetro omitido toma su valor predeterminado, y las
claves que una operación no conoce se ignoran. Un pipeline tiene como máximo 50 pasos; uno vacío
escribe cada entrada tal como se decodificó. El archivo se comprueba antes de leer ninguna imagen:
un archivo que no se puede leer ni analizar imprime ``error: …``, y más de 50 pasos, un paso sin
nombre ``"op"`` o una operación desconocida imprimen una línea ``pipeline error: step N: …`` por
problema; en ambos casos el comando termina con el código 2 y no escribe nada. Un parámetro del
tipo incorrecto (``null``, texto donde va un número) hace fallar esa imagen, lo que se informa, y
el código de salida es 1.

.. list-table::
   :header-rows: 1
   :widths: 14 44 42

   * - Op
     - Parámetros (valores predeterminados)
     - Efecto
   * - ``dehaze``
     - ``strength`` (``1.0``; limitado a 0 – 1)
     - Eliminación de neblina por dark channel prior; ``0`` deja la imagen sin cambios
   * - ``clahe``
     - ``clip`` (``2.0``; al menos 1), ``tiles`` (``8``; al menos 1)
     - Ecualización adaptativa con contraste limitado de la luminancia sobre una cuadrícula de
       ``tiles`` × ``tiles``
   * - ``dither``
     - ``levels`` (``2``; limitado a 2 – 8)
     - Tramado Bayer ordenado 4×4 a ``levels`` valores por canal; el alfa se conserva
   * - ``distort``
     - ``mode`` (``"swirl"``: ``swirl`` / ``pinch`` / ``ripple``), ``strength`` (``0.5``;
       limitado a -1 – 1)
     - Deformación geométrica alrededor del centro; para ``pinch`` una intensidad positiva abomba
       y una negativa pellizca
   * - ``clarity``
     - ``amount`` (``0.5``; -1 – 1, negativo suaviza)
     - Contraste local de radio amplio, ponderado hacia los medios tonos
   * - ``texture``
     - ``amount`` (``0.5``; -1 – 1, negativo suaviza)
     - Contraste local de radio pequeño, de detalle fino
   * - ``grayscale``
     - ninguno
     - Luma (0.299 R + 0.587 G + 0.114 B) en los tres canales; el alfa se conserva
   * - ``invert``
     - ninguno
     - Invierte R, G y B; el alfa se conserva
   * - ``watermark``
     - ``text`` (``""``: sin marca de agua), ``corner`` (``"bottom-right"``: ``top-left`` /
       ``top-right`` / ``bottom-left`` / ``bottom-right`` / ``center``; cualquier otro valor cuenta
       como ``bottom-right``), ``opacity`` (``0.6``; limitado a 0 – 1)
     - Texto blanco con sombra paralela, de un tamaño del 3,5 % del lado largo; ``--font-fraction``,
       ``--color`` y ``--no-shadow`` del subcomando ``watermark`` no tienen parámetro de paso

Por ejemplo, ``look.json``::

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
   * - ``puppet_validate`` / ``puppet_schema``
     - Comprueba un ``.puppet`` frente al formato v1 (JSON Schemas, reglas del cargador,
       comprobaciones del rig); devuelve uno de sus cuatro JSON Schemas publicados.
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
(campos de revisiones posteriores de MCP; el handshake informa ``2025-03-26``), de modo que
los clientes consumen payloads tipados sin volver a
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
         "command": "py",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

``py`` es el lanzador de Python de Windows; en macOS o Linux use ``python3`` o el intérprete del
entorno en el que esté instalado Imervue. Abrir cualquier subdirectorio del repositorio en Claude
Code auto-descubre este servidor.
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

El servidor lee mensajes JSON-RPC 2.0 delimitados por saltos de línea en stdin y escribe las
respuestas y notificaciones en stdout, una línea UTF-8 cada una. Responde a ``initialize`` con la
versión de protocolo ``2025-03-26`` sea cual sea la versión que pida el cliente. Las solicitudes
se atienden de una en una; un lote (un array JSON) se rechaza con ``-32600``.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Método
     - Función
   * - ``initialize``
     - Handshake. Devuelve ``protocolVersion`` ``2025-03-26``, ``serverInfo`` (``imervue``
       ``1.0.0``) y las capacidades ``tools`` y ``prompts`` (``listChanged: false``),
       ``resources`` (``subscribe: true``, ``listChanged: true``), ``completions`` y ``logging``.
   * - ``ping``
     - Devuelve un resultado vacío.
   * - ``tools/list``
     - Las 58 herramientas en una sola página, cada una con ``inputSchema``, ``outputSchema`` y
       ``annotations`` (``readOnlyHint`` / ``destructiveHint`` / ``idempotentHint`` /
       ``openWorldHint``).
   * - ``tools/call``
     - Ejecuta ``{"name", "arguments"}``. El resultado es un bloque de contenido ``text`` con el
       valor de retorno codificado en JSON, más ``structuredContent`` cuando es un objeto. Una
       herramienta que lanza una excepción, o argumentos que no encajan con sus parámetros, dan
       ``isError: true`` y un texto ``Error: …`` en lugar de un error de protocolo; un nombre de
       herramienta desconocido es ``-32602``.
   * - ``prompts/list``
     - Los cuatro prompts con sus argumentos.
   * - ``prompts/get``
     - Construye los mensajes de ``{"name", "arguments"}``; ``caption_image`` y
       ``analyze_composition`` incrustan una miniatura PNG como mensaje de imagen. Un prompt
       desconocido o un ``path`` ausente es ``-32602``.
   * - ``completion/complete``
     - Valores que coinciden por prefijo para un argumento ``ref/prompt``: ``style`` de
       ``suggest_edits`` (general, portrait, landscape, product, street, food, macro) y ``focus``
       de ``analyze_composition`` (all, framing, balance, subject, leading_lines). Cualquier otro
       argumento recibe una lista vacía.
   * - ``resources/list``
     - Las imágenes situadas directamente en la carpeta que indica ``IMERVUE_MCP_ROOT`` (sin los
       archivos ocultos ni los SVG), 100 por página con un ``nextCursor``; vacía cuando la variable
       no está definida.
   * - ``resources/templates/list``
     - Las dos plantillas de URI de la tabla siguiente.
   * - ``resources/read``
     - Lee una URI ``imervue://image/…`` (véase más abajo).
   * - ``resources/subscribe`` / ``resources/unsubscribe``
     - Añade o quita una URI del conjunto que recibe ``notifications/resources/updated``.
   * - ``logging/setLevel``
     - Establece el nivel más bajo (``debug``, ``info``, ``notice``, ``warning``, ``error``,
       ``critical``, ``alert``, ``emergency``; ``info`` al inicio) que se envía como
       ``notifications/message``; cualquier otro valor es ``-32602``.
   * - ``notifications/*`` del cliente
     - Se aceptan sin respuesta (``notifications/initialized``, ``notifications/cancelled``, …);
       una cancelación no detiene una herramienta en ejecución.
   * - ``notifications/progress`` (enviada)
     - ``{progressToken, progress, total, message}`` mientras se ejecuta ``find_similar`` o
       ``build_collage``, cuando la solicitud ``tools/call`` incluía
       ``params._meta.progressToken`` (una cadena o un entero); ``progress`` solo aumenta.
   * - ``notifications/resources/updated`` (enviada)
     - ``{uri}`` cuando cambia un archivo de ``IMERVUE_MCP_ROOT`` y su URI de miniatura está
       suscrita.
   * - ``notifications/resources/list_changed`` (enviada)
     - Ante cualquier cambio en ``IMERVUE_MCP_ROOT`` (vigilada con watchdog, no de forma
       recursiva), haya suscripción o no.
   * - ``notifications/message`` (enviada)
     - Entradas de registro de nivel igual o superior al de ``logging/setLevel``, enviadas mediante
       ``MCPServer.emit_log``. Las herramientas integradas no lo llaman, así que el servidor de
       serie no envía ninguna.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - URI
     - Devuelve
   * - ``imervue://image/{path}``
     - Una miniatura PNG de la imagen — derecha, encajada en 256 px — como ``blob`` en base64 con
       ``mimeType`` ``image/png``. ``resources/list`` devuelve URIs de esta forma.
   * - ``imervue://image/{path}/metadata``
     - El resultado de ``read_image_metadata`` (dimensiones, formato, EXIF, XMP) como ``text`` JSON
       con ``mimeType`` ``application/json``.

``{path}`` es la ruta de archivo de la imagen codificada por completo con porcentajes, separadores
y los dos puntos de la unidad incluidos (``C:\photos\a.jpg`` es
``imervue://image/C%3A%5Cphotos%5Ca.jpg``). Una lectura resuelve la ruta directamente, así que
funciona con cualquier archivo, no solo con los que están bajo ``IMERVUE_MCP_ROOT``; una ruta con
un segmento ``..`` es ``-32602``, un archivo inexistente ``-32002`` y una URI con otro esquema
``-32602``.

Los errores usan los códigos JSON-RPC ``-32700`` (una línea que no es JSON), ``-32600`` (no es un
objeto de solicitud, o falta ``method``), ``-32601`` (método desconocido), ``-32602`` (parámetros
incorrectos, herramienta o prompt desconocidos, nivel de registro o cursor no válidos, URI de
recurso no admitida), ``-32002`` (archivo de recurso no encontrado) y ``-32603`` (error interno).

La implementación vive en ``Imervue/mcp_server/``:

* ``server.py`` — el despachador JSON-RPC (``MCPServer``), el bucle stdio (``run``) y el
  vigilante de ``IMERVUE_MCP_ROOT``.
* ``tools.py`` — la cara pública del conjunto de herramientas: reexporta todos los manejadores y
  registra las herramientas por defecto (``register_default_tools``).
* ``tools_read.py`` / ``tools_edit.py`` — los manejadores de las herramientas (listado, metadatos
  y análisis; ediciones escritas en un destino), con ayudantes compartidos en ``tool_support.py``.
* ``tool_defs_read.py`` / ``tool_defs_edit.py`` — el nombre, la descripción, el esquema de
  entrada y el manejador de cada herramienta, en el orden de ``tools/list``.
* ``tool_schemas.py`` — el ``outputSchema`` y las ``annotations`` de cada herramienta.
* ``prompts.py`` / ``completion.py`` — los cuatro prompts y las sugerencias de
  ``completion/complete``.
* ``resources.py`` — los recursos ``imervue://image/``.
* ``progress.py`` / ``notifications.py`` / ``logging.py`` — el informe de progreso, el escritor de
  stdout con bloqueo y las suscripciones a recursos, y el filtrado por nivel de registro.
* ``__main__.py`` — punto de entrada ``python -m Imervue.mcp_server``.

Se pueden registrar herramientas personalizadas construyendo :class:`MCPServer`, llamando a
:meth:`MCPServer.register` (nombre, descripción, esquema de entrada, manejador, y opcionalmente
esquema de salida y anotaciones; un nombre duplicado lanza ``ValueError``; un manejador con un
parámetro ``progress`` recibe un informador de progreso) y pasando cada mensaje a
:meth:`MCPServer.handle_message`, que devuelve la respuesta o ``None`` para una notificación.
:func:`run` siempre construye su propio servidor con las herramientas por defecto, así que un
conjunto personalizado necesita su propio bucle; asigne a ``server.notifier`` un ``Notifier`` sobre
el flujo de salida para que se envíen las notificaciones.
