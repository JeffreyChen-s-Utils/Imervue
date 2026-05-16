Guia do Usuário do Imervue
==========================

Uma estação de trabalho de imagens acelerada por GPU que oferece **quatro abas principais**.
A maior parte deste guia está organizada em torno dessas quatro seções.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Aba
     - O que faz
   * - **Imervue**
     - Navega, visualiza, organiza, pesquisa e processa em lote sua biblioteca de imagens.
       Consulte *Aba Imervue — Visualizador de Imagens e Biblioteca*.
   * - **Modify**
     - Pipeline de revelação não destrutiva — sliders, curvas, LUTs, máscaras,
       retoque, multi-imagem. Consulte *Aba Modify — Revelação Não Destrutiva*.
   * - **Paint**
     - Estúdio raster de pintura completo com pincéis, camadas, animação,
       ferramentas para mangá e I/O de PSD. Consulte *Aba Paint — Editor Raster Completo*.
   * - **Puppet**
     - Animador de fantoches 2D com rig construído do zero — meshes, deformadores, parâmetros,
       movimentos, física. Consulte *Aba Puppet — Animação 2D com Rig*.

As seções *Primeiros Passos*, *Referência*, *Sistema de Plugins* e *Servidor MCP*
que vêm a seguir são transversais — aplicam-se a todas as quatro abas.

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
- **Direita**: Barra lateral EXIF. Exibe as informações de captura da imagem selecionada.

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
     - ``Arquivo`` > ``Abrir Imagem``, depois escolha um arquivo
   * - Arrastar e Soltar
     - Arraste uma imagem ou pasta diretamente para a janela
   * - Abrir pelo Explorador
     - Clique com o botão direito em uma imagem > ``Open with Imervue`` (requer associação de arquivos)
   * - Arquivos Recentes
     - ``Arquivo`` > ``Recentes``, reabra rapidamente uma pasta visitada anteriormente

Formatos Suportados
^^^^^^^^^^^^^^^^^^^

- **Padrão**: PNG, JPEG, BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 (Canon), NEF (Nikon), ARW (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus)

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
   * - Deslocar com o teclado
     - Teclas de seta; segure ``Shift`` para movimento fino

Cada miniatura mostra emblemas de status: uma faixa colorida na borda esquerda (rótulo de cor),
um coração no canto superior esquerdo (favorito), uma estrela no canto superior direito (marcador) e
estrelas de avaliação no canto inferior esquerdo. Um indicador de carregamento é desenhado para
miniaturas que ainda estão sendo carregadas.

Modo Lista (Detalhes)
^^^^^^^^^^^^^^^^^^^^^

Pressione ``Ctrl + L`` para alternar entre a grade de miniaturas e uma visualização em lista ordenável
com estas colunas: Pré-visualização · Rótulo · Nome · Resolução · Tamanho · Tipo · Modificado.
Clique duas vezes em uma linha (ou pressione ``Enter``) para entrar no Deep Zoom; pressione ``Esc``
para retornar à lista. Miniaturas e metadados são carregados de forma lazy em uma thread de trabalho
para que pastas muito grandes permaneçam responsivas.

Modo Deep Zoom
^^^^^^^^^^^^^^

Clique em uma miniatura para entrar no modo Deep Zoom para visualização individual de alta qualidade.

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
     - ``Shift + P`` — em zoom ≥ 400 %, sobrepõe uma grade de pixels e mostra RGB / HEX sob o cursor
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

No modo Deep Zoom você pode avaliar imagens rapidamente:

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

Marcadores de cor independentes baseados em flags, armazenados separadamente da avaliação por estrelas
de 1 a 5. Úteis para categorização rápida (ex.: vermelho = candidatos a rejeição, verde = selecionadas,
azul = a retocar).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Tecla
   * - Vermelho / Amarelo / Verde / Azul / Roxo
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (pressione a mesma tecla novamente para limpar)
   * - Aplicação em lote à seleção
     - Selecione várias miniaturas, depois pressione a tecla F correspondente
   * - Filtrar por cor
     - ``Filtrar`` > ``Por Rótulo de Cor`` > escolha uma cor / Qualquer rótulo / Sem rótulo

A barra de status mostra um chip colorido para a imagem atual. As miniaturas exibem uma faixa colorida
na borda esquerda. A **Visualização em Lista** tem colunas dedicadas de **Rótulo** e **Avaliação por Estrelas**
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
     - Clique com o botão direito na imagem > ``Adicionar à Tag``
   * - Adicionar ao álbum
     - Clique com o botão direito na imagem > ``Adicionar ao Álbum``
   * - Filtrar por tag/álbum único
     - ``Filtrar`` > ``Por Tag`` / ``Por Álbum``
   * - Filtro multi-tag (E / OU)
     - ``Filtrar`` > ``Filtro Multi-Tag…`` — marque várias tags ou álbuns, escolha Qualquer (OU) ou Todos (E)

Classificação e Filtragem
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Recurso
     - Localização no Menu
   * - Ordenar por nome
     - ``Ordenar`` > ``Por Nome``
   * - Ordenar por data de modificação
     - ``Ordenar`` > ``Por Data de Modificação``
   * - Ordenar por tamanho do arquivo
     - ``Ordenar`` > ``Por Tamanho do Arquivo``
   * - Ordenar por resolução
     - ``Ordenar`` > ``Por Resolução``
   * - Crescente / Decrescente
     - ``Ordenar`` > ``Crescente`` / ``Decrescente``
   * - Filtrar por extensão
     - ``Filtrar`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
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
Você também pode pressionar ``E`` ou clicar com o botão direito > ``Modify`` no modo Deep Zoom.

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
   * - Sombras
     - Levantar ou esmagar detalhes em regiões de tons escuros
   * - Meios-Tons
     - Ajustar a faixa tonal intermediária sem afetar pretos e brancos
   * - Realces
     - Recuperar realces estourados ou empurrar áreas claras ainda mais
   * - Vibração
     - Reforço de saturação consciente — protege tons de pele e cores já saturadas

Esses ajustes são **não destrutivos**. Cada slider grava em uma receita de edição armazenada
por imagem; pressione ``Reset`` a qualquer momento para restaurar o original, ou ``Ctrl + Z``
para voltar passo a passo nas alterações individuais. As receitas sobrevivem a reinicializações
e podem ser exportadas / sincronizadas via o fluxo de sidecar XMP descrito na seção Metadados.

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
quadros de animação e importação/exportação PSD. Mude para ela pela barra de abas ou
pressione ``E`` no modo Deep Zoom para enviar a imagem atual diretamente para uma nova aba Paint.

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
pixels apagados não vazam para uma nova pintura.

::

   +------+----------------------+----------------+
   | Barra|                      | Cor · Pincel   |
   | de   |   Tela (pintar)      | Camada · Nav.  |
   | Ferr.|                      | Material · …   |
   +------+----------------------+----------------+

Os docks do lado direito (Cor, Pincel, Camada, Navegador, biblioteca de Materiais,
Histórico, Paleta, Referência, Histograma, Animação) são organizados em abas em
uma única coluna para que a tela mantenha toda a altura visível. Arraste o título
de qualquer dock para reorganizar ou flutuar um painel, depois salve o resultado
via ``Configurações`` > ``Layouts de Espaço de Trabalho…``.

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
     - Preenchimento por inundação com tolerância / contíguo / amostrar todas as camadas
   * - Conta-gotas
     - ``I``
     - Selecionar cor de primeiro plano a partir da tela
   * - Mover
     - ``V``
     - Transladar a camada ativa ou seleção
   * - Retângulo / Laço / Varinha / Seleção Rápida
     - ``M`` / ``L`` / ``W``
     - Ferramentas de seleção com modos Substituir / Adicionar / Subtrair / Interseccionar
   * - Texto
     - ``T``
     - Editor de texto inline com fonte / tamanho / negrito / itálico
   * - Gradiente
     - ``U``
     - Preenchimento por gradiente Linear / Radial / Angular / Diamante
   * - Desfoque / Esfumar
     - ``R``
     - Manipulação local de pixels
   * - Caneta (Bezier)
     - ``P``
     - Caminho vetorial com edição de âncoras / alças
   * - Carimbo de Clonar
     - ``S``
     - Shift+clique define a origem, clique carimba com pluma
   * - Balão de Fala
     - ``Ctrl + B``
     - Balão estilo quadrinho / mangá com cauda automática
   * - Retângulo / Elipse / Linha / Polígono
     - ``Shift + R/E/I/P``
     - Primitivas vetoriais de forma com traço + preenchimento
   * - Recortar
     - ``C``
     - Recorte interativo com presets de proporção
   * - Transformar
     - ``Ctrl + T``
     - Alças de transformação livre / escala / rotação / inclinação
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
   * - Caneta
     - Linha nítida e antialiased, o pincel do dia a dia
   * - Marcador / Marca-texto
     - Traços largos e semitransparentes que se sobrepõem
   * - Lápis
     - Linha fina de grafite levemente texturizada
   * - Spray
     - Pontos dispersos controlados por densidade e fluxo
   * - Caligrafia
     - Largura varia com a direção do traço
   * - Aquarela
     - Vazamento de borda úmida e mistura suave
   * - Carvão / Giz de cera
     - Traços ásperos e texturizados com inclinação por pressão

Cada pincel expõe Tamanho / Opacidade / Dureza / Densidade / Modo de Mistura no
**dock Pincel** e na **barra de Opções** superior. Use ``Configurações`` >
``Curva de Pressão…`` para remapear a pressão da tablet para largura ou opacidade,
e ``Editar`` > ``Capturar Ponta de Pincel…`` para transformar uma seleção em uma
ponta de pincel personalizada.

Camadas
^^^^^^^

O **dock Camada** oferece miniaturas, alternâncias de visibilidade, renomeação
inline, arrastar para reordenar, e o modo de mistura + opacidade da camada ativa.
O menu ``Camada`` adiciona:

- **Nova / Vetorial / Duplicar / Mesclar Abaixo** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Máscaras** — Adicionar Máscara / A partir da Seleção / Inverter / Aplicar / Excluir
  (``Ctrl + Shift + M`` adiciona; ``Ctrl + Alt + Shift + M`` adiciona a partir da seleção)
- **Máscara de Recorte** — recortar a camada acima ao alfa atual
  (``Ctrl + Alt + G``)
- **Efeitos de Camada** — Sombra Projetada · Brilho Externo · Traço; limpar efeitos
- **Camada de Referência** — fixar uma camada como fonte do conta-gotas
- **Camada 1-bit** — alternar a camada ativa para uma camada binária de line-art
- **Dividir Camada por Cor** — dividir uma camada de cor plana em uma camada por
  cor para facilitar repinturas com balde
- **Mapa de Gradiente** — submenu de presets (sépia / pôr-do-sol / cianotipo …)

Seleções
^^^^^^^^

Use as ferramentas retângulo / laço / varinha / seleção rápida, depois o
**Traçar Seleção…** no menu **Editar** para contornar a marquise com o pincel atual.
``Q`` alterna o **Modo Máscara Rápida** — pinte com qualquer pincel para refinar a
borda da seleção em vermelho, depois pressione ``Q`` novamente para convertê-la de
volta em uma marquise.

Animação
^^^^^^^^

O **dock Animação** transforma o documento em uma tira de quadros:

- ``Adicionar Quadro`` captura o estado atual da camada em um novo keyframe.
- Clique na miniatura de um quadro para saltar até ele.
- ``Onion Skin`` (menu Visualizar) sobrepõe quadros vizinhos com baixa transparência.
- Exporte a tira via **Arquivo > Exportar páginas** (CBZ para leitores de quadrinhos,
  PDF para impressão) ou **Exportação de Animação** para MP4 / GIF.

Menu Mangá
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Ação
     - Descrição
   * - Cortador de Painéis
     - ``Ctrl + Shift + P`` — divide a tela em uma grade de painéis de quadrinhos com linhas / colunas / sarjeta / borda / margem configuráveis
   * - Alternar Camada de Tom
     - Converter a camada ativa em uma camada de tom (pontos de meio-tom)
   * - Carimbar Números de Página
     - Adicionar números de página em documentos de várias páginas
   * - Linhas de Velocidade
     - Geradores de linhas de velocidade Radial / Paralelas / Explosão
   * - Action Flash
     - Sobreposição estilo mangá de explosão / impacto
   * - Ferramenta Balão de Fala
     - Arraste um balão, solte a cauda em direção ao falante

Filtros
^^^^^^^

``Filtro`` abre uma caixa de diálogo com pré-visualização ao vivo para cada efeito:

- **Níveis** — sliders preto / gama / branco, por canal
- **Curvas** — pontos arrastáveis (RGB / R / G / B) com interpolação cúbica monotônica
- **Posterizar** — quantizar cor em N passos
- **Limiar** — converter para preto / branco puro em um corte
- **Balanço Automático de Cor** — neutralizar dominâncias via grey-world / white-patch
- **Granulação de Filme** — ruído de luminância com tamanho e quantidade ajustáveis
- **Converter para Meio-Tom** — tela de pontos estilo jornal

Auxílios de Visualização
^^^^^^^^^^^^^^^^^^^^^^^^

- **Grade de Pixels** (``Ctrl + Shift + '``) — sobrepor grade de um pixel em zoom alto
- **Encaixar em Pixel / Bordas** — colocação sub-pixel travada em coordenadas inteiras
- **Onion Skin** — sobreposição de vizinhos para animação
- **Guias de Sangria** — guias de sangria de impressão / zona segura
- **Rotacionar Tela** (``Ctrl + Shift + H``) — rotação da visualização sem rasterizar

I/O de Arquivos
^^^^^^^^^^^^^^^

- **Abrir PSD…** (``Ctrl + O``) e **Salvar como PSD…** (``Ctrl + S``) — round-trip de PSD em camadas com máscaras, modos de mistura e efeitos de camada
- **Exportar imagem…** — achatar e salvar como PNG / JPEG / WebP / BMP / TIFF
- **Exportar páginas → CBZ** / **→ PDF** — exportação de documento multi-quadro para quadrinhos
- **Importar / Exportar presets de pincel**, **Importar paleta** — compartilhar recursos entre instalações
- **Snapshots de autosalvamento** — snapshots periódicos em segundo plano com restauração do último a partir do menu Arquivo

Layouts de Espaço de Trabalho
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Configurações`` > ``Layouts de Espaço de Trabalho…`` salva o arranjo dos docks,
o estado das opções de ferramenta e os painéis ativos com um nome, depois alterna
entre eles com um clique — por exemplo, um layout "Desenho" com os docks Pincel +
Cor em destaque e um layout "Composição" com os docks Camada + Histórico expandidos.

----

Espaço de Trabalho Puppet (Aba Puppet)
--------------------------------------

A quarta aba principal — **Puppet** — é um sistema de animação de fantoches 2D
com rig construído do zero. Faz o que o Live2D faz (rigs de deformação de mesh,
parâmetros, motions, física, expressões, grupos de pose, sincronização labial,
rastreamento por webcam) mas **sem SDK proprietário**, **sem `live2d-py`**, e com
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

Fluxo de Trabalho de Ponta a Ponta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Importar um PNG** — a barra de ferramentas ``Import PNG…`` executa
   ``puppet.auto_mesh.puppet_from_png``: grade triangulada limitada por alfa,
   um drawable, pronto para renderizar.
2. **Adicionar um deformador** — ``Add Rotation Deformer`` (âncora + ângulo) ou
   ``Add Warp Deformer`` (lattice Bezier de linhas × colunas; os vértices fora
   dos limites passam sem alteração).
3. **Adicionar um parâmetro** — ``Add Parameter`` adiciona um slider ao dock
   **Parâmetros** à direita com id auto-nomeado (``Param1``, ``Param2``, …).
4. **Definir keys** — arraste o slider para um extremo, edite a forma do deformador
   em código ou via edição de mesh, pressione **Set key**. Repita no neutro e
   no extremo oposto. O runtime então faz lerp dos campos do deformador entre
   keys adjacentes sempre que o slider se move.
5. **Salvar** — ``Save As…`` grava o rig + texturas + motions + expressões
   + física em um único zip ``.puppet`` que você pode compartilhar ou abrir
   depois via ``Open Puppet…``.

Experimente um Exemplo Pronto
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O repositório inclui uma demo totalmente riggada em
``examples/puppet/march_7th.puppet`` — um rig Cubism Live2D de 307 drawables
convertido in-tree. Texturas e morphs de vértice por parâmetro são embutidos
no zip ``.puppet``, então a demo abre com o ``requirements.txt`` padrão sem
redistribuir o Cubism SDK.

O rig carrega 203 parâmetros padrão Cubism (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …), então
todo driver de entrada padrão (webcam, piscar, sincronização labial, olhar do
cursor) o aciona sem configuração por rig. Nove motions em loop estão incluídos
no pacote — loops de idle do Cubism convertidos pelo autor mais loops de
gestos de referência nos grupos ``Idle`` e ``TapHead``.

Abra a aba Puppet, clique em **Open Puppet…**, aponte para
``march_7th.puppet`` — a figura aparece centralizada. Arraste qualquer slider
de parâmetro para acionar uma articulação, ou clique em um dos motions no dock
Motions — clique único vincula o motion e inicia a reprodução imediatamente.

**Executando o exemplo incluído, passo a passo:**

1. Inicie o Imervue. A partir do código-fonte: ``python -m Imervue``. A partir
   do build empacotado: execute o executável / bundle de aplicativo ``Imervue``.
   O diretório ``examples/`` é empacotado tanto na wheel quanto no EXE Nuitka,
   então o rig está no disco onde quer que você tenha instalado.
2. Clique na aba **Puppet** no topo da janela.
3. Barra de ferramentas → **File > Examples > March 7Th** (ou o dropdown
   **Examples ▾** da barra de ferramentas). O rig de 307 drawables carrega
   centralizado e o dock de parâmetros é preenchido com os 203 sliders padrão Cubism.
4. No dock **Motions** inferior, clique uma vez em qualquer entrada de motion
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …).
   A reprodução inicia imediatamente; clique novamente para parar, ou escolha
   um motion diferente para fazer cross-fade nele.
5. Alterne os interruptores de entrada ao vivo na barra de ferramentas para
   acionar o rig com suas próprias entradas — **Drag-track head** para olhar
   do cursor, **Auto-blink** para fechamento cíclico dos olhos, **Auto idle**
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

O schema completo (drawables, deformadores, parâmetros, motions, expressões,
pose, física) está em ``Imervue/puppet/FORMAT.md`` no repositório. Somente JSON +
PNG — sem binário proprietário, totalmente diff-vel via git.

Referência da Barra de Ferramentas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Ação
     - Finalidade
   * - Open Puppet… / Examples ▾
     - Carrega um ``.puppet`` do disco, ou escolhe um dos rigs incluídos
       em ``examples/puppet/`` diretamente da barra de ferramentas
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
     - Criar o rig a partir da barra de ferramentas
   * - Drag-track head
     - Offset do cursor → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Ciclo cosseno close→open em ``ParamEyeLOpen`` / ``ParamEyeROpen``
       a cada ~4,5 s (caminho force-write ignora o no-change-skip do canvas
       para que drivers concorrentes não travem o piscar)
   * - Mic lip-sync
     - RMS do microfone → ``ParamMouthOpenY`` (requer ``sounddevice``)
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
     - Captura mudanças de parâmetro em um novo ``Motion`` e o adiciona
       ao documento — bake-from-take, sem autoração manual de keys
   * - Capture frame… / Record… / Export all motions…
     - Salvar um único PNG, alternar gravação de GIF / WebM / MP4, ou
       renderizar em lote cada motion do rig em seu próprio arquivo (tudo via
       o mesmo caminho de render off-screen apenas-personagem usado para streaming)
   * - Output > Virtual camera / NDI output
     - Superfícies de streaming ao vivo — ver *Streaming ao vivo para o OBS* acima
   * - Reset to rest
     - Snap-stop do player de motion, desativa todo driver ao vivo,
       limpa expressões / grupos de pose, restaura padrões de parâmetro
   * - Fit to Window
     - Recentralizar + redimensionar o puppet no canvas

Gravando Seus Próprios Motions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Para capturar uma take customizada em vez de autorizar keyframes manualmente:

1. Alterne **Record motion** na barra de ferramentas — uma caixa de diálogo de nome aparece.
2. Enquanto grava, arraste sliders, habilite **Webcam tracking**, deixe a física
   rodar, qualquer coisa que escreva valores de parâmetro.
3. Desative **Record motion** — o gravador bake do stream capturado a 30 Hz
   em um ``Motion`` com uma trilha de segmento linear por parâmetro que
   efetivamente se moveu (parâmetros que ficaram parados são descartados).
   O novo motion aparece no dock **Motions** inferior imediatamente, pronto
   para reproduzir / repetir / salvar.

Motions customizados salvos dessa forma fazem round-trip pelo mesmo payload
JSON ``motions/<name>.json`` que os autorizados manualmente.

Streaming ao Vivo para o OBS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dois caminhos de saída, ambos renderizando o puppet sozinho (sem fundo de
checker, sem cromo do editor) em um framebuffer off-screen antes de entregá-lo
à superfície de streaming. O lado mais longo da saída é limitado a 1080 px
para que canvases nativos Cubism (March 7th é 3503×7777) não sejam rejeitados
por drivers de câmera virtual DirectShow.

**A. Virtual Camera** — aparece como uma webcam na lista de fontes *Video
Capture Device* do OBS. ``pip install pyvirtualcam`` mais o driver de plataforma:
o OBS Studio 26+ inclui o driver *OBS Virtual Camera* no Windows / macOS
(clique em *Start Virtual Camera* no OBS uma vez para registrá-lo); o Linux usa
``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
A barra de ferramentas **Output > Virtual camera** abre o stream.

DirectShow / AVFoundation / v4l2loopback são apenas RGB — sem canal alfa — então
o Imervue preenche a área fora do personagem com **magenta `#FF00FF`** como uma
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
A barra de ferramentas **Output > NDI output** transmite a fonte (nome
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

O plugin degrada graciosamente quando qualquer um deles está ausente — a
alternância correspondente da barra de ferramentas volta a desligado e mostra
uma dica "install <package>". ``File > Install dependencies…`` instala em
lote cada pacote Python opcional de uma vez.

----

Espaço de Trabalho Desktop Pet (Aba Desktop Pet)
------------------------------------------------

Aba 5 — o **Desktop Pet** coloca qualquer personagem ``.puppet`` na sua
área de trabalho como uma sobreposição sem moldura e transparente. A
aba em si é o painel de controle; o personagem propriamente dito flutua
por cima (ou atrás) das suas outras janelas. Tudo que você pode fazer
com um rig na aba Puppet — motions, expressões, física, drivers de
idle, entrada de webcam / microfone — também funciona aqui.

O que você pode fazer
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Recurso
     - O que faz
   * - Sobreposição sem moldura
     - Sem cromo de janela, sem entrada na barra de tarefas — apenas o
       personagem na sua área de trabalho.
   * - Fundo transparente
     - Tudo que o personagem não cobrir mostra a área de trabalho
       através dele.
   * - Arrastar para mover
     - Clique-arraste com o botão esquerdo no personagem para um novo
       lugar. Solte perto de uma borda da tela para **encaixar** rente
       a ela.
   * - Modo click-through
     - Faz o pet ignorar o mouse para que você possa continuar
       trabalhando por baixo dele.
   * - Travar posição
     - Congela o pet para que arrastos acidentais não possam movê-lo.
   * - Sempre no fundo
     - Coloca o pet atrás de todas as outras janelas — sensação de
       widget de área de trabalho em vez de sempre no topo.
   * - Ocultar em tela cheia
     - Oculta automaticamente enquanto outro aplicativo (jogo / vídeo /
       apresentação) estiver em tela cheia no mesmo monitor; volta
       quando a tela cheia termina.
   * - Pausa quando oculto
     - O pet para de animar enquanto invisível — zero CPU quando fora
       da tela.
   * - Tamanhos predefinidos
     - Pequeno / médio / grande. Redimensiona em torno do centro para
       que o pet não pule pela tela.
   * - Slider de opacidade
     - Esmaece o pet de 10% a 100% para que possa ser um ornamento sutil
       da área de trabalho.
   * - Lembra onde você o deixou
     - Arraste o pet para o seu canto favorito; ele retorna lá na
       próxima inicialização.

Interações de clique
^^^^^^^^^^^^^^^^^^^^

* **Clique esquerdo no corpo** — se o rig define uma área de acerto
  (por exemplo, tocar a cabeça), a motion correspondente é reproduzida.
  Caso contrário, o pet te cumprimenta com um balão de fala.
* **Clique direito em qualquer lugar** — abre um menu de contexto com:
  Ocultar pet, Live drivers, Play motion (lista de cada motion do rig),
  Apply expression, Travar posição, Click-through, Sempre no fundo,
  Ocultar em tela cheia, Balão de fala, Tamanho.
* **Ícone da bandeja do sistema** — clique esquerdo para alternar a
  visibilidade, clique direito para Mostrar/Ocultar, Click-through,
  Open puppet, Ocultar pet.

Drivers ao vivo
^^^^^^^^^^^^^^^

Escolha qualquer combinação na aba ou no menu de clique direito. Cada
um está desligado por padrão — ative apenas o que você quiser.

* **Auto idle** — respiração + deriva sutil para que o personagem
  pareça vivo.
* **Idle motions** — alterna aleatoriamente entre as motions do grupo
  idle do rig.
* **Auto-blink** — fechamento cíclico natural dos olhos a cada poucos
  segundos.
* **Drag-track head** — a cabeça gira para seguir o cursor.
* **Mic lip-sync** — a boca abre com a sua voz (precisa de
  ``sounddevice``).
* **Webcam tracking** — sua cabeça / olhos / boca controlam os do
  puppet (precisa de ``opencv-python`` e ``mediapipe``).

Como começar
^^^^^^^^^^^^

1. Mude para a aba **Desktop Pet**.
2. Clique em **Load bundled March 7th** para usar o personagem incluído,
   ou em **Open Puppet…** para escolher seu próprio arquivo ``.puppet``.
3. Marque **Show pet on desktop**.
4. Arraste o personagem para onde você quiser; escolha os drivers que
   deseja; ajuste a opacidade / tamanho.
5. Clique com o botão direito a qualquer momento para o menu de ação
   rápida, ou use o ícone da bandeja do sistema para ocultar o pet sem
   precisar encontrar a aba.

Tudo que você configurar — posição, drivers, opacidade, click-through,
tamanho — é lembrado entre inicializações.

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
     - Botão direito > Modify > Rotate CW
   * - Rotacionar 90 ° anti-horário
     - ``Shift + R``
     - Botão direito > Modify > Rotate CCW
   * - Inverter horizontal
     - --
     - Botão direito > Modify > Flip Horizontal
   * - Inverter vertical
     - --
     - Botão direito > Modify > Flip Vertical
   * - Rotação sem perdas (JPEG)
     - --
     - Botão direito > Lossless Rotate

----

Exportando Imagens
------------------

Exportação Única
^^^^^^^^^^^^^^^^

Clique com o botão direito em uma imagem > ``Exportar / Salvar Como``.

- Escolha o formato: PNG, JPEG, WebP, BMP, TIFF
- Ajuste a qualidade (para formatos com perdas)
- Pré-visualize o tamanho estimado do arquivo
- Escolha um local para salvar

Presets de Exportação
^^^^^^^^^^^^^^^^^^^^^

Para os alvos comuns de entrega que você não quer reajustar a cada vez, use
``Arquivo`` > ``Exportar com Preset``. Um clique aplica o pipeline correto de
redimensionamento, formato e qualidade:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Preset
     - Pipeline
   * - **Web 1600**
     - Ajusta o lado maior para 1600 px, JPEG qualidade 85, sRGB; para uploads em blog / fórum onde a qualidade visual importa mais que a contagem de pixels.
   * - **Print 300 dpi**
     - TIFF em resolução total / JPEG de alta qualidade com metadados de 300 dpi, saída com gerenciamento de cor para laboratórios e gráficas.
   * - **Instagram 1080**
     - Recorte quadrado (1080 × 1080) ou retrato (1080 × 1350) com a proporção original preservada por dentro, JPEG qualidade 90.

Os presets se compõem com a sobreposição de marca d'água (abaixo) — habilite a
marca d'água uma vez e cada saída de preset a carrega.

Sobreposição de Marca d'Água
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Arquivo`` > ``Marca d'Água…`` abre um configurador de sobreposição não
destrutivo. As configurações se aplicam apenas na exportação — os pixels
originais no disco nunca são tocados.

- **Modo**: texto ou imagem. Marcas d'água em imagem suportam PNG com alfa.
- **Posição**: grade de 9 âncoras (cantos, bordas, centro).
- **Opacidade**: 0 – 100 %.
- **Escala**: porcentagem do lado maior exportado; a marca d'água se redimensiona
  automaticamente conforme você redimensiona para presets diferentes.

Exportação em Lote
^^^^^^^^^^^^^^^^^^

Selecione várias imagens, depois clique com o botão direito > ``Exportação em Lote``.

- Conversão uniforme de formato
- Definir largura / altura máximas (escala automática de proporção)
- Controle de qualidade
- Barra de progresso em tempo real

Criar GIF / Vídeo
^^^^^^^^^^^^^^^^^

Selecione várias imagens, depois clique com o botão direito > ``Criar GIF / Vídeo``.

- Saída GIF e MP4
- Arraste para reordenar quadros
- Defina quadros por segundo (FPS)
- Dimensões personalizadas
- Opção de loop

----

Reprodução de Animação
----------------------

Ao abrir arquivos GIF, APNG ou WebP animados, a animação é reproduzida automaticamente.

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

No modo de miniaturas, selecione 2 -- 4 imagens, depois clique com o botão direito > ``Comparar Imagens``.

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
     - ``Arquivo`` > ``Colar da Área de Transferência``, ou ``Ctrl + V``
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
     - Selecione várias, depois ``Delete`` ou clique com o botão direito > ``Excluir Selecionadas``

As imagens são movidas para a Lixeira do sistema e podem ser recuperadas de lá.

----

Operações em Lote
-----------------

No modo de miniaturas, selecione várias imagens e clique com o botão direito:

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
   * - Adicionar à Tag
     - Aplicar a mesma tag a todas as imagens selecionadas
   * - Adicionar ao Álbum
     - Colocar todas as imagens selecionadas em um álbum

----

Histograma RGB
--------------

Pressione ``H`` no modo Deep Zoom para sobrepor um histograma RGB na imagem. Pressione novamente para ocultar.

----

Definir como Papel de Parede
----------------------------

Clique com o botão direito no modo Deep Zoom > ``Definir como Papel de Parede`` para definir a imagem atual como papel de parede da área de trabalho.

Suportado no Windows, macOS e Linux (GNOME).

----

Múltiplas Janelas
-----------------

``Arquivo`` > ``Nova Janela`` abre outra janela independente do Imervue. Cada janela pode navegar por uma pasta diferente.

Presets de Layout de Espaço de Trabalho
---------------------------------------

``Arquivo`` > ``Espaços de Trabalho…`` captura a geometria atual da janela, o
arranjo de docks / barras de ferramentas, tamanhos de splitter e pasta raiz
ativa sob um nome — depois permite alternar entre layouts salvos da mesma forma
que outros gerenciadores de fotos com suporte a XMP alternam *Library* /
*Develop* / *Export* ou o Adobe Bridge alterna *Metadata* / *Filmstrip*. A
caixa de diálogo suporta Salvar Atual, Carregar, Renomear e Excluir. Espaços
de trabalho persistem em ``user_settings.json`` (sob a chave ``workspaces``)
e sobrevivem entre sessões.

.. tip::
   Construa um espaço de trabalho **Browse** com a árvore e a grade de
   miniaturas visíveis, e um espaço **Develop** separado com o painel de
   revelação maximizado e a árvore colapsada. Um clique move sua janela
   inteira para a forma certa para cada tarefa.

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
2. São necessários privilégios de administrador.
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
     - Deslocar no modo de miniaturas
   * - ``Shift + Seta``
     - Deslocamento fino
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
   * - ``Home``
     - Redefinir zoom

Edição
^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tecla
     - Ação
   * - ``E``
     - Abrir aba Modify
   * - ``R``
     - Rotacionar no sentido horário
   * - ``Shift + R``
     - Rotacionar no sentido anti-horário
   * - ``Ctrl + Z``
     - Desfazer
   * - ``Ctrl + Shift + Z``
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
     - Visualização de pixel (≥ 400 % mostra grade de pixels e valor RGB sob o cursor)
   * - ``Shift + M``
     - Alternar modos de cor (Normal / Tons de Cinza / Inverter / Sépia)
   * - ``S``
     - Slideshow

Animação
^^^^^^^^

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
indexada você pode consultá-la por extensão, largura/altura mínima, faixa de tamanho ou
substring de nome e jogar os resultados no visualizador como um álbum virtual.

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
próximas do índice ordenadas pela distância de Hamming. Ajuste o spin ``Max distance``
para alargar ou apertar a rede.

Pesquisa Semântica (CLIP)
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Semantic Search`` permite digitar uma frase em linguagem natural
(por exemplo *"golden retriever na neve"* ou *"rua de neon à noite"*) e
retorna imagens classificadas da biblioteca indexada. Cada imagem é incorporada com um
encoder visão/linguagem CLIP e armazenada junto com seu caminho; uma consulta de texto é
incorporada no mesmo espaço vetorial e comparada por similaridade de cosseno.

Os embeddings são armazenados em cache em ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows)
ou ``~/.cache/imervue/clip_cache.npz`` (POSIX) como um único arquivo ``.npz`` compacto
para que a próxima inicialização pule a reincorporação. Apenas os caminhos que você varreu são
consultáveis — use ``Scan Folder…`` dentro da caixa de diálogo para estender o índice.

.. note::
   A Pesquisa Semântica requer os pacotes opcionais ``open_clip_torch`` e ``torch``.
   Se não estiverem instalados, a entrada do menu explica o que está faltando
   e outros recursos continuam funcionando.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` aplica tags heurísticas sob
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``). Se ``onnxruntime`` e um modelo CLIP em
``models/clip_vit_b32.onnx`` estiverem disponíveis, também adiciona rótulos
de conteúdo baseados em CLIP. Executa em uma thread de trabalho com uma barra
de progresso em tempo real.

Tags Hierárquicas
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` gerencia tags em estrutura de árvore como
``animal/gato/british``. Selecione uma tag para ver toda imagem abaixo daquele ramo
(descendentes incluídos). Marque ou desmarque a seleção atual com um clique.
Tags hierárquicas vivem no índice da biblioteca e são complementares ao sistema
de tags planas no menu de clique direito.

Renomeação em Lote por Tokens
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` abre uma tabela com pré-visualização ao vivo onde você
digita um template como ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` e vê
exatamente em que cada arquivo será renomeado. Conflitos são destacados para que
nada seja sobrescrito. Tokens suportados: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``.

Exportação de Metadados
^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` escreve uma linha por imagem na
visualização atual cobrindo EXIF, dimensões, rótulo de cor, avaliação, favorito,
tags hierárquicas, estado de cull e notas. Útil para alimentar decisões de cull
em uma planilha ou fluxo de trabalho externo.

Sidecar XMP (Interoperação com outros gerenciadores de fotos com suporte a XMP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O Imervue pode ler e gravar arquivos sidecar XMP da Adobe (``photo.jpg`` ↔
``photo.xmp``) para que avaliações, títulos, descrições, palavras-chave e
rótulos de cor façam round-trip de forma limpa com outros gerenciadores de fotos
com suporte a XMP, Bridge e outras ferramentas com suporte a XMP.

- **Importar XMP da imagem atual** — extrai avaliação / título / palavras-chave /
  rótulo de cor do sidecar para o banco de dados interno.
- **Exportar XMP da imagem atual** — grava a avaliação / título /
  palavras-chave / rótulo de cor atual em um sidecar ao lado da imagem.
- **Importar / exportar em lote** — aplica a mesma operação à seleção ativa
  ou à pasta inteira.

O parser de XML usa ``defusedxml`` para que sidecars malformados ou maliciosos
não possam disparar ataques XXE / billion-laughs. Se ``defusedxml`` não estiver
instalado, as entradas de menu XMP ficam ocultas e nenhum sidecar é gravado.

A **barra lateral EXIF** também expõe uma **tira de avaliação por estrelas**
clicável — a avaliação que ela define é a que a exportação XMP gravará.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

Flag de cull de três estados baseado em sinalização. Pressione ``P`` para escolher
a imagem atual ou cada miniatura selecionada, ``Shift + X`` para rejeitar, ``U`` para
desmarcar. ``Filtrar`` > ``Por Estado de Cull`` mostra apenas escolhidas, rejeitadas
ou não marcadas. ``Extra Tools`` > ``Culling`` aplica o filtro via uma caixa de diálogo
e também expõe um botão **Excluir todas as rejeitadas** que remove permanentemente os
arquivos marcados do disco.

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
mês ou ano (agrupado por data). A data é tirada do EXIF
``DateTimeOriginal`` quando presente, caso contrário do tempo de modificação do arquivo.
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
(1D ou 3D, até 64³). A LUT é parseada com um ``lru_cache`` chaveado por
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
imagem corrigida é salva como um novo arquivo — a correção de lente não faz parte
da receita porque a forma da saída pode mudar.

Visualização de Mapa
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` plota cada imagem geotagueada na biblioteca atual
em um mapa interativo Leaflet + OpenStreetMap (requer
``PySide6.QtWebEngineWidgets``). Sem WebEngine, a caixa de diálogo recai para
uma lista simples de entradas ``(path, lat, lon)`` para que o recurso permaneça
utilizável em instalações mínimas.

Visualização de Calendário
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` mostra um ``QCalendarWidget`` com dias
destacados quando as fotos foram tiradas naquele dia (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → mtime do arquivo). Selecionar uma data lista suas imagens;
clique duas vezes para abrir uma no visualizador principal.

Detecção Facial
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` executa o cascade Haar de detecção
de faces frontais do OpenCV na imagem atual e desenha cada detecção como um retângulo.
Clique duas vezes em uma linha da lista para digitar o nome de uma pessoa; ao salvar, as tags
são gravadas no blob ``extra['face_tags']`` da receita. A detecção é uma técnica clássica —
a precisão é adequada para "mostre-me os rostos" mas não substitui o reconhecimento
moderno baseado em CNN.

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
normalizado (0..1) com um ângulo de endireitamento arbitrário. A saída é
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

Geotag GPS
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` lê quaisquer tags GPS EXIF existentes e
permite editar ou definir novas coordenadas em graus decimais. Requer ``piexif``
instalado; grava em JPEG no local.

Layout de Impressão
^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` compõe múltiplas imagens em um
PDF de várias páginas com tamanho de página, orientação, grade, margens,
sarjeta e marcas de corte configuráveis. Requer ``reportlab``.

----

Uso na Linha de Comando
-----------------------

::

   imervue                        # Iniciar normalmente
   imervue /caminho/para/imagem   # Abrir uma imagem específica
   imervue /caminho/para/pasta    # Abrir uma pasta específica
   imervue --debug                # Habilitar modo debug
   imervue --software_opengl      # Usar renderização por software (quando a GPU não é suportada)

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
     - Dimensões, formato, tags EXIF e campos de sidecar XMP para uma
       imagem. Dados ausentes são reportados como o valor vazio apropriado
       em vez de gerar exceção.
   * - ``read_xmp_tags``
     - Caminho rápido que lê apenas o sidecar XMP — avaliação, rótulo
       de cor, palavras-chave, título, descrição.
   * - ``convert_format``
     - Converte uma imagem para outro formato. O formato de destino é
       inferido pelo sufixo de destino (``png`` / ``jpg`` /
       ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``). O parâmetro opcional
       ``quality`` (1–100) se aplica a JPEG/WebP.
   * - ``puppet_from_png``
     - Constrói um rig ``.puppet`` a partir de um PNG usando o auto-mesh
       do plugin puppet. Inicializa o catálogo padrão de parâmetros Cubism
       para que o rig seja imediatamente dirigível.
   * - ``puppet_inspect``
     - Abre um arquivo ``.puppet`` e retorna um inventário estruturado:
       drawables, deformadores, parâmetros, motions, expressões, áreas
       de hit, partes, blends de parâmetro e rigs de física.

Todas as ferramentas retornam payloads serializados em JSON dentro do envelope
``content`` / ``text`` do MCP; payloads estruturados podem ser parseados de
volta a partir do campo ``text`` no lado do cliente.

Claude Code (Nível de Projeto)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

O repositório inclui um ``.mcp.json`` em nível de projeto na raiz do repositório:

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

Abrir qualquer subdiretório do repositório no Claude Code descobre automaticamente
este servidor. O Claude Code pergunta antes de habilitar servidores de projeto na
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

O servidor implementa o transporte JSON-RPC 2.0 via stdio do MCP
versão ``2025-03-26``:

* ``initialize`` — handshake; anuncia ``capabilities.tools``.
* ``tools/list`` — enumera as ferramentas registradas com suas
  definições de entrada JSON-Schema.
* ``tools/call`` — invoca uma ferramenta com ``{"name", "arguments"}``;
  os resultados voltam dentro do array ``content``.
* ``notifications/*`` — aceitas silenciosamente (sem resposta).

A implementação está em ``Imervue/mcp_server/``:

* ``server.py`` — loop de protocolo + registro de ferramentas.
* ``tools.py`` — funções handler e as definições de ferramenta padrão.
* ``__main__.py`` — ponto de entrada ``python -m Imervue.mcp_server``.

Ferramentas customizadas podem ser registradas construindo :class:`MCPServer`
manualmente, chamando :meth:`MCPServer.register` e alimentando mensagens
através de :meth:`MCPServer.handle_message` (ou conduzindo o loop stdio
com o helper :func:`run` embutido).
