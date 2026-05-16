Guía del Usuario de Imervue
===========================

Una estación de trabajo de imágenes con aceleración GPU que incluye **cuatro pestañas
de nivel superior**. La mayor parte de esta guía está organizada en torno a esas cuatro
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

Las secciones *Primeros pasos*, *Referencia*, *Sistema de plugins* y *Servidor MCP* que
siguen son transversales y se aplican a las cuatro pestañas.

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

- **Estándar**: PNG, JPEG, BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 (Canon), NEF (Nikon), ARW (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus)

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
   * - Encuadrar con el teclado
     - Teclas de flecha; mantenga ``Shift`` para un movimiento fino

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

Modo Deep Zoom
^^^^^^^^^^^^^^

Haga clic en una miniatura para entrar en el modo Deep Zoom y ver imágenes individuales en
alta calidad.

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

En el modo Deep Zoom puede valorar imágenes rápidamente:

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
   * - Ordenar por nombre
     - ``Sort`` > ``By Name``
   * - Ordenar por fecha de modificación
     - ``Sort`` > ``By Modified Date``
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
de edición. También puede pulsar ``E`` o clic derecho > ``Modify`` en el modo Deep Zoom.

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
   * - Sombras
     - Levanta o aplasta el detalle en zonas tonales oscuras
   * - Medios tonos
     - Ajusta el rango tonal medio sin afectar a negros y blancos
   * - Luces
     - Recupera luces quemadas o intensifica las zonas brillantes
   * - Intensidad
     - Refuerzo consciente de la saturación — protege los tonos de piel y los colores ya saturados

Estos ajustes son **no destructivos**. Cada deslizador escribe en una receta de edición
almacenada por imagen; pulse ``Reset`` en cualquier momento para restaurar el original, o
``Ctrl + Z`` para retroceder por los cambios individuales. Las recetas sobreviven a los
reinicios y se pueden exportar / sincronizar mediante el flujo de archivos secundarios XMP
descrito en la sección Metadatos.

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
herramientas de manga, fotogramas de animación e importación/exportación de PSD. Cambie a
ella desde la barra de pestañas o pulse ``E`` desde el modo Deep Zoom para enviar la imagen
actual directamente a una nueva pestaña de Paint.

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

Los docks del lado derecho (Color, Brush, Layer, Navigator, biblioteca de Material, History,
Swatch, Reference, Histogram, Animation) están organizados como pestañas en una sola columna,
de modo que el lienzo mantiene la altura visible completa. Arrastre el título de cualquier dock
para reorganizarlo o flotar un panel, después guarde el resultado mediante
``Settings`` > ``Workspace Layouts…``.

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
sin configuración por rig. Nueve movimientos en bucle se incluyen en el bundle —
bucles idle de Cubism convertidos por el autor más bucles de gestos de referencia en
los grupos ``Idle`` y ``TapHead``.

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
3. Barra de herramientas → **File > Examples > March 7Th** (o el desplegable
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
     - Superficies de streaming en vivo — consulte *Streaming en vivo a OBS* más arriba
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
rellena el área fuera del personaje con **magenta `#FF00FF`** como croma. Elimínelo en OBS
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

La pestaña 5 — **Desktop Pet** — ejecuta cualquier rig ``.puppet`` como una superposición
sin marco, transparente y siempre encima del escritorio. La pestaña dentro de la aplicación
es el panel de control; el personaje real vive en una ventana de nivel superior
independiente que comparte el runtime de Puppet (misma :class:`PuppetCanvas`, misma tubería
de parámetros / movimientos / físicas, mismos drivers de entrada en vivo).

Comportamiento de la ventana
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Característica
     - Notas
   * - Superposición sin marco
     - Sin chrome de ventana, sin entrada en la barra de tareas; se sitúa encima de cualquier
       otra ventana mediante ``Qt.WindowStaysOnTopHint``.
   * - Fondo transparente
     - ``WA_TranslucentBackground`` + un formato de superficie GL consciente del alfa
       + ``glClearColor(0,0,0,0)`` — cada píxel que la marioneta no dibuja deja ver el
       escritorio por detrás.
   * - Arrastrar para mover
     - Arrastre con clic izquierdo sobre el personaje para reubicarlo. Suelte dentro del
       umbral de ajuste configurable (24 px por defecto) de un borde de la pantalla para
       **acoplarlo** contra ese borde. Los arrastres rápidos que se pasan se ajustan de
       vuelta hacia dentro, de modo que la mascota nunca se pierde fuera de pantalla.
   * - Conmutador clic-pasante
     - Modo opcional ``Qt.WindowTransparentForInput`` — cada clic pasa a través hacia el
       escritorio / aplicación detrás de la mascota.
   * - Anclar posición
     - Congela la posición de la mascota con un clic para que los arrastres accidentales no
       puedan moverla.
   * - Siempre debajo
     - Conmuta de ``WindowStaysOnTopHint`` a ``WindowStaysOnBottomHint`` para que la mascota
       quede detrás de todas las ventanas como un widget de escritorio (emparejado con
       ``WindowDoesNotAcceptFocus``).
   * - Ocultar en pantalla completa
     - Un sondeo a 1 Hz vigila la ventana activa mediante la API Win32 ``GetWindowRect``
       (Windows) y oculta la mascota automáticamente mientras otra aplicación mantiene
       pantalla completa en el monitor de la mascota.
   * - Pausar al ocultar
     - El tick de pintado de 33 ms se detiene mientras la superposición está oculta, de
       modo que una mascota dormida consume cero CPU. Se reanuda en ``showEvent``.
   * - Presets de tamaño
     - Pequeño (200×300) / mediano (320×480) / grande (480×720); anclados al centro para
       que la mascota no salte por la pantalla al redimensionarla.
   * - Deslizador de opacidad
     - Opacidad a nivel de ventana 0.1 – 1.0 mediante ``setWindowOpacity`` — el composite
       de ``WA_TranslucentBackground`` más el alfa por ventana da un fundido suave en lugar
       de simplemente atenuar los píxeles de la marioneta.
   * - Persistencia de posición
     - El par ``(x, y)`` posterior al ajuste tras cada suelta de arrastre se escribe en
       ``user_setting_dict["desktop_pet"]["position"]``. En el próximo arranque la mascota
       vuelve a esa posición de pantalla; la desconexión multimonitor recae en la esquina
       inferior derecha de la pantalla primaria.

Interacción
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Acción
     - Comportamiento
   * - **Clic izquierdo sobre el cuerpo**
     - Mapea el clic a coordenadas del lienzo de marioneta mediante la matriz inversa de
       paneo / zoom, ejecuta el :func:`hit_test` existente contra las entradas
       :class:`HitArea` del documento, y reproduce el movimiento enlazado si alguno cubre
       el drawable golpeado. Recae en un saludo round-robin en el bocadillo cuando nada
       coincide.
   * - **Clic derecho en cualquier lugar**
     - Abre un menú contextual con: Ocultar mascota, submenú **Live drivers** (6
       conmutadores marcables), submenú **Play motion** (poblado desde
       ``document.motions``), submenú **Apply expression** (poblado desde
       ``document.expressions``), Bloquear posición, Clic-pasante, Siempre debajo,
       Ocultar en pantalla completa, conmutador del bocadillo y un submenú **Size**.
   * - **Bocadillo de diálogo**
     - Widget sin marco / transparente / siempre encima, con cuerpo redondeado + cola.
       Aparece sobre la mascota al hacer clic, se mantiene durante ~4 s y luego se desvanece
       en 400 ms. Se ancla a la geometría de la mascota, de modo que arrastrarla lleva
       consigo el bocadillo.
   * - **Bandeja del sistema**
     - Mostrar / Ocultar (marcable), Clic-pasante, Open puppet…, Ocultar mascota. El clic
       izquierdo conmuta la visibilidad; el clic derecho abre el menú. Refleja el estado de
       marcado del espacio de trabajo mediante ``sync_visibility`` / ``sync_click_through``.

Drivers en vivo (lazy-init)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cada driver se instancia al activarse por primera vez, de modo que una mascota dormida
consume cero coste de timer / hilo:

* **Auto idle** — respiración + deriva sobre parámetros estándar
  (``ParamBreath`` …) mediante :class:`IdleDriver`.
* **Idle motions** — ciclo aleatorio a través de los movimientos del grupo ``Idle``
  mediante :class:`IdleMotionCycler` + el :class:`MotionPlayer` incluido.
* **Auto-blink** — ciclo coseno cerrar-abrir cada ~4.5 s sobre
  ``ParamEyeLOpen`` / ``ParamEyeROpen`` mediante
  ``InputEngine.set_blink_enabled``.
* **Drag-track head** — offset del cursor → ``ParamAngleX/Y`` +
  ``ParamEyeBallX/Y`` mediante ``InputEngine.set_drag_enabled``.
* **Mic lip-sync** — RMS del micrófono → ``ParamMouthOpenY`` mediante
  ``InputEngine.set_lipsync_enabled`` (requiere ``sounddevice``).
* **Webcam tracking** — MediaPipe FaceLandmarker → cabeza + ojos +
  boca mediante :class:`WebcamTracker` (requiere ``opencv-python`` +
  ``mediapipe``).

Persistencia
^^^^^^^^^^^^

:mod:`Imervue.desktop_pet.settings` se coloca como capa sobre
``user_setting_dict["desktop_pet"]`` con:

* Valores por defecto para cada clave + recorte de rango en la carga, de modo que un
  archivo de configuración corrupto no pueda hacer fallar el arranque.
* Fusión de un nivel de profundidad — los archivos de configuración antiguos a los que
  les faltan claves nuevas siguen produciendo un dict de estado completo.
* Compatibilidad hacia adelante para el sub-dict ``drivers`` — las claves de drivers
  desconocidas hacen ida y vuelta sin tocarse, de modo que una versión futura que añada
  un nuevo driver pueda leer los archivos existentes sin problema.

Cada superficie ajustable por el usuario (posición, tamaño, opacidad, clic-pasante, anclaje,
siempre debajo, ocultar en pantalla completa, bocadillo, umbral de ajuste, cada driver,
último rig cargado, mostrar al arrancar) hace ida y vuelta a través de este helper, de
modo que la mascota regresa al mismo estado en el próximo arranque.

Implementación
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Archivo
     - Rol
   * - ``Imervue/desktop_pet/pet_window.py``
     - Superposición de nivel superior — sin marco / siempre encima /
       ``WA_TranslucentBackground``. Aloja
       ``PuppetCanvas(pet_mode=True)``, gestiona arrastrar para mover, detección de
       impacto, menú contextual, integración del bocadillo, cableado del detector de
       pantalla completa, drivers y escritura-pasante de persistencia.
   * - ``Imervue/desktop_pet/edge_snap.py``
     - Matemáticas de ajuste en Python puro (sin Qt) para acoplamiento a esquinas / bordes
       y recorte de sobrepaso, comprobables con tests unitarios.
   * - ``Imervue/desktop_pet/settings.py``
     - Helper de persistencia — cargar / guardar / actualizar / recortar.
   * - ``Imervue/desktop_pet/speech_bubble.py``
     - Superposición de bocadillo redondeado sin marco con posicionamiento anclado a
       rectángulo + animación de fundido.
   * - ``Imervue/desktop_pet/fullscreen_detector.py``
     - Bucle de sondeo a 1 Hz que lee el rect de la ventana en primer plano (ctypes Win32
       en Windows; fallback no-op en el resto) y emite ``state_changed(bool)``.
   * - ``Imervue/desktop_pet/pet_workspace.py``
     - La pestaña del panel de control. Crea la superposición de forma perezosa, expone
       cada conmutador / deslizador / combo como checkbox o spinbox, persiste el último
       rig cargado + el comportamiento de mostrar al arrancar.
   * - ``Imervue/desktop_pet/tray_icon.py``
     - Helper de bandeja del sistema — instancia única por sesión, sincroniza con el
       estado de marcado del espacio de trabajo.

``PuppetCanvas.__init__(pet_mode=True)`` cortocircuita el fondo damero de transparencia y
la superposición de selección del editor; el resto de la ruta de renderizado (VBOs de
malla, reproductor de movimientos, físicas, expresiones, grupos de poses) es idéntico al
de la pestaña Puppet.

Cada cadena de UI se enruta a través de
``language_wrapper.language_word_dict.get(...)`` con claves definidas en los cinco
paquetes de idioma base (English, 繁體中文, 简体中文, 日本語, 한국어).

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

Clic derecho en una imagen > ``Export / Save As``.

- Elija el formato: PNG, JPEG, WebP, BMP, TIFF
- Ajuste la calidad (para formatos con pérdida)
- Vista previa del tamaño estimado del archivo
- Elija una ubicación de guardado

Presets de exportación
^^^^^^^^^^^^^^^^^^^^^^

Para los destinos de entrega comunes que no quiere reajustar cada vez, use
``File`` > ``Export with Preset``. Un clic aplica el pipeline correcto de redimensionado,
formato y calidad:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Preset
     - Pipeline
   * - **Web 1600**
     - Ajusta el lado largo a 1600 px, JPEG calidad 85, sRGB; para subidas a blogs / foros donde la calidad visual importa más que el recuento de píxeles.
   * - **Print 300 dpi**
     - TIFF a resolución completa / JPEG de alta calidad con metadatos de 300 dpi, salida con gestión de color para laboratorios y imprentas.
   * - **Instagram 1080**
     - Recorte cuadrado (1080 × 1080) o vertical (1080 × 1350) con la relación de aspecto original preservada en el interior, JPEG calidad 90.

Los presets se componen con la superposición de marca de agua (más abajo) — habilite la
marca de agua una vez y todas las salidas con preset la incluirán.

Superposición de marca de agua
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``File`` > ``Watermark…`` abre un configurador de superposición no destructiva. Los ajustes
se aplican sólo en la exportación — los píxeles originales en el disco nunca se tocan.

- **Modo**: texto o imagen. Las marcas de agua de imagen admiten PNG con alfa.
- **Posición**: cuadrícula de 9 anclas (esquinas, bordes, centro).
- **Opacidad**: 0 – 100 %.
- **Escala**: porcentaje del lado largo exportado; la marca de agua se reescala automáticamente
  conforme cambia el tamaño para distintos presets.

Exportación por lotes
^^^^^^^^^^^^^^^^^^^^^

Seleccione varias imágenes, después clic derecho > ``Batch Export``.

- Conversión uniforme de formato
- Establece el ancho / alto máximo (escalado de aspecto automático)
- Control de calidad
- Barra de progreso en tiempo real

Crear GIF / Vídeo
^^^^^^^^^^^^^^^^^

Seleccione varias imágenes, después clic derecho > ``Create GIF / Video``.

- Salida GIF y MP4
- Arrastrar para reordenar fotogramas
- Establecer fotogramas por segundo (FPS)
- Dimensiones personalizadas
- Opción de bucle

----

Reproducción de animaciones
---------------------------

Al abrir archivos GIF, APNG o WebP animado, la animación se reproduce automáticamente.

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
desde allí.

----

Operaciones por lotes
---------------------

En el modo miniaturas, seleccione varias imágenes después clic derecho:

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
   * - Añadir a etiqueta
     - Aplica la misma etiqueta a todas las imágenes seleccionadas
   * - Añadir a álbum
     - Coloca todas las imágenes seleccionadas en un álbum

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
     - Encuadre en modo miniaturas
   * - ``Shift + Arrow``
     - Encuadre fino
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
   * - ``Home``
     - Restablecer zoom

Edición
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Acción
   * - ``E``
     - Abrir la pestaña Modify
   * - ``R``
     - Rotar en sentido horario
   * - ``Shift + R``
     - Rotar en sentido antihorario
   * - ``Ctrl + Z``
     - Deshacer
   * - ``Ctrl + Shift + Z``
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
   * - ``S``
     - Presentación

Animación
^^^^^^^^^

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
una raíz está indexada puede consultarla por extensión, ancho/alto mínimo, rango de tamaño o
subcadena de nombre y soltar los resultados en el visor como un álbum virtual.

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

``Extra Tools`` > ``Semantic Search`` le permite escribir una frase en lenguaje natural (por
ejemplo *"golden retriever en la nieve"* o *"calle de neón por la noche"*) y devuelve imágenes
clasificadas de la biblioteca indexada. Cada imagen se incrusta con un encoder visual/lingüístico
CLIP y se almacena junto a su ruta; una consulta de texto se incrusta en el mismo espacio
vectorial y se compara por similitud coseno.

Las incrustaciones se almacenan en caché en ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows)
o ``~/.cache/imervue/clip_cache.npz`` (POSIX) como un único archivo ``.npz`` compacto, para
que el siguiente lanzamiento omita la re-codificación. Sólo las rutas que ha escaneado son
consultables — use ``Scan Folder…`` dentro del diálogo para extender el índice.

.. note::
   Semantic Search requiere los paquetes opcionales ``open_clip_torch`` y ``torch``. Si no
   están instalados, la entrada del menú explica qué falta y otras funciones siguen
   funcionando.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` aplica etiquetas heurísticas
bajo ``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` / ``portrait``).
Si ``onnxruntime`` y un modelo CLIP en ``models/clip_vit_b32.onnx`` están disponibles,
también añade etiquetas de contenido basadas en CLIP. Se ejecuta en un hilo de trabajo con
una barra de progreso en vivo.

Etiquetas jerárquicas
^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gestiona etiquetas con
estructura de árbol como ``animal/cat/british``. Seleccione una etiqueta para ver todas las
imágenes bajo esa rama (descendientes incluidos). Etiquete o desetiquete la selección actual
con un clic. Las etiquetas jerárquicas viven en el índice de la biblioteca y son
complementarias al sistema de etiquetas planas del menú contextual.

Renombrado por lotes con tokens
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` abre una tabla con vista previa en vivo
donde escribe una plantilla como ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` y ve
exactamente cómo se renombrará cada archivo. Los conflictos se resaltan para que nada se
sobrescriba. Tokens admitidos: ``{name} {ext} {counter[:NN]} {date[:fmt]} {width} {height}
{wxh} {size_kb} {camera} {year} {month} {day} {hour} {minute}``.

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

- **Import XMP for current image** — extrae valoración / título / palabras clave /
  etiqueta de color del archivo secundario a la base de datos interna.
- **Export XMP for current image** — escribe la valoración / título / palabras clave /
  etiqueta de color actuales en un archivo secundario junto a la imagen.
- **Importar / exportar por lotes** — aplica la misma operación a la selección activa
  o a toda la carpeta.

El parseo XML usa ``defusedxml`` para que los archivos secundarios mal formados o maliciosos
no puedan disparar ataques XXE / billion-laughs. Si ``defusedxml`` no está instalado, las
entradas del menú XMP se ocultan y no se escriben archivos secundarios.

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
cualquier archivo Adobe ``.cube`` (1D o 3D, hasta 64³). La LUT se parsea con un ``lru_cache``
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

Geoetiqueta GPS
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lee cualquier etiqueta GPS existente
de EXIF y le permite editar o establecer nuevas coordenadas en grados decimales. Requiere
``piexif`` instalado; escribe en JPEG in situ.

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
     - Dimensiones, formato, etiquetas EXIF y campos del archivo secundario XMP para una
       imagen. Los datos que falten se reportan como el valor vacío apropiado en lugar
       de lanzar una excepción.
   * - ``read_xmp_tags``
     - Ruta rápida que sólo lee el archivo secundario XMP — valoración, etiqueta de color,
       palabras clave, título, descripción.
   * - ``convert_format``
     - Convierte una imagen a otro formato. El formato de destino se infiere del sufijo
       de destino (``png`` / ``jpg`` / ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``). El parámetro
       opcional ``quality`` (1–100) se aplica a JPEG/WebP.
   * - ``puppet_from_png``
     - Construye un rig ``.puppet`` desde un PNG usando el auto-mesh del plugin puppet.
       Siembra el catálogo de parámetros estándar de Cubism para que el rig sea
       inmediatamente controlable.
   * - ``puppet_inspect``
     - Abre un archivo ``.puppet`` y devuelve un inventario estructurado: drawables,
       deformers, parameters, motions, expressions, hit areas, parts, mezclas de parámetros
       y rigs físicos.

Todas las herramientas devuelven payloads serializados como JSON en el sobre
``content`` / ``text`` de MCP; los payloads estructurados pueden parsearse de vuelta desde
el campo ``text`` en el lado del cliente.

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
