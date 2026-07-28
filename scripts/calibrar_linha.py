"""Ferramenta de calibracao da linha de contagem.

Captura um unico frame do RTSP, mostra em uma janela e permite clicar 2
pontos com o mouse (clique esquerdo) para definir a linha virtual. Ao final,
imprime as coordenadas para colar no .env.

Uso:
    python scripts/calibrar_linha.py                          # linha de pessoas (calcada)
    python scripts/calibrar_linha.py --alvo veiculos           # linha de veiculos (via), de dia
    python scripts/calibrar_linha.py --alvo veiculos-noite     # linha de veiculos a noite (rode isso de noite!)
    python scripts/calibrar_linha.py --alvo exclusao           # retangulo de area a ignorar na deteccao

A linha de veiculos-noite e opcional: se nao for calibrada, a contagem
noturna usa a mesma linha/zona de veiculos do dia. Vale calibrar separado
porque a noite o veiculo costuma ser detectado com mais confianca assim
que entra no quadro (antes do farol saturar a cena de perto) - um lugar
diferente do ponto ideal para a linha de dia.

O modo "exclusao" e diferente dos outros: em vez de uma linha, os 2 pontos
clicados definem os cantos opostos de um retangulo (EXCLUDE_ZONES no .env)
- qualquer deteccao com o centro dentro dele e ignorada, antes mesmo do
tracking/contagem. Util pra silenciar uma area do quadro que gera falsos
positivos (ex: um carro estacionado, um quintal fora da rua). Pode ter
mais de um retangulo: rode de novo e junte os blocos com ";" no .env
(formato "x1,y1,x2,y2;x1,y1,x2,y2").
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.rtsp_client import RTSPClient

points = []


def on_click(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
        points.append((x, y))
        print(f"Ponto {len(points)}: ({x}, {y})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alvo",
        choices=["pessoas", "veiculos", "veiculos-noite", "exclusao"],
        default="pessoas",
        help="Qual calibrar: pessoas (calcada), veiculos (via, de dia), veiculos-noite ou "
        "exclusao (retangulo de area a ignorar na deteccao). Padrao: pessoas.",
    )
    args = parser.parse_args()
    is_exclusao = args.alvo == "exclusao"
    env_prefix = {
        "pessoas": "LINE_",
        "veiculos": "LINE_VEICULOS_",
        "veiculos-noite": "LINE_VEICULOS_NOITE_",
        "exclusao": "EXCLUDE_",
    }[args.alvo]

    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Nao foi possivel capturar um frame do stream.")

    window = f"Clique 2 pontos para a linha de {args.alvo} (q para sair)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_click)

    while True:
        display = frame.copy()
        for p in points:
            cv2.circle(display, p, 5, (0, 0, 255), -1)
        if len(points) == 2:
            if is_exclusao:
                cv2.rectangle(display, points[0], points[1], (0, 0, 255), 2)
            else:
                cv2.line(display, points[0], points[1], (0, 255, 0), 2)

        cv2.imshow(window, display)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q") or len(points) == 2:
            cv2.waitKey(1500)
            break

    cv2.destroyAllWindows()

    if len(points) == 2:
        (x1, y1), (x2, y2) = points
        if is_exclusao:
            print("\nAdicione ao seu .env (junte com ';' se ja tiver outro retangulo):")
            print(f"EXCLUDE_ZONES={x1},{y1},{x2},{y2}")
        else:
            print("\nAdicione ao seu .env:")
            print(f"{env_prefix}X1={x1}")
            print(f"{env_prefix}Y1={y1}")
            print(f"{env_prefix}X2={x2}")
            print(f"{env_prefix}Y2={y2}")
    else:
        print("Calibracao cancelada (menos de 2 pontos definidos).")


if __name__ == "__main__":
    main()
