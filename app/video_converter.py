import cv2
import numpy as np
from pathlib import Path
import shutil

class VideoConverter():
    def __init__(self, parents):
        self.extracted_frames = []
        self.parents = parents

    def convert_mp4(self, mp4, prj, output_name=None):
        print(f"[VideoConverter] START convert_mp4 for: {mp4}")
        self.extracted_frames = []
        video = Path(mp4)
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"Error: Could not open video file {video}")
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        target_name = output_name or video.stem
        save_location = Path(prj) / "converted_videos" / target_name
        print(f"[VideoConverter] save_location={save_location}")
        save_location.mkdir(parents=True, exist_ok=True)

        frame_count = 0
        processed_frames = 0
        unique_frames = []
        previous_frame = None
        duplicate_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"[VideoConverter] end of video reached after {frame_count} kept frames")
                break

            processed_frames += 1
            self.parents.progress.emit(processed_frames, total_frames)

            if previous_frame is not None and frame.shape == previous_frame.shape and np.array_equal(frame, previous_frame):
                duplicate_count += 1
                if duplicate_count % 100 == 0:
                    print(f"[VideoConverter] duplicate frames seen so far: {duplicate_count}")
                continue

            frame_path = save_location / f"frame_{frame_count:08d}.jpg"
            ok = cv2.imwrite(str(frame_path), frame)
            if ok:
                unique_frames.append(frame_path)
                previous_frame = frame.copy()
                frame_count += 1
            else:
                print(f"[VideoConverter] failed to write frame {frame_count} to {frame_path}")
                break

        # Move all folder to the project / image_uploads folder
        shutil.move(str(save_location), str(Path(prj) / "image_uploads" / target_name))

        print(f"[VideoConverter] done. kept={len(unique_frames)} duplicate_skips={duplicate_count}")
        cap.release()
        cv2.destroyAllWindows()

        self.extracted_frames = unique_frames
        return unique_frames
