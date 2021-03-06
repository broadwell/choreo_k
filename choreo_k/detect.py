# AUTOGENERATED! DO NOT EDIT! File to edit: 00_detect.ipynb (unless otherwise specified).

__all__ = ['Detector']

# Cell
import torch
import openpifpaf

from PIL import Image
import cv2
import os

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

        net_cpu, _ = openpifpaf.network.factory(checkpoint='shufflenetv2k30w-200510-104256-cif-caf-caf25-o10s-0b5ba06f.pkl', download_progress=False)
        self.net = net_cpu.to(self.device)

        # These could be parameters to __init__()
        openpifpaf.decoder.CifSeeds.threshold = 0.5
        openpifpaf.decoder.nms.Keypoints.keypoint_threshold = 0.2
        openpifpaf.decoder.nms.Keypoints.instance_threshold = 0.2

        self.processor = openpifpaf.decoder.factory_decode(selt.net.head_nets, basenet_stride=self.net.base_net.stride)

        self.__preprocess__ = openpifpaf.transforms.Compose([
            openpifpaf.transforms.NormalizeAnnotations(),
            openpifpaf.transforms.CenterPadTight(16),
            openpifpaf.transforms.EVAL_TRANSFORM,])

    def __detect_one_or_more_images__(self, batch):
        data = openpifpaf.datasets.PilImageList(batch, preprocess=self.__preprocess__)
        batch_size = len(batch)

        loader = torch.utils.data.DataLoader(
            data, batch_size=batch_size, pin_memory=True,
            collate_fn=openpifpaf.datasets.collate_images_anns_meta)

        for images_batch, _, __ in loader:
            detections = self.processor.batch(self.net, images_batch, device=self.device)[0]

        return detections

    def process_image(self, image_path):
        """ Applies the pose detection model to a single image file. Returns detections. """
        pil_image = Image.open(image_path)
        detections = self.__detect_one_or_more_images__([pil_image], self.processor)
        return detections

    def get_poses_from_video(video_file, start_seconds=0.0, end_seconds=0.0, max_frames=0, seconds_to_skip=0.0, images_too=False, write_images=False, folder_name='video_folder'):
        """ Given a video file, extracts video frames as images at `seconds_to_skip` intervals,
            from `start_seconds` to `end_seconds`, and runs `__detect_one_or_more_images__()` on each.
            Returns a list of frame pose data items, which are dictionaries with the following elements:
            { 'frame_id': <the frame's position in this list (not in the entire video, if seconds_to_skip != 0)>,
              'time': <the frame's timecode within the excerpt (not within the full video, if start_seconds != 0)>,
              'figures': [<OpenPifPaf pose detection objects> for all figures detected in the frame]
              <OPTIONAL> 'image': <a PIL image object for the frame>
            }
            `write_images`, if true, causes the extracted frame images to be written to a folder
            specified by `folder_name`, with the naming scheme `image00001.png`
        """

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
            if not os.path.isdir(folder_name):
                os.mkdir(folder_name)
            for filename in os.listdir(folder_name):
                file_path = os.path.join(folder_name, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)

        while cap.isOpened() and (frame_count < total_frames):
            ret_val, im = cap.read()

            timecode = frame_count * frame_duration
            frame_count += 1

            if (end_seconds and timecode > end_seconds) or (max_frames and frames_processed >= max_frames):
                return pose_output

            if timecode < start_seconds:
                continue

            if m is None:
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
            pil_image = Image.fromarray(rgbim)

            detections = self.__detect_one_or_more_images__([pil_image])

            print("Frame",frame_count,"of",total_frames,round(timecode,2),"figures",len(detections))

            this_frame_data = {'frame_id': frame_count, 'time': timecode, 'figures': detections} #, 'flipped_figures': flipped_detections, 'zeroified_figures': zeroified_detections}
            if images_too:
                this_frame_data['image'] = rgbim
            if write_images:
                pil_image.save(os.path.join('video_images', 'image' + str(int(frames_processed + 1)).zfill(5) + '.png'), 'PNG')

            pose_output.append(this_frame_data)
            frames_processed += 1

        return pose_output