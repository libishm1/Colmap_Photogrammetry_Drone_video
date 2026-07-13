# Colab MCP debugging runbook for the GLOMAP notebook

## Purpose

Use Google's `colab-mcp` server to let a supported local coding agent execute and repair `Drone3D_GLOMAP_Colab_MCP_Debug.ipynb` inside the browser-based Colab runtime.

The dataset path is fixed to the existing workflow:

- Project / image set: `/content/drive/MyDrive/Colmap`
- Preferred image subfolder when present: `/content/drive/MyDrive/Colmap/images`
- Outputs: `/content/drive/MyDrive/Colmap/outputs_glomap`

The sparse pipeline must remain:

1. Pinned COLMAP 4.1.0 source build with CUDA.
2. Xvfb wrapper for COLMAP commands.
3. Shared `SIMPLE_RADIAL` camera for extracted video frames.
4. Sequential GPU matching.
5. `view_graph_calibrator`.
6. GLOMAP `global_mapper`.
7. Exhaustive retry only when GLOMAP registers too few images.
8. Incremental mapper only as the final automatic fallback.

Do not replace the source build with Ubuntu's `apt install colmap`, because the old Ubuntu package used by the original notebook was COLMAP 3.7 and does not contain the integrated global mapper.

## Local MCP setup

Install `uv`:

```bash
pip install uv
```

Add the contents of `mcp.json.example` to the MCP configuration of a supported local client such as Gemini CLI, Claude Code, or Windsurf.

Start the client locally, invoke `open_colab_browser_connection`, and allow it to open/connect to the Colab browser session.

## Agent prompt

Use the following prompt after the browser connection is active:

> Open `Drone3D_GLOMAP_Colab_MCP_Debug.ipynb` in Google Colab and select a GPU runtime. Execute the notebook in order. After every code cell, inspect the output and `/content/Drone3D_GLOMAP/debug_state.json`. When a cell fails, inspect the newest file in `/content/Drone3D_GLOMAP/logs` and the mirrored log in `/content/drive/MyDrive/Colmap/outputs_glomap/logs`. Patch only the failing cell, preserve the fixed Drive paths and the COLMAP 4.1.0 + CUDA + Xvfb + GLOMAP architecture, then rerun from the last successful stage. Do not silently accept fewer than 60 percent registered images. Confirm that `fused.ply`, the cleaned PLY mesh, PCD, OBJ, STL, and GLB are non-empty before reporting success.

## Debug checkpoints

The notebook writes these state keys:

- `dataset_discovery`
- `runtime_preflight`
- `colmap_build`
- `cli_option_validation`
- `feature_database_qa`
- `matching_qa`
- `sparse_reconstruction`
- `dense_reconstruction`
- `mesh_exports`
- `sync_outputs`

A stage is complete only when its state is `success`.

## Known failure signatures

### Drive credential propagation failure

Re-authorize Drive in the browser and rerun the mount/configuration cell. This is a Colab session authentication issue, not a COLMAP issue.

### `global_mapper` or `view_graph_calibrator` missing

The wrong COLMAP executable is running. Rerun the pinned source-build cell and verify the notebook uses the explicit executable under `/content/Drone3D_GLOMAP/build/colmap-4.1.0/src/colmap/exe/colmap`.

### Unknown `--gpu_index`

The old notebook used the wrong PatchMatch flag. The correct COLMAP 4.1 option is `--PatchMatchStereo.gpu_index 0`.

### Sparse registration below 60 percent

Let the notebook add exhaustive GPU matches and retry GLOMAP. If that still fails, inspect blur, duplicated frames, frame order, and overlap before relying on the incremental fallback.

### Dense reconstruction fails immediately

Confirm that the selected sparse model contains `cameras.bin`, `images.bin`, and `points3D.bin`, and that the CUDA-enabled build exposes `patch_match_stereo`.

### Colab disk fills during MVS

Reduce `DENSE_MAX_IMAGE_SIZE` from 2400 to 2000, restart the dense stage with `FORCE_RESTART_DENSE=True`, and keep the workspace on `/content` rather than Google Drive.
