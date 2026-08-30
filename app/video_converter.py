import math
from pathlib import Path
import shutil
import subprocess

class VideoConverterFFMPEG:
    def __init__(self, worker):
        self.worker = worker

    def probe(
        self,
        invideo,
        prj,
        frame_keep_percentage,
        output_name=None
    ):
        video = Path(invideo)
        prj = Path(prj)

        if not video.exists():
            print(
                f"[VideoConverter] Error: "
                f"Video does not exist: {video}"
            )
            return []

        if frame_keep_percentage <= 0:
            print(
                "[VideoConverter] Error: "
                "frame_keep_percentage must be greater than 0"
            )
            return []

        num_frames_add_round = max(
            1,
            round(100 / frame_keep_percentage)
        )

        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=nb_frames,r_frame_rate,duration",
            "-of",
            "default=noprint_wrappers=1",
            str(video)
        ]

        print("[VideoConverter] Running ffprobe:")
        print(" ".join(probe_cmd))

        try:
            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                check=True
            )

        except FileNotFoundError:
            print(
                "[VideoConverter] ERROR: "
                "ffprobe was not found in PATH."
            )
            return []

        except subprocess.CalledProcessError as e:
            print(
                f"[VideoConverter] ffprobe failed: {e}"
            )

            if e.stderr:
                print(e.stderr)

            return []

        probe_info = {}

        for line in probe_result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                probe_info[key] = value

        total_video_frames = 0

        nb_frames = probe_info.get("nb_frames")

        if nb_frames and nb_frames != "N/A":
            try:
                total_video_frames = int(nb_frames)
            except ValueError:
                total_video_frames = 0

        if total_video_frames <= 0:
            duration = probe_info.get("duration")
            frame_rate = probe_info.get("r_frame_rate")

            try:
                if duration and frame_rate:
                    numerator, denominator = (
                        frame_rate.split("/")
                    )

                    fps = (
                        float(numerator) /
                        float(denominator)
                    )

                    if fps > 0:
                        total_video_frames = round(
                            float(duration) * fps
                        )

            except (
                ValueError,
                ZeroDivisionError
            ):
                total_video_frames = 0

        print(
            f"[VideoConverter] total video frames="
            f"{total_video_frames}"
        )

        print(
            f"[VideoConverter] keeping every "
            f"{num_frames_add_round} frame(s)"
        )

        # Large video handling
        #one_gib = 1024 ** 3
        #
        #if video.stat().st_size > one_gib:
        #    print(
        #        f"[VideoConverter] {video.name} is larger "
        #        f"than 1 GiB."
        #    )
        #
        #    print(
        #        "[VideoConverter] Splitting into "
        #        "5-second segments."
        #    )
        #
        #    return self.split_video(
        #        video,
        #        prj,
        #        frame_keep_percentage,
        #        output_name
        #    )

        total_frames = 0

        if total_video_frames > 0:
            total_frames = math.ceil(
                total_video_frames /
                num_frames_add_round
            )

        print(
            f"[VideoConverter] estimated output frames="
            f"{total_frames}"
        )

        return self.convert_video(
            video,
            prj,
            num_frames_add_round,
            output_name,
            total_frames
        )

    def convert_video(
        self,
        video,
        prj,
        num_frames_add_round,
        output_name,
        total_frames
    ):
        print(
            f"[VideoConverter] START convert_video for: {video}"
        )

        fp_txt = Path(prj) / "needs_first_pass.txt"

        target_name = output_name or video.stem
        save_location = Path(prj) / "image_uploads" / target_name

        print(
            f"[VideoConverter] save_location={save_location}"
        )

        save_location.mkdir(
            parents=True,
            exist_ok=True
        )

        output_pattern = save_location / f"{target_name}_%08d.jpg"

        select_filter = (
            f"select='not(mod(n\\,{num_frames_add_round}))'"
        )

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video),
            "-vf", select_filter,
            "-q:v", "2",
            "-fps_mode", "vfr",
            "-progress", "pipe:2",
            "-stats_period", "0.5",
            "-nostats",
            str(output_pattern)
        ]

        print(
            "[VideoConverter] Running FFmpeg:"
        )

        print(
            " ".join(
                f'"{x}"' if " " in str(x) else str(x)
                for x in ffmpeg_cmd
            )
        )

        try:
            process = subprocess.Popen(
                ffmpeg_cmd,

                # Progress comes through stderr.
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,

                text=True,

                # Important on Windows.
                encoding="utf-8",
                errors="replace",

                bufsize=1
            )

        except FileNotFoundError:
            print(
                "[VideoConverter] ERROR: FFmpeg was not found."
            )

            return []

        except Exception as exc:
            print(
                f"[VideoConverter] ERROR starting FFmpeg: "
                f"{exc}"
            )

            return []

        if process.stderr is None:
            print(
                "[VideoConverter] ERROR: Could not access "
                "FFmpeg stderr."
            )

            process.kill()
            process.wait()

            return []

        processed_frames = 0
        try:
            for raw_line in process.stderr:
                line = raw_line.strip()

                if not line:
                    continue

                if line.startswith("frame="):
                    processed_frames = 0
                    self.worker.progress.emit(processed_frames, total_frames)
                    
        except Exception as exc:
            print(
                f"[VideoConverter] Error reading FFmpeg "
                f"output: {exc}"
            )

        return_code = process.wait()

        print(
            f"[VideoConverter] FFmpeg exited with code "
            f"{return_code}"
        )

        if return_code != 0:
            print(
                "[VideoConverter] FFmpeg conversion failed."
            )

            return []

        globber = f"{target_name}_*.jpg"
        frame_final_locations = sorted(
            save_location.glob(globber)
        )

        print(
            f"[VideoConverter] Conversion complete. "
            f"kept={len(frame_final_locations)}"
        )

        with open(fp_txt, "a", encoding="utf-8") as f:
            for frame in frame_final_locations:
                relative_frame = frame.relative_to(prj)
                f.write(f"{relative_frame}\n")

        return frame_final_locations

    def split_video(
        self,
        invideo,
        prj,
        frame_keep_percentage,
        output_name
    ):
        invideo = Path(invideo)
        prj = Path(prj)

        split_dir = (
            prj /
            "converting_videos" /
            f"{invideo.stem}_segments"
        )

        if split_dir.exists():
            try:
                shutil.rmtree(split_dir)
            except OSError as e:
                print(
                    f"[VideoConverter] Could not clean "
                    f"old segment directory: {e}"
                )
                return []

        split_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        outpattern = (
            split_dir /
            f"{invideo.stem}_%05d"
            f"{invideo.suffix}"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(invideo),
            "-c", "copy",
            "-map", "0",
            "-segment_time", "5",
            "-f", "segment",
            "-reset_timestamps", "1",
            str(outpattern)
        ]

        print(
            "[VideoConverter] Splitting large video:"
        )
        print(" ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

        except FileNotFoundError:
            print(
                "[VideoConverter] ERROR: "
                "FFmpeg was not found in PATH."
            )
            return []

        if process.stderr is not None:
            for line in process.stderr:
                line = line.strip()

                if line:
                    print(
                        f"[FFMPEG SPLIT] {line}"
                    )

        return_code = process.wait()

        if return_code != 0:
            print(
                f"[VideoConverter] FFmpeg failed while "
                f"splitting {invideo.name}"
            )
            return []

        split_videos = sorted(
            split_dir.glob(
                f"{invideo.stem}_*"
                f"{invideo.suffix}"
            )
        )

        print(
            f"[VideoConverter] Created "
            f"{len(split_videos)} segments."
        )

        if not split_videos:
            print(
                "[VideoConverter] FFmpeg produced "
                "no video segments."
            )
            return []

        all_frames = []

        for index, segment in enumerate(
            split_videos,
            start=1
        ):
            print(
                f"[VideoConverter] Processing segment "
                f"{index}/{len(split_videos)}: "
                f"{segment.name}"
            )

            frames = self.probe(
                segment,
                prj,
                frame_keep_percentage,
                output_name
            )

            if frames:
                all_frames.extend(frames)

        try:
            shutil.rmtree(split_dir)

            print(
                "[VideoConverter] Removed temporary "
                "segment directory."
            )

        except OSError as e:
            print(
                "[VideoConverter] Could not remove "
                f"temporary segment directory: {e}"
            )

        return all_frames