import pandas as pd
import polars as pl
import json
import os
from heroes_utils import HeroesInstance

def generate_visualization(solution_path='sample_submit.csv', output_path='heroes_solution_visualization.html'):
    print(f"Loading data and extending solution from {solution_path}...")
    # Load coordinates
    coords_df = pd.read_csv('coords.csv', index_col='node_id')
    
    # Load HeroesInstance
    hi = HeroesInstance(data_path='')
    submit = pl.read_csv(solution_path)
    # Use remove_out_of_time=True to only include actions within the 7-day limit
    detailed_submit = hi.expand_solution(hi.basic_check(submit), remove_out_of_time=True)
    
    # Package nodes
    nodes_data = []
    nodes_data.append({
        'id': 0,
        'x': float(coords_df.loc[0, 'x']),
        'y': float(coords_df.loc[0, 'y']),
        'day_open': 1,
        'reward': 0,
        'is_depot': True
    })
    for row in hi.objects.iter_rows(named=True):
        nid = row['object_id']
        nodes_data.append({
            'id': nid,
            'x': float(coords_df.loc[nid, 'x']),
            'y': float(coords_df.loc[nid, 'y']),
            'day_open': row['day_open'],
            'reward': row['reward'],
            'is_depot': False
        })
        
    # Collect unique hero ids used in the solution
    used_hero_ids = sorted(set(row['hero_id'] for row in detailed_submit.iter_rows(named=True)))
    
    heroes_data = []
    for row in hi.heroes.iter_rows(named=True):
        heroes_data.append({
            'id': row['hero_id'],
            'max_move_points': row['move_points']
        })
        
    # Build journeys with is_late info
    journeys = []
    for row in detailed_submit.iter_rows(named=True):
        hid = row['hero_id']
        max_mp = hi.hero_mp_map[hid]
        from_id = row['object_id_from']
        to_id = row['object_id_to']
        
        mp_used_start = max_mp - row['move_points_start']
        time_start = (row['day_start'] - 1) * 2000 + mp_used_start
        
        mp_used_arrive = max_mp - row['move_points_arrive']
        time_arrive = (row['day_arrive'] - 1) * 2000 + mp_used_arrive
        
        mp_used_leave = max_mp - row['move_points_leave']
        time_leave = (row['day_leave'] - 1) * 2000 + mp_used_leave
        
        journeys.append({
            'hero_id': hid,
            'max_mp': max_mp,
            'from': from_id,
            'to': to_id,
            'time_start': time_start,
            'time_arrive': time_arrive,
            'time_leave': time_leave,
            'reward': row['reward'],
            'is_late': bool(row['is_late'])
        })

    max_time = max([j['time_leave'] for j in journeys]) if journeys else 14000
    
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Data Fusion Contest 2026 - Heroes</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        h1 { margin-top: 0; color: #f0c040; text-shadow: 0 0 15px rgba(240,192,64,0.4); letter-spacing: 2px; }
        .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 16px; background: #161b22; padding: 12px 24px; border-radius: 10px; border: 1px solid #30363d; width: 1000px; }
        button { background: #238636; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: 600; }
        button:hover { background: #2ea043; }
        input[type=range] { flex-grow: 1; accent-color: #f0c040; height: 6px; }
        .info { font-size: 14px; font-family: 'JetBrains Mono', monospace; color: #8b949e; min-width: 120px; text-align: right; }
        .info b { color: #f0c040; }
        #canvas-container { position: relative; width: 1000px; height: 800px; background: #0d1117; border-radius: 10px; overflow: hidden; border: 1px solid #30363d; }
        canvas { position: absolute; top: 0; left: 0; }
        #routes-canvas { z-index: 1; }
        #dynamic-canvas { z-index: 2; }

        /* SVG image-based node icons */
        .target {
            position: absolute;
            transform: translate(-50%, -50%);
            z-index: 10;
            pointer-events: auto;
            cursor: pointer;
            transition: width 0.2s, height 0.2s, filter 0.2s;
            image-rendering: auto;
        }
        .target:hover { z-index: 50; filter: brightness(1.4); }

        /* Hero icons */
        .hero-icon {
            position: absolute;
            transform: translate(-50%, -50%);
            z-index: 100;
            pointer-events: none;
            transition: left 0.05s, top 0.05s;
        }
        .hero-label {
            position: absolute;
            transform: translate(-50%, -100%);
            font-size: 9px;
            font-weight: bold;
            color: white;
            text-shadow: 0 0 3px black, 0 0 3px black;
            pointer-events: none;
            z-index: 101;
            white-space: nowrap;
        }
        .tooltip { position: absolute; background: rgba(13,17,23,0.95); color: #c9d1d9; padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; display: none; z-index: 300; white-space: nowrap; border: 1px solid #30363d; }
        .legend { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; background: #161b22; padding: 10px 16px; border-radius: 8px; border: 1px solid #30363d; width: 1000px; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #8b949e; }
        .legend-swatch { width: 20px; height: 20px; }
        .legend-sep { width: 1px; height: 20px; background: #30363d; margin: 0 6px; }
    </style>
</head>
<body>
    <h1>&#9876; Data Fusion Contest 2026 - Heroes</h1>
    
    <div class="controls">
        <button id="play-pause">&#9654; Play</button>
        <input type="range" id="slider" min="0" max="MAX_TIME" value="0" step="10">
        <div class="info">Day <b id="day-display">1</b> &middot; MP <b id="time-display">0</b></div>
    </div>
    
    <div id="canvas-container">
        <canvas id="routes-canvas" width="1000" height="800"></canvas>
        <canvas id="dynamic-canvas" width="1000" height="800"></canvas>
        <div id="objects-layer"></div>
        <div id="heroes-layer"></div>
        <div id="tooltip" class="tooltip"></div>
    </div>
    
    <div id="legend" class="legend"></div>

    <script>
        const nodes = NODES_DATA;
        const journeys = JOURNEYS_DATA;
        const usedHeroIds = USED_HERO_IDS;
        const maxTime = MAX_TIME;

        // ─────────────────────────────────────────────
        //  SVG Asset Data URIs
        //  "open"    = gold coin  (yellow reserved — do NOT use for heroes)
        //  "visited" = green check
        //  "late"    = red/orange exclamation
        //  "closed"  = grey cross
        //  "depot"   = purple castle
        //  "hero"    = colored face — tinted per hero via CSS hue-rotate
        // ─────────────────────────────────────────────
        const ASSETS = {
            depot:   'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M10 90 L10 50 L50 10 L90 50 L90 90 Z" fill="%238e44ad" stroke="%23ecf0f1" stroke-width="4"/><rect x="40" y="60" width="20" height="30" fill="%237f8c8d"/><rect x="20" y="52" width="12" height="20" fill="%23ecf0f1" opacity="0.5"/><rect x="68" y="52" width="12" height="20" fill="%23ecf0f1" opacity="0.5"/></svg>',
            open:    'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="%23f1c40f" stroke="%23d35400" stroke-width="8"/><text x="50" y="65" font-size="40" text-anchor="middle" fill="%23d35400" font-family="sans-serif" font-weight="bold">$</text></svg>',
            // closed = not yet reachable — plain grey circle, no symbol
            closed:  'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="%2348515a" stroke="%2330363d" stroke-width="6"/></svg>',
            // missed = was open on a previous day but never visited — grey circle + cross
            missed:  'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="%2348515a" stroke="%2330363d" stroke-width="6"/><line x1="32" y1="32" x2="68" y2="68" stroke="%23c0392b" stroke-width="9" stroke-linecap="round"/><line x1="68" y1="32" x2="32" y2="68" stroke="%23c0392b" stroke-width="9" stroke-linecap="round"/></svg>',
            visited: 'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="%232ecc71" stroke="%2327ae60" stroke-width="8"/><polyline points="28,52 44,68 72,32" fill="none" stroke="white" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            late:    'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="%23e74c3c" stroke="%23ff6b35" stroke-width="8"/><text x="50" y="68" font-size="50" text-anchor="middle" fill="white" font-family="sans-serif" font-weight="bold">!</text></svg>',
            // Base hero SVG — blue tint; we apply hue-rotate via inline filter to get per-hero colour
            hero:    'data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="45" fill="%232980b9" stroke="white" stroke-width="5"/><circle cx="35" cy="42" r="6" fill="white"/><circle cx="65" cy="42" r="6" fill="white"/><path d="M30 63 Q50 82 70 63" stroke="white" stroke-width="6" fill="none" stroke-linecap="round"/></svg>'
        };

        // ─────────────────────────────────────────────
        //  Hero colour system  — distributes hues evenly
        //  but SKIPS yellow band (~40°–78°) already used
        //  by open-node icons.
        // ─────────────────────────────────────────────
        const YELLOW_START = 40;
        const YELLOW_END   = 78;
        const YELLOW_SKIP  = YELLOW_END - YELLOW_START; // 38°
        const EFFECTIVE_RANGE = 360 - YELLOW_SKIP;      // 322°

        function heroHue(index, total) {
            // spread evenly over 322°, then shift past yellow gap
            let h = Math.round((index / Math.max(total, 1)) * EFFECTIVE_RANGE);
            if (h >= YELLOW_START) h += YELLOW_SKIP;
            return h % 360;
        }

        // Pre-compute hue for every used hero
        const heroHueMap = {};
        usedHeroIds.forEach((hid, i) => {
            heroHueMap[hid] = heroHue(i, usedHeroIds.length);
        });

        // Helpers that produce CSS colour strings
        function heroHSL(hid, sat, light)       { return `hsl(${heroHueMap[hid]}, ${sat}%, ${light}%)`; }
        function heroHSLA(hid, sat, light, a)   { return `hsla(${heroHueMap[hid]}, ${sat}%, ${light}%, ${a})`; }

        // CSS hue-rotate value to tint the blue base hero SVG to the hero's hue
        // Base SVG uses hue ≈ 207° (Flat-UI blue #2980b9)
        const BASE_HERO_HUE = 207;
        function heroImgFilter(hid) {
            const rotate = ((heroHueMap[hid] - BASE_HERO_HUE) + 360) % 360;
            return `hue-rotate(${rotate}deg) saturate(1.3) brightness(1.05)`;
        }

        // Generate a per-hero "visited" SVG — hero colour (dark) fill + white checkmark
        // Pre-encoded so they can be set directly on img.src without innerHTML issues
        const visitedAssets = {};
        usedHeroIds.forEach(hid => {
            const h = heroHueMap[hid];
            // dark fill = hero hue, sat 55%, light 28%; border = hero hue, sat 70%, light 42%
            const fill   = `hsl(${h},55%,28%)`;
            const stroke = `hsl(${h},70%,42%)`;
            const svg = `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">`
                      + `<circle cx="50" cy="50" r="40" fill="${fill}" stroke="${stroke}" stroke-width="8"/>`
                      + `<polyline points="28,52 44,68 72,32" fill="none" stroke="white" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>`
                      + `</svg>`;
            visitedAssets[hid] = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
        });

        // ─────────────────────────────────────────────
        //  Normalise coordinates
        // ─────────────────────────────────────────────
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        nodes.forEach(n => {
            if (n.x < minX) minX = n.x; if (n.x > maxX) maxX = n.x;
            if (n.y < minY) minY = n.y; if (n.y > maxY) maxY = n.y;
        });
        const W = 1000, H = 800, pad = 50;
        const rangeX = maxX - minX || 1, rangeY = maxY - minY || 1;
        nodes.forEach(n => {
            n.cx = pad + ((n.x - minX) / rangeX) * (W - 2 * pad);
            n.cy = pad + ((n.y - minY) / rangeY) * (H - 2 * pad);
        });

        // ─────────────────────────────────────────────
        //  Draw static route edges (per-hero colour)
        // ─────────────────────────────────────────────
        const routesCtx = document.getElementById('routes-canvas').getContext('2d');
        // Pass 1 – dark shadow for readability
        journeys.forEach(j => {
            const n1 = nodes[j.from], n2 = nodes[j.to];
            routesCtx.strokeStyle = 'rgba(0,0,0,0.45)';
            routesCtx.lineWidth = 4.5;
            routesCtx.beginPath();
            routesCtx.moveTo(n1.cx, n1.cy);
            routesCtx.lineTo(n2.cx, n2.cy);
            routesCtx.stroke();
        });
        // Pass 2 – hero-coloured line on top
        journeys.forEach(j => {
            const n1 = nodes[j.from], n2 = nodes[j.to];
            routesCtx.strokeStyle = heroHSLA(j.hero_id, 80, 62, 0.60);
            routesCtx.lineWidth = 2.2;
            routesCtx.beginPath();
            routesCtx.moveTo(n1.cx, n1.cy);
            routesCtx.lineTo(n2.cx, n2.cy);
            routesCtx.stroke();
        });

        const dynCtx   = document.getElementById('dynamic-canvas').getContext('2d');
        const objLayer = document.getElementById('objects-layer');
        const heroLayer= document.getElementById('heroes-layer');
        const tooltip  = document.getElementById('tooltip');

        // ─────────────────────────────────────────────
        //  Create node <img> elements
        // ─────────────────────────────────────────────
        const objElements = {};
        // Build node lookup by id
        const nodeById = {};
        nodes.forEach(n => { nodeById[n.id] = n; });

        nodes.forEach(n => {
            const img = document.createElement('img');
            img.className = 'target';
            img.style.left = n.cx + 'px';
            img.style.top  = n.cy + 'px';

            if (n.is_depot) {
                img.src = ASSETS.depot;
                img.style.width  = '36px';
                img.style.height = '36px';
            } else {
                img.src = ASSETS.closed;
                img.style.width  = '18px';
                img.style.height = '18px';
            }

            img.onmouseover = (e) => {
                tooltip.style.display = 'block';
                tooltip.innerHTML = n.is_depot
                    ? `<b>Castle (Depot)</b>`
                    : `<b>Target #${n.id}</b><br>Day open: ${n.day_open}<br>Reward: ${n.reward}`;
            };
            img.onmousemove = (e) => {
                tooltip.style.left = (e.offsetX + 15) + 'px';
                tooltip.style.top  = (e.offsetY + 15) + 'px';
            };
            img.onmouseout = () => { tooltip.style.display = 'none'; };

            objElements[n.id] = img;
            objLayer.appendChild(img);
        });

        // ─────────────────────────────────────────────
        //  Legend — node states + hero colours
        //  Uses createElement (not innerHTML) so SVG data
        //  URIs and filter strings are never HTML-interpolated
        // ─────────────────────────────────────────────
        const legendDiv = document.getElementById('legend');

        function makeLegendItem(srcOrNull, filterOrNull, dotColorOrNull, labelText) {
            const el  = document.createElement('div');
            el.className = 'legend-item';

            if (srcOrNull) {
                const ic = document.createElement('img');
                ic.style.width  = '22px';
                ic.style.height = '22px';
                ic.style.flexShrink = '0';
                ic.src = srcOrNull;
                if (filterOrNull) ic.style.filter = filterOrNull;
                el.appendChild(ic);
            } else if (dotColorOrNull) {
                // Coloured circle fallback (unused currently)
                const dot = document.createElement('div');
                dot.style.cssText = `width:14px;height:14px;border-radius:50%;background:${dotColorOrNull};flex-shrink:0;`;
                el.appendChild(dot);
            }

            const lbl = document.createElement('span');
            lbl.textContent = labelText;
            el.appendChild(lbl);
            return el;
        }

        // Static state icons
        legendDiv.appendChild(makeLegendItem(ASSETS.closed,  null, null, 'Not open yet'));
        legendDiv.appendChild(makeLegendItem(ASSETS.open,    null, null, 'Open today'));
        legendDiv.appendChild(makeLegendItem(ASSETS.missed,  null, null, 'Missed'));
        legendDiv.appendChild(makeLegendItem(ASSETS.late,    null, null, 'Late arrival'));
        legendDiv.appendChild(makeLegendItem(ASSETS.depot,   null, null, 'Depot'));

        // Separator
        const sep = document.createElement('div');
        sep.className = 'legend-sep';
        legendDiv.appendChild(sep);

        // Per-hero: tinted hero icon + a small visited-color swatch + label
        usedHeroIds.forEach(hid => {
            // Hero face icon
            const heroEl = makeLegendItem(ASSETS.hero, heroImgFilter(hid), null, '');
            legendDiv.appendChild(heroEl);

            // Visited swatch for this hero
            const visEl = makeLegendItem(visitedAssets[hid], null, null, '');
            visEl.querySelector('img').style.width  = '18px';
            visEl.querySelector('img').style.height = '18px';
            legendDiv.appendChild(visEl);

            // Label
            const lbl = document.createElement('div');
            lbl.className = 'legend-item';
            const span = document.createElement('span');
            span.textContent = `Hero ${hid}`;
            span.style.color = heroHSL(hid, 80, 70);
            lbl.appendChild(span);

            // Separator between heroes
            const hsep = document.createElement('div');
            hsep.style.cssText = 'width:1px;height:18px;background:#30363d;margin:0 4px;';
            lbl.appendChild(hsep);
            legendDiv.appendChild(lbl);
        });

        // ─────────────────────────────────────────────
        //  Animation helpers
        // ─────────────────────────────────────────────
        function getHeroPosition(j, t) {
            const n1 = nodes[j.from];
            const n2 = nodes[j.to];
            if (t <= j.time_start) return { x: n1.cx, y: n1.cy };
            if (t >= j.time_arrive) return { x: n2.cx, y: n2.cy };
            const ratio = (t - j.time_start) / (j.time_arrive - j.time_start);
            return { x: n1.cx + (n2.cx - n1.cx) * ratio, y: n1.cy + (n2.cy - n1.cy) * ratio };
        }

        const heroElements = {};
        const heroLabels   = {};

        // ─────────────────────────────────────────────
        //  Main update function
        // ─────────────────────────────────────────────
        function updateVisualization() {
            const day        = Math.floor(currentTime / 2000) + 1;
            const timeInDay  = currentTime % 2000;
            dayDisp.innerText  = day;
            timeDisp.innerText = Math.floor(timeInDay);

            // ── 1. Determine visit state for each node ──
            // visitInfo: node_id -> { hero_id, is_late, reward }
            const visitInfo = {};
            journeys.forEach(j => {
                if (j.time_leave <= currentTime) {
                    // keep latest arrival per node (last visit wins)
                    visitInfo[j.to] = { hero_id: j.hero_id, is_late: j.is_late, reward: j.reward };
                }
            });

            nodes.forEach(n => {
                if (n.is_depot) return;
                const img  = objElements[n.id];
                const info = visitInfo[n.id];

                if (info) {
                    if (info.reward > 0) {
                        // Successful visit — hero-coloured dark check icon
                        const asset = visitedAssets[info.hero_id] || ASSETS.visited;
                        img.src = asset;
                        img.style.width  = '22px';
                        img.style.height = '22px';
                        img.style.filter = `drop-shadow(0 0 5px ${heroHSL(info.hero_id, 70, 45)})`;
                    } else if (info.is_late) {
                        // Late — red exclamation, hero-coloured glow
                        img.src = ASSETS.late;
                        img.style.width  = '24px';
                        img.style.height = '24px';
                        img.style.filter = `drop-shadow(0 0 6px ${heroHSL(info.hero_id, 90, 60)})`;
                    } else {
                        // Visited but no reward
                        const asset = visitedAssets[info.hero_id] || ASSETS.visited;
                        img.src = asset;
                        img.style.width  = '20px';
                        img.style.height = '20px';
                        img.style.filter = 'none';
                    }
                } else if (day === n.day_open) {
                    // Opening day, not yet collected — gold coin
                    img.src = ASSETS.open;
                    img.style.width  = '20px';
                    img.style.height = '20px';
                    img.style.filter = 'none';
                } else if (day > n.day_open) {
                    // Was open on a previous day but never visited — missed (grey cross)
                    img.src = ASSETS.missed;
                    img.style.width  = '18px';
                    img.style.height = '18px';
                    img.style.filter = 'none';
                } else {
                    // Not yet open — plain grey circle
                    img.src = ASSETS.closed;
                    img.style.width  = '16px';
                    img.style.height = '16px';
                    img.style.filter = 'none';
                }
            });

            // ── 2. Update hero positions & active/inactive state ──
            // trulyActive: hero has a journey segment covering currentTime
            const trulyActive = new Set();
            journeys.forEach(j => {
                if (currentTime >= j.time_start && currentTime <= j.time_leave) {
                    trulyActive.add(j.hero_id);
                }
            });

            // heroLastKnown: last position we can determine for each hero
            const heroLastKnown = {};
            journeys.forEach(j => {
                if (currentTime >= j.time_start && currentTime <= j.time_leave) {
                    heroLastKnown[j.hero_id] = { pos: getHeroPosition(j, currentTime), max_mp: j.max_mp };
                } else if (currentTime > j.time_leave) {
                    const existing = heroLastKnown[j.hero_id];
                    if (!existing || (existing._leaveTime || 0) < j.time_leave) {
                        heroLastKnown[j.hero_id] = {
                            pos: { x: nodes[j.to].cx, y: nodes[j.to].cy },
                            max_mp: j.max_mp,
                            _leaveTime: j.time_leave
                        };
                    }
                }
            });

            for (let hid in heroLastKnown) {
                if (!heroElements[hid]) {
                    const img = document.createElement('img');
                    img.className = 'hero-icon';
                    img.src = ASSETS.hero;
                    heroElements[hid] = img;
                    heroLayer.appendChild(img);

                    const lbl = document.createElement('div');
                    lbl.className = 'hero-label';
                    lbl.innerText = `H${hid}`;
                    heroLabels[hid] = lbl;
                    heroLayer.appendChild(lbl);
                }

                const hData = heroLastKnown[hid];
                const img   = heroElements[hid];
                const lbl   = heroLabels[hid];
                const active = trulyActive.has(parseInt(hid));

                // Size scaled by move-point capacity
                const size = 18 + Math.max(0, Math.min(1, (hData.max_mp - 1500) / 1000)) * 14;

                img.style.left   = hData.pos.x + 'px';
                img.style.top    = hData.pos.y + 'px';
                img.style.width  = size + 'px';
                img.style.height = size + 'px';
                img.style.opacity = active ? '1' : '0.45';

                if (active) {
                    // Full hero colour
                    img.style.filter = heroImgFilter(hid);
                    lbl.style.color  = heroHSL(hid, 80, 80);
                } else {
                    // Inactive (resting) — desaturated / white tint
                    const rot = ((heroHueMap[hid] - BASE_HERO_HUE) + 360) % 360;
                    img.style.filter = `hue-rotate(${rot}deg) saturate(0.1) brightness(1.6)`;
                    lbl.style.color  = '#888';
                }

                lbl.style.left = hData.pos.x + 'px';
                lbl.style.top  = (hData.pos.y - size / 2 - 4) + 'px';
            }

            // ── 3. Animated trail on dynamic canvas ──
            dynCtx.clearRect(0, 0, W, H);
            journeys.forEach(j => {
                if (currentTime >= j.time_start && currentTime <= j.time_arrive) {
                    const n1  = nodes[j.from];
                    const pos = getHeroPosition(j, currentTime);
                    // Glow shadow pass
                    dynCtx.strokeStyle = heroHSLA(j.hero_id, 90, 70, 0.30);
                    dynCtx.lineWidth = 9;
                    dynCtx.lineCap = 'round';
                    dynCtx.beginPath();
                    dynCtx.moveTo(n1.cx, n1.cy);
                    dynCtx.lineTo(pos.x, pos.y);
                    dynCtx.stroke();
                    // Bright core
                    dynCtx.strokeStyle = heroHSLA(j.hero_id, 85, 65, 0.95);
                    dynCtx.lineWidth = 3.5;
                    dynCtx.beginPath();
                    dynCtx.moveTo(n1.cx, n1.cy);
                    dynCtx.lineTo(pos.x, pos.y);
                    dynCtx.stroke();
                }
            });
        }

        // ─────────────────────────────────────────────
        //  Playback controls
        // ─────────────────────────────────────────────
        let currentTime = 0;
        let isPlaying   = false;
        let playInterval;
        const slider   = document.getElementById('slider');
        const playBtn  = document.getElementById('play-pause');
        const dayDisp  = document.getElementById('day-display');
        const timeDisp = document.getElementById('time-display');

        slider.addEventListener('input', (e) => {
            currentTime = parseInt(e.target.value);
            updateVisualization();
        });

        playBtn.addEventListener('click', () => {
            if (isPlaying) {
                clearInterval(playInterval);
                playBtn.innerHTML = '&#9654; Play';
            } else {
                playInterval = setInterval(() => {
                    currentTime += 10;
                    if (currentTime > maxTime) currentTime = 0;
                    slider.value = currentTime;
                    updateVisualization();
                }, 50);
                playBtn.innerHTML = '&#9646;&#9646; Pause';
            }
            isPlaying = !isPlaying;
        });

        updateVisualization();
    </script>
</body>
</html>"""

    html_template = html_template.replace("NODES_DATA",    json.dumps(nodes_data))
    html_template = html_template.replace("JOURNEYS_DATA", json.dumps(journeys))
    html_template = html_template.replace("USED_HERO_IDS", json.dumps(used_hero_ids))
    html_template = html_template.replace("MAX_TIME",      str(max_time))

    with open(output_path, 'w') as f:
        f.write(html_template)

    print(f"Interactive visualization generated: {output_path}")


if __name__ == '__main__':
    generate_visualization()
