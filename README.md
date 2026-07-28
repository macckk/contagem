# Contagem de Pessoas e Veículos

Sistema de teste para contar pessoas que passam pela calçada (e,
opcionalmente, veículos que passam pela via) em frente a uma câmera IP,
usando YOLOv8 + ByteTrack para detecção/tracking, com contagem única por
`track_id` (quem cruzou a faixa, sem distinguir direção), gravando os
eventos no Supabase.

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
- `LINE_X1`/`LINE_Y1`/`LINE_X2`/`LINE_Y2`: linha de pessoas, preenchida pelo script de calibração (abaixo).
- `LINE_VEICULOS_X1`/`LINE_VEICULOS_Y1`/`LINE_VEICULOS_X2`/`LINE_VEICULOS_Y2`: linha de veículos, opcional (deixe vazio para contar só pessoas).

### Sobre a captura RTSP (por que existe `src/rtsp_client.py`)

O `cv2.VideoCapture` (ffmpeg) não funciona com essa câmera:

1. Ela responde ao `SETUP` em UDP corretamente, mas o roteador não consegue
   rotear de volta o vídeo (RTP/UDP) quando a câmera está numa sub-rede
   diferente do PC de controle — o NAT só mantém estado de fluxos que o
   próprio cliente iniciou, e a câmera empurrando RTP é um fluxo novo.
2. Em TCP interleaved ela responde ao `SETUP` com um cabeçalho `Transport`
   levemente malformado (`RTP/AVP` em vez de `RTP/AVP/TCP`), o que faz o
   parser rígido do ffmpeg recusar a conexão com `Nonmatching transport in
   server reply`.

Por isso o projeto tem um cliente RTSP próprio (`src/rtsp_client.py`) que
fala RTSP/TCP interleaved diretamente (com autenticação Digest) e decodifica
o H.264 recebido via PyAV, contornando os dois problemas. Todos os scripts
usam esse cliente no lugar de `cv2.VideoCapture`.

## Banco de dados (Supabase)

Rode `sql/schema.sql` no SQL editor do Supabase para criar a tabela
`contagem_eventos` antes de usar a Fase 3. A coluna `tipo` marca cada evento
como `'pessoa'` ou com o tipo específico de veículo (`'car'`, `'motorcycle'`,
`'bus'`, `'truck'`, `'bicycle'`). Se você já tinha criado a tabela antes,
rode as migrations em ordem:

- `sql/migrations/001_remove_direcao.sql` — remove a coluna `direcao` (não é mais usada).
- `sql/migrations/002_add_tipo.sql` — adiciona a coluna `tipo`.
- `sql/migrations/003_tipo_especifico_veiculo.sql` — troca o `'veiculo'` genérico pelos tipos específicos.
- `sql/migrations/004_rls_leitura_publica.sql` — habilita RLS e libera leitura pública (`SELECT`) para o dashboard (ver seção **Dashboard** abaixo).
- `sql/migrations/005_timezone_brasilia.sql` — ajusta o timezone padrão do banco para `America/Sao_Paulo`, para que o SQL Editor/Table Editor do Supabase mostrem os horários já convertidos (a coluna `timestamp` é `timestamptz`, então os dados continuam corretos internamente; sem isso, a visualização crua no Supabase aparece 3h adiantada, em UTC).

## Fases

### Fase 1 — validar câmera e detecção

```bash
python scripts/01_captura.py
```

Mostra as bounding boxes de pessoas detectadas em tempo real. Use para
confirmar que o RTSP está estável e que a detecção funciona bem no
ângulo/altura/iluminação reais da câmera. Pressione `q` para sair.

### Calibrar a(s) linha(s) de contagem

```bash
python scripts/calibrar_linha.py                       # linha de pessoas (calcada)
python scripts/calibrar_linha.py --alvo veiculos       # linha de veiculos (via) - opcional
python scripts/calibrar_linha.py --alvo veiculos-noite # linha de veiculos a noite - opcional, rode de noite
```

Abre um frame da câmera; clique 2 pontos definindo a linha. Para pessoas,
deve ficar restrita à faixa de pedestres da calçada, evitando a via de
carros. Para veículos, na faixa da via (é preciso reenquadrar a câmera de
forma que a via fique visível, se ainda não estiver). O script imprime as
variáveis para colar no `.env` (`LINE_*`, `LINE_VEICULOS_*` ou
`LINE_VEICULOS_NOITE_*`).

A linha `veiculos-noite` é opcional e só faz sentido calibrar rodando o
script **de noite**: o veículo costuma ser detectado com mais confiança
assim que entra no quadro (antes do farol saturar a cena de perto), então
vale posicionar essa linha num ponto diferente da linha de dia — mais perto
de onde o carro aparece. Se não for calibrada, a contagem noturna usa a
mesma linha de veículos do dia.

A linha de veículos é opcional — se não for calibrada, os scripts contam só
pessoas normalmente.

### Fase 2 — tracking + linha (sem gravar nada)

```bash
python scripts/02_tracking.py
```

Mostra o vídeo com IDs de tracking, a(s) linha(s) calibrada(s) e o total de
pessoas (e de veículos, se a linha correspondente estiver calibrada) que já
cruzaram na tela. Há um contador independente por tipo específico de veículo
(carro/moto/ônibus/caminhão/bicicleta) — o resumo detalhado por tipo aparece
no console ao encerrar (`x` ou Ctrl+C). Use para validar a lógica de
cruzamento antes de gravar no banco.

Use `--debug` para ver no console **todas** as detecções (não só as que
cruzam a linha) — útil pra confirmar se um tipo de veículo está sendo
detectado mas não contado, ou simplesmente não passou perto da linha ainda.

### Fase 3/4 — pipeline completo (grava no Supabase)

```bash
python scripts/03_pipeline.py                      # com janela de vídeo
python scripts/03_pipeline.py --headless           # sem janela, só console (teste de campo)
python scripts/03_pipeline.py --headless --preview # só console + janelinha leve de vídeo
```

Cada cruzamento de linha gera um insert em `contagem_eventos`
(`camera_id`, `track_id`, `tipo`, `confianca`, `timestamp`). Use o modo
`--headless` para deixar rodando por algumas horas em horário de movimento e
depois comparar o total agregado no Supabase (filtrando por `tipo`) com uma
contagem manual.

`--preview` mostra uma janelinha (360px de largura) só com o vídeo cru
redimensionado, sem nenhum texto/caixas/zonas (que exigem `result.plot()`,
mais custoso), pra acompanhar visualmente um teste `--headless` de longa
duração sem pesar no processamento. Pode ser combinado com `--headless` ou
usado sozinho.

Se a conexão RTSP cair no meio do teste (câmera reiniciou, Wi-Fi caiu,
etc.), o script **não encerra mais** — ele fica tentando reconectar a cada
5s indefinidamente (mensagem `Conexão com a câmera perdida - tentando
reconectar...` no console) e retoma o monitoramento assim que a câmera
volta, mantendo as contagens acumuladas até ali. Só encerra de fato com
`x` na janela (se houver) ou `Ctrl+C` no terminal.

### GPU e FPS

Ao iniciar, os scripts 01/02/03 imprimem se uma GPU CUDA foi detectada
(`GPU detectada: <nome> (cuda:0, X GB)`) ou se vão rodar em CPU. O FPS
efetivo (captura + inferência + tracking) aparece na tela e é impresso no
console a cada 5 segundos (funciona também no modo `--headless`).

Uma única câmera/stream processa um frame por vez — não há como dividir a
inferência de um frame entre 2 GPUs. `DEVICE` no `.env` escolhe **uma** GPU
(`0` ou `1`); a segunda só seria útil rodando um segundo pipeline em
paralelo (ex: uma segunda câmera no futuro).

`HALF_PRECISION=true` ativa precisão FP16 na inferência (via `quantize=16`
no `model.track()`/`predict()` — o parâmetro antigo `half=` foi depreciado
pelo Ultralytics) — quase 2x mais rápido em GPU CUDA, sem perda perceptível
de acurácia. É desligado automaticamente em CPU
(`src/device_info.should_use_half`), então não tem problema deixar `true`
mesmo testando numa máquina sem GPU.

## Variáveis de ajuste fino

- `CONF_THRESHOLD`: confiança mínima do YOLO para considerar uma detecção (padrão `0.4`).
- `FRAME_SKIP`: processa 1 a cada N frames, para economizar GPU (padrão `1` = todo frame).
- `MODEL_PATH`: `yolov8n.pt` por padrão; suba para `yolov8s.pt`/`yolov8m.pt` se a acurácia não for suficiente.
- `IMGSZ`: tamanho de imagem usado na inferência (padrão `640`). Um valor maior (ex: `960`, ou `1280` = resolução nativa da câmera) reduz a fusão de veículos próximos numa única detecção classificada errado e ajuda a detectar veículos menores/mais distantes, ao custo de mais processamento.
- `DEVICE`: vazio = auto, `0`/`1` = escolher GPU específica, `cpu` = forçar CPU.
- `AUGMENT_INFERENCE`: test-time augmentation (múltiplas escalas/espelhamentos combinados) — ajuda a recuperar veículos com motion blur (carro/moto passando rápido) ou parcialmente visíveis. Custa ~2-3x mais processamento; só vale a pena com GPU sobrando.

### Modo noite

A câmera muda para infravermelho preto-e-branco à noite, e os faróis
acesos estouram o brilho e escondem a carroceria dos veículos — o que
derruba bastante a confiança do YOLO (treinado majoritariamente em imagens
diurnas coloridas). `src/night_mode.py` detecta automaticamente esse modo
(pela saturação de cor do frame, quase zero em P&B — o brilho médio sozinho
engana aqui, porque o IV ilumina a cena e reflete no chão molhado, ficando
alto mesmo de noite) e, quando ativo:

1. Aplica um leve desfoque + realce de contraste (CLAHE) no frame antes da
   detecção, para reduzir o ruído granulado do modo IR e destacar melhor a
   silhueta do veículo nas partes não totalmente estouradas pelo farol.
2. Usa um limiar de confiança mais baixo (`NIGHT_CONF_THRESHOLD`, padrão
   `0.15`, vs. `CONF_THRESHOLD` de dia) — motos são o caso mais sensível: o
   farol único e a silhueta menor rendem confiança bem mais baixa que carros
   no modo IR, e com um limiar alto o YOLO simplesmente não gera nenhuma
   detecção para a moto (nem aparece no `--debug`), então esse corte
   precisa ficar bem permissivo. Isso não afeta a contagem em si — quem
   decide o que conta é `NIGHT_ZONE_MIN_CONF` (mais alto, ver seção de
   zona), este aqui só decide o que chega a ser rastreado.

Variáveis: `ENABLE_NIGHT_MODE` (padrão `true`), `NIGHT_SATURATION_THRESHOLD`
(padrão `20`), `NIGHT_LUMINANCE_THRESHOLD` (sinal secundário, para câmeras
sem modo IR), `NIGHT_CONF_THRESHOLD`, `NIGHT_CLAHE_CLIP_LIMIT`. Quando
ativo, aparece `[modo noite]` ao lado dos contadores na tela.

### Tracker mais tolerante (`trackers/bytetrack_tolerante.yaml`)

À noite a detecção fica mais intermitente (ruído do modo IR + desfoque de
movimento por exposição mais longa), então um veículo pode não ser
detectado em frames suficientes para o tracker perceber que ele cruzou a
linha. `trackers/bytetrack_tolerante.yaml` ajusta o ByteTrack padrão da
Ultralytics para tolerar isso:

- `track_buffer: 60` (padrão: 30) — mantém o track vivo por mais tempo sem detecção.
- `track_low_thresh: 0.05` (padrão: 0.1) — aceita detecções mais fracas para reconectar a um track já existente.

Usado sempre (dia e noite) — o Ultralytics só lê a config do tracker uma
vez por sessão (com `persist=True`), então não dá para alternar
dinamicamente entre um tracker "de dia" e um "de noite" no meio da
execução. O trade-off é um risco levemente maior de troca de identidade
(ID switch) quando dois veículos se cruzam bem perto da linha. Pode
sobrescrever com `TRACKER_CONFIG=<caminho>` no `.env` se quiser usar outro
arquivo.

### Contagem de veículos por zona (`src/zone_counter.py`)

Mesmo com o tracker mais tolerante, um veículo pode nunca ser detectado
nos dois lados da linha — o `LineCrossingCounter` exige isso e
simplesmente não contaria nada. Isso é comum à noite (ruído do modo IR),
mas também de dia: carro/moto passando rápido sofre motion blur, ou fica
parcialmente encoberto por outro veículo, e o tracking perde o rastro
antes de completar o cruzamento.

Por isso **veículos (dia e noite) são contados de outro jeito**: em vez de
cruzamento de linha, conta a detecção assim que ela aparece dentro de uma
faixa ao redor da linha (a "zona"), desde que a confiança seja alta o
suficiente — `DAY_ZONE_MIN_CONF` (padrão `0.35`) de dia,
`NIGHT_ZONE_MIN_CONF` (padrão `0.55`) de noite; mais exigente que
`CONF_THRESHOLD`/`NIGHT_CONF_THRESHOLD`, que são só para manter o tracking
vivo.

O risco óbvio disso sozinho seria contar o mesmo veículo físico várias
vezes (o tracking fragmentado gera `track_id`s diferentes para o mesmo
carro/moto passando — moto em especial, por ser menor e mais dificil de
manter o rastro). Por isso tem um **cooldown espaço-temporal**: uma nova
detecção do mesmo tipo, perto (`DAY_ZONE_DEDUPE_DISTANCE_PX`/
`NIGHT_ZONE_DEDUPE_DISTANCE_PX`, padrão `200` pixels — maior que a própria
zona, pra cobrir o quanto o veículo se move entre um fragmento de track e
outro) e logo em seguida (`DAY_ZONE_COOLDOWN_SECONDS`/
`NIGHT_ZONE_COOLDOWN_SECONDS`, padrão `5s`), é tratada como o mesmo
veículo e ignorada.

Pessoas não são afetadas por essa mudança — continuam contadas por
cruzamento de linha (`LineCrossingCounter`).

**Double-count entre zona de dia e de noite**: os contadores de dia e de
noite são instâncias separadas de `ZoneCooldownCounter`. Dois problemas
distintos podiam fazer o mesmo veículo físico ser contado 2x:

1. O mesmo `track_id` sendo reavaliado pelas duas instâncias se a
   classificação dia/noite (`is_night`, por saturação de cor) oscilar
   entre frames (comum no amanhecer/anoitecer, ou quando a saturação fica
   perto de `NIGHT_SATURATION_THRESHOLD`) enquanto o track ainda está
   ativo.
2. Mais sutil: o tracking **fragmenta** (gera um `track_id` **novo** para
   o mesmo veículo físico — moto em especial, por ser menor e mais difícil
   de manter o rastro) bem no momento em que a classificação dia/noite
   muda. Mesmo com o (1) resolvido, cada instância só enxergava seu
   próprio histórico de posições recentes (`_recent`), então um fragmento
   contado como "dia" não impedia o próximo fragmento (outro `track_id`,
   mesma moto) de ser contado de novo como "noite".

A correção definitiva é o parâmetro `shared_state` do `ZoneCooldownCounter`:
os scripts 02/03 criam um dicionário de dedupe (`counted_track_ids` +
`recent`) por tipo de veículo e passam o **mesmo objeto** para as
instâncias de dia e de noite daquele tipo. `total` continua próprio de
cada instância (pra manter a quebra dia/noite no relatório final), mas o
que decide "já contei esse veículo" é compartilhado — resolvendo os dois
problemas de uma vez.

### Área de exclusão (`EXCLUDE_ZONES`)

Se uma região do quadro gera falsos positivos (um carro estacionado, um
quintal fora da rua, etc.), dá pra ignorá-la completamente. Calibre com:

```bash
python scripts/calibrar_linha.py --alvo exclusao
```

Clique 4 pontos — os vértices do polígono a ignorar, na ordem (não precisa
ser um retângulo perfeito, dá pra acompanhar um muro em diagonal, por
exemplo) — e cole o resultado no `.env`:

```
EXCLUDE_ZONES=x1,y1,x2,y2,x3,y3,x4,y4
```

Para mais de uma área, rode de novo e junte os blocos com `;`:
`EXCLUDE_ZONES=x1,y1,x2,y2,x3,y3,x4,y4;x1,y1,x2,y2,x3,y3,x4,y4`. A checagem
(`_point_in_polygon` em `src/zone_counter.py`, ray casting) usa o mesmo
ponto de contato do `ZoneCooldownCounter` (base da caixa) — qualquer
detecção cuja base caia dentro de um desses polígonos é descartada
**antes** do tracking/contagem (não aparece nem no `--debug` além de uma
linha "ignorado"). Os polígonos aparecem desenhados em vermelho na janela
de vídeo (`02_tracking.py` e `03_pipeline.py`, quando não `--headless`).

A zona noturna usa a linha `LINE_VEICULOS_NOITE_*` se calibrada (ver seção
de calibração acima), ou cai para a linha de veículos do dia (`LINE_VEICULOS_*`)
como padrão. Na janela de vídeo, as duas zonas (dia em magenta,
`DAY_ZONE_WIDTH_PX` pixels de cada lado da linha; noite em ciano,
`NIGHT_ZONE_WIDTH_PX`, padrão `220`) aparecem sempre desenhadas como
retângulos translúcidos, facilitando ver exatamente a área usada na
contagem em qualquer horário.

**Importante**: a checagem usa distância ao *segmento* da linha (não à reta
infinita) — um veículo que passe fora da extensão horizontal/vertical da
linha calibrada nunca vai cair "perto" dela, mesmo com confiança alta,
mesmo aumentando `*_ZONE_WIDTH_PX`. Ao calibrar (`scripts/calibrar_linha.py`),
estique a linha ponta a ponta cobrindo toda a largura da via por onde
veículos passam (todas as faixas), não só o trecho onde eles costumam
aparecer com mais confiança — senão veículos em faixas fora do alcance da
linha são detectados mas nunca contados.

## Estrutura

```
src/
  config.py           # leitura do .env
  rtsp_client.py       # cliente RTSP/TCP proprio + decode H.264 (PyAV)
  supabase_client.py   # insert de eventos
  line_crossing.py     # lógica de cruzamento de linha / dedupe
  night_mode.py        # deteccao dia/noite + realce de contraste noturno
  zone_counter.py      # contagem de veiculos a noite por zona + cooldown
  device_info.py       # mostra se ha GPU CUDA disponivel
  fps_meter.py         # medidor de FPS (media movel)
trackers/
  bytetrack_tolerante.yaml  # config do ByteTrack mais tolerante a deteccao intermitente
scripts/
  01_captura.py         # Fase 1
  calibrar_linha.py     # calibração da linha de contagem
  02_tracking.py         # Fase 2
  03_pipeline.py         # Fase 3/4
sql/
  schema.sql             # schema do Supabase
  migrations/            # alteracoes incrementais no schema ja existente
dashboard/                # app React (Vite) publicado no GitHub Pages
```

## Contando veículos além de pessoas

Se você reenquadrar a câmera para também ver a via (o documento original já
notava que dá pra ver a rua/vagas ao lado da calçada), basta:

1. Calibrar a linha da via: `python scripts/calibrar_linha.py --alvo veiculos`.
2. Rodar normalmente (`02_tracking.py` ou `03_pipeline.py`) — a detecção
   passa a incluir carro/moto/ônibus/caminhão automaticamente sempre que
   `LINE_VEICULOS_*` estiver preenchido no `.env`, sem precisar mudar nada
   no código.

Os dois tipos de evento vão para a mesma tabela `contagem_eventos`,
diferenciados pela coluna `tipo`.

## Dashboard (Fase 5)

App React (Vite) em `dashboard/`, publicado automaticamente no **GitHub
Pages** via GitHub Actions a cada push que altere a pasta. É uma página
estática pública que lê a tabela `contagem_eventos` direto do navegador,
usando a chave `anon public` do Supabase (não a `service_role`).

- **Publicação**: em Settings → Pages do repositório, defina a fonte como
  "GitHub Actions" (uma vez só). A URL fica em
  `https://macckk.github.io/contagem/`.
- **Segurança**: a chave `anon public` fica hardcoded em
  `dashboard/src/supabaseClient.js` de propósito — ela é feita para ser
  pública, e o acesso de leitura é controlado pela RLS policy da migration
  `004_rls_leitura_publica.sql` (só permite `SELECT`, nunca escrita).
- **Rodar localmente**:
  ```bash
  cd dashboard
  npm install
  npm run dev
  ```
- **Filtros**: período (hoje / 7 dias / 30 dias / tudo) e confiança mínima
  (slider, que também atualiza o card de distribuição de confiança). Os
  dados só são buscados ao carregar a página ou clicar em "Atualizar" (sem
  polling automático).
- **Cards**: total de pessoas, total de veículos, confiança média (com
  histograma) e horário de pico. **Gráficos**: cruzamentos por hora
  (pessoas vs. veículos) e total por tipo específico de veículo
  (carro/moto/ônibus/caminhão/bicicleta). Tabela de dados brutos disponível
  (colapsável) para acessibilidade/conferência.
