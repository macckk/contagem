"""Cliente RTSP minimalista sobre TCP interleaved, com decode H.264 via PyAV.

Existe porque a camera (chip tipo "HIipCamera"/Hi35xx, comum em cameras
Yoosee) responde ao SETUP em TCP com um cabecalho Transport levemente
malformado (falta o sufixo "/TCP"), o que faz o parser rigido do ffmpeg
embutido no OpenCV recusar a conexao com "Nonmatching transport in server
reply". Alem disso, como a camera fica numa sub-rede diferente do PC de
controle, o RTP sobre UDP nao consegue voltar pelo roteador (o NAT so
mantem estado de fluxos que o proprio cliente iniciou, e o envio de RTP
pela camera e um fluxo novo, nao solicitado). TCP interleaved evita os
dois problemas: usa a mesma conexao TCP ja estabelecida para tudo.

Expoe uma interface parecida com cv2.VideoCapture (isOpened/read/release)
para os scripts nao precisarem mudar muito.

Tambem reaproveitado pelo subprojeto vaga_rotativa/ para falar com DVRs
Dahua/Intelbras, que exigem query string na URL para selecionar canal/
subtipo (ex: ?channel=6&subtype=0) - preservada ao montar a URL interna.
"""
import base64
import hashlib
import queue
import re
import socket
import threading
from urllib.parse import urlsplit

import av


class RTSPClient:
    def __init__(self, url: str, timeout: float = 5.0):
        parts = urlsplit(url)
        self._host = parts.hostname
        self._port = parts.port or 554
        self._user = parts.username or ""
        self._password = parts.password or ""
        self._path = parts.path or "/"
        if parts.query:
            # DVRs Dahua/Intelbras usam query string para selecionar canal/
            # subtipo (ex: ?channel=6&subtype=0) - sem isso o DESCRIBE cai
            # num recurso ambiguo e o DVR responde 404 Not Found.
            self._path += f"?{parts.query}"
        self._url_no_auth = f"rtsp://{self._host}:{self._port}{self._path}"
        self._timeout = timeout

        self._sock = None
        self._codec = av.CodecContext.create("h264", "r")
        self._frame_queue = queue.Queue(maxsize=10)
        self._running = False
        self._thread = None
        self._opened = False
        self._fu_buffer = None

        try:
            self._connect()
            self._opened = True
        except Exception as exc:
            print(f"Falha ao conectar RTSP: {exc}")

    # --- API compativel com cv2.VideoCapture ---
    def isOpened(self):
        return self._opened

    def read(self, timeout=5.0):
        try:
            frame = self._frame_queue.get(timeout=timeout)
            return True, frame
        except queue.Empty:
            return False, None

    def release(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    # --- handshake RTSP ---
    def _send_request(self, method, url, extra_headers, cseq):
        headers = [f"{method} {url} RTSP/1.0", f"CSeq: {cseq}"]
        headers.extend(extra_headers)
        headers.append("User-Agent: contagem-pessoas-rtsp-client")
        req = "\r\n".join(headers) + "\r\n\r\n"
        self._sock.sendall(req.encode())
        return self._read_response()

    def _read_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Conexao RTSP fechada pelo servidor")
            data += chunk
        return data

    def _read_response(self):
        """Le a proxima resposta textual do RTSP.

        Essa camera as vezes ja comeca a empurrar video pelo canal
        interleaved (pacotes comecando com '$') antes mesmo de responder ao
        PLAY, entao qualquer frame binario que aparecer no meio do caminho e
        repassado ao decodificador e ignorado aqui, ate chegar a resposta
        textual de verdade (que comeca com "RTSP/").
        """
        while True:
            first = self._read_exact(1)
            if first == b"$":
                frame_header = self._read_exact(3)
                channel = frame_header[0]
                length = (frame_header[1] << 8) | frame_header[2]
                payload = self._read_exact(length)
                if channel == 0:
                    self._handle_rtp_packet(payload)
                continue

            data = first
            while not data.endswith(b"\r\n\r\n"):
                data += self._read_exact(1)
            text = data.decode(errors="replace")
            m = re.search(r"Content-Length:\s*(\d+)", text)
            body = b""
            if m:
                body = self._read_exact(int(m.group(1)))
            return text, body

    @staticmethod
    def _md5(s):
        return hashlib.md5(s.encode()).hexdigest()

    def _digest_header(self, method, uri, realm, nonce):
        ha1 = self._md5(f"{self._user}:{realm}:{self._password}")
        ha2 = self._md5(f"{method}:{uri}")
        response = self._md5(f"{ha1}:{nonce}:{ha2}")
        return (
            f'Digest username="{self._user}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{response}"'
        )

    def _connect(self):
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        self._sock.settimeout(self._timeout)

        cseq = 1
        headers, _ = self._send_request(
            "DESCRIBE", self._url_no_auth, ["Accept: application/sdp"], cseq
        )
        m = re.search(r'realm="([^"]+)".*nonce="([^"]+)"', headers)
        if not m:
            raise RuntimeError(f"Resposta inesperada do DESCRIBE (esperava desafio digest): {headers!r}")
        realm, nonce = m.group(1), m.group(2)

        cseq += 1
        auth = self._digest_header("DESCRIBE", self._url_no_auth, realm, nonce)
        headers, sdp_body = self._send_request(
            "DESCRIBE",
            self._url_no_auth,
            [f"Authorization: {auth}", "Accept: application/sdp"],
            cseq,
        )
        if "200 OK" not in headers.splitlines()[0]:
            raise RuntimeError(f"DESCRIBE falhou: {headers!r}")
        sdp = sdp_body.decode(errors="replace")

        control = self._parse_video_control(sdp)
        track_url = control if control.startswith("rtsp://") else f"{self._url_no_auth}/{control}"
        self._prime_decoder_with_sprop(sdp)

        cseq += 1
        auth = self._digest_header("SETUP", track_url, realm, nonce)
        headers, _ = self._send_request(
            "SETUP",
            track_url,
            [f"Authorization: {auth}", "Transport: RTP/AVP/TCP;unicast;interleaved=0-1"],
            cseq,
        )
        if "200 OK" not in headers.splitlines()[0]:
            raise RuntimeError(f"SETUP falhou: {headers!r}")
        m = re.search(r"Session:\s*([^\r\n;]+)", headers)
        session = m.group(1).strip()

        cseq += 1
        auth = self._digest_header("PLAY", self._url_no_auth, realm, nonce)
        headers, _ = self._send_request(
            "PLAY",
            self._url_no_auth,
            [f"Authorization: {auth}", f"Session: {session}", "Range: npt=0.000-"],
            cseq,
        )
        if "200 OK" not in headers.splitlines()[0]:
            raise RuntimeError(f"PLAY falhou: {headers!r}")

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    @staticmethod
    def _parse_video_control(sdp):
        in_video = False
        for line in sdp.splitlines():
            if line.startswith("m=video"):
                in_video = True
                continue
            if line.startswith("m=") and in_video:
                break
            if in_video and line.startswith("a=control:"):
                return line.split(":", 1)[1].strip()
        raise RuntimeError("Nao encontrou a linha a=control: do video no SDP")

    def _prime_decoder_with_sprop(self, sdp):
        m = re.search(r"sprop-parameter-sets=([^;\r\n]+)", sdp)
        if not m:
            return
        for b64 in m.group(1).split(","):
            self._feed_nal(base64.b64decode(b64.strip()))

    # --- leitura continua do socket interleaved ---
    def _read_loop(self):
        buf = b""
        try:
            while self._running:
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                buf = self._consume_interleaved(buf)
        except OSError:
            pass
        finally:
            self._running = False

    def _consume_interleaved(self, buf):
        while len(buf) >= 4:
            if buf[0:1] != b"$":
                idx = buf.find(b"$", 1)
                if idx == -1:
                    return b""
                buf = buf[idx:]
                continue
            channel = buf[1]
            length = (buf[2] << 8) | buf[3]
            if len(buf) < 4 + length:
                break
            payload = buf[4:4 + length]
            buf = buf[4 + length:]
            if channel == 0:
                self._handle_rtp_packet(payload)
        return buf

    def _handle_rtp_packet(self, packet):
        if len(packet) < 12:
            return
        cc = packet[0] & 0x0F
        has_ext = bool(packet[0] & 0x10)
        offset = 12 + cc * 4
        if has_ext and len(packet) >= offset + 4:
            ext_len_words = (packet[offset + 2] << 8) | packet[offset + 3]
            offset += 4 + ext_len_words * 4
        if offset >= len(packet):
            return
        self._depacketize_h264(packet[offset:])

    def _depacketize_h264(self, payload):
        if not payload:
            return
        nal_type = payload[0] & 0x1F
        if 1 <= nal_type <= 23:
            self._feed_nal(payload)
        elif nal_type == 24:  # STAP-A: varios NALs agregados
            pos = 1
            while pos + 2 <= len(payload):
                size = (payload[pos] << 8) | payload[pos + 1]
                pos += 2
                if pos + size > len(payload):
                    break
                self._feed_nal(payload[pos:pos + size])
                pos += size
        elif nal_type == 28:  # FU-A: NAL fragmentado
            if len(payload) < 2:
                return
            fu_indicator = payload[0]
            fu_header = payload[1]
            start = bool(fu_header & 0x80)
            end = bool(fu_header & 0x40)
            actual_type = fu_header & 0x1F
            fragment = payload[2:]
            if start:
                nal_header = (fu_indicator & 0xE0) | actual_type
                self._fu_buffer = bytes([nal_header]) + fragment
            elif self._fu_buffer is not None:
                self._fu_buffer += fragment
            if end and self._fu_buffer is not None:
                self._feed_nal(self._fu_buffer)
                self._fu_buffer = None
        # STAP-B/MTAP16/MTAP24 nao sao usados por essa camera - ignorados

    def _feed_nal(self, nal_bytes):
        annex_b = b"\x00\x00\x00\x01" + bytes(nal_bytes)
        try:
            packets = self._codec.parse(annex_b)
        except Exception:
            return
        for packet in packets:
            try:
                frames = self._codec.decode(packet)
            except Exception:
                continue
            for frame in frames:
                array = frame.to_ndarray(format="bgr24")
                try:
                    self._frame_queue.put_nowait(array)
                except queue.Full:
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._frame_queue.put_nowait(array)
