#!/usr/bin/env python3
"""UCI protocol wrapper for the TeX chess engine.

Bridges cutechess-cli (UCI protocol) to the pdfLaTeX chess engine.
Each 'go' command writes uci-moves.tex, compiles chess-uci.tex,
and reads the engine's move from engine-output.dat.
"""

import sys
import os
import subprocess
import logging

log = logging.getLogger("tex-uci")


def main():
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.join(engine_dir, ".tex-uci-work")
    os.makedirs(work_dir, exist_ok=True)

    # Optional debug log (set TEX_UCI_LOG=1 to enable)
    if os.environ.get("TEX_UCI_LOG"):
        logging.basicConfig(
            filename=os.path.join(work_dir, "uci-debug.log"),
            level=logging.DEBUG,
            format="%(asctime)s %(message)s",
        )

    moves = []
    side_to_move = "w"  # track which clock applies

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
            side_to_move = "w"

        elif cmd == "position":
            moves = []
            if len(tokens) > 1 and tokens[1] == "startpos":
                if "moves" in tokens:
                    idx = tokens.index("moves")
                    moves = tokens[idx + 1:]
            side_to_move = "w" if len(moves) % 2 == 0 else "b"

        elif cmd == "go":
            timeout = compute_timeout(tokens, side_to_move)
            log.debug("go: side=%s moves=%d timeout=%.1f tokens=%s",
                      side_to_move, len(moves), timeout, tokens)
            bestmove = generate_move(tex_file, work_dir, moves, env, timeout)
            send("bestmove " + bestmove)

        elif cmd == "quit":
            break


def send(msg):
    """Send a UCI response line (with required flush)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def compute_timeout(tokens, side_to_move):
    """Compute pdflatex timeout from UCI go parameters.

    The TeX engine has fixed computation cost per move (no iterative deepening,
    no way to stop early).  Depth-3 + quiescence typically takes 1-13s depending
    on position complexity and game length (move replay overhead).  The timeout
    must be generous enough for the search to complete; killing pdflatex early
    produces an illegal 0000 which is an instant loss.

    Strategy: allow up to 50% of remaining time for a single move (the engine
    rarely needs more than 15s), but never more than 30s absolute.  The per-move
    budget is remaining / estimated_moves_left + increment.
    """
    params = {}
    i = 1
    while i < len(tokens):
        key = tokens[i]
        if i + 1 < len(tokens) and tokens[i + 1].lstrip("-").isdigit():
            params[key] = int(tokens[i + 1])
            i += 2
        else:
            i += 1

    # Pick our clock
    if side_to_move == "w":
        remaining_ms = params.get("wtime", None)
        inc_ms = params.get("winc", 0)
    else:
        remaining_ms = params.get("btime", None)
        inc_ms = params.get("binc", 0)

    if remaining_ms is None:
        # No clock info (e.g. infinite/fixed-depth) — use generous default
        return 30.0

    remaining_s = max(remaining_ms / 1000.0, 0)
    inc_s = inc_ms / 1000.0
    moves_to_go = params.get("movestogo", None)

    if moves_to_go is not None:
        # Repeating TC: we know exactly how many moves until the next refill
        if moves_to_go < 1:
            moves_to_go = 1
        budget = remaining_s / moves_to_go + inc_s
        max_allowed = remaining_s * 0.80
        timeout = min(budget, max_allowed, 30.0)
        timeout = max(timeout, 2.0)
    else:
        # Sudden death: the TeX engine does fixed-depth search (no iterative
        # deepening) — it either completes in 1-15s or returns nothing useful.
        # Allow a generous per-move budget: up to 15s as long as the bank can
        # cover it.  Only tighten when time is genuinely critical.
        max_per_move = 15.0  # worst-case depth-3 + quiescence
        max_allowed = remaining_s * 0.50  # never burn more than half the bank
        timeout = min(max_per_move, max_allowed, 30.0)
        timeout = max(timeout, min(5.0, remaining_s * 0.80))

    log.debug("time management: remaining=%.1fs inc=%.1fs mtg=%s timeout=%.1f",
              remaining_s, inc_s, moves_to_go, timeout)
    return timeout


def generate_move(tex_file, work_dir, moves, env, timeout=30.0):
    """Run pdflatex to generate the engine's next move."""
    # Write uci-moves.tex with \replaymove for each prior move
    uci_moves_path = os.path.join(work_dir, "uci-moves.tex")
    with open(uci_moves_path, "w") as f:
        for m in moves:
            f.write("\\replaymove{" + m + "}\n")

    # Remove stale output so we can detect pdflatex failures
    output_path = os.path.join(work_dir, "engine-output.dat")
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    # Run pdflatex with time-managed timeout
    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_file],
            cwd=work_dir,
            env=env,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            log.debug("pdflatex exited with code %d", result.returncode)
            log_path = os.path.join(work_dir, "chess-uci.log")
            try:
                with open(log_path, "r") as lf:
                    lines = lf.readlines()
                    # Log last 30 lines of TeX log for diagnosis
                    for line in lines[-30:]:
                        log.debug("TEX: %s", line.rstrip())
            except FileNotFoundError:
                pass
    except subprocess.TimeoutExpired:
        log.debug("pdflatex timed out after %.1fs with %d moves", timeout, len(moves))
        return "0000"

    # Read engine output
    try:
        with open(output_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ENGINEMOVE:"):
                    mv = line[len("ENGINEMOVE:"):]
                    if mv and mv != "none":
                        return mv
                    log.debug("engine returned 'none' or empty move")
                    return "0000"
    except FileNotFoundError:
        log.debug("engine-output.dat not found — pdflatex likely failed")

    return "0000"


if __name__ == "__main__":
    main()
