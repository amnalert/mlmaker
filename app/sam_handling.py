from PySide6.QtWidgets import QWidget, QMessageBox
from PySide6.QtCore import Signal, QThread, QObject
import torch
import sys, os, json, subprocess
from pathlib import Path
import cv2
import numpy as np
from typing import Optional

from sam2.build_sam import build_sam2
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
from sam2.sam2_image_predictor import SAM2ImagePredictor

INSTALL_LOCATION = Path(__file__).resolve().parent.parent
SAM_PATH = Path(INSTALL_LOCATION) / "app" / "packages" / "sam2"

class SAMWorker(QObject):
    finished = Signal()
    failed = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)

    prediction = Signal(object)

    def __init__(self, model, config, device, img_list, project, outdir):
        super().__init__()
        self.model = model
        self.config = config
        self.device = device
        self.img_list = img_list
        self.project = project
        self.outdir = outdir

    def run_auto(self):
        try:
            self.status.emit(f"[SAMPass] Loading SAM2 model {self.model.stem}...")

            sam2 = build_sam2(
                str(self.config),
                str(self.model),
                device=self.device,
                apply_postprocessing=False
            )

            mask_gen = SAM2AutomaticMaskGenerator(sam2)
            total = len(self.img_list)

            for index, img in enumerate(self.img_list, 1):
                img = Path(img)

                image = cv2.imread(str(img))
                if image is None:
                    self.progress.emit(index, total)
                    continue

                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                self.status.emit(f"[SAMPass] Processing {img.name}...")
                masks = mask_gen.generate(image)

                if masks:
                    self.status.emit(f"[SAMPass] Image {img.name} had {len(masks)} objects. Converting to singles.")
                    self.convert_masks(masks, image, img)

                self.update_fp_file(img)
                self.progress.emit(index, total)

            self.finished.emit()

        except Exception as e:
            self.failed.emit(f"[SAMPass] Failed: {str(e)}")

    def run_point(self, px, py, image, obj):
        # obj is 0 for background, 1 for object
        sam2 = build_sam2(str(self.config), str(self.model), device=self.device)
        predictor = SAM2ImagePredictor(sam2)

        print(f"[SAMPredict] image: {image}")
        cv2image = cv2.imread(str(image))
        if cv2image is None:
            return
        cv2image = cv2.cvtColor(cv2image, cv2.COLOR_BGR2RGB)

        predictor.set_image(cv2image)

        self.status.emit(f"[SAMPredict] Start prediction for point ({px}, {py}) for image {image.name}")
        point = np.array([[px, py]])
        label = np.array([obj])

        masks, scores, _ = predictor.predict(
            point_coords=point,
            point_labels=label,
            multimask_output=True
        )

        best_mask_idx = np.argmax(scores)
        best_mask = masks[best_mask_idx].astype(np.uint8) * 255
        self.status.emit(f"[SAMPredict] Best mask confidence score: {scores[best_mask_idx]:.4f}")


        contours, _ = cv2.findContours(best_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        formatted_contours = [c.reshape(-1, 2) for c in contours]

        self.convert_masks(best_mask, cv2image, image, contours)

        self.prediction.emit(formatted_contours)
        self.finished.emit()

    def run_box(self, box, image):
        # can also predict from a bounding box instead of a single point
        sam2 = build_sam2(str(self.config), str(self.model), device=self.device)
        predictor = SAM2ImagePredictor(sam2)

        # box needs to be in format [x_min, y_min, x_max, y_max]
        inbox = np.array(box)

        masks, scores, _ = predictor.predict(
            box=inbox,
            multimask_output=False
        )

    def convert_masks(self, masks, image, source_image, t=[]):
        if len(t) > 0:
            mask = masks > 0

            fg_object = np.zeros_like(image)
            fg_object[mask] = image[mask]

            all_points = np.vstack(t)
            x, y, w, h = cv2.boundingRect(all_points)

            cropped_fg = fg_object[y:y+h, x:x+w]
            cropped_mask = mask[y:y+h, x:x+w]

            max_side = max(w, h)

            raw_noise = np.random.choice([0, 255], size=(max_side, max_side), p=[0.5, 0.5]).astype(np.uint8)
            square_static = cv2.cvtColor(raw_noise, cv2.COLOR_GRAY2RGB)

            pad_x = (max_side - w) // 2
            pad_y = (max_side - h) // 2

            square_static[pad_y:pad_y+h, pad_x:pad_x+w][cropped_mask] = cropped_fg[cropped_mask]

            output = cv2.cvtColor(square_static, cv2.COLOR_RGB2BGR)
            outpath = Path(self.outdir) / source_image.stem
            outpath.mkdir(parents=True, exist_ok=True)

            counter = 1
            outpath = Path(self.outdir) / source_image.stem / f"{source_image.stem}_mask_1.png"
            while outpath.exists():
                counter += 1
                outpath = Path(self.outdir) / source_image.stem / f"{source_image.stem}_mask_{counter}.png"

            cv2.imwrite(str(outpath), output)


        else:
            for idx, mask_data in enumerate(masks):
                mask = mask_data["segmentation"]

                fg_object = np.zeros_like(image)
                fg_object[mask] = image[mask]

                x, y, w, h = [ int(v) for v in mask_data["bbox"] ]

                cropped_fg = fg_object[y:y+h, x:x+w]
                cropped_mask = mask[y:y+h, x:x+w]

                max_side = max(w, h)

                raw_noise = np.random.choice([0, 255], size=(max_side, max_side), p=[0.5, 0.5]).astype(np.uint8)
                square_static = cv2.cvtColor(raw_noise, cv2.COLOR_GRAY2RGB)

                pad_x = (max_side - w) // 2
                pad_y = (max_side - h) // 2

                square_static[pad_y:pad_y+h, pad_x:pad_x+w][cropped_mask] = cropped_fg[cropped_mask]

                output = cv2.cvtColor(square_static, cv2.COLOR_RGB2BGR)
                outpath = Path(self.outdir) / source_image.stem
                outpath.mkdir(parents=True, exist_ok=True)

                cv2.imwrite(str(self.outdir / source_image.stem / f"{source_image.stem}_mask_{idx:03d}.png"), output)

    def update_fp_file(self, image):
        needs_fp_file = self.project / "needs_first_pass.txt"

        lines = needs_fp_file.read_text().splitlines()

        img_rel_path = image.resolve().relative_to(self.project.resolve()).as_posix()

        if img_rel_path in lines:
            lines.remove(img_rel_path)

        needs_fp_file.write_text("\n".join(lines))

# ------------------------------------------------------------------------------

class SAMPass(QWidget):
    def __init__(self, parents, controller):
        super().__init__()
        self.parents = parents
        self.controller = controller

        self.checkpoints = [
            Path(SAM_PATH) / "checkpoints" / "sam2.1_hiera_base_plus.pt",
            Path(SAM_PATH) / "checkpoints" / "sam2.1_hiera_large.pt",
            Path(SAM_PATH) / "checkpoints" / "sam2.1_hiera_small.pt",
            Path(SAM_PATH) / "checkpoints" / "sam2.1_hiera_tiny.pt"
        ]

        self.model_cfgs = [
            Path(SAM_PATH) / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_b+.yaml",
            Path(SAM_PATH) / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_l.yaml",
            Path(SAM_PATH) / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_s.yaml",
            Path(SAM_PATH) / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_t.yaml"
        ]

        self.model  = Path(SAM_PATH)
        self.config = Path(SAM_PATH)

        self.sam2 = ""
        self.mask_gen = ""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"[SAMPass] Device: {self.device}")
        if torch.cuda.is_available():
            print(f"[SAMPass] GPU: {torch.cuda.get_device_name(0)}")

        self.project = Path(INSTALL_LOCATION)
        self.outdir = Path(INSTALL_LOCATION)
        self.username = ""

    def begin_sam_pass(self, img_list, project, username, user_file, default_size=None):
        msg = QMessageBox(self)
        self.project = Path(project)
        self.username = username
        self.outdir = Path(self.project) / "sam_isolated_objects"
        self.outdir.mkdir(parents=True, exist_ok=True)

        msg.setWindowTitle("SAM Size Selection")
        msg.setText("Please choose a size of the sam2.1 model you would like to use.")
        msg.setInformativeText("Larger models are slower and use more processing power but are more accurate.")
        msg.setStandardButtons(QMessageBox.StandardButton.Cancel)

        tiny  = msg.addButton("Tiny", QMessageBox.ButtonRole.ActionRole)
        small = msg.addButton("Small", QMessageBox.ButtonRole.ActionRole)
        base  = msg.addButton("Base+", QMessageBox.ButtonRole.ActionRole)
        large = msg.addButton("Large", QMessageBox.ButtonRole.ActionRole)

        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.exec()

        if (msg.clickedButton() == QMessageBox.StandardButton.Cancel):
            return
        elif (msg.clickedButton() == tiny) or (default_size == "tiny"):
            self.model  = self.checkpoints[3]
            self.config = self.model_cfgs[3]
        elif (msg.clickedButton() == small) or (default_size == "small"):
            self.model  = self.checkpoints[2]
            self.config = self.model_cfgs[2]
        elif (msg.clickedButton() == base) or (default_size == "base+"):
            self.model  = self.checkpoints[0]
            self.config = self.model_cfgs[0]
        elif (msg.clickedButton() == large) or (default_size == "large"):
            self.model  = self.checkpoints[1]
            self.config = self.model_cfgs[1]

        #if choose:
        #    reply = QMessageBox.question(
        #        self,
        #        "Set Default SAM Size",
        #        f"Would you like to set {msg.clickedButton().text()} as your default size SAM model?",
        #        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        #        QMessageBox.StandardButton.No
        #    )
        #    if reply == QMessageBox.StandardButton.Yes:
        #        with open(user_file, "r") as f:
        #            data = json.load(f)
        #        data[self.username]["default_sam_size"] = msg.clickedButton().text()
        #        with open(user_file, "w") as f:
        #            json.dump(data, f, indent=4)
        #        # WIP: Will add user config editing later

        self.start_sam_thread(img_list)
    
    def start_sam_thread(self, img_list):
        self.sam_thread = QThread()
        self.sam_worker = SAMWorker(
            self.model,
            self.config,
            self.device,
            img_list,
            self.project,
            self.outdir
        )

        self.sam_worker.moveToThread(self.sam_thread)

        self.sam_thread.started.connect(self.sam_worker.run_auto)

        self.sam_worker.progress.connect(self.sam_progress)
        self.sam_worker.status.connect(print)

        self.sam_worker.finished.connect(self.sam_finished)
        self.sam_worker.failed.connect(self.sam_failed)

        self.sam_worker.finished.connect(self.sam_thread.quit)
        self.sam_worker.failed.connect(self.sam_thread.quit)

        self.sam_thread.finished.connect(self.sam_worker.deleteLater)
        self.sam_thread.finished.connect(self.sam_thread.deleteLater)

        self.sam_thread.finished.connect(self.sam_thread_finished)

        self.sam_thread.start()

    def sam_progress(self, index, total):
        print(f"[SAMPass] Image: {index} of {total}.")

    def sam_thread_finished(self):
        print("[SAMPass] SAM thread finished")
        self.sam_worker = None
        self.sam_thread = None

    def sam_finished(self):
        print("[SAMPass] SAM pass finished.")

    def sam_failed(self, error):
        QMessageBox.critical(self, "SAM Error", error)

# ------------------------------------------------------------------------------

class SAMPredict(QWidget):
    prediction = Signal(object, object, object)

    def __init__(self, parents):
        super().__init__()
        self.parents = parents

        self.project = Path(INSTALL_LOCATION)
        self.current_image = Path(INSTALL_LOCATION)

        self.model  = Path(SAM_PATH) / "checkpoints" / "sam2.1_hiera_tiny.pt"
        self.config = Path(SAM_PATH) / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_t.yaml"

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.outdir = Path(INSTALL_LOCATION)

        self.sam_worker: Optional[SAMWorker]

    def analyze_point(self, px, py, box, image, label, prj):
        self.current_image = image
        self.project = Path(prj)
        self.outdir = prj / "sam_isolated_objects"

        self.start_sam_thread(image, px, py, box, "point", label)

    def start_sam_thread(self, image, px, py, box, ltype, label):
        self.sam_thread = QThread()
        self.sam_worker = SAMWorker(
            self.model,
            self.config,
            self.device,
            image,
            self.project,
            self.outdir
        )

        self.sam_worker.moveToThread(self.sam_thread)

        if ltype == "point":
            if px is None or py is None:
                return
            self.sam_thread.started.connect(lambda checked=False, pxx=px, pyy=py, img=image: self.sam_worker.run_point(pxx, pyy, img, label) if self.sam_worker is not None else None)
        elif ltype == "box":
            if len(box) < 4:
                return
            self.sam_thread.started.connect(lambda checked=False, boxx=box, img=image: self.sam_worker.run_box(boxx, img) if self.sam_worker is not None else None)

        self.sam_worker.status.connect(print)

        self.sam_worker.prediction.connect(lambda prediction, pxx=px, pyy=py: self.prediction.emit(prediction, pxx, pyy))

        self.sam_worker.finished.connect(self.sam_finished)
        self.sam_worker.failed.connect(self.sam_failed)

        self.sam_worker.finished.connect(self.sam_thread.quit)
        self.sam_worker.failed.connect(self.sam_thread.quit)

        self.sam_thread.finished.connect(self.sam_worker.deleteLater)
        self.sam_thread.finished.connect(self.sam_thread.deleteLater)

        self.sam_thread.finished.connect(self.sam_thread_finished)

        self.sam_thread.start()

    def sam_finished(self):
        print("[SAMPredict] SAM predict finished.")

    def sam_thread_finished(self):
        print("[SAMPredict] SAM thread finished")
        self.sam_worker = None
        self.sam_thread = None
        self.current_image = Path(INSTALL_LOCATION)

    def sam_failed(self, error):
        QMessageBox.critical(self, "SAM Error", error)
