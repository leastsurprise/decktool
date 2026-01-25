import cadquery as cq
import random
import statistics
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
sister_block_len = 140.0 # Length matches standard board width
sister_stock_count = 6
sister_stock_len = 1300.0

# Screw Logic Variables
screw_head_dia = 8.9
screw_butt_offset = 15.0
screw_edge_offset = 38.0

# ==========================================
# 2. LAYOUT & SIMULATION RULES
# ==========================================
top_frame_join_joist = 5
vertical_row_gap = 3
horizontal_joist_gap = 2
list_of_infill_indices = list(range(2, 10))

# ==========================================
# 3. CALCULATIONS & INITIALIZATION
# ==========================================
j2_c = board_w - (joist_w / 2)
j11_c = (deck_width - board_w) + (joist_w / 2)
mid_spacing = (j11_c - j2_c) / 9

joist_centers = [joist_w / 2, j2_c]
for i in range(1, 9):
    joist_centers.append(j2_c + (i * mid_spacing))
joist_centers.extend([j11_c, deck_width - (joist_w / 2)])

anchor_idx = top_frame_join_joist - 1
split_x = joist_centers[anchor_idx]

pf_inner_west = board_w - board_h
pf_inner_east = deck_width - board_w + board_h
pf_inner_north = joist_len - board_w + board_h

def get_garapa_color():
    return cq.Color(random.uniform(0.72, 0.78), random.uniform(0.52, 0.58), random.uniform(0.22, 0.28))

cy_start = pf_inner_north - gap_rows
temp_cy = cy_start
num_rows = 0
while temp_cy > gap_rows + 1.0:
    num_rows += 1
    temp_cy -= (board_w + gap_rows)

# ==========================================
# 4. LAYOUT OPTIMIZATION
# ==========================================
def generate_candidate():
    joins = []
    lockout = {i: 0 for i in list_of_infill_indices}
    prev_idx = anchor_idx
    for r in range(num_rows):
        legal = [i for i in list_of_infill_indices if lockout[i] == 0 and abs(i - prev_idx) >= horizontal_joist_gap]
        if not legal: legal = [i for i in list_of_infill_indices if lockout[i] == 0]
        if not legal: return None
        chosen = random.choice(legal)
        joins.append(chosen)
        prev_idx = chosen
        for i in lockout:
            if lockout[i] > 0: lockout[i] -= 1
        lockout[chosen] = vertical_row_gap + 1
    return joins

def score_layout(joins):
    center_point = 5.5
    left_offsets = [center_point - j for j in joins if j <= 5]
    right_offsets = [j - center_point for j in joins if j >= 6]
    if not left_offsets or not right_offsets: return 9999.0
    mean_imb = abs(statistics.mean(left_offsets) - statistics.mean(right_offsets))
    var_l = statistics.variance(left_offsets) if len(left_offsets) > 1 else 0
    var_r = statistics.variance(right_offsets) if len(right_offsets) > 1 else 0
    return mean_imb + var_l + var_r + abs(var_l - var_r)

candidates = []
for _ in range(5000):
    c = generate_candidate()
    if c: candidates.append((score_layout(c), c))
candidates.sort(key=lambda x: x[0])
best_score, row_joins = candidates[0]

# ==========================================
# 5. ADVANCED STOCK MANAGER
# ==========================================
class DeckStockManager:
    def __init__(self):
        self.garapa_stock = {3600: 10, 3300: 10, 3000: 10}
        self.garapa_registry = []
        self.offcuts = []
        self.sister_stock = [{'id': f'SISTER_STK_{i + 1}', 'rem': sister_stock_len, 'cuts': []} for i in range(sister_stock_count)]
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
        self.garapa_registry.append({'id': bid, 'orig': chosen, 'cuts': [{'len': length, 'usage': f"{board_type}: {usage}"}]})
        rem = chosen - length
        if rem >= 100: self.offcuts.append({'len': rem, 'bid': bid})
        return bid

    def allocate_sister_block(self, joist_num, y_coord, custom_len=sister_block_len):
        # custom_len is used if the deck board is cut (e.g. last row)
        for board in self.sister_stock:
            if board['rem'] >= custom_len:
                board['rem'] -= custom_len
                board['cuts'].append({'len': custom_len, 'usage': f"J{joist_num} @ Y={y_coord:.1f}"})
                self.sister_usage.append((joist_num, y_coord, custom_len))
                return board['id']
        raise Exception("OUT OF SISTER JOIST STOCK.")

sm = DeckStockManager()

# ==========================================
# 6. COMPONENT CALCULATIONS
# ==========================================
W, L, D, OH = board_w, joist_len, deck_width, board_h

# PICTURE FRAME allocation
picture_frame_data = [
    {'pts': [(-OH, 0), (W-OH, 0), (W-OH, L-W+OH), (-OH, L+OH)], 'bid': sm.allocate_garapa(L + OH, "West Side", "PICTURE FRAME")},
    {'pts': [(D+OH, 0), (D-W+OH, 0), (D-W+OH, L-W+OH), (D+OH, L+OH)], 'bid': sm.allocate_garapa(L + OH, "East Side", "PICTURE FRAME")},
    {'pts': [(-OH, L+OH), (split_x, L+OH), (split_x, L-W+OH), (W-OH, L-W+OH)], 'bid': sm.allocate_garapa(split_x + OH, "North-West", "PICTURE FRAME")},
    {'pts': [(split_x, L+OH), (D+OH, L+OH), (D-W+OH, L-W+OH), (split_x, L-W+OH)], 'bid': sm.allocate_garapa(D - split_x + OH, "North-East", "PICTURE FRAME")}
]

# FASCIA allocation from Garapa supply
fascia_data = [
    {'pts': [(-OH, 0), (0, 0), (0, L), (-OH, L+OH)], 'bid': sm.allocate_garapa(L + OH, "West Face", "FASCIA")},
    {'pts': [(D, 0), (D+OH, 0), (D+OH, L), (D, L+OH)], 'bid': sm.allocate_garapa(L + OH, "East Face", "FASCIA")},
    {'pts': [(-OH, L+OH), (split_x, L+OH), (split_x, L), (0, L)], 'bid': sm.allocate_garapa(split_x + OH, "North Left", "FASCIA")},
    {'pts': [(split_x, L+OH), (D+OH, L+OH), (D, L), (split_x, L)], 'bid': sm.allocate_garapa(D - split_x + OH, "North Right", "FASCIA")}
]

infill_data, screw_positions, cy = [], [], cy_start
in_x_start, in_x_end = pf_inner_west + gap_boards, pf_inner_east - gap_boards

for r in range(num_rows):
    j_idx = row_joins[r]
    tx = joist_centers[j_idx]
    l_end, r_start = tx - (gap_boards / 2), tx + (gap_boards / 2)
    rw = W if (cy - gap_rows) >= W else (cy - gap_rows)

    infill_data.append({'len': l_end - in_x_start, 'x': in_x_start, 'y': cy, 'w': rw, 'bid': sm.allocate_garapa(l_end - in_x_start, f"R{r + 1} L", "INFILL")})
    infill_data.append({'len': in_x_end - r_start, 'x': r_start, 'y': cy, 'w': rw, 'bid': sm.allocate_garapa(in_x_end - r_start, f"R{r + 1} R", "INFILL")})

    row_y_center = cy - (rw / 2)
    y_offs = [rw / 2 - screw_edge_offset, -(rw / 2 - screw_edge_offset)]
    for jc in joist_centers:
        if abs(jc - tx) < 0.1:
            for dy in y_offs:
                screw_positions.append((l_end - screw_butt_offset, row_y_center + dy))
                screw_positions.append((r_start + screw_butt_offset, row_y_center + dy))
        elif in_x_start <= jc <= l_end or r_start <= jc <= in_x_end:
            for dy in y_offs: screw_positions.append((jc, row_y_center + dy))

    # Sister block cut to match partial board width if necessary
    sm.allocate_sister_block(j_idx + 1, cy - rw / 2, custom_len=rw)
    cy -= (rw + gap_rows)

# ==========================================
# 7. ASSEMBLY RENDERING
# ==========================================
assembly = cq.Assembly()
for cp in joist_centers:
    assembly.add(cq.Workplane("XY").box(joist_w, L, joist_h).translate((cp, L / 2, -joist_h / 2)), color=cq.Color(0.2, 0.2, 0.2))
for j_num, y, block_l in sm.sister_usage:
    assembly.add(cq.Workplane("XY").box(90, block_l, 45).translate((joist_centers[j_num - 1], y, -22.5)), color=cq.Color("orange"))
for pf in picture_frame_data:
    assembly.add(cq.Workplane("XY").polyline(pf['pts']).close().extrude(board_h), color=get_garapa_color())
for p in infill_data:
    assembly.add(cq.Workplane("XY").box(p['len'], p['w'], board_h).translate((p['x'] + p['len'] / 2, p['y'] - p['w'] / 2, board_h / 2)), color=get_garapa_color())
for sx, sy in screw_positions:
    assembly.add(cq.Workplane("XY").cylinder(height=1.0, radius=screw_head_dia / 2).translate((sx, sy, board_h)), color=cq.Color(0.75, 0.75, 0.75))
for f in fascia_data:
    assembly.add(cq.Workplane("XY").polyline(f['pts']).close().extrude(-fascia_h).translate((0, 0, -vent_gap)), color=get_garapa_color())
show(assembly)

# ==========================================
# 8. REPORTING
# ==========================================
print("=" * 80)
print(f"DECK CONSTRUCTION REPORT | Balance Score: {best_score:.4f}")
print("=" * 80)
for b in sm.garapa_registry:
    print(f"{b['id']:12} | {b['orig']:7.1f}mm | {b['cuts'][0]['usage']}")
    for c in b['cuts'][1:]: print(f"{'':15} | {'':10} | {c['usage']}")

print("\n" + "-" * 80 + "\nGARAPA STOCK TALLY (REMAINING)\n" + "-" * 80)
total_lm = 0
for length in sorted(sm.garapa_stock.keys(), reverse=True):
    count = sm.garapa_stock[length]
    if count > 0:
        print(f"{count:2} x {length:4}mm planks")
        total_lm += (count * length) / 1000.0
print(f"Total Lineage Meters Remaining: {total_lm:.2f}m")
print(f"Total Fasteners Used: {len(screw_positions)}")