# Contagem de Pessoas na Calçada

Sistema de teste para contar pessoas que passam em frente a uma câmera IP,
usando YOLOv8 + ByteTrack para detecção/tracking, com contagem única por
`track_id` e direção (entrada/saída), gravando os eventos no Supabase.

Contexto completo do projeto e decisões já tomadas: ver o documento de
planejamento original (fases, arquitetura, pendências).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Se for usar GPU, instale o PyTorch com CUDA antes (ajuste `cu121` para a
versão de CUDA instalada):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Copie `.env.example` para `.env` e preencha:

```bash
copy .env.example .env
```

- `RTSP_URL`: URL RTSP da câmera (senha de RTSP, não a senha do app).
- `SUPABASE_URL` / `SUPABASE_KEY`: só são necessários a partir da Fase 3.
- `LINE_X1`/`LINE_Y1`/`LINE_X2`/`LINE_Y2`: preenchidos pelo script de calibração (abaixo).

## Banco de dados (Supabase)

Rode `sql/schema.sql` no SQL editor do Supabase para criar a tabela
`contagem_eventos` antes de usar a Fase 3.

## Fases

### Fase 1 — validar câmera e detecção

```bash
python scripts/01_captura.py
```

Mostra as bounding boxes de pessoas detectadas em tempo real. Use para
confirmar que o RTSP está estável e que a detecção funciona bem no
ângulo/altura/iluminação reais da câmera. Pressione `q` para sair.

### Calibrar a linha de contagem

```bash
python scripts/calibrar_linha.py
```

Abre um frame da câmera; clique 2 pontos definindo a linha (deve ficar
restrita à faixa de pedestres da calçada, evitando a via de carros). O
script imprime `LINE_X1`/`LINE_Y1`/`LINE_X2`/`LINE_Y2` para colar no `.env`.

A direção "entrada" é definida por `ENTRADA_SIDE` no `.env`
(`neg_to_pos` ou `pos_to_neg`) — dependendo de qual lado da linha corresponde
a "entrando" na calçada. Se sair invertido na prática (Fase 2), basta trocar
esse valor.

### Fase 2 — tracking + linha (sem gravar nada)

```bash
python scripts/02_tracking.py
```

Mostra o vídeo com IDs de tracking, a linha calibrada e os contadores de
entrada/saída na tela. Use para validar a lógica de cruzamento antes de
gravar no banco.

### Fase 3/4 — pipeline completo (grava no Supabase)

```bash
python scripts/03_pipeline.py             # com janela de vídeo
python scripts/03_pipeline.py --headless  # sem janela, só console (teste de campo)
```

Cada cruzamento de linha gera um insert em `contagem_eventos`
(`camera_id`, `track_id`, `direcao`, `confianca`, `timestamp`). Use o modo
`--headless` para deixar rodando por algumas horas em horário de movimento e
depois comparar o total agregado no Supabase com uma contagem manual.

## Variáveis de ajuste fino

- `CONF_THRESHOLD`: confiança mínima do YOLO para considerar uma detecção (padrão `0.4`).
- `FRAME_SKIP`: processa 1 a cada N frames, para economizar GPU (padrão `1` = todo frame).
- `MODEL_PATH`: `yolov8n.pt` por padrão; suba para `yolov8s.pt`/`yolov8m.pt` se a acurácia não for suficiente.
- `DEVICE`: vazio = auto, `0`/`1` = escolher GPU específica, `cpu` = forçar CPU.

## Estrutura

```
src/
  config.py           # leitura do .env
  supabase_client.py   # insert de eventos
  line_crossing.py     # lógica de cruzamento de linha / direção / dedupe
scripts/
  01_captura.py         # Fase 1
  calibrar_linha.py     # calibração da linha de contagem
  02_tracking.py         # Fase 2
  03_pipeline.py         # Fase 3/4
sql/
  schema.sql             # schema do Supabase
```
