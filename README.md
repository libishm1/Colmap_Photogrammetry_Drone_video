Drone Photogrammetry Pipeline
From Full Arc Drone Video to Textured 3D Mesh
Introduction

This repository documents an open-source workflow to convert a full-arc drone video into a photogrammetry pipeline, resulting in a textured 3D mesh suitable for cultural heritage documentation and fabrication.

The workflow was developed as part of an independent research project focused on documenting a large-scale stone labyrinth in Salem, Tamil Nadu, India, estimated to be over 1200 years old. The emphasis of this repository is strictly technical: acquisition, reconstruction, meshing, and export.

Example subject: 
<img width="2261" height="1272" alt="image" src="https://github.com/user-attachments/assets/c272e339-20a3-45ea-b9af-220bdd89fe84" /> - Stone labyrinth (Labyrinth 1), Salem, Tamil Nadu, India

Related Data & Outputs
Raw Scan (Unprocessed)

Sketchfab (raw reconstruction):
https://sketchfab.com/3d-models/ezhlu-suthu-kottai-labyrinth1-fd98e6ab4a6a447d8f8aaa80f26e390e

Processed & 3D-Printable Files

Cleaned STL models (Rhino + Bambu Studio):
https://skfb.ly/pFrIY-

Google Drive Structure

Full project directory (COLMAP workspace, outputs):
https://drive.google.com/drive/folders/1OHUfLgzkVfzxqVNqoa2_PZS4i0-HLScH

Source Drone Videos

Drone videos used for frame extraction:
https://drive.google.com/drive/folders/1G-3tqRPTlefHTVRCwlt7l8SgC4OGmAsO

Publication Context

The archaeological documentation resulting from this workflow was published in:

Caerdroia – Issue 54 (2025)
https://labyrinthos.net/caerdroia54.html

This repository focuses only on the digital documentation and reconstruction workflow.
Interpretive, mythological, or religious narratives are intentionally excluded.

Overview of the Pipeline

This repository describes a fully open-source photogrammetry pipeline, implemented entirely in Google Colab, that converts drone video into a vertex-colored (textured) PLY mesh.

Core tools used:

ffmpeg – frame extraction from video

COLMAP – sparse & dense photogrammetry

Open3D – meshing, color transfer, export

The final output is a textured PLY mesh, suitable for:

Visualization

Archival documentation

Further cleanup for fabrication

Requirements

This pipeline runs in a Linux / Google Colab environment.

System

Google Colab (GPU optional but recommended)

Dependencies
sudo apt-get install colmap
sudo apt-get install ffmpeg
sudo apt-get install xvfb
pip install open3d


COLMAP – Structure-from-Motion & dense reconstruction

FFmpeg – video → image extraction

Xvfb – headless execution for COLMAP in Colab

Open3D – mesh processing and file export

Workflow
1. Frame Extraction from Drone Video

Drone video is converted into individual image frames using FFmpeg.

ffmpeg -i input_video.mp4 -vf fps=2 -qscale:v 2 images/frame_%04d.jpg


Extracts frames at 2 FPS

Produces high-quality JPEG images

Lower FPS reduces redundancy and computation time

2. Sparse Reconstruction (Structure-from-Motion)

COLMAP computes camera poses and a sparse point cloud.

Example (automatic pipeline):

colmap automatic_reconstructor \
  --workspace_path PROJECT \
  --image_path images \
  --quality high \
  --dense 1 \
  --use_gpu 1


In the notebook, this is executed using xvfb-run to support headless GPU SIFT in Colab.

3. Dense Reconstruction

The dense pipeline consists of:

Image undistortion

Patch-match stereo

Stereo fusion

Key commands:

colmap image_undistorter
colmap patch_match_stereo
colmap stereo_fusion --output_path dense/fused.ply


Output:

fused.ply

Dense point cloud with XYZ + RGB

Often contains millions of points

4. Mesh Reconstruction (Poisson Surface)

The dense point cloud is converted into a watertight mesh using Poisson Surface Reconstruction in Open3D.

mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd, depth=11, scale=1.1
)
mesh.remove_unreferenced_vertices()
mesh.compute_vertex_normals()


Output:

mesh_poisson_o3d.ply

Smooth, continuous surface

Open3D was chosen instead of COLMAP’s Poisson mesher for greater control and extensibility.

5. Color Transfer (Textured Mesh)

To produce a textured mesh, vertex colors are transferred from the dense point cloud using nearest-neighbor lookup.

pcd_tree = o3d.geometry.KDTreeFlann(pcd)
colors = []

for v in mesh.vertices:
    _, idx, _ = pcd_tree.search_knn_vector_3d(v, 1)
    colors.append(pcd.colors[idx[0]])

mesh.vertex_colors = o3d.utility.Vector3dVector(colors)

6. Export Textured PLY
o3d.io.write_triangle_mesh(
    "meshed-poisson-colored.ply",
    mesh,
    write_vertex_colors=True
)


Final output:

meshed-poisson-colored.ply

Vertex-colored, textured mesh

Viewable in MeshLab, Blender, or Rhino

Post-Processing (Outside Colab)

While reconstruction is done in Colab, cleanup and fabrication prep were done using:

Rhino 8 – mesh cleanup, decimation, repairs

Bambu Studio – slicing and print preparation

Results

Fully open-source, reproducible workflow

Textured PLY mesh suitable for documentation

STL derivatives suitable for 3D printing

Applicable to large-scale outdoor heritage objects

Notes on Performance

COLMAP dense reconstruction is slow on Google Drive

Large datasets may take tens of minutes to hours

Disk I/O is a major bottleneck in Colab

Faster Alternative

For production or time-critical work:

Agisoft Metashape offers significantly faster processing

More user-friendly GUI

Commercial, closed-source

This repository prioritizes transparency and reproducibility over speed.

License

This project is licensed under the
Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).

You are free to:

Share and adapt the material

Use it for non-commercial purposes

Under the conditions that:

Proper attribution is given

Derivatives are shared under the same license

License details:
https://creativecommons.org/licenses/by-nc-sa/4.0/

