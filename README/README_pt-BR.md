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
| rawpy | Decodificação de imagens RAW |
| imageio | I/O de imagens |
| imageio-ffmpeg | Exportação MP4 de slideshow (H.264 via ffmpeg) |
| defusedxml | Parsing XML seguro (sidecars XMP) |

Opcionais (com feature gating; omita para desativar o recurso sem erros):

| Pacote | Finalidade |
|---------|---------|
| open_clip_torch + torch | Busca semântica CLIP (consultas em linguagem natural) |
| onnxruntime | Upscale por IA Real-ESRGAN / auto-tag CLIP ONNX |
| opencv-python | Composição HDR, costura de panorama, focus stacking, detecção facial, pincel de cura |
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

---

## Imervue — Visualizador de imagens e biblioteca

A aba **Imervue** é a tela inicial padrão. Combina o visualizador de imagens com árvore de pastas, painel lateral EXIF e ferramentas de biblioteca/organização.

### Visualizador

- **Renderização acelerada por GPU** via OpenGL (shaders GLSL 1.20 com VBO)
- **Pirâmide deep-zoom** — tiles multinível em 512×512 com reamostragem LANCZOS, cache LRU de até 256 tiles / orçamento de 1,5 GB de VRAM, filtragem anisotrópica até 8×
- **Carregamento assíncrono** — decodificação multi-thread com prefetch de ±3 imagens
- **Grade virtualizada de miniaturas** — apenas tiles visíveis são renderizados; o tamanho das miniaturas é configurável (128 / 256 / 512 / 1024 / auto)
- **Cache em disco** — miniaturas PNG comprimidas com invalidação baseada em MD5 em `%LOCALAPPDATA%/Imervue/cache/thumbnails` (ou `~/.cache/imervue/thumbnails`)
- **Reprodução de animação** — GIF / APNG com controles de play / pause / passo por quadro / velocidade

### Modos de navegação

- **Grade** (padrão) — grade de tiles virtualizada com popup de pré-visualização ao passar o mouse (atraso de 500 ms)
- **Lista (detalhe)** — alternar com `Ctrl+L`; colunas: Preview · Etiqueta · Nome · Resolução · Tamanho · Tipo · Modificação
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
- Vista de pixel (`Shift+P`) — zoom ≥ 400 % mostra grade de pixels + RGB / HEX por pixel
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
- **Avaliações** — 0 a 5 estrelas (`1`–`5`) + coração de favorito (`0`)
- **Etiquetas de cor** — bandeiras vermelho/amarelo/verde/azul/roxo (`F1`–`F5`)
- **Triagem (Culling)** — flag de 3 estados compatível com outros gerenciadores de fotos XMP-aware (`P` = manter, `Shift+X` = rejeitar, `U` = remover marca); filtrar por estado; exclusão em lote de rejeitados; a triagem automática escolhe o quadro mais nítido de cada grupo de quase duplicatas e rejeita os demais
- **Tags hierárquicas** — caminhos em árvore como `animal/cat/british`; descendentes são correspondidos automaticamente
- **Tags & Albums** com filtragem multi-tag AND/OR
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

- Ordenar por nome / modificação / criação / tamanho / resolução (asc ou desc)
- Filtrar por extensão, etiqueta de cor, avaliação, tag/álbum, estado de triagem
- **Filtro avançado** — resolução / tamanho de arquivo / orientação / intervalo de data de modificação
- Diálogo de **filtro multi-tag** com lógica booleana AND / OR

### Busca

- **Busca fuzzy por nome de arquivo** com destaque de substring
- **Buscar Imagens Similares** — pHash (DCT 64 bits) com distância de Hamming ajustável
- **Library Search** — índice multi-raiz SQLite com uma DSL de consulta compacta: palavras-chave, tags (incl. negação), avaliações, cor, extensão, lugar, triagem, favoritos, proporção, idade, tamanho, dimensões, câmera / lente e regex / glob de nome de arquivo
- **Find Similar (average hash)** — pHash e dHash são acompanhados por um average-hash (aHash) opcional para uma métrica complementar de quase duplicatas
- **Busca Semântica (CLIP)** — consultas em linguagem natural ("golden retriever na neve") via embeddings em cache; degrada graciosamente quando `open_clip_torch` + `torch` não estão instalados
- **Auto-Tag** — classificação heurística com upgrade opcional CLIP ONNX

### Metadados

- **Painel lateral EXIF** com grupos colapsáveis + faixa inline de 0-5 estrelas
- Diálogo de **editor EXIF**
- **Editor de palavras-chave** — título / autor / descrição / palavras-chave, com **sugestões de tags relacionadas** extraídas da coocorrência de tags e expansão de vocabulário controlado (uma palavra-chave folha aplica automaticamente seus ancestrais + sinônimos de um vocabulário hierárquico editável)
- Diálogo de **informações da imagem** (dimensões / tamanho / datas)
- **Sidecars XMP** (`.xmp` companheiros) — avaliação / título / descrição / palavras-chave / etiqueta de cor com round-trip para interoperabilidade com outros gerenciadores XMP-aware (XML seguro via `defusedxml`)
- **Editor de Geotag GPS** — lê GPS EXIF existente, escreve nova lat/lon via piexif (JPEG)
- **Token Batch Rename** — templates com preview ao vivo como `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata CSV / JSON** — uma linha por imagem incluindo triagem / avaliação / tags / notas

### Ferramentas extras (aba Imervue — processamento em lote)

Acessadas a partir do menu **Tools**; organizadas em submenus agrupados por função:

- **Batch** — Conversão de formato · Remoção EXIF · Sanitizador de imagens (re-renderizar para remover dados ocultos) · Organizador de imagens (ordenar em subpastas por data / resolução / tipo / tamanho) · Token Batch Rename
- **AI / Heurístico** — AI Image Upscale (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Encontrar imagens duplicadas · Encontrar imagens similares · Auto-Tag · Detecção facial (Haar cascade)
- **Library & Metadata** — Library Search · Smart Albums · Tags hierárquicas · Exportar metadados · Sidecars XMP · Geotag GPS

### Integração com o sistema

- Menu de contexto do botão direito do Windows **Abrir com Imervue** (associação de arquivos baseada em registro)
- Monitoramento de pasta com `QFileSystemWatcher` (atualização automática em mudanças)
- Sistema de notificações toast (info / sucesso / aviso / erro)
- Sistema de plugins com downloader online (ver [Sistema de plugins](#sistema-de-plugins))

---

## Modify — Revelação não destrutiva

A aba **Modify** é a estação de revelação. Toda alteração vive em uma **recipe** por imagem armazenada ao lado do arquivo — os pixels originais em disco nunca são sobrescritos até você **Exportar** ou usar **Salvar Como** explicitamente.

### Sliders de revelação

- Balanço de branco — temperatura / matiz
- Regiões tonais — sombras / meios-tons / realces
- Exposição / contraste / saturação / vibrância
- Recorte, rotação, espelhamento horizontal / vertical
- Todas as edições permanecem não destrutivas e fazem round-trip pelo armazenamento de recipes

### Curvas e LUTs

- **Editor de curva tonal** — curva RGB arrastável mais R / G / B por canal com interpolação cubic monotônica
- **Aplicar LUT .cube** — carrega qualquer LUT 3D Adobe (até 64³), interpola trilinearmente, mistura com slider de intensidade
- **Split Toning** — matiz + saturação de sombras / realces baseado em flags com pivô de balanço

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
- **Presets de revelação** — salve uma recipe e depois aplique-a por inteiro ou mescle apenas seus ajustes ativos sobre outras imagens (preservando o recorte próprio de cada imagem, etc.)

### Ajustes locais

- **Máscaras de pincel / radial / gradiente linear** com deltas por máscara de exposição / brilho / contraste / saturação / balanço de branco + slider de feathering
- Máscaras se mesclam não destrutivamente através do pipeline de revelação

### Retoque e transformação

- **Pincel de cura** — manchas circulares, inpainting OpenCV (Telea ou Navier-Stokes)
- **Carimbo de clonagem** — Shift+clique na fonte, blit com feathering no destino
- **Recorte / Endireitar** — retângulo de recorte normalizado mais endireitamento em ângulo arbitrário com auto-recorte para o maior retângulo interno
- **Auto-endireitar** — detecção de horizonte / vertical por linha de Hough
- **Correção de lente** — distorção radial em puro numpy (barrel / pincushion), elevação de vinheta, aberração cromática por canal
- **Redução de ruído / Sharpening** — denoise bilateral que preserva bordas + sharpening unsharp-mask
- **Céu / Plano de fundo** — substitui céu detectado por gradiente ou remove o plano de fundo (preenchimento transparente ou branco); upgrade opcional `rembg` / U²-Net

### Multi-imagem

- **Composição HDR** — combina exposições com bracket via fusão Mertens do OpenCV (com pré-alinhamento AlignMTB)
- **Costura de Panorama** — `Stitcher` do OpenCV em modo panorama ou scans, auto-recorte de bordas pretas
- **Focus Stacking** — mapa de foco por variância Laplaciana + blend Gaussiano com alinhamento ECC opcional

### Saída

- **Sobreposição de marca d'água** — texto ou imagem, 9 posições de âncora, opacidade, escala; aplicado apenas na exportação
- **Presets de exportação** — pipelines de um clique Web 1600 / Print 300 dpi / Instagram 1080
- **Salvar Como / Exportar** — PNG / JPEG / WebP / BMP / TIFF com slider de qualidade para formatos com perdas
- **Operações em lote** — renomear, mover/copiar, rotacionar imagens selecionadas
- **PDF de Contact Sheet** — grade em várias páginas com legendas (A4 / A3 / Letter / Legal)
- **HTML de Galeria Web** — pasta autocontida com `index.html` + miniaturas JPEG + lightbox embutido
- **Slideshow MP4** — vídeo H.264 com FPS / tempo por imagem / transições de fade / dissolução / slide / wipe configuráveis (`imageio-ffmpeg`)
- **Print Layout** — folha PDF em várias páginas com tamanho / orientação / grade / margens / sangria / marcas de corte configuráveis
- **Soft Proof** — carrega um perfil ICC, simula o gamut de destino, destaca pixels fora do gamut em magenta
- **Cópias Virtuais** — snapshots de recipe nomeados por imagem; alterne entre visuais sem perder o mestre

### Editores externos

Registre programas (seu editor de imagem / … / …) em **File > External Editors…** e abra-os com a imagem atual via **File > Open in External Editor**.

---

## Paint — editor raster completo

A aba **Paint** é um estúdio raster completo embutido como seu próprio `QMainWindow` com menus, faixa de ferramentas à esquerda, barra de opções sensível ao contexto e uma coluna de docks com abas à direita. Edição de documentos multi-aba — abra muitos desenhos ao mesmo tempo, cada um com sua própria pilha de undo.

### Ferramentas (27)

Pincel · Borracha · Preenchimento · Conta-gotas · Retângulo / Laço / Varinha / Seleção Rápida · Mover · Texto · Gradiente · Desfocar · Smudge · Dodge · Burn · Sponge · Caneta · Carimbo de Clonagem · Balão de Fala · Retângulo · Elipse · Linha · Polígono · Recorte · Transformar · Mão · Zoom

O trio de tonalização de câmara escura — **Dodge** (clarear), **Burn** (escurecer) e **Sponge** (saturar / dessaturar) — pinta ajustes locais de tom e croma, ponderados pelo pincel e por uma máscara de sombras / meios-tons / realces.

Atalhos de tecla única: `B / E / G / I / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` para variantes de forma.

### Pincéis

Caneta / marcador / lápis / marca-texto / spray / caligrafia / aquarela / carvão / giz de cera, com controles de Tamanho / Opacidade / Dureza / Densidade / Modo de mesclagem. Editor de curva de pressão, captura de ponta de pincel a partir de seleção, importar / exportar presets de pincel.

### Camadas

Painel completo de camadas com miniaturas, alternância de visibilidade, arrastar-para-reordenar, modos de mesclagem, opacidade, busca, camadas vetoriais, camadas 1-bit, **máscaras de camada** (adicionar / a partir da seleção / inverter / aplicar), **clipping masks**, **efeitos de camada** (sombra projetada / brilho externo / contorno). Dividir camada por cor, presets de mapeamento de gradiente.

### Seleção

Retângulo / Laço / Varinha / Seleção Rápida com modos **Substituir / Adicionar / Subtrair / Interseção** e Feathering. **Modo Quick Mask** (`Q`) para fluxos de pintar-a-máscara. Diálogo **Stroke Selection**.

### Animação e mangá

- **Animação** — dock de timeline de frames com snapshots, reprodução, overlay onion-skin, exportação MP4 / GIF
- **Ferramentas de mangá** — Panel Cutter · Camadas de retícula · Carimbar números de página · Speedlines (Radial / Paralelo / Burst) · Action Flash · ferramenta de Balão de Fala

### Filtros e auxiliares de visualização

- **Filtros** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone (cada um com diálogo de preview ao vivo)
- **Auxiliares de visualização** — Grade de Pixels · Snap to Pixel · Snap to Edges · Onion Skin · Guias de Sangria · Rotação de Canvas (`Ctrl+Shift+H` gira CCW)

### Docks (10, em abas)

Cor · Pincel · Camada · Navegador · Biblioteca de materiais · Histórico · Amostras · Referência · Histograma · Animação. Cada dock é movível / flutuável. **Settings > Workspace Layouts** salva e recupera arranjos nomeados.

### I/O de arquivos

- Abrir / salvar **PSD** (Photoshop) com round-trip completo de camadas
- Exportar PNG / JPEG / WebP, mais exportação de quadrinho multipágina para **CBZ** ou **PDF**
- Snapshots de autosave com recuperar-mais-recente

### UX para usuários avançados

- **Tab** alterna todos os docks para pintura sem distração
- `Ctrl+Tab` cicla pelas abas
- `,` / `.` cicla pelos tipos de pincel
- `0`-`9` definem opacidade do pincel em passos de 10 %
- `Alt+[` / `Alt+]` movem a camada ativa
- Clique direito no canvas abre menu rápido de Undo / Redo / Selecionar tudo / Desmarcar / Ajustar / 100 %
- Asterisco de modificação por aba, confirmações toast de undo / redo, prompt de recuperação de autosave na inicialização

Pressione `E` a partir do Deep Zoom para enviar a imagem atual direto para uma nova aba Paint.

---

## Puppet — animação 2D com rigging

A aba **Puppet** é um sistema de animação 2D de marionetes com rigging feito do zero. Faz o que o Live2D faz (rigs com deformação de malha, parâmetros, motions, física, expressões, pose, sincronia labial, rastreamento facial por webcam) mas **sem SDK proprietário**, **sem `live2d-py`**, e com um formato de arquivo `.puppet` totalmente aberto, documentado em `Imervue/puppet/FORMAT.md`.

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

Baseado em JSON, diff-friendly por humanos, sem binário proprietário.

### Renderizador

`QOpenGLWidget` com desenho de triângulos texturizados em vertex-array em draw_order, modos de mesclagem por drawable (normal / additive / multiply), exclusividade de pose-group, projeção ortográfica em image-space, fundo de xadrez de transparência em GL_REPEAT-tiled, zoom com roda + pan com arrasto do botão do meio. Otimizado para rigs grandes — March 7th (307 drawables / 2965 vertex morphs) roda a 60 FPS em CPU.

### Autoria

- **Importar PNG** → gera automaticamente uma malha de grade triangulada que respeita o alpha
- Ações de toolbar **Add Rotation Deformer** (anchor + ângulo) / **Add Warp Deformer** (lattice bezier de rows × cols)
- **Add Parameter** → defina formas-chave nos extremos do slider via **Set Key** no dock de parâmetros
- **Editor de malha** — alterne Edit Mesh para arrastar vértices; cliques dentro de 8 px se ajustam ao mais próximo
- **Save As…** grava o rig inteiro em um zip `.puppet`

### Runtime

- **Rig de parâmetros** — cada parâmetro mantém uma lista de chaves mapeando um valor de slider para um snapshot parcial de forma de deformer; o runtime amostra e faz lerp campo a campo
- **Reprodução de motion** — dock inferior com lista de motions + Play / Pause / Stop / Loop / scrub; o amostrador de curvas honra segmentos `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` (resolução de tempo → param por iteração de Newton); fade-in / fade-out por motion
- **Expressões** — pilha de sobreposições de parâmetros `additive` / `multiply` / `overwrite`
- **Pose groups** — visibilidade mutuamente exclusiva de drawables (trocas de arma, variantes de formato de boca)
- **Física** — cadeias de pêndulo Verlet para cabelo / pano / fitas; param de entrada move a âncora da cadeia, gravidade + amortecimento + molas por partícula puxam de volta ao repouso
- **Vertex morphs** — blend linear estilo Cubism entre rest e ±deltas extremos; numpy vetorizado por frame a 60 FPS
- **Opacity keys** — curvas de alpha dirigidas por parâmetro; permite que malhas de pose alternativa façam fade-in / fade-out conforme um parâmetro de gesto dispara

### Entrada ao vivo

- Arrasto do cursor → parâmetros de ângulo da cabeça
- Auto-piscar em uma curva cosseno open → close → open
- Sincronia labial por microfone via `sounddevice` RMS → `ParamMouthOpenY` (dep opcional)
- Rastreamento facial por webcam via OpenCV + MediaPipe FaceMesh → yaw / pitch / roll da cabeça + abertura de olho / boca (deps opcionais)
- Gravação de motion customizado — captura valores de parâmetros a 30 Hz enquanto você balança sliders / encara a webcam / deixa a física rodar; bake em Motion de segmentos lineares pronto para reproduzir / loopar / salvar

### Interop com Cubism

O **Cubism Native SDK** pode ser plugado (DLL fornecida pelo usuário — a Free Material License do Live2D proíbe a redistribuição) para converter qualquer modelo `.moc3` em um zip `.puppet`. O conversor executa uma varredura sample-and-reconstruct que captura tanto deltas de vertex-morph quanto transições de visibilidade dirigidas por parâmetro, de modo que toggles de gesto (sinal de paz / cobrir o rosto / foto …) sobrevivem à conversão intactos.

### Saída

- **Capture frame…** salva um PNG do canvas atual via `glReadPixels`
- **Record…** alterna um loop de frames de 30 FPS para GIF / WebM / MP4 via `imageio`
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

Imervue limita o lado mais longo da saída de streaming em 1080 px para que canvases nativos do Cubism (March 7th é 3503×7777) não sejam rejeitados pelo driver de câmera virtual DirectShow. A proporção é preservada; o OBS pode escalar mais se necessário.

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

Um rig pronto está em [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — um personagem Cubism Live2D de 307 drawables convertido no próprio repositório. Abra via **Open Puppet…** para ver o rig surgir centralizado; clique em qualquer um dos 18 motions (grupo Idle + grupo Gesture) para reproduzir. Os gestos cobrem sinal de paz, cobrir o rosto, foto, blush, rosto escuro, choro, suor, estrelas, estrela cadente — todos os gestos nomeados que o rig define.

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
| Pausa quando oculto | O pet para de animar enquanto está invisível — zero CPU fora da tela. |
| Presets de tamanho | Pequeno / médio / grande. Redimensiona ao redor do centro, para que o pet não salte pela tela. |
| Slider de opacidade | Faz o pet desbotar de 10% a 100%, para que possa ser um enfeite sutil da área de trabalho. |
| Lembra onde você colocou | Arraste o pet para o seu canto favorito; ele volta para lá no próximo lançamento. |

### Interações de clique

- **Clique esquerdo no corpo** — se o rig definir uma hit area (ex.: tocar na cabeça), o motion correspondente é reproduzido. Caso contrário, o pet te cumprimenta com um balão de fala.
- **Clique direito em qualquer lugar** — abre um menu de contexto com: Esconder pet, Live drivers, Play motion (lista de todos os motions do rig), Apply expression, Travar posição, Click-through, Sempre no fundo, Esconder em tela cheia, Balão de fala, Tamanho.
- **Ícone da bandeja do sistema** — clique esquerdo alterna a visibilidade, clique direito traz Mostrar/Esconder, Click-through, Abrir puppet, Esconder pet.

### Drivers ao vivo

Escolha qualquer combinação na aba ou no menu de clique direito. Cada um vem desligado por padrão — ative apenas o que você quiser.

- **Auto idle** — respiração + drift sutil para o personagem se sentir vivo.
- **Idle motions** — cicla aleatoriamente pelos motions do grupo idle do rig.
- **Auto-blink** — ciclo natural de fechar os olhos a cada poucos segundos.
- **Drag-track head** — a cabeça gira para acompanhar o cursor.
- **Sincronia labial por microfone** — a boca abre com a sua voz (precisa de `sounddevice`).
- **Rastreamento por webcam** — sua cabeça / olhos / boca comandam os do puppet (precisa de `opencv-python` e `mediapipe`).

### Como começar

1. Mude para a aba **Desktop Pet**.
2. Clique em **Load bundled March 7th** para usar o personagem incluído, ou em **Open Puppet…** para escolher seu próprio arquivo `.puppet`.
3. Marque **Show pet on desktop**.
4. Arraste o personagem para onde quiser; escolha os drivers desejados; ajuste opacidade / tamanho.
5. Clique direito a qualquer momento para o menu de ação rápida, ou use o ícone da bandeja do sistema para esconder o pet sem precisar achar a aba.

Tudo o que você configura — posição, drivers, opacidade, click-through, tamanho — é lembrado entre lançamentos.

---

## Atalhos de teclado e mouse

### Navegação (todos os modos)

| Atalho | Ação |
|----------|--------|
| Teclas de seta | Rolar grade / Trocar imagens (Esquerda/Direita em deep zoom) |
| Shift + Seta | Rolagem fina (meio passo) |
| Ctrl+Shift+←/→ | Ir para a pasta irmã anterior / próxima com imagens |
| Alt+← / Alt+→ | Voltar / avançar no histórico |
| Ctrl+G | Ir para imagem por índice |
| X | Saltar para uma imagem aleatória |
| Home | Resetar zoom e pan para a origem |
| Ctrl+F ou / | Abrir diálogo de busca fuzzy |
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
| E | Abrir editor de imagem (aba Modify) |
| W / Shift+W | Ajustar à largura / altura |
| H | Alternar overlay de histograma RGB |
| F8 / Ctrl+F8 | Overlay OSD / HUD de depuração |
| Shift+P | Alternar vista de pixel (zoom ≥ 400 % mostra grade + RGB) |
| Shift+M | Ciclar modos de cor (Normal / Tons de Cinza / Invertido / Sépia) |
| B | Alternar favorito |
| Ctrl+C / Ctrl+V | Copiar / colar imagem do/para o clipboard |
| 0 / 1-5 | Alternar favorito / avaliação rápida |
| F1-F5 | Etiqueta de cor rápida (vermelho / amarelo / verde / azul / roxo) |
| P / Shift+X / U | Triagem: Manter / Rejeitar / Remover marca |
| Shift+S | Vista dividida |
| Shift+D / Ctrl+Shift+D | Página dupla (LTR / RTL) |
| Ctrl+Shift+M | Janela de espelhamento multi-monitor |
| Delete | Mover para lixeira (com undo) |
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
| V / T / U / R | Mover / Texto / Gradiente / Seleção retangular |
| P / S / C / Z / H | Caneta / Smudge / Clone / Zoom / Mão |
| Q | Alternar Modo Quick Mask |
| Tab | Alternar todos os docks |
| Ctrl+Tab | Ciclar abas Paint |
| , / . | Ciclar tipos de pincel |
| 0-9 | Opacidade do pincel em passos de 10% |
| Alt+[ / Alt+] | Mover camada ativa para baixo / cima |

---

## Estrutura de menus

### File

- New Window
- Open Image / Open Folder
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

- **Batch** — Conversão de formato · Remoção EXIF · Sanitizador de imagens · Organizador de imagens · Token Batch Rename
- **Library & Metadata** — Library Search · Smart Albums · Encontrar similares / duplicadas · Auto-Tag · Tags hierárquicas · Exportar metadados · Sidecars XMP · Geotag GPS
- **Views** — Timeline · Calendar · Map
- **Workflow** — Triagem · Staging Tray · Cópias Virtuais · Gerenciador de arquivos de painel duplo · Macros
- **Export** — PDF de Contact Sheet · Galeria Web · Vídeo Slideshow (MP4) · Print Layout
- **Develop (Non-Destructive)** — Curva tonal · LUT .cube · Split Toning · Máscaras de ajuste local · Graduated Density · Velvia · Emboss · Defringe · Film Negative · Filmic Tone Map · Tone / Detail Equalizer · Polar · Kaleidoscope · Frosted Glass · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Redução de ruído / Sharpening · Pincel de cura · Carimbo de clonagem · Detecção facial · Céu / Plano de fundo · Recorte / Endireitar · Auto-endireitar · Correção de lente
- **Multi-Image** — Composição HDR · Costura de Panorama · Focus Stacking

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
| `on_plugin_unloaded()` | No encerramento do app |
| `on_build_menu_bar(menu_bar)` | Depois que a barra de menus padrão é construída |
| `on_build_main_tabs(tabs)` | Depois que as quatro abas embutidas são adicionadas |
| `on_build_context_menu(menu, viewer)` | Quando o menu de clique direito é aberto |
| `on_image_loaded(path, viewer)` | Após a imagem carregar em deep zoom |
| `on_folder_opened(path, images, viewer)` | Após a pasta abrir na grade |
| `on_image_switched(path, viewer)` | Ao navegar entre imagens |
| `on_image_deleted(paths, viewer)` | Após imagens serem soft-deletadas |
| `on_key_press(key, modifiers, viewer)` | Ao pressionar tecla (retorne True para consumir) |
| `on_app_closing(main_window)` | Antes de a aplicação fechar |
| `get_translations()` | Fornecer strings i18n |

### Downloader de plugins

**Plugins > Download Plugins** abre o downloader online. Repositório-fonte: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## Servidor MCP

Imervue traz um servidor [Model Context Protocol](https://modelcontextprotocol.io) embutido para que assistentes de IA (Claude Code / Desktop, Cursor, Cline, …) possam chamar os helpers de lógica pura do projeto sem uma GUI rodando. Sem dependência de Qt; um único comando:

```sh
python -m Imervue.mcp_server
```

### Ferramentas

Ferramentas selecionadas (41 no total — lista completa na documentação). Toda
ferramenta anuncia um `outputSchema` JSON e `annotations` de somente-leitura /
destrutivas, retorna seu resultado como `structuredContent` e ferramentas de
longa duração transmitem `notifications/progress`.

| Ferramenta | Finalidade |
|------|---------|
| `list_images` | Listar arquivos de imagem em uma pasta (recursivo opcional) |
| `read_image_metadata` / `read_xmp_tags` | Dimensões, formato, EXIF, sidecar XMP (avaliação, etiqueta, palavras-chave) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | Análise sem referência: estatísticas por canal, colorfulness/entropia/contraste, histograma + clipping, pontuação de desfoque |
| `image_thumbnail` / `ocr_text` / `find_similar` | Prévia em base64, texto via Tesseract, grupos de quase duplicatas por hash perceptual (com progresso) |
| `convert_format` | Converter entre PNG / JPEG / WebP / TIFF / BMP (+ HEIC / AVIF / JXL opcionais) |
| `apply_watermark` / `apply_frame` | Gravar uma marca d'água de texto ou uma moldura passe-partout / Polaroid + legenda |
| `build_collage` | Compor imagens em uma montagem em grade (com progresso) |
| `crop_image` / `resize_image` / `rotate_image` | Recorte por pixel, redimensionamento preservando proporção, rotação / espelhamento sem perdas |
| `collection_stats` | Resumo de avaliação / favorito / etiqueta de cor / triagem da pasta |
| `search_images` | Filtra uma pasta com a DSL de consulta dos smart albums (caminho / EXIF / tamanho / dimensões) |
| `extract_gps` / `dominant_colors` | Lê coordenadas GPS do EXIF (encadeia com `reverse_geocode`); paleta de cores por median-cut (rgb / hex / proporção) |
| `error_level_analysis` | Mapa de adulteração por recompressão JPEG como um PNG data URI |
| `solarize_image` / `glow_image` | Aplica uma inversão tonal solarize ou um brilho difuso e salva |
| `velvia_image` / `emboss_image` / `defringe_image` | Boost de saturação Velvia, emboss de luz direcional, dessaturação de franjas de borda |
| `film_negative_image` / `graduated_density_image` | Inverte um negativo escaneado; aplica um gradiente de densidade graduada linear |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Rolloff filmic de realces; exposição por zona; contraste por banda |
| `colormap_image` / `false_color_image` | Recolorir a luminância por um mapa viridis/magma/jet; escala de exposição em falsas cores |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Pontilhado Bayer ordenado; split-toning de sombras/luzes; ordenação de pixels por faixa de brilho |
| `reverse_geocode` / `extract_video_frame` | GPS → cidade offline, decodificar um frame de vídeo em imagem estática |
| `puppet_from_png` / `puppet_inspect` | Construir um rig `.puppet` a partir de um PNG; abrir um e retornar seu inventário |

### Prompts

Quatro prompts reutilizáveis: `caption_image`, `suggest_edits`, `analyze_composition`
(crítica de composição guiada por saliência) e `flag_issues` (triagem de nitidez +
qualidade + clipping). Os argumentos dos prompts podem ser completados via
`completion/complete`.

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

Plugins podem registrar idiomas inteiramente novos via `language_wrapper.register_language()`, ou contribuir traduções via `get_translations()`. Veja [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## Configurações do usuário

Armazenadas em `user_setting.json` no diretório de trabalho. Entradas principais:

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

---

## Arquitetura

```
Imervue/
├── __main__.py              # Ponto de entrada da aplicação
├── Imervue_main_window.py   # Janela principal (QMainWindow) — monta as 4 abas
├── gpu_image_view/          # ABA IMERVUE — viewer GPU + deep zoom
├── gui/                     # Diálogos e painéis laterais (revelação, EXIF, etc.)
├── paint/                   # ABA PAINT — editor raster completo
├── puppet/                  # ABA PUPPET — animador 2D de marionetes com rigging
├── export/                  # Geradores de exportação (contact sheet, galeria web, MP4)
├── image/                   # Utilidades de imagem (pirâmide, gerente de tiles, info)
├── library/                 # Helpers de biblioteca (stacks RAW+JPEG, indexação)
├── macros/                  # Gravação / reprodução de macros
├── menu/                    # Definições de menu (file / tools / filter / …)
├── mcp_server/              # Servidor stdio do Model Context Protocol
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # Integração de editor externo
├── plugin/                  # Sistema de plugins (base / manager / downloader)
├── sessions/                # Serialização de workspace
├── system/                  # Associação de arquivos do Windows
└── user_settings/           # Configuração persistente do usuário
```

### Pipeline de renderização (aba Imervue)

1. `GPUImageView` estende `QOpenGLWidget`
2. Dois programas GLSL 1.20 (quads texturizados + retângulos de cor sólida)
3. Cache LRU de texturas — limite de 256 tiles, orçamento de 1,5 GB de VRAM
4. Pirâmide de tiles multinível construída com LANCZOS em tamanho de tile 512 × 512
5. Filtragem anisotrópica até 8× quando o hardware suporta
6. Fallback de renderização por software se a compilação de shader falhar

### Cache de miniaturas

- **Chave**: MD5 de `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
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
