import cv2
import numpy as np
from pathlib import Path
import shutil

class VideoConverter():
    def __init__(self, parents):
        self.parents = parents

    def convert_mp4(self, mp4, prj, output_name=None):
        print(f"[VideoConverter] START convert_mp4 for: {mp4}")
        video = Path(mp4)
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"Error: Could not open video file {video}")
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        target_name = output_name or video.stem
        save_location = Path(prj) / "converting_videos" / target_name
        fp_txt = Path(prj) / "needs_first_pass.txt"
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
        video_final_folder = Path(prj) / "image_uploads" / target_name
        shutil.move(str(save_location), str(video_final_folder))
        frame_final_locations = [Path(p) for p in video_final_folder.iterdir()]

        print(f"[VideoConverter] done. kept={len(unique_frames)} duplicate_skips={duplicate_count}")
        cap.release()
        cv2.destroyAllWindows()

        print(frame_final_locations[0:2])

        with open(fp_txt, "+a") as f:
            for frame in frame_final_locations:
                relative_frame = frame.relative_to(prj)
                f.write(f"{Path(relative_frame)}\n")

        return frame_final_locations
