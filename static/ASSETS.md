# Static assets — sources and licences

Every third-party file under `static/` is listed here with its pinned source,
licence and sha256. Nothing is fetched at runtime: the files were downloaded
once with `curl -fsSL` and are served from `/static/`.
`tests/js/assets.test.mjs` checks that every file in the tables below exists
and matches its hash, so a changed or missing file fails the suite.

## Fonts

Source: the `@fontsource` npm packages, version **5.3.0** for all three
families, latin subset, from
`https://cdn.jsdelivr.net/npm/@fontsource/<family>@5.3.0/`. Licence: SIL Open
Font License 1.1 (the licence text ships beside the files).

All the weights the plan asked for were available; no substitutions.

| File | Source URL | Version | Licence | sha256 |
|---|---|---|---|---|
| `fonts/libre-caslon-display-latin-400-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-display@5.3.0/files/libre-caslon-display-latin-400-normal.woff2 | 5.3.0 | OFL-1.1 | 84267e937417f10dff37df818c5ef7f1e9f2e6a703e03c2dd286d3320af53269 |
| `fonts/libre-caslon-text-latin-400-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-text@5.3.0/files/libre-caslon-text-latin-400-normal.woff2 | 5.3.0 | OFL-1.1 | 29310efc1007f608549e29ff78fa5ce8dffe0c1aa82c21b082d1de9dfc7334f0 |
| `fonts/libre-caslon-text-latin-400-italic.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-text@5.3.0/files/libre-caslon-text-latin-400-italic.woff2 | 5.3.0 | OFL-1.1 | 20eac03c053229ce982a337fce41f12e42e18d33c4e29d8e89188ef4fa970425 |
| `fonts/libre-caslon-text-latin-700-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-text@5.3.0/files/libre-caslon-text-latin-700-normal.woff2 | 5.3.0 | OFL-1.1 | 2819c345e64c715cc4235a5e9c3576351d28b4c0bbbeb934fcbd50ceab0406a0 |
| `fonts/atkinson-hyperlegible-latin-400-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/atkinson-hyperlegible@5.3.0/files/atkinson-hyperlegible-latin-400-normal.woff2 | 5.3.0 | OFL-1.1 | d64ba838ef5472bba248620ec4fd8b5aa7cf0db2908e0bb230600caf279ba7bc |
| `fonts/atkinson-hyperlegible-latin-700-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/atkinson-hyperlegible@5.3.0/files/atkinson-hyperlegible-latin-700-normal.woff2 | 5.3.0 | OFL-1.1 | 140e2bd25a7315c8a062508391426b0d8c3297400c947b8d847be28f73a199f0 |
| `fonts/LICENSE-libre-caslon-display.txt` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-display@5.3.0/LICENSE | 5.3.0 | OFL-1.1 (text) | 78c9f56e0d8a7ad7b9d26842a8eae728337a8671d8ddc6e889fa10645935dc7b |
| `fonts/LICENSE-libre-caslon-text.txt` | https://cdn.jsdelivr.net/npm/@fontsource/libre-caslon-text@5.3.0/LICENSE | 5.3.0 | OFL-1.1 (text) | f655e804b05a2ed71ec88ef3006394e51972ec20546d4a14328a43c53ccd2607 |
| `fonts/LICENSE-atkinson-hyperlegible.txt` | https://cdn.jsdelivr.net/npm/@fontsource/atkinson-hyperlegible@5.3.0/LICENSE | 5.3.0 | OFL-1.1 (text) | e137caeef2ff7c04fbf87078ad09cf3dcba8a3a58a4aa4e2f399d42c50bc4b18 |

## Pieces

Source: the Lichess repository `lichess-org/lila`, pinned at commit
**`d52ae7f9177bb1c5eb3536968284d83efdb133aa`**, folder `public/piece/cburnett/`,
from
`https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/`.
Author: Colin M.L. Burnett. Credit shown in the settings panel:
"Pieces: cburnett, CC BY-SA 3.0" (see `pieces/cburnett/LICENSE.md`).

Licence note: the design credits the set as CC BY-SA 3.0 (the Wikimedia Commons
original). Lichess's `COPYING.md` at the pinned commit lists its copy of
`public/piece/cburnett` as GPLv2+. Both are recorded in
`pieces/cburnett/LICENSE.md`; which credit to show is the project owner's call.

| File | Source URL | Version | Licence | sha256 |
|---|---|---|---|---|
| `pieces/cburnett/wK.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wK.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 09837f1f99dae2d05c2a0bfb5ce0fb9f37a95b124de44f428a08ae18d7b7c557 |
| `pieces/cburnett/wQ.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wQ.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 9c0a960b360e08cea48eedab54e852107145de289b81a82fe27942045e2ab665 |
| `pieces/cburnett/wR.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wR.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 05746153e11de3ff4a43d6725f704e226e5d5b49c6ff170ed598d3e9883f2cd5 |
| `pieces/cburnett/wB.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wB.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 8bf4f38cc170686775f81158934301942b07e3f1162e76c6305e76d66aaa0910 |
| `pieces/cburnett/wN.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wN.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 43d8bed9cd40836335072a20f52d30237e6e2cbe304ffb13e258fa1d576c156a |
| `pieces/cburnett/wP.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/wP.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | a8bd79f344ea69a577cdd7b11cbab7bbebfc157cce01c6d29b8f2edf1c44068e |
| `pieces/cburnett/bK.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bK.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 2dc3caba39a67a707ebc27f4e41b727dd5252f4f49da695fc15cc2589dd92a47 |
| `pieces/cburnett/bQ.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bQ.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 2d0162d1fe776ac5a4d307d4f6e5960804273edc0d3743f1c97a158f5a64c4b1 |
| `pieces/cburnett/bR.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bR.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 5928b86919ae815f5d35dea8a25f5a84c3f8839468a137e429d42f618185cbcd |
| `pieces/cburnett/bB.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bB.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 48ff9dba84dae861b1a81ac58f4647e05cee8a827acad1618bf11beaedcce60d |
| `pieces/cburnett/bN.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bN.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 72e1565fbc9024015dcb6ee28d918c876523119f6f552c0a40d3118c13a67e13 |
| `pieces/cburnett/bP.svg` | https://raw.githubusercontent.com/lichess-org/lila/d52ae7f9177bb1c5eb3536968284d83efdb133aa/public/piece/cburnett/bP.svg | d52ae7f | CC BY-SA 3.0 / GPLv2+ | 93e11e46deceff0768211a28df3e39c6d3427aa172bdb5e3928b025bd2858587 |

## Puzzles (data, outside `static/`)

The tactics puzzles in `puzzles/*.json` (project root, not under `static/`)
come from the Lichess puzzle database, https://database.lichess.org/#puzzles,
released under **CC0 1.0** (public domain). They were curated once by
`scripts/curate_puzzles.py` from
`https://database.lichess.org/lichess_db_puzzle.csv.zst`; the date, the filter
and the seed are recorded in `puzzles/LICENSE.md`. Positions and moves are
unchanged. CC0 asks for no credit, but the app shows "Puzzles from the Lichess
puzzle database, released under CC0." under the Tactics list and on the puzzle
screen. Nothing is downloaded at runtime.

## Project-made files

- `logo.svg`: the JustChess mark (2×2 checker in a walnut tile with a brass
  inlay), drawn for this project. Not third-party; no hash pinned.
- `js/vendor/qrcode.js`: the QR code encoder used by the share dialog
  (ADR-008). Licence: **MIT**, with the licence text in the file's header.
  Origin: written for JustChess in 2026 from ISO/IEC 18004:2015 (byte mode,
  error correction levels L and M, versions 1–10, Reed–Solomon, format and
  version information, the eight masks with the standard penalty). It is not a
  copy of another library and nothing was downloaded. It sits in `vendor/` so
  it can be replaced by an upstream encoder without touching
  `js/qr-canvas.js`, which is its only caller. It makes no network request.
