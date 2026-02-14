#!/usr/bin/env python3
"""Convert PGN file to LaTeX document with board diagrams.

Parses PGN output from cutechess-cli, tracks board state to generate
FEN positions, and produces a LaTeX document using the chessboard package.
"""

import sys
import re


INITIAL_BOARD = [
    ["R", "N", "B", "Q", "K", "B", "N", "R"],
    ["P", "P", "P", "P", "P", "P", "P", "P"],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    ["p", "p", "p", "p", "p", "p", "p", "p"],
    ["r", "n", "b", "q", "k", "b", "n", "r"],
]


class Board:
    """Simple chess board tracker for generating FEN positions."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [row[:] for row in INITIAL_BOARD]

    def get(self, file, rank):
        """Get piece at (file 0-7, rank 0-7). Rank 0 = rank 1."""
        return self.board[rank][file]

    def set(self, file, rank, piece):
        self.board[rank][file] = piece

    def apply_move(self, move):
        """Apply a move in coordinate notation (e.g., e2e4, e7e8q)."""
        ff = ord(move[0]) - ord("a")
        fr = int(move[1]) - 1
        tf = ord(move[2]) - ord("a")
        tr = int(move[3]) - 1
        promo = move[4] if len(move) > 4 else None

        piece = self.get(ff, fr)
        captured = self.get(tf, tr)

        # Move piece
        self.set(tf, tr, piece)
        self.set(ff, fr, ".")

        # Castling: king moves two squares
        if piece in ("K", "k") and abs(tf - ff) == 2:
            if tf > ff:  # Kingside
                rook = self.get(7, fr)
                self.set(5, fr, rook)
                self.set(7, fr, ".")
            else:  # Queenside
                rook = self.get(0, fr)
                self.set(3, fr, rook)
                self.set(0, fr, ".")

        # En passant: pawn captures to empty square on different file
        if piece in ("P", "p") and ff != tf and captured == ".":
            self.set(tf, fr, ".")

        # Promotion
        if promo:
            promo_piece = promo.upper() if piece.isupper() else promo.lower()
            self.set(tf, tr, promo_piece)

    def to_fen(self):
        """Generate FEN piece placement string."""
        fen_rows = []
        for rank in range(7, -1, -1):
            row = ""
            empty = 0
            for file in range(8):
                piece = self.get(file, rank)
                if piece == ".":
                    empty += 1
                else:
                    if empty > 0:
                        row += str(empty)
                        empty = 0
                    row += piece
            if empty > 0:
                row += str(empty)
            fen_rows.append(row)
        return "/".join(fen_rows)


def parse_pgn(filename):
    """Parse a PGN file and return a list of games."""
    games = []
    with open(filename) as f:
        content = f.read()

    # Split into games by [Event tags at start of line
    game_texts = re.split(r"\n(?=\[Event )", content.strip())

    for text in game_texts:
        text = text.strip()
        if not text:
            continue
        game = parse_single_game(text)
        if game:
            games.append(game)

    return games


def parse_single_game(text):
    """Parse a single PGN game into headers and moves."""
    headers = {}
    for match in re.finditer(r'\[(\w+)\s+"([^"]*)"\]', text):
        headers[match.group(1)] = match.group(2)

    # Find movetext: everything after the last header line
    lines = text.split("\n")
    movetext_lines = []
    in_headers = True
    for line in lines:
        if in_headers:
            if line.startswith("[") and line.endswith("]"):
                continue
            if line.strip() == "":
                in_headers = False
                continue
            in_headers = False
        movetext_lines.append(line)

    movetext = " ".join(movetext_lines)

    # Remove comments
    movetext = re.sub(r"\{[^}]*\}", "", movetext)
    # Remove result at end
    movetext = re.sub(r"(1-0|0-1|1/2-1/2|\*)\s*$", "", movetext)

    # Extract moves (skip move numbers)
    moves = []
    for token in movetext.split():
        token = token.strip().rstrip(".")
        if not token:
            continue
        if re.match(r"^\d+$", token):
            continue
        if re.match(r"^[a-h][1-8][a-h][1-8][qrbn]?$", token):
            moves.append(token)

    return {
        "headers": headers,
        "moves": moves,
        "result": headers.get("Result", "*"),
        "white": headers.get("White", "?"),
        "black": headers.get("Black", "?"),
    }


def escape_latex(s):
    """Escape special LaTeX characters."""
    s = s.replace("&", r"\&")
    s = s.replace("%", r"\%")
    s = s.replace("$", r"\$")
    s = s.replace("#", r"\#")
    s = s.replace("_", r"\_")
    s = s.replace("{", r"\{")
    s = s.replace("}", r"\}")
    s = s.replace("~", r"\textasciitilde{}")
    s = s.replace("^", r"\textasciicircum{}")
    return s


def identify_players(games):
    """Identify which player is the TeX engine and which is Stockfish."""
    all_names = set()
    for g in games:
        all_names.add(g["white"])
        all_names.add(g["black"])

    tex_name = None
    sf_name = None
    for name in all_names:
        nl = name.lower()
        if "tex" in nl:
            tex_name = name
        elif "stockfish" in nl or "sf" in nl:
            sf_name = name

    if tex_name is None:
        tex_name = sorted(all_names)[0]
    if sf_name is None:
        remaining = all_names - {tex_name}
        sf_name = sorted(remaining)[0] if remaining else "Opponent"

    return tex_name, sf_name


def compute_stats(games, tex_name, sf_name):
    """Compute win/loss/draw statistics."""
    tex_wins = 0
    sf_wins = 0
    draws = 0

    for g in games:
        if g["result"] == "1-0":
            if g["white"] == tex_name:
                tex_wins += 1
            else:
                sf_wins += 1
        elif g["result"] == "0-1":
            if g["black"] == tex_name:
                tex_wins += 1
            else:
                sf_wins += 1
        elif g["result"] == "1/2-1/2":
            draws += 1

    return tex_wins, sf_wins, draws


def find_interesting_games(games, tex_name):
    """Find games worth showing move-by-move diagrams."""
    interesting = set()

    # Any TeX engine wins
    for i, g in enumerate(games):
        is_tex_win = (g["white"] == tex_name and g["result"] == "1-0") or (
            g["black"] == tex_name and g["result"] == "0-1"
        )
        if is_tex_win:
            interesting.add(i)

    # Shortest and longest games
    if games:
        lengths = [(len(g["moves"]), i) for i, g in enumerate(games)]
        lengths.sort()
        interesting.add(lengths[0][1])  # shortest
        interesting.add(lengths[-1][1])  # longest

    return interesting


def generate_latex(games, output_file):
    """Generate LaTeX document from parsed games."""
    if not games:
        print("No games found.")
        return

    tex_name, sf_name = identify_players(games)
    tex_wins, sf_wins, draws = compute_stats(games, tex_name, sf_name)
    interesting = find_interesting_games(games, tex_name)

    with open(output_file, "w") as f:
        # Preamble
        f.write("\\documentclass[11pt]{article}\n")
        f.write("\\usepackage[utf8]{inputenc}\n")
        f.write("\\usepackage{chessboard}\n")
        f.write("\\usepackage{geometry}\n")
        f.write("\\usepackage{parskip}\n")
        f.write("\\geometry{margin=1in}\n")
        f.write(
            "\\storechessboardstyle{small}"
            "{maxfield=h8,fieldmaxwidth=0.6cm,"
            "labelleft=false,labelbottom=false}\n"
        )
        f.write("\n\\begin{document}\n")
        f.write(
            "\\title{"
            + escape_latex(tex_name)
            + " vs "
            + escape_latex(sf_name)
            + " --- Elo Assessment}\n"
        )
        f.write("\\date{\\today}\n")
        f.write("\\maketitle\n\n")

        # Summary
        f.write("\\section*{Summary}\n")
        f.write("\\begin{tabular}{ll}\n")
        f.write("Total games: & %d \\\\\n" % len(games))
        f.write("%s wins: & %d \\\\\n" % (escape_latex(tex_name), tex_wins))
        f.write("%s wins: & %d \\\\\n" % (escape_latex(sf_name), sf_wins))
        f.write("Draws: & %d \\\\\n" % draws)
        if len(games) > 0:
            score = (tex_wins + draws * 0.5) / len(games)
            f.write(
                "Score for %s: & %.1f\\%% \\\\\n"
                % (escape_latex(tex_name), score * 100)
            )
        f.write("\\end{tabular}\n\n")
        f.write("\\bigskip\n\n")

        # Each game
        for i, game in enumerate(games):
            game_num = i + 1

            f.write(
                "\\subsection*{Game %d: %s vs %s (%s)}\n"
                % (
                    game_num,
                    escape_latex(game["white"]),
                    escape_latex(game["black"]),
                    game["result"],
                )
            )

            # Move list
            board = Board()
            move_text = ""
            for j, move in enumerate(game["moves"]):
                if j % 2 == 0:
                    move_num = j // 2 + 1
                    move_text += "%d.~%s " % (move_num, move)
                else:
                    move_text += "%s " % move
                board.apply_move(move)

            move_text += game["result"]
            f.write("\\noindent %s\n\n" % move_text)

            # Final position diagram
            fen = board.to_fen()
            f.write("\\medskip\n")
            f.write("\\noindent Final position:\\\\\n")
            f.write("\\setchessboard{setfen=%s}\n" % fen)
            f.write("\\chessboard[maxfield=h8,fieldmaxwidth=0.8cm]\n\n")

            # For interesting games, show key positions
            if i in interesting and len(game["moves"]) > 4:
                f.write("\\medskip\n")
                f.write("\\noindent Key positions:\\\\\n")
                board2 = Board()
                step = max(2, len(game["moves"]) // 6)
                for j, move in enumerate(game["moves"]):
                    board2.apply_move(move)
                    if (j + 1) % step == 0 and j < len(game["moves"]) - 1:
                        fen2 = board2.to_fen()
                        if j % 2 == 0:
                            desc = "After %d.~%s" % (j // 2 + 1, move)
                        else:
                            desc = "After %d...%s" % (j // 2 + 1, move)
                        f.write("\\noindent %s\\\\\n" % desc)
                        f.write("\\setchessboard{setfen=%s}\n" % fen2)
                        f.write("\\chessboard[style=small]\n")
                        f.write("\\medskip\n\n")

            if i < len(games) - 1:
                f.write("\\hrule\n")
                f.write("\\bigskip\n\n")

        f.write("\\end{document}\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: %s <pgn-file> <output-tex-file>" % sys.argv[0])
        sys.exit(1)

    pgn_file = sys.argv[1]
    output_file = sys.argv[2]

    games = parse_pgn(pgn_file)
    print("Parsed %d games from %s" % (len(games), pgn_file))

    generate_latex(games, output_file)
    print("Generated LaTeX file: %s" % output_file)


if __name__ == "__main__":
    main()
