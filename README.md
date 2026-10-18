# PokéRadar — the Pokémon card opportunity desk

A deployable, mobile-friendly **personal/noncommercial** research dashboard for English-language Pokémon chase cards released from **2017 to the present**. Designed for **raw/ungraded cards with TCGplayer-derived market prices under $100**.

**What you get**

- A curated watchlist of 153 cards across Sun & Moon, Sword & Shield, Scarlet & Violet and Mega Evolution eras, including IR, SIR, alternate arts, Galarian Gallery, select trainer galleries and earlier chase cards.
- A scheduled server-side refresh using the documented **TickerMint API**, with 7-, 30- and 90-day movements, drawdowns and a 0–100 opportunity score.
- **Buy Now / Wait to Buy / Watch** rule-based signals that refuse to recommend on missing or stale data.
- Click card artwork or its name to open **TCGplayer**: a precise TCGplayer search by name, set and collector number is always available; a direct product link is used only when supplied by the data provider. Never assume TickerMint IDs are TCGplayer IDs. Click the rest of a card for its price chart and signal details.
- Rarity, year, search and sort controls; saved-card favorites stored in that browser; CSV export.
- A GitHub Actions workflow that runs daily and deploys to GitHub Pages; no paid hosting or API key is required for a personal site.

## Important limits

1. **Not yet live when first downloaded**: `site/data.json` has **no fabricated market prices**. Price cards remain marked `Awaiting sync` until GitHub Actions can reach the upstream API. I verified the provider's published endpoint documentation, but could not complete a live API scan from this environment (outbound networking was restricted).
2. **This scans a curated 153-card scouting roster**, not every IR/SIR ever printed. Add entries to `scripts/roster.json` as new sets release. Some tracked cards exceed $100; they drop out of the live eligible board when the API confirms their value.
3. **Not Near Mint transaction quotes.** TickerMint reports TCGplayer-derived *market aggregates per printing*. They do not guarantee a seller's Near Mint condition, available listing, tax, shipping or fees. Confirm every purchase on TCGplayer.
4. **Hype is an editorial 0–100 fan-appeal proxy**, based on broad familiarity with Pokémon fandom, not measured Google Trends, transaction volume or social media. The score is subjective, not empirical evidence or a predictive model. Buy/Wait is a heuristic, not advice or a promise of price appreciation.
5. History from this provider begins **February 2024**; a 2017 card does not have its full lifetime history here. No sold-volume, reprint probability, or liquidity feed is currently integrated.
6. TickerMint's free API is **personal and noncommercial** with visible credit/link requirements. A commercially operated site needs the provider's commercial license; don't resell these prices, publish a standalone price feed or republish its full archive. See [the provider's terms](https://tickermint.cards/developers).
7. No automatic refresh is possible until this code has been deployed to an account you control. Browser **Refresh** reloads the last published snapshot; it does not scrape TCGplayer or start a new job. In GitHub, manually run **Actions → Update Pokémon prices and publish website → Run workflow** for an on-demand new scan.

## Put the website online — GitHub Pages

1. Create a **new GitHub repository** (for example `pokemon-card-radar`) and upload **the contents of this folder** so that `.github/`, `scripts/`, `site/` and `README.md` are at the repository root. GitHub's **Add file → Upload files** handles the contents; uploading the ZIP itself does *not* unzip it.
2. In **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** if needed so Actions can save the non-price `scripts/resolved_ids.json` lookup cache.
3. In **Settings → Pages → Build and deployment**, set **Source: GitHub Actions**.
4. Go to **Actions → Update Pokémon prices and publish website → Run workflow**. The initial run discovers card IDs and histories. It can take several minutes (the updater deliberately throttles requests to respect API rate limits). The workflow creates a published GitHub Pages site and shows its URL in the deployment summary, typically `https://YOUR-USERNAME.github.io/pokemon-card-radar/` (this example isn't your live URL until you deploy).
5. It will run every day at about **09:23 UTC** (GitHub schedules may be delayed). Use the site's Refresh button to load the latest deployed snapshot. New card IDs are cached in the repository, but **raw prices/history are not committed to Git** — only delivered with the Pages website build.
6. Optional: In repository **Settings → Secrets and variables → Actions**, create `TICKERMINT_KEY` for a paid plan; the free personal plan does not need it.

You may use a custom domain via the repository's Pages settings. The underlying GitHub Pages host is public: do **not** add private purchase details or secrets to the site code.

## Run the preview locally

```bash
cd pokemon-card-radar
python -m http.server 8080 --directory site
```

Visit `http://localhost:8080/`. The first-run preview shows scouting cards with `Awaiting sync` rather than invented recommendations.

To collect prices locally, after installing `requests`:

```bash
python -m pip install requests
python scripts/update_data.py
```

Open a local server and click Refresh. Local execution requires external internet access to `https://api.tickermint.cards`.

## Methodology

- Input: dated, per-printing TCGplayer-derived *market* prices from TickerMint (last 120 observations are used; rolling high uses last 90 days).
- **30D movement** = (last observed market / available market ~30 days earlier − 1) × 100.
- **90D drawdown** = (last observed market / highest observed market in the past 90 days − 1) × 100.
- **Buy Now**: 90D drawdown ≤ −18%, 30D change ≤ −7%, 7D change between −3% and +4%, editorial fan score ≥ 75, and ≥ 28 observed days.
- **Wait**: 90D drawdown ≤ −12% or 30D change ≤ −10%, and 7D change < −3% or a steep falling 30D trend.
- **Watch**: observed market ≤ $100 but no conclusive buy/wait pattern, or insufficient history.
- **Score** = 37% drawdown magnitude + 26% fan-appeal proxy + 27% latest-week trend quality + 10% maturity proxy.
- A stale record (last price dated more than 3 days ago) is **excluded from the live eligible board**.

The classification rules live in `scripts/update_data.py` and are intended as an explainable first-pass screen, not a tested forecasting model. Hype scores are stored in `scripts/roster.json` and can be edited. The default dashboard includes `Other` to cover earlier years without mislabeling pre-Scarlet & Violet IR/SIR cards.

## Technical structure

```
site/index.html          static accessible responsive UI
site/styles.css          dashboard design
site/app.js              filters, card details, links, mini charts, favorites, CSV
site/data.json           first-sync empty snapshot, generated on each publish
scripts/roster.json      target list, exact card names/sets/numbers, fan proxies
scripts/resolved_ids.json verified TickerMint/TCGplayer product IDs (no price history)
scripts/update_data.py   server-side TickerMint API updater / scorer
.github/workflows/daily-update.yml   daily cron, refresh + Pages deployment
```

This is a one-file static frontend with a server-side data publisher, so it avoids TickerMint's browser CORS restriction. The published JSON is only a bounded internal site snapshot — not a substitute for the underlying pricing API.

## Data providers

- [TickerMint's developer docs and license](https://tickermint.cards/developers)
- [TickerMint Python and history examples](https://tickermint.cards/developers/python)
- [TCGplayer](https://www.tcgplayer.com/)

Independent hobby project; not affiliated with The Pokémon Company, Nintendo, TCGplayer, or TickerMint. Do not make buying decisions from a heuristic alone.
