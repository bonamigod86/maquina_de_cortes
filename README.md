# Máquina de Cortes (ClipForge Local)

Aplicação **local** que transforma vídeos longos em cortes verticais prontos para TikTok, Reels e Shorts — com transcrição por IA, seleção inteligente de trechos, legendas animadas e reenquadramento que segue o rosto.

Tudo roda na sua máquina: sem upload para nuvem, sem custo por vídeo.

---

## ✨ Funcionalidades

- **Importação de vídeos**
  - Upload de arquivo local (MP4, MOV, MKV, AVI, WebM, M4V, FLV, WMV, TS) via arrastar-e-soltar.
  - Importação por **link** (YouTube, Twitch, Kick e outros suportados pelo `yt-dlp`), com escolha de **qualidade** (360p/720p/1080p/Original) e plataforma.
- **Pipeline automático de cortes**
  1. Extração de áudio (WAV 16 kHz).
  2. Transcrição com **Whisper** (`faster-whisper`), com modelos de `tiny` a `large-v3`.
  3. Análise de **cenas, silêncios e energia** (PySceneDetect).
  4. IA **entende o conteúdo** (Ollama / OpenAI-compatível / modo heurístico offline).
  5. Geração de **cortes inteligentes** (15, 30, 45 ou 60 s) nos momentos mais relevantes.
  6. Geração de títulos e textos para postagem.
  7. Renderização dos cortes com legendas.
- **Reenquadramento 9:16 (1080×1920)**
  - **Detecção de rosto** (YOLOv8-face / ONNX Runtime) com suavização — o corte segue o rosto.
  - Fallback para recorte centralizado quando não há rosto.
- **Legendas animadas**
  - Estilos prontos: **TikTok**, **Instagram**, **Minimalista**, **Palavra por palavra** e **Karaokê**.
  - Animações: `pop`, `fade`, `word_pop`, `karaoke` ou nenhuma.
  - Configurável: fonte, tamanho, cor, contorno, sombra, posição e **palavras por linha**.
  - Exportação de legendas **SRT / VTT / TXT**.
- **Editor de cortes**
  - Dividir e mesclar cortes, editar textos, **regenerar títulos** com IA.
  - Aplicar um **template visual** ao corte (botão **Template** → escolha na galeria).
  - Avaliar cortes (👍/👎) para o app aprender suas preferências.
  - Timeline visual com miniaturas.
  - Linha do tempo do vídeo original: barras **roxas** no topo = energia da fala de cada frase (a altura indica a ênfase da voz); faixa inferior com barras **verdes** = cortes gerados (a barra **roxa** = corte selecionado); faixas **vermelhas** = silêncios; **azul-céu** = cenas; a linha **branca** é a posição atual de reprodução.
- **Identidade visual (Brand Kit)**
  - Upload da **logo** da marca, ativar "Usar logo no vídeo" e escolher a posição (canto superior/inferior).
  - Cores **primária** e **secundária**, e opção de usar a **fonte da marca** nas legendas.
- **Templates de corte**
  - **Galeria** com filtros (Todos / Galeria / Meus) e busca; aplica um template ao corte com 1 clique (botão **Template** no editor).
  - **8 templates built-in**: Podcast Clássico, Feed da Fofoca, Breaking News, Gaming Highlights, Minimalista Clean, Toguro Style, Interview e Quiz/Enigma.
  - **Editor visual WYSIWYG**: canvas 9:16 com arrastar/redimensionar (sem dependências), elementos de texto, forma, vídeo, imagem, logo, capa e área de legenda; fundo (cor/gradiente/imagem); preview de frame renderizado via FFmpeg; salvar rascunho ou publicar.
- **Exportação**
  - MP4 H.264 + AAC em 3 qualidades (Alta / Média / Rápida).
  - Exportar um corte ou todos de uma vez.
  - Progresso em tempo real via WebSocket.
- **Busca na transcrição** e **configurações persistentes** em `settings.json`.

---

## 🛠 Stack / Tecnologias

**Backend (Python)**
| Componente | Tecnologia |
|---|---|
| API | FastAPI + Uvicorn + Pydantic v2 |
| Transcrição | faster-whisper (CTranslate2), modelos `tiny`…`large-v3` |
| Análise de cenas | PySceneDetect (OpenCV) |
| Detecção de rosto | YOLOv8-face (ONNX Runtime) |
| Download de vídeos | yt-dlp |
| Processamento de vídeo | FFmpeg / FFprobe |
| IA de conteúdo | Ollama · OpenAI-compatível · heurística offline |
| Mídia/áudio | OpenCV, numpy, scipy, soundfile, Pillow |

**Frontend (React)**
| Componente | Tecnologia |
|---|---|
| Framework | React 19 + TypeScript |
| Build | Vite 8 |
| Estilo | Tailwind CSS 4 |
| Componentes | @base-ui/react |
| Extras | lucide-react, sonner (toasts), next-themes |

**Armazenamento local** — projetos, vídeos, modelos baixados, `settings.json` e banco de feedbacks ficam em `backend/data/` (gerado em runtime). Os **templates built-in** (`backend/data/templates/`) são versionados.

---

## 📋 Pré-requisitos

- **Python 3.10+**
- **Node.js 18+** (recomendado 20+)
- **FFmpeg + FFprobe** (com `ffprobe` no PATH). No Windows: `winget install Gyan.FFmpeg`. A aplicação também procura em instalações do winget automaticamente.
- **Opcional — Ollama** para análise semântica de conteúdo: `winget install Ollama.Ollama` e rode `ollama pull qwen2.5:7b` (ou outro modelo).
- **Opcional — GPU NVIDIA + CUDA** para transcrição mais rápida (detectada automaticamente).

> A primeira transcrição baixa o modelo Whisper escolhido (~1 GB para `medium`) para `backend/data/models/`. A detecção de rosto baixa o modelo YOLOv8-face ONNX (~232 KB) na primeira renderização.

---

## 🚀 Como instalar e rodar

### 1. Backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python run.py
```

O backend sobe em **http://127.0.0.1:8000** (saúde: `http://127.0.0.1:8000/api/health`).

### 2. Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Abra **http://localhost:5173** — o Vite encaminha `/api` e `/media` para o backend.

### Atalho no Windows (`start.bat`)

Na raiz do projeto há um `start.bat`: dê **duplo clique** e ele sobe o backend
(já em execução, ele reutiliza), sobe o frontend e abre o navegador em
http://localhost:5173 automaticamente. Feche as janelas abertas para parar.

### 3. Fluxo de uso

1. Clique em **Importar** (botão com ➕/upload no painel esquerdo).
2. Arraste um vídeo **ou** cole um link do YouTube.
3. Selecione o projeto e clique em **Processar**.
4. Acompanhe o progresso em tempo real; ao terminar, os cortes aparecem no centro.
5. Edite, avalie e **exporte** (individual ou todos). Os arquivos ficam em `backend/data/projects/<id>/clips/`.

#### Converter só para 9:16 (sem cortes)

Já tem um vídeo curto pronto e só quer ele no formato vertical (Shorts/Reels)?
Sem transcrição, sem IA, sem legendas:

1. No card do projeto, clique no botão **9:16** (ícone de celular).
2. O vídeo inteiro é reenquadrado para **1080×1920** respeitando o modo de
   reenquadramento das configurações (fundo desfocado / cortar / automático).
3. Ao terminar, aparece um corte chamado **"Vídeo completo 9:16"** na lista da
   direita — é só **Baixar**.

#### Ajustar um corte manualmente

O corte gerado às vezes começa ou termina cedo demais. Para pegar alguns
segundos a mais (ou encurtar), selecione o corte na lista da direita — abre o
painel **Editor do corte**:

1. Use os sliders **Início** e **Fim** para mover o trecho. Arraste **Início**
   para a esquerda para começar antes (pega os segundos anteriores) e **Fim**
   para a direita para alongar. O trecho mínimo é de 1 segundo.
2. Clique em **Salvar alterações** (o botão fica logo acima de **Renderizar**
   e só habilita quando algo mudou).
3. Clique em **Re-renderizar 1080x1920** para gerar o MP4 com o novo trecho —
   as legendas são recortadas automaticamente para o intervalo ajustado.
4. Use **Dividir no playhead** para cortar o corte em dois no ponto onde a
   linha de reprodução (playhead) estiver, e **Ver trecho** para pré-visualizar.

Também dá para pedir o texto do corte de novo à IA: os botões ✨ ao lado do
**Título** e da **Legenda** regeneram cada campo.

---

## ⚙️ Configurações

Disponíveis em **Ajustes** (ícone de engrenagem) e persistidas em `backend/data/settings.json`:

| Grupo | Opções |
|---|---|
| Transcrição | Modelo Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`), idioma (`auto`, `pt`, `en`, …) |
| IA de conteúdo | Provedor (`ollama` / OpenAI-compat / `none`), modelo, URL base |
| Cortes | Durações (15/30/45/60 s), máximo de cortes, qualidade de exportação, reenquadramento (`automático`, `sempre cortar`, `fundo desfocado`) |
| Legendas | Palavras por linha, tamanho, fonte |
| Marca (Brand Kit) | Logo (upload), usar logo no vídeo, posição, cores primária/secundária, fonte da marca (também nas legendas) |
| Sistema | Usar GPU (CUDA), detecção de rosto, gerar legendas `.srt` |

---

## 📁 Estrutura do projeto

```
maquina_de_cortes/
├── backend/
│   ├── app/
│   │   ├── api/            # Rotas FastAPI (projetos, cortes, sistema, templates, WebSocket)
│   │   ├── core/           # Configurações, CUDA, eventos
│   │   ├── models/         # Schemas (Project, Clip, Template, …)
│   │   ├── services/
│   │   │   ├── pipeline/   # Áudio, transcrição, análise, cortes, legendas, reframe, export, template_render
│   │   │   ├── ai/         # Provedores de IA (Ollama, OpenAI-compat, heurística)
│   │   │   ├── learning/   # Feedback e perfil do usuário
│   │   │   ├── downloader.py
│   │   │   ├── template_store.py  # CRUD + templates built-in
│   │   │   └── project.py  # Persistência dos projetos
│   │   └── utils/          # FFmpeg, helpers
│   ├── data/
│   │   ├── templates/      # Templates (built-ins versionados + seus criados por você)
│   │   └── ...             # (gerado em runtime: projetos, modelos, settings) — não versionado
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── components/     # Painéis, editor, timeline, dialogs, TemplateGallery, TemplateEditor
│   │   └── lib/            # API client, tipos, WebSocket
│   ├── package.json
│   └── vite.config.ts
└── .gitignore
```

---

## 🧩 Detalhes técnicos

- **Cortes 9:16** — o vídeo é escalado (cobrindo a área vertical) e recortado com `crop` dinâmico (`if(lt(t,…))`) seguindo as âncoras do rosto, em 30 fps, H.264 + AAC.
- **Detecção de rosto** — modelo `face_detection_yunet_2023mar.onnx` (formato YOLOv8-face) executado com ONNX Runtime em CPU; entrada em [0,255], confiança mínima 0.35.
- **Progresso em tempo real** — eventos WebSocket em `/api/ws/project/{id}` com etapas (`audio`, `transcription`, `signals`, `content`, `clips`, `metadata`, `render`).
- **Feedback** — avaliações ficam em `backend/data/feedback.db` e influenciam a seleção de cortes futuros.

---

## 🛠 Solução de problemas

| Problema | Solução |
|---|---|
| `FFmpeg não encontrado` | Instale com `winget install Gyan.FFmpeg` e reinicie o backend |
| Import do YouTube falha | Verifique conexão; o `yt-dlp` pode precisar de atualização (`pip install -U yt-dlp`) |
| Transcrição lenta | Troque o modelo para `small`/`base` em Ajustes, ou ative GPU/CUDA |
| Sem análise semântica | Instale o Ollama e rode `ollama pull qwen2.5:7b`; senão, o app usa o modo heurístico |
| Primeira renderização baixa um modelo | Aguarde; o download é único (fica em `backend/data/models/`) |

---

## 📄 Licença

Projeto de uso pessoal/estudo — sem licença definida.
