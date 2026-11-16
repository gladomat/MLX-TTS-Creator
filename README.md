# make_audio.py

Turns text files into speech using a local oMLX
server running the `chatterbox-turbo-8bit` model. Optionally clones a voice from
a reference recording.

## Requirements

- oMLX running on `http://localhost:8000` with `chatterbox-turbo-8bit` loaded
- The oMLX API key
- [`uv`](https://docs.astral.sh/uv/) and `ffmpeg` (`brew install uv ffmpeg`)

## Basic usage (default voice)

```sh
export OMLX_API_KEY=<your-key>
uv run --with requests make_audio.py chapter*.txt
```

Output in `output/`:

- `output/<name>.wav` per input file, e.g. `chapter_1.txt` → `output/chapter_1.wav`
- `output/audiobook.mp3`: all chapters joined into one MP3

Chapters are ordered naturally (`chapter_2` before `chapter_10`), regardless of
how the shell sorts the glob. Existing files in `output/` are overwritten.

## Using your own voice (reference audio)

Point `REF_AUDIO` at a recording of the voice you want:

```sh
export OMLX_API_KEY=<your-key>
REF_AUDIO=glads_voice.m4a uv run --with requests make_audio.py chapter*.txt
```

Any format ffmpeg can read works (m4a, mp3, wav, ...). The script converts it
to 24 kHz mono WAV before sending it, so you don't need to convert it yourself.

### What makes a good reference clip

- **Only the first 15 seconds are used.** Leading silence is skipped first.
  Longer files are fine, but only that first stretch matters.
- One speaker, clean speech, no music or background noise.
- Speak in the tone you want the output to have (calm narration in, calm
  narration out).
- At least ~5 seconds of actual speech.

If the start of your recording is noisy or not representative, cut a better
section and use that instead:

```sh
# take 15 s starting at 0:20
ffmpeg -ss 20 -t 15 -i glads_voice.m4a clean.wav
REF_AUDIO=clean.wav uv run --with requests make_audio.py chapter*.txt
```

To record a new clip on macOS:

```sh
ffmpeg -f avfoundation -i ":0" -t 15 myvoice.wav
```

### `REF_TEXT`

The server requires a transcript alongside the reference audio, but
Chatterbox ignores it, so the script sends a placeholder. You can set
`REF_TEXT="..."` if you switch to a model that does use transcripts.

## How it works

1. Splits each text file into sentence-based chunks of up to ~450 characters.
2. Sends each chunk to `/v1/audio/speech` (with the reference voice if set).
3. Joins the chunks with ffmpeg into `output/<name>.wav`. The temporary
   chunk files are deleted afterwards.
4. Joins all chapter WAVs, in order, into `output/audiobook.mp3`
   (LAME VBR `-q:a 2`, ~190 kbps).

## Configuration

Edit the constants at the top of `make_audio.py`:

| Constant    | Default                                 | Meaning                     |
|-------------|-----------------------------------------|-----------------------------|
| `URL`       | `http://localhost:8000/v1/audio/speech` | oMLX speech endpoint        |
| `MODEL`     | `chatterbox-turbo-8bit`                 | TTS model id                |
| `MAX_CHARS` | `450`                                   | Max characters per request  |

List the models your server has loaded:

```sh
curl -H "Authorization: Bearer $OMLX_API_KEY" localhost:8000/v1/models
```

## Troubleshooting

| Error                       | Cause / fix                                                    |
|-----------------------------|----------------------------------------------------------------|
| `KeyError: 'OMLX_API_KEY'`  | Set `OMLX_API_KEY`.                                            |
| `401 Unauthorized`          | Wrong API key.                                                 |
| `404` / model not found     | `MODEL` doesn't match an id from `/v1/models`.                 |
| Voice sounds off            | Use a cleaner 15 s clip (see above).                           |
| Connection refused          | oMLX isn't running.                                            |
