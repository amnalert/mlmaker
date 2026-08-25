import cv2
import math
from pathlib import Path
import shutil
import subprocess

class VideoConverter():
    def __init__(self, parents):
        self.parents = parents

    def convert_mp4(self, invideo, prj, frame_keep_percentage, output_name=None):
        print(f"[VideoConverter] START convert_mp4 for: {invideo}")
        video = Path(invideo)
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"Error: Could not open video file {video}")
            return []

        target_name = output_name or video.stem
        save_location = Path(prj) / "image_uploads" / target_name
        fp_txt = Path(prj) / "needs_first_pass.txt"
        print(f"[VideoConverter] save_location={save_location}")
        save_location.mkdir(parents=True, exist_ok=True)

        frame_count = 0
        processed_frames = 0
        unique_frames = []
        previous_frame = None
        duplicate_count = 0

        # ex. 100/100 = 1, 100/25 = 4
        num_frames_add_round = round(100/frame_keep_percentage)
        total_frames = round(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / num_frames_add_round)

        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)

            ret, frame = cap.read()
            if not ret:
                print(f"[VideoConverter] end of video reached after ~{round(frame_count / num_frames_add_round)} kept frames")
                break

            processed_frames += 1
            self.parents.progress.emit(processed_frames, total_frames)

            frame_path = save_location / f"frame_{frame_count:08d}.jpg"
            ok = cv2.imwrite(str(frame_path), frame)
            if ok:
                unique_frames.append(frame_path)
                frame_count += num_frames_add_round
            else:
                print(f"[VideoConverter] failed to write frame {frame_count} to {frame_path}")
                break

        frame_final_locations = [Path(p) for p in save_location.iterdir()]

        print(f"[VideoConverter] done. kept={len(unique_frames)} duplicate_skips={duplicate_count}")
        cap.release()
        cv2.destroyAllWindows()

        with open(fp_txt, "+a") as f:
            for frame in frame_final_locations:
                relative_frame = frame.relative_to(prj)
                f.write(f"{Path(relative_frame)}\n")

        return frame_final_locations

class VideoConverter2():
    def __init__(self, parents):
        self.parents = parents

    def convert_mp4(self, invideo, prj, frame_keep_percentage, output_name=None):
        print(f"[VideoConverter] START convert_mp4 for: {invideo}")
        video = Path(invideo)
        if not video.exists():
            print(f"[VideoConverter] Error: Video does not exist: {video}")
            return []

        target_name = output_name or video.stem
        save_location = Path(prj) / "image_uploads" / target_name
        fp_txt = Path(prj) / "needs_first_pass.txt"

        print(f"[VideoConverter] save_location={save_location}")
        save_location.mkdir(parents=True, exist_ok=True)

        # ex. 100/100 = 1, 100/25 = 4
        num_frames_add_round = max(1, round(100 / frame_keep_percentage))

        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,r_frame_rate",
            "-of", "default=noprint_wrappers=1",
            str(video)
        ]

        try:
            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[VideoConverter] ffprobe failed: {e}")
            return []

        probe_info = {}
        for line in probe_result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                probe_info[key] = value

        try:
            total_video_frames = int(probe_info.get("nb_frames", 0))
        except ValueError:
            total_video_frames = 0

        total_frames = 0
        if total_video_frames > 0:
            total_frames = math.ceil(
                total_video_frames / num_frames_add_round
            )

        print(
            f"[VideoConverter] total video frames={total_video_frames}"
        )
        print(
            f"[VideoConverter] keeping every {num_frames_add_round} frame(s)"
        )
        print(
            f"[VideoConverter] estimated output frames={total_frames}"
        )

        output_pattern = save_location / "frame%08d.jpg"
        select_filter = f"select='not(mod(n\\,{num_frames_add_round}))'"
        ffmpeg_cmd = [
            "ffmpeg",
            "-y", "-i", str(video),
            "-vf", select_filter,
            "-q:v", "2",
            "-fps_mode", "vfr",
            "-progress", "pipe:1",
            "-nostats",
            str(output_pattern)
        ]

        print("[VideoConverter] running ffmpeg:")
        print(" ".join(ffmpeg_cmd))

        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )

            if process.stdout is None:
                print("[VideoConverter] ERROR: Could not access FFmpeg stdout")
                process.kill()
                return []
            
            processed_frames = 0

            for line in process.stdout:
                line = line.strip()
                print(f"[FFMPEG] {line}")

                if line.startswith("[FFMPEG] frame="):
                    try:
                        processed_frames = int(line.split("=", 1)[1])
                        if total_frames > 0:
                            self.parents.progress.emit(
                                min(processed_frames, total_frames),
                                total_frames
                            )
                    except ValueError:
                        pass

            return_code = process.wait()

            if return_code != 0:
                print("[VideoConverter] FFmpeg error.")

        except FileNotFoundError:
            print(
                "[VideoConverter] ERROR: FFmpeg was not found."
                "Please install and add ffmpeg to your environment's PATH(pip install ffmpeg-python)"
            )
            return []

        frame_final_locations = list(
            save_location.glob("frame*.jpg")
        )

        print(f"[VideoConverter] done. kept={len(frame_final_locations)}")

        with open(fp_txt, "+a") as f:
            for frame in frame_final_locations:
                relative_frame = frame.relative_to(prj)
                f.write(f"{Path(relative_frame)}\n")

        return frame_final_locations
