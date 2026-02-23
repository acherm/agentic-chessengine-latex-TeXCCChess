# TeXCCChess

**A complete chess engine written entirely in pure TeX** (~2,100 lines of TeX macros).

All game logic — board representation, move generation, legal move validation, search, and evaluation — runs inside TeX at compile time. No Lua, no external programs for the chess logic itself. Just `\count` registers, `\csname` tables, and a lot of `\expandafter`.

Estimated strength: **~1300 Elo** (measured: 46% score vs Stockfish 1320 over 100 games, time control 40/60+1).

## Features

- Complete chess rules: castling, en passant, promotion, check/checkmate/stalemate detection
- Depth-3 negamax search with alpha-beta pruning
- Quiescence search (1-ply captures) at leaf nodes
- Piece-square tables (Simplified Evaluation Function)
- MVV-LVA move ordering
- 4 strength levels: random, greedy, depth-2, depth-3 + quiescence
- UCI protocol support for tournament play against other engines
- Interactive terminal mode
- Test suite (23 assertions covering move generation, evaluation, search, and game rules)

## How to Play

### Option 1: Play by recompiling

Edit `chess-game.tex` — add your moves as `\playmove{e2e4}` lines, then recompile:

```bash
pdflatex chess-game.tex
```

The engine responds automatically. Open the PDF to see the board, move history, and game status. Add another `\playmove{...}` and recompile for the next turn.

Configuration (in `chess-game.tex`):
```latex
\def\gameseed{42}      % Change for a different game
\enginestrength=3       % 0=random, 1=greedy, 2=depth-2, 3=depth-3+quiescence
```

### Option 2: Interactive terminal

```bash
bash chess-interactive.sh
```

Play in the terminal with a text board display. Enter moves in coordinate notation (`e2e4`, `g1f3`). Type `help` for commands.

### Option 3: UCI protocol (tournament play)

```bash
python3 chess-uci.py
```

The UCI wrapper lets the engine play in tournaments via [cutechess-cli](https://github.com/cutechess/cutechess) or any UCI-compatible GUI.

## Files

| File | Description |
|------|-------------|
| `chess-engine.tex` | The engine (~2,100 lines of TeX) |
| `chess-game.tex` | Play-by-recompile document |
| `chess-test.tex` | Test suite |
| `chess-uci.py` | UCI protocol bridge (Python) |
| `chess-uci.tex` | UCI-mode TeX document |
| `chess-interactive.sh` | Interactive terminal mode |
| `run-elo-test.sh` | Tournament runner (vs Stockfish) |
| `pgn2latex.py` | PGN to LaTeX book converter |

## Technical Details

- **Board**: `\count` registers 200–263 (one per square, a1=index 1, h8=index 64)
- **Piece encoding**: 1=wP, 2=wN, 3=wB, 4=wR, 5=wQ, 6=wK; negatives for black
- **Search**: 3-ply negamax + 1-ply quiescence, alpha-beta pruning, MVV-LVA move ordering
- **Evaluation**: material + piece-square tables (384 `\csname` entries precomputed at load time)
- **State stack**: `\count10000+` registers for make/unmake move (9 values per depth)
- **File/rank lookups**: precomputed `\csname` tables to avoid `\numexpr` rounding pitfalls
- **Speed**: ~1–3 seconds per move at depth 3

## Running the Tests

```bash
pdflatex chess-test.tex
```

Check the log output for PASS/FAIL results:

```bash
grep -E "PASS|FAIL" chess-test.log
```

## Running an Elo Tournament

Requires [cutechess-cli](https://github.com/cutechess/cutechess), Stockfish, and Python 3:

```bash
bash run-elo-test.sh
```

Configuration via environment variables:
```bash
GAMES=100 STOCKFISH_ELO=1320 TIME_CONTROL="40/60+1" bash run-elo-test.sh
```

## Prerequisites

- **pdfLaTeX** (any TeX distribution: TeX Live, MiKTeX)
- **chessboard** LaTeX package (for board display in PDFs — not needed for engine logic)
- For tournaments: Python 3, cutechess-cli, Stockfish

## How It Was Built

This engine was entirely AI-generated using [Claude Code](https://claude.com/claude-code) (agentic coding). A human guided the process through iterative prompting — the TeX code itself was written by Claude.
