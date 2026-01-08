Introduction
A Workflow to Convert a full Arc Drone video into a Photogrametry workflow, towards rendering a textured obj for cultural heritage and documentation.

This project is an independent reserach for documenting a stone labyrinth in india believed to be more than 1200 years old
<img width="2261" height="1272" alt="image" src="https://github.com/user-attachments/assets/c272e339-20a3-45ea-b9af-220bdd89fe84" /> - Labyrinth 1 in Salem, Tamil Nadu, India.

raw unprocessed scan is also hosted here - https://sketchfab.com/3d-models/ezhlu-suthu-kottai-labyrinth1-fd98e6ab4a6a447d8f8aaa80f26e390e
Processed and 3dprintable STL files can be downloaded here - [https://skfb.ly/pFrIY](https://sketchfab.com/3d-models/labyrinth-model-for-3dprinting-3298401c8cc6465da40a7c1e2170e6f6)- 

the google drive structure is as follows - https://drive.google.com/drive/folders/1OHUfLgzkVfzxqVNqoa2_PZS4i0-HLScH?usp=sharing

the videos to extract images from are hosted here - https://drive.google.com/drive/folders/1G-3tqRPTlefHTVRCwlt7l8SgC4OGmAsO?usp=sharing

The Archeological documentation was published in the 54th edition of Caedroia - https://labyrinthos.net/caerdroia54.html , with the help of 
Jeff Saward , Sachin patil and Dr Pandurang Sabale

Drone Photogrammetry Pipeline

This repository describes an open‐source pipeline (implemented in Google Colab) that converts a drone video into a textured 3D mesh. In summary, we extract video frames, run COLMAP for SfM (sparse and dense reconstruction), and use Open3D for meshing and coloring. The final output is a vertex-colored PLY mesh. The pipeline uses ffmpeg, colmap, and open3d to automate these steps.

Requirements

A Linux/Colab environment (GPU optional)

COLMAP (for SfM/dense reconstruction) – install via sudo apt-get install colmap.

FFmpeg (for frame extraction) – install via sudo apt-get install ffmpeg.

Open3D (Python library for meshing and I/O) – install via pip install open3d.

Xvfb (virtual X server for headless COLMAP) – install via sudo apt-get install xvfb.

Workflow

Extract frames from the drone video: Use FFmpeg to convert the video into individual image files. For example:

ffmpeg -i input_video.mp4 -vf fps=2 -qscale:v 2 images/frame_%04d.jpg


This command (shown in our notebook) extracts frames at 2 FPS and saves them as JPEGs.

Run COLMAP Structure-from-Motion: With the extracted frames, run COLMAP’s SfM to compute camera poses and a sparse point cloud. This can be done using xvfb-run in Colab to allow GPU SIFT: e.g. colmap automatic_reconstructor --workspace_path PROJECT --image_path images --quality high --dense 1 --use_gpu 1. (The notebook also shows running sequential matching and colmap mapper to refine the sparse model.)

Dense reconstruction: Use COLMAP’s dense pipeline to generate a fused point cloud. Specifically, run:

colmap image_undistorter to undistort images and prepare for stereo (max side ~2500 px).

colmap patch_match_stereo with geometric consistency to compute depth maps.

colmap stereo_fusion to fuse all depth maps into a dense colored point cloud (fused.ply).

In the notebook this is automated with commands like:

xvfb-run -a colmap patch_match_stereo ... 
xvfb-run -a colmap stereo_fusion --workspace_path dense --output_path dense/fused.ply


After this step, the dense point cloud (fused.ply) contains millions of XYZRGB points. The commands above are illustrated in the notebook.

Mesh reconstruction (Poisson): Convert the dense point cloud into a surface mesh. We apply Poisson surface reconstruction (via Open3D) to recover a smooth surface from the point cloud (fusing depth maps and normals)
colmap.github.io
. In practice, the notebook loads fused.ply into Open3D and runs:

mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=11, scale=1.1)
mesh.remove_unreferenced_vertices()
mesh.compute_vertex_normals()


This yields a watertight mesh (mesh_poisson_o3d.ply) representing the labyrinth surface. (COLMAP also offers poisson_mesher, but we used Open3D for flexibility.)

Color transfer: To produce a textured (colored) mesh, we transfer colors from the fused point cloud to the mesh vertices. The notebook builds a KD-tree on the point cloud and, for each mesh vertex, finds the nearest point’s color. In code:

pcd_tree = o3d.geometry.KDTreeFlann(pcd)
colors = []
for v in mesh.vertices:
    _, idx, _ = pcd_tree.search_knn_vector_3d(v, 1)
    colors.append(pcd.colors[idx[0]])
mesh.vertex_colors = o3d.utility.Vector3dVector(colors)


Finally, we save the colored mesh to PLY:

o3d.io.write_triangle_mesh("meshed-poisson-colored.ply", mesh, write_vertex_colors=True)


This writes a PLY file with RGB vertex colors (i.e. a “textured” point-colored mesh).

Results: The pipeline outputs a .ply file (e.g. meshed-poisson-colored.ply) that contains the final geometry with color. (In Colab output we see “Colored mesh saved at: …meshed-poisson-colored.ply”.) This file can be viewed in MeshLab or a 3D viewer, and can be further cleaned or prepared for printing in tools like Rhino or BambuStudio as needed.

Notes

Performance: Running COLMAP dense reconstruction on Google Drive (Colab) can be time-consuming (tens of minutes) due to large images and point clouds. A more user-friendly, faster alternative for smaller projects is Agisoft Metashape, which automates many steps with optimized C++ code.

Skip religious context: This documentation focuses only on the technical photogrammetry steps; all cultural or mythological discussion from the source material has been omitted for clarity.

References: The workflow above follows standard photogrammetry techniques
colmap.github.io
. In particular, COLMAP’s dense fusion and Poisson meshing produce a colored point cloud and mesh, and Open3D was used to finalize and save the textured PLY.

This project is licensed under the Creative Commons BY-NC-SA 4.0 License. This license allows others to distribute, remix, adapt, and build upon the material for non-commercial purposes only, provided that proper attribution is given to the creator. Any derivatives or adaptations must be released under the same license terms. For full details, please see the license description: https://creativecommons.org/licenses/by-nc-sa/4.0/ .


