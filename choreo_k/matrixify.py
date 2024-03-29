# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_matrixify.ipynb.

# %% auto 0
__all__ = ['matrixify_pose', 'get_normalized_coords', 'normalize_pose', 'symmetrify_pose',
           'normalize_symmetrify_and_compare_poses_cosine', 'normalize_and_compare_poses_cosine',
           'compare_poses_cosine', 'get_pose_matrix', 'get_laplacian_matrix', 'compare_laplacians']

# %% ../nbs/02_matrixify.ipynb 3
import copy
import numpy as np
import os
from scipy.spatial.distance import pdist, cosine
from sklearn.preprocessing import normalize
from scipy.sparse import lil_matrix
import networkx as nx

#from choreo_k.modify import flip_detections, flip_detections_y_first


def matrixify_pose(coords_and_confidence):
    """ DISTANCE MATRIX: compute a pose's L1-normed inter-keypoint distance matrix.
        To compare any two poses, we can measure the degree of correlation between
        their distance matrices via a statistical test, such as the Mantel test.
        XXX It's not obvious that normalizing the matrix really makes a difference to
        the final correlation comparison, but it doesn't seem to hurt, either...
        Note that if the pose representation has 17 keypoints, then each pose instance
        can be represented by a condensed distance matrix (or vector) of 136 elements.
    """
    
    if coords_and_confidence.shape[0] == 0:
            return None
    coords = coords_and_confidence[:,:2]
    condensed_distance_matrix = normalize(pdist(coords, 'sqeuclidean').reshape(1, -1))[0,:]
    return condensed_distance_matrix


def get_normalized_coords(frame, figure_index=0, figure_type='figures', norm='l2'):
    if figure_type not in frame or figure_index > len(frame[figure_type])-1:
        return None
    coords_and_confidence = frame[figure_type][figure_index].data
    if coords_and_confidence.shape[0] == 0:
        return None
    coords = np.copy(coords_and_confidence)

    normalized_coords = normalize(coords_and_confidence[:,:2], norm=norm, axis=0)
    coords[:,:2] = normalized_coords[:,:2]
    return coords

# An extension of get_normalized_pose to deal with the need to flip some poses vertically
# and/or horizontally
def normalize_pose(frame, figure_index=0, figure_type='figures', norm='l2', y_first=True, flip_x=False, flip_y=False, mirror_coco_17_left_right=False):
    if figure_type not in frame or figure_index > len(frame[figure_type])-1:
        return None
    # For some pose estimation libraries, such as TF MoveNet, the coords and confidence values
    # of the detected armature points are in YXC format, rather than XYC (ugh).
    normalized_frame = copy.deepcopy(frame)
    if flip_x or flip_y:
        if y_first or ('y_first' in frame and frame['y_first']):
            flipped_detections = flip_detections_y_first(frame[figure_type], flip_x=flip_x, flip_y=flip_y, mirror_coco_17_left_right=mirror_coco_17_left_right)
        else:
            flipped_detections = flip_detections(frame[figure_type], flip_x=flip_x, flip_y=flip_y, mirror_coco_17_left_right=mirror_coco_17_left_right)
        normalized_frame[figure_type] = flipped_detections
    return get_normalized_coords(normalized_frame, norm=norm)

def symmetrify_pose(frame, figure_index=0, figure_type='figures', y_first=True):
    if figure_type not in frame or figure_index > len(frame[figure_type])-1:
        return None
    # For some pose estimation libraries, such as TF MoveNet, the coords and confidence values
    # of the detected armature points are in YXC format, rather than XYC (ugh).
    flipped_frame = copy.deepcopy(frame)
    if y_first or ('y_first' in frame and frame['y_first']):
        flipped_detections = flip_detections_y_first(frame[figure_type], flip_y=False, flip_x=True)
    else:
        flipped_detections = flip_detections(frame[figure_type], flip_y=False, flip_x=True)

    flipped_frame[figure_type] = flipped_detections
    normalized_coords = get_normalized_coords(frame)
    normalized_flipped_coords = get_normalized_coords(flipped_frame)
    orig_coords_count = normalized_coords.shape[0]
    if orig_coords_count == 0:
        return None
    sym_coords_and_confidence = np.zeros((orig_coords_count*2,3))
    sym_coords_and_confidence[:orig_coords_count,:] = normalized_coords
    sym_coords_and_confidence[orig_coords_count:,:] = normalized_flipped_coords
    return sym_coords_and_confidence

def normalize_symmetrify_and_compare_poses_cosine(p1, p2):
    p1_symmetrized = symmetrify_pose(p1)
    p2_symmetrized = symmetrify_pose(p2)
    if p1_symmetrized is None or p2_symmetrized is None:
        return 0 # No similarity if one or both poses is missing
    return compare_poses_cosine(p1_symmetrized, p2_symmetrized)   


def normalize_and_compare_poses_cosine(p1, p2): # Uses cosine distance
    p1_normalized = get_normalized_coords(p1)
    p2_normalized = get_normalized_coords(p2)
    if p1_normalized is None or p2_normalized is None:
        return 0 # No similarity if one or both poses is missing
    return compare_poses_cosine(p1_normalized, p2_normalized)


def compare_poses_cosine(p1, p2):
    return 1 - cosine(p1[:,:2].flatten(), p2[:,:2].flatten())


def get_pose_matrix(frame, figure_index=0, figure_type='flipped_figures'):
    if figure_type not in frame or figure_index > len(frame[figure_type])-1:
        return None
    coords_and_confidence = frame[figure_type][figure_index].data
    return matrixify_pose(coords_and_confidence)


def get_laplacian_matrix(frame, normalized=True, show=False, figure_index=0, figure_type='flipped_figures'):
    """ LAPLACIAN: compute the Delaunay triangulation between keypoints, then
        use the connections to build an adjacency matrix, which is then converted
        to its (normalized) Laplacian matrix (a single matrix that encapsulates the
        degree of each node and the connections between the nodes). Then you can
        subtract a pose's Laplacian from another's to get a measure of the degree of
        similarity or difference between them.
    """
    
    if figure_type not in frame or figure_index > len(frame[figure_type])-1 or frame[figure_type][figure_index].data.shape[0] == 0:
        return None
    
    all_points = frame[figure_type][figure_index].data

    # For visualization, remove all [x,y,0] (unknown) coordinates.
    nonzero = (all_points!=0).all(axis=1)
    nz_points = all_points[nonzero]
    points = nz_points[:,:2]
    total_points = len(points)
    try:
        tri = Delaunay(points)
    except:
        # Not sure why this happens -- maybe the points are all in a line or something
        print("Error computing Delaunay triangulation")
        return None

    if show:
        plot_delaunay(frame[figure_type][figure_index])

    adjacency_matrix = lil_matrix((total_points, total_points), dtype=int)
    for i in np.arange(0, np.shape(tri.simplices)[0]):
        for j in tri.simplices[i]:
            if j < total_points:
                adjacency_matrix[j, tri.simplices[i][tri.simplices[i] < total_points]] = 1

    adjacency_graph = nx.from_scipy_sparse_matrix(adjacency_matrix)

    if normalized:
        lm = nx.normalized_laplacian_matrix(adjacency_graph)
    else:
        lm = nx.laplacian_matrix(adjacency_graph)

    return lm


def compare_laplacians(p1, p2, figure_index=0, figure_type='flipped_figures', show=False):
    lm1 = get_laplacian_matrix(p1, figure_index=figure_index, figure_type=figure_type, show=show).todense()
    lm2 = get_laplacian_matrix(p2, figure_index=figure_index, figure_type=figure_type, show=show).todense()
    if lm1.shape[0] != lm2.shape[0]:
        return None
    movement = np.subtract(lm1, lm2)
    return 1 - abs(movement.sum())
