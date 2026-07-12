# MCNP Input Card Generator (MCNP 输入卡生成器)

A **PyQt5** desktop application for visually creating, editing, and validating **MCNP** (Monte Carlo N-Particle) input files (`.INP`). Replaces manual text editing with a structured, form-based GUI.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

---

## Features

| Feature | Description |
|---------|-------------|
| **Form-based editing** | 8 organized tabs covering all MCNP input sections |
| **INP generation** | Auto-generates standard MCNP input decks with 80-column formatting |
| **INP import** | Parse existing `.INP` files and backfill all tab fields |
| **Project save/load** | Save/restore complete workspace as JSON |
| **Material library** | 50+ preset materials (compounds, elements, alloys, shielding, tissue, absorbers) |
| **Dual source mode** | Fixed multi-source with probability weighting, or distribution source (SDEF + SI/SP) |
| **Dual material input** | Manual ZAID table or chemical formula (via `pymcnp M_0.from_formula()`) |
| **3D preview** | PyVista-based geometry visualization |
| **Output analysis** | Parse MCNP output files, plot tallies (matplotlib), export CSV/Parquet |
| **xsdir integration** | Cross-section library ZAID validation and lookup |
| **Dark/Light theme** | Built-in QSS theme toggle |
| **MCNP auto-detect** | Automatically finds installed MCNP executable |

---

## Quick Start

### Prerequisites

- Python 3.10+
- MCNP (optional, for running generated input decks)

### Installation

```bash
# Clone or download
cd MCNP-Input-Card-Generator

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Build Standalone EXE

```bash
build.bat
```

The packaged executable will be output to `dist/MCNP输入卡生成器/`.

---

## User Interface

| Tab | Section | Description |
|-----|---------|-------------|
| Basic | Title, MODE, NPS, CTME | Deck identification and particle transport parameters |
| Materials | Material cards | ZAID/fraction entries with preset library |
| Geometry | Surfaces & Cells | Surface definitions, cell table with 3D preview |
| Source | SDEF | Fixed point sources or distribution source mode |
| Tallies | F1–F8 | Enable/disable tallies with parameters |
| Energy | E0, CUT cards | Energy mesh and time/energy cutoffs |
| Advanced | PHYS, Other | Physics cards, auxiliary cards, xsdir path |
| Output | Results | MCNP output parsing, plotting, export |

---

## Project Structure

```
├── main.py                    # Application entry point
├── requirements.txt           # Dependencies
├── build.bat                  # PyInstaller build script
├── app/
│   ├── main_window.py         # Main window orchestrator
│   ├── models.py              # Data models (DeckData, CellData, etc.)
│   ├── style.py               # QSS stylesheets
│   ├── project_io.py          # JSON project save/load
│   ├── inp_importer.py        # INP file importer
│   ├── material_presets.py    # Preset material library
│   ├── mcnp_detector.py       # MCNP executable auto-detection
│   ├── xsdir_db.py            # xsdir cross-section database
│   ├── xsdir_manager.py       # xsdir path management
│   ├── tabs/                  # 8 UI tab pages
│   ├── dialogs/               # Modal edit dialogs
│   ├── widgets/               # Reusable widgets (text mode toggle)
│   └── generator/             # INP generation & parsing engine
│       ├── inp_generator.py   # Main generator (~800 lines)
│       ├── validator.py       # Deck validation
│       └── parsers/           # INP file parser subpackage
```

---

## License

All Rights Reserved. This software is provided for **viewing purposes only**. No modification, distribution, or commercial use is permitted without explicit permission.

---

Built with [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) and [pymcnp](https://pypi.org/project/pymcnp/).
