import cadquery as cq
import random
from cadquery.vis import show

# ==========================================
# 1. PHYSICAL DIMENSIONS
# ==========================================
deck_width = 3975.0
joist_len = 2255.0
joist_w = 45.0
joist_h = 90.0
board_w = 140.0  # Garapa board width
board_h = 19.0  # Garapa board thickness
gap_rows = 6.4  # Swelling gap between rows
gap_boards = 3.0  # Swelling gap between board ends
vent_gap = 12.0  # Airflow gap below decking for fascia
fascia_h = 140.0  # Vertical fascia height
min_board_len = 600.0

# Sister Block Specs
sister_block_len = 140.0
sister_stock_count = 6
sister_stock_len = 1300.0

# Screw Logic Variables
screw_head_dia = 8.9
screw_butt_offset = 15.0  # Distance from board end for join screws
screw_edge_offset = 38.0  # Updated per request

# ==========================================
# 2. CALCULATIONS & LAYOUT RULES
# ==========================================
j2_c = board_w - (joist_w / 2)
j11_c = (deck_width - board_w) + (joist_w / 2)
mid_spacing = (j11_c - j2_c) / 9

joist_centers = [joist_w / 2, j2_c]
for i in range(1, 9):
    joist_centers.append(j2_c + (i * mid_spacing))
joist_centers.extend([j11_c, deck_width - (joist_w / 2)])

top_frame_join_joist = 5
anchor_idx = top_frame_join_joist - 1
split_x = joist_centers[anchor_idx]

# Picture Frame Inner Boundaries
pf_inner_west = board_w - board_h
pf_inner_east = deck_width - board_w + board_h
pf_inner_north = joist_len - board_w + board_h


def get_garapa_color():
    return cq.Color(random.uniform(0.72, 0.78), random.uniform(0.52, 0.58), random.uniform(0.22, 0.28))


# ==========================================
# 3. ADVANCED STOCK MANAGER
# ==========================================
class DeckStockManager:
    def __init__(self):
        self.garapa_stock = {3600: 25, 3300: 10, 3000: 10}
        self.garapa_registry = []
        self.offcuts = []
        self.sister_stock = [{'id': f'SISTER_STK_{i + 1}', 'rem': sister_stock_len, 'cuts': []} for i in
                             range(sister_stock_count)]
        self.sister_usage = []
        self.next_id = 1

    def allocate_garapa(self, length, usage, board_type="DECK"):
        self.offcuts.sort(key=lambda x: x['len'])
        for i, off in enumerate(self.offcuts):
            if off['len'] >= length:
                self.offcuts.pop(i)
                board = next(b for b in self.garapa_registry if b['id'] == off['bid'])
                board['cuts'].append({'len': length, 'usage': f"{board_type}: {usage}"})
                rem = off['len'] - length
                if rem >= 100: self.offcuts.append({'len': rem, 'bid': board['id']})
                return board['id']

        available = sorted([l for l, c in self.garapa_stock.items() if c > 0 and l >= length])
        if not available: raise Exception(f"OUT OF GARAPA STOCK for {usage}")

        chosen = available[0]
        self.garapa_stock[chosen] -= 1
        bid = f"P{self.next_id:02}"
        self.next_id += 1
        self.garapa_registry.append(
            {'id': bid, 'orig': chosen, 'cuts': [{'len': length, 'usage': f"{board_type}: {usage}"}]})

        rem = chosen - length
        if rem >= 100: self.offcuts.append({'len': rem, 'bid': bid})
        return bid

    def allocate_sister_block(self, joist_num, y_coord):
        for board in self.sister_stock:
            if board['rem'] >= sister_block_len:
                board['rem'] -= sister_block_len
                board['cuts'].append({'len': sister_block_len, 'usage': f"J{joist_num} @ Y={y_coord:.1f}"})
                self.sister_usage.append((joist_num, y_coord))
                return board['id']
        raise Exception("OUT OF SISTER JOIST STOCK.")


sm = DeckStockManager()

# ==========================================
# 4. COMPONENT CALCULATIONS
# ==========================================
W, L, D, OH = board_w, joist_len, deck_width, board_h

# --- A. PICTURE FRAME ---
# West/East side boards extend past joist ends to miter with North boards
pf_west_pts = [(-OH, 0), (W - OH, 0), (W - OH, L - W + OH), (-OH, L + OH)]
pf_east_pts = [(D + OH, 0), (D - W + OH, 0), (D - W + OH, L - W + OH), (D + OH, L + OH)]
pf_nw_pts = [(-OH, L + OH), (split_x, L + OH), (split_x, L - W + OH), (W - OH, L - W + OH)]
pf_ne_pts = [(split_x, L + OH), (D + OH, L + OH), (D - W + OH, L - W + OH), (split_x, L - W + OH)]

picture_frame_data = [
    {'pts': pf_west_pts, 'bid': sm.allocate_garapa(L + OH, "West Side", "PICTURE FRAME")},
    {'pts': pf_east_pts, 'bid': sm.allocate_garapa(L + OH, "East Side", "PICTURE FRAME")},
    {'pts': pf_nw_pts, 'bid': sm.allocate_garapa(split_x + OH, "North-West", "PICTURE FRAME")},
    {'pts': pf_ne_pts, 'bid': sm.allocate_garapa(D - split_x + OH, "North-East", "PICTURE FRAME")}
]

# --- B. FASCIA (FIXED POSITIONING) ---
# Side fascia boards moved away from center by board_h
fascia_data = []
# West Side: Outer edge is -(board_h * 2) from X=0
fascia_data.append({'pts': [(-OH, 0), (0, 0), (0, L), (-OH, L + OH)],
                    'bid': sm.allocate_garapa(L + OH, "West Face", "FASCIA")})
# East Side: Outer edge is +(board_h * 2) from X=D
fascia_data.append({'pts': [(D, 0), (D + OH, 0), (D + OH, L), (D, L + OH)],
                    'bid': sm.allocate_garapa(L + OH, "East Face", "FASCIA")})
# North Face
fascia_data.append({'pts': [(-OH, L + OH), (split_x, L + OH), (split_x, L), (0, L)],
                    'bid': sm.allocate_garapa(split_x + OH, "North Left", "FASCIA")})
fascia_data.append({'pts': [(split_x, L + OH), (D + OH, L + OH), (D, L), (split_x, L)],
                    'bid': sm.allocate_garapa(D - split_x + OH, "North Right", "FASCIA")})

# --- C. INFILL & SCREWS ---
infill_data = []
screw_positions = []
cy = pf_inner_north - gap_rows
in_x_start = pf_inner_west + gap_boards
in_x_end = pf_inner_east - gap_boards

for r in range(15):
    j_idx = random.randint(2, 9)
    tx = joist_centers[j_idx]
    l_end = tx - (gap_boards / 2)
    r_start = tx + (gap_boards / 2)

    infill_data.append({'len': l_end - in_x_start, 'x': in_x_start, 'y': cy,
                        'bid': sm.allocate_garapa(l_end - in_x_start, f"R{r + 1} L", "INFILL")})
    infill_data.append({'len': in_x_end - r_start, 'x': r_start, 'y': cy,
                        'bid': sm.allocate_garapa(in_x_end - r_start, f"R{r + 1} R", "INFILL")})

    row_y_center = cy - (W / 2)
    y_offs = [W / 2 - screw_edge_offset, -(W / 2 - screw_edge_offset)]

    for jc in joist_centers:
        if abs(jc - tx) < 0.1:  # At the Join
            for dy in y_offs:
                screw_positions.append((l_end - screw_butt_offset, row_y_center + dy))
                screw_positions.append((r_start + screw_butt_offset, row_y_center + dy))
        else:  # Standard Joist
            if in_x_start <= jc <= l_end or r_start <= jc <= in_x_end:
                for dy in y_offs: screw_positions.append((jc, row_y_center + dy))

    sm.allocate_sister_block(j_idx + 1, cy - W / 2)
    cy -= (W + gap_rows)

# ==========================================
# 5. ASSEMBLY RENDERING
# ==========================================
assembly = cq.Assembly()

# 1. Joists & Sister Blocks
for cp in joist_centers:
    assembly.add(cq.Workplane("XY").box(joist_w, L, joist_h).translate((cp, L / 2, -joist_h / 2)),
                 color=cq.Color(0.2, 0.2, 0.2))
for j_num, y in sm.sister_usage:
    assembly.add(cq.Workplane("XY").box(90, 140, 45).translate((joist_centers[j_num - 1], y, -22.5)),
                 color=cq.Color("orange"))

# 2. Decking & Screws
for pf in picture_frame_data:
    assembly.add(cq.Workplane("XY").polyline(pf['pts']).close().extrude(board_h), color=get_garapa_color())
for p in infill_data:
    assembly.add(
        cq.Workplane("XY").box(p['len'], W, board_h).translate((p['x'] + p['len'] / 2, p['y'] - W / 2, board_h / 2)),
        color=get_garapa_color())

scol = cq.Color(0.75, 0.75, 0.75)
for sx, sy in screw_positions:
    assembly.add(cq.Workplane("XY").cylinder(height=1.0, radius=screw_head_dia / 2).translate((sx, sy, board_h)),
                 color=scol)

# 3. Fascia
for f in fascia_data:
    assembly.add(cq.Workplane("XY").polyline(f['pts']).close().extrude(-fascia_h).translate((0, 0, -vent_gap)),
                 color=get_garapa_color())

show(assembly)

# ==========================================
# 6. REPORTING
# ==========================================
print("=" * 80)
print("DECK CONSTRUCTION REPORT")
print("=" * 80)
for b in sm.garapa_registry:
    print(f"{b['id']:12} | {b['orig']:7.1f}mm | {b['cuts'][0]['usage']}")
print(f"\nTOTAL SCREWS USED: {len(screw_positions)}")