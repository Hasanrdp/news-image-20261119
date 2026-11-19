[![make.fun](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/Hasanrdp/news-image-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/Hasanrdp/news-image-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119)

# The Daily Globe — 19 November 2026

A one-page newspaper front page summing up the world's news of
**Thursday, 19 November 2026**, drawn at run time by a pure-stdlib
Python 3 program. No network, no files besides this repository, no clock:
every run writes the same bytes to `entry.png`.

## The day's stories

- **Grand Theft Auto VI launches worldwide** — after a 13-year wait,
  gamers enter Vice City as the global rollout begins.
- **Democrats nominate Hakeem Jeffries for US House Speaker** — he would
  be the first Black Speaker.
- **Cyclone Akvan nears India's east coast** — landfall expected between
  Machilipatnam and Puri.
- **Voyager 1 reaches one light-day from Earth** — NASA to confirm the
  milestone today, nearly 50 years after launch.
- **EU plans a 45-billion-euro loan for Ukraine** — Brussels lends Kyiv
  45 billion euros.
- **US–Iran strikes widen in the Gulf** — Iran hit bases in Kuwait and
  Bahrain; the US struck back.
- **Also today:** the ICJ rules on the Myanmar genocide case; Pew finds
  Islam set to be the largest faith by 2035; Fed minutes point to more
  rate rises; Trump, Xi and Putin meet in Shenzhen.

## How it works

`main.py` draws the whole front page with a small built-in 5×7 bitmap
font — masthead, headlines, decks and six small illustrations (a Vice
City sunset, the US Capitol, a cyclone, Voyager 1, the EU stars and Gulf
shipping) — and encodes the result as a PNG with only the Python
standard library (`zlib` + `struct`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (1024×1024, about 22 KB). Run it twice and
the two files are byte-identical.

## Entry

Competition: [news-image-20261119](https://make.fun/bounty/news-image-20261119)
on [make.fun](https://make.fun) — $250 shared by the 50 best entries.
License: MIT.
