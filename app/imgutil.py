from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QPushButton, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QPixmap, QIcon, QFont, QKeyEvent
from pathlib import Path
import shutil

from labelling_controls import ImageLabellingControls

INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class ImageView(QWidget):
    def __init__(self, side_view, controller):
        super().__init__()
        self.controller = controller
        self.side_view = side_view

        self.project = ""
        self.images = []
        self.species = []
        self.image_label_file = ""
        self.default_class = "none"

        main_layout = QHBoxLayout(self)

        # Fonts
        self.pt16 = QFont()
        self.pt8 = QFont()
        self.pt16.setPointSize(16)
        self.pt8.setPointSize(8)

        ### Image stuff

        imglayout = QVBoxLayout()
        imglayout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(imglayout)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.setFixedHeight(40)
        self.back_button.setFixedWidth(120)
        self.back_button.clicked.connect(lambda: self.controller.switch_page(2))
        self.back_button.clicked.connect(lambda: self.controller.home.update_image_page)

        # Image index
        self.img_index = 0
        self.img_index_lbl = QLabel("Image: 0/0")
        self.img_index_lbl.setFont(self.pt8)

        # Image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(QSize(10, 10))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.image_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_scroll_area.setMinimumSize(QSize(120, 120))

        imglayout.addWidget(self.image_scroll_area, stretch=1)
        imglayout.addWidget(self.back_button)
        imglayout.addWidget(self.img_index_lbl)

        # Always create labelling controls and UI widgets (for both side_view True and False)
        self.img_labelling_controls = ImageLabellingControls(self, self.image_label)

        self.image_name = self.img_labelling_controls.image_name
        self.box_label_1 = self.img_labelling_controls.box_label_1
        self.box_label_2 = self.img_labelling_controls.box_label_2
        self.mouse_pos_label = self.img_labelling_controls.mouse_pos_label
        self.scroll_boxes = self.img_labelling_controls.scroll_boxes
        self.change_default_class_btn = self.img_labelling_controls.change_default_class_btn
        self.show_all_boxes_btn = self.img_labelling_controls.show_all_boxes_btn

        if self.side_view:
            ### Right-side UI - Only add to layout if side_view is True
            right_layout = QVBoxLayout()
            main_layout.addLayout(right_layout)

                # Add to layout
            right_layout.addWidget(self.image_name, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_2, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.mouse_pos_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.scroll_boxes, stretch=1)
            right_layout.addWidget(self.change_default_class_btn)
            right_layout.addWidget(self.show_all_boxes_btn, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter))

    def view_image(self, img, prj, img_list):
        self.images = img_list
        self.img_index = img_list.index(img)
        self.image_name.setText(f"{img.parent.name}/{img.name}")
        self.orig_pixmap = QPixmap(str(img))
        self.project = prj

        # Sync with img_labelling_controls
        if self.side_view:
            self.species = self.controller.home.project_classes
            self.img_labelling_controls.species = self.species
            self.img_labelling_controls.project = self.project
        
            label_folder = prj / "image_labels"
            if img.parent.name != "image_uploads":
                label_folder /= img.parent.name
            self.image_label_file = label_folder / f"{img.stem}.txt"
            self.image_label_file.parent.mkdir(parents=True, exist_ok=True)
            self.image_label_file.touch()
            self.img_index_lbl.setText(f"Image: {self.img_index + 1}/{len(self.images)}")
            self.image_label.setPixmap(self.orig_pixmap)
            self.update_image()
            self.img_labelling_controls.load_saved_boxes(self.image_label_file)
        else:
            # For FirstPass mode (no side_view), just display the image
            self.image_label.setPixmap(self.orig_pixmap)
            self.update_image()

    def update_image(self):
        if not hasattr(self, "orig_pixmap") or self.orig_pixmap.isNull():
            return

        available_size = self.image_scroll_area.viewport().size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return

        pixmap = self.orig_pixmap.scaled(
            available_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(pixmap.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "orig_pixmap"):
            self.update_image()

class FirstPass(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("First Pass")

        self.controls_dialog = QLabel(
            """
            Left Key    - Mark to delete
            Right Key   - Mark to save
            Spacebar    - Next Frame / Skip
            Shift Key   - Previous Frame / Back

            X Key       - Toggle auto skip to next Frame on Left/Right Key press(Default: True)
            C Key       - Hold to display these controls

            Enter Key   - Mark all remaining frames / Confirm Selection(Opens dialog box before deletion)
            Escape Key  - Open Menu: Remove Frame's Entire Video, Save for later and Exit
            """
        )

        self.menu_dialog = QWidget(self, Qt.WindowType.Dialog)
        screen = QApplication.primaryScreen().availableGeometry()
        self.menu_dialog.resize(int(screen.width() * 0.5), int(screen.height() * 0.5))
        self.menu_dialog.move(screen.center() - self.menu_dialog.rect().center())
        self.menu_layout = QVBoxLayout()
        self.menu_dialog.setLayout(self.menu_layout)
        self.menu_text = QLabel("First Pass Menu")
        self.cancel_vid_btn = QPushButton("Remove Video From Project")
        self.discard_quit_btn = QPushButton("Discard choices and Exit")
        self.save_later_btn = QPushButton("Delete selected and Exit")
        self.cancel_vid_btn.clicked.connect(lambda _: self.cancel_this_video())
        self.save_later_btn.clicked.connect(lambda _: self.save_and_quit())

        self.menu_layout.addWidget(self.menu_text, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.cancel_vid_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.save_later_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))

        # Reuse imageview without the side view
        self.image_view = ImageView(False, self.controller)

        # UI
        self.imgs_remaining_lbl = QLabel("Unmarked frames: 0")

        # Internal info
        self.current_project = Path(INSTALL_LOCATION)
        self.current_video = Path(INSTALL_LOCATION)
        self.all_input_imgs = []
        self.unmarked_imgs = []
        self.marked_del = []
        self.marked_save = []
        self.current_img_index = 0
        self.auto_skip = True
        self.needs_fp_file = Path(INSTALL_LOCATION)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.menu_dialog.show()

        elif event.key() == Qt.Key.Key_Right:
            pass

        elif event.key() == Qt.Key.Key_Left:
            pass

        elif event.key() == Qt.Key.Key_Enter:
            if len(self.unmarked_imgs) > 0:
                unmarked_str = "\n".join([str(frame.name) for frame in self.unmarked_imgs])
                msg = QMessageBox(self)
                msg.setWindowTitle("Notice")
                msg.setText("The following frames have not been marked yet.")
                msg.setInformativeText(
                    "Please go back and mark them or choose from one of the following other options:"
                )
                msg.setDetailedText(unmarked_str)
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                delete_button = msg.addButton("Mark frames for Deletion", QMessageBox.ButtonRole.ActionRole)
                save_button   = msg.addButton("Mark frames for Saving", QMessageBox.ButtonRole.ActionRole)
                msg.setDefaultButton(QMessageBox.StandardButton.Ok)
                msg.exec()

                if msg.clickedButton() == delete_button:
                    self.mark_all(self.unmarked_imgs, "delete")
                elif msg.clickedButton() == save_button:
                    self.mark_all(self.unmarked_imgs, "save")

            else:
                self.finish_and_delete()

    def begin_pass(self, needs_fp, prj):
        self.needs_fp_file = Path(prj) / "needs_first_pass.txt"
        if len(needs_fp) == 0:
            self.controller.switch_page(2)
            return
        self.all_input_imgs = needs_fp
        self.unmarked_imgs = needs_fp
        self.imgs_remaining_lbl.setText(f"Unmarked frames: {len(self.unmarked_imgs)}")
        self.current_project = prj

        QMessageBox.information(
            self,
            "How to do a First Pass",
            f"""
            After uploading a video, it converts itself to individual frames. It is useful to run a 'First Pass' by quickly going through all frames and selecting frames for deletion(e.g. if the frame has no objects in it).

            The controls are as follows:

            {self.controls_dialog.text()}

            Pres the Escape Key for exit options, or press "Enter" when there are 0 unmarked frames remaining.
            """
        )

        print(self.all_input_imgs[0])
        self.image_view.view_image(Path(self.all_input_imgs[0]), self.current_project, self.all_input_imgs)

    def mark_all(self, remaining_imgs, option):
        if option == "delete":
            self.marked_del.extend(remaining_imgs)
        else:
            self.marked_save.extend(remaining_imgs)
        self.update_ui()

    def mark_delete(self, img):
        self.marked_del.append(img)
        self.unmarked_imgs.remove(img)
        try:
            if len(self.unmarked_imgs) > 0 and self.auto_skip:
                self.image_view.view_image(Path(self.all_input_imgs[self.current_img_index + 1]), self.current_project, self.all_input_imgs)
        except IndexError:
            pass
        self.update_ui()            

    def mark_save(self, img):
        self.marked_save.append(img)
        self.unmarked_imgs.remove(img)
        try:
            if len(self.unmarked_imgs) > 0 and self.auto_skip:
                self.image_view.view_image(Path(self.all_input_imgs[self.current_img_index + 1]), self.current_project, self.all_input_imgs)
        except IndexError:
            pass
        self.update_ui()

    def next_img(self):
        try:
            self.image_view.view_image(Path(self.all_input_imgs[self.current_img_index + 1]), self.current_project, self.all_input_imgs)
            self.update_ui()
        except IndexError:
            pass
        self.update_ui()

    def prev_img(self):
        if self.current_img_index >= 1:
            self.image_view.view_image(Path(self.all_input_imgs[self.current_img_index - 1]), self.current_project, self.all_input_imgs)
        self.update_ui()

    def cancel_this_video(self):
        reply = QMessageBox.question(
            self,
            "Remove Video from Project",
            f"Are you sure you want to remove video '{self.current_video.name}' from the project, which will also remove all of its image Frames? All labels will be lost!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Get all images from the current video
            video_imgs = [img for img in self.all_input_imgs if img.parent == self.current_video]
            
            # Remove from all tracking lists
            self.delete_frames(video_imgs)
            
            # Delete the video directory
            try:
                shutil.rmtree(self.current_video)
            except OSError:
                pass
        
        self.update_ui()

    def discard_and_quit(self):
        reply = QMessageBox.question(
            self,
            "Discard Changes and Quit",
            f"Are you sure you want to exit without deleting? Your choices will be reset!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            pass

    def save_and_quit(self):
        reply = QMessageBox.question(
            self,
            "Delete and Quit",
            f"Are you sure you want to remove these frames from the project? They will be gone forever unless the whole video is reuploaded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_frames(self.marked_del)

    def update_ui(self):
        self.current_video = self.all_input_imgs[self.current_img_index].parent
        if len(self.unmarked_imgs) > 0:
            self.imgs_remaining_lbl.setText(f"Unmarked frames: {len(self.unmarked_imgs)}")
        else:
            self.imgs_remaining_lbl.setText(f"All frames marked! Press Enter to confirm selection.")

    def finish_and_delete(self):
        reply = QMessageBox.question(
            self,
            "Delete and Finish",
            f"Are you sure you want to remove the marked for deletion frames from the project? They will be gone forever unless the whole video is reuploaded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_frames(self.marked_del)

    def delete_frames(self, to_be_deleted):
        for img in to_be_deleted:
            if img in self.all_input_imgs:
                self.all_input_imgs.remove(img)
            if img in self.unmarked_imgs:
                self.unmarked_imgs.remove(img)
            if img in self.marked_del:
                self.marked_del.remove(img)
            if img in self.marked_save:
                self.marked_save.remove(img)
            if img in self.needs_fp_file.read_text().strip().splitlines():
                # Remove from needs_first_pass.txt
                lines = self.needs_fp_file.read_text().strip().splitlines()
                lines.remove(str(img))
                self.needs_fp_file.write_text("\n".join(lines))

        # Navigate to next image or go back
        if len(self.all_input_imgs) > 0:
            self.current_img_index = 0
            self.image_view.view_image(Path(self.all_input_imgs[0]), self.current_project, self.all_input_imgs)
        else:
            self.controller.switch_page(2)
            self.controller.home.show_images()

    # stop forced exit with warning
    def closeEvent(self, event):
        # update the needs_first_pass.txt file just in case
        self.needs_fp_file.write_text("\n".join([str(img) for img in self.all_input_imgs]))

        if len(self.marked_del) > 0 or len(self.marked_save) > 0:
            reply = QMessageBox.question(
                self,
                "Exit First Pass",
                f"You have marked frames for deletion or saving. Are you sure you want to exit? Your choices will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()