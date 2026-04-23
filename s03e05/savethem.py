"""
s03e05 — savethem
Discovers tools, fetches map + vehicles, plans an optimal route to Skolwin,
and submits the answer to central.

Rules (from /api/books):
  - W = water: only horse/walk can cross
  - R = rocks: impassable by all
  - T = tree: passable, but +0.2 fuel for powered vehicles (car/rocket)
  - S = start, G = goal
  - Dismount command: leave vehicle, continue on foot (walk mode)
  - Resources: 10 fuel, 10 food
  - Vehicles: rocket (1.0 fuel/0.1 food), car (0.7 fuel/1.0 food),
              horse (0 fuel/1.6 food, water OK), walk (0 fuel/2.5 food, water OK)
"""
import os
import sys
import json
import heapq
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.central_client import send_to_central

load_dotenv(dotenv_path=Path(__file__).parent.parent / "resources" / ".env")

HUB_BASE = "https://hub.ag3nts.org"

VEHICLES = {
    "rocket": {"fuel": 1.0, "food": 0.1, "water": False},
    "car":    {"fuel": 0.7, "food": 1.0, "water": False},
    "horse":  {"fuel": 0.0, "food": 1.6, "water": True},
    "walk":   {"fuel": 0.0, "food": 2.5, "water": True},
}

DIRECTION_DELTA = {
    "up":    (-1,  0),
    "down":  ( 1,  0),
    "left":  ( 0, -1),
    "right": ( 0,  1),
}

MAX_FUEL = 10
MAX_FOOD = 10
TREE_FUEL_PENALTY = 0.2


def call_api(path: str, query: str) -> dict:
    key = os.getenv("CENTRAL_TOKEN")
    url = path if path.startswith("http") else f"{HUB_BASE}{path}"
    resp = requests.post(url, json={"apikey": key, "query": query}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_map() -> list[list[str]]:
    data = call_api("/api/maps", "Skolwin")
    grid = data["map"]
    print("Map:")
    for i, row in enumerate(grid):
        print(f"  {i}: {''.join(row)}")
    return grid


def find_cell(grid, marker):
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == marker:
                return r, c
    raise ValueError(f"Marker '{marker}' not found in grid")


def cell_passable(cell: str, can_cross_water: bool) -> bool:
    if cell == "R":
        return False
    if cell == "W" and not can_cross_water:
        return False
    return True


def move_cost(cell: str, vehicle: str) -> tuple[float, float]:
    """Returns (fuel_cost, food_cost) for entering this cell with this vehicle/mode."""
    v = VEHICLES[vehicle]
    fuel = v["fuel"]
    food = v["food"]
    if cell == "T" and fuel > 0:
        fuel += TREE_FUEL_PENALTY
    return fuel, food


def dijkstra(grid, start, goal):
    """
    State: (row, col, vehicle_or_walk_mode, fuel_used_x1000, food_used_x1000)
    We search for minimum-step paths that respect resource limits.
    Returns (vehicle_name, list_of_commands) or None.
    """
    rows, cols = len(grid), len(grid[0])
    sr, sc = start
    gr, gc = goal

    best = {}

    # heap: (steps, fuel*1000, food*1000, row, col, mode, path)
    heap = []

    for start_vehicle in ["rocket", "car", "horse", "walk"]:
        heapq.heappush(heap, (0, 0, 0, sr, sc, start_vehicle, start_vehicle, []))

    while heap:
        steps, fuel_i, food_i, r, c, mode, start_v, path = heapq.heappop(heap)
        fuel = fuel_i / 1000
        food = food_i / 1000

        state_key = (r, c, mode, fuel_i, food_i, start_v)
        if state_key in best:
            continue
        best[state_key] = True

        if (r, c) == (gr, gc):
            return start_v, path

        can_water = VEHICLES[mode]["water"]

        # Move in four directions
        for direction, (dr, dc) in DIRECTION_DELTA.items():
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            cell = grid[nr][nc]
            if not cell_passable(cell, can_water):
                continue

            df, dd = move_cost(cell, mode)
            new_fuel = fuel + df
            new_food = food + dd
            if new_fuel > MAX_FUEL + 1e-9 or new_food > MAX_FOOD + 1e-9:
                continue

            new_fuel_i = round(new_fuel * 1000)
            new_food_i = round(new_food * 1000)
            new_state = (nr, nc, mode, new_fuel_i, new_food_i, start_v)
            if new_state not in best:
                heapq.heappush(heap, (
                    steps + 1, new_fuel_i, new_food_i,
                    nr, nc, mode, start_v,
                    path + [direction]
                ))

        # Dismount option: only if current mode is not already walk/horse
        if mode not in ("walk", "horse") and "dismount" not in path:
            # after dismount, move in walk mode (fuel=0, food=2.5)
            new_state = (r, c, "walk", fuel_i, food_i, start_v)
            if new_state not in best:
                heapq.heappush(heap, (
                    steps, fuel_i, food_i,
                    r, c, "walk", start_v,
                    path + ["dismount"]
                ))

    return None


def main():
    grid = fetch_map()
    start = find_cell(grid, "S")
    goal  = find_cell(grid, "G")
    print(f"Start: {start}, Goal: {goal}")

    result = dijkstra(grid, start, goal)
    if result is None:
        raise RuntimeError("No valid route found!")

    vehicle, commands = result
    print(f"Vehicle: {vehicle}")
    print(f"Commands: {commands}")
    print(f"Total moves: {len([c for c in commands if c != 'dismount'])}")

    answer = [vehicle] + commands

    response = send_to_central("savethem", answer)
    print("Central response:", response)


if __name__ == "__main__":
    main()
