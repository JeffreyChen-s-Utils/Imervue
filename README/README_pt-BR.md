<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  Visualizador / revelador / estúdio de pintura / animador de marionetes de imagens acelerado por GPU, construído com PySide6 e OpenGL
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <strong>Português (BR)</strong> ·
  <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <a href="https://imervue.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/imervue/badge/?version=latest" alt="Documentation Status"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## Sumário

- [Visão geral](#visão-geral)
- [Instalação](#instalação)
- [Uso](#uso)
- [Imervue — Visualizador de imagens e biblioteca](#imervue--visualizador-de-imagens-e-biblioteca)
- [Modify — Revelação não destrutiva](#modify--revelação-não-destrutiva)
- [Paint — editor raster completo](#paint--editor-raster-completo)
- [Puppet — animação 2D com rigging](#puppet--animação-2d-com-rigging)
- [Desktop Pet — overlay sem moldura](#desktop-pet--overlay-sem-moldura)
- [Atalhos de teclado e mouse](#atalhos-de-teclado-e-mouse)
- [Estrutura de menus](#estrutura-de-menus)
- [Sistema de plugins](#sistema-de-plugins)
- [Servidor MCP](#servidor-mcp)
- [Suporte multilíngue](#suporte-multilíngue)
- [Configurações do usuário](#configurações-do-usuário)
- [Arquitetura](#arquitetura)
- [Licença](#licença)

---

## Visão geral

Imervue é uma estação de trabalho de imagens acelerada por GPU que oferece **cinco abas de nível superior**:

| Aba | O que faz |
|---|---|
| **Imervue** | Navegar, visualizar, organizar, pesquisar e processar em lote sua biblioteca de imagens |
| **Modify** | Pipeline de revelação não destrutiva — sliders, curvas, LUTs, máscaras, retoque, multi-imagem |
| **Paint** | Estúdio raster completo com pincéis, camadas, animação, ferramentas de mangá, I/O PSD |
| **Puppet** | Animador 2D de marionetes com rigging feito do zero — malhas, deformadores, parâmetros, motions, física |
| **Desktop Pet** | Roda qualquer rig `.puppet` como overlay sem moldura, transparente e sempre no topo, sobre a área de trabalho |

**Puppet** e **Desktop Pet** são opcionais: desligue qualquer um deles em **File > Preferences > Optional tabs** e, a partir da próxima inicialização, a aba não é adicionada e o código dela não é carregado, então o Imervue inicia mais rápido e usa menos memória. Os dois vêm ligados; cada um é montado na primeira vez que você abre a aba, e a aba Desktop Pet já na inicialização quando o pet está configurado para aparecer ao iniciar.

Princípios de design:

- **Desempenho em primeiro lugar** — renderização acelerada por GPU com shaders GLSL modernos e VBO
- **Suporte a coleções grandes** — grade de tiles virtualizada carrega apenas miniaturas visíveis
- **Experiência fluida** — carregamento assíncrono multi-thread de imagens com prefetching
- **Revelação não destrutiva** — toda alteração vive em uma recipe por imagem; o arquivo em disco nunca é sobrescrito até você exportar explicitamente
- **Extensível** — sistema completo de plugins com hooks de ciclo de vida / menu / imagem / entrada; servidor MCP expõe ferramentas de lógica pura (sem Qt) para assistentes de IA

---

## Instalação

### Requisitos

- Python >= 3.10
- GPU com suporte a OpenGL (fallback de renderização por software disponível)

### Instalar a partir do código-fonte

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### Instalar como pacote

```bash
pip install .
```

### Dependências

| Pacote | Finalidade |
|---------|---------|
| PySide6 | Framework de GUI Qt6 |
| qt-material | Tema Material Design |
| Pillow | Processamento de imagens |
| PyOpenGL | Bindings OpenGL |
| PyOpenGL_accelerate | Otimização de desempenho do OpenGL |
| numpy | Operações de array e cache de miniaturas |
| rawpy | Decodificação de imagens RAW (CR2 / CR3 / NEF / ARW / RAF / ORF / RW2 / PEF / DNG e outros) |
| imageio | I/O de imagens |
| imageio-ffmpeg | MP4 de slideshow e MP4 do Create GIF / Video (H.264 via ffmpeg) |
| defusedxml | Parsing XML seguro (sidecars XMP) |
| watchdog | Automação Watched Folder e as notificações de mudança do servidor MCP |

Opcionais (com feature gating; omita para desativar o recurso sem erros):

| Pacote | Finalidade |
|---------|---------|
| onnxruntime + huggingface_hub | Busca semântica CLIP e rótulos CLIP do Auto-Tag (a instalação é oferecida no primeiro uso; o modelo de ~150 MB é baixado uma única vez) |
| onnxruntime | Upscale por IA Real-ESRGAN |
| opencv-python<5 | Composição HDR, costura de panorama, focus stacking, detecção facial, pincel de cura |
| sounddevice | Sincronia labial do Puppet via microfone |
| mediapipe | Rastreamento facial por webcam do Puppet |

---

## Uso

### Inicialização básica

```bash
python -m Imervue
```

### Abrir uma imagem ou pasta específica

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### Opções de linha de comando

| Opção | Descrição |
|--------|-------------|
| `--debug` | Habilita o modo de depuração |
| `--software_opengl` | Usa renderização OpenGL por software (define `QT_OPENGL=software` e `QT_ANGLE_PLATFORM=warp`) |
| `file` | (posicional) Arquivo de imagem ou pasta a abrir na inicialização |

### CLI de lote sem interface

`Imervue.cli` executa as operações de imagem puras a partir do shell **sem iniciar o Qt** — útil para scripts, etapas de CI e servidores sem display:

```bash
py -m Imervue.cli resize photos/ --max 1600 --out web/
py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
py -m Imervue.cli info *.png --json
py -m Imervue.cli list-ops          # imprime todos os subcomandos disponíveis
```

| Subcomando | Finalidade |
|---|---|
| `info` / `stats` | Dimensões e formato; métricas de qualidade sem referência (`--json` para saída legível por máquina) |
| `convert` / `resize` / `thumbnail` | Conversão de formato (`--format` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL, `--quality`); redimensionamento pelo lado maior (`--max`) ou para `--width` / `--height` exatos; caixa de miniatura |
| `watermark` / `optimize` | Marca d'água de texto (`--text`, `--corner`, `--opacity`, `--font-fraction`, `--color R G B`, `--no-shadow`); codificar dentro de um orçamento `--max-kb` |
| `dehaze` / `clahe` / `dither` / `distort` | Remoção de neblina por canal escuro, equalização adaptativa, dithering Bayer ordenado, swirl / pinch / ripple |
| `auto-orient` / `strip` | Gravar a orientação EXIF nos pixels; salvar novamente sem EXIF / XMP / ICC |
| `collage` / `anaglyph` | Montagem em grade (`--columns`, `--cell-width` / `--cell-height`, `--gap`, `--margin`, `--background R G B`); 3D vermelho-ciano a partir de um par estéreo (`--method`) |
| `preset` / `pipeline` | Aplicar uma predefinição de revelação salva pelo nome; executar um pipeline JSON ordenado |
| `list-ops` | Listar todos os subcomandos (`--json` para saída legível por máquina) |

Todo subcomando decodifica como o visualizador: as saídas são endireitadas pela orientação EXIF e convertidas para sRGB a partir do perfil de cor embutido, entradas AVIF são lidas pelo próprio Pillow, e entradas HEIC / JPEG XL quando o backend opcional está instalado. Um RAW de câmera é revelado como no visualizador, em vez de lido pela pequena prévia embutida; `resize` e `strip` o gravam como PNG. Um arquivo ilegível é relatado e o restante é processado mesmo assim. Um arquivo incompleto é lido até onde vai, como no visualizador. Tons de cinza de 16 bits e de ponto flutuante são escalados para 8 bits como no visualizador; `resize` e `strip` mantêm a profundidade de bits da origem.

Os subcomandos que recebem arquivos ou pastas (todos exceto `collage`, `anaglyph` e `list-ops`) compartilham `--out` (diretório de saída), `--recursive`, `--dry-run` (listar ações sem escrever nada), `--overwrite` e `-j` / `--jobs` (workers paralelos; `0` usa todos os núcleos). `collage` e `anaglyph` gravam o único arquivo indicado por `--out`. `--version` mostra a versão da CLI.

Toda ferramenta do [Servidor MCP](#servidor-mcp) também é um subcomando. Dez delas são os subcomandos acima
(`convert_format` é `convert`, `quality_metrics` é `stats`, `build_collage` é `collage` e assim por diante);
as outras 48 executam o próprio código da ferramenta MCP:

| Tipo | Subcomandos |
|---|---|
| Edições: gravam `<stem>_<name>.png` ao lado de cada origem, ou `<stem>.png` em `--out` | `frame`, `crop`, `rotate`, `solarize`, `glow`, `velvia`, `emboss`, `film-negative`, `defringe`, `graduated-density`, `filmic-tonemap`, `tone-equalizer`, `detail-equalizer`, `colormap`, `false-color`, `split-toning`, `pixel-sort`, `polar`, `kaleidoscope`, `frosted-glass`, `local-contrast`, `posterize`, `gradient-map`, `film-grain`, `levels`, `auto-color-balance`, `channel-mixer`, `curve`, `lens-correction` |
| Outras saídas | `ela` (mapa de Error Level Analysis em PNG), `video-frame` (um quadro de um vídeo, `--frame-index`), `puppet-from-png` (um rig `.puppet`, `--cell-size`) |
| Relatórios: um resultado por imagem, `--json` para saída legível por máquina | `metadata`, `xmp`, `gps`, `dominant-colors`, `sharpness`, `statistics`, `histogram`, `ocr`, `puppet-inspect`, `puppet-validate` |
| Executam uma vez e imprimem JSON | `list-images FOLDER`, `search FOLDER --query "..."`, `similar FOLDER`, `collection-stats FOLDER`, `reverse-geocode --latitude .. --longitude ..`, `puppet-schema --name ..` |

Cada parâmetro MCP vira uma opção com o mesmo valor padrão e os mesmos valores permitidos: `zone_gains` vira
`--zone-gains`, um parâmetro sim/não vira `--grayscale` / `--no-grayscale`, e uma cor ou uma linha de matriz
recebe seus valores em ordem (`--red 1 0 0`). `py -m Imervue.cli <subcommand> --help` lista todas elas.

`pipeline FILE INPUTS…` encadeia operações a partir de um arquivo JSON — uma lista de etapas, ou
`{"pipeline": [...]}`, cada etapa um `"op"` mais seus parâmetros (no máximo 50 etapas). As operações são
`dehaze`, `clahe`, `dither`, `distort`, `clarity`, `texture`, `grayscale`, `invert` e
`watermark`; a documentação lista cada parâmetro e valor padrão.

```bash
py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
py -m Imervue.cli histogram a.jpg --json
py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"
```

---

## Imervue — Visualizador de imagens e biblioteca

A grade de miniaturas libera espaço para novas texturas GPU removendo primeiro as que estão fora da área visível, preservando as visíveis e respeitando o orçamento de memória. As que apenas tocam a borda não reservam capacidade.

Desenho, solicitações de miniaturas e liberação de texturas compartilham a área visível com uma linha/coluna extra. Os tamanhos normais são decodificados sob demanda, sem exceder o número de workers do grupo de miniaturas; rolar substitui solicitações ainda não iniciadas. O modo de resolução completa continua descobrindo imagens que ultrapassam as células com trabalho de fundo limitado. O progresso conta a vista atual e as solicitações explícitas. Ao voltar do Deep Zoom, o cache e a posição são mantidos.

A pré-carga de imagens vizinhas soma os bytes reais das pirâmides e as reservas das decodificações em andamento. As janelas abertas compartilham igualmente 20% da RAM física (256 MiB–8 GiB); sem detecção opcional de memória, compartilham um orçamento alternativo de 2 GiB. As reservas de decodificações canceladas permanecem até o término real; ao abrir uma imagem ignorada pelo orçamento, ela é carregada normalmente em primeiro plano. O orçamento de RAM é separado do de texturas GPU e não limita o processo inteiro nem a imagem em primeiro plano.

A aba **Imervue** é a tela inicial padrão. Combina o visualizador de imagens com árvore de pastas, painel lateral EXIF e ferramentas de biblioteca/organização.

### Visualizador

- **Renderização acelerada por GPU** via OpenGL (shaders GLSL 1.20 com VBO)
- **Pirâmide de zoom profundo** — ladrilhos multinível de 512×512 com reamostragem LANCZOS; o LRU de ladrilhos guarda 256 entradas (teto rígido 512). O orçamento de VRAM é sondado do driver GL na inicialização e recua para 1,5 GB, substituível pela configuração `vram_limit_mb` (é limitado, nunca descartado em silêncio). Filtragem anisotrópica até 8×; panoramas muito acima do limite de segurança de 179 MP do Pillow também abrem (o limite acompanha a memória: cerca de 1,4 gigapixel com 16 GB)
- **Carregamento assíncrono** — decodificação multithread com uma janela de pré-carregamento adaptativa: ±3 imagens ao navegar, ampliando para 5 à frente / 1 atrás assim que você avança de forma consistente numa direção
- **Pools de workers separados** — rajadas de miniaturas e decodificações de zoom profundo rodam em pools distintos, então abrir uma pasta grande nunca deixa sem recursos a imagem que você está vendo
- **Grade virtualizada de miniaturas** — apenas tiles visíveis são renderizados; o tamanho das miniaturas é configurável (128 / 256 / 512 / 1024 / auto)
- **Cache em disco** — miniaturas PNG comprimidas com invalidação baseada em MD5 em `%LOCALAPPDATA%/Imervue/cache/thumbnails` (ou `~/.cache/imervue/thumbnails`)
- **Orientação EXIF** — fotos em retrato que o celular ou a câmera apenas marcaram em vez de girar aparecem na posição certa no visualizador, nas miniaturas, na lista, na prévia ao passar o mouse e na aba Modify; um recorte / giro de revelação salvo antes continua valendo para a orientação em que foi feito
- **Gerenciamento de cor** — fotos com perfil de cor embutido (Display P3 de celulares, Adobe RGB de câmeras, CMYK e os perfis de cinza que o Photoshop embute em imagens em tons de cinza, como Dot Gain 20% ou Gray Gamma 1.8) são convertidas para sRGB no visualizador e nas miniaturas; imagens sem perfil ou em sRGB aparecem como estão
- **Arquivos incompletos** — um JPEG, PNG, TIFF, GIF ou BMP que termina antes da hora (um download ou cópia interrompidos, uma foto recuperada de um cartão de memória com defeito) abre com a parte que foi lida, como no navegador, em vez de não abrir
- **Arquivos alterados por outros programas** — quando outro programa salva por cima de uma imagem (um editor externo, direto no arquivo ou renomeando uma cópia por cima), o visualizador mostra a versão nova: a imagem aberta no zoom profundo em menos de um segundo após a última gravação, as miniaturas da grade e as linhas da Lista em poucos segundos
- **Tons de cinza de 16 bits e de ponto flutuante** — um PNG ou TIFF em cinza de 16 bits (um escaneamento, um mapa de profundidade, uma imagem científica ou astronômica) e um TIFF de ponto flutuante mostram seu brilho real no visualizador, nas miniaturas, nas prévias e nas ferramentas, em vez de quase branco ou preto
- **Arquivos ocultos** — arquivos que o Windows marca como ocultos (ocultos também no Explorer e na árvore de pastas) e nomes que começam com ponto, como o `._foto.jpg` que o macOS grava ao lado de cada foto em cartões de memória e unidades de rede, ficam fora da grade de miniaturas, dos ícones de pasta, das listas das ferramentas em lote, das pastas monitoradas, das varreduras da biblioteca, da CLI e das ferramentas de pasta do servidor MCP; varreduras recursivas pulam pastas ocultas como `$RECYCLE.BIN` e a `.Trashes` de um Mac. Uma imagem oculta aberta de propósito abre mesmo assim
- **JPEG com qualquer nome** — `.jpe`, `.jfif` e `.jif` abrem como `.jpg` (Chrome e Edge no Windows costumam salvar fotos baixadas como `.jfif`): no visualizador, no filtro JPG, nas ferramentas em lote e na CLI
- **Mais formatos** — ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (a imagem mesclada) abrem para visualização, lidos pelo próprio Pillow; girar um no lugar e outras regravações são recusados, então uma edição sai por Salvar como / Exportar
- **Reprodução de animação** — GIF / APNG com controles de play / pause / passo por quadro / velocidade; uma animação que ocuparia mais de 512 MB decodificada é decodificada quadro a quadro durante a reprodução, não toda de antemão; um quadro de 10 ms ou menos é exibido por 100 ms, como nos navegadores; um TIFF de várias páginas (um documento digitalizado) mostra uma página por vez, virada com `,` e `.` (o indicador mostra o número da página), e a prévia que a câmera embute no JPEG (MPF) nunca aparece como segundo quadro, nem a imagem padrão de um APNG (a imagem estática para programas sem suporte a APNG) como primeiro

### Modos de navegação

- **Grade** (padrão) — grade de tiles virtualizada com popup de pré-visualização ao passar o mouse (atraso de 500 ms)
- **Lista (detalhe)** — alternar com `Ctrl+L`; colunas: Preview · Etiqueta · Avaliação · Nome · Resolução · Tamanho · Tipo · Modificação; `Delete` remove as linhas selecionadas e `Ctrl+Z` as traz de volta, e as teclas de avaliação (`1`–`5`), favorito (`0`), seleção (`P` / `Shift+X` / `U`) e cor (`F1`–`F5`) as marcam, como na grade
- **Deep Zoom** — duplo clique em um tile; pan/zoom suave por GPU com overlay de minimapa
- **Vista dividida** (`Shift+S`) — duas imagens lado a lado
- **Leitura em página dupla** (`Shift+D`, `Ctrl+Shift+D` para mangá da direita para a esquerda) — leitor de páginas opostas
- **Espelhamento multi-monitor** (`Ctrl+Shift+M`) — janela em monitor secundário
- **Modo cinema** (`Shift+Tab`) — esconde todo o chrome
- **Diálogo de comparação** — lado a lado / sobreposição (slider de alpha) / diferença (slider de ganho) / divisão A|B com divisor arrastável
- **Vistas Timeline / Calendar / Map** — agrupa a biblioteca por data de captura, navega em um calendário, plota fotos geotaggeadas em Leaflet + OpenStreetMap

### Sobreposições de tela

- Histograma RGB (`H`)
- OSD F8 (nome do arquivo / tamanho / tipo), HUD de depuração Ctrl+F8 (VRAM / cache / threads)
- Vista de pixel (`Shift+P`) — a partir de 400 % de zoom mostra RGB / HEX por pixel, mais uma grade de pixels quando no máximo 40.000 pixels estão na tela
- Modos de cor (`Shift+M`) — Normal / Tons de Cinza / Invertido / Sépia via GLSL

### Navegação

- Teclas de seta, histórico estilo navegador (`Alt+←/→`), salto aleatório (`X`)
- Navegação entre pastas (`Ctrl+Shift+←/→`)
- Ir para imagem por índice (`Ctrl+G`)
- Busca fuzzy (`Ctrl+F` / `/`)
- **Paleta de Comandos** (`Ctrl+Shift+P`) — busca fuzzy de todas as ações de menu
- Auto-loop no fim da pasta
- Pinch-zoom no touchpad + deslizar horizontal para navegar

### Organização

- **Favoritos** — até 5000 caminhos
- **Avaliações** — 0 a 5 estrelas (`1`–`5`) + coração de favorito (`0`); na grade valem para as miniaturas selecionadas, senão para a escolhida com as setas, senão para a que está sob o mouse
- **Etiquetas de cor** — bandeiras vermelho/amarelo/verde/azul/roxo (`F1`–`F5`)
- **Triagem (Culling)** — flag de três estados (`P` = manter, `Shift+X` = rejeitar, `U` = remover marca); filtrar por estado; exclusão em lote de rejeitados; a triagem automática escolhe o quadro mais nítido de cada grupo de quase duplicatas e rejeita os demais
- **Tags hierárquicas** — caminhos em árvore como `animal/cat/british`; descendentes são correspondidos automaticamente; **Operações em lote** > **Index Keywords** no menu de clique direito (com miniaturas selecionadas) arquiva uma hierarquia de palavras-chave do Lightroom / darktable (`Places|Taiwan|Taipei`) sob os pais
- **Tags & Albums** com filtragem multi-tag AND/OR; um nome novo ou renomeado que difere de outro só em maiúsculas/minúsculas ou espaços é recusado, e **Clean Up…** esquece arquivos que não existem mais e mescla nomes que diferem só em maiúsculas/minúsculas
- **Smart Albums** — salva consultas baseadas em regras e reaplica com um clique; os filtros abrangem extensão, resolução e **proporção**, **tamanho de arquivo**, **piso / teto** de avaliação, cor, triagem, tags (incl. **exclusão**), **câmera / lente**, **regex / glob de nome de arquivo** e **idade do arquivo**, além de **exportar / importar** para um arquivo JSON portável
- **Empilhar pares RAW+JPEG** — colapsa capturas de mesmo nome em um único tile; o RAW continua acessível como irmão
- **Notas por imagem** no painel EXIF — salvamento com debounce, persiste entre sessões
- **Staging Tray** — cesta entre pastas que sobrevive a reinicializações; mover / copiar / exportar em lote
- **Gerenciador de arquivos de painel duplo** — visualização em duas árvores em painel duplo
- **Sessões / Layouts de Workspace** — captura snapshot de abas / seleção / filtro / geometria das docks para `.imervue-session.json`; salva layouts nomeados para arranjos de Navegação / Revelação / Exportação
- **Macros** — grava / reproduz lotes de ações de avaliação / favorito / cor / tag (`Alt+M` reproduz o último macro)
- **Badges + densidade de miniaturas** — faixa de cor, favorito, marcador, estrelas de avaliação; padding Compacto / Padrão / Relaxado
- **Arrastar para fora para apps externos** — arraste um tile direto para o Explorer / Chrome / Discord
- **Pastas / imagens recentes** rastreadas; última pasta restaurada automaticamente na inicialização

### Ordenação e filtragem

- Ordenar por nome (ordem natural, como o Explorer: `img2` antes de `img10`) / modificação / criação / data da foto (horário EXIF da câmera; senão, modificação) / tamanho / resolução (asc ou desc)
- Filtrar por extensão, etiqueta de cor, avaliação, tag/álbum, estado de triagem
- **Filtro avançado** — resolução / tamanho de arquivo / orientação / intervalo de data de modificação
- Diálogo de **filtro multi-tag** com lógica booleana AND / OR

### Busca

- **Busca fuzzy por nome de arquivo** com destaque de substring
- **Buscar Imagens Similares** — pHash (DCT 64 bits) com distância de Hamming ajustável
- **Library Search** — índice multi-raiz SQLite, pesquisado por nome de arquivo, largura / altura mínima e tamanho de arquivo (até 2000 resultados; clique duas vezes em um para abri-lo); uma nova varredura só lê arquivos novos ou alterados (e, com **Compute perceptual hash** marcado, os que ainda não têm hash), vários ao mesmo tempo
- **Search by Query** (clique direito) — uma linguagem de consulta compacta sobre a pasta aberta: palavras-chave, tags (incl. negação), avaliações, cor, extensão, lugar, triagem, favoritos, proporção, idade, tamanho, dimensões, câmera / lente e regex / glob de nome de arquivo; `place:` corresponde a uma cidade, um país ou ambos, e um valor com espaços vai entre aspas duplas (`place:"Rio de Janeiro"`)
- **Find Similar (average hash)** — pHash e dHash são acompanhados por um average-hash (aHash) opcional para uma métrica complementar de quase duplicatas
- **Busca Semântica (CLIP)** — consultas em linguagem natural ("golden retriever na neve") via embeddings em cache do CLIP ViT-B/32 sobre onnxruntime, sem PyTorch: o Imervue oferece instalar o `onnxruntime` no primeiro uso e baixa o modelo de ~150 MB uma única vez, em uma revisão fixada; roda em uma GPU NVIDIA via CUDA quando disponível, senão na CPU, nunca em uma GPU integrada
- **Auto-Tag** — tags heurísticas a partir de cor, bordas e forma: document / screenshot / photo / graphic, landscape / portrait; depois que a Busca Semântica tiver baixado o modelo CLIP, usa rótulos CLIP zero-shot em vez disso (até três entre photo, document, screenshot, graphic, illustration, portrait, landscape, animal, food, text)

### Metadados

- **Painel lateral EXIF** com grupos colapsáveis + faixa inline de 0-5 estrelas
- Diálogo de **editor EXIF** — descrição, artista, copyright, câmera e comentário (Unicode incluído) gravados em um JPEG ou WebP sem pacote extra, sem alterar pixels nem as outras tags; **Describe** preenche a descrição com uma frase de um modelo de visão local (Ollama com `llava` em `localhost:11434`), então a imagem nunca sai do seu computador
- **Editor de palavras-chave** — título / autor / descrição / palavras-chave, com **sugestões de tags relacionadas** extraídas da coocorrência de tags e expansão de vocabulário controlado (uma palavra-chave folha aplica automaticamente seus ancestrais + sinônimos de um vocabulário hierárquico editável)
- Diálogo de **informações da imagem** (dimensões / tamanho / datas)
- **Sidecars XMP** (`.xmp` companheiros) — avaliação / título / descrição / palavras-chave / etiqueta de cor em round-trip com outros gerenciadores de fotos com suporte a XMP (XML seguro via `defusedxml`). Salvar mescla no sidecar existente: só estes campos mudam, então as configurações de revelação, o recorte e o histórico de outro programa são mantidos, e um sidecar ilegível nunca é sobrescrito. Além de `photo.xmp` (Lightroom, Bridge), o `photo.jpg.xmp` que o darktable e o digiKam escrevem é lido e atualizado quando é o único sidecar; os rótulos de cor são entendidos nas palavras do Lightroom (`Red` … `Purple`) e do Bridge (`Select`, `Second`, `Approved`, `Review`, `To Do`), e exportados como o Lightroom os escreve. Uma foto rejeitada (`xmp:Rating` -1 no Lightroom, Bridge e darktable) vira um Reject da seleção, e um Reject é exportado como -1. Um arquivo sem sidecar é lido e importado a partir do XMP e da avaliação EXIF embutidos nele (JPEG, PNG, WebP, TIFF, CR3, RW2, RWL, ORF, RAF): é assim que o Lightroom guarda a avaliação e as palavras-chave de um JPEG, e o Explorador do Windows as estrelas.
- **Editor de Geotag GPS** — lê GPS EXIF existente, escreve nova lat/lon em um JPEG ou WebP sem pacote extra, sem alterar pixels, outras tags nem a miniatura
- **Geotag a partir de trilha GPX** — compara os horários de captura EXIF da seleção com um registro `.gpx` de um celular ou registrador GPS, considerando o fuso horário da câmera, um limite de intervalo e a interpolação entre pontos, e depois grava as posições nos arquivos JPEG / WebP
- **Editar data de captura** — desloca a data de captura EXIF da seleção em dias / horas / minutos / segundos, ou informando quando a primeira foto foi realmente tirada; DateTimeOriginal, DateTimeDigitized e DateTime são reescritos em arquivos JPEG / WebP
- **Modelo de metadados** — título, descrição e palavras-chave memorizados, com os tokens `{filename}` / `{name}` / `{folder}` / `{date}` / `{year}`, aplicados à seleção apenas nos campos vazios (palavras-chave acrescentadas) ou por cima do que já existe; Sidecars XMP e Exportar metadados gravam o resultado
- **Token Batch Rename** — templates com preview ao vivo como `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata CSV / JSON** — uma linha por imagem incluindo triagem / avaliação / tags / notas

### Ferramentas extras (aba Imervue — processamento em lote)

Acessadas a partir do menu **Tools**; organizadas em submenus agrupados por função:

- **Batch** — Conversão de formato · Remoção EXIF · Sanitizador de imagens (re-renderizar para remover dados ocultos) · Organizador de imagens (ordenar em subpastas por data / resolução / tipo / tamanho) · Token Batch Rename
- **Retouch & Transform** — AI Image Upscale (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Detecção facial (Haar cascade) · cura, clonagem, recorte / endireitamento e correção de lente
- **Library & Metadata** — Library Search · Smart Albums · Encontrar imagens similares · Busca semântica · Encontrar imagens duplicadas · Auto-Tag · Tags hierárquicas · Exportar metadados · Sidecars XMP · Geotag GPS · Geotag a partir de trilha GPX · Editar data de captura · Modelo de metadados

### Integração com o sistema

- Menu de contexto do botão direito do Windows **Abrir com Imervue** (associação de arquivos baseada em registro)
- Monitoramento de pasta: a pasta aberta é verificada cerca de uma vez por segundo, então arquivos adicionados, removidos ou renomeados em outro lugar aparecem em um ou dois segundos; nada mantém a pasta aberta, por isso no Windows as pastas acima dela ainda podem ser renomeadas ou movidas. A árvore de pastas se atualiza com F5 / **Refresh**, quando o Imervue volta ao primeiro plano e quando a pasta aberta muda
- Sistema de notificações toast (info / sucesso / aviso / erro)
- Sistema de plugins com downloader online (ver [Sistema de plugins](#sistema-de-plugins))

---

## Modify — Revelação não destrutiva

Modify mantém os controles responsivos com uma prévia de menor resolução em segundo plano durante os ajustes e calcula a qualidade completa após uma pausa. Alterações rápidas e trocas de foto descartam resultados antigos; as anotações mantêm as coordenadas do tamanho completo. Salvar ou aplicar efeitos destrutivos conclui primeiro o cálculo em qualidade completa.

A aba **Modify** é a estação de revelação. Toda alteração vive em uma **recipe** por imagem armazenada ao lado do arquivo — os pixels originais em disco nunca são sobrescritos até você **Exportar** ou usar **Salvar Como** explicitamente. **Apply Crop** e o **Save** de anotações são as duas exceções: gravam o resultado sobre o arquivo e mantêm seu EXIF (câmera, data de captura, GPS), XMP e DPI. Um RAW de câmera, um HEIC ou um arquivo animado / de várias páginas nunca é sobrescrito — o recorte pede que você exporte e o salvamento de anotações pede um arquivo novo. As ferramentas de uso único (CLAHE, mixer HSL, moldura, endireitamento automático…) salvam o resultado ao lado do original como `photo_clahe.png`; executá-las de novo salva `photo_clahe_1.png` em vez de substituir o último resultado. **Auto-Rotate by EXIF**, as cópias do **Batch EXIF Strip** e **Split Pages…** numeram seus arquivos da mesma forma. A receita e as cópias virtuais de uma foto a acompanham quando o Imervue a gira sem perda (o recorte gira junto) ou reescreve o EXIF (geotag GPS, editor EXIF); uma receita com máscaras locais, camadas, reflexo de lente ou tags de rostos fica com a versão sem giro até que seja girada de volta.

### Sliders de revelação

- Balanço de branco — temperatura / matiz
- Regiões tonais — realces / sombras / brancos / pretos
- Exposição / contraste / saturação / vibrância
- Recorte, rotação, espelhamento horizontal / vertical
- Todas as edições permanecem não destrutivas e fazem round-trip pelo armazenamento de recipes

### Curvas e LUTs

- **Editor de curva tonal** — curva RGB arrastável mais R / G / B por canal com interpolação cubic monotônica
- **Aplicar LUT .cube** — carrega qualquer LUT Adobe (3D até 65³, 1D até 65.536 pontos; inclusive o `LUT_3D_INPUT_RANGE` do DaVinci Resolve), interpola trilinearmente, mistura com slider de intensidade
- **Split Toning** — matiz + saturação de sombras / realces com pivô de balanço

### Efeitos criativos

- **Solarize** — inversão tonal estilo câmara escura (limiar + mix)
- **Diffuse Glow / Orton** — brilho suave de realces com foco difuso (quantidade / raio / limiar de realces)
- **Gradient Map** — luminância → paleta, com um modo opcional de interpolação perceptual (OkLCH) que mantém gradientes saturados vívidos ao longo do ponto médio em vez de acinzentá-los
- **Ordered Dither** — quantização por matriz de Bayer em N níveis (extremos preservados)
- **Graduated Density** — gradiente ND linear por ângulo/dureza/deslocamento com tonalização opcional, para céus e primeiros planos
- **Tone Equalizer** — exposição independente por zona de luminância (das sombras aos realces) sobre uma máscara suavizada
- **Detail Equalizer** — repondera o contraste por banda de frequência (textura fina vs contraste grosseiro), além de um único slider de clareza
- **Filmic Tone Map** — rolloff puro de realces Reinhard/Hable com contraste pivotado e restauração de saturação, para capturas únicas de alto contraste
- **Velvia** — boost de saturação ponderado por luminância que intensifica cores apagadas poupando as sombras
- **Film Negative** — inverte um negativo colorido escaneado, removendo a base laranja do filme, com gamma de saída
- **Defringe** — dessatura franjas de aberração cromática roxas/verdes em bordas de alto contraste
- **Emboss** — relevo de luz direcional a partir de um campo de altura de luminância
- **Polar Coordinates** — envolve um quadro em um disco ou o desenrola (planeta-miniatura / inversão polar)
- **Kaleidoscope** — espelha uma cunha angular em simetria de ordem n
- **Frosted Glass** — espalhamento local de pixels determinístico com semente fixa
- **Frame & Caption** — uma borda passe-partout em qualquer cor, uma faixa inferior opcional no estilo Polaroid e uma legenda com cor própria
- **Presets de revelação** — salve uma recipe e depois aplique-a por inteiro ou mescle apenas seus ajustes ativos sobre outras imagens (preservando o recorte próprio de cada imagem, etc.)

### Ajustes locais

- **Máscaras de pincel / radial / gradiente linear** com deltas por máscara de exposição / brilho / contraste / saturação / balanço de branco + slider de feathering
- Máscaras se mesclam não destrutivamente através do pipeline de revelação

### Retoque e transformação

- **Pincel de cura** — manchas circulares, inpainting OpenCV (Telea ou Navier-Stokes)
- **Carimbo de clonagem** — Shift+clique na fonte, blit com feathering no destino
- **Recorte / Endireitar** — retângulo de recorte normalizado mais endireitamento de até ±15° com auto-recorte para o maior retângulo interno
- **Auto-endireitar** — detecção de horizonte / vertical por linha de Hough
- **Correção de lente** — distorção radial em puro numpy (barrel / pincushion), elevação de vinheta, aberração cromática por canal
- **Redução de ruído / Sharpening** — denoise bilateral que preserva bordas + sharpening unsharp-mask
- **Céu / Plano de fundo** — substitui céu detectado por gradiente ou remove o plano de fundo (preenchimento transparente ou branco); upgrade opcional `rembg` / U²-Net

### Multi-imagem

- **Composição HDR** — combina exposições com bracket via fusão Mertens do OpenCV (com pré-alinhamento AlignMTB)
- **Costura de Panorama** — `Stitcher` do OpenCV em modo panorama ou scans, auto-recorte de bordas pretas
- **Focus Stacking** — mapa de foco por variância Laplaciana + blend Gaussiano com alinhamento ECC opcional

### Saída

- **Presets de exportação** — na Exportação em Lote: Web 1600 px / 4K Web 3840 px / Print 300 DPI PNG / Instagram 1080 × 1080 quadrado / Thumbnail 400 px, ou Custom
- **Marca d'água** — na Exportação em Lote: uma marca d'água de texto em um canto ou no centro, com sua opacidade; aplicada apenas às cópias exportadas
- **Revelação em lote na GPU** — com o plugin **GPU Develop** (**Plugins > Download Plugins**), a Exportação em Lote renderiza as receitas de revelação em uma GPU dedicada, escolhida em **Render on**; **Plugins > GPU Develop…** instala o `wgpu` no primeiro uso e informa a GPU que encontrou. Balanço de branco, exposição, realces / sombras, brancos / pretos, brilho, contraste, vibração, saturação e a curva tonal rodam na GPU (uma foto de 24 MP em cerca de 0,1 s em vez de cerca de 7 s); o restante de uma receita fica na CPU. GPUs integradas nunca são usadas, uma imagem em que a GPU falha é renderizada na CPU, e a saída coincide com a do renderizador de CPU com diferença de poucos níveis em uma pequena parcela dos pixels
- **Salvar Como / Exportar** — PNG / JPEG / WebP / BMP / TIFF (e AVIF quando o Pillow tem suporte a AVIF, HEIC com `pillow-heif` e JPEG XL com `pillow-jxl-plugin`) com slider de qualidade para formatos com perdas; mantém o EXIF de câmera, lente e data de captura, com a localização opcional (**Metadados**: todos / todos menos localização / nenhum); o nome sugerido é um ainda livre (`photo_1.png` ao lado de `photo.png`), e um arquivo existente — sobretudo a própria foto — só é substituído após confirmação
- **Operações em lote** — renomear, mover/copiar, rotacionar imagens selecionadas. Mover ou copiar nunca sobrescreve um arquivo de mesmo nome (ele chega como `name_1`), e uma foto renomeada ou movida no Imervue (renomeação em lote, renomeação por tokens, árvore de pastas, Mover / Copiar, painel duplo, bandeja de preparação, organizador de imagens) mantém a avaliação, o favorito, as tags, o rótulo de cor, o título, as notas e a marcação de seleção; os sidecars `.xmp` e de anotações vão junto; o mesmo vale para uma foto renomeada em outro programa enquanto a pasta está aberta no Imervue. Um nome novo que outra foto selecionada tem agora (renumerar, trocar dois nomes) renomeia a seleção inteira na ordem certa em vez de só uma parte
- **PDF de Contact Sheet** — grade em várias páginas com legendas (A4 / A3 / Letter / Legal); a caixa **Layout** preenche um preset — Default 4 × 5, Compact 6 × 8, Proof 5 × 6, Editorial 2 × 3, Index 8 × 10 (colunas × linhas, cada um com sua margem e suas legendas) — e editar a grade à mão muda a caixa para Custom
- **HTML de Galeria Web** — pasta autocontida com `index.html` + miniaturas JPEG + lightbox embutido; **Revisão do cliente** adiciona uma caixa de comentário abaixo de cada imagem; os comentários ficam no navegador de quem revisa e são baixados juntos em um único arquivo JSON
- **Slideshow MP4** — vídeo H.264 com FPS / tempo por imagem / transições de fade / dissolução / slide / wipe configuráveis (`imageio-ffmpeg`)
- **Print Layout** — folha PDF em várias páginas com tamanho / orientação / grade / margens / sangria / marcas de corte configuráveis
- **Soft Proof** — carrega um perfil ICC, simula o gamut de destino, destaca pixels fora do gamut em magenta
- **Cópias Virtuais** — snapshots de recipe nomeados por imagem; alterne entre visuais sem perder o mestre

### Editores externos

Registre programas (um editor de imagem, por exemplo) em **File > External Editors…** e abra-os com a imagem atual via **File > Open in External Editor**. Quando o editor salva, o visualizador mostra a versão nova sozinho.

---

## Paint — editor raster completo

A aba **Paint** é um estúdio raster completo embutido como seu próprio `QMainWindow` com menus, faixa de ferramentas à esquerda, barra de opções sensível ao contexto e uma coluna de docks com abas à direita. Edição de documentos multi-aba — abra muitos desenhos ao mesmo tempo, cada um com sua própria pilha de undo.

### Ferramentas (27)

Pincel · Borracha · Preenchimento · Conta-gotas · Retângulo / Laço / Varinha / Seleção Rápida · Mover · Texto · Gradiente · Desfocar · Smudge · Dodge · Burn · Sponge · Caneta · Carimbo de Clonagem · Balão de Fala · Retângulo · Elipse · Linha · Polígono · Recorte · Transformar · Mão · Zoom

A **Caneta** liga os pontos que você clica com linhas retas, ou com curvas onde você arrasta alças; com **Smooth** marcado na barra de opções, ela traça em vez disso uma única curva suave por todos os pontos.

O trio de tonalização de câmara escura — **Dodge** (clarear), **Burn** (escurecer) e **Sponge** (dessaturar) — pinta ajustes locais ponderados pelo pincel; Dodge e Burn atuam nos meios-tons. Nenhum dos três tem opções.

O botão **Base colours on a new layer** do dock **Balde** dá a cada região fechada da arte-final (line art) sua própria cor chapada (as cores do dock Amostras, quando ele mostra alguma) numa nova camada abaixo dela — a etapa de cores chapadas antes do sombreamento — e deixa vazios os traços e o espaço ao redor do desenho.

A ferramenta **Gradiente** pinta da cor de primeiro plano → cor de fundo, ou com um gradiente seu: escolha-o em **Colours** na barra de opções, e **Edit…** ali abre o editor de gradientes, onde cada gradiente tem um nome e paradas de cor (cada uma com uma posição e uma cor com opacidade) que você adiciona, move, recolore e remove. Seus gradientes são mantidos entre sessões.

Atalhos de tecla única: `B / E / G / I / M / L / W / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` para variantes de forma.

### Pincéis

Seis tipos de pincel — Lápis / Caneta / Marcador / Aerógrafo / Aquarela / Sumi — mais presets construídos sobre eles (Giz de cera, Marca-texto, caligrafia Sumi …). O dock Pincel define Tamanho / Opacidade / Dureza / Densidade / Modo de mesclagem; a barra de opções traz Tamanho / Opacidade / Dureza. A pressão da caneta da mesa digitalizadora escala o tamanho e a opacidade pela curva definida em **Settings > Pressure Curve…**; um mouse desenha com pressão total. No dock Pincel, **Dispersão** desloca cada toque do pincel para fora do traço em até a fração do tamanho do pincel que ela define, **Variação de cor** altera o matiz, a saturação e o brilho de cada toque, e **Seguir inclinação da caneta** estreita a ponta no sentido transversal à direção em que a caneta da mesa digitalizadora se inclina e a gira para acompanhar essa inclinação (o preset caligrafia Sumi vem com essa opção ativada); um pincel de pixel art mantém sua ponta quadrada. Captura de ponta de pincel a partir de seleção, **File > Import brush preset…**.

### Camadas

Painel completo de camadas com miniaturas, alternância de visibilidade, botões ↑ / ↓ para reordenar (ou `Ctrl+[` / `Ctrl+]`), modos de mesclagem, opacidade, busca, camadas vetoriais, camadas 1-bit, **máscaras de camada** (adicionar / a partir da seleção / inverter / aplicar), **clipping masks**, **efeitos de camada** (sombra projetada / brilho externo / contorno). Dividir camada por cor, presets de mapeamento de gradiente.

### Seleção

Retângulo / Laço / Varinha / Seleção Rápida com modos **Substituir / Adicionar / Subtrair / Interseção**; com **Magnetic** marcado na barra de opções, o contorno do Laço se encaixa na borda mais forte da camada num raio de 10 px quando você solta o botão. **Modo Quick Mask** (`Q`) para fluxos de pintar-a-máscara. Diálogo **Stroke Selection**.

### Animação e mangá

- **Animação** — dock de timeline de frames: **+ Frame** faz um snapshot da imagem achatada, reprodução no FPS escolhido, o onion skin mostra o frame anterior; **Export…** salva os frames como GIF animado, WebP (sem perdas) ou PNG, cada frame durando um tique do FPS escolhido
- **Ferramentas de mangá** — Panel Cutter (depois, o **Snap to panel** do pincel mantém cada traço dentro do painel em que ele começa) · Camadas de retícula · Carimbar números de página · Speedlines (Radial / Paralelo / Burst) · Action Flash · Texto ao longo da seleção (dispõe o texto que você digita ao longo do contorno da seleção, em uma nova camada) · ferramenta de Balão de Fala

### Filtros e auxiliares de visualização

- **Filtros** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone · Match Colour (a atmosfera de cor de uma imagem de referência que você escolhe) · Match Swatches (cada pixel na cor mais próxima do dock Amostras) (os filtros de um único slider — Posterize, Threshold, Halftone, Match Colour — mostram um preview ao vivo num recorte em tamanho real da camada enquanto você arrasta; os demais abrem um diálogo de parâmetros OK / Cancel)
- **Auxiliares de visualização** — Grade de Pixels · Snap to Pixel · Snap to Edges · Onion Skin · Guias de Sangria · Rotação de Canvas (`Ctrl+Shift+H` gira CCW)

### Docks (14, em abas dentro de 3 grupos)

| Grupo | Docks |
|---|---|
| Desenho | Cor · Pincel · Balde · Amostras |
| Tela | Camada · Navegador · Histórico · Páginas · Animação · Histograma |
| Biblioteca | Materiais · Carimbos · Pose · Referência |

O dock Cor abre com um anel de matiz e um triângulo de saturação / brilho: arraste no anel para escolher o matiz e no triângulo para escolher a tonalidade, e os sliders e o campo HEX logo abaixo acompanham. O dock Materiais lista seus próprios materiais antes das retículas e texturas embutidas: imagens na pasta `materials` da pasta do programa do Imervue (uma pasta de primeiro nível chamada `texture`, `tone`, `pattern`, `brush_tip` ou `pose` as classifica nessa categoria) e as pontas de pincel que você capturou. **Edit > Save Selection as Material…** salva ali a parte selecionada do desenho, sem nunca sobrescrever um material anterior. O dock Amostras mostra suas cores recentes ou uma paleta — as embutidas Standard, Pastel e Manga, ou uma sua: **Save as Palette…** guarda as cores recentes com um nome e **Delete Palette** remove uma das suas — e **Filter > Match Swatches…** usa as cores que ele mostra. Cada dock é móvel / flutuante e pode ser alternado individualmente pelo menu **Window**. **Settings > Workspace Layouts…** oferece os layouts embutidos Default / Drawing / Comic / Compact; **Save current…** guarda, com um nome, quais dos docks Camada / Cor / Pincel / Navegador / Histórico / Referência estão visíveis, e aplicar um layout mostra ou oculta esses docks. Opções de ferramenta e tamanhos dos docks não são guardados.

### I/O de arquivos

- **New Canvas…** abre uma aba do tamanho que você escolher — um preset de papel, mangá ou tela (A4, página de mangá B5, 1080p, 4K …), um que você salvou com **Save as Preset…**, ou qualquer largura e altura — com fundo branco ou transparente; **New Tab** (`Ctrl+N`) mantém o padrão de 1024 × 1024 em branco
- **Open PSD…** achata o arquivo em uma única camada em uma nova aba; **Save as PSD…** grava as camadas com seus modos de mesclagem (sem máscaras nem efeitos de camada)
- **Export image…** grava PNG, JPEG, WebP, TIFF ou BMP, conforme o tipo de arquivo escolhido (JPEG e BMP, que não têm transparência, sobre fundo branco); projetos de quadrinhos exportam suas páginas para **CBZ** ou **PDF**. **Save Comic Project…** salva um quadrinho inteiro, cada página com suas camadas, em um único arquivo `.imervue-proj`, e **Open Comic Project…** o reabre. Só **Save as PSD…** conta como salvar a aba: depois de uma exportação, fechar ainda pergunta sobre as alterações não salvas dela
- **Autosave** — A cada 2 minutos, cada documento modificado mantém seus oito snapshots mais recentes. **File > Restore Autosave** abre a última versão legível em uma nova aba modificada, preservando as edições atuais; se estiver danificada, tenta uma versão anterior. Os snapshots nativos preservam o recorte dos painéis de mangá. A barra de status mostra o último autosave do documento ativo, falhas de gravação são informadas e fechar uma aba remove apenas seus próprios snapshots.

### UX para usuários avançados

- **Tab** alterna todos os docks para pintura sem distração
- `Ctrl+Tab` cicla pelas abas
- `,` / `.` cicla pelos tipos de pincel
- `0`-`9` definem opacidade do pincel em passos de 10 %
- `Alt+[` / `Alt+]` movem a camada ativa
- Clique direito no canvas abre menu rápido de Undo / Redo / Selecionar tudo / Desmarcar / Ajustar / 100 %
- Asterisco de modificação por aba, confirmações toast de undo / redo, prompt de recuperação de autosave na inicialização

Undo / Redo restaura a criação, exclusão, ordenação e mesclagem de camadas, além de propriedades, máscaras, vetores, grupos, seleções e camada de referência. Os comandos do menu e painel de camadas, camadas de mangá e inserção de materiais criam etapas de desfazer; cada documento mantém seu próprio histórico.

Cada documento Paint mantém até 50 etapas de histórico dentro de um limite de 512 MiB, incluindo o estado-base atual e os ramos Undo/Redo. Os pixels inalterados são compartilhados; pincel e borracha armazenam apenas os blocos modificados. As etapas antigas são removidas ao atingir o limite. Se um único instantâneo exceder o limite, o histórico é esvaziado e o documento editável é preservado.

Mudar para Paint preserva os documentos, as camadas, as alterações não salvas e o histórico de desfazer; a primeira visita mostra uma tela em branco. **File > Open Current Image in Paint** abre a imagem do visualizador em um novo documento. Esquerda/Direita na barra de abas principal de Paint também abre a imagem anterior/seguinte em um novo documento. `E` no Deep Zoom abre o editor de anotações separado.

---

## Puppet — animação 2D com rigging

A aba **Puppet** é um sistema de animação 2D de marionetes com rigging feito do zero: rigs com deformação de malha, parâmetros, motions, física, expressões, pose, sincronia labial e rastreamento facial por webcam, **sem SDK proprietário**, **sem `live2d-py`**, e com um formato de arquivo `.puppet` totalmente aberto, documentado em `Imervue/puppet/FORMAT.md`.

> **Tutorial completo**: [`puppet_guide.md`](../puppet_guide.md) cobre o
> fluxo de ponta a ponta tanto para transmissão ao vivo (OBS / NDI / câmera virtual)
> quanto para produção de animação (gravação / edição na timeline / exportação MP4).
> Versões em chinês em
> [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) e
> [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md).

### Formato de arquivo

`.puppet` é um contêiner zip:

- `puppet.json` — manifest (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — texturas de atlas
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — sobreposições de parâmetros
- `physics.json` — configuração de rig Verlet

Baseado em JSON, diff-friendly por humanos, sem binário proprietário. O formato é aberto e verificável: um arquivo salvo começa com uma entrada `mimetype` sem compressão (`application/vnd.imervue.puppet+zip`) e todo arquivo JSON indica seu schema em `$schema`; os quatro JSON Schemas estão publicados em [`docs/schemas/`](../docs/schemas/); `py -m Imervue.cli puppet-validate examples/puppet/imeru.puppet` (MCP `puppet_validate`) verifica um arquivo e `puppet-schema` (MCP `puppet_schema`) imprime um schema; [`docs/examples/read_puppet.py`](../docs/examples/read_puppet.py) lê um arquivo usando apenas a biblioteca padrão do Python. A especificação ([`Imervue/puppet/FORMAT.md`](../Imervue/puppet/FORMAT.md)) e os schemas têm licença MIT, então qualquer programa pode ler ou gravar arquivos `.puppet`.

### Renderizador

`QOpenGLWidget` com desenho de triângulos texturizados em vertex-array em draw_order, modos de mesclagem por drawable (normal / additive / multiply), exclusividade de pose-group, projeção ortográfica em image-space, fundo de xadrez de transparência em GL_REPEAT-tiled, zoom com roda + pan com arrasto do botão do meio. Otimizado para rigs grandes — um rig Cubism convertido com 307 drawables e 2965 vertex morphs roda a 60 FPS em CPU.

### Autoria

- **Importar PNG** → gera automaticamente uma malha de grade triangulada que respeita o alpha
- **Add Rotation Deformer** (anchor + ângulo) / **Add Warp Deformer** (lattice bilinear de rows × cols) no menu **Edit**
- **Add Parameter** → defina formas-chave nos extremos do slider via **Set Key** no dock de parâmetros
- **Editor de malha** — alterne Edit Mesh para arrastar vértices; cliques dentro de 8 px se ajustam ao mais próximo
- **Linha do tempo de motion** — em **Edit > Edit motion…** arraste chaves e alças de bézier; **Ease** remodela uma trilha com um de 31 easings nomeados (elastic e bounce viram chaves amostradas) e **Simplify Keys** descarta as chaves de uma take gravada que ficam dentro de uma tolerância da linha que liga as chaves vizinhas
- **Repair Rig** — **Tools > Repair Rig** limpa a malha de cada drawable (triângulos quebrados e de área zero, vértices duplicados que compartilham posição e UV, vértices não usados — os pesos de osso e os vertex morphs acompanham os vértices que permanecem) e faz os pesos de osso de cada vértice somarem 1
- **Save As…** grava o rig inteiro em um zip `.puppet`

### Runtime

- **Rig de parâmetros** — cada parâmetro mantém uma lista de chaves mapeando um valor de slider para um snapshot parcial de forma de deformer; o runtime amostra e faz lerp campo a campo
- **Reprodução de motion** — dock inferior com lista de motions + Play / Pause / Stop / Loop / scrub; o amostrador de curvas honra segmentos `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` (resolução de tempo → param por iteração de Newton); fade-in / fade-out por motion
- **Expressões** — pilha de sobreposições de parâmetros `additive` / `multiply` / `overwrite`
- **Pose groups** — visibilidade mutuamente exclusiva de drawables (trocas de arma, variantes de formato de boca); o dock **Pose** escolhe qual membro cada grupo mostra
- **Física** — cadeias de pêndulo Verlet para cabelo / pano / fitas; param de entrada move a âncora da cadeia, gravidade + amortecimento + molas por partícula puxam de volta ao repouso
- **Vertex morphs** — blend linear estilo Cubism entre rest e ±deltas extremos; numpy vetorizado por frame a 60 FPS
- **Opacity keys** — curvas de alpha dirigidas por parâmetro; permite que malhas de pose alternativa façam fade-in / fade-out conforme um parâmetro de gesto dispara

### Entrada ao vivo

- Drag-track head — a cabeça e os olhos se voltam para o cursor enquanto ele se move sobre o canvas
- Auto-piscar em uma curva cosseno open → close → open
- Sincronia labial por microfone via `sounddevice` RMS → `ParamMouthOpenY` (dep opcional)
- Sincronia labial a partir de um arquivo de áudio — **Live > Lip-sync from Audio File…** transforma um WAV em um motion que abre `ParamMouthOpenY` conforme o volume (30 vezes por segundo, descartando as chaves que não acrescentam nada) e toca o WAV como seu som; sem dependência extra
- Rastreamento facial por webcam via OpenCV + o FaceLandmarker do MediaPipe Tasks → yaw / pitch / roll da cabeça + abertura de olho / boca (deps opcionais)
- Gravação de motion customizado — captura valores de parâmetros a 30 Hz enquanto você balança sliders / encara a webcam / deixa a física rodar; bake em Motion de segmentos lineares pronto para reproduzir / loopar / salvar

### Interop com Cubism

O **Cubism Native SDK** pode ser plugado (DLL fornecida pelo usuário — a Free Material License do Live2D proíbe a redistribuição) para converter qualquer modelo `.moc3` em um zip `.puppet`. O conversor executa uma varredura sample-and-reconstruct que captura tanto deltas de vertex-morph quanto transições de visibilidade dirigidas por parâmetro, de modo que toggles de gesto (sinal de paz / cobrir o rosto / foto …) sobrevivem à conversão intactos.

### Saída

- **Capture frame…** salva um PNG só do personagem, no tamanho próprio do rig (lado maior de no máximo 4096 px), sobre fundo transparente
- **Record…** alterna um loop de frames de 30 FPS para GIF / WebM / MP4 via `imageio`, com o personagem ajustado em 1080 px sobre branco (esses frames não têm alpha)
- **Câmera virtual** — expõe o canvas do puppet como webcam do sistema
- **Saída NDI** — transmite o puppet como fonte NDI na LAN
- **Servidor de API VTube Studio** — API WebSocket opcional para clientes compatíveis com VTS

### Transmissão ao vivo para OBS

Dois caminhos suportados. Escolha A para "funciona logo de cara", B se você quer
menor latência e melhor qualidade em uma LAN rápida.

#### A. Câmera virtual (mais fácil)

O canvas do puppet aparece como webcam que o OBS capta via sua fonte padrão
Video Capture Device.

1. `pip install pyvirtualcam`
2. Instale o driver da plataforma:
   - **Windows**: o OBS Studio 26+ traz o driver *OBS Virtual Camera*. Após instalar o OBS, abra-o uma vez e clique em **Start Virtual Camera** no painel inferior direito — isso registra o driver no sistema para que `pyvirtualcam` consiga encontrá-lo.
   - **macOS**: o OBS para Mac traz uma system extension OBS Virtual Camera. A primeira execução vai pedir para habilitá-la em System Settings → Privacy & Security.
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (instale `v4l2loopback-dkms` antes).
3. Na aba Puppet, abra seu rig, depois alterne **Output > Virtual camera**. A barra de status mostra o nome exato do dispositivo a escolher.
4. No OBS: **Sources > + > Video Capture Device**, escolha o dispositivo nomeado no passo 3 (tipicamente *OBS Virtual Camera*).

Imervue limita o lado mais longo da saída de streaming em 1080 px para que canvases nativos do Cubism (muitas vezes com 3000–8000 px de altura) não sejam rejeitados pelo driver de câmera virtual DirectShow. A proporção é preservada; o OBS pode escalar mais se necessário.

##### Por que o fundo é magenta? (e como removê-lo)

Câmeras virtuais rodam sobre **DirectShow** (Windows) / **AVFoundation**
(macOS) / **v4l2loopback** (Linux). Os três transportes são
**apenas RGB — sem canal alpha**. A fonte *Video Capture Device* do OBS
trata o que a câmera envia como RGB opaco, então qualquer cor
que o Imervue coloque atrás do personagem é o que o OBS exibe.

Imervue escolhe **magenta `#FF00FF`** como esse fundo porque
é a cor de chroma-key padrão da indústria: quase nunca
aparece em tons de pele, cabelo ou olhos, então o limiar
do chroma-key pode ficar bem aberto sem comer o personagem.

Para remover o magenta no OBS:

1. Clique direito na fonte *Video Capture Device* que você adicionou → **Filters**
2. No painel inferior esquerdo **Effect Filters** → **+** → **Color Key**
3. Configure:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF` (ou R = 255 / G = 0 / B = 255)
   - **Similarity**: comece em `80`, suba para `200–300` se ainda aparecerem bordas magenta. Maior = remoção mais agressiva.
   - **Smoothness**: `30–50` suaviza a borda para que o corte não fique duro / pixelizado.
4. Feche o diálogo. O OBS associa o filtro à fonte, então da próxima vez que você habilitar a câmera virtual o chroma-key será aplicado automaticamente.

Se o personagem tiver magenta na paleta (incomum mas possível em arte de figurino / adereços), o chroma key vai comer aqueles pixels também. Mude para o caminho NDI abaixo — o NDI carrega o canal alpha diretamente, então nenhum chroma-keying é necessário.

**Solução de problemas: ainda vejo magenta no OBS**

- Verifique que o filtro Color Key está anexado à fonte **Video Capture Device**, não a uma Scene. Filtros na fonte viajam com ela; filtros na Scene se aplicam por cima depois que a fonte é renderizada.
- Cheque que o hex é `FF00FF` exatamente — `FF00FE` ou similar não vai pegar todos os pixels magenta.
- Aumente *Similarity* para `300` se houver um halo fino de pixels magenta no contorno do personagem. As bordas vêm da interpolação GL_LINEAR contra o fundo magenta; uma tolerância de similaridade mais ampla as elimina.

#### B. NDI (menor latência, qualidade profissional)

NDI (Network Device Interface da Newtek) transporta o puppet pela
LAN com latência inferior a 50 ms e canal alpha intacto.

1. Baixe e instale o **NDI Tools** em
   <https://ndi.video/tools/> (inclui o runtime NDI).
2. `pip install ndi-python`
3. Instale o plugin **obs-ndi** no OBS:
   <https://github.com/obs-ndi/obs-ndi/releases>
4. Na aba Puppet, alterne **Output > NDI output**. A barra de status
   informa o nome da fonte NDI (padrão *Imervue Puppet*).
5. No OBS: **Sources > + > NDI Source**, escolha a fonte do
   passo 4.

NDI transmite na mesma resolução com limite de 1080 que o caminho A, mas
entrega RGBA — a renderização off-screen produz um fundo
transparente fora do personagem, o NDI envia o canal alpha
intacto, e OBS / vMix compõem o puppet diretamente sobre sua
cena sem qualquer passo de chroma-key.

#### C. Captura de janela (fallback)

OBS **Sources > + > Window Capture** pode capturar a janela do Imervue
diretamente, sem dependências extras. Qualidade menor e você precisa
recortar o chrome manualmente, mas funciona em máquinas com
restrições onde você não pode instalar drivers.

### Demo

O rig incluído é [`examples/puppet/imeru.puppet`](../examples/puppet/imeru.puppet) — **Imeru**, o mascote original do Imervue: 45 drawables em um canvas de 1024 × 1336, todos os parâmetros padrão do Cubism mais braços com duas articulações, giros de cabeça com paralaxe no estilo Live2D, uma sombra no rosto que muda de forma conforme ela se vira para longe da luz, piscadas com as íris recortadas pelo branco dos olhos, física de cabelo, 8 motions (dois loops Idle, TapHead, TapBody e quatro Gestures, incluindo um aceno) e 7 expressões. Abra-o via **File > Examples > Imeru** ou **Open Puppet…** e clique na cabeça ou no corpo dela para vê-la reagir. Ela é feita inteiramente por código, do jeito que os jogos de anime em 3D constroem seus personagens: o cabelo, o corpo, a roupa e os braços dela são modelados e recebem cel shading no Blender com os truques de sombreamento desses jogos (cabelo iluminado pelas normais de uma forma substituta suave, mechas e traços de brilho pintados, oclusão pré-calculada), sendo renderizados uma camada do puppet por vez, o rosto dela é sombreado a partir de um mapa de sombra facial SDF, os olhos, as sobrancelhas e a boca são pintados por cima, e as camadas são então riggadas, então o arquivo não carrega direitos de terceiros; `py -3 examples/puppet/imeru/build.py` o reconstrói (Blender 4.2 ou mais recente).

---

## Desktop Pet — overlay sem moldura

Aba 5 — o **Desktop Pet** coloca qualquer personagem `.puppet` na sua área de trabalho como um overlay sem moldura e transparente. A aba em si é o painel de controle; o personagem propriamente dito flutua por cima (ou atrás) das suas outras janelas. Tudo o que você pode fazer com um rig na aba Puppet — motions, expressões, física, drivers ociosos, entrada por webcam / microfone — também funciona aqui.

### O que dá para fazer

| Recurso | O que faz |
|---|---|
| Overlay sem moldura | Sem chrome de janela, sem entrada na barra de tarefas — só o personagem na sua área de trabalho. |
| Fundo transparente | Tudo o que o personagem não cobre deixa a área de trabalho aparecer atrás. |
| Arrastar para mover | Arraste o personagem com o botão esquerdo para uma nova posição. Solte perto de uma borda da tela para **encaixar** rente a ela. |
| Modo click-through | Faça o pet ignorar o mouse para que você continue trabalhando por baixo dele. |
| Travar posição | Congela o pet para que arrastos acidentais não consigam movê-lo. |
| Sempre no fundo | Coloca o pet atrás de todas as outras janelas — sensação de widget de desktop em vez de sempre no topo. |
| Esconder em tela cheia | Esconde automaticamente enquanto outro app (jogo / vídeo / apresentação) estiver em tela cheia no mesmo monitor; volta quando a tela cheia termina. |
| Pausa quando oculto | O pet para de redesenhar enquanto está invisível; os temporizadores dos drivers ao vivo continuam rodando. |
| Presets de tamanho | Pequeno / médio / grande. Redimensiona ao redor do centro, para que o pet não salte pela tela. |
| Slider de opacidade | Faz o pet desbotar de 10% a 100%, para que possa ser um enfeite sutil da área de trabalho. |
| Lembra onde você colocou | Arraste o pet para o seu canto favorito; ele volta para lá no próximo lançamento. |
| Atalhos globais | Mostre / esconda o pet, trave-o, alterne o click-through ou faça-o falar a partir de qualquer app (precisa de `pynput`): Ctrl+Shift+P / L / T / Space por padrão, cada um reatribuível no grupo **Global hotkeys** da aba. Uma tecla que outra ação já usa é recusada, e teclas salvas que duas ações compartilham são indicadas na linha de status. |

### Interações de clique

- **Clique esquerdo no corpo** — se o rig definir uma hit area (ex.: tocar na cabeça), o motion correspondente é reproduzido. Caso contrário, o pet te cumprimenta com um balão de fala.
- **Clique direito em qualquer lugar** — abre um menu de contexto com: Esconder pet, Live drivers, Play motion (lista de todos os motions do rig), Apply expression, Pose (escolher o membro exibido de cada pose group), Travar posição, Click-through, Sempre no fundo, Esconder em tela cheia, Balão de fala, Tamanho.
- **Ícone da bandeja do sistema** — clique esquerdo alterna a visibilidade, clique direito traz Mostrar/Esconder, Click-through, Abrir puppet, Esconder pet.

### Drivers ao vivo

Escolha qualquer combinação na aba ou no menu de clique direito. Auto idle, Idle motions e Auto-blink vêm ligados por padrão; os demais vêm desligados — ative apenas o que você quiser.

- **Auto idle** — respiração + drift sutil para o personagem se sentir vivo.
- **Idle motions** — cicla aleatoriamente pelos motions do grupo idle do rig.
- **Auto-blink** — ciclo natural de fechar os olhos a cada poucos segundos.
- **Drag-track head** — a cabeça e os olhos se voltam para o cursor enquanto ele está sobre o pet.
- **Mouse gaze** — os olhos e a cabeça seguem o cursor em qualquer lugar da tela.
- **Sincronia labial por microfone** — a boca abre com a sua voz (precisa de `sounddevice`).
- **Rastreamento por webcam** — sua cabeça / olhos / boca comandam os do puppet (precisa de `opencv-python` e `mediapipe`).

### Como começar

1. Mude para a aba **Desktop Pet**.
2. Clique em **Load bundled Imeru** para usar o personagem incluído, ou em **Open Puppet…** para escolher seu próprio arquivo `.puppet`.
3. Marque **Show pet on desktop**.
4. Arraste o personagem para onde quiser; escolha os drivers desejados; ajuste opacidade / tamanho.
5. Clique direito a qualquer momento para o menu de ação rápida, ou use o ícone da bandeja do sistema para esconder o pet sem precisar achar a aba.

Tudo o que você configura — posição, drivers, opacidade, click-through, tamanho — é lembrado entre lançamentos.

O plugin **Desktop Pet Integrations** (**Plugins > Download Plugins**) adiciona **Plugins > Desktop Pet Integrations**: o pet reage ao OBS (transmissão, gravação, troca de cena), a palavras-chave do chat da Twitch (em qualquer parte de uma mensagem, ou `=hi` para a mensagem inteira, `!dance*` para o início dela, `/go+al/` para uma expressão regular), a um webhook local (`POST http://127.0.0.1:9876/trigger` com `{"group": "Wave", "speech": "Hi!"}`) e às notificações do Windows. Ele também é o exemplo de um plugin de pet construído sobre `on_pet_created`.

### Voz personalizada (pet script)

O balão de fala do pet vem de um arquivo JSON que você mesmo pode criar. Clique em **Load script…** no grupo **Pet script** da aba Desktop Pet e escolha um `.petscript.json`. O esquema:

```json
{
  "version": 1,
  "name": "Friendly pet",
  "greetings": ["Hi!", "Hello!"],
  "time_of_day_greetings": {
    "morning": ["Good morning!"],
    "night": ["Still up?"]
  },
  "hit_responses": {
    "HitAreaHead": ["Don't poke me!", "Stop!"]
  },
  "motion_lines": {
    "wave": ["Hi there!"]
  },
  "scheduled": [
    {"every_seconds": 1800, "messages": ["Stretch break!"]}
  ]
}
```

- **`greetings`** — usadas quando nada mais específico corresponde a um clique.
- **`time_of_day_greetings`** — saudações por faixa do relógio local (`morning` 05–11 h, `afternoon` 12–17 h, `evening` 18–21 h, `night` 22–04 h), usadas antes de `greetings`; uma faixa sem linhas recorre a `greetings`.
- **`hit_responses`** — linhas por `HitArea`. As chaves precisam corresponder aos IDs das hit areas definidos no rig.
- **`motion_lines`** — linhas por motion. Faladas quando um clique em hit area reproduz um motion com esse nome (não quando um motion é iniciado pelo menu de contexto).
- **`scheduled`** — avisos disparados por temporizador. Cada entrada dispara a cada `every_seconds` segundos.

As linhas alternam em round-robin por bucket para que o usuário não ouça a mesma linha duas vezes seguidas. **Reset to default** descarta o script personalizado e traz de volta o conjunto de saudações embutido.

Um exemplo funcional vive em [`examples/desktop_pet/imeru.petscript.json`](../examples/desktop_pet/imeru.petscript.json); suas linhas de cabeça e corpo respondem a cliques nas hit areas `Head` e `Body` da Imeru.

---

## Atalhos de teclado e mouse

### Navegação (todos os modos)

| Atalho | Ação |
|----------|--------|
| Teclas de seta | Grade: mover o anel de foco (Enter o abre) / Deep zoom: Esquerda/Direita trocam imagens |
| Ctrl+Shift+←/→ | Ir para a pasta irmã anterior / próxima com imagens |
| Alt+← / Alt+→ | Voltar / avançar no histórico |
| Ctrl+G | Ir para imagem por índice |
| X | Saltar para uma imagem aleatória |
| Home | Ajustar a imagem à janela (na grade: rolar de volta ao topo) |
| Ctrl+F ou / | Abrir diálogo de busca fuzzy |
| T | Abrir Tags & Albums |
| Ctrl+Shift+P | Abrir Paleta de Comandos |
| Alt+M | Reproduzir último macro na seleção atual |
| S | Abrir diálogo de slideshow |
| Ctrl+Z | Desfazer |
| Ctrl+Shift+Z / Ctrl+Y | Refazer |

### Deep Zoom / imagem única

| Atalho | Ação |
|----------|--------|
| F | Alternar tela cheia |
| Shift+Tab | Alternar modo cinema (esconder todo o chrome) |
| R / Shift+R | Rotacionar CW / CCW |
| E | Abrir a imagem atual no editor de anotações |
| W / Shift+W | Ajustar à largura / altura |
| Shift+F | Ajustar à janela |
| - / = | Diminuir / aumentar o zoom |
| V | Modo de leitura (ajustar à largura, rolar para ler, avançar para a próxima imagem no fim) |
| L | Lupa: uma lente de aumento que segue o cursor (também sobre as miniaturas) |
| H | Alternar overlay de histograma RGB |
| F8 / Ctrl+F8 | Overlay OSD / HUD de depuração |
| Shift+P | Alternar vista de pixel (zoom ≥ 400 % mostra RGB; a grade quando ≤ 40.000 pixels estão na tela) |
| Shift+M | Ciclar modos de cor (Normal / Tons de Cinza / Invertido / Sépia) |
| B | Alternar favorito |
| Ctrl+C / Ctrl+V | Copiar / colar imagem do/para o clipboard |
| 0 / 1-5 | Alternar favorito / avaliação rápida |
| F1-F5 | Etiqueta de cor rápida (vermelho / amarelo / verde / azul / roxo) |
| P / Shift+X / U | Triagem: Manter / Rejeitar / Remover marca |
| Shift+S | Vista dividida |
| Shift+D / Ctrl+Shift+D | Página dupla (LTR / RTL) |
| Ctrl+Shift+M | Janela de espelhamento multi-monitor |
| Delete | Mover para lixeira com os sidecars `.xmp` / de anotações (com undo); numa unidade sem lixeira (cartão de memória, pendrive, unidade de rede) o arquivo fica até você confirmar a exclusão definitiva |
| Escape | Sair do deep zoom / Sair da tela cheia |

### Reprodução de animação (GIF / APNG)

| Atalho | Ação |
|----------|--------|
| Espaço | Play / Pause |
| , (vírgula) / . (ponto) | Quadro anterior / próximo |
| [ / ] | Diminuir / aumentar velocidade de reprodução |

### Grade de Tiles

| Atalho | Ação |
|----------|--------|
| Ctrl+L | Alternar Grade ↔ Lista |
| Hover (500 ms) | Popup de pré-visualização ao passar o mouse |
| Delete | Excluir tiles selecionados |
| Escape | Desmarcar todos |

### Mouse / touchpad

| Ação | Comportamento |
|--------|----------|
| Clique esquerdo | Selecionar tile ou abrir imagem |
| Arrasto esquerdo | Multi-seleção retangular na grade |
| Pressionar e segurar (500 ms) | Entrar no modo de seleção de tiles |
| Arrasto do meio | Pan em deep zoom |
| Roda de rolagem | Zoom in/out ou rolagem |
| Clique direito | Menu de contexto |
| Pinça | Zoom in/out em deep zoom |
| Deslizar horizontal | Imagem anterior / próxima |

### Aba Paint (além dos anteriores)

| Atalho | Ação |
|----------|--------|
| B / E / G / I | Pincel / Borracha / Preenchimento / Conta-gotas |
| V / T / U / R | Mover / Texto / Gradiente / Smudge |
| M / L / W | Seleção retangular / Laço / Varinha mágica |
| P / S / C / Z / H | Caneta / Clone / Recortar / Zoom / Mão |
| Q | Alternar Modo Quick Mask |
| Tab | Alternar todos os docks |
| Ctrl+Tab / Ctrl+Shift+Tab | Aba Paint seguinte / anterior |
| , / . | Ciclar tipos de pincel |
| 0-9 | Opacidade do pincel em passos de 10% |
| Alt+[ / Alt+] | Mover camada ativa para baixo / cima |
| Ctrl+[ / Ctrl+] | Mover a camada ativa para baixo / cima na pilha |
| Ctrl+D | Desmarcar seleção |
| [ / ] | Diminuir / aumentar o tamanho do pincel em 1 px |
| Shift+[ / Shift+] | Diminuir / aumentar o tamanho do pincel em 5 px |
| Ctrl+Shift+N / Ctrl+J / Ctrl+E | Adicionar camada / Duplicar camada / Mesclar para baixo |
| Ctrl+0 / Ctrl+1 | Ajustar à janela / Tamanho real (100 %) |
| X | Trocar cores de primeiro plano / fundo |
| D | Redefinir cores para preto / branco |

---

## Estrutura de menus

### File

- New Window
- Open File / Open Folder
- Recent (pastas + imagens)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — salvar / carregar / renomear layouts de janela nomeados
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (vinculações customizáveis)
- Exit

### Tools (ferramentas extras — organizadas em 8 submenus agrupados)

- **Batch** — Conversão de formato · Remoção EXIF · Sanitizador de imagens · Organizador de imagens · Token Batch Rename · Deflicker (time-lapse) · Binarização de documentos · Limiar de Otsu · Editar animação · Otimizar para tamanho-alvo · Legenda de meme · Esteganografia
- **Library & Metadata** — Library Search · Smart Albums · Encontrar imagens similares · Busca semântica · Encontrar imagens duplicadas · Auto-Tag de imagens · Tags hierárquicas · Exportar metadados (CSV / JSON) · Sidecars XMP · Geotag GPS · Geotag a partir de trilha GPX · Editar data de captura · Modelo de metadados · Cache de miniaturas
- **Views** — Vista Timeline (por dia / mês / ano) · Vista Calendar · Vista Map · Scopes & Inspector · Tiny Planet (360°) · Estatísticas da imagem · Relatório de qualidade · Carta de teste · Prévia de daltonismo (protanopia / deuteranopia / tritanopia / acromatopsia)
- **Workflow** — Triagem · Staging Tray · Painel de referência · Cópias Virtuais · Gerenciador de arquivos de painel duplo · Macros · Pasta monitorada
- **Export** — PDF de Contact Sheet · Galeria Web · Vídeo Slideshow (MP4) · Print Layout · Colagem · Folha de fotos para documento
- **Develop (Non-Destructive)** — Comparar antes / depois · Predefinições de revelação · Curva tonal · LUT .cube · Split Toning · Máscaras de ajuste local · Camadas · Níveis · Channel Mixer · Gradient Map · Balanço de cor automático · Clarity / Dehaze · HSL / Color Mixer · CLAHE · Achatar fundo · Moldura e legenda · Dither ordenado · Color Map · Distorcer · Coordenadas polares · Kaleidoscope · Frosted Glass · Pixel Sort · Granulação de filme · Lens Flare · Limiar / Posterizar · Solarizar · Brilho difuso · Graduated Density · Velvia · Emboss · Defringe · Film Negative · Filmic Tone Map · Tone / Detail Equalizer · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Redução de ruído / Sharpening · Pincel de cura · Carimbo de clonagem · Separação de frequências · Recorte inteligente · Retoque automático de retrato · Detecção facial · Céu / Plano de fundo · Recorte / Endireitar · Auto-endireitar · Correção de lente · Barra de escala
- **Multi-Image** — Composição HDR · Costura de Panorama · Focus Stacking · Pilha de imagens · Anáglifo 3D

### View / Sort / Filter / Language / Plugins / Instructions

(Menus padrão — veja no aplicativo as opções completas.)

### Menu de contexto do botão direito

Navegação · Ações rápidas (revelar / copiar caminho / copiar imagem) · Transformações · Operações em lote · Excluir · Wallpaper · Comparar / Slideshow · Exportar · Ferramentas extras · Favoritos · Informações da imagem · Itens contribuídos por plugins.

---

## Sistema de plugins

Imervue suporta plugins de terceiros. Veja [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) para a referência completa.

### Início rápido

1. Crie uma pasta dentro de `plugins/` na raiz do projeto
2. Defina uma classe estendendo `ImervuePlugin`
3. Registre-a em `__init__.py` com `plugin_class = YourPlugin`
4. Reinicie o Imervue

### Hooks

| Hook | Gatilho |
|------|---------|
| `on_plugin_loaded()` | Após o plugin ser instanciado |
| `on_plugin_unloaded()` | Quando a janela dele fecha, e antes de Reload Plugins |
| `on_build_menu_bar(plugin_menu)` | Depois que o menu Plugins compartilhado é construído |
| `on_build_main_tabs(tabs)` | Depois que as cinco abas embutidas são adicionadas |
| `on_build_context_menu(menu, viewer)` | Quando o menu de clique direito é aberto |
| `on_image_loaded(path, viewer)` | Após a imagem carregar em deep zoom |
| `on_folder_opened(path, images, viewer)` | Após a pasta abrir na grade |
| `on_image_switched(path, viewer)` | Ao navegar entre imagens |
| `on_image_deleted(paths, viewer)` | Após imagens serem soft-deletadas |
| `on_key_press(key, modifiers, viewer)` | Ao pressionar tecla (retorne True para consumir) |
| `on_pet_created(pet)` | Quando a janela do Desktop Pet é criada, ou se ela já existe quando o plugin carrega |
| `on_app_closing(main_window)` | Antes de a aplicação fechar |
| `get_translations()` | Fornecer strings i18n |
| `register_languages()` | Método de classe: registrar novos idiomas (antes de cada carregamento e na inicialização) |

Além dos hooks, um plugin pode dar à Exportação em Lote outro renderizador para as receitas de revelação: registre um `BackendProvider` com `Imervue.image.develop_backends.register` em `on_plugin_loaded`. O plugin GPU Develop é o exemplo; [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) traz os detalhes.

Um diálogo que executa uma transformação de imagem ao clicar em **OK** pode obter a linha de botões, a instalação de pacotes opcionais, o worker e o toast de resultado de `Imervue.plugin.tool_dialog.ToolDialogMixin`. Um plugin que importa código do programa principal adicionado depois de versões mais antigas declara a versão da API de plugins de que precisa em um `plugin.json` ao lado do seu `__init__.py` (`{"min_api_version": 2}`); um Imervue antigo demais o ignora e registra o motivo no log, em vez de falhar dentro dos imports do plugin.

### Downloader de plugins

**Plugins > Download Plugins** abre o downloader online. Repositório-fonte: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins). Um plugin que precisa de um Imervue mais novo não é instalado: a linha de status mostra a versão da API de plugins de que ele precisa, e qualquer cópia já instalada fica como estava. Atualize o Imervue e baixe o plugin novamente.

---

## Servidor MCP

Imervue traz um servidor [Model Context Protocol](https://modelcontextprotocol.io) embutido para que assistentes de IA (Claude Code / Desktop, Cursor, Cline, …) possam chamar os helpers de lógica pura do projeto sem uma GUI rodando. Sem dependência de Qt; um único comando:

```sh
python -m Imervue.mcp_server
```

### Ferramentas

Ferramentas selecionadas (58 no total — lista completa na documentação). Toda
ferramenta anuncia um `outputSchema` JSON e `annotations` de somente-leitura /
destrutivas, retorna seu resultado como `structuredContent` e ferramentas de
longa duração transmitem `notifications/progress`.

| Ferramenta | Finalidade |
|------|---------|
| `list_images` | Listar arquivos de imagem em uma pasta (recursivo opcional) |
| `read_image_metadata` / `read_xmp_tags` | Dimensões, formato, EXIF, XMP: o sidecar ou, sem ele, o embutido no arquivo (avaliação, etiqueta, palavras-chave) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | Análise sem referência: estatísticas por canal, colorfulness/entropia/contraste, histograma + clipping, pontuação de desfoque |
| `image_thumbnail` / `ocr_text` / `find_similar` | Prévia em base64, texto via Tesseract, grupos de quase duplicatas por hash perceptual (com progresso) |
| `convert_format` | Converter entre PNG / JPEG / WebP / TIFF / BMP / AVIF (+ HEIC / JXL opcionais) |
| `apply_watermark` / `apply_frame` | Gravar uma marca d'água de texto ou uma moldura passe-partout / Polaroid + legenda |
| `build_collage` | Compor imagens em uma montagem em grade (com progresso) |
| `crop_image` / `resize_image` / `rotate_image` | Recorte por pixel, redimensionamento (informar um lado mantém a proporção; informar os dois dá um tamanho exato), rotação / espelhamento sem perdas. Tamanhos e coordenadas se referem à imagem endireitada pelo EXIF. |
| `collection_stats` | Resumo de avaliação / favorito / etiqueta de cor / triagem da pasta |
| `search_images` | Filtra uma pasta com a DSL de consulta dos smart albums (caminho / EXIF / tamanho / dimensões) |
| `extract_gps` / `dominant_colors` | Lê coordenadas GPS do EXIF (encadeia com `reverse_geocode`); paleta de cores por median-cut (rgb / hex / pixel_count) |
| `error_level_analysis` | Mapa de adulteração por recompressão JPEG como um PNG data URI |
| `solarize_image` / `glow_image` | Aplica uma inversão tonal solarize ou um brilho difuso e salva |
| `velvia_image` / `emboss_image` / `defringe_image` | Boost de saturação Velvia, emboss de luz direcional, dessaturação de franjas de borda |
| `film_negative_image` / `graduated_density_image` | Inverte um negativo escaneado; aplica um gradiente de densidade graduada linear |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Rolloff filmic de realces; exposição por zona; contraste por banda |
| `colormap_image` / `false_color_image` | Recolorir a luminância por um mapa viridis/magma/jet; escala de exposição em falsas cores |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Pontilhado Bayer ordenado; split-toning de sombras/luzes; ordenação de pixels por faixa de brilho |
| `polar_image` / `kaleidoscope_image` | Distorção para/de polar (tiny-planet); espelhamento em cunhas de caleidoscópio |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | Dispersão de vidro fosco por vizinho aleatório; equalização local CLAHE; contraste local de clareza + textura |
| `posterize_image` / `gradient_map_image` | Quantizar os canais em faixas planas; remapear a luminância por um gradiente |
| `film_grain_image` / `dehaze_image` / `distort_image` | Granulação gaussiana ajustável; remoção de névoa por canal escuro; distorção redemoinho/pinça/ondulação |
| `levels_image` / `curve_image` | Níveis de ponto preto/branco + gama; curva de tons (curva em S / clarear sombras / comprimir luzes) |
| `auto_color_balance_image` / `channel_mixer_image` | Balanço de branco automático (4 métodos); mixer de canais 3×3 + conversão mono |
| `lens_correction_image` | Corrigir distorção (k1), vinheta e aberração cromática vermelha/azul |
| `reverse_geocode` / `extract_video_frame` | GPS → cidade offline, decodificar um frame de vídeo em imagem estática |
| `puppet_from_png` / `puppet_inspect` | Construir um rig `.puppet` a partir de um PNG; abrir um e retornar seu inventário |
| `puppet_validate` / `puppet_schema` | Verificar um `.puppet` contra o formato v1 (schemas, carregador, verificações do rig); retornar um dos seus JSON Schemas |

### Prompts

Quatro prompts reutilizáveis: `caption_image`, `suggest_edits`, `analyze_composition`
(crítica de composição guiada por saliência) e `flag_issues` (triagem de nitidez +
qualidade + clipping). `completion/complete` sugere valores para o `style` de
`suggest_edits` e o `focus` de `analyze_composition`.

### Configuração

O repositório traz um `.mcp.json` na raiz para auto-descoberta pelo Claude Code. Para Desktop / outros clientes, adicione isto ao `claude_desktop_config.json` (ou equivalente):

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

Superfície completa do protocolo na seção MCP de [docs/en/index.rst](../docs/en/index.rst).

---

## Suporte multilíngue

| Idioma | Código |
|----------|------|
| English | `English` |
| 繁體中文 (Chinês Tradicional) | `Traditional_Chinese` |
| 简体中文 (Chinês Simplificado) | `Chinese` |
| 한국어 (Coreano) | `Korean` |
| 日本語 (Japonês) | `Japanese` |

Altere pelo menu **Language**. Requer reinicialização.

Plugins podem registrar idiomas totalmente novos via `language_wrapper.register_language()` ou contribuir traduções para os embutidos via `get_translations()` (chaves existentes nunca são sobrescritas, então um plugin não consegue quebrar uma string de fábrica). Uma string de plugin vazia, ou cujos `{placeholders}` diferem dos da string em inglês, é descartada e registrada no log, de modo que o texto embutido aparece no lugar de um espaço em branco ou de um erro. **Español** é oferecido exatamente assim: instale o plugin `spanish_translation` pelo downloader e ele aparece no menu Language ao lado dos cinco idiomas embutidos. Veja [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## Configurações do usuário

Armazenado em `user_setting.json` ao lado da aplicação — a raiz do projeto num checkout de código-fonte, a pasta que contém o `.exe` num build congelado (PyInstaller **ou** Nuitka).

O arquivo é um **contêiner multiperfil**: cada perfil guarda um dicionário de configurações independente, então uma única instalação pode carregar configurações separadas (por exemplo *Work* e *Personal*). Alterne, crie, renomeie e exclua perfis em **File > Profiles…**. Um arquivo v1 de perfil único herdado de uma versão anterior é migrado automaticamente para o perfil `default` na primeira leitura. As gravações são agrupadas alguns segundos após a última mudança e chegam de forma atômica (arquivo `.tmp` irmão + `os.replace`), de modo que um salvamento interrompido nunca trunca o arquivo. Se o arquivo não puder ser lido na inicialização (JSON corrompido ou outro programa o segurando), o Imervue inicia com as configurações padrão e, antes do primeiro salvamento, guarda uma cópia ao lado como `user_setting.json.unreadable-<data>-<hora>`; sem essa cópia ele nunca grava por cima. Um aviso na inicialização mostra o arquivo e como recuperar as configurações anteriores.

O log de cada sessão, `imervue.log`, é gravado na mesma pasta (em `%LOCALAPPDATA%\Imervue`, ou em `~/.cache/imervue` fora do Windows, quando essa pasta é somente leitura). O log da sessão anterior fica ao lado como `imervue.previous.log`, então, depois de um travamento, o log que o explica continua lá quando o Imervue volta a rodar — anexe os dois ao relatar um problema.

Entradas principais do perfil ativo:

| Configuração | Tipo | Descrição |
|---------|------|-------------|
| `language` | string | Código do idioma atual |
| `user_recent_folders` / `user_recent_images` | list | Aberturas recentes |
| `user_last_folder` | string | Restaurada automaticamente na inicialização |
| `bookmarks` | list | Caminhos de imagens favoritadas (máx 5000) |
| `sort_by` / `sort_ascending` | string / bool | Método de ordenação + ordem |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | Organização por imagem |
| `thumbnail_size` / `tile_padding` | int | Configuração da grade |
| `navigation_auto_loop` | bool | Loop nos extremos da pasta |
| `keyboard_shortcuts` | dict | Vinculações de tecla customizadas |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | Persistência de layout |
| `stack_raw_jpeg_pairs` | bool | Toggle de empilhamento RAW+JPEG |
| `external_editors` | list | Editores configurados |
| `macros` / `macro_last_name` | list / string | Macros salvos + alvo do Alt+M |
| `puppet_tab_enabled` / `desktop_pet_tab_enabled` | bool | Abas opcionais (ligadas por padrão; aplicado na próxima inicialização) |

---

## Arquitetura

```
Imervue/
├── __main__.py              # Ponto de entrada da aplicação
├── cli.py                   # CLI de lote sem interface (sem Qt)
├── Imervue_main_window.py   # Janela principal (QMainWindow) — monta as 5 abas
├── gpu_image_view/          # ABA IMERVUE — visualizador GPU, zoom profundo, mural de ladrilhos
│   ├── actions/             #   ações do visualizador (excluir / selecionar / comparar / slideshow)
│   └── images/              #   camada de carga (workers de decodificação, varredura de pasta, pré-carga)
├── gui/                     # Cascas Qt — diálogos, painéis laterais, painel de revelação, telas
├── paint/                   # ABA PAINT — editor raster completo
│   ├── docks/               #   painéis dock (cor / pincel / camada / material / …)
│   └── tools/               #   manipuladores de ferramentas de ponteiro
├── puppet/                  # ABA PUPPET — animador 2D com rig + interoperabilidade Cubism
├── desktop_pet/             # ABA DESKTOP PET — sobreposição sem moldura + drivers e hooks
├── image/                   # Núcleo de imagem puro (sem Qt) — pipeline de recipe, filtros, codecs,
│                            #   pirâmide / gerenciador de ladrilhos, XMP, pHash, metadados
├── library/                 # Índice SQLite da biblioteca, álbuns inteligentes, busca CLIP, triagem
├── export/                  # Geradores de exportação (folha de contato, galeria web, MP4, colinha)
├── macros/                  # Gravação / reprodução de macros
├── menu/                    # Definições de menu (file / tools / filter / clique direito / …)
├── mcp_server/              # Servidor stdio do Model Context Protocol
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko) + validação
├── external/                # Integração com editores externos
├── plugin/                  # Sistema de plugins (base / manager / downloader / instalador pip)
├── sessions/                # Serialização de sessão e workspace + migração
├── system/                  # Integração com o SO — temas, escala de UI, associação de arquivos,
│                            #   monitor de área de transferência, observador de árvore, lixeira em lote, logging
└── user_settings/           # Configuração multiperfil persistente, tags, avaliações, favoritos
```

Duas regras valem em toda a árvore:

- **A lógica pura é separada do Qt.** Uma ferramenta de imagem única normalmente é `image/<feature>.py` (NumPy / Pillow, importável de uma thread de trabalho ou de um teste sem display) mais `gui/<feature>_dialog.py` (a casca Qt) e uma entrada em `menu/extra_tools_menu.py`.
- **Classes Qt grandes delegam.** `GPUImageView`, `PetWindow` e `PaintWorkspace` mantêm apenas as sobrescritas de eventos e o ciclo de vida; o comportamento vive em colaboradores nomeados (`InputController`, `OverlayPainter`, `PetInteraction`, `ToolDispatcher`, …), cuja matemática é novamente extraída para módulos puros testáveis sem contexto GL.

### Pipeline de renderização (aba Imervue)

1. `GPUImageView` estende `QOpenGLWidget`
2. Dois programas GLSL 1.20 (quads texturizados + retângulos de cor sólida)
3. Cache LRU de texturas — limite flexível de 256 ladrilhos (teto rígido 512); orçamento de VRAM sondado do driver GL, recuo para 1,5 GB, substituível pelo usuário
4. Pirâmide de tiles multinível construída com LANCZOS em tamanho de tile 512 × 512
5. Filtragem anisotrópica até 8× quando o hardware suporta
6. Fallback de renderização por software se a compilação de shader falhar

### Cache de miniaturas

- **Chave**: MD5 de `{path}|{mtime_ns}|{file_size}|{thumbnail_size}|{recipe_hash}` — o hash do recipe é o que faz uma edição de revelação aparecer na miniatura sem invalidar todas as outras entradas
- **Formato**: PNG comprimido (`compress_level=1` — escrita rápida, footprint pequeno)
- **Local**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) ou `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidação**: Automática quando os metadados do arquivo mudam

### Renderização do Puppet (aba Puppet)

- `QOpenGLWidget` com `glDrawElements` + vertex arrays client-side
- Por drawable: vértices rest cacheados como numpy float32; vertex morphs vetorizados; ordenação topológica de deformers içada para fora do loop por drawable
- O fundo de transparência é uma textura 2×2 em GL_REPEAT-tiled (eram 100k+ quads em immediate-mode antes da otimização)
- O conversor Cubism produz curvas opacity_keys junto com deltas de vertex-morph, para que transições de visibilidade dirigidas por parâmetro sobrevivam à conversão `.moc3 → .puppet`

---

## Licença

Este projeto é licenciado sob a [MIT License](../LICENSE).

Copyright (c) 2026 JE-Chen
