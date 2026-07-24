"""Ferramenta de calibracao da linha de contagem.

Captura um unico frame do RTSP, mostra em uma janela e permite clicar 2
pontos com o mouse (clique esquerdo) para definir a linha virtual. Ao final,
imprime as coordenadas para colar no .env (LINE_X1, LINE_Y1, LINE_X2, LINE_Y2).

Uso:
    python scripts/calibrar_linha.py
"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

points = []


def on_click(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
        points.append((x, y))
        print(f"Ponto {len(points)}: ({x}, {y})")


def main():
    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    cap = cv2.VideoCapture(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Nao foi possivel capturar um frame do stream.")

    window = "Clique 2 pontos para definir a linha (q para sair)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_click)

    while True:
        display = frame.copy()
        for p in points:
            cv2.circle(display, p, 5, (0, 0, 255), -1)
        if len(points) == 2:
            cv2.line(display, points[0], points[1], (0, 255, 0), 2)

        cv2.imshow(window, display)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q") or len(points) == 2:
            cv2.waitKey(1500)
            break

    cv2.destroyAllWindows()

    if len(points) == 2:
        (x1, y1), (x2, y2) = points
        print("\nAdicione ao seu .env:")
        print(f"LINE_X1={x1}")
        print(f"LINE_Y1={y1}")
        print(f"LINE_X2={x2}")
        print(f"LINE_Y2={y2}")
    else:
        print("Calibracao cancelada (menos de 2 pontos definidos).")


if __name__ == "__main__":
    main()
