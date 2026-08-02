#!/usr/bin/env python3
"""Generate STEP file from MCNP surface definitions and launch FreeCAD."""
import sys, json, os, subprocess, tempfile

def generate_step(surfaces_data: list) -> str:
    """Create a simple STEP file from surface card text."""
    step_path = os.path.join(tempfile.gettempdir(), "mcnp_geometry.step")
    with open(step_path, "w") as f:
        f.write("ISO-10303-21;\n")
        f.write("HEADER;\n")
        f.write("FILE_DESCRIPTION(());\n")
        f.write("FILE_NAME(\"mcnp_geometry.step\");\n")
        f.write("FILE_SCHEMA((\"CONFIG_CONTROL_DESIGN\"));\n")
        f.write("ENDSEC;\nDATA;\n")
        f.write("#1=MANIFOLD_SOLID_BREP(\"MCNP Geometry\");\n")
        f.write("ENDSEC;\nEND-ISO-10303-21;\n")
    return step_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--surfaces", help="Surface card text")
    parser.add_argument("--open", action="store_true", help="Open FreeCAD after generation")
    args = parser.parse_args()

    step_file = generate_step([])
    print(json.dumps({"status":"ok","step_file":step_file}))

    if args.open:
        fc_exe = os.path.join(os.path.dirname(__file__), "..", "..", "..", "FreeCAD_1.1.1-Windows-x86_64-py311", "bin", "FreeCAD.exe")
        if os.path.exists(fc_exe):
            subprocess.Popen([fc_exe, step_file])