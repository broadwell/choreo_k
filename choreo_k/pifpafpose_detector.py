# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_pifpafpose_detector.ipynb.

# %% auto 0
__all__ = ['Detector']

# %% ../nbs/00_pifpafpose_detector.ipynb 4
import torch
import openpifpaf

import cv2
import os
from matplotlib import pyplot as plt
import PIL
import io
import numpy as np

#%matplotlib inline

openpifpaf.show.Canvas.show = True
openpifpaf.show.Canvas.image_min_dpi = 200

class Detector:
    """Given a still image (or video frame), finds poses.
    
    Attributes:  
      device: PyTorch computing resource (GPU or CPU)  
      net: Pose detection neural network model  
      processor: Pose detection image processor  
    """
    
    def __init__(self):
        try:
            self.device = torch.device('cuda')  # if cuda is available
        except:
            self.device = torch.device('cpu')

    def init_model(self, model_url=None, model_name="resnet50", decoder="cifcaf"):
        #self.predictor = openpifpaf.Predictor(checkpoint='shufflenetv2k30-wholebody')
        #self.predictor = openpifpaf.Predictor(checkpoint='shufflenetv2k30')
        self.decoder = decoder # other decoder option="posesimilarity"
        self.predictor = openpifpaf.Predictor(checkpoint=model_name)

    def detect_image(self, image_path, viz=False):
        """ Applies the pose detection model to a single image file. Returns detections. """
        pil_im = PIL.Image.open(image_path)
        image_array = np.asarray(pil_im)
        
        detections, gt_anns, image_meta = self.predictor.pil_image(pil_im)
        
        if viz:
            self.plot_poses(detections, image_array, show=True)
        
        return detections
    
    def __detect_pil_image__(self, pil_im):
        detections, gt_anns, image_meta = self.predictor.pil_image(pil_im)
        return detections
        
    
    def plot_poses(self, detections, image_array=None, show=True, savepath="", show_axis=False):

        skeleton_painter = openpifpaf.show.painters.KeypointPainter()
        # These are some of the viz parameters
        #skeleton_painter = openpifpaf.show.painters.KeypointPainter(show_box=True, marker_size=1, line_width=6, highlight_invisible=True, show_joint_scales=True)
        
        # This is the most straightforward way to draw the skeletons and annotations, but
        # it doesn't provide access to the viz parameters and doesn't allow the background
        # to be blank
        #annotation_painter = openpifpaf.show.AnnotationPainter()
        #with openpifpaf.show.image_canvas(image_array) as ax:
        #    annotation_painter.annotations(ax, detections) 

        vis_detections = []
        
        if hasattr(detections, 'data'):
            vis_detections = [detections]
        else:
            for pose in detections:
                if pose.data.shape[0] == 0:
                    continue
                vis_detections.append(pose)
                
        with openpifpaf.show.canvas() as ax:
            if image_array is not None:
                ax.imshow(image_array)
            else:
                # If there isn't a background image, the poses are plotted with the
                # origin in the bottom left, rather than top left
                ax.set_aspect('equal')
                ax.invert_yaxis()
            for detection in vis_detections:
                skeleton_painter.annotation(ax, detection)
            if not show_axis:
                ax.set_axis_off()
            fig = ax.get_figure()
            fig.set_constrained_layout(True)
            
            if savepath != "":
                fig.savefig(savepath)

        return fig
    
    def overlay_poses(self, image_array, figures_frame, show=False, source_figure='figures', show_axis=False, savepath=""):
        return self.plot_poses(figures_frame[source_figure], image_array, show=show, show_axis=show_axis, savepath=savepath)
    
    
    def detect_video(self, video_file, start_seconds=0.0, end_seconds=0.0, max_frames=0, seconds_to_skip=0.0, images_too=False, write_images=False, output_images_path='video_folder'):
        """ Given a video file, extracts video frames as images at `seconds_to_skip` intervals,
            from `start_seconds` to `end_seconds`, and runs `__detect_one_or_more_images__()` on each.
            Returns a list of frame pose data items, which are dictionaries with the following elements:
            { 'frame_id': <the frame's position in this list (not in the entire video, if seconds_to_skip != 0)>, 
              'time': <the frame's timecode within the excerpt (not within the full video, if start_seconds != 0)>,
              'figures': [<OpenPifPaf pose detection objects> for all figures detected in the frame]
              <OPTIONAL> 'image': <a PIL image object for the frame>
            }
            `write_images`, if true, causes the extracted frame images to be written to a folder
            specified by `output_images_path`, with the naming scheme `image00001.png`
        """
        
        GC_INTERVAL = 1000
        
        cap = cv2.VideoCapture(video_file)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print('total frames in video:',total_frames)

        video_framerate = cap.get(cv2.CAP_PROP_FPS)
        print('video FPS:',video_framerate)
        frame_duration = 1 / float(video_framerate)

        frame_count = 0.0
        frames_processed = 0
        timecode = 0.0
        skip_until = start_seconds

        pose_output = []

        if write_images:
            if not os.path.isdir(output_images_path):
                os.mkdir(output_images_path)
            for filename in os.listdir(output_images_path):
                file_path = os.path.join(output_images_path, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)

        bar = display(self.__progress__(0, total_frames-1), display_id=True)
        while cap.isOpened() and (frame_count < total_frames):
            ret_val, im = cap.read()

            timecode = frame_count * frame_duration
            frame_count += 1

            bar.update(self.__progress__(frame_count, total_frames-1))

            if (end_seconds and timecode > end_seconds) or (max_frames and frames_processed >= max_frames):
                return pose_output

            if timecode < start_seconds:
                continue

            if im is None:
                # Might want to retry here
                # print("Missed a frame, continuing...")
                # For now, we'll count a missed frame as a processed frame
                continue

            if seconds_to_skip and timecode < skip_until:
                continue
            else:
                skip_until += seconds_to_skip

            im_height, im_width, im_channels = im.shape

            frame_id = int(round(cap.get(1)))

            # Image doesn't necessarily come in as RGB(A)!
            rgbim = cv2.cvtColor(im, cv2.COLOR_BGR2RGBA)
            pil_image = PIL.Image.fromarray(rgbim)

            detections = self.__detect_pil_image__(pil_image)

            print("Frame",frame_count,"of",total_frames,round(timecode,2),"figures",len(detections))

            this_frame_data = {'frame_id': frame_count, 'time': timecode, 'figures': detections} #, 'flipped_figures': flipped_detections, 'zeroified_figures': zeroified_detections}
            if images_too:
                this_frame_data['image'] = rgbim
            if write_images:
                savepath = os.path.join(output_images_path, 'image' + str(int(frames_processed + 1)).zfill(5) + '.png')
                self.overlay_poses(im, this_frame_data, source_figure='figures', savepath=savepath)
                del im, rgbim, pil_image

            pose_output.append(this_frame_data)
            frames_processed += 1

        return pose_output
