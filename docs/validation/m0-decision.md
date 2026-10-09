# FrameGuard M0 gate decision

Recorded: 2026-10-08  
Verdict: **M0 pass — go for M1 only after explicit owner authorization**

## Task status

| Task | Status | Evidence |
|---|---|---|
| M0.1 runtime and capability inventory | Complete | macOS arm64, Python 3.14.8, exact FFmpeg/FFprobe 9.0.2 and required capabilities recorded under owner-amended A3 |
| M0.2 baseline and probe experiments | Complete | 29 temporary fixtures; rational rates, video-only, MOV/MP4, rotation, defaults, multiple tracks and attached-picture exclusion observed |
| M0.3 detector/timestamp/failure contract | Complete | decoded oracles, native EOF edges, explicit edit lists, signed/nonzero starts, `-xerror`, cancellation and parser states validated |
| M0.4 offline/operational safety gate | Complete | file-only/forced-MOV/reference rejection, caps, timeout/flood/cancellation cleanup and unchanged hashes validated |

M1–M3 were implemented later as the local scan on this Mac. This file remains the M0 gate record only.

## Passed observations

- Exact environment and 22/22 M0 gate checks passed in the final helper run.
- Probe inventory selected default real video/audio by absolute index and
  excluded attached picture.
- Black and silence native events matched decoded oracles within accepted
  tolerances, including the approved black EOF understatement/miss.
- Stored `elst` structure, decoded PTS, nonzero and negative common origins,
  unequal offsets and one-origin normalization were observed.
- Native decode failure/cancellation and simulated sticky-error/tail rotation
  remained incomplete.
- Forced MOV, file-only protocol and disabled external-reference controls
  rejected manifest, URL and QuickTime alias attempts.
- All 29 fixture SHA-256 values were unchanged.

## Unresolved risks

The gate passes with these residual limitations:

- A3 was materially narrowed by the owner to exact FFmpeg/FFprobe 9.0.2 on
  this macOS arm64 host. There is no FFmpeg 6.1+, Linux, Intel macOS, Windows
  or cross-build compatibility evidence.
- R01 remains an accepted product limitation: trailing black ends at final
  picture PTS and a true 15-frame/0.5-second EOF run can be missed.
- R04 remains: attributed info-log grammar is not a stable formal FFmpeg API.
- R05 remains: caps and cleanup are not a CPU/memory/filesystem sandbox.
- R06 remains by A2: alternate tracks are inventoried but uninspected.
- R09 remains bounded: file-only protocols and disabled drefs are defense in
  depth, not filesystem isolation or a native-parser sandbox.
- The negative-PTS and QuickTime alias fixtures are controlled atom-patched
  media. They establish the tested semantics, not exhaustive malformed-media
  coverage.
- Native cancellation emitted no closing detector event in this run. The
  validated rule is still that cancellation state overrides any event; the
  sticky closing-event/zero-return case was simulated and is labeled as such.

## Decision

M0 passes under the amended exact-build contract. The local tree later added
the installable scan, metadata checks, black and silence detection, and
JSON/HTML reports. Support remains exact FFmpeg/FFprobe 9.0.2 on this macOS
arm64 host. No 6.1 floor, Linux media run, or release tag is claimed here.

## Evidence links

- [Environment and capabilities](m0-environment.md)
- [Technical observations](m0-observations.md)
- [Gate decision](m0-decision.md)
