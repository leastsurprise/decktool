import cadquery as cq
import random
import statistics
import math

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
vent_gap = 12.0
fascia_h = 140.0
min_board_len = 400.0 # was 600.0
report_filename = "deck_layout_report.txt"
step_path = "deck_layout.step"
# The gap between joist 1 and joist 2 inner faces is 50mm as measured in FreeCAD.

# Sister Block Specs
sister_block_len = 140.0
sister_stock_count = 10
sister_stock_len = 1300.0

# Screw Logic Variables
screw_head_dia = 8.9
screw_butt_offset = 30.0  # 30mm from board end towards center
screw_edge_offset = 20.0  # Used for vertical positioning

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

# Master screw lines
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
# 4. UPDATED LAYOUT OPTIMIZATION
# ==========================================
def generate_candidate():
    joins = []
    lockout = {i: 0 for i in list_of_infill_indices}
    prev_idx = anchor_idx

    # Pre-calculate boundary constraints
    in_x_start, in_x_end = pf_inner_west + gap_boards, pf_inner_east - gap_boards

    for r in range(num_rows):
        # 1. Filter by existing lockout and gap rules
        legal = [i for i in list_of_infill_indices if lockout[i] == 0 and abs(i - prev_idx) >= horizontal_joist_gap]

        # 2. ENFORCE MIN_BOARD_LENGTH RULE
        # Only allow joists that leave enough room on both the left and right sides
        strictly_legal = []
        for i in legal:
            tx = joist_centers[i]
            l_len = (tx - 1.5) - in_x_start
            r_len = in_x_end - (tx + 1.5)

            if l_len >= min_board_len and r_len >= min_board_len:
                strictly_legal.append(i)

        if not strictly_legal:
            return None  # Discard this candidate entirely

        chosen = random.choice(strictly_legal)
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
        self.garapa_registry.append(
            {'id': bid, 'orig': chosen, 'cuts': [{'len': length, 'usage': f"{board_type}: {usage}"}]})
        rem = chosen - length
        if rem >= 100: self.offcuts.append({'len': rem, 'bid': bid})
        return bid

    def allocate_sister_block(self, joist_num, y_coord, custom_len=sister_block_len):
        for board in self.sister_stock:
            if board['rem'] >= custom_len:
                board['rem'] -= custom_len
                board['cuts'].append({'len': custom_len, 'usage': f"J{joist_num} @ Y={y_coord:.1f}"})
                self.sister_usage.append((joist_num, y_coord, custom_len))
                return board['id']
        raise Exception("OUT OF SISTER JOIST STOCK.")

sm = DeckStockManager()


def get_miter_details(pts, board_type, usage_name):
    """Calculates edges based on orientation: 140mm ref for PF/Infill, 19mm ref for Fascia."""
    xs = [p[0] for p in pts];
    ys = [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    l_max = max(w, h)

    # Differentiate dimensions based on orientation
    if "FASCIA" in board_type:
        # Fascia: standing on edge (140mm plumb, 19mm level)
        ref_side = board_h  # 19mm (The side you measure across/mark)
        depth_side = fascia_h  # 140mm (The vertical side the saw cuts through)
        face_w = board_h  # 19mm (Width the blade travels at 45°)
    else:
        # Picture Frame / Infill: laid flat (19mm plumb, 140mm level)
        ref_side = board_w  # 140mm (The side you measure across/mark)
        depth_side = board_h  # 19mm (The vertical thickness the saw cuts through)
        face_w = board_w  # 140mm (Width the blade travels at 45°)

    # Identify parallel edge lengths (Tip vs Heel) from the 2D layout points
    if w > h:
        y_vals = sorted(list(set(ys)))
        edge_lens = [max([p[0] for p in pts if p[1] == y]) - min([p[0] for p in pts if p[1] == y]) for y in y_vals]
    else:
        x_vals = sorted(list(set(xs)))
        edge_lens = [max([p[1] for p in pts if p[0] == x]) - min([p[1] for p in pts if p[0] == x]) for x in x_vals]

    l_min = min(edge_lens)
    is_miter = abs(l_max - l_min) > 0.1

    if is_miter:
        # j is the hypotenuse of the saw path across the reference face width
        j_len = face_w * math.sqrt(2)
        msg = (f"MITER: Mark {ref_side}mm side. Edges: {l_max:.1f}mm & {l_min:.1f}mm. "
               f"Face: {depth_side}mm x {j_len:.1f}mm (45°).")
    else:
        msg = f"Straight: {l_max:.1f}mm (Face: {depth_side}mm x {ref_side:.1f}mm)."

    return l_max, msg

## ==========================================
## 6. COMPONENT CALCULATIONS
## ==========================================
#W, L, D, OH = board_w, joist_len, deck_width, board_h
#
## PICTURE FRAME & FASCIA (Standard logic)
#picture_frame_data = [
#    {'pts': [(-OH, 0), (W - OH, 0), (W - OH, L - W + OH), (-OH, L + OH)],
#     'bid': sm.allocate_garapa(L + OH, "West Side", "PICTURE FRAME")},
#    {'pts': [(D + OH, 0), (D - W + OH, 0), (D - W + OH, L - W + OH), (D + OH, L + OH)],
#     'bid': sm.allocate_garapa(L + OH, "East Side", "PICTURE FRAME")},
#    {'pts': [(-OH, L + OH), (split_x, L + OH), (split_x, L - W + OH), (W - OH, L - W + OH)],
#     'bid': sm.allocate_garapa(split_x + OH, "North-West", "PICTURE FRAME")},
#    {'pts': [(split_x, L + OH), (D + OH, L + OH), (D - W + OH, L - W + OH), (split_x, L - W + OH)],
#     'bid': sm.allocate_garapa(D - split_x + OH, "North-East", "PICTURE FRAME")}
#]
#
#fascia_data = [
#    {'pts': [(-OH, 0), (0, 0), (0, L), (-OH, L + OH)], 'bid': sm.allocate_garapa(L + OH, "West Face", "FASCIA")},
#    {'pts': [(D, 0), (D + OH, 0), (D + OH, L), (D, L + OH)], 'bid': sm.allocate_garapa(L + OH, "East Face", "FASCIA")},
#    {'pts': [(-OH, L + OH), (split_x, L + OH), (split_x, L), (0, L)],
#     'bid': sm.allocate_garapa(split_x + OH, "North Left", "FASCIA")},
#    {'pts': [(split_x, L + OH), (D + OH, L + OH), (D, L), (split_x, L)],
#     'bid': sm.allocate_garapa(D - split_x + OH, "North Right", "FASCIA")}
#]
#
#infill_data, screw_positions, cy = [], [], cy_start
#in_x_start, in_x_end = pf_inner_west + gap_boards, pf_inner_east - gap_boards
#
#for r in range(num_rows):
#    j_idx = row_joins[r]
#    tx = joist_centers[j_idx]
#
#    # CENTER THE 3MM GAP OVER THE MAIN JOIST CENTER
#    # Left board end: 1.5mm west of joist center
#    # Right board start: 1.5mm east of joist center
#    l_end = tx - 1.5
#    r_start = tx + 1.5
#
#    rw = W if (cy - gap_rows) >= W else (cy - gap_rows)
#
#    infill_data.append({'len': l_end - in_x_start, 'x': in_x_start, 'y': cy, 'w': rw,
#                        'bid': sm.allocate_garapa(l_end - in_x_start, f"R{r + 1} L", "INFILL")})
#    infill_data.append({'len': in_x_end - r_start, 'x': r_start, 'y': cy, 'w': rw,
#                        'bid': sm.allocate_garapa(in_x_end - r_start, f"R{r + 1} R", "INFILL")})
#
#    row_y_center = cy - (rw / 2)
#    y_offs = [rw / 2 - screw_edge_offset, -(rw / 2 - screw_edge_offset)]
#
#    for jc in joist_centers:
#        # If this is the join joist, place screws at calculated positions
#        if abs(jc - tx) < 0.1:
#            # Left board: screw 30mm from end (west) towards center
#            left_screw_x = l_end - screw_butt_offset
#            # Right board: screw 30mm from start (east) towards center
#            right_screw_x = r_start + screw_butt_offset
#            for dy in y_offs:
#                screw_positions.append((left_screw_x, row_y_center + dy))
#                screw_positions.append((left_screw_x, row_y_center - dy))
#                screw_positions.append((right_screw_x, row_y_center + dy))
#                screw_positions.append((right_screw_x, row_y_center - dy))
#        elif in_x_start <= jc <= l_end or r_start <= jc <= in_x_end:
#            for dy in y_offs:
#                screw_positions.append((jc, row_y_center + dy))
#
#    # Allocate TWO sister blocks (one for west, one for east) for the join joist
#    sm.allocate_sister_block(j_idx + 1, cy - rw / 2, custom_len=rw)
#    sm.allocate_sister_block(j_idx + 1, cy - rw / 2, custom_len=rw)
#    cy -= (rw + gap_rows)

# ==========================================
# 6. COMPONENT CALCULATIONS (Miter Aware)
# ==========================================
W, L, D, OH = board_w, joist_len, deck_width, board_h

# 1. Define Point Sets (Geometry only)
raw_frame_data = [
    {'pts': [(-OH, 0), (W - OH, 0), (W - OH, L - W + OH), (-OH, L + OH)], 'usage': "West Side",
     'type': "PICTURE FRAME"},
    {'pts': [(D + OH, 0), (D - W + OH, 0), (D - W + OH, L - W + OH), (D + OH, L + OH)], 'usage': "East Side",
     'type': "PICTURE FRAME"},
    {'pts': [(-OH, L + OH), (split_x, L + OH), (split_x, L - W + OH), (W - OH, L - W + OH)], 'usage': "North-West",
     'type': "PICTURE FRAME"},
    {'pts': [(split_x, L + OH), (D + OH, L + OH), (D - W + OH, L - W + OH), (split_x, L - W + OH)],
     'usage': "North-East", 'type': "PICTURE FRAME"}
]

raw_fascia_data = [
    {'pts': [(-OH, 0), (0, 0), (0, L), (-OH, L + OH)], 'usage': "West Face", 'type': "FASCIA"},
    {'pts': [(D, 0), (D + OH, 0), (D + OH, L), (D, L + OH)], 'usage': "East Face", 'type': "FASCIA"},
    {'pts': [(-OH, L + OH), (split_x, L + OH), (split_x, L), (0, L)], 'usage': "North Left", 'type': "FASCIA"},
    {'pts': [(split_x, L + OH), (D + OH, L + OH), (D, L), (split_x, L)], 'usage': "North Right", 'type': "FASCIA"}
]

# 2. Process and Allocate based on Longest Edge (l_max)
picture_frame_data, fascia_data = [], []
for raw in raw_frame_data + raw_fascia_data:
    # FIXED: Added raw['usage'] as the 3rd argument
    l_max, miter_msg = get_miter_details(raw['pts'], raw['type'], raw['usage'])
    bid = sm.allocate_garapa(l_max, raw['usage'], raw['type'])
    entry = {**raw, 'bid': bid, 'l_max': l_max, 'miter_msg': miter_msg}
    (picture_frame_data if raw['type'] == "PICTURE FRAME" else fascia_data).append(entry)

# 3. Process Infill Boards
infill_data, screw_positions, cy = [], [], cy_start
in_x_start, in_x_end = pf_inner_west + gap_boards, pf_inner_east - gap_boards

for r in range(num_rows):
    j_idx, tx = row_joins[r], joist_centers[row_joins[r]]
    l_end, r_start = tx - 1.5, tx + 1.5
    rw = W if (cy - gap_rows) >= W else (cy - gap_rows)

    for side, (start, end) in [("L", (in_x_start, l_end)), ("R", (r_start, in_x_end))]:
        length = end - start
        usage_str = f"R{r + 1} {side}"
        # FIXED: Added usage_str as the 3rd argument
        l_max, msg = get_miter_details([(0, 0), (length, 0), (length, rw), (0, rw)], "INFILL", usage_str)
        bid = sm.allocate_garapa(l_max, usage_str, "INFILL")
        infill_data.append({'pts': [(start, cy), (end, cy), (end, cy-rw), (start, cy-rw)],
                            'len': length, 'x': start, 'y': cy, 'w': rw, 'bid': bid,
                            'miter_msg': msg, 'l_max': l_max})
    # (Screw and sister block allocation remains same as original script)
    row_y_center = cy - (rw / 2)
    y_offs = [rw / 2 - screw_edge_offset, -(rw / 2 - screw_edge_offset)]
    for jc in joist_centers:
        if abs(jc - tx) < 0.1:
            for sx in [l_end - screw_butt_offset, r_start + screw_butt_offset]:
                for dy in y_offs: screw_positions.append((sx, row_y_center + dy))
        elif in_x_start <= jc <= l_end or r_start <= jc <= in_x_end:
            for dy in y_offs: screw_positions.append((jc, row_y_center + dy))

    sm.allocate_sister_block(j_idx + 1, cy - rw / 2, custom_len=rw)
    sm.allocate_sister_block(j_idx + 1, cy - rw / 2, custom_len=rw)
    cy -= (rw + gap_rows)

# ==========================================
# 7. ASSEMBLY RENDERING (Unique Names Fixed)
# ==========================================
main_asm = cq.Assembly(name="Complete_Deck")

# Sub-assemblies (Folders)
joist_asm = cq.Assembly(name="Joists")
sister_asm = cq.Assembly(name="Sister_Joists")
pf_asm = cq.Assembly(name="Picture_Frame")
infill_asm = cq.Assembly(name="Infill_Boards")
fascia_asm = cq.Assembly(name="Fascia_Boards")
screw_asm = cq.Assembly(name="Fasteners")

# Render Joists
for i, cp in enumerate(joist_centers):
    j_obj = cq.Workplane("XY").box(joist_w, L, joist_h).translate((cp, L / 2, -joist_h / 2))
    joist_asm.add(j_obj, name=f"Joist_{i+1}", color=cq.Color(0.2, 0.2, 0.2))

# Render Sisters
for i, (j_num, y, block_l) in enumerate(sm.sister_usage):
    cp = joist_centers[j_num - 1]
    w_sis = cq.Workplane("XY").box(joist_w, block_l, joist_h).translate((cp - joist_w, y, -joist_h / 2))
    # Added i to make name unique
    sister_asm.add(w_sis, name=f"Sister_J{j_num}_West_{i}", color=cq.Color("orange"))
    e_sis = cq.Workplane("XY").box(joist_w, block_l, joist_h).translate((cp + joist_w, y, -joist_h / 2))
    # Added i to make name unique
    sister_asm.add(e_sis, name=f"Sister_J{j_num}_East_{i}", color=cq.Color("orange"))

# Render Picture Frame
for i, pf in enumerate(picture_frame_data):
    pf_obj = cq.Workplane("XY").polyline(pf['pts']).close().extrude(board_h)
    pf_asm.add(pf_obj, name=f"PF_{pf['bid']}_{i}", color=get_garapa_color())

# Render Infill Boards (CRASH FIXED HERE)
for i, p in enumerate(infill_data):
    board_obj = cq.Workplane("XY").box(p['len'], p['w'], board_h).translate(
        (p['x'] + p['len'] / 2, p['y'] - p['w'] / 2, board_h / 2))
    # Combined Plank ID with loop index 'i' for uniqueness
    infill_asm.add(board_obj, name=f"Board_{p['bid']}_{i}", color=get_garapa_color())

# Render Fascia
for i, f in enumerate(fascia_data):
    fascia_obj = cq.Workplane("XY").polyline(f['pts']).close().extrude(-fascia_h).translate((0, 0, -vent_gap))
    fascia_asm.add(fascia_obj, name=f"Fascia_{f['bid']}_{i}", color=get_garapa_color())

# Render Screws
for i, (sx, sy) in enumerate(screw_positions):
    screw_obj = cq.Workplane("XY").cylinder(height=1.0, radius=screw_head_dia / 2).translate((sx, sy, board_h))
    screw_asm.add(screw_obj, name=f"Screw_{i}", color=cq.Color(0.75, 0.75, 0.75))

# Build Final Assembly
main_asm.add(joist_asm)
main_asm.add(sister_asm)
main_asm.add(pf_asm)
main_asm.add(infill_asm)
main_asm.add(fascia_asm)
main_asm.add(screw_asm)

main_asm.save(step_path, "STEP", linear_deflection=0.1)

## ==========================================
## 8. REPORTING (Complete implementation)
## ==========================================
#print(f"REPORT SAVED TO: {report_filename}")
#
## Calculate total screws: 4 screws per join (2 sister blocks * 2 screws each)
#total_screws = 4 * len(row_joins)
#print(f"Total screws required: {total_screws} (4 screws per join)")
#
## Complete reporting code
#report = ["=" * 75, "DECK CONSTRUCTION: CUT & LAYOUT REPORT", "=" * 75]
#report.append(f"Balance Score: {best_score:.4f} | Total Infill Rows: {num_rows}")
#report.append("-" * 75)
#report.append("INDIVIDUAL PLANK UTILIZATION (CUT LIST):")
#
#for b in sm.garapa_registry:
#    report.append(f"Plank {b['id']} ({b['orig']}mm):")
#    total_cut = 0
#    for c in b['cuts']:
#        report.append(f"  > Cut {c['len']:8.2f}mm for: {c['usage']}")
#        total_cut += c['len']
#    scrap = b['orig'] - total_cut
#    report.append(f"  > Final Scrap/Waste: {scrap:8.2f}mm")
#
#report.append("-" * 75)
#report.append("CONSTRUCTION SEQUENCE (PLACEMENT):")
#
## Calculate frame lengths for reporting
#def calculate_length(pts):
#    # Calculate the length of a rectangle based on the points
#    x1, y1 = pts[0]
#    x2, y2 = pts[1]
#    return abs(x2 - x1)
#
#for p in picture_frame_data + fascia_data:
#    length = calculate_length(p['pts'])
#    report.append(f"FRAME: {p['bid']:12} | {length:8.2f}mm | Plank {p['bid']}")
#
#for r in range(1, num_rows + 1):
#    # Find the left and right boards for this row
#    left_board = None
#    right_board = None
#    for p in infill_data:
#        # Calculate expected y position for this row
#        expected_y = cy_start - (r * (board_w + gap_rows)) + (board_w / 2)
#        if abs(p['y'] - expected_y) < 0.1:
#            if p['x'] < split_x:
#                left_board = p
#            else:
#                right_board = p
#    if left_board and right_board:
#        report.append(
#            f"ROW {r:02}: Join @ J{row_joins[r-1]:02} | Left: {left_board['len']:7.2f}({left_board['bid']}) | Right: {right_board['len']:7.2f}({right_board['bid']})")
#
#report_output = "\n".join(report)

# ==========================================
# 8. CONSTRUCTION SEQUENCE (PLACEMENT)
# ==========================================
report = []
report.append("=" * 115)
report.append("DECK CONSTRUCTION: ORIENTATION & PLACEMENT REPORT")
report.append("=" * 115)

def get_joist_range(pts):
    """Identifies which joists a board starts and ends on based on X coordinates."""
    xs = [p[0] for p in pts]
    min_x, max_x = min(xs), max(xs)
    overlapping_joists = [i + 1 for i, jx in enumerate(joist_centers) if (min_x - 5.0) <= jx <= (max_x + 5.0)]
    if not overlapping_joists: return "N/A"
    return f"J{min(overlapping_joists)} to J{max(overlapping_joists)}"


# --- PHASE 1: FRAME & FASCIA ---
report.append("\nSTEP 1: EXTERIOR FRAME & FASCIA")
report.append("PF = 140mm Level (Plank Flat) | Fascia = 19mm Level (Plank on Edge)")
report.append("-" * 115)
report.append(f"{'LOCATION':<20} | {'TYPE':<10} | {'STOCK':<8} | {'JOIST RANGE':<12} | {'CUTTING INSTRUCTIONS'}")
report.append("-" * 115)

for p in picture_frame_data + fascia_data:
    joist_info = get_joist_range(p['pts'])
    report.append(f"{p['usage']:<20} | {p['type']:<10} | {p['bid']:<8} | {joist_info:<12} | {p['miter_msg']}")

# --- PHASE 2: INFILL FIELD ---
report.append("\n" + "-" * 115)
report.append("STEP 2: INFILL BOARD PLACEMENT (SOUTH TO NORTH)")
report.append("-" * 115)

row_y_coords = [cy_start - i * (board_w + gap_rows) for i in range(num_rows)]

for idx, target_y in enumerate(row_y_coords):
    row_num = idx + 1
    join_idx = row_joins[idx]
    row_boards = [p for p in infill_data if abs(p['y'] - target_y) < 1.0]
    if not row_boards: continue

    report.append(f"ROW {row_num:02} | Primary Join over Joist J{join_idx + 1:02} | Y: {target_y:.2f}")

    row_boards.sort(key=lambda p: p['x'])
    for p in row_boards:
        side = "WEST" if p['x'] < split_x else "EAST"
        joist_info = get_joist_range(p['pts'])
        report.append(f"  [{side:<4}] {p['bid']:<8} | Over: {joist_info:<12} | {p['miter_msg']}")
    report.append("")

report.append("=" * 115)
report_output = "\n".join(report)
print(report_output)
with open(report_filename, "a") as f:
    f.write(report_output)


# ==========================================
# 9. POST-REPORTING AUDIT
# ==========================================
audit = ["", "=" * 75, "MATERIAL AUDIT & FEASIBILITY CHECK", "=" * 75]

# --- 1. INITIAL INVENTORY STATE ---
max_garapa_len = max(sm.garapa_stock.keys())
total_garapa_available = sum(l * c for l, c in {3600: 10, 3300: 10, 3000: 10}.items())
total_sister_available = sister_stock_count * sister_stock_len

audit.append(f"INITIAL INVENTORY:")
audit.append(f"  - Max Garapa Length: {max_garapa_len}mm")
audit.append(f"  - Total Garapa Stock: 30 planks ({total_garapa_available/1000:.1f}m total)")
audit.append(f"  - Sister Stock: {sister_stock_count} x {sister_stock_len}mm ({total_sister_available/1000:.1f}m total)")
audit.append("-" * 75)

# --- 2. USAGE VALIDATION ---
garapa_used_count = len(sm.garapa_registry)
total_sister_req = sum(item[2] for item in sm.sister_usage)

audit.append(f"QUANTITY CONSUMPTION:")
audit.append(f"  - Garapa Planks Used: {garapa_used_count} of 30")
if garapa_used_count > 30:
    audit.append("  [!!] WARNING: GARAPA EXCEEDS INVENTORY COUNT")

audit.append(f"  - Sister Material: {total_sister_req:.1f}mm used of {total_sister_available}mm")
if total_sister_req > total_sister_available:
    audit.append("  [!!] WARNING: SISTER MATERIAL EXCEEDS STOCK")

# --- 3. DIMENSIONAL BOUNDS CHECK ---
audit.append("-" * 75)
audit.append("PHYSICAL DIMENSION AUDIT (MAX LENGTH CHECK):")
violations = 0

# Check Infill & Picture Frame Dimensions
all_components = []
for pf in picture_frame_data:
    # Estimate length from points
    x_coords = [p[0] for p in pf['pts']]
    y_coords = [p[1] for p in pf['pts']]
    length = max(max(x_coords) - min(x_coords), max(y_coords) - min(y_coords))
    all_components.append((f"PF {pf['bid']}", length))

for infill in infill_data:
    all_components.append((f"Infill {infill['bid']}", infill['len']))

for fascia in fascia_data:
    x_coords = [p[0] for p in fascia['pts']]
    y_coords = [p[1] for p in fascia['pts']]
    length = max(max(x_coords) - min(x_coords), max(y_coords) - min(y_coords))
    all_components.append((f"Fascia {fascia['bid']}", length))

for name, length in all_components:
    if length > max_garapa_len:
        audit.append(f"  [!!] VIOLATION: {name} is {length:.1f}mm (Max stock is {max_garapa_len}mm)")
        violations += 1

if violations == 0:
    audit.append("  [OK] All components fit within the 3600mm maximum board length.")
else:
    audit.append(f"  [!!] TOTAL VIOLATIONS: {violations}")

# --- 4. JOIST INTEGRITY ---
# Standard joists are joist_len (2255mm).
if joist_len > 6000: # Assuming 6m is absolute max joist length available
    audit.append(f"  [!!] WARNING: Joists are {joist_len}mm. Check transport/availability.")

# --- 5. BOARD UTILIZATION BREAKDOWN ---
audit.append("-" * 75)
audit.append("GARAPA UTILIZATION BY STOCK LENGTH:")

usage_by_len = {3600: {'used': 0, 'whole': 0, 'cut': 0},
                3300: {'used': 0, 'whole': 0, 'cut': 0},
                3000: {'used': 0, 'whole': 0, 'cut': 0}}

all_cut_lengths = []

for b in sm.garapa_registry:
    orig = b['orig']
    usage_by_len[orig]['used'] += 1

    # Calculate total cut from this board
    total_cut = sum(c['len'] for c in b['cuts'])

    # Store individual cut lengths for min/max tracking
    for c in b['cuts']:
        all_cut_lengths.append(c['len'])

    # A board is "whole" if waste is negligible (e.g., < 10mm for blade kerf/squaring)
    if (orig - total_cut) < 10.0:
        usage_by_len[orig]['whole'] += 1
    else:
        usage_by_len[orig]['cut'] += 1

for length in sorted(usage_by_len.keys(), reverse=True):
    stats = usage_by_len[length]
    audit.append(f"  - {length}mm Stock: {stats['used']} used (Whole: {stats['whole']}, Cut: {stats['cut']})")

# --- 6. EXTREMES (LONGEST & SHORTEST CUTS) ---
if all_cut_lengths:
    longest = max(all_cut_lengths)
    shortest = min(all_cut_lengths)

    # Count occurrences
    long_count = sum(1 for l in all_cut_lengths if abs(l - longest) < 0.1)
    short_count = sum(1 for l in all_cut_lengths if abs(l - shortest) < 0.1)

    audit.append("-" * 75)
    audit.append("CUT PIECE EXTREMES:")
    audit.append(f"  - Longest Cut:  {longest:8.2f}mm (Quantity: {long_count})")
    audit.append(f"  - Shortest Cut: {shortest:8.2f}mm (Quantity: {short_count})")

    if shortest < min_board_len:
        audit.append(f"  [!!] WARNING: Shortest cut ({shortest:.1f}mm) is below min_board_len ({min_board_len}mm)")

# Final output
audit_output = "\n".join(audit)
print(audit_output)

with open(report_filename, "a") as f:
    f.write(audit_output)