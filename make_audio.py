import base64
import os
import pathlib
import re
import subprocess
import sys
import tempfile

import requests

URL = "http://localhost:8000/v1/audio/speech"
MODEL = "chatterbox-turbo-8bit"
MAX_CHARS = 450
HEADERS = {"Authorization": f"Bearer {os.environ['OMLX_API_KEY']}"}

# Voice cloning: REF_AUDIO=any_audio_file (m4a/mp3/wav...).
# Server saves it as .wav, so convert to 24 kHz mono wav; Chatterbox only uses
# the first 10-15 s. ref_text is required by the server but ignored by Chatterbox.
VOICE = {}
if os.environ.get("REF_AUDIO"):
    wav = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", os.environ["REF_AUDIO"],
         "-af", "silenceremove=start_periods=1:start_threshold=-50dB",
         "-ac", "1", "-ar", "24000", "-t", "15", "-f", "wav", "pipe:1"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    VOICE = {
        "ref_audio": base64.b64encode(wav).decode(),
        "ref_text": os.environ.get("REF_TEXT", "reference voice"),
    }


def chunks(text):
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    buf = ""
    for s in sentences:
        if len(buf) + len(s) > MAX_CHARS and buf:
            yield buf.strip()
            buf = ""
        buf += " " + s
    if buf.strip():
        yield buf.strip()


OUT = pathlib.Path("output")
OUT.mkdir(exist_ok=True)

# Natural sort so chapter_10 comes after chapter_9 (shell globs sort lexically).
files = sorted(
    sys.argv[1:],
    key=lambda f: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", f)],
)
chapters = []

for path in files:
    p = pathlib.Path(path)
    chapters.append((OUT / f"{p.stem}.wav").resolve())
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        parts = []
        for i, piece in enumerate(chunks(p.read_text(encoding="utf-8"))):
            r = requests.post(
                URL,
                json={"model": MODEL, "input": piece, **VOICE},
                headers=HEADERS,
                timeout=600,
            )
            r.raise_for_status()
            part = tmp / f"{i:03d}.wav"
            part.write_bytes(r.content)
            parts.append(part)
            print(p.name, i)
        listfile = tmp / "list.txt"
        listfile.write_text("".join(f"file '{x}'\n" for x in parts))
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listfile), str(chapters[-1])],
            check=True,
        )  # fmt: skip

# All chapters -> one MP3.
with tempfile.NamedTemporaryFile("w", suffix=".txt") as listfile:
    listfile.write("".join(f"file '{c}'\n" for c in chapters))
    listfile.flush()
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", listfile.name, "-c:a", "libmp3lame", "-q:a", "2",
         str(OUT / "audiobook.mp3")],
        check=True,
    )  # fmt: skip
print("wrote", OUT / "audiobook.mp3")
