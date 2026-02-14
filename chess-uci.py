#!/usr/bin/env python3
"""UCI protocol wrapper for the TeX chess engine.

Bridges cutechess-cli (UCI protocol) to the pdfLaTeX chess engine.
Each 'go' command writes uci-moves.tex, compiles chess-uci.tex,
and reads the engine's move from engine-output.dat.
"""

import sys
import os
import subprocess


def main():
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.join(engine_dir, ".tex-uci-work")
    os.makedirs(work_dir, exist_ok=True)

    moves = []

    # Set TEXINPUTS so pdflatex finds chess-engine.tex and chess-uci.tex
    env = os.environ.copy()
    env["TEXINPUTS"] = engine_dir + "/:" + env.get("TEXINPUTS", "")

    tex_file = os.path.join(engine_dir, "chess-uci.tex")

    while True:
        try:
            line = input()
        except EOFError:
            break

        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        cmd = tokens[0]

        if cmd == "uci":
            send("id name TeX Chess Engine")
            send("id author pdfLaTeX")
            send("uciok")

        elif cmd == "isready":
            send("readyok")

        elif cmd == "ucinewgame":
            moves = []

        elif cmd == "position":
            moves = []
            if len(tokens) > 1 and tokens[1] == "startpos":
                if "moves" in tokens:
                    idx = tokens.index("moves")
                    moves = tokens[idx + 1:]

        elif cmd == "go":
            bestmove = generate_move(tex_file, work_dir, moves, env)
            send("bestmove " + bestmove)

        elif cmd == "quit":
            break


def send(msg):
    """Send a UCI response line (with required flush)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def generate_move(tex_file, work_dir, moves, env):
    """Run pdflatex to generate the engine's next move."""
    # Write uci-moves.tex with \replaymove for each prior move
    uci_moves_path = os.path.join(work_dir, "uci-moves.tex")
    with open(uci_moves_path, "w") as f:
        for m in moves:
            f.write("\\replaymove{" + m + "}\n")

    # Run pdflatex
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_file],
            cwd=work_dir,
            env=env,
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "0000"

    # Read engine output
    output_path = os.path.join(work_dir, "engine-output.dat")
    try:
        with open(output_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ENGINEMOVE:"):
                    mv = line[len("ENGINEMOVE:"):]
                    if mv and mv != "none":
                        return mv
                    return "0000"
    except FileNotFoundError:
        pass

    return "0000"


if __name__ == "__main__":
    main()
