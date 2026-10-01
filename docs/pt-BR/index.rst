Guia do Usuário do Imervue
==========================

Uma estação de trabalho de imagens acelerada por GPU que oferece **cinco abas principais**.
A maior parte deste guia está organizada em torno dessas cinco seções.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Aba
     - O que faz
   * - **Imervue**
     - Navega, visualiza, organiza, pesquisa e processa em lote sua biblioteca de imagens.
       Consulte *Abrindo Imagens*, *Navegando pelas Imagens* e *Organizando Imagens*.
   * - **Modify**
     - Pipeline de revelação não destrutiva — sliders, curvas, LUTs, máscaras,
       retoque, multi-imagem. Consulte *Editando Imagens (Aba Modify)*.
   * - **Paint**
     - Estúdio raster de pintura completo com pincéis, camadas, animação,
       ferramentas para mangá e I/O de PSD. Consulte *Espaço de Trabalho Paint (Aba Paint)*.
   * - **Puppet**
     - Animador de fantoches 2D com rig construído do zero — meshes, deformadores, parâmetros,
       movimentos, física. Consulte *Espaço de Trabalho Puppet (Aba Puppet)*.
   * - **Desktop Pet**
     - Sobreposição sem moldura, transparente e sempre no topo que roda os
       mesmos rigs ``.puppet`` na sua área de trabalho com drivers ao vivo (idle /
       blink / mic / webcam / drag-track). Consulte *Espaço de Trabalho Desktop Pet (Aba Desktop Pet)*.

As seções *Primeiros Passos*, *Referência de Atalhos de Teclado*, *Referência do Menu Extra
Tools*, *Sistema de Plugins*, *Uso na Linha de Comando* e *Servidor MCP* são transversais —
aplicam-se a todas as cinco abas.

**Puppet** e **Desktop Pet** são opcionais: desligue qualquer um deles em ``File`` > ``Preferences`` > **Optional tabs** e, a partir da próxima inicialização, a aba não é adicionada e o código dela não é carregado, então o Imervue inicia mais rápido e usa menos memória. Os dois vêm ligados; cada um é montado na primeira vez que você abre a aba, e a aba Desktop Pet já na inicialização quando o pet está configurado para aparecer ao iniciar.

.. contents:: Sumário
   :depth: 2
   :local:

----

Primeiros Passos
----------------

Ao abrir o Imervue, você verá três áreas:

::

   +------------+----------------------+----------+
   |  Árvore    |                      |   EXIF   |
   |  de        |   Visualizador       |  Barra   |
   |  Pastas    |   de Imagens         | lateral  |
   +------------+----------------------+----------+

- **Esquerda**: Árvore de pastas. Clique em uma pasta para navegar pelas imagens internas.
- **Centro**: Área de exibição de imagens. Mostra todas as imagens em uma grade de miniaturas.
- **Direita**: Barra lateral EXIF, recolhida em uma faixa fina ao iniciar: clique nela para abri-la. Mostra as informações de captura da imagem aberta.

O Imervue grava um log de cada sessão em ``imervue.log`` ao lado do programa (em ``%LOCALAPPDATA%\Imervue``, ou em ``~/.cache/imervue`` fora do Windows, quando essa pasta é somente leitura). O log da sessão anterior é mantido como ``imervue.previous.log``, então, depois de um travamento, o log que o explica continua lá quando o Imervue volta a rodar — anexe os dois ao relatar um problema.

----

Abrindo Imagens
---------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Método
     - Como
   * - Abrir Pasta
     - ``Arquivo`` > ``Abrir Pasta``, depois escolha um diretório
   * - Abrir Imagem Individual
     - ``Arquivo`` > ``Abrir Arquivo``, depois escolha um arquivo
   * - Arrastar e Soltar
     - Arraste uma imagem ou pasta diretamente para a janela
   * - Abrir pelo Explorador
     - Clique com o botão direito em uma imagem > ``Open with Imervue`` (requer associação de arquivos)
   * - Arquivos Recentes
     - ``Arquivo`` > ``Recentes`` > Pastas Recentes / Imagens Recentes, para reabrir uma pasta ou imagem

Formatos Suportados
^^^^^^^^^^^^^^^^^^^

- **Padrão**: PNG, JPEG (.jpg, .jpeg, .jpe, .jfif, .jif), BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 / CR3 / CRW (Canon), NEF / NRW (Nikon), ARW / SRF / SR2 (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus / OM System), RW2 (Panasonic), RWL (Leica), PEF (Pentax), SRW (Samsung), 3FR (Hasselblad), IIQ (Phase One), MEF (Mamiya), MOS (Leaf), ERF (Epson), MRW (Minolta), KDC / DCR (Kodak)
- **Modernos**: AVIF (embutido); HEIC / HEIF com o opcional ``pillow-heif``; JPEG XL com o opcional ``pillow-jxl-plugin``
- **Outros**: ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (a imagem mesclada) — para visualização; girar um no lugar e outras regravações são recusados, então uma edição sai por Salvar como / Exportar

----

Navegando pelas Imagens
-----------------------

Modo de Grade de Miniaturas
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Depois de abrir uma pasta, todas as imagens são exibidas como miniaturas.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Método
   * - Rolar
     - Roda do mouse
   * - Deslocar (pan)
     - Mantenha o botão do meio do mouse pressionado e arraste
   * - Entrar em visualização em tamanho real
     - Clique com o botão esquerdo em qualquer miniatura
   * - Alterar tamanho da miniatura
     - Menu ``Tamanho da Miniatura`` > escolha 128 / 256 / 512 / 1024
   * - Densidade das miniaturas
     - ``Tamanho da Miniatura`` > ``Densidade da Miniatura`` > Compacta / Padrão / Espaçada
   * - Pop-up de pré-visualização ao passar o mouse
     - Mantenha o cursor sobre uma miniatura por 500 ms para ver uma pré-visualização ampliada
   * - Selecionar várias imagens
     - Clique com o botão esquerdo e arraste para desenhar um retângulo de seleção
   * - Mover entre miniaturas com o teclado
     - As teclas de seta movem um anel de foco e rolam até ele; ``Enter`` abre a imagem

Cada miniatura mostra emblemas de status: uma faixa colorida na borda esquerda (rótulo de cor),
um coração no canto superior esquerdo (favorito), uma estrela no canto superior direito (marcador) e
estrelas de avaliação no canto inferior esquerdo. Um indicador de carregamento é desenhado para
miniaturas que ainda estão sendo carregadas.

Modo Lista (Detalhes)
^^^^^^^^^^^^^^^^^^^^^

Pressione ``Ctrl + L`` para alternar entre a grade de miniaturas e uma visualização em lista ordenável
com estas colunas: Pré-visualização · Rótulo · Avaliação · Nome · Resolução · Tamanho · Tipo · Modificado.
Clique duas vezes em uma linha (ou pressione ``Enter``) para entrar no Deep Zoom; pressione ``Esc``
para retornar à lista. Miniaturas e metadados são carregados de forma lazy em uma thread de trabalho
para que pastas muito grandes permaneçam responsivas.

``Delete`` remove as linhas selecionadas e ``Ctrl + Z`` as traz de volta, e as teclas de avaliação (``1`` – ``5``), favorito (``0``), seleção (``P`` / ``Shift + X`` / ``U``) e cor (``F1`` – ``F5``) as marcam, como na grade; todas, exceto ``F1`` – ``F5``, seguem as configurações de atalhos.

Modo Deep Zoom
^^^^^^^^^^^^^^

Clique em uma miniatura para entrar no modo Deep Zoom para visualização individual de alta qualidade.

Panoramas muito acima do limite de segurança de 179 megapixels do Pillow também abrem: o limite acompanha a memória do computador (com 16 GB, cerca de 1,4 gigapixel) e essas imagens gigantes são decodificadas uma de cada vez.

Um JPEG, PNG, TIFF, GIF ou BMP incompleto — um download ou cópia interrompidos, uma foto recuperada de um cartão de memória com defeito — abre com a parte que foi lida, como no navegador, em vez de não abrir.

Quando outro programa salva por cima de uma imagem — um editor externo, direto no arquivo ou renomeando uma cópia por cima —, o visualizador mostra a versão nova: a imagem aberta no zoom profundo em menos de um segundo após a última gravação, as miniaturas da grade e as linhas da Lista em poucos segundos.

Um PNG ou TIFF em cinza de 16 bits — um escaneamento, um mapa de profundidade, uma imagem científica ou astronômica — e um TIFF de ponto flutuante mostram seu brilho real no visualizador, nas miniaturas, nas prévias e nas ferramentas, em vez de quase branco ou preto: valores de 16 bits são escalados em toda a faixa, valores de ponto flutuante de 0 a 1 vão do preto ao branco e qualquer outra faixa é esticada.

Imagens com perfil de cor embutido — Display P3 de celulares, Adobe RGB de câmeras, CMYK e os perfis de cinza que o Photoshop embute em imagens em tons de cinza, como Dot Gain 20% ou Gray Gamma 1.8 — são convertidas para sRGB no visualizador e nas miniaturas; uma imagem em tons de cinza continua em tons de cinza. Imagens sem perfil ou em sRGB aparecem como estão.

Arquivos que o Windows marca como ocultos — ocultos também no Explorer e na árvore de pastas — e nomes que começam com ponto, como o ``._foto.jpg`` que o macOS grava ao lado de cada foto em cartões de memória e unidades de rede, ficam fora da grade de miniaturas, dos ícones de pasta, das listas das ferramentas em lote, das pastas monitoradas, das varreduras da biblioteca, da CLI e das ferramentas de pasta do servidor MCP; varreduras recursivas pulam pastas ocultas como ``$RECYCLE.BIN`` e a ``.Trashes`` de um Mac. Uma imagem oculta aberta de propósito abre mesmo assim.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Método
   * - Zoom in/out
     - Roda do mouse ou pinça no touchpad
   * - Deslocar
     - Mantenha o botão do meio do mouse pressionado
   * - Imagem anterior
     - ``Seta Esquerda`` (ou deslize para a direita no touchpad)
   * - Próxima imagem
     - ``Seta Direita`` (ou deslize para a esquerda no touchpad)
   * - Salto entre pastas
     - ``Ctrl + Shift + Esquerda`` / ``Direita`` para a pasta irmã anterior/próxima com imagens
   * - Voltar / avançar no histórico
     - ``Alt + Esquerda`` / ``Alt + Direita`` (estilo navegador)
   * - Saltar para imagem por número
     - ``Ctrl + G``
   * - Imagem aleatória
     - ``X``
   * - Ajustar à largura
     - ``W``
   * - Ajustar à altura
     - ``Shift + W``
   * - Redefinir zoom
     - ``Home``
   * - Voltar às miniaturas
     - ``Esc``
   * - Tela cheia
     - ``F`` (pressione novamente para sair)
   * - Modo cinema
     - ``Shift + Tab`` oculta menu / status / árvore / abas para visualização sem distrações
   * - Sobreposição OSD de informações
     - ``F8`` mostra nome do arquivo / tamanho / tipo; ``Ctrl + F8`` mostra um HUD de depuração (VRAM / cache / threads)
   * - Visualização de pixel
     - ``Shift + P`` — a partir de 400 % de zoom mostra RGB / HEX sob o cursor, mais uma grade de pixels quando no máximo 40.000 pixels da imagem estão na tela
   * - Modos de cor
     - ``Shift + M`` alterna entre Normal / Tons de Cinza / Inverter / Sépia (GLSL, não destrutivo)

Visão Dividida e Leitura em Página Dupla
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Exiba duas imagens lado a lado diretamente na janela principal sem abrir a caixa de diálogo Comparar:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Ação
     - Atalho
   * - Visão dividida (duas imagens)
     - ``Shift + S``
   * - Página dupla (atual + próxima)
     - ``Shift + D``
   * - Página dupla, da direita para a esquerda (mangá)
     - ``Ctrl + Shift + D``
   * - Voltar ao modo anterior
     - ``Esc``

No modo de página dupla, as teclas de seta avançam de duas em duas imagens. A variante da direita
para a esquerda inverte os dois painéis para que a página 1 apareça à direita.

Janela Multi-Monitor
^^^^^^^^^^^^^^^^^^^^

Pressione ``Ctrl + Shift + M`` para abrir uma segunda janela sem moldura em seu display secundário
que espelha a imagem atualmente mostrada no visualizador principal. A janela principal continua
navegando independentemente — útil para exposições, fluxos de edição em tela dupla ou apresentações
para clientes. Pressione ``Ctrl + Shift + M`` novamente para fechar, ou use ``Esc`` dentro da segunda janela.

----

Organizando Imagens
-------------------

Avaliação e Favoritos
^^^^^^^^^^^^^^^^^^^^^

As teclas avaliam a imagem mostrada no Deep Zoom. Na grade avaliam as miniaturas selecionadas, senão a escolhida com as setas, senão a que está sob o mouse — as mesmas fotos que um rótulo de cor ou uma marcação de seleção tomaria. Se todas já têm essa avaliação, a tecla a remove.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Tecla
   * - Alternar favorito
     - ``0``
   * - Avaliar 1 -- 5 estrelas
     - ``1`` ``2`` ``3`` ``4`` ``5`` (pressione novamente para limpar)

Rótulos de Cor (F1 -- F5)
^^^^^^^^^^^^^^^^^^^^^^^^^

Marcadores de cor, armazenados separadamente da avaliação por estrelas
de 1 a 5. Úteis para categorização rápida (ex.: vermelho = candidatos a rejeição, verde = selecionadas,
azul = a retocar).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Tecla
   * - Vermelho / Amarelo / Verde / Azul / Roxo
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (pressione a mesma tecla novamente para
       limpar; em uma seleção, só limpa quando todas as imagens selecionadas já têm essa cor)
   * - Aplicação em lote à seleção
     - Selecione várias miniaturas, depois pressione a tecla F correspondente
   * - Filtrar por cor
     - ``Filtrar`` > ``Por Rótulo de Cor`` > escolha uma cor / Qualquer rótulo / Sem rótulo

A barra de status mostra um chip colorido para a imagem atual. As miniaturas exibem uma faixa colorida
na borda esquerda. A **Visualização em Lista** tem colunas dedicadas de **Rótulo** e **Avaliação**
pelas quais você pode ordenar — clique em qualquer célula na coluna de estrelas para definir a avaliação
sem sair da lista.

Marcadores (Bookmarks)
^^^^^^^^^^^^^^^^^^^^^^

Salve imagens usadas com frequência como marcadores para acesso rápido posteriormente.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Método
   * - Adicionar / remover marcador
     - Pressione ``B`` no modo Deep Zoom
   * - Gerenciar marcadores
     - ``Arquivo`` > ``Marcadores``

Tags e Álbuns
^^^^^^^^^^^^^

Categorize suas imagens com tags e álbuns.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Método
   * - Abrir gerenciador
     - Pressione ``T`` ou ``Arquivo`` > ``Tags e Álbuns``
   * - Marcar uma imagem com tag
     - No Deep Zoom, clique com o botão direito > ``Tags``; para miniaturas selecionadas, clique
       com o botão direito > ``Operações em Lote`` > ``Adicionar à Tag``
   * - Adicionar ao álbum
     - No Deep Zoom, clique com o botão direito > ``Álbuns``; para miniaturas selecionadas, clique
       com o botão direito > ``Operações em Lote`` > ``Adicionar ao Álbum``
   * - Filtrar por tag/álbum único
     - ``Filtrar`` > ``Por Tag`` / ``Por Álbum``
   * - Filtro multi-tag (E / OU)
     - ``Filtrar`` > ``Filtro Multi-Tag…`` — marque várias tags ou álbuns, escolha Qualquer (OU) ou Todos (E)
   * - Limpar
     - **Limpar…** no gerenciador esquece as entradas de arquivos que não existem mais e mescla nomes
       que diferem só em maiúsculas/minúsculas (o que tem mais imagens mantém a sua grafia), depois que
       você confirma as contagens. Criar ou renomear uma tag ou álbum com um nome que difere de outro só
       em maiúsculas/minúsculas ou espaços é recusado, assim como um nome com tabulação ou quebra de linha

Classificação e Filtragem
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Recurso
     - Localização no Menu
   * - Ordenar por nome (ordem natural: ``img2`` antes de ``img10``)
     - ``Ordenar`` > ``Por Nome``
   * - Ordenar por data de modificação
     - ``Ordenar`` > ``Por Data de Modificação``
   * - Ordenar por data da foto (horário EXIF da câmera; sem ele, a data de modificação)
     - ``Ordenar`` > ``Por Data da Foto``
   * - Ordenar por tamanho do arquivo
     - ``Ordenar`` > ``Por Tamanho do Arquivo``
   * - Ordenar por resolução
     - ``Ordenar`` > ``Por Resolução``
   * - Crescente / Decrescente
     - ``Ordenar`` > ``Crescente`` / ``Decrescente``
   * - Filtrar por extensão
     - ``Filtrar`` > ``Por Extensão`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
   * - Filtrar por avaliação
     - ``Filtrar`` > ``Por Avaliação``
   * - Filtrar por rótulo de cor
     - ``Filtrar`` > ``Por Rótulo de Cor`` (Todos / Qualquer rótulo / Sem rótulo / Vermelho / Amarelo / Verde / Azul / Roxo)
   * - Filtro avançado
     - ``Filtrar`` > ``Filtro Avançado…`` — faixa de resolução, faixa de tamanho de arquivo, orientação (paisagem / retrato / quadrada), faixa de data de modificação
   * - Limpar filtros
     - ``Filtrar`` > ``Limpar Filtro``

Modo de Navegação (Grade / Lista)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Alterne o navegador de imagens entre a grade de blocos e uma lista detalhada ordenável:

- ``Ctrl + L`` — alternar Grade ↔ Lista
- Menu: ``Tamanho da Miniatura`` > ``Modo de Navegação`` > Grade / Lista
- No modo Lista, qualquer coluna (incluindo Rótulo) é ordenável; clique duas vezes em uma linha ou pressione ``Enter`` para abrir o Deep Zoom.

----

Editando Imagens (Aba Modify)
-----------------------------

Mude para a aba **Modify** na parte superior da janela para entrar no modo de edição.
No modo Deep Zoom, o clique com o botão direito > ``Modify`` > ``Develop`` também abre a imagem atual aqui;
já ``E`` (ou clique com o botão direito > ``Modify`` > ``Annotate``) a abre no editor de anotações separado.

::

   +--------+----------------------+------------+
   | Tira   |                      | Propriedades|
   | de     |   Tela (desenhe aqui)| Pincéis    |
   | Ferr.  |                      | Revelar    |
   +--------+----------------------+------------+

Ferramentas de Anotação (Painel Esquerdo)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Ferramenta
     - Ícone
     - Descrição
   * - Selecionar
     - |select|
     - Selecionar anotações existentes; arraste para mover
   * - Retângulo
     - |rect|
     - Desenhar retângulos
   * - Elipse
     - |ellipse|
     - Desenhar elipses ou círculos
   * - Linha
     - |line|
     - Desenhar linhas retas
   * - Seta
     - |arrow|
     - Desenhar setas
   * - Mão livre
     - |freehand|
     - Desenho de forma livre
   * - Texto
     - T
     - Adicionar texto à imagem
   * - Mosaico
     - |mosaic|
     - Pixelar uma região selecionada
   * - Desfoque
     - |blur|
     - Aplicar desfoque gaussiano em uma região selecionada

.. |select| unicode:: U+2B1A
.. |rect| unicode:: U+25A2
.. |ellipse| unicode:: U+25EF
.. |line| unicode:: U+2571
.. |arrow| unicode:: U+2192
.. |freehand| unicode:: U+270E
.. |mosaic| unicode:: U+25A6
.. |blur| unicode:: U+25CC

.. tip::
   Pressione ``Seta Esquerda`` / ``Seta Direita`` enquanto estiver na aba Modify para alternar entre imagens sem sair do editor.

Tipos de Pincel (Painel Direito)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pincel
     - Efeito
   * - Caneta
     - Linha fina padrão, o pincel mais comum
   * - Marcador
     - Traços mais grossos e semitransparentes
   * - Lápis
     - Linha fina ligeiramente esmaecida
   * - Marca-texto
     - Largo e altamente transparente, como um marca-texto real
   * - Spray
     - Efeito de pontos dispersos
   * - Caligrafia
     - A largura do traço varia com a direção
   * - Aquarela
     - Efeito suave de bordas úmidas com mistura
   * - Carvão
     - Traço áspero e texturizado
   * - Giz de cera
     - Textura cerosa, como giz de cera

Propriedades de Desenho (Painel Direito)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Propriedade
     - Descrição
   * - Cor
     - Clique na amostra de cor para escolher uma cor de desenho
   * - Largura do Traço
     - Arraste o slider para ajustar a espessura da linha (1 -- 40)
   * - Opacidade
     - Ajuste a transparência (0 % -- 100 %)
   * - Fonte
     - Escolha a fonte para a ferramenta Texto
   * - Tamanho da Fonte
     - Ajuste o tamanho do texto (6 -- 200 px)

Ajustes de Imagem (Painel Direito, Inferior)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Slider
     - Função
   * - Exposição
     - Ajustar o brilho geral
   * - Brilho
     - Ajuste fino das áreas claras e escuras
   * - Contraste
     - Ajustar a diferença entre claros e escuros
   * - Saturação
     - Ajustar a vivacidade da cor
   * - Balanço de Branco — Temperatura
     - Deslocamento quente / frio (azul → amarelo); útil para luz mista ou fotos em ambientes fechados
   * - Balanço de Branco — Matiz
     - Deslocamento magenta / verde; corrige dominância fluorescente
   * - Realces
     - Recuperar realces estourados ou empurrar áreas claras ainda mais
   * - Sombras
     - Levantar ou esmagar detalhes em regiões de tons escuros
   * - Brancos
     - Para a direita, estica os tons mais claros até o branco; para a esquerda, escurece o branco até um cinza
   * - Pretos
     - Para a esquerda, esmaga os tons mais escuros até o preto; para a direita, clareia o preto até um cinza desbotado
   * - Vibração
     - Reforço de saturação consciente — protege tons de pele e cores já saturadas

Esses ajustes são **não destrutivos**. Cada slider grava em uma receita de edição armazenada
por imagem; pressione ``Reset`` a qualquer momento para restaurar o original, ou ``Undo`` / ``Redo``
abaixo dos sliders para percorrer as alterações individuais. As receitas sobrevivem a reinicializações
e podem ser exportadas / sincronizadas via o fluxo de sidecar XMP descrito na seção Metadados.

O arquivo em disco só muda quando você pede. **Apply Crop** e o **Save** de anotações gravam o resultado sobre o arquivo e mantêm seu EXIF (câmera, data de captura, GPS), XMP e DPI. Um RAW de câmera, um HEIC ou um arquivo animado / de várias páginas nunca é sobrescrito: o recorte pede que você exporte e o salvamento de anotações pede um arquivo novo. As ferramentas de uso único (CLAHE, mixer HSL, moldura, endireitamento
automático…) salvam o resultado ao lado do original como ``photo_clahe.png``;
executá-las de novo salva ``photo_clahe_1.png`` em vez de substituir o último
resultado. **Auto-Rotate by EXIF**, as cópias do **Batch EXIF Strip** e **Split Pages…** numeram seus arquivos da mesma forma. A receita e as cópias virtuais de uma foto a acompanham quando o Imervue a gira
sem perda (o recorte gira junto) ou reescreve o EXIF (geotag GPS, editor EXIF); uma
receita com máscaras locais, camadas, reflexo de lente ou tags de rostos fica com a
versão sem giro até que seja girada de volta.

Salvar e Desfazer
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Botão
     - Descrição
   * - Salvar
     - Gravar anotações e ajustes no arquivo original
   * - Desfazer
     - Desfazer a última operação
   * - Refazer
     - Refazer uma operação desfeita
   * - Resetar
     - Limpar todos os ajustes de imagem

----

Espaço de Trabalho Paint (Aba Paint)
------------------------------------

A terceira aba principal — **Paint** — é um espaço de trabalho completo para pintura
com documentos em múltiplas abas, camadas vetoriais e raster, ferramentas para mangá,
quadros de animação e importação/exportação PSD. Ao mudar para ela pela barra de abas,
a imagem exibida no visualizador é carregada na tela.

Destaques de usabilidade — o espaço de trabalho Paint vem com um cursor completo de
tamanho de pincel que escala com o zoom, ícones de cursor distintos por ferramenta,
um padrão de checker de transparência sob a tela, sobreposição de destaque para
arrastar-e-soltar, asterisco de modificado por aba, confirmações via toast para
desfazer / refazer, um segmento de status de autosalvamento na barra de status, e
um prompt de recuperação de autosalvamento na inicialização que apresenta snapshots
de uma sessão anterior que travou.

Atalhos para usuários avançados: ``Tab`` alterna todos os docks para pintura sem
distrações, ``Ctrl+Tab`` alterna entre abas, ``,`` / ``.`` alternam os tipos de pincel,
``0–9`` definem a opacidade do pincel em passos de 10 %, ``Alt+[`` / ``Alt+]`` percorrem
a camada ativa, e o clique com o botão direito na tela abre um menu rápido com Desfazer
/ Refazer / Selecionar Tudo / Desselecionar / Ajustar / 100 %.

O dock de cores agora expõe um slot "transparente / sem cor" (BG padrão = transparente),
e tanto preenchimento quanto varinha mágica respeitam limites de alfa, de forma que
pixels apagados não vazam para uma nova pintura. Abaixo dos slots de cor fica um
anel de matiz em volta de um triângulo de saturação / brilho: arraste no anel para
escolher o matiz e dentro do triângulo para escolher a tonalidade; os sliders HSB /
RGB e o campo HEX acompanham, e uma cor definida em outro lugar move os marcadores
da roda. O **dock Amostras** mostra suas cores recentes, ou uma paleta escolhida na
caixa acima delas: as embutidas Standard, Pastel e Manga, ou uma das suas.
**Salvar como Paleta…** guarda as cores recentes com um nome, **Excluir Paleta**
remove uma das suas (as embutidas continuam), e ``Filtro`` >
``Corresponder Amostras…`` repinta com as cores que o dock estiver mostrando.

::

   +------+----------------------+----------------+
   | Barra|                      | Cor · Pincel   |
   | de   |   Tela (pintar)      | Camada · Nav.  |
   | Ferr.|                      | Material · …   |
   +------+----------------------+----------------+

Os catorze docks do lado direito são organizados em abas em uma única coluna para
que a tela mantenha toda a altura visível, agrupados em três conjuntos:

- **Desenho** — Cor, Pincel, Balde, Amostras
- **Tela** — Camadas, Navegador, Histórico, Páginas, Animação, Histograma
- **Biblioteca** — Materiais, Carimbos, Pose, Referência

Cada dock pode ser exibido ou ocultado individualmente pelo menu ``Janela``. Arraste
o título de qualquer dock para reorganizar ou flutuar um painel;
``Configurações`` > ``Layouts de Espaço de Trabalho…`` lembra quais docks estão
visíveis (veja *Layouts de Espaço de Trabalho*).

Paleta de Ferramentas (Tira Esquerda)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Ferramenta
     - Atalho
     - Finalidade
   * - Pincel
     - ``B``
     - Pintar com o tipo de pincel ativo
   * - Borracha
     - ``E``
     - Apagar alfa na camada ativa
   * - Preenchimento (balde)
     - ``G``
     - Preenchimento por inundação com tolerância / contíguo / amostrar todas as camadas.
       No dock Balde, **Auto-fill closed regions** preenche com a cor de primeiro
       plano cada região fechada da arte-final (a camada de referência, ou então a
       ativa); **Base colours on a new layer** dá a cada região sua própria cor
       chapada — as cores do dock Amostras, quando ele mostra alguma — numa nova
       camada abaixo da arte-final, deixando vazios os traços e o espaço ao redor
       do desenho. Linhas escuras em papel branco funcionam tão bem quanto linhas
       sobre transparência
   * - Conta-gotas
     - ``I``
     - Selecionar cor de primeiro plano a partir da tela
   * - Mover
     - ``V``
     - Transladar a camada ativa ou seleção
   * - Retângulo / Laço / Varinha / Seleção Rápida
     - ``M`` / ``L`` / ``W``
     - Ferramentas de seleção com modos Substituir / Adicionar / Subtrair / Interseccionar; no
       Laço, **Magnetic** na barra de Opções encaixa o contorno na borda mais forte
       da camada num raio de 10 px quando você solta o botão
   * - Texto
     - ``T``
     - Clique abre o diálogo **Adicionar Texto** (fonte / tamanho / cor /
       negrito / itálico); o texto é desenhado nos pixels da camada
   * - Gradiente
     - ``U``
     - Preenchimento por gradiente Linear / Radial / Angular / Diamante, da cor
       de primeiro plano para a de fundo ou ao longo de um gradiente salvo de
       várias paradas escolhido em **Colours** na barra de Opções; **Edit…** ao
       lado cria, altera e exclui esses gradientes (nome, paradas de cor com
       posição e opacidade), que são mantidos entre sessões
   * - Desfoque / Esfumar
     - ``R`` (Esfumar)
     - Manipulação local de pixels
   * - Dodge / Burn / Sponge
     -
     - Tonalização de câmara escura ponderada pelo pincel — Dodge clareia e
       Burn escurece os meios-tons, Sponge dessatura; sem opções
   * - Caneta (Bezier)
     - ``P``
     - Caminho vetorial com edição de âncoras / alças; **Smooth** na barra de
       Opções traça uma única curva suave por todos os pontos clicados em vez
       de linhas retas
   * - Carimbo de Clonar
     - ``S``
     - Alt+clique define a origem, depois arraste para carimbar com o
       tamanho / dureza / opacidade do pincel
   * - Balão de Fala
     - ``Ctrl + B``
     - Arraste uma caixa para desenhar um balão de quadrinho / mangá
       (desenhado sem cauda)
   * - Retângulo / Elipse / Linha / Polígono
     - ``Shift + R/E/I/P``
     - Primitivas vetoriais de forma com traço + preenchimento
   * - Recortar
     - ``C``
     - Recorte livre — arraste um retângulo; a tela é recortada ao soltar
   * - Transformar
     - ``Ctrl + T``
     - Oito alças de escala e uma alça de rotação
   * - Mão
     - ``H``
     - Deslocar a tela arrastando com o cursor
   * - Zoom
     - ``Z``
     - Clique para aproximar, Alt-clique para afastar

Pincéis
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Pincel
     - Efeito
   * - Lápis
     - Linha fina de grafite levemente texturizada
   * - Caneta
     - Linha nítida e antialiased, o pincel do dia a dia
   * - Marcador
     - Traços largos e semitransparentes que se sobrepõem
   * - Aerógrafo
     - Pontos dispersos que se acumulam em um spray suave
   * - Aquarela
     - Borda úmida com interior mais claro, como pigmento acumulado na borda
   * - Sumi
     - Tinta em estilo caligráfico com bordas de pincel seco

Giz de cera, Marca-texto e caligrafia Sumi são presets de pincel construídos
sobre esses tipos. Cada pincel expõe Tamanho / Opacidade / Dureza / Densidade /
Modo de Mistura no **dock Pincel**; a **barra de Opções** superior traz
Tamanho / Opacidade / Dureza. A pressão da caneta da mesa digitalizadora escala
o tamanho e a opacidade do pincel pela curva definida em ``Configurações`` >
``Curva de Pressão…`` (arraste um ponto, clique para adicionar um, clique com o
botão direito para remover um, ou comece por Linear / Suave / Dura); um mouse
desenha com pressão total. No dock Pincel, **Dispersão** desloca cada toque do
pincel para fora do traço em até a fração do tamanho do pincel que ela define,
**Variação de cor** altera o matiz, a saturação e o brilho de cada toque, e
**Seguir inclinação da caneta** estreita a ponta no sentido transversal à
direção em que a caneta da mesa digitalizadora se inclina e a gira para
acompanhar essa inclinação (o preset caligrafia Sumi vem com essa opção
ativada); um pincel de pixel art mantém sua ponta quadrada. Use ``Editar`` >
``Capturar Ponta de Pincel…`` para transformar uma seleção em uma ponta de
pincel personalizada. O **dock Materiais** lista seus próprios materiais antes
das retículas e texturas embutidas: imagens na pasta ``materials`` da pasta do
programa do Imervue (uma pasta de primeiro nível chamada ``texture``, ``tone``,
``pattern``, ``brush_tip`` ou ``pose`` as classifica nessa categoria) e as
pontas de pincel que você capturou. ``Editar`` >
``Salvar Seleção como Material…`` salva ali a parte selecionada da imagem
visível com o nome e a categoria que você escolher (os pixels fora da seleção
ficam transparentes, e um material anterior com o mesmo nome é mantido); ele
aparece no dock na hora.

Camadas
^^^^^^^

O **dock Camada** oferece miniaturas, alternâncias de visibilidade, renomeação
inline, reordenação com os botões ↑ / ↓ (ou ``Ctrl + ]`` / ``Ctrl + [``), e o
modo de mistura + opacidade da camada ativa. O menu ``Camada`` adiciona:

- **Nova / Vetorial / Duplicar / Mesclar Abaixo** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Máscaras** — Adicionar Máscara / A partir da Seleção / Inverter / Aplicar / Excluir
  (``Ctrl + Shift + M`` adiciona; ``Ctrl + Alt + Shift + M`` adiciona a partir da seleção)
- **Máscara de Recorte** — alternar o recorte na camada ativa, recortando-a ao
  alfa da camada abaixo (``Ctrl + Alt + G``)
- **Efeitos de Camada** — Sombra Projetada · Brilho Externo · Traço; limpar efeitos
- **Camada de Referência** — fixar uma camada como a fonte contra a qual o balde
  de **Preenchimento** compara as cores
- **Camada 1-bit** — alternar a camada ativa para uma camada binária de line-art
- **Dividir Camada por Cor** — dividir uma camada de cor plana em uma camada por
  cor para facilitar repinturas com balde
- **Mapa de Gradiente** — submenu de presets (sépia / pôr-do-sol / cianotipo …)

Seleções
^^^^^^^^

Use as ferramentas retângulo / laço / varinha / seleção rápida, depois o
**Traçar Seleção…** no menu **Editar** para contornar a marquise com a cor de
primeiro plano, usando a Largura e o Posicionamento do diálogo.
``Q`` alterna o **Modo Máscara Rápida** — pinte com qualquer pincel para refinar a
borda da seleção em vermelho, depois pressione ``Q`` novamente para convertê-la de
volta em uma marquise.

Animação
^^^^^^^^

O **dock Animação** transforma o documento em uma tira de quadros:

- ``+ Quadro`` captura a imagem achatada em um novo quadro.
- Clique na miniatura de um quadro para carregá-lo na camada ativa.
- ``Onion Skin`` (menu Visualizar) sobrepõe o quadro anterior com baixa opacidade.
- ``▶ Reproduzir`` percorre os quadros no FPS escolhido.
- ``Exportar…`` salva os quadros como GIF animado, WebP ou PNG — o tipo de
  arquivo escolhido define o formato, e um nome sem tipo vira GIF —, cada
  quadro durando um tique do FPS escolhido. O WebP é gravado sem perdas; o
  GIF reduz cada quadro a 255 cores e torna transparentes os pixels tênues,
  de baixa opacidade.

Menu Mangá
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Ação
     - Descrição
   * - Cortador de Painéis
     - ``Ctrl + Shift + P`` — divide a tela em uma grade de painéis de quadrinhos com linhas / colunas / sarjeta / borda / margem configuráveis; com **Snap to panel** marcado na barra de Opções do pincel, cada traço passa a ficar dentro do painel em que começa (até o tamanho da tela mudar)
   * - Alternar Camada de Tom
     - Converter a camada ativa em uma camada de tom (pontos de meio-tom)
   * - Carimbar Números de Página
     - Adicionar números de página em documentos de várias páginas
   * - Linhas de Velocidade
     - Geradores de linhas de velocidade Radial / Paralelas / Explosão
   * - Action Flash
     - Sobreposição estilo mangá de explosão / impacto
   * - Texto ao Longo da Seleção…
     - Dispõe o texto ao longo do contorno da seleção, em uma nova camada — texto, fonte, tamanho, cor, negrito e itálico vêm do diálogo Adicionar Texto

Filtros
^^^^^^^

Os filtros com um único slider — Posterizar, Limiar, Converter para Meio-Tom
e Corresponder Cor — mostram uma pré-visualização ao vivo enquanto você
arrasta, nos 480 × 480 pixels centrais da camada em tamanho real; OK aplica
o valor à camada inteira. Os demais abrem uma caixa de diálogo simples de
parâmetros OK / Cancelar:

- **Níveis** — sliders de ponto preto / ponto branco / gama
- **Curvas** — um preset (Curva em S, Levantar sombras, Comprimir realces) com um slider de Intensidade
- **Posterizar** — quantizar cor em N passos
- **Limiar** — converter para preto / branco puro em um corte
- **Balanço Automático de Cor** — neutralizar dominâncias via grey-world / white-patch
- **Granulação de Filme** — ruído de luminância com tamanho e quantidade ajustáveis
- **Converter para Meio-Tom** — tela de pontos estilo jornal
- **Corresponder Cor** — pede uma imagem de referência e então dá à camada a
  atmosfera de cor dessa imagem (cada canal assume a média e a dispersão da
  referência); **Intensidade** mistura de inalterada até a correspondência total
- **Corresponder Amostras** — repinta cada pixel com a cor mais próxima do
  dock Amostras (escolha ou importe cores antes)

Auxílios de Visualização
^^^^^^^^^^^^^^^^^^^^^^^^

- **Grade de Pixels** (``Ctrl + Shift + '``) — sobrepor grade de um pixel em zoom alto
- **Encaixar em Pixel / Bordas** — Encaixar em Pixel posiciona os toques do pincel em pixels inteiros; Encaixar em Bordas puxa os pontos para bordas próximas da tela ou da camada
- **Onion Skin** — sobrepõe o quadro de animação anterior
- **Guias de Sangria** — guias de sangria de impressão / zona segura
- **Rotacionar Tela** (``Ctrl + Shift + H``) — rotação da visualização sem rasterizar

I/O de Arquivos
^^^^^^^^^^^^^^^

- **Nova Tela…** — uma nova aba do tamanho que você escolher: um preset de papel, mangá ou monitor (A4, página de mangá B5, 1080p, 4K …), um que você salvou com **Salvar como preset…**, ou qualquer largura e altura até 16384 px, com fundo branco ou transparente (**Nova Aba**, ``Ctrl + N``, mantém o padrão de 1024 × 1024 em branco)
- **Abrir PSD…** (``Ctrl + O``) achata o arquivo em uma única camada em uma nova aba; **Salvar como PSD…** (``Ctrl + S``) grava as camadas com seus modos de mistura (sem máscaras nem efeitos de camada)
- **Exportar imagem…** — achatar e salvar como PNG, JPEG, WebP, TIFF ou BMP, conforme o tipo de arquivo escolhido (JPEG e BMP, que não têm transparência, sobre fundo branco). Só **Salvar como PSD…** marca a aba como salva; depois de uma exportação, fechar o Imervue ainda pergunta sobre as alterações não salvas da aba
- **Exportar páginas → CBZ** / **→ PDF** — exportar as páginas de um projeto de quadrinhos; **Salvar projeto de quadrinhos…** salva o quadrinho inteiro, cada página com suas camadas, em um único arquivo ``.imervue-proj``, e **Abrir projeto de quadrinhos…** o reabre
- **Importar preset de pincel…**, **Importar paleta…** — trazer pincéis e paletas de outras instalações ou aplicativos
- **Autosalvamento** — a cada 2 minutos, enquanto a aba ativa tiver edições não salvas, um snapshot é gravado; na próxima inicialização um toast oferece os snapshots e **Arquivo > Restaurar Autosalvamento** carrega o mais recente na aba ativa. A barra de status mostra quando o último snapshot foi feito, e ao fechar o Imervue ele pergunta sobre abas Paint com alterações não salvas.

Layouts de Espaço de Trabalho
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Configurações`` > ``Layouts de Espaço de Trabalho…`` lista os layouts embutidos
**Padrão**, **Desenho**, **Quadrinhos** e **Compacto**, além dos seus.
**Salvar atual…** guarda, com um nome, quais dos docks Camadas / Cor / Pincel /
Navegador / Histórico / Referência estão visíveis; aplicar um layout mostra ou
oculta esses docks e traz o primeiro visível para a frente. Opções de ferramenta
e tamanhos dos docks não são guardados.

----

Espaço de Trabalho Puppet (Aba Puppet)
--------------------------------------

A quarta aba principal — **Puppet** — é um sistema de animação de fantoches 2D
com rig construído do zero: rigs de deformação de mesh, parâmetros, motions,
física, expressões, grupos de pose, sincronização labial e rastreamento por webcam,
**sem SDK proprietário**, **sem** ``live2d-py``, e com
um formato de arquivo ``.puppet`` totalmente aberto.

.. note::

   O tutorial completo de ponta a ponta — partindo de uma instalação nova até
   uma transmissão ao vivo no OBS ou um MP4 renderizado — está em ``puppet_guide.md``
   na raiz do repositório (com espelhos em ``puppet_guide.zh-TW.md`` e
   ``puppet_guide.zh-CN.md``). Esta seção é a referência;
   o guia é o passo a passo.

::

   +-----------+----------------------+----------------+
   |  Barra de |                      |   Dock         |
   |  Ferr.    |   Canvas GL          |   Parâmetros   |
   |           |                      |                |
   +-----------+----------------------+                |
   |               Dock Motions                        |
   +---------------------------------------------------+

Os docks da direita compartilham uma área com abas: **Parameters** (um controle deslizante por parâmetro), **Expressions** (liga ou desliga cada expressão), **Pose** (escolhe qual membro de cada pose group aparece — um grupo mostra o primeiro membro até que outro seja escolhido) e **Bones** (a hierarquia de deformers).

Fluxo de Trabalho de Ponta a Ponta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Importar um PNG** — ``File`` > ``Import PNG…`` executa
   ``puppet.auto_mesh.puppet_from_png``: grade triangulada limitada por alfa,
   um drawable, pronto para renderizar.
2. **Adicionar um deformador** — ``Edit`` > ``Add Rotation Deformer`` (âncora + ângulo) ou
   ``Add Warp Deformer`` (lattice bilinear de linhas × colunas; os vértices fora
   dos limites passam sem alteração).
3. **Adicionar um parâmetro** — ``Edit`` > ``Add Parameter`` adiciona um slider ao dock
   **Parâmetros** à direita com id auto-nomeado (``Param1``, ``Param2``, …).
4. **Definir keys** — arraste o slider para um extremo, edite a forma do deformador
   em código, pressione **Set key**. Repita no neutro e
   no extremo oposto. O runtime então faz lerp dos campos do deformador entre
   keys adjacentes sempre que o slider se move. **Set key** guarda apenas formas
   de deformador: **Edit mesh** move de vez os vértices de repouso do drawable,
   então uma edição de mesh não vira key.
5. **Salvar** — ``Save As…`` grava o rig + texturas + motions + expressões
   + física em um único zip ``.puppet`` que você pode compartilhar ou abrir
   depois via ``Open Puppet…``.

Experimente um Exemplo Pronto
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O repositório inclui uma demo totalmente riggada em
``examples/puppet/imeru.puppet`` — **Imeru**, o mascote original do
Imervue. Ela é feita inteiramente por
``examples/puppet/imeru/build.py`` (``py -3`` reconstrói o arquivo; exige
o Blender 4.2 ou mais recente): o cabelo, o corpo, a roupa e os braços dela
são modelados e recebem cel shading no Blender com os truques de
sombreamento dos jogos de anime em 3D (cabelo iluminado pelas normais de
uma forma substituta suave, mechas e traços de brilho pintados, oclusão
pré-calculada), sendo renderizados uma camada do puppet por vez, o rosto
dela é sombreado a partir de um mapa de sombra facial SDF, os olhos, as
sobrancelhas e a boca são pintados por cima como nos personagens de jogos
3D, e as camadas são então riggadas, então a demo não carrega direitos de
terceiros: 45 drawables em um canvas de 1024 × 1336, giros de cabeça
feitos de morphs de vértice com paralaxe no estilo Live2D, uma sombra no
rosto que muda de forma conforme ela se vira para longe da luz, íris
recortadas pelo branco dos olhos, braços com duas articulações construídos
com rotation deformers, e três cadeias de física que balançam o cabelo.

O rig carrega todos os parâmetros padrão Cubism (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …) mais
``ParamArmLA/LB/RA/RB`` para os braços, então todo driver de entrada padrão
(webcam, piscar, sincronização labial, olhar do cursor) o aciona sem
configuração por rig. Oito motions estão incluídos no arquivo: dois motions de
idle em loop no grupo ``Idle``, ``tap_head`` em ``TapHead`` e ``shy`` em
``TapBody`` (clicar na cabeça ou no corpo dela os reproduz), e ``greet``,
``wave``, ``surprised`` e ``sleepy`` em ``Gesture``; sete expressões vêm
junto (smile, happy, surprised, sad, angry, blush, sleepy).

Abra a aba Puppet, clique em **Open Puppet…**, aponte para
``imeru.puppet`` — a figura aparece centralizada. Arraste qualquer slider
de parâmetro para acionar uma articulação, ou clique em um dos motions no dock
Motions — clique único vincula o motion e inicia a reprodução imediatamente.

**Executando o exemplo incluído, passo a passo:**

1. Inicie o Imervue. A partir do código-fonte: ``python -m Imervue``. A partir
   do build empacotado: execute o executável / bundle de aplicativo ``Imervue``.
   O diretório ``examples/`` é empacotado nos builds Nuitka e PyInstaller;
   uma instalação via pip / wheel não o inclui (em um checkout do código-fonte
   os rigs ficam em ``examples/puppet/``).
2. Clique na aba **Puppet** no topo da janela.
3. **File > Examples > Imeru** (ou o dropdown
   **Examples ▾** da barra de ferramentas). O rig carrega centralizado e o
   dock de parâmetros é preenchido com seus sliders.
4. No dock **Motions** inferior, clique uma vez em qualquer entrada de motion
   (``idle_look``, ``wave``, ``tap_head`` …).
   A reprodução inicia imediatamente; clicar nela de novo a reinicia, o botão
   **Stop** do dock para a reprodução, e escolher um motion diferente faz
   cross-fade nele.
5. Alterne os interruptores de entrada ao vivo na barra de ferramentas para
   acionar o rig com suas próprias entradas — **Drag-track head** para virar a
   cabeça e os olhos para o cursor enquanto ele se move sobre o canvas,
   **Auto-blink** para fechamento cíclico dos olhos, **Auto idle**
   + **Idle motions** para respiração + clipes Idle aleatórios, **Mic lip-sync**
   para abertura da boca a partir do RMS do microfone, **Webcam tracking**
   para cabeça + olhos + boca completos do FaceLandmarker do MediaPipe.
6. **Reset to rest** na barra de ferramentas para todo motion, desativa todo
   driver ao vivo, limpa expressões / overrides de pose, e retorna todo
   parâmetro ao seu padrão — a ação canônica de "começar de novo".
7. Para abrir um rig diferente depois: **File > Open Puppet…** escolhe qualquer
   zip ``.puppet`` do disco; **File > Examples ▾** permanece vinculado à
   lista incluída.

Formato de arquivo ``.puppet`` (v1)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Um arquivo ``.puppet`` é um arquivo zip:

::

   my_character.puppet
   ├── puppet.json              # obrigatório — manifesto, drawables, deformadores, parâmetros
   ├── textures/
   │   ├── face.png             # referenciado por drawables[].texture
   │   └── body.png
   ├── motions/                 # opcional
   │   ├── idle.json
   │   └── wave.json
   ├── expressions/             # opcional
   │   └── smile.json
   └── physics.json             # opcional

Exemplo de ``puppet.json`` de nível superior::

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

A especificação completa (drawables, deformadores, parâmetros, motions, expressões,
pose, física) está em ``Imervue/puppet/FORMAT.md`` no repositório. Somente JSON +
PNG — sem binário proprietário, totalmente diff-vel via git.

O formato é aberto e verificável por máquina:

- Um ``.puppet`` salvo começa com uma entrada ``mimetype`` sem compressão contendo
  ``application/vnd.imervue.puppet+zip``, para que um programa possa reconhecê-lo pelos
  seus primeiros bytes, e todo arquivo JSON indica seu JSON Schema em ``$schema``.
- Quatro JSON Schemas (draft 2020-12) — ``puppet``, ``motion``, ``expression``
  e ``physics`` — estão publicados em ``docs/schemas/``; editores que seguem
  ``$schema`` verificam o arquivo enquanto ele é digitado.
- ``py -m Imervue.cli puppet-validate character.puppet`` (MCP
  ``puppet_validate``) verifica um arquivo contra os schemas, as regras do carregador
  e as verificações do rig; ``puppet-schema`` (MCP ``puppet_schema``) imprime um schema.
- ``docs/examples/read_puppet.py`` lê um ``.puppet`` usando apenas a biblioteca padrão
  do Python, como referência para outros programas; a especificação e os
  schemas têm licença MIT, então qualquer programa pode ler ou gravar o formato.
- Um arquivo de uma versão mais nova do formato é recusado informando a versão que usa, para que
  um Imervue mais antigo peça para ser atualizado em vez de lê-lo incorretamente.

Referência da Barra de Ferramentas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A barra de ferramentas traz **Examples ▾**, os seis toggles ao vivo, **Edit mesh**,
**Record…** e **Reset to rest**. Todas as outras entradas abaixo são itens dos
menus **File**, **Edit**, **Live**, **Output** ou **Tools**; esses menus também
contêm as entradas da barra de ferramentas.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Finalidade
   * - Open Puppet… / Examples ▾
     - Carrega um ``.puppet`` do disco (menu **File**), ou escolhe um dos rigs
       incluídos em ``examples/puppet/`` por **Examples ▾** (o botão da barra
       de ferramentas, também em **File**)
   * - Import PNG… / Import PSD… / Import Cubism…
     - Auto-mesh de um PNG, divisão por camadas de um PSD, ou
       sample-and-reconstruct de um rig Cubism. O seletor Cubism aceita
       tanto ``.moc3`` quanto ``.model3.json``; sem rig aberto, qualquer
       caminho executa a conversão completa ``.moc3 → .puppet`` (Cubism
       Native SDK fornecido pelo usuário). Escolher ``.model3.json`` com
       um rig carregado mescla seus metadados apenas-JSON (motions /
       expressões / física) no documento ativo.
   * - Recent
     - Reabrir rapidamente um puppet aberto recentemente
   * - Save As…
     - Gravar o rig atual como um zip ``.puppet``
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - Criar o rig a partir do menu **Edit**
   * - Drag-track head
     - A cabeça e os olhos se voltam para o cursor enquanto ele se move sobre o
       canvas: offset do cursor → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Ciclo cosseno close→open em ``ParamEyeLOpen`` / ``ParamEyeROpen``
       a cada ~4,5 s (caminho force-write ignora o no-change-skip do canvas
       para que drivers concorrentes não travem o piscar)
   * - Mic lip-sync
     - RMS do microfone → ``ParamMouthOpenY`` (requer ``sounddevice``)
   * - Lip-sync from Audio File…
     - Menu **Live**: transforma um WAV (PCM de 8, 16 ou 32 bits) em um motion
       chamado ``lipsync_<file>`` que abre ``ParamMouthOpenY`` conforme o
       volume, 30 vezes por segundo (chaves que não acrescentam nada são
       descartadas), e toca o WAV como seu som; substitui um motion com esse
       nome e é escolhido no dock **Motions**. Não precisa de dependência opcional
   * - Webcam tracking
     - FaceLandmarker da MediaPipe Tasks API → yaw / pitch / roll da cabeça +
       olhos + boca (requer ``opencv-python`` + ``mediapipe``;
       abre uma caixa de diálogo de pré-visualização ao vivo com landmarks detectados)
   * - Auto idle / Idle motions
     - Ciclo de respiração + drift em parâmetros padrão, mais ciclador
       aleatório opcional pelos motions do grupo Idle
   * - Edit mesh
     - Clique e arraste vértices do canvas para refinar a mesh
   * - Record motion
     - Somente no menu **Output**: captura mudanças de parâmetro em um novo
       ``Motion`` e o adiciona ao documento — bake-from-take, sem autoração
       manual de keys
   * - Capture frame… / Record… / Export all motions…
     - Salvar um único PNG, alternar gravação de GIF / WebM / MP4, ou
       renderizar em lote cada motion do rig em seu próprio arquivo (tudo via
       o mesmo caminho de render off-screen apenas-personagem usado para streaming).
       Um frame capturado mantém o tamanho próprio do rig (lado maior de no
       máximo 4096 px) sobre fundo transparente; uma gravação ou exportação em
       lote ajusta o personagem em 1080 px sobre branco, pois frames GIF / WebM /
       MP4 não têm alpha
   * - Output > Virtual camera / NDI output
     - Superfícies de streaming ao vivo — ver *Streaming ao vivo para o OBS* abaixo
   * - Reset to rest
     - Snap-stop do player de motion, desativa todo driver ao vivo,
       limpa expressões / grupos de pose, restaura padrões de parâmetro
   * - Fit to Window
     - Menu **Tools**: recentralizar + redimensionar o puppet no canvas
   * - Repair Rig
     - Menu **Tools**: em cada drawable, descartar triângulos quebrados e de
       área zero, mesclar vértices duplicados que compartilham posição e UV
       (uma costura de textura continua separada), remover vértices que
       nenhum triângulo usa — pesos de osso e morphs de vértice acompanham
       os vértices que permanecem — e fazer os pesos de osso de cada vértice
       somarem 1; a barra de status informa o que mudou

Gravando Seus Próprios Motions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Para capturar uma take customizada em vez de autorizar keyframes manualmente:

1. Alterne **Output > Record motion** — uma caixa de diálogo de nome aparece.
2. Enquanto grava, arraste sliders, habilite **Webcam tracking**, deixe a física
   rodar, qualquer coisa que escreva valores de parâmetro.
3. Desative **Record motion** — o gravador bake do stream capturado a 30 Hz
   em um ``Motion`` com uma trilha de segmento linear por parâmetro que
   efetivamente se moveu (parâmetros que ficaram parados são descartados).
   O novo motion aparece no dock **Motions** inferior imediatamente, pronto
   para reproduzir / repetir / salvar.

Motions customizados salvos dessa forma fazem round-trip pelo mesmo payload
JSON ``motions/<name>.json`` que os autorizados manualmente.

**Edit > Edit motion…** abre a linha do tempo do motion carregado no player:
arraste uma key ou uma alça de bézier, remodele a trilha escolhida com um
easing nomeado usando **Ease** e **Apply to Track** (31 curvas; elastic e
bounce viram 16 keys lineares por segmento), ou afine uma take de 30 Hz com
**Simplify Keys**, que descarta toda key que fica dentro da tolerância — uma
porcentagem do intervalo de cada parâmetro — da linha que passa pelas keys
vizinhas.

Streaming ao Vivo para o OBS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dois caminhos de saída, ambos renderizando o puppet sozinho (sem fundo de
checker, sem cromo do editor) em um framebuffer off-screen antes de entregá-lo
à superfície de streaming. O lado mais longo da saída é limitado a 1080 px
para que canvases nativos Cubism (muitas vezes com 3000–8000 px de altura) não sejam rejeitados
por drivers de câmera virtual DirectShow.

**A. Virtual Camera** — aparece como uma webcam na lista de fontes *Video
Capture Device* do OBS. ``pip install pyvirtualcam`` mais o driver de plataforma:
o OBS Studio 26+ inclui o driver *OBS Virtual Camera* no Windows / macOS
(clique em *Start Virtual Camera* no OBS uma vez para registrá-lo); o Linux usa
``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
O toggle de menu **Output > Virtual camera** abre o stream.

DirectShow / AVFoundation / v4l2loopback são apenas RGB — sem canal alfa — então
o Imervue preenche a área fora do personagem com **magenta #FF00FF** como uma
chave de croma. Remova-o no OBS via o filtro Color Key:

1. Clique com o botão direito na fonte Video Capture Device > **Filters**
2. **Effect Filters > + > Color Key**
3. Defina **Key Color Type** = ``Custom Color``,
   **Custom Color** = HEX ``FF00FF``,
   **Similarity** = ``80–300``,
   **Smoothness** = ``30–50``

O filtro permanece na fonte de modo que a chave de croma é reaplicada
automaticamente sempre que a câmera virtual é retomada.

**B. Saída NDI** — transmissão LAN sub-50 ms carregando RGBA, então OBS / vMix
compõem diretamente sobre suas próprias cenas sem passe de chave de croma.
``pip install ndi-python`` + o runtime
`NDI Tools <https://ndi.video/tools/>`_ + o plugin
`obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_.
O toggle de menu **Output > NDI output** transmite a fonte (nome
padrão *Imervue Puppet*).

O ``ndi-python`` traz apenas uma source distribution; o pip o constrói
a partir de C++ no momento da instalação. Usuários do Windows precisam do
Visual Studio Build Tools 2022 (com workload C++), CMake no PATH, e o NDI SDK
de <https://ndi.video/for-developers/ndi-sdk/> instalado no local padrão com
a variável de ambiente ``NDI_SDK_DIR`` apontando para ele.

Veja ``puppet_guide.md`` § 1.2 para o passo a passo completo mais a lista de
solução de problemas (câmera mostra magenta, falha de cmake do ndi-python,
estiramento da câmera virtual, etc.).

Dependências Opcionais
^^^^^^^^^^^^^^^^^^^^^^

* ``sounddevice`` — captura de microfone para sincronização labial
* ``opencv-python`` + ``mediapipe`` — rastreamento facial por webcam
* ``imageio-ffmpeg`` — gravação MP4 / WebM (já incluído para o Slideshow Video)
* ``pyvirtualcam`` — saída de câmera virtual (ver *Streaming ao vivo*)
* ``ndi-python`` — saída NDI (ver *Streaming ao vivo*)
* DLL Cubism Native SDK fornecida pelo usuário — conversão ``.moc3 → .puppet``
  (a Free Material License da Live2D proíbe redistribuição; os usuários
  colocam o SDK em ``<cwd>/sdk/`` ou definem a variável de ambiente ``CUBISM_CORE_DLL``)

A aba Puppet degrada graciosamente quando falta um pacote Python — a
alternância correspondente fica desligada e o instalador de dependências abre,
oferecendo a instalação; depois de instalado, a alternância volta a ligar. Uma
dica de texto só aparece quando o pacote está presente, mas o dispositivo ou o
driver falha. ``File > Install dependencies…`` instala em
lote cada pacote Python opcional de uma vez.

----

Espaço de Trabalho Desktop Pet (Aba Desktop Pet)
------------------------------------------------

Aba 5 — o **Desktop Pet** coloca qualquer personagem ``.puppet`` na
sua área de trabalho como uma sobreposição sem moldura e transparente.
A aba em si é um painel de controle; o personagem propriamente dito é
uma janela de nível superior separada que compartilha todo o runtime
do Puppet (motions, expressões, física, drivers de idle, entrada de
microfone / webcam). O pet pode reagir a cliques, executar animações
controladas por temporizador, seguir seu cursor, se ocultar enquanto
outro aplicativo estiver em tela cheia e falar linhas personalizadas
que você cria em um arquivo JSON.

Este capítulo é uma referência completa para a aba. Está organizado
como:

#. **Início rápido** — caminho de cinco passos, de "acabei de abrir o
   Imervue" até "tem um puppet na minha área de trabalho".
#. **Carregando um rig** — seletor de arquivos, exemplo incluído,
   restauração entre inicializações.
#. **A janela de sobreposição** — todo comportamento em nível de
   janela (arrastar para mover, encaixe em borda, click-through,
   trava de âncora, sempre no fundo, ocultar em tela cheia, pausar
   quando oculto, opacidade, tamanho, restauração multi-monitor).
#. **Modelo de interação** — áreas de acerto no clique esquerdo, menu
   de contexto completo no clique direito, bandeja do sistema.
#. **Drivers ao vivo** — sete drivers de entrada (três ligados por padrão)
   e suas dependências opcionais.
#. **Pet script** — o arquivo JSON que permite substituir a voz do pet
   por suas próprias linhas, agendar lembretes e vincular respostas
   por-área-de-acerto / por-motion.
#. **Persistência** — o que é lembrado entre inicializações e o
   esquema exato de configurações.
#. **Criando um novo pet** — ponteiro para a aba Puppet + o formato
   de arquivo ``.puppet``.
#. **Solução de problemas** — surpresas comuns e o que fazer a
   respeito.

Início rápido
^^^^^^^^^^^^^

1. Mude para a aba **Desktop Pet**.
2. Clique em **Load bundled Imeru** para usar o personagem
   incluído, ou em **Open Puppet…** para escolher seu próprio
   arquivo ``.puppet``.
3. A sobreposição aparece na sua área de trabalho e o checkbox
   **Show pet on desktop** é marcado automaticamente. (Se você quiser
   ocultar o pet sem fechar o Imervue, desmarque o checkbox ou use o
   ícone da bandeja do sistema.)
4. Arraste o personagem para onde você quiser. Solte perto de uma
   borda da tela para encaixar rente a ela.
5. Escolha os **Live drivers** que deseja — respiração de idle, blink,
   seguir cursor, lip-sync de microfone, rastreamento de webcam — a
   partir da aba do espaço de trabalho ou do menu de clique direito
   do pet.

Tudo que você configurar sobrevive à próxima inicialização, então o
passo 5 é uma decisão única por rig / persona.

Carregando um rig
^^^^^^^^^^^^^^^^^

A aba expõe três caminhos de carregamento:

* **Open Puppet…** — escolha qualquer arquivo ``.puppet`` do disco.
* **Load bundled Imeru** — abre o rig fornecido em
  ``examples/puppet/imeru.puppet``. O resolvedor procura em
  ``examples_dir()`` primeiro (ao lado do programa nos builds
  empacotados Nuitka / PyInstaller, a raiz do repositório em um
  checkout do código-fonte) e cai para uma busca relativa à pasta de
  trabalho atual.
* **Last rig** — o rig carregado anteriormente é restaurado
  automaticamente na inicialização do Imervue a partir do campo
  ``last_rig_path`` das configurações; a aba Desktop Pet
  re-instancia a sobreposição invisivelmente para que o pet esteja a
  um clique de distância do mesmo estado em que você o deixou.

Um carregamento bem-sucedido marca automaticamente **Show pet on
desktop** para que o pet apareça imediatamente. O caminho de falha
deixa o checkbox em paz e escreve o erro no rótulo de status da aba.

A janela de sobreposição
^^^^^^^^^^^^^^^^^^^^^^^^

O personagem vive em uma janela de nível superior, separada da janela
principal do Imervue. A janela é sem moldura, não tem entrada na
barra de tarefas e (por padrão) fica acima de qualquer outra janela.

.. list-table:: Comportamentos da janela
   :header-rows: 1
   :widths: 28 72

   * - Comportamento
     - Detalhe
   * - Sobreposição sem moldura
     - Sem cromo de janela, sem botões de minimizar / fechar, sem
       entrada na barra de tarefas. O personagem é toda a superfície
       visível.
   * - Fundo transparente
     - Tudo que o personagem não cobrir é totalmente transparente. A
       área de trabalho / aplicativo atrás do pet aparece pixel a
       pixel.
   * - Arrastar para mover
     - Pressione o botão esquerdo em qualquer lugar do corpo, arraste,
       solte. O arrasto é reconhecido como clique apenas se o cursor
       se moveu menos de seis pixels — mover mais longe transforma o
       gesto em movimento e o handler de clique não dispara.
   * - Encaixe em borda
     - Solte perto de uma borda da tela (padrão: dentro de 24 px) e o
       pet "estala" rente a essa borda. O limiar é configurável de 0
       (desligado) a 200 (muito grudento). O encaixe roda
       independentemente em cada eixo, então arrastar para um canto
       acopla nas duas bordas de uma vez.
   * - Clamp de excesso
     - Um arrasto que termina além de uma borda da tela é trazido de
       volta para dentro. Você não pode deixar o pet fora da tela
       onde não conseguiria pegá-lo de novo.
   * - Modo click-through
     - Quando habilitado, todo evento de mouse atravessa o pet até o
       que estiver atrás. O personagem ainda é visível, mas não pode
       ser arrastado, clicado com o botão direito ou usado para
       disparar motions. Ative quando o pet for puramente decorativo.
   * - Travar posição
     - Desativa o arrastar-para-mover sem afetar o click-through.
       Útil quando você colocou o pet exatamente onde queria e não
       quer que arrastos acidentais o movam.
   * - Sempre no fundo
     - Inverte o pet de sempre-no-topo para sempre-no-fundo. O pet
       fica atrás de todas as outras janelas como um widget de área
       de trabalho. Também desativa a flag de aceitação de foco, então
       clicar no pet não o eleva.
   * - Ocultar em tela cheia
     - Um polling em segundo plano a 1 Hz observa a janela em primeiro
       plano no monitor do pet. Quando essa janela cobre ≥ 99 % da
       tela com uma tolerância por-borda ≤ 4 px (capturando tanto
       tela cheia real quanto jogos em janela sem borda), o pet se
       oculta automaticamente. Quando a tela cheia termina, o pet
       reaparece na posição anterior. O detector usa a API Win32
       ``GetWindowRect`` no Windows; no macOS / Linux ele faz no-op
       graciosamente (o pet permanece visível).
   * - Pausa quando oculto
     - O tick de pintura de ~30 FPS, o tick de script de 1 Hz e o
       polling de tela cheia (a menos que a tela cheia seja o que
       ocultou o pet) param em ``hideEvent`` e retomam no próximo
       ``showEvent``. Os timers dos drivers ao vivo (blink, idle,
       idle motions, olhar) continuam rodando.
   * - Tamanhos predefinidos
     - Pequeno (200 × 300), médio (320 × 480), grande (480 × 720). O
       pet redimensiona em torno do seu centro atual, então uma
       mudança de tamanho não o realoca. O encaixe roda novamente
       após o redimensionamento.
   * - Slider de opacidade
     - 10 – 100 %. Atua no nível da janela (via ``setWindowOpacity``),
       então o pet inteiro desbota, não apenas a textura. O piso
       mínimo de 10 % existe para que você sempre possa ver e pegar
       o pet — totalmente invisível faria você o perder.
   * - Memória de posição
     - O ``(x, y)`` pós-encaixe após cada soltura é persistido,
       junto com o monitor em que ele está. Na próxima inicialização
       o pet retorna a essa posição, limitada ao interior desse
       monitor. Se o monitor não existir mais (você o desconectou
       desde a última inicialização), o pet vai para a primeira tela
       com a posição salva limitada ao interior dela. O canto
       inferior direito só é usado quando nenhuma posição foi salva.

Modelo de interação
^^^^^^^^^^^^^^^^^^^

O pet responde à entrada do mouse via três canais independentes.

**Clique esquerdo no corpo**

A posição do clique é mapeada de volta para coordenadas do canvas do
puppet (desfazendo o pan / zoom do canvas) e passa pelo pipeline
existente de ``hit_test``. O resultado dirige o comportamento da
seguinte forma:

#. Se um ``HitArea`` cobre o drawable clicado E essa área tem uma
   motion anexada, a motion é reproduzida.
#. Independentemente de uma motion ter sido reproduzida, o pet pode
   abrir um balão de fala — veja a seção *Pet script* para a
   prioridade de escolha de linha.
#. Se nenhuma área de acerto cobre o clique, o pet cai para uma
   saudação (da lista ``greetings`` do script ou da saudação
   embutida).

Um gesto de arrastar-para-mover suprime o handler de clique, então
mover o pet não abre um balão de fala. Pressionar reproduz uma motion
do grupo ``Drag`` do rig e soltar após um arrasto reproduz uma do
grupo ``Land``, quando o rig tem esses grupos.

**Clique direito em qualquer lugar do corpo**

Abre um menu de contexto com a seguinte estrutura:

* **Hide pet** — ação de nível superior que fecha a sobreposição.
* Submenu **Live drivers** — sete toggles marcáveis (Auto idle, Idle
  motions, Auto-blink, Drag-track head, Mouse gaze, Mic lip-sync,
  Webcam tracking). O estado de marcação espelha o estado dos drivers
  ao vivo, então o menu mostra o que está rodando no momento.
* Submenu **Play motion** — populado a partir da lista
  ``document.motions`` do rig ativo. Selecionar uma entrada
  reproduz essa motion; ela não fala nenhuma linha de
  ``motion_lines`` (essas respondem apenas a um clique em área de
  acerto).
* Submenu **Apply expression** — populado a partir de
  ``document.expressions`` do rig. Cada entrada fica marcada enquanto
  sua expressão está ativa; selecionar uma adiciona a sobreposição de
  parâmetros da expressão e selecioná-la de novo a remove.
* Submenu **Pose** — um submenu por pose group do rig (rotulado com o
  nome de exibição do grupo ou, se não houver, com seu id), listando os
  membros do grupo; o membro exibido fica marcado e selecionar outro o
  exibe no lugar. Fica desabilitado quando o rig não tem pose groups.
* Cinco toggles marcáveis de nível superior: **Lock position**,
  **Click-through**, **Always on bottom**, **Hide on fullscreen**,
  **Speech bubble** — acesso rápido aos mesmos toggles na aba do
  espaço de trabalho.
* Submenu **Size** — Pequeno / Médio / Grande; o preset atual está
  marcado.

Os submenus de motion / expression ficam desabilitados quando nenhum
rig está carregado.

**Ícone da bandeja do sistema**

Um ícone na bandeja (instanciado apenas em plataformas que reportam
suporte a bandeja) fornece uma quarta superfície para as ações mais
comuns:

* Clique esquerdo alterna a visibilidade do pet.
* Clique direito abre um menu com **Show pet** (marcável),
  **Click-through**, **Open puppet…**, **Hide pet**.
* Os itens marcáveis Show / Click-through espelham o estado de
  marcação do espaço de trabalho via ``sync_visibility`` /
  ``sync_click_through``, então eles permanecem sincronizados onde
  quer que o usuário alterne o switch correspondente.

Drivers ao vivo
^^^^^^^^^^^^^^^

Cada driver ao vivo é criado preguiçosamente na primeira ativação,
então um pet dormente paga zero custo de timer / thread para drivers
que você nunca liga. O estado de cada driver é persistido; ligar,
fechar o Imervue e relançar restaura o rig com os mesmos drivers
rodando. A sobreposição em si só aparece na inicialização quando
**Show the pet when Imervue starts** está marcado no grupo Window
da aba.

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - Driver
     - O que faz
     - Dependência opcional
   * - **Auto idle**
     - Respiração + deriva sutil em parâmetros padrão
       (``ParamBreath`` etc.) para que o personagem pareça vivo
       quando nada mais estiver animando.
     - nenhuma
   * - **Idle motions**
     - Escolhe aleatoriamente uma motion do grupo ``Idle`` do rig e
       a reproduz — uma logo ao ligar, depois a cada poucos segundos.
       Dá passagem enquanto uma motion que não é Idle está tocando.
     - nenhuma
   * - **Auto-blink**
     - Fecha e reabre os olhos em uma curva cosseno suave a cada
       ~4,5 s. O driver força a escrita do parâmetro para que outros
       drivers que mexem em valores de abertura de olhos não
       suprimam o blink.
     - nenhuma
   * - **Drag-track head**
     - A cabeça + olhos viram em direção ao cursor enquanto ele se
       move sobre o pet. Dirige
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - nenhuma
   * - **Mouse gaze**
     - Os olhos e a cabeça seguem o cursor em qualquer lugar da tela,
       em relação ao centro do pet (os olhos vão à frente). Dirige os
       mesmos quatro parâmetros.
     - nenhuma
   * - **Mic lip-sync**
     - A amplitude RMS do microfone dirige ``ParamMouthOpenY``. A
       boca abre proporcional ao volume da sua voz, então o personagem
       parece estar falando quando você fala.
     - ``sounddevice``
   * - **Webcam tracking**
     - O MediaPipe FaceLandmarker lê sua webcam a ~30 FPS e dirige a
       pose da cabeça + parâmetros de abertura de olhos + abertura de
       boca. Nenhuma janela de pré-visualização abre para o pet (a
       pré-visualização da câmera pertence à aba Puppet).
     - ``opencv-python`` + ``mediapipe``

Os dois drivers com dep opcional degradam graciosamente: se o pacote
necessário não estiver instalado, alternar o checkbox volta para o
desligado e o rótulo de status do espaço de trabalho mostra uma dica
"install sounddevice" / "install opencv-python + mediapipe".

Pet script — voz personalizada e eventos agendados
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O balão de fala do pet recorre a um arquivo JSON que você pode criar
e carregar pelo grupo **Pet script** na aba. O script governa cinco
coisas:

* **Greetings** — linhas padrão de clique quando nada mais específico
  combina.
* **Time-of-day greetings** — saudações para a faixa do relógio local
  (``morning`` 05–11 h, ``afternoon`` 12–17 h, ``evening``
  18–21 h, ``night`` 22–04 h), usadas antes das saudações simples;
  uma faixa sem linhas recorre a elas.
* **Hit-area responses** — buckets de linha por ``HitArea.id``.
* **Motion lines** — buckets de linha por nome-de-motion, faladas
  quando um clique em área de acerto reproduz essa motion (não
  quando uma motion é iniciada pelo menu de contexto).
* **Scheduled chimes** — linhas controladas por temporizador que
  disparam a cada ``every_seconds`` de tempo monotônico de relógio.

Esquema (versionado — campos futuros são compatíveis para frente):

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

Regras de carregamento:

* Listas são amostradas em round-robin por bucket para que o usuário
  não veja a mesma linha duas vezes seguidas.
* Chaves de nível superior desconhecidas são ignoradas (compatível
  para frente — um futuro arquivo v2 ainda carrega em um runtime v1).
* Entradas de lista inválidas (tipo errado, entradas agendadas
  malformadas, ``every_seconds`` zero / negativo) são puladas — uma
  linha ruim não faz o carregamento inteiro falhar. Apenas JSON
  totalmente não parseável levanta um erro e expõe o caminho no
  rótulo de status.
* A cascata de hit-area / motion / greeting é em camadas: um clique
  esquerdo consulta primeiro ``hit_responses[area.id]``, depois
  ``motion_lines[area.motion]``, depois ``time_of_day_greetings``,
  depois ``greetings``, depois o conjunto de saudações padrão embutido
  como piso.
* O rastreamento de tempo usa ``time.monotonic`` para que suspender o
  notebook ou pular o relógio do sistema não possa disparar em
  excesso eventos enfileirados.

**Reset to default** descarta o script do usuário e reverte para o
conjunto de saudações embutido; o caminho persistido do script é
limpo para que a próxima inicialização não o recarregue.

Um exemplo funcional vive em
``examples/desktop_pet/imeru.petscript.json`` — seis saudações,
uma linha para cada período do dia, dois buckets de hit-area
(``Head`` / ``Body``), linhas para cinco motions (wave / greet /
surprised / sleepy / shy) e um lembrete de alongamento a cada 30
minutos. Os nomes dos buckets são as hit areas da Imeru, então a
cabeça e o corpo dela respondem a cliques; um rig cujas hit areas
usam os nomes do Cubism (``HitAreaHead`` / ``HitAreaBody``)
precisa de buckets com esses nomes.

Persistência
^^^^^^^^^^^^

Todo estado do Desktop Pet faz round-trip através de
``user_setting_dict["desktop_pet"]`` (um slot no arquivo padrão de
configurações de usuário do Imervue). Cada campo tem um padrão +
clamp de intervalo no carregamento, então um arquivo de configurações
corrompido não pode travar o lançamento.

.. list-table:: Campos persistidos
   :header-rows: 1
   :widths: 28 18 54

   * - Campo
     - Padrão
     - Notas
   * - ``last_rig_path``
     - ``""``
     - Restaurado automaticamente na inicialização se o arquivo
       ainda existir.
   * - ``script_path``
     - ``""``
     - Restaurado automaticamente na inicialização se o script ainda
       fizer parse; um script ilegível reverte para os padrões
       silenciosamente.
   * - ``position``
     - ``[-1, -1]``
     - Coordenada de tela ``(x, y)`` da última soltura de arrasto.
       ``-1, -1`` (nunca salvo) significa "use o canto inferior
       direito". Quando o monitor salvo não existe mais, a posição é
       limitada ao interior da primeira tela.
   * - ``size_preset``
     - ``"medium"``
     - Um de ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Valores fora do intervalo são restringidos a ``[0.1, 1.0]``;
       só um valor não numérico volta para o padrão.
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - Mutuamente exclusivo com sempre-no-topo.
   * - ``hide_on_fullscreen``
     - ``true``
     - Defina como ``false`` para manter o pet visível durante tela
       cheia.
   * - ``snap_threshold``
     - ``24``
     - Restringido a ``[0, 200]`` px.
   * - ``drivers``
     - ``auto_idle``, ``idle_motion``, ``auto_blink``
       ``true``; os demais ``false``
     - Sub-dict com chaves por id de driver (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mouse_gaze``, ``mic_lipsync``, ``webcam_tracking``).
       Chaves desconhecidas fazem round-trip intactas para
       compatibilidade para frente.
   * - ``show_on_launch``
     - ``false``
     - Definido por **Show the pet when Imervue starts** no grupo
       Window da aba. O rig e os drivers são restaurados na
       inicialização de qualquer forma; a sobreposição só aparece
       quando isto está ligado.
   * - ``speech_enabled``
     - ``true``
     - Quando false o balão de fala nunca aparece.
   * - ``hotkeys_enabled``
     - ``false``
     - Definido por **Enable global hotkeys (needs pynput)** no grupo
       Global hotkeys da aba.
   * - ``hotkeys``
     - ``{}``
     - Substituições ``{action: key}`` dos padrões ``ctrl+shift+p``
       (mostrar / esconder), ``ctrl+shift+l`` (travar), ``ctrl+shift+t``
       (click-through) e ``ctrl+shift+space`` (falar agora), definidas
       pelos campos de tecla do grupo Global hotkeys. Uma tecla que outra
       ação já usa é recusada ali; teclas salvas que duas ações
       compartilham são indicadas na linha de status quando a aba abre.

O comportamento de merge do dict de configurações é de um nível de
profundidade: arquivos de configurações mais antigos sem chaves mais
novas ainda produzem um dict de estado completo no carregamento (os
padrões preenchem as lacunas); chaves mais novas que você salvou
sobrevivem a um downgrade para um runtime mais antigo que não as
conhece.

Criando um novo pet
^^^^^^^^^^^^^^^^^^^

Qualquer arquivo ``.puppet`` funciona como um personagem de Desktop
Pet — a aba Desktop Pet é puramente uma camada de renderização +
interação; a criação de rigs acontece na aba Puppet (veja *Espaço de
Trabalho Puppet (Aba Puppet)*).

Para criar seu próprio rig de pet:

#. Mude para a aba Puppet e importe uma arte via **File > Import
   PNG…** ou **File > Import PSD…**, ou puxe um modelo Cubism via
   **File > Import Cubism…**.
#. Crie deformadores de rotação / warp, parâmetros, motions,
   expressões e (opcionalmente) áreas de acerto vinculadas a partes
   do corpo para que o handler de clique esquerdo do Desktop Pet
   possa disparar motions.
#. Salve o rig via **File > Save As…** em um zip ``.puppet``.
#. Volte para a aba Desktop Pet e carregue o novo arquivo via
   **Open Puppet…**.

Se seu rig define entradas ``HitArea``, você pode criar linhas de
balão de fala por área de acerto em um ``.petscript.json`` cujas
chaves ``hit_responses`` combinam com os ids das áreas.

Plugin de integrações
^^^^^^^^^^^^^^^^^^^^^

O plugin **Desktop Pet Integrations** (``Plugins`` > ``Download Plugins``, categoria
``plugins``, nome ``pet_integrations``) faz o pet reagir ao mundo exterior. Ele adiciona
``Plugins`` > ``Desktop Pet Integrations`` com uma entrada por integração e uma entrada
``Settings…`` para as opções delas; uma entrada pode ser ativada depois que o pet foi exibido,
instala antes o pacote opcional de que precisa e continua ativada entre reinicializações. Ele
também é o exemplo completo de um plugin que estende o pet — veja *Escrevendo Plugins* e
``on_pet_created``.

.. list-table::
   :header-rows: 1
   :widths: 22 56 22

   * - Integração
     - O que o pet faz
     - Requisitos
   * - Reagir a eventos do OBS
     - Toca uma motion do grupo ``Stream``, ``Record`` ou ``Scene`` quando a transmissão ou a
       gravação começa ou para, ou quando a cena muda. Defina o host, a porta e a senha do servidor
       WebSocket do OBS em ``Settings…``
     - ``obs-websocket-py`` (instalado no primeiro uso); OBS com o servidor WebSocket ativado
   * - Reagir ao chat da Twitch
     - Entra no chat de um canal e toca o grupo de motions mapeado para uma palavra-chave sempre
       que uma mensagem a contém (sem diferenciar maiúsculas de minúsculas; linhas
       ``keyword = Group`` em ``Settings…``). ``=hi`` só corresponde a uma mensagem que seja
       exatamente "hi", ``!dance*`` a uma que comece com "!dance", ``/go+al/`` a uma expressão
       regular; vence a primeira linha que corresponder
     - Um nome de canal e um token ``oauth:``
   * - Webhook local (127.0.0.1)
     - Escuta em ``http://127.0.0.1:9876/trigger`` (porta em ``Settings…``) um POST JSON
       ``{"group": "Wave", "speech": "Hi!"}`` — qualquer um dos campos pode ser omitido — vindo de
       scripts, do Stream Deck ou de ferramentas de automação. Com um token definido, as
       requisições precisam enviar ``Authorization: Bearer <token>``; requisições vindas de uma
       página web são recusadas
     - Nada extra
   * - Reagir a notificações do Windows
     - Toca o grupo ``Notify`` e fala o título da notificação quando outro app exibe uma
       notificação do Windows; apps listados nos ids de app ignorados são pulados. O Windows pede
       acesso às notificações na primeira vez
     - Windows; os pacotes de notificação ``winrt`` (instalados no primeiro uso)

Um rig reage apenas aos grupos de motions que possui; um grupo ausente não toca nada.

Solução de problemas
^^^^^^^^^^^^^^^^^^^^

**O pet aparece dentro de um retângulo cinza em vez de ser totalmente
transparente.** O atributo de fundo translúcido em nível de SO
requer uma superfície GL ciente de alfa mais atributos correspondentes
no widget GL incorporado. Certifique-se de que nenhuma ferramenta de
gerenciamento de janelas de terceiros esteja sobrepondo o atributo
``WA_TranslucentBackground`` na janela de sobreposição (alguns
gerenciadores de janelas personalizados no Linux fazem isso). No
Windows / macOS isso deve "simplesmente funcionar".

**"Load bundled Imeru" reporta que o arquivo não foi encontrado.**
O resolvedor consulta primeiro ``examples_dir()`` (a localização
segura para congelamento usada por builds empacotados) e cai para um
caminho relativo ao CWD. Se nenhum dos dois contiver o rig, o rótulo
de status expõe o caminho esperado. Verifique se o diretório
``examples/`` foi enviado com sua instalação — para checkouts do
fonte, inicie o Imervue a partir da raiz do repositório.

**O pet não fala quando clicado.** Três verificações:

#. Certifique-se de que o toggle **Speech bubble on click** está
   ligado (na aba ou no menu de clique direito).
#. Se você carregou um script personalizado, verifique se o JSON faz
   parse — o rótulo de status da aba mostra o erro de carregamento.
#. Se **Click-through** estiver ligado, o clique vai para a janela
   atrás do pet; desligue-o na aba ou no menu da bandeja. (Com a fala
   ligada, todo clique recebe uma linha: um rig sem áreas de acerto
   não reproduz motion, mas o clique ainda cumprimenta você.)

**O checkbox de webcam tracking volta para o desligado.** O
rastreamento de webcam precisa de ``opencv-python`` e ``mediapipe``
instalados no mesmo ambiente Python em que o Imervue está rodando.
Instale com ``pip install opencv-python mediapipe``. Depois de
instalar, marque o checkbox de novo. O pet não abre janela de
pré-visualização; para ver o que a câmera detecta, ligue **Webcam
tracking** na aba Puppet, que mostra os marcos faciais.

**O pet não se oculta automaticamente durante apps em tela cheia.** O
detector de tela cheia faz polling da janela em primeiro plano a
1 Hz. No Windows ele usa a API Win32 ``GetWindowRect``; no macOS /
Linux não há um equivalente multi-plataforma confiável e ele faz
no-op (o pet permanece visível). Para Windows: certifique-se de que
**Hide when other app is fullscreen** está marcado e verifique se a
janela em tela cheia realmente cobre ≥ 99 % do mesmo monitor do pet.

**A posição do pet flutua para fora da tela entre inicializações.**
Isso acontece quando a tela em que o pet estava não está mais
conectada na próxima inicialização (dock de notebook, segundo monitor
desconectado). Neste caso o pet vai para a primeira tela com a
posição salva limitada ao interior dela — arraste-o para onde você
quiser e o próximo salvamento sobrescreverá a posição desatualizada.

----

Rotação e Inversão
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Ação
     - Atalho
     - Menu
   * - Rotacionar 90 ° horário
     - ``R``
     - Botão direito > Modify > Rotate Clockwise
   * - Rotacionar 90 ° anti-horário
     - ``Shift + R``
     - Botão direito > Modify > Rotate Counter-clockwise
   * - Inverter horizontal
     - --
     - Botão direito > Modify > Flip Horizontal
   * - Inverter vertical
     - --
     - Botão direito > Modify > Flip Vertical
   * - Rotação sem perdas
     - --
     - Botão direito > Lossless Rotate > Lossless Rotate CW / CCW. Só um JPEG é realmente
       sem perdas (sua tag de orientação muda); PNG / BMP / TIFF / WebP /
       GIF são decodificados, girados e salvos de novo (um WebP com perdas é recodificado);
       RAW de câmera, HEIC e arquivos de vários quadros são recusados

----

Exportando Imagens
------------------

Exportação Única
^^^^^^^^^^^^^^^^

Abra uma imagem (Deep Zoom) e clique com o botão direito > ``Exportar / Salvar Como``.

- Escolha o formato: PNG, JPEG, WebP, BMP, TIFF; AVIF quando o Pillow tem suporte a AVIF, HEIC e JPEG XL quando ``pillow-heif`` / ``pillow-jxl-plugin`` está instalado
- Ajuste a qualidade (para formatos com perdas)
- Escolha os metadados a manter: todos, todos menos a localização (padrão) ou nenhum. Câmera, lente e data de captura são mantidas; a escolha é lembrada e a exportação em lote oferece a mesma opção
- Pré-visualize o tamanho estimado do arquivo
- Escolha um local para salvar. O nome sugerido é um ainda livre (``photo_1.png`` ao lado de ``photo.png``); um arquivo existente — sobretudo a própria foto — só é substituído após confirmação

Presets de Exportação
^^^^^^^^^^^^^^^^^^^^^

A Exportação em Lote (abaixo) tem uma lista **Preset** que preenche o tamanho, o formato e a
qualidade para destinos comuns; **Custom** deixa essas escolhas com você:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Preset
     - Saída
   * - **Web — 1600 px JPEG**
     - Lado maior até 1600 px, JPEG qualidade 85.
   * - **4K Web — 3840 px JPEG**
     - Lado maior até 3840 px, JPEG qualidade 90.
   * - **Print — 300 DPI PNG**
     - Resolução total, PNG, 300 dpi.
   * - **Instagram — 1080×1080 square**
     - Recorte quadrado central, 1080 × 1080, JPEG qualidade 90.
   * - **Thumbnail — 400 px JPEG**
     - Lado maior até 400 px, JPEG qualidade 80.

Marca d'Água
^^^^^^^^^^^^

A Exportação em Lote também pode desenhar uma marca d'água de texto em cada cópia exportada:
o texto, sua posição (um canto ou o centro) e sua opacidade. Os arquivos originais nunca são
alterados.

Exportação em Lote
^^^^^^^^^^^^^^^^^^

Selecione várias imagens, depois clique com o botão direito > ``Operações em Lote`` > ``Exportação em Lote``.

- Conversão uniforme de formato
- Definir largura / altura máximas (escala automática de proporção)
- Controle de qualidade
- Barra de progresso em tempo real
- **Render on**: a CPU, ou uma GPU dedicada quando o plugin GPU Develop está instalado (abaixo)

Plugin GPU Develop
^^^^^^^^^^^^^^^^^^

O plugin **GPU Develop** (``Plugins`` > ``Download Plugins``, categoria ``plugins``, nome
``gpu_develop``) permite que a Exportação em Lote renderize receitas de revelação em uma GPU dedicada.
``Plugins`` > ``GPU Develop…`` instala o ``wgpu`` na primeira vez e depois informa a GPU que vai
usar; a Exportação em Lote passa então a mostrar **Render on** com essa GPU escolhida (escolha
**CPU** para renderizar como antes).

- Balanço de branco, exposição, realces / sombras, brancos / pretos, brilho, contraste, vibração, saturação e a curva tonal rodam na GPU; rotação, espelhamentos, o recorte e tudo o que vem depois da curva tonal (split toning, LUT, máscaras, níveis e o restante) ficam na CPU
- Uma foto de 24 MP leva cerca de 0,1 s na GPU em vez de cerca de 7 s na CPU, sem contar a decodificação e o salvamento
- Só uma GPU dedicada é usada, nunca uma GPU integrada nem um renderizador por software; no Windows, primeiro via Vulkan e depois via Direct3D 12
- Uma imagem em que a GPU falha é renderizada na CPU, então a exportação ainda é concluída
- A saída coincide com a do renderizador de CPU com diferença de poucos níveis em uma pequena parcela dos pixels

Criar GIF / Vídeo
^^^^^^^^^^^^^^^^^

Selecione várias imagens, depois clique com o botão direito > ``Operações em Lote`` > ``Criar GIF / Vídeo``.

- Saída GIF e MP4; o MP4 usa o ffmpeg do PATH, senão o que vem com a dependência padrão ``imageio-ffmpeg``
- Arraste para reordenar quadros
- Defina quadros por segundo (FPS)
- Dimensões personalizadas
- Opção de loop: repetir sem fim ou, se desligada, tocar uma vez
- O arquivo sugerido é ``output.gif`` ao lado do primeiro quadro, numerado (``output_1.gif``) se esse nome estiver ocupado; um nome digitado que já existe só é substituído após confirmação

----

Reprodução de Animação
----------------------

Ao abrir arquivos GIF, APNG ou WebP animados, a animação é reproduzida automaticamente. Uma animação que ocuparia
mais de 512 MB decodificada é decodificada quadro a quadro durante a reprodução, então
abri-la não congela a janela nem enche a memória.
Um quadro de 10 ms ou menos é exibido por 100 ms, como nos navegadores: muitos GIFs contam com isso.

Um TIFF de várias páginas — um documento digitalizado — não é reproduzido: mostra uma página por vez, virada com ``,`` e ``.``, e o indicador mostra o número da página. Quadros que não são animação também nunca são reproduzidos: a prévia que a câmera embute no JPEG (MPF), as camadas de um PSD e a imagem padrão de um APNG, a imagem estática para programas sem suporte a APNG.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``Space``
     - Reproduzir / Pausar
   * - ``,``
     - Quadro anterior
   * - ``.``
     - Próximo quadro
   * - ``]``
     - Acelerar
   * - ``[``
     - Desacelerar

----

Comparação de Imagens
---------------------

No modo de miniaturas, selecione 2 ou 4 imagens, depois clique com o botão direito > ``Comparar Imagens``
(ou escolha-as na lista da caixa de diálogo).

A caixa de diálogo tem quatro abas:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Aba
     - Finalidade
   * - **Lado a lado**
     - Exibir 2 ou 4 imagens simultaneamente; cada uma é redimensionada automaticamente em seu painel.
   * - **Sobreposição**
     - Misturar duas imagens com um slider de alfa (0 → apenas A, 100 → apenas B). Requer exatamente 2 selecionadas.
   * - **Diferença**
     - Visualização ``|A − B|`` por pixel com um slider de ganho (0,10× – 20×) para amplificar mudanças sutis.
   * - **Divisão A | B**
     - Visualização dividida antes / depois com um divisor vertical arrastável. Arraste o handle para varrer entre as duas
       imagens; ideal para mostrar ajustes de receita de revelação ou comparar exportações. Requer exatamente 2 selecionadas.

Quando as duas imagens têm tamanhos diferentes, ``B`` é reamostrada para as dimensões de ``A`` com Lanczos. Imagens muito grandes
são limitadas a 2048 px no lado maior internamente para que a sobreposição / diferença permaneçam interativas.

.. seealso::
   Para comparação inline sem abrir uma caixa de diálogo, use **Visão Dividida** (``Shift + S``) ou
   **Leitura em Página Dupla** (``Shift + D`` / ``Ctrl + Shift + D``) descritas na seção Navegação.

----

Slideshow
---------

Pressione ``S`` ou clique com o botão direito > ``Slideshow`` para iniciar um slideshow automático.

- Intervalo ajustável por imagem
- Transição opcional de fade entre imagens

----

Pesquisa
--------

Pressione ``Ctrl + F`` ou ``/`` e digite uma palavra-chave para pesquisar imagens na pasta atual por nome de arquivo.

A pesquisa usa **correspondência aproximada (fuzzy)** com um ranqueamento em três níveis (prefixo > substring > subsequência) e
**destaque de substring** nos resultados. Pressione ``Enter`` ou clique duas vezes para saltar para uma imagem.

Para saltar por **índice de imagem** em vez de nome, pressione ``Ctrl + G`` para a caixa de diálogo Ir Para.

----

Copiar e Colar
--------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Ação
     - Método
   * - Copiar imagem para a área de transferência
     - ``Ctrl + C`` no modo Deep Zoom
   * - Colar imagem da área de transferência
     - ``Arquivo`` > ``Colar da Área de Transferência`` a abre no editor de anotações (nada é salvo);
       ``Ctrl + V`` a salva como ``pasted_<timestamp>.png`` na pasta atual e a abre, ou
       abre um caminho de arquivo copiado para a área de transferência
   * - Monitoramento automático da área de transferência
     - ``Arquivo`` > ``Anotar Automaticamente Imagens da Área de Transferência`` (alternar)

.. note::
   Quando o monitoramento automático está habilitado, toda vez que uma nova imagem aparece na área de transferência (por exemplo, de uma ferramenta de captura de tela), o editor de anotações abre automaticamente.

----

Excluindo Imagens
-----------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Ação
     - Método
   * - Excluir imagem atual
     - Pressione ``Delete``
   * - Excluir imagens selecionadas
     - Selecione várias, depois ``Delete`` ou clique com o botão direito > ``Excluir Imagens Selecionadas``

As imagens são movidas para a Lixeira do sistema e podem ser recuperadas de lá. Numa
unidade sem lixeira — cartão de memória, pendrive ou unidade de rede, onde o Windows
apagaria de vez — o arquivo é mantido: ao fechar, o Imervue lista esses arquivos e
pergunta se deve excluí-los definitivamente.

Os sidecars vão junto: ``IMG.JPG.xmp``, ``IMG.JPG.annotations.json`` e
``IMG.xmp``, a menos que o RAW de um par RAW + JPEG ainda use este último. Um
sidecar deixado para trás grudaria a avaliação e as edições no próximo ``IMG.*``
que a câmera gravar com o mesmo nome.

----

Operações em Lote
-----------------

No modo de miniaturas, selecione várias imagens e clique com o botão direito > ``Operações em Lote``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Recurso
     - Descrição
   * - Renomear em Lote
     - Renomear usando templates: ``{name}``, ``{n}``, ``{ext}``
   * - Mover / Copiar
     - Mover ou copiar imagens para outra pasta
   * - Rotacionar Todas
     - Rotacionar todas as imagens selecionadas de uma vez
   * - Exportação em Lote
     - Converter formato e redimensionar em massa
   * - Criar GIF / Vídeo
     - Animar a seleção como GIF ou MP4 (veja *Criar GIF / Vídeo*)
   * - Marcar por Localização
     - Adicionar a cidade e o país mais próximos de cada foto georreferenciada às palavras-chave XMP dela
   * - Indexar Palavras-chave
     - Adicionar as palavras-chave XMP da seleção à biblioteca
   * - Descarte Automático de Desfocadas
     - Marcar as fotos desfocadas como Reject
   * - Descarte Automático de Baixa Qualidade
     - Marcar o quarto mais fraco da seleção (nitidez, exposição, contraste) como Reject
   * - Rotação Automática por EXIF
     - Salvar uma cópia PNG na orientação correta de cada foto como ``<name>_oriented.png``
   * - Combinar em PDF / TIFF…
     - Colocar a seleção, na ordem de exibição, em um único PDF ou TIFF de várias páginas
   * - Importar para Pastas por Data…
     - Copiar a seleção para pastas ``YYYY/MM`` pela data de captura (EXIF, senão a data do arquivo);
       um arquivo que já está lá mantém o nome e o recém-chegado recebe ``_1``
   * - Adicionar à Tag
     - Aplicar a mesma tag a todas as imagens selecionadas
   * - Adicionar ao Álbum
     - Colocar todas as imagens selecionadas em um álbum

Mover ou copiar nunca sobrescreve um arquivo de mesmo nome: ele chega como
``name_1.ext``. Uma foto renomeada ou movida no Imervue — renomeação em lote,
renomeação por tokens, árvore de pastas, Mover / Copiar, painel duplo, bandeja de
preparação, organizador de imagens — mantém a avaliação, o favorito, as tags, o
rótulo de cor, o título, a descrição, a nota da biblioteca e a marcação de
seleção (uma pasta renomeada ou movida, as de todas as suas fotos). Os sidecars
vão junto: ``IMG.xmp``, ``IMG.JPG.xmp`` e ``IMG.JPG.annotations.json``. Um
``IMG.xmp`` que o RAW de um par RAW + JPEG ainda usa é copiado em vez de movido.

Uma foto renomeada em outro programa enquanto a pasta está aberta no Imervue
mantém os mesmos dados; os dados que o novo nome já tinha ficam como estão.

----

Histograma RGB
--------------

Pressione ``H`` no modo Deep Zoom para sobrepor um histograma RGB na imagem. Pressione novamente para ocultar.

----

Definir como Papel de Parede
----------------------------

Clique com o botão direito no modo Deep Zoom > ``Definir como Papel de Parede`` para definir a imagem atual como papel de parede da área de trabalho.

Suportado no Windows, macOS e Linux (GNOME).

O Windows deixa a área de trabalho preta, e ainda informa sucesso, quando recebe um arquivo que não consegue decodificar. Por isso, uma imagem que não é JPEG, PNG nem BMP — RAW de câmera, HEIC, PSD, TGA, WebP e os demais formatos que o Imervue abre — e uma foto que precisa ser endireitada são entregues como uma cópia JPEG do que o visualizador mostra. A cópia fica em ``%LOCALAPPDATA%\Imervue\wallpaper`` (``~/.local/share/imervue/wallpaper`` no macOS e no Linux); só a mais recente é mantida.

----

Múltiplas Janelas
-----------------

``Arquivo`` > ``Nova Janela`` abre outra janela independente do Imervue. Cada janela pode navegar por uma pasta diferente.

Presets de Layout de Espaço de Trabalho
---------------------------------------

``Arquivo`` > ``Espaços de Trabalho…`` captura a geometria atual da janela, o
arranjo de docks / barras de ferramentas, a divisão árvore / visualizador e
pasta raiz ativa sob um nome — depois permite alternar entre layouts salvos.
A aba ativa e a divisão de painéis da aba Modify não são guardadas. A
caixa de diálogo suporta Salvar Atual, Carregar, Renomear e Excluir. Espaços
de trabalho persistem em ``user_setting.json`` (sob a chave ``workspaces``)
e sobrevivem entre sessões.

.. tip::
   Construa um espaço de trabalho **Browse** com uma árvore larga ao lado
   do visualizador, e um espaço **Focus** separado com a árvore arrastada
   até ficar estreita e os docks de que você não precisa fechados. Um clique
   move sua janela inteira para a forma certa para cada tarefa.

Gestos de Touchpad
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Gesto
     - Ação
   * - Pinça
     - Zoom in / out no Deep Zoom (ancorado no centro da pinça)
   * - Deslize horizontal
     - Imagem anterior / próxima

----

Associação de Arquivos (Windows)
--------------------------------

Registrar o Imervue como visualizador de imagens no Windows Explorer:

1. ``Arquivo`` > ``Associação de Arquivos`` > ``Registrar 'Open with Imervue'``
2. Não são necessários direitos de administrador: o registro grava no registro do usuário atual.
3. Após o registro, clique com o botão direito em qualquer imagem no Explorer para ver a opção ``Open with Imervue``.

Para remover: ``Arquivo`` > ``Associação de Arquivos`` > ``Remover associação de arquivos``.

----

Sistema de Plugins
------------------

O Imervue suporta plugins para funcionalidade estendida.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Ação
     - Localização no Menu
   * - Ver plugins instalados
     - ``Plugins`` > ``Gerenciar Plugins``
   * - Baixar novos plugins
     - ``Plugins`` > ``Baixar Plugins``
   * - Abrir pasta de plugins
     - ``Plugins`` > ``Abrir Pasta de Plugins``
   * - Recarregar plugins
     - ``Plugins`` > ``Recarregar Plugins``

Escrevendo Plugins
^^^^^^^^^^^^^^^^^^

Um plugin é um pacote Python em ``plugins/<name>/`` — ao lado do pacote ``Imervue`` em um
checkout do código-fonte, ao lado do executável em uma build empacotada (``Plugins`` > ``Open Plugin
Folder`` abre a pasta). O ``__init__.py`` dele define ``plugin_class`` como uma subclasse de
``Imervue.plugin.plugin_base.ImervuePlugin``; um único arquivo ``.py`` em ``plugins/`` também é
carregado (a primeira subclasse de ``ImervuePlugin`` nele é usada), mas o downloader de plugins só
distribui pacotes. Os atributos de classe ``plugin_name``, ``plugin_version``, ``plugin_description`` e
``plugin_author`` são opcionais (``"Unnamed Plugin"``, ``"0.0.1"`` e strings vazias por padrão).
Cada janela principal cria a própria instância de cada plugin e passa a si mesma, então um hook pode usar
``self.main_window`` e ``self.viewer`` (o ``GPUImageView``). Sobrescreva apenas os hooks de que você
precisa; cada chamada é protegida, então uma exceção é registrada no log com o nome do plugin em vez de
interromper o Imervue. O guia completo, com exemplos, é
`PLUGIN_DEV_GUIDE.md <https://github.com/JeffreyChen-s-Utils/Imervue/blob/main/PLUGIN_DEV_GUIDE.md>`_.
Além dos hooks, um plugin pode dar à Exportação em Lote outro renderizador para as receitas de
revelação registrando um ``BackendProvider`` com ``Imervue.image.develop_backends.register`` em
``on_plugin_loaded()``; o plugin GPU Develop é o exemplo.

Um diálogo que executa uma transformação de imagem ao clicar em **OK** pode obter a linha de botões, a
instalação de pacotes opcionais, a thread de trabalho e o toast de resultado de
``Imervue.plugin.tool_dialog.ToolDialogMixin``: ele define ``output_suffix`` e as chaves do toast e
retorna a transformação em ``_transform()``. Um plugin que importa código do programa principal
adicionado depois de versões mais antigas declara a versão da API de plugins de que precisa em um
arquivo ``plugin.json`` ao lado do seu ``__init__.py`` (``{"min_api_version": 2}``).
``Plugins`` > ``Download Plugins`` recusa esse plugin em um Imervue antigo demais e mantém qualquer
cópia já instalada, mostrando na linha de status a versão de que ele precisa; o carregador de plugins o
ignora sem importá-lo e registra o motivo no log.

.. list-table::
   :header-rows: 1
   :widths: 28 40 32

   * - Hook
     - Chamado quando
     - Argumentos / retorno
   * - ``register_languages()`` (método de classe)
     - Na classe do plugin antes de cada instância ser criada (a cada carregamento e em ``Reload
       Plugins``), e na inicialização antes de a janela principal ser construída quando o idioma salvo
       não é um dos embutidos; essa passada de inicialização importa todos os plugins e não executa mais nada
     - Sem argumentos. Chame ``language_wrapper.register_language(language_code, display_name,
       word_dict)`` aqui; um código de idioma embutido é recusado. Uma string vazia ou cujos
       ``{placeholders}`` diferem dos do inglês é descartada e registrada no log (o texto embutido
       aparece), e chaves ausentes são registradas no log. O valor de retorno é ignorado; uma
       exceção é registrada no log e o plugin é carregado mesmo assim
   * - ``on_plugin_loaded()``
     - Logo depois de a instância ser criada: enquanto a janela principal é construída, e de novo depois de
       ``Plugins`` > ``Reload Plugins``
     - Sem argumentos; valor de retorno ignorado
   * - ``get_translations()``
     - Logo depois de ``on_plugin_loaded()``, uma vez por carregamento
     - Retorna ``{language_code: {key: text}}`` (padrão ``{}``). As strings são mescladas nas
       tabelas de idioma; chaves que já existem nunca são sobrescritas e códigos de idioma
       desconhecidos são ignorados. Uma string vazia, ou cujos ``{placeholders}`` diferem dos da
       string em inglês do payload para essa chave, é descartada; os problemas são registrados no log
   * - ``on_build_main_tabs(tabs)``
     - Uma vez enquanto a janela principal é construída, depois das cinco abas embutidas e antes de
       ``on_build_menu_bar``; ``Reload Plugins`` não o executa de novo
     - ``tabs``: o ``QTabWidget`` de nível superior da janela principal; adicione uma aba com
       ``tabs.addTab(widget, label)``. Valor de retorno ignorado
   * - ``on_build_menu_bar(plugin_menu)``
     - Uma vez depois de o menu ``Plugins`` compartilhado ser construído, e de novo depois de ``Reload Plugins``
     - ``plugin_menu``: o ``QMenu`` ``Plugins`` (não a ``QMenuBar``). As entradas que um plugin adiciona
       em qualquer lugar da barra de menus aqui são removidas ao recarregar. Valor de retorno ignorado
   * - ``on_build_context_menu(menu, viewer)``
     - Cada vez que o menu de clique direito do visualizador é construído, depois das entradas embutidas e
       logo antes de abrir
     - ``menu``: o ``QMenu`` de contexto; ``viewer``: o ``GPUImageView``. Valor de retorno ignorado
   * - ``on_folder_opened(folder_path, image_paths, viewer)``
     - Quando termina a varredura de uma pasta aberta
     - ``folder_path``: a pasta; ``image_paths``: todas as imagens que a varredura encontrou. Valor de
       retorno ignorado
   * - ``on_image_loaded(image_path, viewer)``
     - Cada vez que uma imagem aparece na tela em tamanho total no deep zoom, não importa como foi
       aberta, e de novo quando é recarregada após uma edição; não para a prévia de baixa resolução
       exibida enquanto uma imagem grande é decodificada
     - ``image_path``: o caminho da imagem. Valor de retorno ignorado
   * - ``on_image_switched(image_path, viewer)``
     - Quando próxima / anterior (incluindo a volta em qualquer uma das pontas da lista) passa para
       outra imagem, assim que o carregamento dela começa; ``on_image_loaded`` vem depois, quando ela é
       exibida. Abrir uma imagem pela grade ou pela filmstrip não o chama
     - ``image_path``: a nova imagem atual. Valor de retorno ignorado
   * - ``on_image_deleted(deleted_paths, viewer)``
     - Depois que imagens são soft-deletadas (colocadas na pilha de desfazer) a partir do visualizador —
       a imagem atual ou as miniaturas selecionadas — ou da árvore de pastas; não para um arquivo que a
       árvore envia direto para a Lixeira porque ele não está na lista de imagens
     - ``deleted_paths``: lista dos caminhos excluídos. Valor de retorno ignorado
   * - ``on_key_press(key, modifiers, viewer)``
     - A cada tecla pressionada que o visualizador recebe, antes das teclas embutidas dele e das
       vinculações de Shortcut Settings; os plugins são consultados na ordem de carregamento. Uma tecla
       que um atalho de menu ou de janela captura primeiro nunca chega ao visualizador
     - ``key``: um código ``Qt.Key`` (int); ``modifiers``: flags ``Qt.KeyboardModifier``. Retorne
       ``True`` para consumir a tecla — os plugins seguintes e o tratamento padrão são pulados; retorne
       ``False`` (o padrão) para repassá-la. Uma exceção conta como ``False``
   * - ``on_pet_created(pet)``
     - Quando a aba Desktop Pet cria a janela do pet, e logo depois de o plugin carregar (ou de
       ``Reload Plugins`` ser executado) se o pet já existe
     - ``pet``: a janela do pet. Os plugins usam ``play_group(group)``, ``speak(line)``,
       ``speak_notification(line)``, ``speech_on``, ``setting(key, default)``,
       ``persist(**fields)``, ``add_integration(key, controller)`` /
       ``remove_integration(key)`` / ``integration(key)`` e os sinais ``hit_triggered``,
       ``moved`` e ``visibility_changed``. Valor de retorno ignorado
   * - ``on_app_closing(main_window)``
     - Quando a última janela principal fecha, depois que o aviso de abas não salvas do Paint é aceito
       e as configurações são salvas, logo antes de os plugins serem descarregados; fechar outra janela
       não o chama
     - ``main_window``: a ``ImervueMainWindow`` que está fechando. Valor de retorno ignorado
   * - ``on_plugin_unloaded()``
     - Quando a janela do plugin fecha (depois de ``on_app_closing`` para a última janela), e antes de
       ``Reload Plugins`` carregar os plugins de novo; os plugins são descarregados na ordem inversa
       à de carregamento
     - Sem argumentos; valor de retorno ignorado

----

Idioma
------

Mude o idioma da interface a partir do menu ``Idioma``:

- Inglês (English)
- Chinês Tradicional (繁體中文)
- Chinês Simplificado (简体中文)
- Coreano (한국어)
- Japonês (日本語)

É necessária uma reinicialização após a mudança.

Plugins podem adicionar idiomas próprios. **Español** é distribuído exatamente assim:
instale o plugin ``spanish_translation`` pelo downloader de plugins e ele aparece no menu
``Language`` ao lado dos cinco idiomas embutidos. Um plugin também pode contribuir traduções
para um idioma existente; chaves que já existem nunca são sobrescritas, então um plugin não
consegue quebrar uma string de fábrica.

----

Referência de Atalhos de Teclado
--------------------------------

Navegação
^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``Esquerda`` / ``Direita``
     - Imagem anterior / próxima
   * - Teclas de seta
     - Mover o anel de foco pelas miniaturas
   * - ``Ctrl + Shift + Esquerda`` / ``Direita``
     - Saltar para a pasta irmã anterior / próxima com imagens
   * - ``Alt + Esquerda`` / ``Alt + Direita``
     - Voltar / avançar no histórico (estilo navegador)
   * - ``Ctrl + G``
     - Saltar para imagem por número
   * - ``X``
     - Saltar para uma imagem aleatória
   * - Roda do mouse / Pinça
     - Zoom in / out
   * - Deslize horizontal
     - Imagem anterior / próxima
   * - Arrastar com botão do meio
     - Deslocar
   * - ``F``
     - Tela cheia
   * - ``Shift + Tab``
     - Modo cinema (oculta todo o cromo)
   * - ``Ctrl + L``
     - Alternar Grade ↔ Lista (detalhe) modo de navegação
   * - ``Shift + S``
     - Visão dividida (duas imagens lado a lado)
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - Leitura em página dupla / RTL (mangá)
   * - ``Ctrl + Shift + M``
     - Espelhar imagem atual em um segundo monitor
   * - ``Esc``
     - Voltar às miniaturas / sair da tela cheia / fechar modo duplo ou de lista
   * - ``W``
     - Ajustar à largura
   * - ``Shift + W``
     - Ajustar à altura
   * - ``Shift + F``
     - Ajustar à janela
   * - ``-`` / ``=``
     - Diminuir / aumentar o zoom
   * - ``V``
     - Modo de leitura: ajustar à largura, rolar para ler, avançar para a próxima imagem no fim
   * - ``Home``
     - Ajustar a imagem inteira à janela (na grade: voltar ao topo)

Edição
^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``E``
     - Abrir o editor de anotações
   * - ``R``
     - Rotacionar no sentido horário
   * - ``Shift + R``
     - Rotacionar no sentido anti-horário
   * - ``Ctrl + Z``
     - Desfazer
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Refazer
   * - ``Delete``
     - Excluir imagem

Organização
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``0``
     - Alternar favorito
   * - ``1`` -- ``5``
     - Avaliar (pressione novamente para limpar)
   * - ``F1`` -- ``F5``
     - Rótulo de cor: vermelho / amarelo / verde / azul / roxo (pressione a mesma tecla para limpar)
   * - ``P``
     - Cull: Pick (marcar para manter)
   * - ``Shift + X``
     - Cull: Reject
   * - ``U``
     - Cull: Unflag
   * - ``B``
     - Alternar marcador
   * - ``T``
     - Gerenciador de Tags e Álbuns

Ferramentas e Sobreposições
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``Ctrl + F`` / ``/``
     - Pesquisa fuzzy com destaque de substring
   * - ``Ctrl + C``
     - Copiar imagem para a área de transferência
   * - ``Ctrl + V``
     - Colar da área de transferência
   * - ``H``
     - Histograma RGB
   * - ``F8`` / ``Ctrl + F8``
     - Sobreposição OSD de informações / HUD de Debug (VRAM, cache, threads)
   * - ``Shift + P``
     - Visualização de pixel (a partir de 400 % mostra RGB / HEX sob o cursor; a grade quando ≤ 40.000 pixels da imagem estão na tela)
   * - ``Shift + M``
     - Alternar modos de cor (Normal / Tons de Cinza / Inverter / Sépia)
   * - ``L``
     - Lupa: uma lente de aumento que segue o cursor (também sobre as miniaturas)
   * - ``S``
     - Slideshow
   * - ``Ctrl + Shift + P``
     - Paleta de Comandos
   * - ``Alt + M``
     - Reproduzir o último macro na seleção

Imagens animadas
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``Space``
     - Reproduzir / Pausar
   * - ``,``
     - Quadro anterior
   * - ``.``
     - Próximo quadro
   * - ``[``
     - Desacelerar
   * - ``]``
     - Acelerar

Paint
^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``[`` / ``]``
     - Diminuir / aumentar o tamanho do pincel em 1 px
   * - ``Shift + [`` / ``Shift + ]``
     - Diminuir / aumentar o tamanho do pincel em 5 px
   * - ``Ctrl + Z``
     - Desfazer
   * - ``Ctrl + Shift + Z`` / ``Ctrl + Y``
     - Refazer
   * - ``Ctrl + D``
     - Desmarcar seleção
   * - ``Ctrl + 0`` / ``Ctrl + 1``
     - Ajustar à janela / Tamanho real (100 %)
   * - ``X``
     - Trocar as cores de primeiro plano / fundo
   * - ``D``
     - Redefinir as cores para preto / branco
   * - ``Ctrl + Tab`` / ``Ctrl + Shift + Tab``
     - Aba Paint seguinte / anterior

As teclas das ferramentas estão listadas em *Paleta de Ferramentas (Tira Esquerda)*. ``Settings`` >
``Shortcuts…`` na aba Paint remapeia as teclas de ferramenta, tamanho do pincel, camada, desfazer /
refazer, desmarcar, visualização e cor (``Ctrl + Y`` continua como segunda tecla de Refazer).

----

Gerenciamento de Biblioteca e Metadados
---------------------------------------

O Imervue mantém um índice baseado em SQLite em ``%LOCALAPPDATA%/Imervue/library.db``
(Windows) ou ``~/.cache/imervue/library.db`` (POSIX) para pesquisa entre pastas,
tags hierárquicas, álbuns inteligentes, hashes perceptuais, notas e flags de cull.
Tudo abaixo fica em ``Extra Tools`` salvo indicação contrária. Na última versão,
o menu está organizado em oito submenus agrupados por função —
``Batch``, ``Library & Metadata``, ``Views``, ``Workflow``, ``Export``,
``Develop (Non-Destructive)``, ``Retouch & Transform`` e ``Multi-Image`` —
então cada caminho abaixo é mostrado como ``Extra Tools`` > ``<submenu>`` > ``<tool>``.

Pesquisa de Biblioteca
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` permite adicionar uma ou mais **pastas raiz**
a um índice global que é varrido em uma thread em segundo plano. Uma vez que uma raiz é
indexada você pode pesquisá-la por nome de arquivo, largura / altura mínima e tamanho de
arquivo (até 2000 resultados); clique duas vezes em um resultado para abri-lo. Uma nova varredura só lê os arquivos novos ou alterados desde a anterior e, com **Compute
perceptual hash** marcado, os indexados antes sem hash; os arquivos lidos são decodificados em
várias threads ao mesmo tempo.

Clique direito > ``Search by Query…`` filtra a pasta atual com uma linguagem de consulta compacta, por exemplo ``kw:beach rating:>=4 type:video place:Paris``. ``place:`` aceita uma cidade, um país ou ambos (``Paris``, ``France``, ``Paris, France``); um valor com espaços vai entre aspas duplas (``place:"Rio de Janeiro"``).

Álbuns Inteligentes
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` persiste regras de filtro (extensões, dimensões
mínimas, rótulos de cor, avaliação, favoritos, estado de cull, tags hierárquicas,
substring de nome) sob um nome amigável. Reaplicar um álbum filtra a pasta ativa
pelas regras salvas.

Pesquisa de Imagens Similares
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` executa um pHash DCT de 64 bits na
imagem atual em deep-zoom (ou na primeira miniatura selecionada) e lista correspondências
próximas do índice ordenadas pela distância de Hamming. Ajuste o spin
``Max Hamming distance`` para alargar ou apertar a rede.

Pesquisa Semântica (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Semantic Search`` permite digitar uma frase em linguagem natural
(por exemplo *"golden retriever na neve"* ou *"rua de neon à noite"*) e
retorna, classificadas, as imagens da pasta aberta. Cada imagem é incorporada com um
encoder visão/linguagem CLIP e armazenada junto com seu caminho; uma consulta de texto é
incorporada no mesmo espaço vetorial e comparada por similaridade de cosseno.

Os embeddings são armazenados em cache em ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) ou ``~/.cache/imervue/clip_cache.npz`` (POSIX) como um único arquivo ``.npz`` compacto. A caixa de diálogo pesquisa a pasta aberta: incorpora apenas as imagens que o cache ainda não tem ou que mudaram desde então (tamanho ou data de modificação), então pesquisar de novo a mesma pasta começa na hora, e os resultados vêm só dessa pasta.

.. note::
   A Pesquisa Semântica executa o CLIP ViT-B/32 sobre ``onnxruntime``, sem PyTorch. Na
   primeira vez que você a abre sem ``onnxruntime``, o Imervue oferece instalá-lo; o modelo
   (cerca de 150 MB, quantizado em int8) é então baixado uma única vez do Hugging Face em uma
   revisão fixada e, depois disso, lido do cache local. Ele roda em uma GPU NVIDIA via CUDA
   quando o ``onnxruntime`` tem suporte a ela, senão na CPU; nunca escolhe uma GPU
   integrada. Embeddings armazenados em cache por um modelo diferente são calculados de novo.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` aplica tags heurísticas sob
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``graphic`` / ``landscape`` /
``portrait``), lidas da saturação de cor, das bordas e da forma da imagem como o
visualizador a mostra. Executa em uma thread de trabalho com uma barra
de progresso em tempo real.

Depois que a Pesquisa Semântica tiver baixado o modelo CLIP, o Auto-Tag passa a rotular
cada imagem com ele em modo zero-shot: até três entre ``photo``, ``document``,
``screenshot``, ``graphic``, ``illustration``, ``portrait``, ``landscape``, ``animal``,
``food`` e ``text``, o mais próximo primeiro. Uma imagem que o CLIP não consegue ler recebe
as tags heurísticas, e o Auto-Tag nunca inicia o download por conta própria.

Tags Hierárquicas
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gerencia tags em estrutura de árvore como
``animal/gato/british``. Selecione uma tag para ver toda imagem abaixo daquele ramo
(descendentes incluídos). Marque ou desmarque a seleção atual com um clique.
Tags hierárquicas vivem no índice da biblioteca e são complementares ao sistema
de tags planas no menu de clique direito.

Clique direito > ``Operações em Lote`` > ``Index Keywords`` (com miniaturas selecionadas)
adiciona à biblioteca as palavras-chave XMP da seleção. Uma hierarquia de palavras-chave escrita pelo Lightroom ou darktable
(``lr:hierarchicalSubject``, ``Places|Taiwan|Taipei``) é arquivada como o caminho de
tag ``Places/Taiwan/Taipei``, e as palavras soltas ``Places`` / ``Taiwan`` /
``Taipei`` que só repetem os níveis não são adicionadas de novo.

Renomeação em Lote por Tokens
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` abre uma tabela com pré-visualização ao vivo onde você
digita um template como ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` e vê
exatamente em que cada arquivo será renomeado. Conflitos são destacados para que
nada seja sobrescrito. Tokens suportados: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``. Um nome novo que outro arquivo selecionado tem agora
não é conflito: renumerar (``002`` → ``003`` enquanto ``003`` → ``004``) ou trocar
dois nomes renomeia a seleção inteira. O Batch Rename faz o mesmo.

Exportação de Metadados
^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` escreve uma linha por imagem na
visualização atual cobrindo EXIF, dimensões, rótulo de cor, avaliação, favorito,
tags hierárquicas, estado de cull e notas. Útil para alimentar decisões de cull
em uma planilha ou fluxo de trabalho externo.

Sidecars XMP
^^^^^^^^^^^^

O Imervue pode ler e gravar arquivos sidecar XMP da Adobe (``photo.jpg`` ↔
``photo.xmp``) para que avaliações, títulos, descrições, palavras-chave e
rótulos de cor façam round-trip de forma limpa com o Adobe Bridge e outros
gerenciadores de fotos com suporte a XMP.

Salvar mescla no sidecar existente: só estes campos mudam, então as configurações de revelação, o recorte e o histórico de outro programa são mantidos, e um sidecar ilegível nunca é sobrescrito.

Além de ``photo.xmp`` (Lightroom, Bridge), o ``photo.jpg.xmp`` que o darktable
e o digiKam escrevem é lido e atualizado quando é o único sidecar. Os rótulos de
cor são entendidos nas palavras do Lightroom (``Red`` … ``Purple``) e do Bridge
(``Select``, ``Second``, ``Approved``, ``Review``, ``To Do``). Uma cor nova ou alterada
é exportada como o Lightroom a escreve; um sidecar que já tem a palavra do Bridge para
a mesma cor mantém essa palavra. Um rótulo sem cor (personalizado) fica no sidecar.

Uma foto rejeitada — ``xmp:Rating`` -1 no Lightroom, Bridge e darktable — é
importada como **Reject** da seleção, sem estrelas, e um Reject é exportado como
-1. Um sidecar não rejeitado remove um Reject; um Pick fica como está.

Um arquivo sem sidecar é lido — e importado — a partir do que ele mesmo embute: o
pacote XMP (JPEG, PNG, WebP, TIFF, CR3, RW2, ORF, RAF) e depois o ``Rating`` / ``RatingPercent`` EXIF.
É ali que o Lightroom guarda a avaliação e as palavras-chave de um JPEG, e onde o
Explorador do Windows e algumas câmeras guardam as estrelas. Havendo sidecar, ele
prevalece.

``Extra Tools`` > ``Library & Metadata`` > ``XMP Sidecars`` tem dois botões que se aplicam a
todas as imagens da visualização atual:

- **Export sidecars** — grava a avaliação / título / descrição / palavras-chave /
  rótulo de cor de cada imagem no seu sidecar.
- **Import sidecars** — lê esses dados de volta para os registros do próprio Imervue.

O parser de XML usa ``defusedxml`` para que sidecars malformados ou maliciosos
não possam disparar ataques XXE / billion-laughs.

A **barra lateral EXIF** também expõe uma **tira de avaliação por estrelas**
clicável — a avaliação que ela define é a que a exportação XMP gravará.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

Um flag de cull de três estados. Pressione ``P`` para escolher
a imagem atual ou cada miniatura selecionada, ``Shift + X`` para rejeitar, ``U`` para
desmarcar. ``Filtrar`` > ``Por Estado de Cull`` mostra apenas escolhidas, rejeitadas
ou não marcadas. ``Extra Tools`` > ``Workflow`` > ``Culling`` aplica o filtro via uma caixa de diálogo
e também expõe um botão **Excluir todas as rejeitadas** que remove permanentemente os
arquivos marcados do disco. O botão **Escolher a mais nítida por grupo similar** da mesma
caixa de diálogo agrupa as quase duplicatas da pasta por hash perceptual, pontua cada uma
pela nitidez e marca o quadro mais nítido de cada grupo como escolhido e o restante como
rejeitado.

Bandeja de Staging
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` é uma cesta entre pastas. Adicione qualquer conjunto
de miniaturas à bandeja (a lista sobrevive entre reinicializações), depois mova ou copie a bandeja
inteira para uma pasta de destino com um clique. Útil para reunir escolhidas de
várias sessões antes da exportação.

Gerenciador de Arquivos de Painel Duplo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` abre uma visualização
com dois painéis e duas árvores. Escolha uma pasta em cada painel e mova/copie
a seleção entre eles sem sair do Imervue.

Visualização de Linha do Tempo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` agrupa o conjunto atual de imagens por dia,
mês ou ano (agrupado por data). A data vem do EXIF ``DateTimeOriginal``, depois de
``DateTimeDigitized``, depois de ``DateTime`` e, caso contrário, do tempo de modificação
do arquivo.
Clique duas vezes em qualquer imagem para abri-la em Deep Zoom.

Arrastar para Apps Externos
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pressione e arraste de uma miniatura **selecionada** para soltar o arquivo no Explorer,
Chrome, Discord ou qualquer app que aceite URLs de arquivo. A pré-visualização do arrasto
é a miniatura.

Notas por Imagem
^^^^^^^^^^^^^^^^

A barra lateral EXIF inclui uma caixa **Notas** de texto livre. A digitação salva
automaticamente no índice da biblioteca após um pequeno debounce. As notas viajam
com o caminho da imagem, então sobrevivem a re-varreduras de pasta.

----

Revelação Avançada e Composição
-------------------------------

Curva de Tons
^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` abre um editor de curvas com pontos arrastáveis e
quatro canais (RGB, R, G, B). Clique com o botão esquerdo no canvas vazio para adicionar um ponto;
arraste para mover; clique com o botão direito para excluir. Os pontos são interpolados com um
spline cúbico monotônico e armazenados na receita da imagem, então a curva se aplica
de forma não destrutiva no momento da renderização.

Aplicar LUT .cube
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` permite escolher qualquer arquivo ``.cube`` da Adobe
(3D até 65³, 1D até 65.536 pontos). ``LUT_1D_INPUT_RANGE`` /
``LUT_3D_INPUT_RANGE`` do DaVinci Resolve define a faixa de entrada como
``DOMAIN_MIN`` / ``DOMAIN_MAX``, e um arquivo salvo com BOM também carrega. A LUT é parseada com um ``lru_cache`` chaveado por
caminho + mtime, avaliada com interpolação trilinear, e misturada contra
o original via um slider de intensidade. O caminho da LUT e a intensidade ficam na receita.

Cópias Virtuais
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` dá a cada imagem snapshots nomeados de
receitas. Capture a edição atual, continue experimentando e volte para qualquer
variante anterior depois. As variantes ficam ao lado da receita master na loja
de receitas e sobrevivem ao reset do master para a identidade.

Mesclagem HDR
^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` combina duas ou mais exposições com bracket
em uma única imagem via a fusão de exposição Mertens do OpenCV. A caixa opcional
"Align exposures" executa ``cv2.AlignMTB`` primeiro para compensar trepidação ao
segurar a câmera. A saída é salva em um arquivo escolhido pelo usuário — não toca
nenhuma imagem fonte.

Stitch de Panorama
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` envolve a API de alto nível
``Stitcher`` do OpenCV. Escolha o modo **Panorama** para paisagens / cityscapes ou
o modo **Scans** para documentos planos e obras de arte. As bordas pretas produzidas pelo
warp podem ser auto-recortadas.

Empilhamento de Foco
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` funde múltiplos disparos tirados em
diferentes distâncias de foco. Para cada pixel o algoritmo escolhe qualquer
quadro de entrada que tem a maior nitidez local (variância Laplaciana), depois
suaviza a máscara de seleção com uma mistura gaussiana para evitar emendas. O
alinhamento ECC fica ligado por padrão para pequenos offsets ao segurar a câmera.

Pincel de Cura
^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` mostra a imagem atual em até
720 px no lado maior. Clique com o botão esquerdo para adicionar uma mancha circular;
clique com o botão direito em uma mancha existente para removê-la; o slider de raio
define o tamanho da nova mancha. Ao aplicar, o inpainting do OpenCV (Telea para velocidade,
Navier-Stokes para mistura mais suave) preenche cada região mascarada a partir dos pixels
circundantes e o resultado é salvo em um novo arquivo.

Correção de Lente
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` expõe quatro sliders pure-numpy:
distorção radial ``k1`` (barril / pincushion), elevação de vinheta, e
escala radial de aberração cromática por canal para vermelho e azul. A
imagem corrigida, do mesmo tamanho que a original, é salva como um novo arquivo.

Visualização de Mapa
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` plota as imagens geotagueadas da pasta aberta
em um mapa interativo Leaflet + OpenStreetMap, com um marcador por cidade mais próxima e
o número de imagens ali (requer ``PySide6.QtWebEngineWidgets``). Sem WebEngine, a caixa
de diálogo recai para uma lista desses lugares com suas contagens e coordenadas, para que
o recurso permaneça utilizável em instalações mínimas.

Visualização de Calendário
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` mostra um ``QCalendarWidget`` com dias
destacados quando as fotos foram tiradas naquele dia (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → ``DateTime`` → mtime do arquivo). Selecionar uma data lista suas
imagens; clique duas vezes para abrir uma no visualizador principal.

Detecção Facial
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` executa o cascade Haar de detecção
de faces frontais do OpenCV na imagem atual e desenha cada detecção como um retângulo.
Clique duas vezes em uma linha da lista para digitar o nome de uma pessoa; ao salvar, as tags
são gravadas no blob ``extra['face_tags']`` da receita. A detecção é uma técnica clássica —
a precisão é adequada para "mostre-me os rostos" mas não substitui o reconhecimento
moderno baseado em CNN.
Requer OpenCV 4 (``pip install "opencv-python<5"``): o OpenCV 5 removeu os cascades
Haar, e nesse caso o diálogo avisa em vez de detectar.

Máscaras de Ajuste Local
^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` coloca máscaras de pincel, radial ou
gradiente linear sobre a imagem. Cada máscara carrega sua própria exposição,
brilho, contraste, saturação, temperatura, deltas de matiz mais um slider de
pluma. As máscaras são salvas em ``recipe.extra['masks']`` e aplicadas
de forma não destrutiva no carregamento, então o arquivo subjacente nunca é tocado.

Tonalização Dividida
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` aplica matizes distintos a sombras e
realces com saturação por região e um pivô de balanço. Armazenado em
``recipe.extra['split_toning']`` e aplicado após a curva de tons no pipeline
de revelação.

Carimbo de Clonagem
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` copia um patch fonte com pluma para um
destino — o complemento de borda dura do pincel de cura. Shift+clique
define a fonte, um clique normal carimba, clique com o botão direito desfaz. O resultado é
gravado em um novo arquivo para que o original permaneça intacto.

Recorte / Endireitar
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` combina um retângulo de recorte
normalizado (0..1) com um ângulo de endireitamento de até ±15°. A saída é
auto-recortada para o maior retângulo interno para que fotos rotacionadas não tenham
cantos pretos.

Endireitamento Automático
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` detecta o horizonte ou linhas verticais
dominantes via detecção de linhas de Hough e propõe uma rotação. Um
clique aplica o endireitamento; você pode ajustar o ângulo primeiro se a
auto-detecção escolher a referência errada.

Redução de Ruído / Nitidez
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` aplica uma redução
de ruído bilateral (preservando bordas) seguida de um sharpen unsharp-mask.
"Apenas luminância" mantém o ruído de cor intacto mas achata a granulação sem
borrar bordas de chroma.

Céu / Fundo
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` substitui o céu detectado por um
gradiente ou remove o fundo para transparente / branco. Quando
``rembg`` (U²-Net) está instalado, a máscara de primeiro plano vem da
rede de segmentação; caso contrário, a regra heurística HSV é usada.

Soft Proof
^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` carrega um perfil ICC, converte a
imagem através dele e de volta, e destaca em magenta os pixels que clipparam durante
o round-trip — uma verificação rápida fora-de-gamut antes de imprimir.

Efeitos Tonais e Criativos
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` reúne um conjunto de efeitos de
aplicação única (apply-and-save), cada um uma caixa de diálogo enxuta de sliders
sobre uma transformação pure-NumPy (Frame & Caption desenha com Pillow; a mesma
lógica também é exposta como uma ferramenta MCP):

- **Graduated Density** — um gradiente linear de densidade neutra definido por
  ângulo, dureza e offset, opcionalmente tonalizado; escurece um céu ou primeiro
  plano sem uma máscara manual.
- **Tone Equalizer** — exposição independente por zona de luminância (um slider
  para cada, de pretos → brancos) sobre uma máscara suavizada, para que o ajuste
  siga os tons da cena.
- **Detail Equalizer** — um slider de ganho por banda de frequência (textura fina
  → contraste grosseiro), a alternativa multiescala a um único slider de clareza.
- **Filmic Tone Map** — um rolloff de realces Reinhard ou Hable com contraste
  pivotado e uma restauração de saturação, para capturas únicas de alto contraste.
- **Velvia** — um boost de saturação ponderado por luminância que intensifica
  cores apagadas enquanto poupa as já saturadas e as sombras.
- **Film Negative** — inverte um negativo colorido escaneado, removendo a base
  laranja do filme estimada automaticamente, com um slider de gamma de saída.
- **Defringe** — dessatura franjas roxas/verdes de aberração cromática ao longo
  de bordas de alto contraste, deixando a cor plana intocada.
- **Emboss** — um relevo de luz direcional a partir do campo de altura de
  luminância (azimute / elevação / profundidade + uma alternância para tons de cinza).
- **Polar Coordinates** — envolve o quadro em um disco ou o desenrola (o visual
  planeta-miniatura / inversão polar).
- **Kaleidoscope** — espelha uma cunha angular em simetria de ordem ``n``.
- **Frosted Glass** — um espalhamento local de pixels determinístico e
  reproduzível por semente.
- **Frame & Caption** — uma borda passe-partout em qualquer cor, uma faixa
  inferior opcional mais grossa no estilo Polaroid e uma legenda gravada nela
  com cor própria.

Geotag GPS
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lê quaisquer tags GPS EXIF existentes e
permite editar ou definir novas coordenadas em graus decimais. Um JPEG é gravado no local
sem pacote extra: só o bloco EXIF muda, então os pixels, as outras tags e a miniatura
continuam iguais. Um WebP é tratado da mesma forma; outros formatos não podem ser marcados.

O **editor EXIF** (botão ``Edit EXIF`` do painel lateral EXIF) altera descrição, artista, copyright, marca / modelo da câmera e comentário. Um JPEG ou WebP não precisa de pacote extra e só o bloco EXIF é reescrito; os outros formatos mostram por que não podem ser editados. **Describe**, ao lado da descrição, pede a um modelo de visão no seu próprio computador um texto alternativo de uma frase e o coloca no campo para você editar antes de **Save**: é preciso ter o `Ollama <https://ollama.com>`__ rodando em ``localhost:11434`` com um modelo de visão (``ollama pull llava``), e quando nenhum responde o diálogo avisa e deixa o campo como está. A imagem é enviada só para esse servidor local.

Galeria Web
^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Web Gallery`` grava as imagens selecionadas (ou a pasta inteira)
como um site autocontido: ``index.html`` com lightbox, miniaturas JPEG e cópias dos originais, a
menos que você desmarque **Copiar originais em tamanho real**. Você define o título da página e o
tamanho e a qualidade das miniaturas. Com os originais copiados, a página não precisa de servidor:
abra-a direto do disco ou publique-a em qualquer hospedagem estática. Sem eles, os links para o
tamanho real apontam para as imagens no seu próprio disco.

Marque **Revisão do cliente** para enviar a galeria e receber o feedback do cliente. Cada imagem
ganha uma caixa de comentário; as anotações ficam no navegador de quem revisa, e o botão
**Export comments** da página salva todas elas em um único arquivo JSON.

Layout de Impressão
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` compõe múltiplas imagens em um
PDF de várias páginas com tamanho de página, orientação, grade, margens,
sarjeta e marcas de corte configuráveis. Requer ``reportlab``.

----

Referência do Menu Extra Tools
------------------------------

Todas as entradas do menu ``Extra Tools``, submenu por submenu, na ordem do menu. Muitas têm uma
seção mais completa acima; esta lista é o inventário completo. As entradas que salvam um arquivo novo
o gravam ao lado da origem e acrescentam ``_1``, ``_2`` … quando o nome já existe; as entradas marcadas
"guardado na receita" são edições não destrutivas das configurações de revelação da imagem. Plugins podem
adicionar suas próprias entradas a estes submenus.

Lote (Batch)
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``Batch Format Conversion``
     - Converte as imagens de uma pasta (a pasta atual por padrão) para PNG, JPEG, WebP, BMP ou TIFF,
       ou para HEIC / AVIF / JXL quando os codificadores estão instalados, com opções de qualidade, de
       pular o mesmo formato e de enviar os originais para a lixeira.
   * - ``Batch EXIF Strip``
     - Remove EXIF, GPS e outros metadados de todas as imagens de uma pasta por privacidade,
       sobrescrevendo os originais ou gravando cópias limpas em uma pasta de saída.
   * - ``Image Sanitizer``
     - Re-renderiza as imagens de uma pasta a partir dos pixels brutos, removendo todos os dados ocultos
       (metadados, esteganografia, bytes no fim do arquivo) e renomeando cada uma para data + texto
       aleatório; também pode ampliar imagens pequenas para uma resolução-alvo, como em ``AI Image Upscale``.
   * - ``Image Organizer``
     - Separa as imagens de uma pasta em subpastas por data (ano-mês ou ano), resolução, tipo de arquivo,
       tamanho de arquivo ou uma quantidade fixa por pasta, copiando ou movendo, com prévia.
   * - ``Token Batch Rename``
     - Renomeia as imagens selecionadas (ou a pasta inteira) a partir de um template de tokens como
       ``{name}_{counter:04}`` ou ``{date}_{camera}``, com prévia ao vivo que sinaliza conflitos;
       sidecars, avaliações e tags acompanham os arquivos.
   * - ``Deflicker (Time-lapse)``
     - Uniformiza o brilho de quadro a quadro nos quadros de time-lapse da pasta atual (alvo por média
       móvel ou média global) e grava as cópias corrigidas em uma subpasta ``deflickered/``, sem tocar
       nos originais.
   * - ``Document Binarize``
     - Transforma a foto ou o escaneamento de uma página em preto sobre branco limpo com limiarização
       adaptativa de Sauvola (sliders de tamanho da janela e k), salvando ``<name>_bw.png`` ao lado da
       origem.
   * - ``Otsu Threshold``
     - Converte a imagem atual para preto e branco no limiar global de Otsu escolhido automaticamente,
       com opção de inverter, salvando ``<name>_otsu.png``.
   * - ``Edit Animation``
     - Inverte, faz bumerangue, altera o tempo (0,25x a 4x) ou otimiza (mescla quadros repetidos de)
       o GIF, APNG ou WebP animado atual, salvando ``<name>_edited.gif``.
   * - ``Optimize to Target Size``
     - Recodifica a imagem atual como JPEG ou WebP na maior qualidade que cabe em um orçamento de
       tamanho em KB, salvando ``<name>_opt.jpg`` ou ``<name>_opt.webp``.
   * - ``Meme Caption``
     - Adiciona as legendas clássicas de meme em cima e embaixo (texto branco em maiúsculas com contorno
       preto e quebra de linha) à imagem atual, salvando ``<name>_meme.png``.
   * - ``Steganography``
     - Esconde uma mensagem de texto nos bits menos significativos da imagem atual, salva como um
       ``<name>_stego.png`` sem perdas, ou revela uma mensagem escondida dessa forma.

Biblioteca e Metadados (Library & Metadata)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``Library Search``
     - Gerencia as pastas-raiz da biblioteca, varre-as para o índice (opcionalmente com hashes
       perceptuais) e pesquisa-o por nome de arquivo, largura / altura mínima e tamanho de arquivo em KB;
       clique duas vezes em um resultado para abri-lo.
   * - ``Smart Albums``
     - Salva álbuns baseados em regras (extensões, nome, tags, lugar, tamanho e avaliação mínimos,
       etiqueta de cor, estado de triagem, favoritos) e mostra as correspondências; pode criar um álbum
       por cidade a partir dos dados de GPS, e importar ou exportar álbuns.
   * - ``Find Similar Images``
     - Encontra imagens da biblioteca parecidas com a imagem atual (ou a primeira selecionada) por hash
       perceptual dentro de uma distância de Hamming escolhida; varra antes suas raízes com pHash em
       ``Library Search``.
   * - ``Semantic Search``
     - Encontra imagens na pasta atual que correspondem a uma descrição em texto como "praia ao pôr do
       sol" usando CLIP sobre ``onnxruntime`` (oferecido para instalação no primeiro uso); o modelo de
       ~150 MB é baixado uma única vez.
   * - ``Find Duplicate Images``
     - Varre uma pasta (opcionalmente com subpastas) em busca de duplicatas exatas por hash de arquivo ou
       de imagens parecidas por hash perceptual; pode pré-selecionar todas exceto a melhor cópia de cada
       grupo e mover a seleção para a Lixeira.
   * - ``Auto-Tag Images``
     - Marca as imagens selecionadas, ou a pasta inteira, com tags heurísticas de conteúdo (photo,
       document, screenshot, graphic, landscape, portrait) sob ``auto/`` na árvore de tags hierárquicas,
       ou com rótulos CLIP depois que a Pesquisa Semântica tiver baixado o modelo.
   * - ``Hierarchical Tags``
     - Cria e exclui tags em árvore como ``animal/cat/british``, lista as imagens sob uma tag e
       aplica ou remove tags dos tiles selecionados.
   * - ``Export Metadata (CSV / JSON)``
     - Grava um registro por imagem da visualização atual (detalhes do arquivo, campos EXIF principais
       como câmera, lente, exposição e ISO, avaliação, etiqueta de cor, tags e nota) em um arquivo CSV
       ou JSON.
   * - ``XMP Sidecars``
     - Exporta ou importa arquivos sidecar ``.xmp`` para todas as imagens da visualização atual, para
       que avaliação, título, descrição, palavras-chave e etiqueta de cor façam round-trip com Adobe
       Bridge, Lightroom e outras ferramentas com suporte a XMP.
   * - ``GPS Geotag``
     - Grava uma latitude e uma longitude (graus decimais) nas tags GPS EXIF da imagem atual,
       substituindo as que já existirem; apenas arquivos JPEG e WebP.
   * - ``Geotag from GPX Track``
     - Compara as imagens selecionadas (ou a visualização inteira) com uma trilha ``.gpx`` pelo horário
       de captura EXIF: defina quanto o relógio da câmera diferia do UTC, a que distância de um ponto da
       trilha uma foto pode estar (e se deve interpolar entre pontos), veja quantas caem na trilha e
       então grave suas posições nas tags GPS EXIF; apenas arquivos JPEG e WebP.
   * - ``Edit Capture Time``
     - Desloca a data de captura EXIF das imagens selecionadas (ou da visualização inteira) em dias,
       horas, minutos e segundos, ou pelo momento em que a primeira foto foi realmente tirada,
       reescrevendo DateTimeOriginal, DateTimeDigitized e DateTime; fotos sem data de captura EXIF são
       deixadas como estão, e apenas JPEG e WebP podem ser reescritos.
   * - ``Metadata Template``
     - Aplica um título, uma descrição e palavras-chave separadas por vírgula às imagens selecionadas
       (ou à visualização inteira). ``{filename}``, ``{name}``, ``{folder}``, ``{date}`` e ``{year}``
       são preenchidos para cada foto; com **Only fill empty fields** ligado, a foto mantém o próprio
       título e a própria descrição e ganha as palavras-chave; desligado, o modelo os substitui e suas
       palavras-chave substituem as tags da foto. Pede confirmação antes de aplicar e lembra o modelo;
       ``XMP Sidecars`` e ``Export Metadata`` gravam o resultado.
   * - ``Thumbnail Cache``
     - Mostra quanto espaço em disco o cache de miniaturas usa e o limpa.

Visualizações (Views)
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``By day``
     - Em ``Timeline View``: substitui a visualização principal pelas imagens da pasta atual agrupadas
       sob um cabeçalho por dia de captura (data EXIF, senão a data do arquivo); clique duas vezes em
       uma imagem para abri-la.
   * - ``By month``
     - Em ``Timeline View``: a mesma linha do tempo, agrupada por mês de captura.
   * - ``By year``
     - Em ``Timeline View``: a mesma linha do tempo, agrupada por ano de captura.
   * - ``Calendar View``
     - Mostra um calendário que destaca os dias com fotos na pasta atual (pela data de captura);
       clique em um dia para listar as imagens dele e clique duas vezes em uma para abri-la.
   * - ``Map View``
     - Plota as imagens geotaggeadas da pasta atual em um mapa do OpenStreetMap, um marcador por cidade
       mais próxima com uma contagem; o mapa carrega online e recua para uma lista de coordenadas
       sem QtWebEngine.
   * - ``Scopes & Inspector``
     - Analisa a imagem atual em abas: forma de onda de luminância, parade RGB, exposição em falsa cor,
       focus peaking, Error Level Analysis e detecção de clonagem (copy-move).
   * - ``Tiny Planet (360°)``
     - Reprojeta um panorama equirretangular 360° de proporção 2:1 em um "pequeno planeta" quadrado do
       tamanho escolhido, salvando ``<name>_planet.png``; avisa quando a imagem não é 2:1.
   * - ``Image Statistics``
     - Mostra a média, o mínimo, o máximo, o desvio-padrão e a mediana dos canais R, G, B e de
       luminância da imagem atual, e exporta o histograma de 256 níveis dela como CSV.
   * - ``Quality Report``
     - Lista métricas de qualidade sem referência da imagem atual: colorido, entropia tonal, contraste
       RMS, densidade de bordas e ruído estimado.
   * - ``Test Chart``
     - Gera um padrão de calibração (barras de cor SMPTE, cunha de cinzas, rampa de gradiente,
       tabuleiro de xadrez ou cor sólida) na largura e altura escolhidas e o salva em um arquivo.
   * - ``Off``
     - Em ``Color blindness preview``: desliga a prévia de deficiência de visão de cores.
   * - ``Protanopia (red-blind)``
     - Em ``Color blindness preview``: mostra a imagem no visualizador como uma pessoa com protanopia a
       vê; só na tela, o arquivo e a receita dele ficam intactos.
   * - ``Deuteranopia (green-blind)``
     - Em ``Color blindness preview``: simula a deuteranopia, a deficiência vermelho-verde mais comum;
       só na tela.
   * - ``Tritanopia (blue-blind)``
     - Em ``Color blindness preview``: simula a tritanopia (deficiência azul-amarelo); só na
       tela.
   * - ``Achromatopsia (greyscale)``
     - Em ``Color blindness preview``: mostra a imagem totalmente em tons de cinza, como na acromatopsia;
       só na tela.

Fluxo de Trabalho (Workflow)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``Culling``
     - Filtra a pasta atual para imagens escolhidas, rejeitadas ou sem marca, faz a triagem automática
       escolhendo a imagem mais nítida de cada grupo de imagens parecidas e rejeitando as demais, e pode
       excluir permanentemente todas as rejeitadas.
   * - ``Staging Tray``
     - Uma cesta persistente entre pastas: adicione os tiles selecionados ou a imagem atual de qualquer
       pasta, depois mova ou copie todos para uma pasta, ou mostre a bandeja como um álbum.
   * - ``Reference Panel``
     - Fixa imagens de referência (adicionadas de arquivos, arrastando e soltando ou a partir da imagem
       atual) com uma prévia grande para comparação lado a lado; a lista persiste entre reinicializações.
   * - ``Virtual Copies``
     - Salva snapshots nomeados da receita de revelação da imagem atual e alterna entre eles sem
       duplicar o arquivo.
   * - ``Dual-Pane File Manager``
     - Duas árvores de pastas lado a lado para copiar ou mover a seleção de uma para a outra, ou abrir
       um arquivo no visualizador.
   * - ``Macros``
     - Grava, edita, limpa e reproduz macros de ações de avaliação, favorito, etiqueta de cor e tag
       nas imagens selecionadas.
   * - ``Watched Folder``
     - Enquanto o diálogo está aberto, monitora uma pasta (incluindo subpastas) e atribui uma
       predefinição de revelação escolhida a cada nova imagem que chega, para fluxos de captura tethered
       ou de importação sem intervenção.

Exportação (Export)
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``Contact Sheet PDF``
     - Dispõe miniaturas das imagens selecionadas (ou da pasta inteira) em uma grade de linhas x colunas
       em páginas A4, A3, Letter ou Legal, com margens, um título opcional e legendas opcionais com o
       nome do arquivo. A caixa **Layout** preenche um preset — Default (4 × 5, 10 mm, com legendas),
       Compact (6 × 8, 5 mm, sem legendas), Proof (5 × 6, 8 mm, com legendas), Editorial (2 × 3, 18 mm,
       com legendas) ou Index (8 × 10, 4 mm, sem legendas), em colunas × linhas — e editar qualquer um
       desses valores à mão muda a caixa para Custom.
   * - ``Web Gallery``
     - Exporta as imagens selecionadas (ou a pasta inteira) como uma galeria HTML autocontida com
       miniaturas e lightbox; pode copiar os originais e adicionar caixas de comentário de revisão do
       cliente que são exportadas como JSON.
   * - ``Slideshow Video``
     - Renderiza as imagens selecionadas (ou a pasta inteira) em um MP4 com tamanho, taxa de quadros,
       tempo de exibição, qualidade e transição (fade, dissolve, slide ou wipe) escolhidos.
   * - ``Print Layout``
     - Dispõe imagens em uma grade de PDF de várias páginas com tamanho de página, orientação, linhas,
       colunas, margem, sarjeta e marcas de corte; requer o pacote opcional ``reportlab``.
   * - ``Collage``
     - Compõe as imagens selecionadas (ou a pasta inteira) em uma montagem em grade de 1 a 12 colunas,
       salvando ``collage.png`` ao lado da primeira imagem.
   * - ``ID Photo Sheet``
     - Repete o retrato atual em um tamanho de documento (35 x 45 mm, 2 x 2 pol, 33 x 48 mm ou
       50 x 70 mm) em papel 4x6, 5x7, A4 ou Letter a 300 DPI, salvando ``<name>_idsheet.png``.

Revelação Não Destrutiva (Develop)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``Before / After Compare``
     - Mostra a imagem atual sem e com a receita de revelação em uma única visualização, dividida por um
       divisor arrastável.
   * - ``Develop Presets…``
     - Salva a receita da imagem atual como uma predefinição nomeada e depois a aplica à imagem atual ou
       à seleção, ou mescla apenas os ajustes ativos dela nas receitas de cada uma.
   * - ``Tone Curve``
     - Edita uma curva RGB mestra e curvas separadas de vermelho, verde e azul sobre um histograma
       (clique para adicionar, arraste para mover, clique com o botão direito para remover um ponto);
       guardado na receita.
   * - ``Apply .cube LUT``
     - Aplica uma LUT 3D ou 1D ``.cube`` da Adobe com intensidade ajustável; guardado na receita, e
       ``Clear`` a remove.
   * - ``Split Toning``
     - Tinge sombras e realces com matiz e saturação separados, mais um slider de equilíbrio; guardado
       na receita.
   * - ``Local Adjustment Masks``
     - Adiciona máscaras de pincel, radiais e de gradiente linear, cada uma com a própria exposição,
       brilho, contraste, saturação, temperatura, matiz, realces, sombras e suavização; guardado na
       receita.
   * - ``Layers``
     - Empilha até oito camadas de sobreposição de texto, imagem ou LUT com opacidade e mesclagem
       normal, multiplicação, tela ou sobreposição; guardado na receita.
   * - ``Levels``
     - Define o ponto preto, o ponto branco e o gama; guardado na receita.
   * - ``Channel Mixer``
     - Reconstrói cada canal de saída a partir de entradas ponderadas de vermelho, verde e azul mais um
       deslocamento, com modo monocromático para conversão em preto e branco; guardado na receita.
   * - ``Gradient Map``
     - Mapeia a luminância por um gradiente predefinido (Mono, Sepia, Cyanotype, Fire, Ocean,
       Magenta–Teal) com intensidade ajustável, opcionalmente mesclado no espaço perceptual OkLCH;
       guardado na receita.
   * - ``Auto Color Balance``
     - Remove dominantes de cor com o método gray-world, white-patch, auto-levels (percentil) ou
       Retinex, mesclado por um slider de intensidade, salvando ``<name>_balanced.png``.
   * - ``Clarity / Dehaze``
     - Aplica os sliders de contraste local Dehaze, Clarity e Texture, salvando ``<name>_local.png``.
   * - ``HSL / Color Mixer``
     - Ajusta matiz, saturação e luminância separadamente para oito faixas de cor (do vermelho ao
       magenta), salvando ``<name>_hsl.png``.
   * - ``CLAHE (Local Equalize)``
     - Realça o contraste local com equalização adaptativa de histograma com limite de contraste
       (limite de corte e quantidade de blocos) na luminância, salvando ``<name>_clahe.png``.
   * - ``Flatten Background``
     - Remove um gradiente de fundo suave, como poluição luminosa ou iluminação irregular (subtrair),
       ou vinheta (dividir), com grau ajustável, salvando ``<name>_flat.png``.
   * - ``Frame & Caption``
     - Adiciona uma borda passe-partout colorida, uma faixa inferior opcional no estilo Polaroid e uma
       legenda, salvando ``<name>_framed.png``.
   * - ``Ordered Dither``
     - Reduz cada canal a 2 a 8 níveis com um padrão de dithering ordenado Bayer para um visual de
       impressão retrô, salvando ``<name>_dither.png``.
   * - ``Color Map``
     - Recolore a luminância da imagem pelo mapa de cores viridis, magma ou jet, salvando
       ``<name>_colormap.png``.
   * - ``Distort``
     - Aplica redemoinho, compressão / abaulamento ou ondulação à imagem com intensidade ajustável,
       salvando ``<name>_distort.png``.
   * - ``Polar Coordinates``
     - Enrola a imagem em um disco, ou desenrola um disco em uma faixa, opcionalmente invertendo o raio,
       salvando ``<name>_polar.png``.
   * - ``Kaleidoscope``
     - Espelha uma fatia em torno do centro em um padrão simétrico com número de segmentos e rotação
       escolhidos, salvando ``<name>_kaleidoscope.png``.
   * - ``Frosted Glass``
     - Espalha cada pixel para uma posição próxima aleatória (raio em pixels, semente reproduzível) para
       um visual de vidro texturizado, salvando ``<name>_frosted.png``.
   * - ``Pixel Sort``
     - Ordena pixels por brilho ao longo de linhas ou colunas dentro de uma faixa de brilho inferior /
       superior para um visual glitch, salvando ``<name>_pixelsort.png``.
   * - ``Film Grain``
     - Adiciona granulação de filme procedural com controles de intensidade, tamanho do grão,
       monocromático e semente; guardado na receita.
   * - ``Lens Flare``
     - Adiciona um lens flare sintético em uma posição escolhida com controles de intensidade, tamanho do
       halo e cor; guardado na receita.
   * - ``Threshold / Posterize``
     - Aplica um limiar de preto e branco (0 a 255) e / ou posteriza cada canal para 2 a 64
       níveis; guardado na receita.
   * - ``Solarize``
     - Inverte os tons acima de um limiar para um visual de solarização de laboratório, mesclado por um
       slider de mistura, salvando ``<name>_solarize.png``.
   * - ``Diffuse Glow``
     - Adiciona um brilho suave no estilo Orton com controles de quantidade, raio e limiar de realces,
       salvando ``<name>_glow.png``.
   * - ``Graduated Density``
     - Escurece um lado do quadro ao longo de uma linha reta como um filtro ND graduado (ângulo, stops,
       dureza, deslocamento, tingimento opcional), salvando ``<name>_gradnd.png``.
   * - ``Velvia``
     - Realça mais as cores apagadas, como o filme de slide Velvia, com sliders de intensidade e de
       proteção das sombras, salvando ``<name>_velvia.png``.
   * - ``Emboss``
     - Renderiza um relevo iluminado a partir de um azimute e uma elevação escolhidos, com slider de
       profundidade e opção de tons de cinza, salvando ``<name>_emboss.png``.
   * - ``Defringe``
     - Dessatura franjas roxas, verdes ou de todas as cores ao longo de bordas de alto contraste, com
       sliders de quantidade e de limiar de borda, salvando ``<name>_defringe.png``.
   * - ``Film Negative``
     - Inverte um negativo colorido escaneado em positivo, removendo a base laranja do filme (estimada
       automaticamente), com gama de saída, salvando ``<name>_positive.png``.
   * - ``Filmic Tone Map``
     - Suaviza os realces com uma curva filmic Reinhard ou Hable, com sliders de exposição, ponto
       branco, contraste e saturação, salvando ``<name>_filmic.png``.
   * - ``Tone Equalizer``
     - Define a exposição separadamente para pretos, sombras, tons médios, realces e brancos, com
       suavização para evitar halos, salvando ``<name>_toneeq.png``.
   * - ``Detail Equalizer``
     - Aumenta ou reduz o contraste separadamente nas faixas de detalhe fino, médio, grosso e amplo,
       salvando ``<name>_detaileq.png``.
   * - ``Soft Proof``
     - Pré-visualiza a imagem atual através de um perfil ICC de saída escolhido, pintando de magenta os
       pixels fora do gamut e contando-os; nada é salvo.

Retoque e Transformação (Retouch & Transform)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``AI Image Upscale``
     - Amplia uma pasta de imagens com Real-ESRGAN (geral x4, anime x4 ou x2) ou reamostragem Lanczos,
       Bicubic ou Nearest; os modelos de IA instalam o ``onnxruntime`` sob demanda e são baixados
       automaticamente no primeiro uso (~65 MB).
   * - ``Noise Reduction / Sharpening``
     - Aplica redução de ruído que preserva bordas (opcionalmente só na luminância) e nitidez por
       máscara de nitidez (unsharp mask) com quantidade e raio, salvando em um arquivo escolhido; requer
       OpenCV (``opencv-python``).
   * - ``Healing Brush``
     - Remove as manchas em que você clica em uma prévia (clique com o botão direito exclui uma mancha)
       por inpainting com o método Telea ou Navier-Stokes, salvando em um arquivo escolhido; requer OpenCV.
   * - ``Clone Stamp``
     - Copia um trecho de bordas suaves de um ponto de origem marcado com Shift+clique para cada ponto em
       que você clica em uma prévia (clique com o botão direito desfaz), salvando o resultado em um
       arquivo escolhido.
   * - ``Frequency Separation``
     - Divide a imagem atual em um raio de desfoque escolhido em ``<name>_low.png`` (cor e tom) e
       ``<name>_high.png`` (textura) para retoque em outro programa; recombine como low + (high - 128).
   * - ``Smart Crop``
     - Sugere recortes baseados em saliência (livre, 1:1, 4:5, 3:2, 16:9) que colocam o assunto em um
       ponto da regra dos terços, e grava o escolhido na receita como um recorte não destrutivo.
   * - ``Portrait Auto-Retouch``
     - Suaviza áreas de tom de pele, remove olhos vermelhos e adiciona uma passada final de nitidez,
       cada um com seu próprio slider, salvando ``<name>_retouched.png``.
   * - ``Face Detection``
     - Detecta rostos na imagem atual com a Haar cascade do OpenCV e deixa você nomear cada um; os
       nomes são salvos com a receita. Requer OpenCV 4 (``opencv-python<5``).
   * - ``Sky / Background``
     - Substitui o céu por um gradiente, ou remove o fundo para transparente ou branco, salvando em um
       arquivo escolhido; precisa de OpenCV e usa ``rembg`` para o recorte do fundo quando instalado.
   * - ``Crop / Straighten``
     - Gira até ±15° (cortando os cantos vazios) e recorta por coordenadas normalizadas ou por uma
       predefinição de proporção, salvando em um arquivo escolhido; o endireitamento requer OpenCV.
   * - ``Auto-Straighten``
     - Mede a inclinação do horizonte ou das linhas verticais, deixa você ajustar a rotação e salva a
       imagem endireitada em um arquivo escolhido; requer OpenCV.
   * - ``Lens Correction``
     - Corrige distorção de barril / almofada, vinheta e aberração cromática vermelho / azul com
       sliders, salvando em um arquivo escolhido.
   * - ``Scale Bar``
     - Grava na imagem atual uma barra de escala calibrada a partir de um valor de pixels por unidade e
       um rótulo de unidade, salvando ``<name>_scalebar.png``.

Multi-Imagem (Multi-Image)
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entrada
     - O que faz
   * - ``HDR Merge``
     - Funde duas ou mais fotos com exposições diferentes por fusão de exposição de Mertens (sem
       precisar de dados de exposição), opcionalmente alinhando-as antes; requer OpenCV.
   * - ``Panorama Stitch``
     - Costura duas ou mais fotos sobrepostas, tiradas em ordem com 20 a 40 % de sobreposição, no modo
       panorama ou flat-scan, opcionalmente cortando as bordas pretas; requer OpenCV.
   * - ``Focus Stacking``
     - Mescla um bracketing de foco em uma única imagem toda em foco mantendo os pixels mais nítidos de
       cada quadro, opcionalmente alinhando-os antes; requer OpenCV.
   * - ``Image Stack``
     - Combina uma sequência já alinhada pixel a pixel por média, mediana, máximo, mínimo ou média com
       sigma-clipping, para longas exposições, remoção de multidões ou rastros de estrelas; não precisa
       de OpenCV.
   * - ``Anaglyph 3D``
     - Combina a imagem atual (olho esquerdo) com uma imagem de olho direito escolhida em um anáglifo
       vermelho-ciano (método Dubois, colorido, cinza ou verdadeiro), salvando ``<name>_anaglyph.png``.

----


Uso na Linha de Comando
-----------------------

::

   python -m Imervue                          # Iniciar normalmente
   python -m Imervue /caminho/para/imagem     # Abrir uma imagem específica
   python -m Imervue /caminho/para/pasta      # Abrir uma pasta específica
   python -m Imervue --debug                  # Habilitar modo debug
   python -m Imervue --software_opengl        # Usar renderização por software (quando a GPU não é suportada)

CLI de lote sem interface
^^^^^^^^^^^^^^^^^^^^^^^^^

``Imervue.cli`` executa as operações de imagem puras a partir do shell **sem iniciar
o Qt**, o que o torna utilizável em scripts, etapas de CI e servidores sem display::

   py -m Imervue.cli resize photos/ --max 1600 --out web/
   py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
   py -m Imervue.cli info *.png --json
   py -m Imervue.cli list-ops          # imprime todos os subcomandos disponíveis

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Subcomando
     - Finalidade
   * - ``info`` / ``stats``
     - Dimensões e formato; métricas de qualidade sem referência (``--json`` para saída legível por máquina)
   * - ``convert`` / ``resize`` / ``thumbnail``
     - Conversão de formato (``--format`` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL,
       ``--quality``); redimensionamento pelo lado maior (``--max``) ou para ``--width`` /
       ``--height`` exatos; caixa de miniatura
   * - ``watermark`` / ``optimize``
     - Marca d'água de texto (``--text``, ``--corner``, ``--opacity``, ``--font-fraction``,
       ``--color R G B``, ``--no-shadow``); codificar sob um orçamento ``--max-kb``
   * - ``dehaze`` / ``clahe`` / ``dither`` / ``distort``
     - Remoção de neblina por canal escuro, equalização adaptativa, dithering Bayer ordenado, swirl / pinch / ripple
   * - ``auto-orient`` / ``strip``
     - Gravar a orientação EXIF nos pixels; salvar novamente sem EXIF / XMP / ICC
   * - ``collage`` / ``anaglyph``
     - Montagem em grade (``--columns``, ``--cell-width`` / ``--cell-height``, ``--gap``,
       ``--margin``, ``--background R G B``); 3D vermelho-ciano a partir de um par estéreo (``--method``)
   * - ``preset`` / ``pipeline``
     - Aplicar uma predefinição de revelação salva pelo nome; executar um pipeline JSON ordenado
   * - ``list-ops``
     - Listar todos os subcomandos (``--json`` para saída legível por máquina)

Todo subcomando decodifica como o visualizador: as saídas são endireitadas pela orientação EXIF e convertidas para sRGB a partir do perfil de cor embutido, entradas AVIF são lidas pelo próprio Pillow, e entradas HEIC / JPEG XL quando o backend opcional está instalado. Um RAW de câmera é revelado como no visualizador, em vez de lido pela pequena prévia embutida; ``resize`` e ``strip`` o gravam como PNG. Um arquivo ilegível é relatado e o restante é processado mesmo assim. Um arquivo incompleto é lido até onde vai, como no visualizador. Tons de cinza de 16 bits e de ponto flutuante são escalados para 8 bits como no visualizador; ``resize`` e ``strip`` mantêm a profundidade de bits da origem.

Os subcomandos que recebem arquivos ou pastas (todos exceto ``collage``, ``anaglyph`` e ``list-ops``) compartilham ``--out`` (diretório de saída), ``--recursive``, ``--dry-run`` (listar ações sem escrever nada), ``--overwrite`` e ``-j`` / ``--jobs`` (workers paralelos; ``0`` usa todos os núcleos). ``collage`` e ``anaglyph`` gravam o único arquivo indicado por ``--out``. ``--version`` mostra a versão da CLI.

Toda ferramenta do servidor MCP (veja `Servidor MCP`_) também é um subcomando. Dez delas são os
subcomandos acima (``convert_format`` é ``convert``, ``quality_metrics`` é ``stats``,
``build_collage`` é ``collage`` e assim por diante); as outras 48 executam o próprio código da ferramenta MCP:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tipo
     - Subcomandos
   * - Edições: gravam ``<stem>_<name>.png`` ao lado de cada origem, ou ``<stem>.png`` em ``--out``
     - ``frame``, ``crop``, ``rotate``, ``solarize``, ``glow``, ``velvia``, ``emboss``, ``film-negative``, ``defringe``, ``graduated-density``, ``filmic-tonemap``, ``tone-equalizer``, ``detail-equalizer``, ``colormap``, ``false-color``, ``split-toning``, ``pixel-sort``, ``polar``, ``kaleidoscope``, ``frosted-glass``, ``local-contrast``, ``posterize``, ``gradient-map``, ``film-grain``, ``levels``, ``auto-color-balance``, ``channel-mixer``, ``curve``, ``lens-correction``
   * - Outras saídas
     - ``ela`` (mapa de Error Level Analysis em PNG), ``video-frame`` (um quadro de um vídeo,
       ``--frame-index``), ``puppet-from-png`` (um rig ``.puppet``, ``--cell-size``)
   * - Relatórios: um resultado por imagem, ``--json`` para saída legível por máquina
     - ``metadata``, ``xmp``, ``gps``, ``dominant-colors``, ``sharpness``, ``statistics``, ``histogram``, ``ocr``, ``puppet-inspect``, ``puppet-validate``
   * - Executam uma vez e imprimem JSON
     - ``list-images FOLDER``, ``search FOLDER --query "..."``, ``similar FOLDER``,
       ``collection-stats FOLDER``, ``reverse-geocode --latitude .. --longitude ..``,
       ``puppet-schema --name ..``

Cada parâmetro MCP vira uma opção com o mesmo valor padrão e os mesmos valores permitidos: ``zone_gains``
vira ``--zone-gains``, um parâmetro sim/não vira ``--grayscale`` / ``--no-grayscale``, e uma cor ou uma
linha de matriz recebe seus valores em ordem (``--red 1 0 0``). ``py -m Imervue.cli <subcommand> --help``
lista todas elas::

   py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
   py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
   py -m Imervue.cli histogram a.jpg --json
   py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"

``pipeline FILE INPUTS…`` executa uma cadeia ordenada de operações em cada entrada e grava um PNG
por entrada: ``<stem>_pipeline.png`` ao lado da origem, ou ``<stem>.png`` em ``--out``. ``FILE`` é
um JSON em UTF-8 (uma marca de ordem de bytes não atrapalha) contendo uma lista de etapas ou um objeto
``{"pipeline": [...]}``. Cada etapa é um objeto com um ``"op"`` que nomeia a operação mais os
parâmetros dessa operação; um parâmetro omitido assume o valor padrão, e chaves que uma operação não
conhece são ignoradas. Um pipeline tem no máximo 50 etapas; um pipeline vazio grava cada entrada como foi
decodificada. O arquivo é verificado antes de qualquer imagem ser lida: um arquivo que não pode ser lido
ou interpretado imprime ``error: …``, e mais de 50 etapas, uma etapa sem nome em ``"op"`` ou uma operação
desconhecida imprimem uma linha ``pipeline error: step N: …`` por problema; em qualquer desses casos o
comando sai com código 2 e não grava nada. Um parâmetro do tipo errado (``null``, texto onde cabe um
número) faz aquela imagem falhar, o que é relatado, e o código de saída é 1.

.. list-table::
   :header-rows: 1
   :widths: 14 44 42

   * - Operação
     - Parâmetros (padrões)
     - Efeito
   * - ``dehaze``
     - ``strength`` (``1.0``; limitado a 0 – 1)
     - Remoção de neblina por dark channel prior; ``0`` deixa a imagem inalterada
   * - ``clahe``
     - ``clip`` (``2.0``; no mínimo 1), ``tiles`` (``8``; no mínimo 1)
     - Equalização adaptativa com limite de contraste da luminância em uma grade ``tiles`` × ``tiles``
   * - ``dither``
     - ``levels`` (``2``; limitado a 2 – 8)
     - Dithering Bayer ordenado 4×4 para ``levels`` valores por canal; alfa mantido
   * - ``distort``
     - ``mode`` (``"swirl"``: ``swirl`` / ``pinch`` / ``ripple``), ``strength`` (``0.5``;
       limitado a -1 – 1)
     - Deformação geométrica em torno do centro; em ``pinch`` uma intensidade positiva abaula e uma
       negativa comprime
   * - ``clarity``
     - ``amount`` (``0.5``; -1 – 1, negativo suaviza)
     - Contraste local de raio grande, ponderado nos tons médios
   * - ``texture``
     - ``amount`` (``0.5``; -1 – 1, negativo suaviza)
     - Contraste local de raio pequeno, para detalhes finos
   * - ``grayscale``
     - nenhum
     - Luma (0,299 R + 0,587 G + 0,114 B) nos três canais; alfa mantido
   * - ``invert``
     - nenhum
     - Inverte R, G e B; alfa mantido
   * - ``watermark``
     - ``text`` (``""``: sem marca d'água), ``corner`` (``"bottom-right"``: ``top-left`` /
       ``top-right`` / ``bottom-left`` / ``bottom-right`` / ``center``; qualquer outro valor conta como
       ``bottom-right``), ``opacity`` (``0.6``; limitado a 0 – 1)
     - Texto branco com sombra projetada, com 3,5 % do lado maior; ``--font-fraction``, ``--color`` e
       ``--no-shadow`` do subcomando ``watermark`` não têm parâmetro de etapa

Por exemplo, ``look.json``::

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

O Imervue inclui um servidor `Model Context Protocol <https://modelcontextprotocol.io>`_
embutido que permite que assistentes de IA chamem os helpers de lógica pura
do projeto sem uma GUI rodando. Inicie-o com::

   python -m Imervue.mcp_server

O servidor é livre de Qt e carrega apenas o que cada ferramenta precisa no momento
da chamada.

Ferramentas Disponíveis
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Ferramenta
     - Finalidade
   * - ``list_images``
     - Lista arquivos de imagem em uma pasta (caminho, tamanho, mtime). Passe
       ``recursive=true`` para percorrer subpastas.
   * - ``read_image_metadata``
     - Dimensões, formato, tags EXIF e campos XMP (sidecar ou, sem ele, embutidos) para uma
       imagem. Dados ausentes são reportados como o valor vazio apropriado
       em vez de gerar exceção.
   * - ``read_xmp_tags``
     - Caminho rápido que lê apenas o XMP (sidecar ou, sem ele, embutido) — avaliação, rótulo
       de cor, palavras-chave, título, descrição.
   * - ``convert_format``
     - Converte uma imagem para outro formato. O formato de destino é
       inferido pelo sufixo de destino (``png`` / ``jpg`` /
       ``jpeg`` / ``webp`` / ``tiff`` / ``bmp`` / ``avif``, e ``heic`` /
       ``jxl`` quando o backend opcional está instalado). O parâmetro opcional
       ``quality`` (1–100) se aplica a JPEG / WebP / AVIF / HEIC / JXL.
   * - ``puppet_from_png``
     - Constrói um rig ``.puppet`` a partir de um PNG usando o auto-mesh
       do plugin puppet. Inicializa o catálogo padrão de parâmetros Cubism
       para que o rig seja imediatamente dirigível.
   * - ``puppet_inspect``
     - Abre um arquivo ``.puppet`` e retorna um inventário estruturado:
       drawables, deformadores, parâmetros, motions, expressões, áreas
       de hit, partes, blends de parâmetro e rigs de física.
   * - ``puppet_validate`` / ``puppet_schema``
     - Verifica um ``.puppet`` contra o formato v1 (JSON Schemas, regras do carregador,
       verificações do rig); retorna um dos seus quatro JSON Schemas publicados.
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - Média/mín/máx/desvio padrão/mediana por canal, métricas de
       qualidade sem referência (colorfulness, entropia, contraste,
       densidade de bordas, ruído) e o histograma de 256 bins com frações
       de clipping de sub/superexposição.
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Pontuação de desfoque por variância Laplaciana, texto OCR via
       Tesseract (degrada graciosamente quando ausente) e uma prévia PNG
       em base64 limitada.
   * - ``find_similar``
     - Agrupa imagens quase duplicadas por hash perceptual (limiar de
       Hamming). Reporta o progresso por arquivo quando um token de
       progresso é fornecido.
   * - ``apply_watermark`` / ``apply_frame``
     - Grava uma marca d'água de texto ou envolve a imagem em uma moldura
       passe-partout / Polaroid com legenda opcional.
   * - ``build_collage``
     - Compõe várias imagens em uma montagem em grade (colunas, tamanho de
       célula, espaçamento, margem e fundo configuráveis). Reporta o
       progresso.
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - Recorte por caixa de pixels, redimensionamento (informar um lado mantém a
       proporção; informar os dois dá um tamanho exato) e rotação sem perdas de
       90/180/270 ou espelhamento horizontal/vertical.
       Tamanhos e coordenadas se referem à imagem endireitada pelo EXIF.
   * - ``collection_stats``
     - Resume avaliações, favoritos, rótulos de cor e estados de triagem de
       uma pasta (contagens, distribuição de 0–5 estrelas e média).
   * - ``reverse_geocode`` / ``extract_video_frame``
     - Resolve coordenadas GPS para a cidade mais próxima offline e
       decodifica um frame de um vídeo em uma imagem estática.
   * - ``extract_gps`` / ``dominant_colors``
     - Lê latitude/longitude GPS do EXIF (encadeia com ``reverse_geocode``);
       extrai uma paleta de cores por median-cut (rgb / hex / contagem de pixels).
   * - ``error_level_analysis``
     - Mapa de adulteração por Error-Level-Analysis de recompressão JPEG como um
       PNG data URI (regiões editadas se destacam contra o fundo).
   * - ``search_images``
     - Filtra uma pasta com a DSL de consulta dos smart albums (extensão / nome /
       tamanho / dimensões / proporção / câmera EXIF / lente / lugar).
   * - ``solarize_image`` / ``glow_image``
     - Aplica uma inversão tonal solarize ou um brilho difuso / Orton e salva
       o resultado.
   * - ``velvia_image`` / ``emboss_image`` / ``defringe_image``
     - Boost de saturação Velvia ponderado por luminância, relevo emboss de luz
       direcional e dessaturação de franjas de borda roxas/verdes.
   * - ``film_negative_image`` / ``graduated_density_image``
     - Inverte um negativo colorido escaneado (base de filme automática) e aplica
       um gradiente linear de densidade neutra graduada.
   * - ``filmic_tonemap_image`` / ``tone_equalizer_image`` / ``detail_equalizer_image``
     - Rolloff filmic de realces Reinhard/Hable, exposição por zona de luminância
       e contraste por banda de frequência.
   * - ``colormap_image`` / ``false_color_image``
     - Recolore a luminância por um mapa perceptual viridis/magma/jet, ou a mapeia
       para uma escala de exposição em falsas cores.
   * - ``dither_image`` / ``split_toning_image`` / ``pixel_sort_image``
     - Pontilhado ordenado (Bayer) para alguns tons por canal, split-toning de
       sombras/realces e ordenação de pixels por faixa de brilho.
   * - ``polar_image`` / ``kaleidoscope_image``
     - Distorce entre coordenadas retangulares e polares (tiny-planet), ou espelha
       o quadro em um número de cunhas de caleidoscópio.
   * - ``frosted_glass_image`` / ``clahe_image`` / ``local_contrast_image``
     - Espalhamento de vidro fosco por vizinho aleatório, equalização de histograma
       adaptativa limitada por contraste (CLAHE) e clareza de meios-tons + textura
       de detalhes finos.
   * - ``posterize_image`` / ``gradient_map_image``
     - Quantiza cada canal em algumas faixas planas, ou remapeia a luminância por
       um gradiente preto-para-branco misturado por intensidade.
   * - ``film_grain_image`` / ``dehaze_image`` / ``distort_image``
     - Granulação de filme gaussiana ajustável, remoção de névoa por
       dark-channel-prior e distorção geométrica de redemoinho / pinça / ondulação.
   * - ``levels_image`` / ``curve_image``
     - Níveis de ponto preto/branco e gama, e um preset mestre de curva de tons
       (curva em S, clarear sombras, comprimir realces).
   * - ``auto_color_balance_image`` / ``channel_mixer_image``
     - Balanço de branco automático (gray-world, white-patch, percentile-stretch,
       retinex) e um mixer de canais 3x3 com conversão mono.
   * - ``lens_correction_image``
     - Corrige distorção barril/pincushion (k1), eleva ou aprofunda a vinheta dos
       cantos e cancela a aberração cromática vermelha/azul.

Toda ferramenta anuncia um ``outputSchema`` JSON e ``annotations`` de
somente-leitura / destrutivas, e retorna seu resultado como
``structuredContent`` junto com o envelope de texto (campos de revisões posteriores do MCP; o
handshake informa ``2025-03-26``), de modo que os clientes consomem payloads tipados sem
re-parsear. Ferramentas de longa duração transmitem
``notifications/progress`` quando o chamador passa um token de progresso.

Prompts
^^^^^^^

O servidor expõe quatro prompts via ``prompts/list`` / ``prompts/get``:
``caption_image``, ``suggest_edits``, ``analyze_composition`` (uma crítica
de composição guiada por saliência) e ``flag_issues`` (uma triagem de
nitidez + qualidade + clipping). ``completion/complete`` sugere valores para o ``style`` de
``suggest_edits`` e o ``focus`` de ``analyze_composition``.

Claude Code (Nível de Projeto)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O repositório inclui um ``.mcp.json`` em nível de projeto na raiz do repositório:

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

``py`` é o Python Launcher do Windows; no macOS ou Linux use ``python3`` ou o interpretador do
ambiente em que o Imervue está instalado. Abrir qualquer subdiretório do repositório no Claude Code
descobre automaticamente este servidor. O Claude Code pergunta antes de habilitar servidores de projeto na
primeira vez — aceite o prompt para usá-lo.

Claude Desktop
^^^^^^^^^^^^^^

Adicione a mesma entrada à sua configuração do Claude Desktop:

* macOS: ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\Claude\claude_desktop_config.json``

Use um diretório de trabalho absoluto ou ative um virtualenv no qual o
Imervue esteja instalado; a invocação ``python`` deve resolver para um
interpretador capaz de ``import Imervue``.

Superfície do Protocolo
^^^^^^^^^^^^^^^^^^^^^^^

O servidor lê mensagens JSON-RPC 2.0 delimitadas por quebra de linha no stdin e grava respostas e
notificações no stdout, uma linha UTF-8 cada. Ele responde ao ``initialize`` com a versão de protocolo
``2025-03-26`` qualquer que seja a versão pedida pelo cliente. As requisições são tratadas uma de cada
vez; um lote (um array JSON) é recusado com ``-32600``.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Método
     - O que faz
   * - ``initialize``
     - Handshake. Retorna ``protocolVersion`` ``2025-03-26``, ``serverInfo`` (``imervue``
       ``1.0.0``) e as capabilities ``tools`` e ``prompts`` (``listChanged: false``),
       ``resources`` (``subscribe: true``, ``listChanged: true``), ``completions`` e ``logging``.
   * - ``ping``
     - Retorna um resultado vazio.
   * - ``tools/list``
     - Todas as 58 ferramentas em uma única página, cada uma com ``inputSchema``, ``outputSchema`` e
       ``annotations`` (``readOnlyHint`` / ``destructiveHint`` / ``idempotentHint`` / ``openWorldHint``).
   * - ``tools/call``
     - Executa ``{"name", "arguments"}``. O resultado é um bloco de conteúdo ``text`` com o valor de
       retorno codificado em JSON, mais ``structuredContent`` quando ele é um objeto. Uma ferramenta que
       lança uma exceção, ou argumentos que não se encaixam nos parâmetros dela, dão ``isError: true`` e
       um texto ``Error: …`` em vez de um erro de protocolo; um nome de ferramenta desconhecido é ``-32602``.
   * - ``prompts/list``
     - Os quatro prompts com seus argumentos.
   * - ``prompts/get``
     - Monta as mensagens de ``{"name", "arguments"}``; ``caption_image`` e
       ``analyze_composition`` incorporam uma miniatura PNG como mensagem de imagem. Um prompt
       desconhecido ou um ``path`` ausente é ``-32602``.
   * - ``completion/complete``
     - Valores correspondentes por prefixo para um argumento ``ref/prompt``: ``style`` de
       ``suggest_edits`` (general, portrait, landscape, product, street, food, macro) e ``focus`` de
       ``analyze_composition`` (all, framing, balance, subject, leading_lines). Qualquer outro argumento
       recebe uma lista vazia.
   * - ``resources/list``
     - As imagens diretamente na pasta indicada por ``IMERVUE_MCP_ROOT`` (arquivos ocultos e SVG
       ficam de fora), 100 por página com um ``nextCursor``; vazio quando a variável não está definida.
   * - ``resources/templates/list``
     - Os dois templates de URI da tabela abaixo.
   * - ``resources/read``
     - Lê uma URI ``imervue://image/…`` (veja abaixo).
   * - ``resources/subscribe`` / ``resources/unsubscribe``
     - Adiciona ou remove uma URI do conjunto que recebe ``notifications/resources/updated``.
   * - ``logging/setLevel``
     - Define o nível mais baixo (``debug``, ``info``, ``notice``, ``warning``, ``error``,
       ``critical``, ``alert``, ``emergency``; ``info`` no início) enviado como
       ``notifications/message``; qualquer outro valor é ``-32602``.
   * - ``notifications/*`` vindas do cliente
     - Aceitas sem resposta (``notifications/initialized``, ``notifications/cancelled``, …);
       um cancelamento não interrompe uma ferramenta em execução.
   * - ``notifications/progress`` (enviada)
     - ``{progressToken, progress, total, message}`` enquanto ``find_similar`` ou ``build_collage``
       executa, quando a requisição ``tools/call`` trouxe ``params._meta.progressToken`` (uma string ou
       um inteiro); ``progress`` só aumenta.
   * - ``notifications/resources/updated`` (enviada)
     - ``{uri}`` quando um arquivo em ``IMERVUE_MCP_ROOT`` muda e a URI da miniatura dele está assinada.
   * - ``notifications/resources/list_changed`` (enviada)
     - Em qualquer mudança em ``IMERVUE_MCP_ROOT`` (monitorada com watchdog, sem recursão),
       assinada ou não.
   * - ``notifications/message`` (enviada)
     - Entradas de log no nível de ``logging/setLevel`` ou acima, enviadas por
       ``MCPServer.emit_log``. As ferramentas embutidas não o chamam, então o servidor padrão não envia nenhuma.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - URI
     - Retorna
   * - ``imervue://image/{path}``
     - Uma miniatura PNG da imagem — na orientação correta, cabendo em 256 px — como um ``blob`` base64
       com ``mimeType`` ``image/png``. ``resources/list`` retorna URIs nesse formato.
   * - ``imervue://image/{path}/metadata``
     - O resultado de ``read_image_metadata`` (dimensões, formato, EXIF, XMP) como ``text`` JSON com
       ``mimeType`` ``application/json``.

``{path}`` é o caminho do arquivo da imagem totalmente codificado em percent-encoding, incluindo
separadores e os dois-pontos da unidade (``C:\photos\a.jpg`` é ``imervue://image/C%3A%5Cphotos%5Ca.jpg``).
Uma leitura resolve o caminho diretamente, então funciona para qualquer arquivo, não só os que estão em
``IMERVUE_MCP_ROOT``; um caminho com um segmento ``..`` é ``-32602``, um arquivo inexistente ``-32002`` e
uma URI com outro esquema ``-32602``.

Os erros usam os códigos JSON-RPC ``-32700`` (uma linha que não é JSON), ``-32600`` (não é um objeto de
requisição, ou não tem ``method``), ``-32601`` (método desconhecido), ``-32602`` (parâmetros inválidos,
ferramenta ou prompt desconhecido, nível de log ou cursor inválido, URI de recurso não suportada),
``-32002`` (arquivo do recurso não encontrado) e ``-32603`` (erro interno).

A implementação está em ``Imervue/mcp_server/``:

* ``server.py`` — o despachante JSON-RPC (``MCPServer``), o loop stdio (``run``) e o
  monitor de ``IMERVUE_MCP_ROOT``.
* ``tools.py`` — a face pública do conjunto de ferramentas: reexporta todos os handlers e registra as
  ferramentas padrão (``register_default_tools``).
* ``tools_read.py`` / ``tools_edit.py`` — os handlers das ferramentas (listagem, metadados e análise;
  edições gravadas em um destino), com helpers compartilhados em ``tool_support.py``.
* ``tool_defs_read.py`` / ``tool_defs_edit.py`` — o nome, a descrição, o schema de entrada e o handler
  de cada ferramenta, na ordem de ``tools/list``.
* ``tool_schemas.py`` — o ``outputSchema`` e as ``annotations`` de cada ferramenta.
* ``prompts.py`` / ``completion.py`` — os quatro prompts e as sugestões de
  ``completion/complete``.
* ``resources.py`` — os recursos ``imervue://image/``.
* ``progress.py`` / ``notifications.py`` / ``logging.py`` — relatório de progresso, o gravador de stdout
  com trava e as assinaturas de recursos, e a filtragem por nível de log.
* ``__main__.py`` — ponto de entrada ``python -m Imervue.mcp_server``.

Ferramentas customizadas podem ser registradas construindo :class:`MCPServer`, chamando
:meth:`MCPServer.register` (nome, descrição, schema de entrada, handler, schema de saída e annotations
opcionais; um nome duplicado lança ``ValueError``; um handler com um parâmetro ``progress`` recebe um
reporter de progresso) e passando cada mensagem para :meth:`MCPServer.handle_message`, que retorna a
resposta ou ``None`` para uma notificação. :func:`run` sempre monta o próprio servidor com as
ferramentas padrão, então um conjunto customizado precisa do próprio loop; defina ``server.notifier``
como um ``Notifier`` no fluxo de saída para que as notificações sejam enviadas.
