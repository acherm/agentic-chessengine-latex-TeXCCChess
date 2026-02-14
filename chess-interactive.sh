#!/bin/bash
# chess-interactive.sh -- Interactive terminal chess against the TeX engine
# Usage: bash chess-interactive.sh

set -e

MOVES_FILE="interactive-moves.txt"
TEX_FILE="interactive-game.tex"
OUTPUT_FILE="engine-output.dat"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

newgame() {
    > "$MOVES_FILE"
    rm -f "$OUTPUT_FILE"
    echo -e "${GREEN}New game started! You play White.${NC}"
    echo "Enter moves in coordinate notation: e2e4, d7d5, etc."
    echo "Commands: quit, new, board (open PDF), help"
    echo ""
    display_start_board
}

display_start_board() {
    echo "8  r n b q k b n r"
    echo "7  p p p p p p p p"
    echo "6  . . . . . . . ."
    echo "5  . . . . . . . ."
    echo "4  . . . . . . . ."
    echo "3  . . . . . . . ."
    echo "2  P P P P P P P P"
    echo "1  R N B Q K B N R"
    echo "   a b c d e f g h"
    echo ""
}

generate_tex() {
    cat > "$TEX_FILE" <<'HEADER'
\documentclass{article}
\usepackage{chessboard}
\input{chess-engine}
\begin{document}
\initboard
\initgamestate
HEADER

    # Add all moves
    while IFS= read -r move; do
        if [ -n "$move" ]; then
            echo "\\playmovealiased{$move}" >> "$TEX_FILE"
        fi
    done < "$MOVES_FILE"

    cat >> "$TEX_FILE" <<'FOOTER'
\showboard
\end{document}
FOOTER
}

compile_and_read() {
    local move="$1"
    echo "$move" >> "$MOVES_FILE"

    generate_tex

    # Compile silently
    if ! pdflatex -interaction=nonstopmode "$TEX_FILE" > /dev/null 2>&1; then
        echo -e "${RED}TeX compilation error. Check $TEX_FILE.log for details.${NC}"
        # Remove the bad move
        sed -i '' '$d' "$MOVES_FILE" 2>/dev/null || sed -i '$d' "$MOVES_FILE"
        return 1
    fi

    # Read output
    if [ ! -f "$OUTPUT_FILE" ]; then
        echo -e "${RED}No engine output generated.${NC}"
        sed -i '' '$d' "$MOVES_FILE" 2>/dev/null || sed -i '$d' "$MOVES_FILE"
        return 1
    fi

    # Check for errors
    if grep -q "^ERROR:" "$OUTPUT_FILE"; then
        local err
        err=$(grep "^ERROR:" "$OUTPUT_FILE" | head -1 | sed 's/^ERROR://')
        echo -e "${RED}$err${NC}"
        # Remove the bad move
        sed -i '' '$d' "$MOVES_FILE" 2>/dev/null || sed -i '$d' "$MOVES_FILE"
        return 1
    fi

    # Display engine move
    local engine_move
    engine_move=$(grep "^ENGINEMOVE:" "$OUTPUT_FILE" | head -1 | sed 's/^ENGINEMOVE://')
    if [ -n "$engine_move" ] && [ "$engine_move" != "none" ]; then
        echo -e "${BLUE}Engine plays: ${YELLOW}$engine_move${NC}"
    fi

    # Display board
    echo ""
    local in_board=0
    while IFS= read -r line; do
        if [[ "$line" == "BOARD:" ]]; then
            in_board=1
            continue
        fi
        if [ $in_board -eq 1 ]; then
            echo "  $line"
        fi
    done < "$OUTPUT_FILE"
    echo ""

    # Check game status
    local status
    status=$(grep "^STATUS:" "$OUTPUT_FILE" | head -1 | sed 's/^STATUS://')
    case "$status" in
        white_wins)
            echo -e "${GREEN}Checkmate! White wins!${NC}"
            return 2
            ;;
        black_wins)
            echo -e "${GREEN}Checkmate! Black wins!${NC}"
            return 2
            ;;
        draw)
            echo -e "${YELLOW}Game drawn!${NC}"
            return 2
            ;;
    esac

    return 0
}

# Main loop
echo "============================="
echo "  Chess Engine in Pure TeX"
echo "============================="
echo ""

newgame

game_active=1

while true; do
    if [ $game_active -eq 1 ]; then
        echo -ne "${GREEN}Your move: ${NC}"
    else
        echo -ne "${YELLOW}(game over) ${NC}"
    fi
    read -r input

    case "$input" in
        quit|exit|q)
            echo "Goodbye!"
            exit 0
            ;;
        new|reset)
            newgame
            game_active=1
            continue
            ;;
        board|pdf)
            if [ -f "interactive-game.pdf" ]; then
                open "interactive-game.pdf" 2>/dev/null || xdg-open "interactive-game.pdf" 2>/dev/null || echo "Cannot open PDF viewer"
            else
                echo "No PDF generated yet. Make a move first."
            fi
            continue
            ;;
        help|h|\?)
            echo "Commands:"
            echo "  e2e4    - Make a move (coordinate notation)"
            echo "  new     - Start a new game"
            echo "  board   - Open the PDF board"
            echo "  quit    - Exit"
            continue
            ;;
        "")
            continue
            ;;
    esac

    if [ $game_active -ne 1 ]; then
        echo "Game is over. Type 'new' to start a new game."
        continue
    fi

    # Validate input format (basic check)
    if ! echo "$input" | grep -qE '^[a-h][1-8]-?[a-h][1-8]$'; then
        echo -e "${RED}Invalid format. Use coordinate notation like e2e4 or e2-e4${NC}"
        continue
    fi

    # Remove dashes for consistency
    clean_move=$(echo "$input" | tr -d '-')

    compile_and_read "$clean_move"
    result=$?
    if [ $result -eq 2 ]; then
        game_active=0
    fi
done
