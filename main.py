import cadquery as cq
import random
import statistics
from collections import Counter
from cadquery.vis import show

# ==========================================
# 1. PHYSICAL DIMENSIONS
# ==========================================
deck_width = 3975.0
joist_len = 2255.0
joist_w = 45.0
joist_h = 90.0
board_w = 137.0
board_h = 19.0
gap = 6.4
min_board_len = 600.0

# ==========================================
# 2. LAYOUT RULES
# ==========================================
top_frame_join_joist = 5  # Joist to split the top frame on1GdGiimport cadquery as cq
import random
import statistics
from collections import Counter
from cadquery.vis import show

# ==========================================
# 1. PHYSICAL DIMENSIONS
# ==========================================
deck_width = 3975.0
joist_len = 2255.0
joist_w = 45.0
joist_h = 90.0
board_w = 137.0
board_h = 19.0
gap = 6.4
min_board_len = 600.0

# ==========================================
# 2. LAYOUT RULES
# ==========================================
top_frame_join_joist = 5  # Joist index for frame split
vertical_row_gap = 3
horizontal_joist_gap = 2

# ==========================================
# 3. CALCULATIONS & INITIALIZATION
# ==========================================
j1_center = joist_w / 2
j2_center = board_w - (joist_w / 2)
j11_center = (deck_width - board_w) + (joist_w / 2)
j12_center = deck_width - (joist_w / 2)
mid_spacing = (j11_center - j2_center) / 9

joist_centers = [j1_center, j2_center]
for i in range(1, 9):
    joist_centers.append(j2_center + (i * mid_spacing))
joist_centers.extend([j11_center, j12_center])

anchor_idx = top_frame_join_joist - 1
valid_j_indices = list(range(2, 10))  # Joists 3-10

def get_garapa_color():
    return cq.Color(random.uniform(0.72, 0.78), random.uniform(0.52, 0.58), random.uniform(0.22, 0.28))

# Calculate number of rows
temp_y = joist_len - board_w - gap
num_rows = 0
while temp_y > gap + 1.0:
    num_rows += 1
    temp_y -= (board_w + gap)

# ==========================================
# 4. SIMULATION & MATHEMATICAL SCORING
# ==========================================
def generate_candidate():
    joins = []
    lockout = {i: 0 for i in valid_j_indices}
    prev_idx = anchor_idx
    for r in range(num_rows):
        legal = [i for i in valid_j_indices if lockout[i] == 0 and abs(i - prev_idx) >= horizontal_joist_gap]
        if not legal: legal = [i for i in valid_j_indices if lockout[i] == 0]
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

print("Simulating 5,000 layouts to find mathematical balance...")
candidates = []
for _ in range(5000):
    c = generate_candidate()
    if c: candidates.append((score_layout(c), c))
candidates.sort(key=lambda x: x[0])
best_score, row_joins = candidates[0]

# ==========================================
# 5. WOOD STOCK MANAGEMENT & ALLOCATION
# ==========================================
class StockManager:
    def __init__(self):
        # Initial Stock: 10 each of 3600, 3300, 3000
        self.stock = {3600: 10, 3300: 10, 3000: 10}
        self.offcuts = []
        self.board_registry = []
        self.next_id = 1
        self.min_reuse = mid_spacing  # Offcut must be at least one span

    def allocate(self, length, usage_info):
        """
        usage_info expects a dict: {'row': str, 'side': str, 'j_start': int, 'j_end': int}
        """
        # Calculate spans covered
        num_spans = abs(usage_info['j_end'] - usage_info['j_start'])
        usage_str = f"{usage_info['row']} {usage_info['side']} (J{usage_info['j_start']}-J{usage_info['j_end']}, {num_spans} spans)"

        # 1. Try offcuts first
        self.offcuts.sort(key=lambda x: x['len'])
        for i, off in enumerate(self.offcuts):
            if off['len'] >= length:
                self.offcuts.pop(i)
                board = next(b for b in self.board_registry if b['id'] == off['bid'])
                board['cuts'].append({'len': length, 'usage': usage_str})
                rem = off['len'] - length
                if rem >= self.min_reuse:
                    self.offcuts.append({'len': rem, 'bid': board['id']})
                return board['id']

        # 2. Use new board
        available = sorted([l for l, c in self.stock.items() if c > 0 and l >= length])
        if not available:
            raise Exception(f"OUT OF STOCK: {usage_str} needs {length:.1f}mm")

        chosen_len = available[0]
        self.stock[chosen_len] -= 1
        bid = f"P{self.next_id:02}"
        self.next_id += 1

        board = {'id': bid, 'orig': chosen_len, 'cuts': [{'len': length, 'usage': usage_str}]}
        self.board_registry.append(board)

        rem = chosen_len - length
        if rem >= self.min_reuse:
            self.offcuts.append({'len': rem, 'bid': bid})
        return bid


sm = StockManager()
W, L, D = board_w, joist_len, deck_width
split_x = joist_centers[anchor_idx]

# --- 1. Frame Allocation ---
frame_data = [
    {'len': L, 'info': {'row': 'FRAME', 'side': 'Left', 'j_start': 1, 'j_end': 2},
     'pts': [(0, 0), (0, L), (W, L - W), (W, 0)]},
    {'len': L, 'info': {'row': 'FRAME', 'side': 'Right', 'j_start': 11, 'j_end': 12},
     'pts': [(D, 0), (D, L), (D - W, L - W), (D - W, 0)]},
    {'len': split_x - gap / 2, 'info': {'row': 'FRAME', 'side': 'Top-West', 'j_start': 1, 'j_end': 5},
     'pts': [(0, L), (split_x - gap / 2, L), (split_x - gap / 2, L - W), (W, L - W)]},
    {'len': D - (split_x + gap / 2), 'info': {'row': 'FRAME', 'side': 'Top-East', 'j_start': 5, 'j_end': 12},
     'pts': [(split_x + gap / 2, L), (D, L), (D - W, L - W), (split_x + gap / 2, L - W)]}
]
for p in frame_data: p['bid'] = sm.allocate(p['len'], p['info'])

# --- 2. Infill Allocation ---
infill_data = []
cy = L - W - gap
for r in range(num_rows):
    rw = W if (cy - gap) >= W else (cy - gap)
    j_join_idx = row_joins[r]
    tx = joist_centers[j_join_idx]

    # Left Piece: From Joist 2 to Joint Joist
    l_len = tx - (W + gap)
    l_bid = sm.allocate(l_len, {'row': f"Row {r + 1}", 'side': "Left", 'j_start': 2, 'j_end': j_join_idx + 1})
    infill_data.append(
        {'len': l_len, 'bid': l_bid, 'y': cy, 'w': rw, 'x_start': W + gap, 'x_len': l_len - gap / 2, 'row': r + 1,
         'side': 'L', 'j_join': j_join_idx + 1})

    # Right Piece: From Joint Joist to Joist 11
    r_len = (D - W - gap) - tx
    r_bid = sm.allocate(r_len, {'row': f"Row {r + 1}", 'side': "Right", 'j_start': j_join_idx + 1, 'j_end': 11})
    infill_data.append(
        {'len': r_len, 'bid': r_bid, 'y': cy, 'w': rw, 'x_start': tx + gap / 2, 'x_len': r_len - gap / 2, 'row': r + 1,
         'side': 'R'})

    cy -= (rw + gap)

# ==========================================
# 6. UPDATED REPORTING
# ==========================================
report = ["=" * 75, "DECK CONSTRUCTION: CUT & LAYOUT REPORT", "=" * 75]
report.append(f"Balance Score: {best_score:.4f} | Total Infill Rows: {num_rows}")
report.append("-" * 75)
report.append("INDIVIDUAL PLANK UTILIZATION:")

for b in sm.board_registry:
    report.append(f"Plank {b['id']} ({b['orig']}mm):")
    for c in b['cuts']:
        report.append(f"  > Cut {c['len']:8.2f}mm for: {c['usage']}")
    scrap = b['orig'] - sum(c['len'] for c in b['cuts'])
    report.append(f"  > Final Scrap: {scrap:8.2f}mm")

report.append("-" * 75)
report.append("CONSTRUCTION SEQUENCE (PLACEMENT):")
for p in frame_data:
    report.append(f"FRAME: {p['info']['side']:12} | {p['len']:8.2f}mm | Plank {p['bid']}")
for r in range(1, num_rows + 1):
    lp = next(p for p in infill_data if p['row'] == r and p['side'] == 'L')
    rp = next(p for p in infill_data if p['row'] == r and p['side'] == 'R')
    # BUG FIX: eval lp['bid'] and rp['bid'] instead of literal string
    report.append(
        f"ROW {r:02}: Join @ J{lp['j_join']:02} | Left: {lp['len']:7.2f}({lp['bid']}) | Right: {rp['len']:7.2f}({rp['bid']})")

report_output = "\n".join(report)
print(report_output)
with open("cut_and_layout", "w") as f:
    f.write(report_output)

# ==========================================
# 7. ASSEMBLY RENDERING
# ==========================================
assembly = cq.Assembly()

# Joists
for cp in joist_centers:
    assembly.add(cq.Workplane("XY").box(joist_w, joist_len, joist_h).translate((cp, L/2, -joist_h/2)),
                 color=cq.Color(0.2, 0.2, 0.2))

# Mitered Frame
for p in frame_data:
    assembly.add(cq.Workplane("XY").polyline(p['pts']).close().extrude(board_h), color=get_garapa_color())

# Infill
for p in infill_data:
    assembly.add(cq.Workplane("XY").box(p['x_len'], p['w'], board_h).translate(
        (p['x_start'] + p['x_len']/2, p['y'] - p['w']/2, board_h/2)), color=get_garapa_color())

show(assembly)
vertical_row_gap = 3
horizontal_joist_gap = 2

# ==========================================
# 3. CALCULATIONS & INITIALIZATION
# ==========================================
j1_center = joist_w / 2
j2_center = board_w - (joist_w / 2)
j11_center = (deck_width - board_w) + (joist_w / 2)
j12_center = deck_width - (joist_w / 2)
mid_spacing = (j11_center - j2_center) / 9

joist_centers = [j1_center, j2_center]
for i in range(1, 9):
    joist_centers.append(j2_center + (i * mid_spacing))
joist_centers.extend([j11_center, j12_center])

anchor_idx = top_frame_join_joist - 1
valid_j_indices = list(range(2, 10))  # Joists 3-10


def get_garapa_color():
    return cq.Color(random.uniform(0.72, 0.78), random.uniform(0.52, 0.58), random.uniform(0.22, 0.28))


# Calculate number of rows
temp_y = joist_len - board_w - gap
num_rows = 0
while temp_y > gap + 1.0:
    num_rows += 1
    temp_y -= (board_w + gap)


# ==========================================
# 4. SIMULATION & MATHEMATICAL SCORING
# ==========================================
def generate_candidate():
    joins = []
    lockout = {i: 0 for i in valid_j_indices}
    prev_idx = anchor_idx
    for r in range(num_rows):
        legal = [i for i in valid_j_indices if lockout[i] == 0 and abs(i - prev_idx) >= horizontal_joist_gap]
        if not legal: legal = [i for i in valid_j_indices if lockout[i] == 0]
        if not legal: return None
        chosen = random.choice(legal)
        joins.append(chosen)
        prev_idx = chosen
        for i in lockout:
            if lockout[i] > 0: lockout[i] -= 1
        lockout[chosen] = vertical_row_gap + 1
    return joins


def score_layout(joins):
    center_point = 5.5  # Center of indices 2-9
    left_offsets = [center_point - j for j in joins if j <= 5]
    right_offsets = [j - center_point for j in joins if j >= 6]

    if not left_offsets or not right_offsets: return 9999.0

    mean_imb = abs(statistics.mean(left_offsets) - statistics.mean(right_offsets))
    var_l = statistics.variance(left_offsets) if len(left_offsets) > 1 else 0
    var_r = statistics.variance(right_offsets) if len(right_offsets) > 1 else 0
    return mean_imb + var_l + var_r + abs(var_l - var_r)


print("Simulating 5,000 layouts to find mathematical balance...")
candidates = []
for _ in range(5000):
    c = generate_candidate()
    if c: candidates.append((score_layout(c), c))

candidates.sort(key=lambda x: x[0])
best_score, row_joins = candidates[0]
print(f"Best layout found with score {best_score:.4f}")

# ==========================================
# 5. ASSEMBLY RENDERING
# ==========================================
assembly = cq.Assembly()

# Joists
for cp in joist_centers:
    assembly.add(cq.Workplane("XY").box(joist_w, joist_len, joist_h).translate((cp, joist_len / 2, -joist_h / 2)),
                 color=cq.Color(0.2, 0.2, 0.2))

# --- MITERED FRAME RENDERING ---
W, L, D = board_w, joist_len, deck_width
split_x = joist_centers[anchor_idx]

# 1. Left Side Board: Square at house (y=0), Mitered at end (y=L)
# Outer edge is at X=0 (long), Inner edge at X=W (short)
left_side_pts = [(0, 0), (0, L), (W, L - W), (W, 0)]
assembly.add(cq.Workplane("XY").polyline(left_side_pts).close().extrude(board_h), color=get_garapa_color())

# 2. Right Side Board: Square at house (y=0), Mitered at end (y=L)
# Outer edge at X=D (long), Inner edge at X=D-W (short)
right_side_pts = [(D, 0), (D, L), (D - W, L - W), (D - W, 0)]
assembly.add(cq.Workplane("XY").polyline(right_side_pts).close().extrude(board_h), color=get_garapa_color())

# 3. Top-West Board: Mitered at deck edge (X=0), Square at split
# Outer edge at Y=L (long), Inner edge at Y=L-W (short)
top_w_pts = [(0, L), (split_x - gap / 2, L), (split_x - gap / 2, L - W), (W, L - W)]
assembly.add(cq.Workplane("XY").polyline(top_w_pts).close().extrude(board_h), color=get_garapa_color())

# 4. Top-East Board: Square at split, Mitered at deck edge (X=D)
# Outer edge at Y=L (long), Inner edge at Y=L-W (short)
top_e_pts = [(split_x + gap / 2, L), (D, L), (D - W, L - W), (split_x + gap / 2, L - W)]
assembly.add(cq.Workplane("XY").polyline(top_e_pts).close().extrude(board_h), color=get_garapa_color())

# --- INFILL RENDERING ---
curr_y = joist_len - board_w - gap
for r in range(num_rows):
    row_w = board_w if (curr_y - gap) >= board_w else (curr_y - gap)
    target_x = joist_centers[row_joins[r]]

    # Left board of the row
    l_start_x = board_w + gap
    l_len = target_x - l_start_x
    assembly.add(cq.Workplane("XY").box(l_len - gap / 2, row_w, board_h).translate(
        (l_start_x + (l_len - gap / 2) / 2, curr_y - row_w / 2, board_h / 2)), color=get_garapa_color())

    # Right board of the row
    r_end_x = deck_width - board_w - gap
    r_len = r_end_x - target_x
    assembly.add(cq.Workplane("XY").box(r_len - gap / 2, row_w, board_h).translate(
        (target_x + gap / 2 + (r_len - gap / 2) / 2, curr_y - row_w / 2, board_h / 2)), color=get_garapa_color())

    curr_y -= (row_w + gap)

show(assembly)