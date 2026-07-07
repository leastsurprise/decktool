# decktool

Parametric design, layout optimisation, and cut-planning scripts for refurbishing a timber deck, written in Python with [CadQuery](https://cadquery.readthedocs.io/). Built for a real project — a Garapa hardwood deck approximately 3975mm × 2255mm on a 12-joist H3.2 subframe — but all dimensions are parameters at the top of each script.

This is a **refurbishment** tool, not a from-scratch build: the existing bearers and posts remain in place, and the scripts plan everything from the joists up — joists, decking boards, picture frame, and fascia. That's why the models start at joist level, and why the deck's overall footprint is treated as a fixed constraint rather than a design variable.

The scripts do three jobs at once:

1. **Layout optimisation** — deck boards are laid in rows, each row made of two boards butt-joined over a joist. The join positions are chosen by Monte Carlo simulation (5,000 random candidate layouts) subject to aesthetic and structural rules, then scored for left/right visual balance. The best layout wins.
2. **Stock management and cut planning** — a stock manager allocates every cut from a defined inventory of plank lengths (10 each of 3600/3300/3000mm by default), reusing offcuts wherever possible, and emits a plank-by-plank cut list with scrap figures and a construction placement sequence. See `cut_and_layout` for example output.
3. **3D visualisation** — the joists, frame, infill boards (and in later variants, fascia, sister blocks, and screw positions) are rendered as a CadQuery assembly so the design can be inspected before a single board is cut.

## Repository contents

The scripts are progressive iterations of the same deck model — each adds detail to the previous one. The current working choice (per the project notes) is the **sandwich joists** approach, which suits this deck and keeps costs down.

| File | What it adds |
| --- | --- |
| `main.py` | The base model: joists, mitered picture frame, infill rows, layout simulation, `StockManager`, cut & layout report, 3D render. |
| `sister_joists.py` | Adds sister-joist inserts: 45×90mm blocks cut from joist offcuts, fixed beside the join joist so both board ends land on solid timber. Includes extensive TODO notes on fascia/drip-edge design. |
| `fascia.py` | Adds vertical Garapa fascia boards to the north, east, and west faces, tucked under a 19mm picture-frame overhang to form a drip edge, with a 12mm ventilation gap below the decking. |
| `sandwich_joists.py` | The preferred variant: each butt join is supported by **two** sister blocks sandwiching the join joist (one each side). Also enforces a minimum board length during layout generation and exports the assembly to `deck_layout.step`. |
| `combo.py` | Combines picture frame + fascia + sister blocks + screw placement into one model, and produces the most detailed report: per-plank cut lists, sister-block usage, remaining stock tally in linear metres, and total fastener count. |
| `collision_detection.py` | QA check: imports `deck_layout.step` and boolean-intersects every pair of solids, reporting any overlap greater than 0.1mm³. |
| `cut_and_layout` | Example cut & layout report produced by `main.py`. |

## How the layout optimisation works

Each infill row needs one butt join, placed over one of the interior joists (J3–J10). A random candidate layout is generated row by row under these rules:

- **Vertical lockout** — once a joist hosts a join, it can't host another for the next `vertical_row_gap` rows (default 3), so joins don't stack visually.
- **Horizontal stagger** — consecutive rows must place their joins at least `horizontal_joist_gap` joists apart (default 2).
- **Minimum board length** (`sandwich_joists.py`) — candidates producing any board shorter than `min_board_len` are discarded outright.

Each surviving candidate is scored: joins are split into left-of-centre and right-of-centre groups, and the score is the imbalance of their mean offsets plus both variances plus the variance difference — lower is better, rewarding layouts that scatter joins evenly and symmetrically. 5,000 candidates are simulated and the best score is kept.

## Stock management

`StockManager` / `DeckStockManager` allocate each required cut using a smallest-offcut-first strategy: sort existing offcuts by length and take the first that fits; otherwise open the shortest new plank that fits. Remainders above a reuse threshold go back into the offcut pool. Sister blocks are allocated from a separate stock of joist offcuts (e.g. 6–10 pieces of 1300mm). If stock runs out, the script raises an exception naming the cut that couldn't be satisfied — so you find out at design time, not at the timber yard.

## Requirements

- Python 3
- [CadQuery](https://cadquery.readthedocs.io/) 2.x, including `cadquery.vis` for the interactive `show()` viewer:

```bash
pip install cadquery
```

## Usage

Edit the parameters in section 1 of the script you want (deck dimensions, board sizes, gaps, stock inventory), then run it:

```bash
python sandwich_joists.py     # preferred variant; writes deck_layout_report.txt and deck_layout.step
python collision_detection.py # then verify no solids overlap in the exported STEP
```

Each run re-randomises the simulation, so expect a different (but comparably scored) layout each time. Reports are written alongside the script (`cut_and_layout` or `deck_layout_report.txt`) and also printed to stdout.

## Design notes baked into the parameters

- 6.4mm gaps between rows and 3mm between board ends allow the Garapa to swell with moisture.
- Picture-frame boards overhang the subframe by the board thickness (19mm) so the fascia tucks under a drip edge.
- 12mm ventilation gap between fascia top and decking underside.
- Screw positions are computed per joist crossing and per butt join (with configurable edge and butt offsets), giving a total fastener count for purchasing.

## Known issues

- `main.py` contains an accidental duplicated paste: the file's contents repeat from around line 22 (`...on1GdGiimport cadquery...`), so it will not run as-is. The second copy (from line 23) is the cleaner one; the file needs a manual tidy-up. The later variants are unaffected.
- `sister_joists.py` carries TODO placeholders (`cladding_protrusion`, `gap_cladding_to_deck`) awaiting real-world measurements.
- Layout selection is stochastic — pin `random.seed(...)` if you need a reproducible cut list.

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Michael T. Emslie.
