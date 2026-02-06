import cadquery as cq
import itertools

# Path to your exported file
step_file = "deck_layout.step"


def check_for_collisions(file_path):
    print(f"Loading {file_path}...")
    try:
        # Import the STEP file - this returns a Workplane object
        imported_workplane = cq.importers.importStep(file_path)
    except Exception as e:
        print(f"Error loading STEP: {e}")
        return

    # Extract all individual solids from the Workplane
    # .objects contains the list of shapes (solids, faces, etc.)
    all_solids = [obj for obj in imported_workplane.objects if isinstance(obj, cq.Solid)]

    print(f"Checking {len(all_solids)} solids for overlaps...")

    collisions = []

    # Check every unique pair
    for i, (sol_a, sol_b) in enumerate(itertools.combinations(all_solids, 2)):
        try:
            # Perform a boolean intersection
            intersect_shape = sol_a.intersect(sol_b)
            overlap_vol = intersect_shape.Volume()

            # Report overlaps larger than 0.1 cubic mm
            if overlap_vol > 0.1:
                # Since names are lost in STEP import, we use indices or
                # you can estimate which part it is by its volume
                collisions.append((i, overlap_vol))
                print(f"[!] OVERLAP DETECTED between Solid Index {i}")
                print(f"    Shared Volume: {overlap_vol:.2f} mm³\n")
        except Exception:
            continue

    print("-" * 50)
    if not collisions:
        print("PASS: No overlaps detected > 0.1mm³.")
    else:
        print(f"FAIL: Found {len(collisions)} overlapping pairs.")


if __name__ == "__main__":
    check_for_collisions(step_file)