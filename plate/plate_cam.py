#!/usr/bin/env python3
"""Car Talk 번호판 카메라 (라즈베리파이 5 + Camera Module 3).

하는 일
  1. 카메라로 사진을 계속 찍는다.
  2. tesseract(한국어)로 글자를 읽어 번호판 모양(예: 12가3456)을 찾는다.
  3. 찾으면 맥 브리지에 TCP로 한 줄 `PLATE:<번호판>`을 보낸다.
     처음 보일 때 바로, 보이는 동안 --repeat 초마다 다시.

설치: sudo apt install -y tesseract-ocr tesseract-ocr-kor
실행: python3 plate_cam.py --host <맥 IP> --known 12가3456
"""
from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import time

PLATE_RE = re.compile(r"(\d{2,3})\s*([가-힣])\s*(\d{4})")
FRAME_PATH = "/tmp/plate_frame.pgm"


def find_plate(text: str, known: list[str]) -> str | None:
    """읽은 글자에서 번호판을 찾는다.

    1) 번호판 모양(숫자 2~3 + 한글 1 + 숫자 4)이 그대로 있으면 그것.
    2) 시연 보조: 한글을 잘못 읽어도, 뒤 숫자 4자리가 --known 번호판과 같으면 그 번호판으로 본다.
    """
    squashed = re.sub(r"\s+", "", text)
    m = PLATE_RE.search(squashed)
    if m:
        return "".join(m.groups())
    digits = re.sub(r"\D", "", squashed)
    for plate in known:
        tail = re.sub(r"\D", "", plate)[-4:]
        if len(tail) == 4 and tail in digits:
            return plate
    return None


def otsu(gray):
    """흑백 두 덩어리로 가르는 문턱값(Otsu)."""
    import numpy as np
    hist = np.bincount(gray.ravel(), minlength=256).astype(float)
    total = gray.size
    cum = hist.cumsum()
    cum_mean = (hist * np.arange(256)).cumsum()
    w0 = cum / total
    w1 = 1 - w0
    mu0 = cum_mean / np.maximum(cum, 1)
    mu1 = (cum_mean[-1] - cum_mean) / np.maximum(total - cum, 1)
    between = w0 * w1 * (mu0 - mu1) ** 2
    return int(between.argmax())


class Camera:
    def __init__(self, width: int, height: int):
        from picamera2 import Picamera2  # 라즈베리파이 OS(데스크톱)에 기본 포함
        self.cam = Picamera2()
        self.cam.configure(self.cam.create_still_configuration(
            main={"size": (width, height), "format": "RGB888"}))
        self.cam.start()
        try:
            self.cam.set_controls({"AfMode": 2})  # Camera Module 3 연속 자동 초점
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)

    def grab_gray(self):
        import numpy as np
        frame = self.cam.capture_array()
        return frame.mean(axis=2).astype(np.uint8)


def save_pgm(img, path: str) -> None:
    h, w = img.shape
    with open(path, "wb") as f:
        f.write(b"P5 %d %d 255\n" % (w, h))
        f.write(img.tobytes())


def read_text(path: str) -> str:
    out = subprocess.run(["tesseract", path, "stdout", "-l", "kor", "--psm", "6"],
                         capture_output=True, text=True, timeout=15)
    return out.stdout


class Sender:
    """맥 브리지에 TCP로 한 줄씩 보낸다. 끊기면 다음에 다시 붙는다."""

    def __init__(self, host: str | None, port: int):
        self.host, self.port, self.sock = host, port, None

    def send(self, line: str) -> None:
        if not self.host:
            print("  (보내기 없음, --host 미지정)", line)
            return
        for _ in range(2):
            try:
                if self.sock is None:
                    self.sock = socket.create_connection((self.host, self.port), timeout=3)
                self.sock.sendall((line + "\n").encode("utf-8"))
                print("  → 맥", line)
                return
            except OSError as exc:
                print("  맥 연결 실패:", exc)
                if self.sock:
                    self.sock.close()
                self.sock = None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Car Talk 번호판 카메라")
    p.add_argument("--host", help="맥(브리지) IP. 없으면 화면에만 출력")
    p.add_argument("--port", type=int, default=9100)
    p.add_argument("--known", action="append", default=[], help="시연 번호판(여러 번 가능). 예: 12가3456")
    p.add_argument("--repeat", type=float, default=2.0, help="보이는 동안 다시 보내는 간격(초)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--once", action="store_true", help="한 장만 찍고 읽은 글자를 보여 주고 끝")
    args = p.parse_args(argv)

    cam = Camera(args.width, args.height)
    sender = Sender(args.host, args.port)
    last_sent: dict[str, float] = {}
    print("카메라 시작. 끝내려면 Ctrl+C")
    try:
        while True:
            t0 = time.monotonic()
            gray = cam.grab_gray()
            bw = ((gray > otsu(gray)) * 255).astype("uint8")
            save_pgm(bw, FRAME_PATH)
            text = read_text(FRAME_PATH)
            ms = (time.monotonic() - t0) * 1000
            plate = find_plate(text, args.known)
            shown = " ".join(text.split())[:60]
            print(f"[{ms:5.0f} ms] 읽음: {shown!r} → {plate or '-'}")
            if args.once:
                return 0
            if plate:
                now = time.monotonic()
                if now - last_sent.get(plate, 0) >= args.repeat:
                    sender.send(f"PLATE:{plate}")
                    last_sent[plate] = now
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
