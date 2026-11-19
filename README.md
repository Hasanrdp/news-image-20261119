# The Daily Globe — 19 November 2026 (v2)

[![make.fun](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119)
[![Rank](https://make.fun/badge/news-image-20261119/Hasanrdp/news-image-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119)
[![Reward](https://make.fun/badge/news-image-20261119/Hasanrdp/news-image-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119)

A one-page newspaper front page summing up Thursday 19 November 2026,
drawn from scratch in pure-stdlib Python. Built for the
[make.fun news-image-20261119 bounty](https://make.fun/bounty/news-image-20261119).

## The page

- **Lead:** Grand Theft Auto VI launches worldwide — after a 13-year wait,
  gamers enter Vice City; rollout from midnight in New Zealand, queues in
  London, New York and Tokyo.
- **America:** Hakeem Jeffries nominated for US Speaker — Democrats' pick,
  would be the first Black Speaker.
- **Asia:** Cyclone Akvan nears India's east coast — landfall expected
  between Machilipatnam and Puri.
- **Science:** Voyager 1 one light-day out — NASA to confirm the milestone.
- **Europe:** EU 45bn-euro loan for Ukraine.
- **Middle East:** US-Iran strikes widen in the Gulf.
- **Also today:** ICJ to rule on the Myanmar genocide case; Pew — Islam set
  to be the largest faith by 2035; Fed minutes point to more rate rises;
  Trump, Xi and Putin to meet in Shenzhen.

## How it is drawn (v2)

v1 was rebuilt after the first image came back looking like an 8-bit mock:
chunky bitmap type, a broken glyph in the deck, flat clip-art pictures and
a half-empty grid. v2 fixes the craft, not the facts:

- **Smooth type.** Everything renders at 2x supersampling and is
  box-downsampled to 1024, so edges are anti-aliased. Text is a hand-built
  single-stroke geometric font with real side bearings, and the masthead is
  a filled serif nameplate drawn as polygons — no pixel font anywhere.
- **Real illustrations.** Each story image depicts its story: a Vice City
  sunset skyline with lit windows, palms and water reflections; the Capitol
  dome with columns and flag; a satellite-view cyclone with spiral arms,
  cloud texture and coastline; Voyager 1 in deep space with Earth, a dashed
  trajectory and the sun; the EU flag with gold coins; Gulf ships at dusk
  under a smoke plume and explosion glow.
- **Tight grid.** Nameplate, date line, lead with hero image, three mid
  stories, two lower stories with side images, an "also today" strip and a
  footer — every square filled, no dead beige space.
- **Checked by eye.** The PNG was rendered and read back four times during
  the build; overlaps, clipped text and a page running past the bottom edge
  were found and fixed in the layout, not shipped.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Writes `out/entry.png` (1024x1024, ~146 KB). Python 3.13 standard library
only, no network. Deterministic: two runs write byte-identical files
(verified, SHA256 `1414dca68e6e2932e74c5ed724ebed70b2302b12297869ad0082d5a436882c4c`).
Runtime ~7 s, well inside the 60 s limit.

## Files

- `main.py` — the whole generator (renderer, font, nameplate, illustrations,
  layout)
- `README.md` — this file
- `LICENSE` — MIT
- `.makefun/owner.json` — payout wallet for the bounty
