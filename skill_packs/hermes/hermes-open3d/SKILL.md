---
name: hermes-open3d
description: Bridge Open3D point-cloud and mesh ops into Hermes.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [3d, point-cloud, mesh, open3d, vision]
    category: data-processing
    related_skills: [requesting-code-review]
    config: {}
---

# Open3D Skill

Point-cloud and mesh operations via
[Open3D](https://github.com/isl-org/Open3D) (C++/Python 3D library).
Be honest: this is a **bridge to the `pip install open3d` package**, not a
C++ port — every op runs `import open3d` in a subprocess, and without the
package the tools return `available: false`.

## When to Use

- Downsampling a dense point-cloud (`voxel_downsample`).
- Estimating normals before meshing or registration (`estimate_normals`).
- Cleaning scans with statistical outlier removal (`outlier_remove`).
- Probing whether the workspace has a usable `open3d` install (`info`).
- Producing `.ply` / `.pcd` / `.obj` artifacts for deterministic-brain
  `vision_analysis`.

Do not use for real-time SLAM, GPU reconstruction, or C++-only Open3D
features — this bridge covers pip-package point-cloud file ops only.

## Prerequisites

- Python 3.9+ with `pip install open3d` in the Hermes environment.
- Input files in `.ply` / `.pcd` / `.obj` format (meshes are sampled to
  5000 points when no point-cloud is found).
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-open3d` or run `install.ps1`.
- Without the package, both tools return `available: false` with an
  install hint — install it instead of expecting local fallbacks.

## How to Run

Via tools (preferred in-session):

- `open3d_process` with `operation` + `input` (+ `output`, `voxel_size`).
- `open3d_info` with no args to check availability + version.

Via CLI (operator terminal):

```bash
hermes open3d info
hermes open3d process voxel_downsample ./scan.ply --output ./scan.small.ply --voxel-size 0.02
hermes open3d process estimate_normals ./scan.ply
```

Via slash command: `/open3d info`, `/open3d process <op> <input>`
(tool-guided for full options).

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `open3d_process(operation, input, output?, voxel_size?)` | pip-`open3d` op writing `.ply`/`.pcd`/`.obj` |
| Tool | `open3d_info()` | `import open3d` probe + `__version__` |
| CLI | `hermes open3d process <op> <in> --output <p>` | Same as `open3d_process` from argv |
| Files | `<output>.ply` | Consumed by deterministic-brain `vision_analysis` |

## Procedure

1. **Check availability.** Run `open3d_info` (or `hermes open3d info`) to
   confirm the pip package imports and note its version.
2. **Pick the op.** `info` (inspect), `voxel_downsample` (thin),
   `estimate_normals` (normals), `outlier_remove` (clean).
3. **Process.** Call `open3d_process` with `operation` + `input`; set
   `output` explicitly or accept the default next to the input.
4. **Confirm the artifact.** Check the returned `output` path exists and
   note the `stats.points` count.
5. **Hand off.** Point deterministic-brain `vision_analysis` at the
   artifact path — never re-derive geometry from prose.
6. **Tune deliberately.** Adjust `voxel_size` (default 0.02) in small steps;
   over-aggressive downsampling destroys registration targets.

## Pitfalls

- **No package means no processing.** Without `pip install open3d` the
  process tool returns `success: false` + `available: false` — no silent
  numpy fallback is attempted.
- **Empty inputs fail honestly.** Files with zero points/vertices return
  `success: false` rather than an invented cloud.
- **Large clouds take time.** Ops run with a 180s subprocess timeout —
  tile or pre-downsample huge scans first.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **Meshes are sampled, not meshed.** Mesh inputs are uniformly sampled to
  5000 points — Poisson reconstruction is out of scope for this bridge.
- **Outputs default beside inputs.** Pass `output` explicitly when the
  workspace layout matters to downstream consumers.

## Verification

- `hermes open3d info` reports `available: true` with a version string.
- The `output` artifact exists on disk (`.ply` / `.pcd` / `.obj`).
- `stats.points` in the result is a positive integer.
- The artifact loads in deterministic-brain `vision_analysis`.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
