from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QPushButton, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer, QPoint, QEvent
from PySide6.QtGui import QPainter, QPixmap, QIcon, QFont, QKeyEvent
from pathlib import Path
import shutil

from labelling_controls import ImageLabellingControls

INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class ImageView(QWidget):
    def __init__(self, side_view, parents, controller):
        super().__init__()
        self.controller = controller
        self.parents = parents
        self.side_view = side_view

        self.project = ""
        self.images = []
        self.species = []
        self.image_label_file = ""
        self.default_class = "none"

        main_layout = QHBoxLayout(self)

        # Fonts
        self.pt32 = QFont()
        self.pt16 = QFont()
        self.pt8 = QFont()
        self.pt32.setPointSize(32)
        self.pt16.setPointSize(16)
        self.pt8.setPointSize(8)

        ### Image stuff

        imglayout = QVBoxLayout()
        belowimglayout = QHBoxLayout()
        imglayout.addLayout(belowimglayout)
        imglayout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(imglayout, 5)

        # Back button
        if self.side_view:
            self.back_button = QPushButton("Back")
            self.back_button.clicked.connect(lambda: self.controller.switch_page(2))
            self.back_button.clicked.connect(lambda: self.controller.home.update_image_page)
        else:
            self.back_button = QPushButton("Menu")
            self.back_button.clicked.connect(self.parents.menu_dialog.show)
        self.back_button.setFixedHeight(40)
        self.back_button.setFixedWidth(120)

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
        belowimglayout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        belowimglayout.addWidget(self.img_index_lbl, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)

        # first pass
        if not self.side_view:
            # Show autoskip status
            self.autoskip_lbl = QLabel("Autoskip: True")
            belowimglayout.addWidget(self.autoskip_lbl, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

            self.mark_status = QLabel()
            self.mark_status.setFixedSize(50, 50)
            self.mark_status.setStyleSheet(
                "background-color: gray; border: 1px solid black;"
            )
            belowimglayout.addWidget(self.mark_status, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

            self.image_name = QLabel("parent/child.jpg")
            belowimglayout.addWidget(self.image_name, alignment=Qt.AlignmentFlag.AlignRight)

        # annotating
        else:
            self.img_labelling_controls = ImageLabellingControls(self, self.image_label)

            self.image_name = self.img_labelling_controls.image_name
            self.box_label_1 = self.img_labelling_controls.box_label_1
            self.box_label_2 = self.img_labelling_controls.box_label_2
            self.mouse_pos_label = self.img_labelling_controls.mouse_pos_label
            self.scroll_boxes = self.img_labelling_controls.scroll_boxes
            self.change_default_class_btn = self.img_labelling_controls.change_default_class_btn
            self.show_all_boxes_btn = self.img_labelling_controls.show_all_boxes_btn

            ### Right-side UI - Only add to layout if side_view is True
            right_layout = QVBoxLayout()
            main_layout.addLayout(right_layout, 1)

                # Add to layout
            right_layout.addWidget(self.image_name, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_2, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.mouse_pos_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.scroll_boxes, stretch=1)
            right_layout.addWidget(self.change_default_class_btn)
            right_layout.addWidget(self.show_all_boxes_btn, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter))

    def view_image(self, img, prj, img_list):
        self.current_image = Path(img)
        self.images = img_list
        self.img_index = img_list.index(Path(self.current_image))
        self.project = prj

        self.orig_pixmap = QPixmap(str(self.current_image))

        self.image_name.setText(f"{self.current_image.parent.name}/{self.current_image.name}")

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
        self.image_label.clear()

        if self.side_view:
            self.img_labelling_controls.load_saved_boxes(self.image_label_file)

        QTimer.singleShot(0, self.update_image)  # Update image after the widget is shown   

    def update_image(self):
        if not hasattr(self, "orig_pixmap") or self.orig_pixmap.isNull():
            print("No valid pixmap")
            return

        available_size = self.image_scroll_area.viewport().size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            QTimer.singleShot(50, self.update_image) # retry
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

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.update_image)  # Update image after the widget is shown

    def set_mark_status(self, status):
        if status == "delete":
            self.mark_status.setStyleSheet(
                "background-color: red; border: 1px solid black;"
            )
        elif status == "save":
            self.mark_status.setStyleSheet(
                "background-color: green; border: 1px solid black;"
            )
        else:
            self.mark_status.setStyleSheet(
                "background-color: gray; border: 1px solid black;"
            )

class FirstPass(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("First Pass")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Fonts
        self.pt32b = QFont()
        self.pt32b.setBold(True)
        self.pt32b.setPointSize(32)

        self.controls_dialog = QLabel(
            """
            Comma( , )  - Mark to delete
            Period( . ) - Mark to save
            Z           - Previous Frame / Back
            X           - Next Frame / Skip

            C Key       - Toggle auto skip to next Frame on Left/Right Key press(Default: True)
            V Key       - Show this information box again

            Enter Key   - Mark all remaining frames / Confirm Selection(Opens dialog box before deletion)
            Escape Key  - Open Menu: Remove Frame's Entire Video, Save for later and Exit
            """
        )

        self.ctrls = QMessageBox()
        self.ctrls.setWindowTitle("How to do a First Pass")
        self.ctrls.setText(f"""
            After uploading a video, it converts itself to individual frames. It is useful to run a 'First Pass' by quickly going through all frames and selecting frames for deletion(e.g. if the frame has no objects in it).

            The controls are as follows:
            {self.controls_dialog.text()}

            Press the Escape Key for exit options, or press "Enter" when there are 0 unmarked frames remaining.
            """
        )
        self.ctrls.setStyleSheet("QLabel { min-width: 750px; min-height: 150px; }")

        self.menu_dialog = QWidget(self, Qt.WindowType.Dialog)
        screen = QApplication.primaryScreen().availableGeometry()
        self.menu_dialog.resize(int(screen.width() * 0.5), int(screen.height() * 0.5))
        self.menu_dialog.move(screen.center() - self.menu_dialog.rect().center())
        self.menu_layout = QVBoxLayout()
        self.menu_dialog.setLayout(self.menu_layout)
        self.menu_text = QLabel("First Pass Menu")
        self.menu_text.setFont(self.pt32b)
        self.cancel_vid_btn = QPushButton("Remove Video From Project")
        self.cancel_vid_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.discard_quit_btn = QPushButton("Discard choices and Exit")
        self.discard_quit_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.save_later_btn = QPushButton("Delete selected and Exit")
        self.save_later_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cancel_vid_btn.clicked.connect(lambda _: self.cancel_this_video())
        self.save_later_btn.clicked.connect(lambda _: self.save_and_quit())
        self.discard_quit_btn.clicked.connect(lambda _: self.discard_and_quit())

        self.menu_layout.addWidget(self.menu_text, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.cancel_vid_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.save_later_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.discard_quit_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))

        # dont show the menu until the menu button is pressed(Esc)
        self.menu_dialog.hide()

        # Reuse imageview without the side view
        self.image_view = ImageView(False, self, self.controller)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.image_view, stretch=1)
        self.setLayout(self.main_layout)

        # UI
        self.imgs_remaining_lbl = QLabel("Unmarked frames: 0")
        self.main_layout.addWidget(self.imgs_remaining_lbl, alignment=(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom))

        # Internal info
        self.current_project = Path(INSTALL_LOCATION)
        self.current_video = Path(INSTALL_LOCATION)
        self.current_uuid = ""
        self.current_user = ""
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

        elif event.key() == Qt.Key.Key_Period:
            self.mark_save(self.current_img_index)

        elif event.key() == Qt.Key.Key_Comma:
            self.mark_delete(self.current_img_index)

        elif event.key() == Qt.Key.Key_X:
            self.next_img()
        
        elif event.key() == Qt.Key.Key_Z:
            self.prev_img()

        elif event.key() == Qt.Key.Key_C:
            self.auto_skip = not self.auto_skip
            self.image_view.autoskip_lbl.setText(f"Autoskip: {self.auto_skip}")

        elif event.key() == Qt.Key.Key_V:
            self.display_controls()

        elif event.key() == Qt.Key.Key_Return:
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

    def display_controls(self):
        self.ctrls.exec()

    def begin_pass(self, needs_fp, prj, user, uuid):
        self.current_user = user
        self.current_uuid = uuid

        self.setFocus()
        self.activateWindow()
        self.needs_fp_file = Path(prj) / "needs_first_pass.txt"
        if len(needs_fp) == 0:
            self.controller.switch_page(2)
            return
        self.all_input_imgs = needs_fp.copy()
        self.unmarked_imgs = needs_fp.copy()
        self.imgs_remaining_lbl.setText(f"Unmarked frames: {len(self.unmarked_imgs)}")
        self.current_project = prj

        self.ctrls.exec()

        self.show_img(0)

    def mark_all(self, remaining_imgs, option):
        if option == "delete":
            self.marked_del.extend(remaining_imgs)
        else:
            self.marked_save.extend(remaining_imgs)
        self.unmarked_imgs.clear()
        self.update_ui()

    def mark_delete(self, img_idx):
        img = self.all_input_imgs[img_idx]
        if img in self.marked_save:
            self.marked_save.remove(img)
        if img not in self.marked_del:
            self.marked_del.append(img)
        if img in self.unmarked_imgs:
            self.unmarked_imgs.remove(img)

        if len(self.unmarked_imgs) > 0 and self.auto_skip and self.current_img_index < (len(self.all_input_imgs) - 1):
            self.show_img(self.current_img_index + 1)
        else:
            self.show_img(self.current_img_index)

        self.update_ui()            

    def mark_save(self, img_idx):
        img = self.all_input_imgs[img_idx]
        if img in self.marked_del:
            self.marked_del.remove(img)
        if img not in self.marked_save:
            self.marked_save.append(img)
        if img in self.unmarked_imgs:
            self.unmarked_imgs.remove(img)

        self.image_view.set_mark_status("save")

        if len(self.unmarked_imgs) > 0 and self.auto_skip and self.current_img_index < (len(self.all_input_imgs) - 1):
            self.show_img(self.current_img_index + 1)
        else:
            self.show_img(self.current_img_index)
        self.update_ui()
    
    def show_img(self, index):
        self.current_img_index = index
        img = self.all_input_imgs[index]

        if img in self.marked_del:
            self.image_view.set_mark_status("delete")
        elif img in self.marked_save:
            self.image_view.set_mark_status("save")
        else:
            self.image_view.set_mark_status(None)

        self.image_view.view_image(img, self.current_project, self.all_input_imgs)

    def next_img(self):
        if self.current_img_index < (len(self.all_input_imgs) - 1):
            self.show_img(self.current_img_index + 1)
        self.update_ui()

    def prev_img(self):
        if self.current_img_index >= 1:
            self.show_img(self.current_img_index - 1)
        self.update_ui()

    def cancel_this_video(self):
        reply = QMessageBox.question(
            self,
            "Remove Video from Project",
            f"Are you sure you want to remove video '{self.current_video.name}' from the project, which will also remove all of its image frames? Any labels existing for any of these frames will be lost!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Get all images from the current video
            video_imgs = [img for img in self.all_input_imgs if img.parent == self.current_video]
            
            # Remove from all tracking lists
            self.delete_video(video_imgs)

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
            self.return_to_project()

    def update_ui(self):
        self.current_video = self.all_input_imgs[self.current_img_index].parent
        if len(self.unmarked_imgs) > 0:
            self.imgs_remaining_lbl.setText(f"Unmarked frames: {len(self.unmarked_imgs)}")
        else:
            self.imgs_remaining_lbl.setText(f"All frames marked! Press Enter to confirm selection.")

    def save_and_quit(self):
        reply = QMessageBox.question(
            self,
            "Delete and Quit",
            f"Are you sure you want to remove these frames from the project? They will be gone forever unless the whole video is reuploaded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_frames()
            self.return_to_project()

    def finish_and_delete(self):
        for_deletion_str = "\n".join([str(img) for img in self.marked_del])
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete and Finish")
        msg.setText("Are you sure you want to remove the marked for deletion frames from the project?")
        msg.setInformativeText(
            "These images will be gone unless the video is reuploaded."
        )
        msg.setDetailedText(for_deletion_str)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)

        reply = msg.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete frames from project and remove from self lists
            self.delete_frames()
            self.return_to_project()

    def delete_video(self, video_frames):
        lines = self.needs_fp_file.read_text().strip().splitlines()
        video_paths = {
            Path(img).resolve().relative_to(self.current_project.resolve()).as_posix()
            for img in video_frames
        }

        lines = [
            line for line in lines
            if Path(line).as_posix() not in video_paths
        ]
        
        # Delete the video directory
        try:
            shutil.rmtree(self.current_video)
        except OSError:
            pass

    def delete_frames(self):
        lines = self.needs_fp_file.read_text().strip().splitlines()

        marked = self.marked_del + self.marked_save

        marked_paths = {
            Path(img).resolve().relative_to(self.current_project.resolve()).as_posix()
            for img in marked
        }

        lines = [
            line for line in lines
            if Path(line).as_posix() not in marked_paths
        ]

        self.needs_fp_file.write_text("\n".join(lines))

        for img in self.marked_del:
            img.unlink(missing_ok=True)

            if img in self.all_input_imgs:
                self.all_input_imgs.remove(img)
            if img in self.unmarked_imgs:
                self.unmarked_imgs.remove(img)
            if img in self.marked_save:
                self.marked_save.remove(img)
        self.marked_del.clear()

    def return_to_project(self):
        if self.all_input_imgs:
            self.all_input_imgs.clear()
        if self.unmarked_imgs:
            self.unmarked_imgs.clear()
        if self.marked_del:
            self.marked_del.clear()
        if self.marked_save:
            self.marked_save.clear()

        self.controller.switch_page(2)
        self.controller.home.load_saved_images(self.current_project, self.current_user, self.current_uuid)


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