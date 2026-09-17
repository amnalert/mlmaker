from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QFontMetrics
from PySide6.QtCore import QTimer, Qt
from pathlib import Path
import shutil

INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

class AutoScalingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("font-weight: bold;")
        self._last_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        super().setText(text)
        self.updateGeometry()
        QTimer.singleShot(0, self.scale_font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scale_font()

    def scale_font(self):
        text = self.text()
        if not text:
            return

        target_width = self.width() - 20
        target_height = self.height() - 10
        if target_width <= 20 or target_height <= 10:
            return

        font = self.font()
        font_size = 128 # Max desired
        font.setPointSize(font_size)

        while font_size > 10:
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() <= target_width and rect.height() <= target_height:
                break
            font_size -= 1
            font.setPointSize(font_size)

        self.setFont(font)


def reorganize_auto_isolated():
    pth = Path(INSTALL_LOCATION) / "users" / "ammon" / "projects" / "rockfish_id" / "auto_sam_isolated"
    for speciesdir in pth.iterdir():
        imgs = [ path for path in speciesdir.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS ]

        out = Path(INSTALL_LOCATION) / f"{speciesdir.stem}"
        out.mkdir(parents=True, exist_ok=True)

        for img in imgs:
            shutil.copy2(img, Path(out) / f"{img.name}")

from sam2.build_sam import build_sam2_video_predictor
def run_sam_on_video(video):
    import torch

    v = Path(video)
    cp = "./packages/sam2/checkpoints/sam2.1_hiera_large.pt"
    cfg = "./packages/sam2/sam2/configs/sam2.1/sam2.1_hiera_l.yaml"
    pred = build_sam2_video_predictor(cfg, cp)

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        state = pred.init_state(v)
        grid_size = 8
        x_coords = torch.linspace(0, state["video_width"] - 1, grid_size)
        y_coords = torch.linspace(0, state["video_height"] - 1, grid_size)
        grid_x, grid_y = torch.meshgrid(x_coords, y_coords, indexing="xy")
        grid_points = torch.stack((grid_x, grid_y), dim=-1).reshape(-1, 2)
        grid_labels = torch.ones(len(grid_points), dtype=torch.int32)

        frame_masks = []
        for frame_idx in range(state["num_frames"]):
            _, _, masks = pred.add_new_points_or_box(
                state,
                frame_idx=frame_idx,
                obj_id=1,
                points=grid_points,
                labels=grid_labels,
                clear_old_points=True,
                normalize_coords=True,
            )
            frame_masks.append(masks)

    return frame_masks

def run_videos():
    pth = Path(INSTALL_LOCATION) / "users" / "ammon" / "projects" / "rockfish_id" / "image_uploads"
    vids = [ vid for vid in pth.iterdir() if vid.name.split("_")[0] == 20260818 ]
    print(vids)
    for vid in vids:
        # remove video file
        for file in vid.iterdir():
            if file.suffix == ".mp4":
                file.unlink()
        run_sam_on_video(vid)