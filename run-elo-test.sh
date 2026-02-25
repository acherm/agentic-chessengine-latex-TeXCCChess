#!/usr/bin/env bash
# Run an Elo assessment tournament: TeX Chess Engine vs Stockfish
set -euo pipefail

# Configuration (override via environment variables)
GAMES=${GAMES:-100}
STOCKFISH_ELO=${STOCKFISH_ELO:-1320}
# Default: Stockfish UCI_Elo calibration TC (120s + 1s increment).
# The UCI_Elo scale was tuned at this TC, anchored to CCRL 40/4.
# For a longer/stabler alternative, use: TIME_CONTROL="40/240+2"
TIME_CONTROL=${TIME_CONTROL:-"120+1"}
TAG="elo${STOCKFISH_ELO}"
PGN_FILE="${TAG}-games.pgn"
TEX_FILE="${TAG}-games.tex"
PDF_FILE="${TAG}-games.pdf"
NATIVE_TEX_FILE="${TAG}-games-native.tex"
NATIVE_PDF_FILE="${TAG}-games-native.pdf"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "  TeX Chess Engine Elo Assessment"
echo "========================================="
echo "Games: $GAMES"
echo "Stockfish Elo: $STOCKFISH_ELO"
echo "Time control: $TIME_CONTROL"
echo ""

# Check dependencies
missing=0
for cmd in cutechess-cli stockfish pdflatex python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd not found. Please install it first."
        missing=1
    fi
done
if [ "$missing" -eq 1 ]; then
    exit 1
fi

# Make UCI wrapper executable
chmod +x "$SCRIPT_DIR/chess-uci.py"

# Clean previous results and work directory
rm -f "$SCRIPT_DIR/$PGN_FILE"
rm -f "$SCRIPT_DIR/$TEX_FILE" "$SCRIPT_DIR/$PDF_FILE"
rm -f "$SCRIPT_DIR/$NATIVE_TEX_FILE" "$SCRIPT_DIR/$NATIVE_PDF_FILE"
rm -rf "$SCRIPT_DIR/.tex-uci-work"

echo "Starting tournament..."
echo ""

ROUNDS=$(( (GAMES + 1) / 2 ))
if [ "$ROUNDS" -lt 1 ]; then
    ROUNDS=1
fi

cutechess-cli \
    -engine name="TeX Chess Engine" cmd="$SCRIPT_DIR/chess-uci.py" proto=uci \
    -engine name="Stockfish" cmd=stockfish proto=uci \
        "option.Skill Level=0" option.UCI_LimitStrength=true option.UCI_Elo="$STOCKFISH_ELO" \
        "option.Move Overhead=200" \
    -each tc="$TIME_CONTROL" timemargin=500 \
    -rounds "$ROUNDS" -games 2 -repeat \
    -pgnout "$SCRIPT_DIR/$PGN_FILE" \
    -recover \
    -wait 50

echo ""
echo "Tournament complete!"
echo "PGN saved to: $SCRIPT_DIR/$PGN_FILE"
echo ""

# Generate LaTeX books
cd "$SCRIPT_DIR"

echo "Generating LaTeX book (Python FEN mode)..."
python3 pgn2latex.py "$PGN_FILE" "$TEX_FILE"
echo "Compiling PDF..."
pdflatex -interaction=nonstopmode "$TEX_FILE" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$TEX_FILE" >/dev/null 2>&1 || true

echo "Generating LaTeX book (native TeX engine boards)..."
python3 pgn2latex.py --native "$PGN_FILE" "$NATIVE_TEX_FILE"
echo "Compiling PDF..."
pdflatex -interaction=nonstopmode "$NATIVE_TEX_FILE" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$NATIVE_TEX_FILE" >/dev/null 2>&1 || true

echo ""
echo "========================================="
echo "  Results"
echo "========================================="
echo "PGN file:          $SCRIPT_DIR/$PGN_FILE"
echo "PDF (Python FEN):  $SCRIPT_DIR/$PDF_FILE"
echo "PDF (native TeX):  $SCRIPT_DIR/$NATIVE_PDF_FILE"
echo "========================================="
