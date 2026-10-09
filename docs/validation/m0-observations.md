# FrameGuard M0 technical observations

Recorded: 2026-10-08  
Status: **M0.2–M0.4 observations passed on exact FFmpeg/FFprobe 9.0.2**

## Reproduction and command record

Final acceptance run:

```text
$ python3 tools/validate_media.py --keep /tmp/frameguard-m0-9.0.2-final2
exit 0; 22/22 gate checks passed; 129 subprocess records emitted
```

The helper is standard-library Python 3.14.8. Every child uses an argv array,
`shell=False`, `stdin=DEVNULL`, concurrent stdout/stderr drains, deadlines,
bounded stdout/diagnostic tail/event lines, environment without `FFREPORT`,
`AV_LOG_FORCE_NOCOLOR=1`, process-group termination, two-second grace, kill
and reap. Its JSON command ledger records every generation, probe, oracle,
detector and fake-child argv, return code, elapsed time, cap and cancellation
state. Generated media remained under `/tmp`; it is not a project artifact.

The accepted detector argv shapes were:

```text
ffmpeg -nostdin -hide_banner -nostats -loglevel info -xerror -copyts
  -noautorotate -f mov -protocol_whitelist file -enable_drefs 0
  -use_absolute_path 0 -i INPUT -map 0:ABSOLUTE_INDEX
  -an -vf blackdetect=d=0.5:pic_th=0.98:pix_th=0.10
  -fps_mode passthrough -f null -

ffmpeg -nostdin -hide_banner -nostats -loglevel info -xerror -copyts
  -noautorotate -f mov -protocol_whitelist file -enable_drefs 0
  -use_absolute_path 0 -i INPUT -map 0:ABSOLUTE_INDEX
  -vn -af silencedetect=n=-60dB:d=2:mono=false -f null -
```

No detector argv contained seeking, `-shortest`, artificial truncation,
`-r`, downmix (`-ac`), resampling (`-ar`), or user-supplied filter fragments.
Probe used the same forced MOV/file-only/reference restrictions and bounded
JSON `-show_format/-show_streams` entries.

During helper development, one generation attempt failed because FFmpeg 9
does not accept `d=14/30` as a lavfi duration; the recipe now supplies the
equivalent decimal. Two exploratory runs emitted oversized frame/sample
detail and were rejected as evidence because terminal capture truncated
them. The final run emits summaries and a complete 129-entry ledger; no
authoritative output was lost.

## Probe and stream observations

- Baseline: H.264 High/yuv420p, coded 320x240,
  `avg_frame_rate=r_frame_rate=30000/1001`, AAC 48 kHz, indexes video 0/audio
  1, both default. Filename contained a space and `ü`.
- Video-only: selected video 0, audio null.
- Multi-track plus cover: streams were video 0/video 1/audio 2/audio 3/cover
  4. Defaults selected absolute video 1 and audio 3; indexes 0, 2 and attached
  picture 4 remained uninspected.
- Rotation MOV retained coded 320x240 and display-matrix rotation 90 degrees.
- Selection mapped exact absolute indexes; no fallback or all-stream claim.

## Black observations and decoded-frame oracle

All native runs returned 0 with attributed grammar:
`[Parsed_blackdetect_0 @ …] black_start:S black_end:E black_duration:D`.

| Fixture | Decoded black oracle | Native event | Result |
|---|---|---|---|
| interior | 1.000000–3.000000 | 1–3, duration 2 | exact |
| leading | 0–1 | 0–1 | exact |
| trailing | 1–3.000001 | 1–2.966667, duration 1.966667 | native final-frame-PTS understatement |
| all black | 0–2.000001 | 0–1.966667 | same limitation |
| 14-frame tail | 1–1.466666 | none | below 0.5 s |
| 15-frame tail | 1–1.500001 | none | accepted threshold-edge EOF miss |
| 16-frame tail | 1–1.533333 | 1–1.5, duration 0.5 | native endpoint is one frame early |

No endpoint was padded from average FPS or container duration. The A1 report
limitation is required on every completed black check.

## Silence observations and decoded-sample oracle

All native runs returned 0. PCM and AAC events matched their independently
decoded all-channel sample runs:

| Fixture | Decoded oracle | Native event |
|---|---|---|
| PCM interior | 1.0026667–4.0106667 | 1.002667–4.010667 |
| AAC interior | 1.0037917–4.0095417 | 1.003792–4.009542 |
| all silent | 0–3 | 0–3 |
| leading | 0–2.5000208 | 0–2.500021 |
| trailing | 1–3.5 | 1–3.5 |
| 1.99 s tail | 1–2.99 | none |
| 2.00 s tail | 1–3 | 1–3 |
| 2.01 s tail | 1–3.01 | 1–3.01 |

One active stereo channel produced no event; both-silent stereo produced
0–3. This confirms collective-channel behavior. Silence EOF closed at the
decoded sample end on this build.

## Timestamp and edit-list observations

The explicit edit-list fixture stored two `moov/trak/edts/elst` boxes. The
video list contained `segment_duration=2304000, media_time=1024`; the audio
list contained an empty edit (`media_time=-1`) followed by media time 0.
Decoded video PTS began 0; audio began 0.5. Raw detector events were black
1–3 and silence 1.502667–4.510667. With common format origin 0, normalized
times remain those raw values and preserve the 0.5-second A/V offset.

A nonzero-start MOV stored common format/video/audio start 2.0. Raw events
black 3–5 and silence 3.002667–6.010667 normalized once to black 1–3 and
silence 1.002667–4.010667.

A controlled negative-CTS MOV stored format/video origin -0.194010 while
audio began 0. Decoded video PTS began -0.194010. Raw black
0.805990–2.805990 normalized to 1–3. Raw silence
1.002667–4.010667 normalized to 1.196677–4.204677, preserving the audio
offset rather than independently resetting it. The fixture is explicitly
atom-patched test media, not a support claim about arbitrary edits.

An unknown-origin simulated payload produced `basis=source_pts`,
`origin=null`; no zero-relative origin or duration-derived endpoint was
invented.

## Completion, parser and process observations

Actual native observations:

- A packet-noised H.264 file under `-xerror` returned 183, latched an
  attributable decode error and remained incomplete.
- Native cancellation returned -15, `cancelled=true`, no closure event, and
  remained incomplete. A closure event is never required for cancellation
  and would not override it.

Simulated parser/process observations, kept separate from native claims:

- Early attributable decode error, 2 MB of rotating diagnostics, two valid
  closing events and simulated return 0 retained sticky decode failure;
  completion remained false.
- Signed/scientific `-1e-1 … +5e-1` parsed; an unattributed lookalike was
  ignored; nonfinite `nan` was rejected.
- Both-pipe flood capped stdout at 32 KiB and set
  `output_limit_exceeded=true` even though the child raced to return 0.
- SIGTERM-ignoring timeout child was killed after the two-second grace and
  reaped (`returncode=-9`, `timed_out=true`, elapsed 2.11 s).
- Cancellation child was terminated and reaped (`returncode=-15`).

Operational production defaults remain those in architecture.md: tool 10 s,
probe 30 s, each detector 600 s, probe stdout 8 MiB, diagnostic tail 1 MiB,
event line 64 KiB, findings 10,000, terminate grace 2 s. Cap loss makes the
owning check incomplete; authoritative events are never silently truncated.

## Offline/reference observations

- A manifest disguised as MP4 was rejected by the forced MOV demuxer,
  return 183.
- `http://127.0.0.1:9/not-contacted.mp4` was rejected before connection:
  `Protocol 'http' not on whitelist 'file'`, return 234.
- A controlled QuickTime `alis` external-reference fixture logged
  `Skipped opening external track … Set enable_drefs to allow this` with
  `-enable_drefs 0`, then failed decode, return 183.
- The enabled control attempted alias resolution but
  `-use_absolute_path 0` refused it and returned 183.

No external service was contacted. These controls establish safe rejection
for the exact argv/build, not a filesystem sandbox or general FFmpeg parser
sandbox.

## Source preservation

All 29 generated source fixtures had identical SHA-256 before and after
probing/detection. Representative pairs:

```text
baseline: 6de0bb8fa60a762ff3163d25344ee8524484d3ab13201058fe3cde3eaf31ed91
interior black: 9e25a4beafadd6cbd51cca0260abedae755f67bc91f413f12eb340c5c03136e4
PCM silence: 3483bbfe846151d8e4a183e6e4e5433f9ca213a4a870e80e57967125a7c0bd49
AAC silence: 8cbf552bf8c301c2c574758143cb841bee6202cfd05e0a98baa3306711794925
multi/cover: 258d7fdca2a8169e7ded787f234f60e1577ef6bff72f167b80ff167947751345
edit list: c93e7b5111cd8011eff7a1a4599d3144567510727cc634d1a30c69b947533c25
negative start: da633e55b9e0b9ee3b2b961f5bb0fc4e444c55c6a921062a9dd12ca9373be5a9
```

The helper never writes, chmods or deletes an input after generation.

See [m0-environment.md](m0-environment.md) for the exact host/build record
and [m0-decision.md](m0-decision.md) for the gate decision.
