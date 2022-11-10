# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_visualize.ipynb.

# %% auto 0
__all__ = ['GC_INTERVAL', 'MIN_MOVE', 'MAX_MOVE', 'plot_poses', 'plot_delaunay', 'fig2img', 'excerpt_pose', 'overlay_poses',
           'overlay_video', 'draw_figure', 'viz_dist_matrices']

# %% ../nbs/03_visualize.ipynb 3
import openpifpaf

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import cv2
import os
#from IPython.display import display
#from skbio.stats.distance import mantel
from scipy.spatial import Delaunay
from scipy.spatial.distance import squareform

import warnings
warnings.filterwarnings(
  action='ignore', module='matplotlib.figure', category=UserWarning,
  message=('This figure includes Axes that are not compatible with tight_layout, '
           'so results might be incorrect.'))


# Note: If an image is supplied, the detections are expected to be non-flipped
# Otherwise, they should be flipped.
def plot_poses(detections, image=None, show=True, savepath="", show_axis=True):

    skeleton_painter = openpifpaf.show.KeypointPainter(color_connections=True, linewidth=6, highlight_invisible=True)
    # Older verions of Open PifPaf:
    #skeleton_painter = openpifpaf.show.KeypointPainter(
    #  show_box=True, color_connections=True, markersize=1, linewidth=6, highlight_invisible=True, show_joint_scale=True)

    if hasattr(detections, 'data'):
        vis_detections = [detections]
    else:
        for pose in detections:
            if pose.data.shape[0] == 0:
                continue
            vis_detections.append(pose)

    with openpifpaf.show.canvas() as ax:
        if image is not None:
            ax.imshow(image)
        else:
            ax.set_aspect('equal')
        skeleton_painter.annotations(ax, vis_detections)
        if show:
            openpifpaf.show.canvas()
        if not show_axis:
            ax.set_axis_off()
        fig = ax.get_figure()
        if savepath != "":
            fig.savefig(savepath)
    
    return fig


def plot_delaunay(figure, image=None, show=True, show_axis=True):

    if hasattr(figure, 'data'):
        vis_figures = [figure]
    else:
        vis_figures = []
        for pose in figures:
            if pose.data.shape[0] == 0:
                continue
        vis_figures.append(pose)

    for figure in vis_figures:
        all_points = figure.data

        # For visualization, remove all [x,y,0] (unknown) coordinates.
        nonzero = (all_points!=0).all(axis=1)
        nz_points = all_points[nonzero]
        points = nz_points[:,:2]
        total_points = len(points)
        tri = Delaunay(points)

        plt.triplot(points[:,0], points[:,1], tri.simplices.copy())
        plt.plot(points[:,0], points[:,1], 'o')
    
    if image is not None:
        plt.gca().imshow(image)
    else:
        plt.gca().set_aspect('equal')
    if not show_axis:
        plt.gca().set_axis_off()
    if show:
        plt.show()
    
    return plt.gcf()


# From http://www.icare.univ-lille1.fr/tutorials/convert_a_matplotlib_figure
def fig2img(fig2, w=8, h=8, dpi=72):

    fig2.dpi=dpi
    fig2.set_size_inches(w, h)
    fig2.tight_layout()
    fig2.gca().set_anchor('NE')

    fig2.canvas.draw()

    # Get the RGBA buffer from the figure
    w,h = fig2.canvas.get_width_height()
    buf = np.frombuffer(fig2.canvas.tostring_argb(), dtype=np.uint8)
    buf.shape = (w,h,4)

    # canvas.tostring_argb give pixmap in ARGB mode. Roll the ALPHA channel to have it in RGBA mode
    buf = np.roll(buf, 3, axis=2)

    # put the figure pixmap into a numpy array
    w, h, d = buf.shape
    im = Image.frombytes("RGBA", (w,h), buf)
    return im


from .modify import zeroify_detections, flip_detections, shift_figure


# For visualizing individual poses with detection overlays
def excerpt_pose(video_file, frame_poses, figure_index=0, show=False, plot_type='pose', source_figure='figures', flip_figures=False, margin=.2, width=None, height=None, show_axis=True):
  
  if source_figure not in frame_poses or len(frame_poses[source_figure]) == 0:
    return None

  figures_frame = copy.deepcopy(frame_poses)
    
  figures_frame['zeroified_figures'] = zeroify_detections(figures_frame[source_figure], width=width, height=height)

  if flip_figures:
    figures_frame['zeroified_figures'] = flip_detections(figures_frame['zeroified_figures'])

  # This is used to cut out the background image, so it must be in the original (non-zeroified) coordinates
  bbox = get_bbox(figures_frame[source_figure][figure_index].data, False, margin=margin, width=width, height=height)
  figures_frame['zeroified_figures'][figure_index].data = shift_figure(figures_frame['zeroified_figures'][figure_index].data, bbox['marg'], bbox['marg'])
    
  cap = cv2.VideoCapture(video_file)

  total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  video_framerate = cap.get(cv2.CAP_PROP_FPS)

  timecode = figures_frame['time']

  frameno = int(round(timecode * video_framerate))
      
  if frameno > total_frames:
    print(frameno,"IS GREATER THAN TOTAL FRAMES IN VIDEO:",total_frames)
    return None

  cap.set(cv2.CAP_PROP_POS_FRAMES, frameno)
  ret_val, im = cap.read()
    
  # Image doesn't necessarily come in as RGB(A)!
  rgbim = cv2.cvtColor(im, cv2.COLOR_BGR2RGBA)
  pil_image = PIL.Image.fromarray(rgbim)

  cropped_image = pil_image.crop((bbox['xmin'], bbox['ymin'], bbox['xmax'], bbox['ymax']))
  if plot_type == 'delaunay':
    fig = plot_delaunay(figures_frame['zeroified_figures'][figure_index], cropped_image, show=show, show_axis=show_axis)
  else:
    fig = plot_poses(figures_frame['zeroified_figures'][figure_index], cropped_image, show=show, show_axis=show_axis)
    
  return fig


# Overlay all detected poses in a single frame on the full image
# (For multi-dancer videos)
def overlay_poses(pil_image, figures_frame, show=False, plot_type='pose', source_figure='figures', show_axis=False, savepath=""):

    if plot_type == 'delaunay':
        fig = plot_delaunay(figures_frame[source_figure], pil_image, show=show, show_axis=show_axis)
    else:
        fig = plot_poses(figures_frame[source_figure], pil_image, show=show, show_axis=show_axis, savepath=savepath)
    
    return fig


GC_INTERVAL = 1000

def overlay_video(video_file, pose_data, plot_type='pose', source_figure='figures', show_axis=False, savedir="", start_frame=0):
    """ Set savedir to a folder where a whole bunch of images from the video, with
        pose overlays drawn on them, will be stored. These can be turned into
        a video (poses_video.mp4 or similar) later using this command:
        !ffmpeg -y -framerate $FPS -pattern_type glob -i 'savedir/*.png' -strict '-2' -c:v libx264 -vf "fps=$FPS" -pix_fmt yuv420p poses_video.mp4
        Note that both occurrences of $FPS should be replaced with the framerate of
        the video, which can be obtained from get_video_stats(video_filename)
    """
    cap = cv2.VideoCapture(video_file)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_framerate = cap.get(cv2.CAP_PROP_FPS)

    for figures_frame in pose_data[start_frame:len(pose_data)]:

        timecode = figures_frame['time']
        frameno = int(round(timecode * video_framerate))

        cap.set(cv2.CAP_PROP_POS_FRAMES, frameno)
        ret_val, im = cap.read()

        # Image doesn't necessarily come in as RGB(A)!
        rgbim = cv2.cvtColor(im, cv2.COLOR_BGR2RGBA)
        pil_image = PIL.Image.fromarray(rgbim)

        savepath = os.path.join(savedir, 'image' + str(frameno+1).zfill(5) + '.png')

        fig = overlay_poses(pil_image, figures_frame, source_figure=source_figure, savepath=savepath)

        del im, rgbim, pil_image

        plt.cla()
        plt.clf()
        plt.close('all')
        plt.close(fig)
        if frameno % GC_INTERVAL == 0:
            gc.collect()
    
        del fig

MIN_MOVE = 200
MAX_MOVE = 1200

def draw_figure(point_weights=None, show=True):
    """ Scale keypoint radii by how much they moved in a video """
    links = [[0, 1], [0, 2], [1, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5, 6],
           [5, 7], [6, 8], [7, 9], [8, 10], [5, 11], [6, 12], [11, 12],
           [11, 13], [12, 14], [13, 15], [14, 16]]
    coords = [[160, 510],
            [175, 525],
            [145, 525],
            [200, 520],
            [120, 520],
            [215, 440],
            [105, 440],
            [260, 335],
            [60, 335],
            [285, 215],
            [35, 215],
            [200, 280],
            [120, 280],
            [200, 150],
            [120, 150],
            [200, 25],
            [120, 25]]

    xcoords = [c[0] for c in coords]
    ycoords = [c[1] for c in coords]

    if point_weights.any():
        input_weights = np.copy(point_weights)
    else:
        return None

    input_weights *= (200/input_weights.min())

    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    cm = plt.cm.get_cmap('RdYlBu_r')
    ax.set_aspect('equal', adjustable='box')
    ax.scatter(x=xcoords, y=ycoords, s=input_weights, c=input_weights, vmin=MIN_MOVE, vmax=MAX_MOVE, cmap=cm)

    for link in links:
        ax.plot([coords[link[0]][0], coords[link[1]][0]], [coords[link[0]][1], coords[link[1]][1]], 'k-')

    ax.set_xlim([-35, 340])
    ax.set_ylim([-20, 570])

    ax.set_axis_off()

    if show:
        plt.show()
    return fig


# Distance matrix-based comparison tests
from .matrixify import get_pose_matrix

def viz_dist_matrices(p1, p2, figure_type='flipped_figures'):
    dmatrix1 = squareform(get_pose_matrix(p1, figure_type=figure_type))
    dmatrix2 = squareform(get_pose_matrix(p2, figure_type=figure_type))
    
    plt.xticks(np.arange(17))
    plt.yticks(np.arange(17))

    plt.imshow(dmatrix1, cmap='viridis', origin='upper')
    plot_poses(p1[figure_type][0].data)

    plt.xticks(np.arange(17))
    plt.yticks(np.arange(17))

    plt.imshow(dmatrix2, cmap='viridis', origin='upper')
    plot_poses(p2[figure_type][0].data)
    plt.tight_layout()

    #print("Similarity:",mantel(dmatrix1, dmatrix2)[0])

    diffmatrix = np.absolute(dmatrix1 - dmatrix2)
    movers = diffmatrix.sum(axis=1)
    plt.xticks(np.arange(17))
    plt.yticks(np.arange(17))
    plt.imshow(diffmatrix, cmap='viridis', origin='upper')
    plt.figure()
    plt.xticks(np.arange(17))
    plt.bar(range(17), movers)
    print(movers.shape)