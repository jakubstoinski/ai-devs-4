import os
import requests
from collections import deque
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

API_KEY = os.getenv("CENTRAL_TOKEN")
BASE_URL = "https://hub.ag3nts.org/verify"
TASK = "reactor"

BOTTOM_ROW = 5  # 1-indexed
TOP_ROW = 1     # 1-indexed
GOAL_COL = 7    # 1-indexed
LEFT_EDGE = 1   # 1-indexed


def send_command(command: str) -> dict:
    payload = {
        "apikey": API_KEY,
        "task": TASK,
        "answer": {"command": command},
    }
    resp = requests.post(BASE_URL, json=payload)
    if resp.status_code == 409:
        return {"code": 409, "message": resp.text}
    resp.raise_for_status()
    return resp.json()


def next_block_state(blocks: list[dict]) -> list[dict]:
    """Advance all blocks one tick."""
    new = []
    for b in blocks:
        top = b["top_row"]
        bot = b["bottom_row"]
        d = b["direction"]
        if d == "down":
            top += 1
            bot += 1
            if bot >= BOTTOM_ROW:
                d = "up"
        else:
            top -= 1
            bot -= 1
            if top <= TOP_ROW:
                d = "down"
        new.append({"col": b["col"], "top_row": top, "bottom_row": bot, "direction": d})
    return new


def is_crushed(blocks: list[dict], col: int) -> bool:
    """True if block occupies bottom row in this column."""
    for b in blocks:
        if b["col"] == col and b["bottom_row"] == BOTTOM_ROW:
            return True
    return False


def blocks_key(blocks: list[dict]) -> tuple:
    return tuple((b["col"], b["top_row"], b["direction"]) for b in sorted(blocks, key=lambda x: x["col"]))


def bfs_next_action(robot_col: int, blocks: list[dict], max_depth: int = 50) -> str:
    """BFS to find first action toward goal, avoiding crushes."""
    initial_key = (robot_col, blocks_key(blocks))
    queue = deque([(robot_col, blocks, [])])
    visited = {initial_key}

    while queue:
        r_col, blks, path = queue.popleft()

        if len(path) >= max_depth:
            continue

        for action in ["right", "wait", "left"]:
            new_r_col = r_col
            if action == "right":
                new_r_col = min(GOAL_COL, r_col + 1)
            elif action == "left":
                new_r_col = max(LEFT_EDGE, r_col - 1)

            new_blks = next_block_state(blks)

            if is_crushed(new_blks, new_r_col):
                continue

            if new_r_col == GOAL_COL:
                return path[0] if path else action

            state = (new_r_col, blocks_key(new_blks))
            if state not in visited:
                visited.add(state)
                new_path = path + [action]
                queue.append((new_r_col, new_blks, new_path))

    return "wait"  # fallback


def print_board(board: list[list[str]]) -> None:
    for row in board:
        print("".join(row))


def run() -> None:
    print("Sending start...")
    resp = send_command("start")
    print(f"Initial: {resp}\n")

    for step in range(200):
        code = resp.get("code")

        if resp.get("reached_goal"):
            print(f"\nGoal reached! {resp}")
            return

        board = resp.get("board", [])
        player = resp.get("player", {})
        blocks = resp.get("blocks", [])
        robot_col = player.get("col", 1)

        print(f"\nStep {step} | robot col={robot_col} (1-indexed)")
        if board:
            print_board(board)
        print(f"  blocks: {[(b['col'], b['top_row'], b['bottom_row'], b['direction']) for b in blocks]}")

        msg = str(resp.get("message", ""))
        if "flag" in msg.lower() or "FLG" in msg:
            print(f"\nSUCCESS: {resp}")
            return

        if code == 409 or "crushed" in msg.lower() or "dead" in msg.lower() or "game over" in msg.lower():
            print(f"\nGame over or error: {resp}")
            print("Restarting...")
            resp = send_command("start")
            print(f"Restart: {resp}")
            continue

        if robot_col >= GOAL_COL:
            print(f"\nAt goal column {robot_col}! {resp}")
            return

        action = bfs_next_action(robot_col, blocks)
        print(f"  → {action}")

        resp = send_command(action)
        print(f"  API: {resp}")

    print("Max steps reached.")


if __name__ == "__main__":
    run()
