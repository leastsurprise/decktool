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
joist_sister_width = 90.0 # where joists have a
joist_offcuts_available_for_sistering_count = 6 # six offcuts available for sistering
joist_offcuts_available_for_sistering_length = 1300  # each is 1300 long
joist_half_w = joist_w / 2
joist_h = 90.0
board_w = 140.0
board_h = 19.0
gap_between_rows = 6.4 # this allows the wood (garapa) to swell widthwise with moisture
gap_between_boards_in_same_row = 3  # this allows the wood (garapa) to swell lengthwise with moisture
screw_offset = 15 # screw points are 15mm from either end of a board
infill_joist_bays = 9 # count of spaces between inner joists (j2 to j11) which is number of infill_joists + 1
cladding_protrusion = 0 # TODO: TO BE MEASURED
gap_cladding_to_deck = 10 # TODO: TO BE CONFIRMED
side_picture_board_length = joist_len - cladding_protrusion - gap_cladding_to_deck # TODO: INSERT INTO CUT BOARD ALLOCATION

# ==========================================
# STILL TO DO - DO NOT DO YET - IGNORE
# Calculate total number of joists needed given spacing no greater than 450mm
# Change J12 and J11 variables to be called Jmax and jmax-1 or something else generic not based on known number of joists
# Calculate bays as infill joists +1
# ==========================================

# ==========================================
# TODO: IMPLEMENT FASCIA & DRIP-EDGE LOGIC
# ---------------------------------------
# WHY:
# The current model lacks the vertical perimeter cladding (fascia). To protect
# the H3.2 subframe from UV/moisture and provide a finished look, 140x19mm
# Garapa boards should be applied to the North, East, and West faces.
# The south face abuts the house and does not need a fascia.
#
# SOLUTION & CALCULATIONS:
# 1. OVERHANG: The picture-frame boards (Left, Right, and Top West/East) should
#    protrude 19mm past the joist face. The 19mm fascia is then tucked
#    directly UNDER this overhang to create a 'drip edge' that keeps water
#    off the fascia-to-joist interface.
# 2. DIMENSIONS:
#    - Side Fascias (East/West): Length of inner edge = joist_len (2255mm).
#    - Side Fascias (East/West): Length of outer edge = joist_len (2255mm) + board_h (19mm).
#    - Front Fascia (North): Length of inner edge = deck_width
#    - Front Fascia (North): Length of outer edge = deck_width + (2 * board_h).
#    - All fascia boards have a 45 degree bevel cut where they abut another fascia board.
#      This is why the outer edges are longer than the inner edges.
#      The bevel cut faces should allow two fascia boards to form a 90 degree angle when the
#      two bevel edges are butted together.
# 3. VENTILATION: Maintain a 12mm gap between the top of the fascia and the
#    underside of the deck boards.
# 4. QUANTITY: The fascia boards are to be supplied from the StockManager.
#    The north Fascia needs to joined as the stock manager does not have any boards of the
#    required length.  The side fascias may have max_number_of_side_fascia_joins.  The front
#    fascia may have max_number_of_front_fascia_joins. 50% of the proposed layouts must
#    require fascia cut points to be a multiple of the space between infill joists.  The
#    remaining 50% of the proposed layouts must allow fascia cut points to be any length,
#    which enables them to make use of odd sized decking board offcuts that are in the
#    StockManagers bins.
# ==========================================

# ==========================================
# TODO: IMPLEMENT JOINER BLOCK (SLOTTED SISTERING) LOGIC
# ------------------------------------------------------
# WHY:
# Standard 45mm joists are mathematically insufficient for joining two Garapa boards.
# A board-to-board join with a 3mm gap, 15mm board-end screw setback, and 15mm
# joist-edge clearance requires a minimum width of 63mm.
# To maintain structural integrity without doubling every joist, a 'modified
# sistering' approach is required: a 140mm long, 45mm deep slot is cut into the
# top of the joist at the join location, and a 90x45mm block is inserted to
# create a 90mm wide bearing surface.
#
# CODE RECOMMENDATIONS:
# 1. TRACKING: Modify the 'infill_data' loop to log the exact Y-coordinate and
#    Joist ID for every 'target_x' join location.
# 2. MAPPING: Create a 'Joist Prep Map' in the final Report. This should list
#    each Joist (J01-J12) and the specific Y-offsets where slots must be
#    pre-cut before the joists are laid onto the bearers.
# 3. VISUALIZATION: Update the CadQuery 'Assembly' to render these 140mm
#    sistering blocks in a contrasting color to aid in assembly planning.
# ==========================================

# ==========================================
# 2. LAYOUT RULES
# ==========================================
top_frame_join_joist = 7 #5  # Joist to split the top frame on
vertical_row_gap = 3
horizontal_joist_gap = 2

# ==========================================
# 3. CALCULATIONS & INITIALIZATION
# ==========================================
j1_center = joist_half_w
j12_center = deck_width - joist_half_w

j2_center = j1_center - joist_half_w - board_h + board_w + gap_between_rows + screw_offset
j11_center = j12_center + joist_half_w + board_h - board_w - gap_between_rows - screw_offset
infill_joist_centre_to_centre_gap = (j11_center - j2_center) / infill_joist_bays

joist_centers = [j1_center, j2_center]
for i in range(1, infill_joist_bays):
    joist_centers.append(j2_center + (i * infill_joist_centre_to_centre_gap))
joist_centers.extend([j11_center, j12_center])

anchor_idx = top_frame_join_joist - 1
list_of_infill_indices = list(range(2, 10))  # Joists 3-10


def get_garapa_color():
    return cq.Color(random.uniform(0.72, 0.78), random.uniform(0.52, 0.58), random.uniform(0.22, 0.28))


# Calculate number of rows

# the top board is a picture frame and overhangs the fascia board, we need to add board_h
# we subtract board_w because this represents the top picture frame board
# and of course we have a gap between picture frame and the first infill board.
# so temp_y is initialized to the start point from which we need to fill boards
# back towards the house
temp_y = joist_len - board_w - gap_between_rows + board_h
num_rows = 0
while temp_y > gap_between_rows + 1.0:
    num_rows += 1
    temp_y -= (board_w + gap_between_rows)


# ==========================================
# 4. SIMULATION & MATHEMATICAL SCORING
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


print("Simulating 5,000 layouts to find mathematical balance...")
candidates = []
for _ in range(5000):
    c = generate_candidate()
    if c: candidates.append((score_layout(c), c))

candidates.sort(key=lambda x: x[0])
best_score, row_joins = candidates[0]
print(f"Best layout found with score {best_score:.4f}")


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
        self.min_reuse = infill_joist_centre_to_centre_gap  # Offcut must be at least one span length

    def allocate(self, length, usage_info):
        """
        usage_info: {'row': str, 'side': str, 'j_start': int, 'j_end': int}
        """
        num_spans = abs(usage_info['j_end'] - usage_info['j_start'])
        usage_str = f"{usage_info['row']} {usage_info['side']} (J{usage_info['j_start']}-J{usage_info['j_end']}, {num_spans} spans)"

        # 1. Try offcuts first (Smallest fit)
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

        # 2. Buy new board (Smallest available)
        available = sorted([l for l, c in self.stock.items() if c > 0 and l >= length])
        if not available:
            raise Exception(f"OUT OF WOOD STOCK for: {usage_str} ({length:.1f}mm)")

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
    {'len': L, 'info': {'row': 'FRAME', 'side': 'Left Side', 'j_start': 1, 'j_end': 2},
     'pts': [(0, 0), (0, L), (W, L - W), (W, 0)]},
    {'len': L, 'info': {'row': 'FRAME', 'side': 'Right Side', 'j_start': 11, 'j_end': 12},
     'pts': [(D, 0), (D, L), (D - W, L - W), (D - W, 0)]},
    {'len': split_x - gap_between_rows / 2, 'info': {'row': 'FRAME', 'side': 'Top-West', 'j_start': 1, 'j_end': 5},
     'pts': [(0, L), (split_x - gap_between_rows / 2, L), (split_x - gap_between_rows / 2, L - W), (W, L - W)]},
    {'len': D - (split_x + gap_between_rows / 2), 'info': {'row': 'FRAME', 'side': 'Top-East', 'j_start': 5, 'j_end': 12},
     'pts': [(split_x + gap_between_rows / 2, L), (D, L), (D - W, L - W), (split_x + gap_between_rows / 2, L - W)]}
]
for p in frame_data: p['bid'] = sm.allocate(p['len'], p['info'])

# --- 2. Infill Allocation ---
infill_data = []
cy = L - W - gap_between_rows
for r in range(num_rows):
    rw = W if (cy - gap_between_rows) >= W else (cy - gap_between_rows)
    j_join_idx = row_joins[r]
    tx = joist_centers[j_join_idx]

    # Left Piece: From Joist 2 to Joint Joist
    l_len = tx - (W + gap_between_rows)
    l_bid = sm.allocate(l_len, {'row': f"Row {r + 1}", 'side': "Left", 'j_start': 2, 'j_end': j_join_idx + 1})
    infill_data.append(
        {'len': l_len, 'bid': l_bid, 'y': cy, 'w': rw, 'x_start': W + gap_between_rows, 'x_len': l_len - gap_between_rows / 2, 'row': r + 1,
         'side': 'L', 'j_join': j_join_idx + 1})

    # Right Piece: From Joint Joist to Joist 11
    r_len = (D - W - gap_between_rows) - tx
    r_bid = sm.allocate(r_len, {'row': f"Row {r + 1}", 'side': "Right", 'j_start': j_join_idx + 1, 'j_end': 11})
    infill_data.append(
        {'len': r_len, 'bid': r_bid, 'y': cy, 'w': rw, 'x_start': tx + gap_between_rows / 2, 'x_len': r_len - gap_between_rows / 2, 'row': r + 1,
         'side': 'R'})

    cy -= (rw + gap_between_rows)

# ==========================================
# 6. REPORTING
# ==========================================
report = ["=" * 75, "DECK CONSTRUCTION: CUT & LAYOUT REPORT", "=" * 75]
report.append(f"Balance Score: {best_score:.4f} | Total Infill Rows: {num_rows}")
report.append("-" * 75)
report.append("INDIVIDUAL PLANK UTILIZATION (CUT LIST):")

for b in sm.board_registry:
    report.append(f"Plank {b['id']} ({b['orig']}mm):")
    total_cut = 0
    for c in b['cuts']:
        report.append(f"  > Cut {c['len']:8.2f}mm for: {c['usage']}")
        total_cut += c['len']
    scrap = b['orig'] - total_cut
    report.append(f"  > Final Scrap/Waste: {scrap:8.2f}mm")

report.append("-" * 75)
report.append("CONSTRUCTION SEQUENCE (PLACEMENT):")
for p in frame_data:
    report.append(f"FRAME: {p['info']['side']:12} | {p['len']:8.2f}mm | Plank {p['bid']}")

for r in range(1, num_rows + 1):
    lp = next(p for p in infill_data if p['row'] == r and p['side'] == 'L')
    rp = next(p for p in infill_data if p['row'] == r and p['side'] == 'R')
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
    assembly.add(cq.Workplane("XY").box(joist_w, joist_len, joist_h).translate((cp, joist_len / 2, -joist_h / 2)),
                 color=cq.Color(0.2, 0.2, 0.2))

# Mitered Frame
for p in frame_data:
    assembly.add(cq.Workplane("XY").polyline(p['pts']).close().extrude(board_h), color=get_garapa_color())

# Infill
for p in infill_data:
    assembly.add(cq.Workplane("XY").box(p['x_len'], p['w'], board_h).translate(
        (p['x_start'] + p['x_len'] / 2, p['y'] - p['w'] / 2, board_h / 2)), color=get_garapa_color())

show(assembly)