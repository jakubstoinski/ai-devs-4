"""
S02E02 — Electricity puzzle solver.

Strategy:
  1. Download current board + target board, save to resources/
  2. Detect cable connections in each cell via pixel-level edge sampling
  3. Calculate minimum CW rotations needed per cell
  4. Execute rotations via the hub API and re-verify until flag is received
"""

import sys
import os
import json
import time
import requests
import numpy as np
from io import BytesIO
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "resources" / ".env")

API_KEY = os.getenv("CENTRAL_TOKEN")
RESOURCES = Path(__file__).parent / "resources"
VERIFY_URL = "https://hub.ag3nts.org/verify"
CURRENT_URL = f"https://hub.ag3nts.org/data/{API_KEY}/electricity.png"
TARGET_URL = "https://hub.ag3nts.org/i/solved_electricity.png"

# Grid pixel boundaries (detected via dark-pixel column/row density analysis).
# (left_col, top_row, right_col, bottom_row) of the full 3x3 grid.
TARGET_GRID = (141, 88, 429, 376)
CURRENT_GRID = (237, 98, 525, 386)

# How far inside the cell boundary to sample when checking for a cable exit.
# Must be large enough to clear the border line (~4-5px) but small enough to
# stay within the first third of the cell where the cable would still be visible.
EDGE_INSET = 15          # px from cell boundary to start sampling
EDGE_SAMPLE_DEPTH = 20   # px depth of the sampling strip
DARK_THRESHOLD = 100     # pixel value below which we consider "cable present"


# ---------------------------------------------------------------------------
# Image I/O
# ---------------------------------------------------------------------------

def fetch_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert("RGB")


def download_current(reset: bool = False) -> Image.Image:
    url = CURRENT_URL + ("?reset=1" if reset else "")
    img = fetch_image(url)
    img.save(RESOURCES / "current.png")
    return img


def download_target() -> Image.Image:
    img = fetch_image(TARGET_URL)
    img.save(RESOURCES / "target.png")
    return img


# ---------------------------------------------------------------------------
# Cable connection detection (pixel-level)
# ---------------------------------------------------------------------------

def get_connections(img: Image.Image, row: int, col: int, grid_bounds: tuple) -> set[str]:
    """
    Return which edges (T/R/B/L) have a cable exiting the cell.

    For each edge, we sample a rectangular strip inside the cell, offset EDGE_INSET
    pixels from the boundary (to skip the drawn cell-border line).  If any pixel
    in that strip is darker than DARK_THRESHOLD we consider that edge "connected".
    """
    x1, y1, x2, y2 = grid_bounds
    cw = (x2 - x1) // 3
    ch = (y2 - y1) // 3
    cx = x1 + (col - 1) * cw   # left edge of cell
    cy = y1 + (row - 1) * ch   # top edge of cell

    arr = np.array(img)

    # Sample width/height: centre 33% of the edge to avoid corner artefacts
    sw = cw // 3
    sh = ch // 3
    mx = cx + cw // 2 - sw // 2   # horizontal midpoint strip
    my = cy + ch // 2 - sh // 2   # vertical midpoint strip

    i = EDGE_INSET
    d = EDGE_SAMPLE_DEPTH

    strips = {
        "T": arr[cy + i : cy + i + d,        mx : mx + sw],
        "B": arr[cy + ch - i - d : cy + ch - i,  mx : mx + sw],
        "L": arr[my : my + sh,               cx + i : cx + i + d],
        "R": arr[my : my + sh,               cx + cw - i - d : cx + cw - i],
    }

    return {edge for edge, strip in strips.items() if np.any(np.all(strip < DARK_THRESHOLD, axis=2))}


# ---------------------------------------------------------------------------
# Rotation maths
# ---------------------------------------------------------------------------

# One 90° CW rotation: T→R, R→B, B→L, L→T
_CW = {"T": "R", "R": "B", "B": "L", "L": "T"}


def rotate_connections(edges: set[str], n: int = 1) -> frozenset[str]:
    result = set(edges)
    for _ in range(n):
        result = {_CW[e] for e in result}
    return frozenset(result)


def rotations_needed(current: set[str], target: set[str]) -> int | None:
    """Return 0-3 CW rotations to reach target, or None if piece types differ."""
    c = frozenset(current)
    t = frozenset(target)
    for n in range(4):
        if rotate_connections(c, n) == t:
            return n
    return None


# ---------------------------------------------------------------------------
# Hub API
# ---------------------------------------------------------------------------

def send_rotation(cell: str) -> dict:
    payload = {"apikey": API_KEY, "task": "electricity", "answer": {"rotate": cell}}
    resp = requests.post(VERIFY_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def has_flag(resp: dict) -> bool:
    return "FLG" in json.dumps(resp)


# ---------------------------------------------------------------------------
# Core solver
# ---------------------------------------------------------------------------

CELLS = [f"{r}x{c}" for r in range(1, 4) for c in range(1, 4)]


def analyse_board(current_img: Image.Image, target_img: Image.Image) -> list[dict]:
    """Compare every cell and return list of {cell, rotations} that need action."""
    plan = []
    print("\nCell analysis:")
    for cell in CELLS:
        row, col = int(cell[0]), int(cell[2])
        cur = get_connections(current_img, row, col, CURRENT_GRID)
        tgt = get_connections(target_img,  row, col, TARGET_GRID)
        n = rotations_needed(cur, tgt)
        status = "✓" if n == 0 else (f"→ {n} rotation(s)" if n else "TYPE MISMATCH")
        print(f"  {cell}: cur={sorted(cur)} tgt={sorted(tgt)}  {status}")
        if n and n > 0:
            plan.append({"cell": cell, "rotations": n})
    return plan


def execute_plan(plan: list[dict]) -> dict | None:
    """Send all rotations; return the hub response that contained a flag, or None."""
    total = sum(p["rotations"] for p in plan)
    print(f"\nExecuting {total} rotation(s)...")
    for item in plan:
        cell, n = item["cell"], item["rotations"]
        for i in range(n):
            print(f"  rotate {cell} ({i + 1}/{n})...", end=" ", flush=True)
            result = send_rotation(cell)
            print(result)
            time.sleep(0.3)
            if has_flag(result):
                return result
    return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    RESOURCES.mkdir(exist_ok=True)

    print("Fetching target board...")
    target_img = download_target()

    print("Fetching current board (reset)...")
    current_img = download_current(reset=True)

    for attempt in range(1, 6):
        print(f"\n{'='*50}")
        print(f"Attempt {attempt}")
        print("=" * 50)

        plan = analyse_board(current_img, target_img)

        if not plan:
            print("\nBoard matches target — waiting for flag confirmation...")
            # Nudge: rotate a cell that is already correct once, then back,
            # just to trigger a hub response that might return the flag.
            # (Skip this if you trust the analysis.)
            break

        flag_resp = execute_plan(plan)
        if flag_resp:
            print(f"\n{'='*50}")
            print(f"FLAG: {flag_resp}")
            print("=" * 50)
            return

        print("\nRe-fetching current board to verify...")
        current_img = download_current()

    print("\nNo flag received. Check board state manually.")


if __name__ == "__main__":
    main()
