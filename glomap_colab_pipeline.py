#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/content/drive/MyDrive/Colmap")
OUTPUT_DIR = PROJECT_DIR / "outputs_glomap"
ROOT = Path("/content/Drone3D_GLOMAP")
IMAGES = ROOT / "images"
WORK = ROOT / "work"
LOGS = ROOT / "logs"
SRC = ROOT / "src" / "colmap-4.1.0"
BUILD = ROOT / "build" / "colmap-4.1.0"
COLMAP = BUILD / "src/colmap/exe/colmap"
DB = WORK / "database.db"
GLOBAL_DB = WORK / "database_global.db"
SPARSE_G = WORK / "sparse_glomap"
SPARSE_I = WORK / "sparse_incremental"
DENSE = WORK / "dense"
STATE = ROOT / "debug_state.json"

COLMAP_TAG = "4.1.0"
MIN_REGISTERED_FRACTION = 0.60
SIFT_MAX_IMAGE_SIZE = 3200
SIFT_MAX_FEATURES = 12000
SEQUENTIAL_OVERLAP = 10
DENSE_MAX_IMAGE_SIZE = 2400
BUILD_JOBS = 2
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
EXCLUDED_DIRS = {"outputs_glomap", "outputs", "dense", "sparse", "logs", ".cache", "stereo"}

for p in (PROJECT_DIR, OUTPUT_DIR, ROOT, IMAGES, WORK, LOGS, SRC.parent, BUILD.parent):
    p.mkdir(parents=True, exist_ok=True)

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_state(step: str, status: str, **details) -> None:
    data = {"created_at": now(), "steps": {}}
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text())
        except Exception:
            pass
    data["updated_at"] = now()
    data.setdefault("steps", {})[step] = {"status": status, "time": now(), **details}
    STATE.write_text(json.dumps(data, indent=2))
    shutil.copy2(STATE, OUTPUT_DIR / STATE.name)

def run(step: str, cmd: list[str | Path | int | float], check: bool = True,
        env: dict[str, str] | None = None) -> int:
    cmd = [str(x) for x in cmd]
    log = LOGS / f"{step}.log"
    print("$", " ".join(cmd), flush=True)
    write_state(step, "running", command=cmd, log=str(log))
    merged = os.environ.copy()
    if env:
        merged.update(env)
    with log.open("w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, env=merged)
        assert p.stdout is not None
        for line in p.stdout:
            print(line, end="")
            f.write(line)
        rc = p.wait()
    (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(log, OUTPUT_DIR / "logs" / log.name)
    write_state(step, "success" if rc == 0 else "failed",
                return_code=rc, command=cmd, log=str(log))
    if check and rc:
        raise RuntimeError(f"{step} failed; inspect {log}")
    return rc

def capture(cmd: list[str | Path]) -> str:
    return subprocess.run([str(x) for x in cmd], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True).stdout.strip()

def ccmd(*args) -> list[str]:
    if not COLMAP.exists():
        raise FileNotFoundError(f"Missing COLMAP executable: {COLMAP}")
    return ["xvfb-run", "-a", "--server-args=-screen 0 1024x768x24",
            str(COLMAP), *map(str, args)]

def discover_images() -> list[Path]:
    preferred = PROJECT_DIR / "images"
    source = preferred if preferred.exists() and any(
        p.suffix.lower() in IMAGE_EXTS for p in preferred.rglob("*") if p.is_file()
    ) else PROJECT_DIR
    files = sorted(
        p for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        and not any(part.lower() in EXCLUDED_DIRS
                    for part in p.relative_to(source).parts[:-1])
    )
    if len(files) < 3:
        raise FileNotFoundError(f"Found only {len(files)} input images under {source}")
    if IMAGES.exists():
        shutil.rmtree(IMAGES)
    IMAGES.mkdir(parents=True)
    for src in files:
        dst = IMAGES / src.relative_to(source)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(src)
    write_state("dataset_discovery", "success", source=str(source), image_count=len(files))
    return files

def cuda_arch() -> str:
    out = capture(["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"])
    m = re.search(r"(\d+)\.(\d+)", out)
    if m:
        return m.group(1) + m.group(2)
    name = capture(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]).upper()
    for token, arch in {"T4":"75","V100":"70","P100":"60","A100":"80",
                        "A10":"86","L4":"89","L40":"89","H100":"90"}.items():
        if token in name:
            return arch
    raise RuntimeError(f"Cannot infer CUDA architecture from {name!r}")

def build_colmap() -> None:
    help_text = capture([COLMAP, "help"]) if COLMAP.exists() else ""
    if all(x in help_text for x in ("global_mapper", "view_graph_calibrator",
                                    "patch_match_stereo", "poisson_mesher")):
        return
    pkgs = [
        "git","cmake","ninja-build","build-essential","ccache","xvfb","xauth",
        "libboost-program-options-dev","libboost-graph-dev","libboost-system-dev",
        "libeigen3-dev","libopenimageio-dev","openimageio-tools","libmetis-dev",
        "libgoogle-glog-dev","libgtest-dev","libgmock-dev","libsqlite3-dev",
        "libglew-dev","libgl1-mesa-dev","libglu1-mesa-dev","qtbase5-dev",
        "libqt5opengl5-dev","libqt5svg5-dev","libcgal-dev","libceres-dev",
        "libsuitesparse-dev","libcurl4-openssl-dev","libssl-dev","libunwind-dev",
        "libopenblas-openmp-dev"
    ]
    run("apt_update", ["apt-get","update","-qq"])
    run("apt_dependencies", ["apt-get","install","-y","--no-install-recommends",*pkgs])
    Path("/usr/include/opencv4").mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        run("clone_colmap", ["git","clone","--recursive","--depth","1",
                             "--branch",COLMAP_TAG,
                             "https://github.com/colmap/colmap.git",SRC])
    env = {"CCACHE_DIR": str(PROJECT_DIR / ".cache" / "ccache"),
           "CMAKE_BUILD_PARALLEL_LEVEL": str(BUILD_JOBS)}
    Path(env["CCACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    run("configure_colmap", [
        "cmake","-S",SRC,"-B",BUILD,"-GNinja","-DCMAKE_BUILD_TYPE=Release",
        "-DGUI_ENABLED=OFF","-DTESTS_ENABLED=OFF","-DONNX_ENABLED=OFF",
        "-DCUDA_ENABLED=ON","-DMVS_ENABLED=ON","-DOPENGL_ENABLED=ON",
        "-DCGAL_ENABLED=ON","-DBLA_VENDOR=OpenBLAS",
        f"-DCMAKE_CUDA_ARCHITECTURES={cuda_arch()}"], env=env)
    run("build_colmap", ["cmake","--build",BUILD,"--target","colmap",
                         "--parallel",BUILD_JOBS], env=env)
    help_text = capture([COLMAP, "help"])
    if "global_mapper" not in help_text:
        raise RuntimeError("Built COLMAP does not expose global_mapper")
    write_state("colmap_build", "success", binary=str(COLMAP), version=COLMAP_TAG)

def db_count(table: str) -> int:
    if not DB.exists():
        return 0
    try:
        with sqlite3.connect(DB) as con:
            return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0

def model_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    out = []
    if (root / "cameras.bin").exists() and (root / "images.bin").exists():
        out.append(root)
    out.extend(p for p in root.iterdir() if p.is_dir()
               and (p / "cameras.bin").exists() and (p / "images.bin").exists())
    return sorted(set(out))

def registered_count(model: Path, label: str) -> int:
    report = capture([COLMAP,"model_analyzer","--path",model])
    (LOGS / f"model_analyzer_{label}.log").write_text(report + "\n")
    m = re.search(r"Registered images:\s*(\d+)", report)
    return int(m.group(1)) if m else 0

def prepare_global(label: str) -> None:
    shutil.copy2(DB, GLOBAL_DB)
    if run(f"view_graph_calibrator_{label}",
           ccmd("view_graph_calibrator","--database_path",GLOBAL_DB),
           check=False):
        shutil.copy2(DB, GLOBAL_DB)

def glomap_attempt(label: str) -> tuple[Path | None, int]:
    if SPARSE_G.exists():
        shutil.rmtree(SPARSE_G)
    SPARSE_G.mkdir(parents=True)
    rc = run(f"global_mapper_{label}",
             ccmd("global_mapper","--database_path",GLOBAL_DB,
                  "--image_path",IMAGES,"--output_path",SPARSE_G), check=False)
    models = model_dirs(SPARSE_G)
    if rc or not models:
        return None, 0
    return models[0], registered_count(models[0], label)

def sparse(images: list[Path]) -> tuple[Path, str, int]:
    if db_count("keypoints") < len(images):
        run("feature_extraction", ccmd(
            "feature_extractor","--database_path",DB,"--image_path",IMAGES,
            "--ImageReader.camera_model","SIMPLE_RADIAL",
            "--ImageReader.single_camera",1,
            "--ImageReader.default_focal_length_factor",1.2,
            "--FeatureExtraction.use_gpu",1,"--FeatureExtraction.gpu_index",0,
            "--FeatureExtraction.max_image_size",SIFT_MAX_IMAGE_SIZE,
            "--SiftExtraction.max_num_features",SIFT_MAX_FEATURES))
    if db_count("two_view_geometries") == 0:
        run("sequential_matching", ccmd(
            "sequential_matcher","--database_path",DB,
            "--SequentialMatching.overlap",SEQUENTIAL_OVERLAP,
            "--SequentialMatching.quadratic_overlap",1,
            "--SequentialMatching.loop_detection",0,
            "--FeatureMatching.use_gpu",1,"--FeatureMatching.gpu_index",0,
            "--FeatureMatching.guided_matching",1,
            "--TwoViewGeometry.min_num_inliers",20,
            "--TwoViewGeometry.max_error",4.0))
    required = max(3, int(len(images) * MIN_REGISTERED_FRACTION))
    prepare_global("sequential")
    model, reg = glomap_attempt("sequential")
    if reg < required:
        run("exhaustive_matching_retry", ccmd(
            "exhaustive_matcher","--database_path",DB,
            "--FeatureMatching.use_gpu",1,"--FeatureMatching.gpu_index",0,
            "--FeatureMatching.guided_matching",1,
            "--ExhaustiveMatching.block_size",50,
            "--TwoViewGeometry.min_num_inliers",20,
            "--TwoViewGeometry.max_error",4.0))
        prepare_global("exhaustive")
        model, reg = glomap_attempt("exhaustive")
    backend = "GLOMAP"
    if reg < required:
        if SPARSE_I.exists():
            shutil.rmtree(SPARSE_I)
        SPARSE_I.mkdir(parents=True)
        run("incremental_mapper_fallback", ccmd(
            "mapper","--database_path",DB,"--image_path",IMAGES,
            "--output_path",SPARSE_I))
        models = model_dirs(SPARSE_I)
        if not models:
            raise RuntimeError("No sparse model was produced")
        model = models[0]
        reg = registered_count(model, "incremental")
        backend = "COLMAP_INCREMENTAL_FALLBACK"
    if model is None or reg < 3:
        raise RuntimeError("Sparse reconstruction has fewer than three images")
    write_state("sparse_reconstruction","success",backend=backend,
                selected_model=str(model),registered_images=reg,
                total_images=len(images))
    return model, backend, reg

def dense(model: Path) -> list[Path]:
    fused = DENSE / "fused.ply"
    if not fused.exists():
        if DENSE.exists():
            shutil.rmtree(DENSE)
        DENSE.mkdir(parents=True)
        run("image_undistorter", ccmd(
            "image_undistorter","--image_path",IMAGES,"--input_path",model,
            "--output_path",DENSE,"--output_type","COLMAP",
            "--max_image_size",DENSE_MAX_IMAGE_SIZE))
        run("patch_match_stereo", ccmd(
            "patch_match_stereo","--workspace_path",DENSE,
            "--workspace_format","COLMAP","--PatchMatchStereo.gpu_index",0,
            "--PatchMatchStereo.max_image_size",DENSE_MAX_IMAGE_SIZE,
            "--PatchMatchStereo.geom_consistency",1,
            "--PatchMatchStereo.num_samples",15,
            "--PatchMatchStereo.num_iterations",5,
            "--PatchMatchStereo.filter",1))
        run("stereo_fusion", ccmd(
            "stereo_fusion","--workspace_path",DENSE,
            "--workspace_format","COLMAP","--input_type","geometric",
            "--output_path",fused,"--StereoFusion.min_num_pixels",4,
            "--StereoFusion.max_reproj_error",2.0))
    if not fused.exists() or fused.stat().st_size < 1024:
        raise RuntimeError("Invalid fused.ply")
    poisson = DENSE / "meshed-poisson.ply"
    if not poisson.exists():
        run("poisson_mesher", ccmd(
            "poisson_mesher","--input_path",fused,"--output_path",poisson,
            "--PoissonMeshing.depth",10,"--PoissonMeshing.trim",10))
    run("install_open3d", [sys.executable,"-m","pip","install","-q",
                           "open3d>=0.19.0","trimesh>=4.0"])
    import open3d as o3d
    import trimesh
    pcd = o3d.io.read_point_cloud(str(fused))
    pcd_path = DENSE / "fused.pcd"
    o3d.io.write_point_cloud(str(pcd_path), pcd, compressed=True)
    mesh = o3d.io.read_triangle_mesh(str(poisson))
    mesh.remove_duplicated_vertices()
    mesh.remove_duplicated_triangles()
    mesh.remove_degenerate_triangles()
    mesh.remove_non_manifold_edges()
    mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    clean = DENSE / "meshed-poisson-clean.ply"
    obj = DENSE / "meshed-poisson-clean.obj"
    stl = DENSE / "meshed-poisson-clean.stl"
    glb = DENSE / "meshed-poisson-clean.glb"
    o3d.io.write_triangle_mesh(str(clean), mesh)
    o3d.io.write_triangle_mesh(str(obj), mesh)
    o3d.io.write_triangle_mesh(str(stl), mesh)
    trimesh.load(str(clean), force="mesh", process=False).export(str(glb))
    exports = [fused, pcd_path, poisson, clean, obj, stl, glb]
    if any(not p.exists() or p.stat().st_size == 0 for p in exports):
        raise RuntimeError("One or more exports are missing")
    write_state("mesh_exports","success",
                exports={p.name:p.stat().st_size for p in exports})
    return exports

def sync(model: Path, backend: str, reg: int, total: int, exports: list[Path]) -> None:
    final = OUTPUT_DIR / "final"
    final.mkdir(parents=True, exist_ok=True)
    for p in exports:
        shutil.copy2(p, final / p.name)
    sparse_out = OUTPUT_DIR / "sparse_selected"
    if sparse_out.exists():
        shutil.rmtree(sparse_out)
    shutil.copytree(model, sparse_out)
    archive = shutil.make_archive(str(OUTPUT_DIR / "Drone3D_GLOMAP_outputs"),
                                  "zip", root_dir=OUTPUT_DIR, base_dir="final")
    summary = {"backend":backend,"images_total":total,"images_registered":reg,
               "selected_model":str(model),"final_dir":str(final),
               "archive":archive,
               "exports":{p.name:p.stat().st_size for p in exports}}
    (OUTPUT_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2))
    write_state("sync_outputs","success",**summary)
    print(json.dumps(summary, indent=2))

def main() -> None:
    if not Path("/content/drive/MyDrive").exists():
        raise RuntimeError("Mount Google Drive in the notebook before running this script")
    if "NVIDIA-SMI has failed" in capture(["nvidia-smi"]) or not shutil.which("nvcc"):
        raise RuntimeError("Use a Colab GPU runtime with nvcc available")
    images = discover_images()
    build_colmap()
    model, backend, reg = sparse(images)
    exports = dense(model)
    sync(model, backend, reg, len(images), exports)

if __name__ == "__main__":
    main()
