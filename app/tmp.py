from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from PIL import Image
import cv2
import numpy as np
import torch
from pathlib import Path

INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
OUTPUT_DIR = Path("./output")

def run_sam_on_photo(photo, pred):
    with Image.open(photo) as image:
        image = image.convert("RGB")
        width, height = image.size
        grid_size = 8
        x_coords = torch.linspace(0, width - 1, grid_size)
        y_coords = torch.linspace(0, height - 1, grid_size)
        grid_x, grid_y = torch.meshgrid(x_coords, y_coords, indexing="xy")
        grid_points = torch.stack((grid_x, grid_y), dim=-1).reshape(-1, 2).numpy()
        grid_labels = torch.ones(len(grid_points), dtype=torch.int32).numpy()

        pred.set_image(image)
        masks, scores, low_res_masks = pred.predict(
            point_coords=grid_points,
            point_labels=grid_labels,
            multimask_output=False,
            normalize_coords=False,
        )
        return masks, np.asarray(image).copy()

def run_videos():
    pth = Path(INSTALL_LOCATION) / "users" / "ammon" / "projects" / "rockfish_id" / "image_uploads"
    vids = [vid for vid in pth.iterdir() if vid.is_dir() and vid.name.split("_")[0] == "20260818"]
    cp = Path(__file__).resolve().parent / "packages" / "sam2" / "checkpoints" / "sam2.1_hiera_large.pt"
    cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"
    pred = SAM2ImagePredictor(build_sam2(cfg, cp))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng()

    print(vids)
    for vid in vids:
        photo_files = sorted(
            photo for photo in vid.iterdir() if photo.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not photo_files:
            print(f"No photos found in: {vid}")
            continue

        for photo in photo_files:
            print(f"Running SAM2 on photo: {photo.name}")
            masks, original_image = run_sam_on_photo(photo, pred)
            object_mask = ~masks[0].astype(bool)
            static = rng.integers(
                0, 2, size=original_image.shape[:2], dtype=np.uint8
            ) * 255
            static = np.repeat(static[:, :, None], 3, axis=2)
            composite = np.where(object_mask[:, :, None], original_image, static)
            output_path = OUTPUT_DIR / f"{photo.stem}_static.png"
            cv2.imwrite(
                str(output_path), cv2.cvtColor(composite, cv2.COLOR_RGB2BGR)
            )

def main():
    run_videos()

main()