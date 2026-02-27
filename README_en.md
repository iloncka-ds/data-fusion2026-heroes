# 🗺️ Data Fusion 2026 Task 3 — Solution Visualizer

> 🌐 Язык / Language: [🇷🇺 Русский](README.md) | **🇬🇧 English**


Interactive visualization for [Data Fusion 2026 Task 3](https://ods.ai/competitions/data-fusion2026-heroes) solutions. Shows hero movements, mill states, and timing across the 7‑day game week. Self‑contained, runs in any browser.

---

## 🧭 Generate Coordinates

Before using the visualizer, create `coords.csv` from the competition distance matrices:

```bash
python generate_coords.py
```

**Dependencies:** `pandas`, `numpy`, `networkx`  
**Inputs:** `dist_objects.csv`, `dist_start.csv`  
**Output:** `coords.csv` with columns `node_id`, `x`, `y`.

---

## 🚀 Generate Visualization


### 📁 Input Data

| File               | Description                                                    |
| ------------------ | -------------------------------------------------------------- |
| `coords.csv`       | Node coordinates (depot + 700 mills) – must be generated first |
| `data_objects.csv` | Mill metadata: `object_id`, `day_open`, `reward`               |
| `data_heroes.csv`  | Hero metadata: `hero_id`, `move_points`                        |
| `solution_*.csv`   | Your solution: `hero_id`, `object_id` sequences                |


---

```python
from generate_visualization import generate_visualization

generate_visualization()                       # uses default solution
generate_visualization('my_solution.csv', 'viz.html')
```


Output: a single `.html` file – no server needed.

---

## 🖥️ Interface

- **Canvas:** 1000×800 px, nodes placed using `coords.csv`.
- **Routes:** Each hero has a unique color; static paths + glowing live trail.
- **Controls:** Play/pause, slider scrubbing, current day / MP display.

---

## 🎨 Node States

| Icon | State           | Meaning                            |
| ---- | --------------- | ---------------------------------- |
| ⬤    | Not open yet    | current_day < day_open             |
| 💰    | Open today      | current_day == day_open, unvisited |
| ✅    | Visited on‑time | rewarded (500 gold)                |
| ❗    | Late arrival    | visited after day_open, no reward  |
| ✖    | Missed          | day passed, never visited          |
| 🏰    | Depot           | node 0                             |

Visited nodes are tinted with the visiting hero’s color.

