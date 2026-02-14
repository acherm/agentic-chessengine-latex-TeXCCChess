#!/usr/bin/env python3
"""Convert PGN file to LaTeX document with board diagrams.

Parses PGN output from cutechess-cli (Standard Algebraic Notation),
tracks board state to generate FEN positions, and produces a LaTeX
document using the chessboard package.
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
    """Chess board tracker with SAN move resolution."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [row[:] for row in INITIAL_BOARD]
        self.is_white_turn = True
        self.ep_file = -1  # en passant target file (-1 = none)

    def get(self, file, rank):
        """Get piece at (file 0-7, rank 0-7). Rank 0 = rank 1."""
        return self.board[rank][file]

    def set(self, file, rank, piece):
        self.board[rank][file] = piece

    def path_clear(self, ff, fr, tf, tr):
        """Check if path between two squares is unobstructed (exclusive)."""
        df = tf - ff
        dr = tr - fr
        steps = max(abs(df), abs(dr))
        if steps <= 1:
            return True
        sf = (1 if df > 0 else -1) if df != 0 else 0
        sr = (1 if dr > 0 else -1) if dr != 0 else 0
        for i in range(1, steps):
            if self.get(ff + i * sf, fr + i * sr) != ".":
                return False
        return True

    def can_reach(self, ff, fr, tf, tr, piece):
        """Check if piece at (ff,fr) can geometrically reach (tf,tr)."""
        p = piece.upper()
        df = tf - ff
        dr = tr - fr

        if p == "P":
            direction = 1 if piece.isupper() else -1
            # Forward push
            if df == 0:
                if dr == direction and self.get(tf, tr) == ".":
                    return True
                start_rank = 1 if piece.isupper() else 6
                if dr == 2 * direction and fr == start_rank:
                    if self.get(tf, fr + direction) == "." and self.get(tf, tr) == ".":
                        return True
            # Capture (normal or en passant)
            if abs(df) == 1 and dr == direction:
                target = self.get(tf, tr)
                if target != ".":
                    return True
                # En passant
                if tf == self.ep_file:
                    ep_rank = 5 if piece.isupper() else 2
                    if tr == ep_rank:
                        return True
            return False

        if p == "N":
            return (abs(df), abs(dr)) in [(1, 2), (2, 1)]

        if p == "K":
            return abs(df) <= 1 and abs(dr) <= 1

        if p == "R":
            return (df == 0 or dr == 0) and self.path_clear(ff, fr, tf, tr)

        if p == "B":
            return abs(df) == abs(dr) and df != 0 and self.path_clear(ff, fr, tf, tr)

        if p == "Q":
            if df == 0 or dr == 0:
                return self.path_clear(ff, fr, tf, tr)
            if abs(df) == abs(dr):
                return self.path_clear(ff, fr, tf, tr)
            return False

        return False

    def apply_san(self, san):
        """Apply a move in Standard Algebraic Notation."""
        # Strip check/mate symbols
        san = san.rstrip("+#")

        is_white = self.is_white_turn

        # Castling
        if san in ("O-O", "0-0"):
            rank = 0 if is_white else 7
            self._do_move(4, rank, 6, rank)
            self._do_move(7, rank, 5, rank)
            self.ep_file = -1
            self.is_white_turn = not self.is_white_turn
            return

        if san in ("O-O-O", "0-0-0"):
            rank = 0 if is_white else 7
            self._do_move(4, rank, 2, rank)
            self._do_move(0, rank, 3, rank)
            self.ep_file = -1
            self.is_white_turn = not self.is_white_turn
            return

        # Parse promotion
        promo = None
        if "=" in san:
            idx = san.index("=")
            promo = san[idx + 1]
            san = san[:idx]

        # Parse target square (always the last two characters)
        target_file = ord(san[-2]) - ord("a")
        target_rank = int(san[-1]) - 1
        san = san[:-2]

        # Remove capture indicator
        san = san.replace("x", "")

        # Determine piece type and disambiguation
        if not san:
            # Pawn move
            piece_char = "P" if is_white else "p"
            disambig_file = None
            disambig_rank = None
        elif san[0] in "KQRBN":
            piece_char = san[0] if is_white else san[0].lower()
            san = san[1:]
            disambig_file = None
            disambig_rank = None
            if len(san) >= 2:
                disambig_file = ord(san[0]) - ord("a")
                disambig_rank = int(san[1]) - 1
            elif len(san) == 1:
                if "a" <= san[0] <= "h":
                    disambig_file = ord(san[0]) - ord("a")
                else:
                    disambig_rank = int(san[0]) - 1
        else:
            # Pawn with file disambiguation (e.g., "exd4" -> san is "e")
            piece_char = "P" if is_white else "p"
            disambig_file = ord(san[0]) - ord("a")
            disambig_rank = None

        # Find the source square
        found = False
        for rank in range(8):
            for file in range(8):
                piece = self.get(file, rank)
                if piece != piece_char:
                    continue
                if disambig_file is not None and file != disambig_file:
                    continue
                if disambig_rank is not None and rank != disambig_rank:
                    continue
                if self.can_reach(file, rank, target_file, target_rank, piece):
                    from_file, from_rank = file, rank
                    found = True
                    break
            if found:
                break

        if not found:
            sys.stderr.write("WARNING: Could not resolve SAN move: %s\n" % san)
            self.is_white_turn = not self.is_white_turn
            return

        # Detect en passant capture
        is_ep = False
        if piece_char.upper() == "P" and from_file != target_file:
            if self.get(target_file, target_rank) == ".":
                is_ep = True

        # Detect double pawn push for en passant
        new_ep_file = -1
        if piece_char.upper() == "P" and abs(target_rank - from_rank) == 2:
            new_ep_file = target_file

        # Execute the move
        self._do_move(from_file, from_rank, target_file, target_rank)

        # En passant: remove captured pawn
        if is_ep:
            self.set(target_file, from_rank, ".")

        # Promotion
        if promo:
            promo_piece = promo.upper() if is_white else promo.lower()
            self.set(target_file, target_rank, promo_piece)

        self.ep_file = new_ep_file
        self.is_white_turn = not self.is_white_turn

    def _do_move(self, ff, fr, tf, tr):
        """Move piece from (ff,fr) to (tf,tr)."""
        piece = self.get(ff, fr)
        self.set(tf, tr, piece)
        self.set(ff, fr, ".")

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


# SAN move pattern: piece moves, pawn moves, castling
_MOVE_RE = re.compile(
    r"^(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8]"  # piece moves
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?"          # pawn captures (with optional promo)
    r"|[a-h][1-8](?:=[QRBN])?"                 # pawn pushes (with optional promo)
    r"|O-O-O|O-O|0-0-0|0-0"                    # castling
    r")[+#]?$"
)


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

    # Remove comments {like this}
    movetext = re.sub(r"\{[^}]*\}", "", movetext)
    # Remove result at end
    movetext = re.sub(r"(1-0|0-1|1/2-1/2|\*)\s*$", "", movetext)

    # Extract SAN moves (skip move numbers and results)
    moves = []
    for token in movetext.split():
        token = token.strip()
        if not token:
            continue
        # Skip move numbers like "1." or "12..." or bare numbers
        if re.match(r"^\d+\.+$", token):
            continue
        if re.match(r"^\d+$", token):
            continue
        # Skip results
        if token in ("1-0", "0-1", "1/2-1/2", "*"):
            continue
        if _MOVE_RE.match(token):
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

            # Move list and board tracking
            board = Board()
            move_text = ""
            for j, move in enumerate(game["moves"]):
                if j % 2 == 0:
                    move_num = j // 2 + 1
                    move_text += "%d.~%s " % (move_num, escape_latex(move))
                else:
                    move_text += "%s " % escape_latex(move)
                board.apply_san(move)

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
                    board2.apply_san(move)
                    if (j + 1) % step == 0 and j < len(game["moves"]) - 1:
                        fen2 = board2.to_fen()
                        if j % 2 == 0:
                            desc = "After %d.~%s" % (j // 2 + 1, escape_latex(move))
                        else:
                            desc = "After %d\\ldots %s" % (
                                j // 2 + 1,
                                escape_latex(move),
                            )
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
