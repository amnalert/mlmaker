from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QMessageBox, QScrollArea, QComboBox, QInputDialog, QDialog
from PySide6.QtCore import Qt, QPoint, QEvent, QRectF, QDir, Slot
from PySide6.QtGui import QKeySequence, QBrush, QPainter, QPolygonF, QPixmap, QFont, QKeyEvent, QPen, QColor, QPalette, QImageReader, QGuiApplication, QColorSpace, QAction, QImageWriter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from pathlib import Path
import shutil, json

INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class ImageContainer(QWidget):
    def __init__(self, annotating, parents, controller):
        super().__init__()

        self.controller = controller
        self.parents = parents # should be the ProjectView object
        self.annotating = annotating

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

        imglayout = QVBoxLayout()
        belowimglayout = QHBoxLayout()

        imglayout.addLayout(belowimglayout)
        imglayout.setContentsMargins(10, 10, 10, 10)

        main_layout.addLayout(imglayout, 5)

        if self.annotating:
            self.back_button = QPushButton("Back")
            self.back_button.clicked.connect(lambda: (self.controller.switch_page(2), self.parents.load_saved_images(self.project, self.parents.username, self.parents.user_folder, self.parents.uuid)))
        else:
            self.back_button = QPushButton("Menu")
            self.back_button.clicked.connect(self.parents.menu_dialog.show)

        self.back_button.setFixedHeight(40)
        self.back_button.setFixedWidth(120)
        belowimglayout.addWidget(self.back_button, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft))

        self.img_index = 0
        self.img_index_lbl = QLabel("Image: 0/0")
        self.img_index_lbl.setFont(self.pt8)
        belowimglayout.addWidget(self.img_index_lbl, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter))

        self.image_viewer = ImageViewer(self)
        imglayout.addWidget(self.image_viewer, stretch=1)

        self.image_label = self.image_viewer.image_label
        self.image_scroll_area = self.image_viewer.scroll_area

        if not self.annotating:
            self.autoskip_lbl = QLabel("Autoskip: True")
            belowimglayout.addWidget(self.autoskip_lbl, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight))

            self.mark_status = QLabel()
            self.mark_status.setFixedSize(50, 50)

            self.mark_status.setStyleSheet("background-color: gray; border: 1px solid black;")
            belowimglayout.addWidget(self.mark_status, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight))

            self.image_name = QLabel("parent/child.jpg")
            belowimglayout.addWidget(self.image_name, alignment=Qt.AlignmentFlag.AlignRight)

        else:
            self.img_labelling_controls = ImageLabellingControls(self.image_viewer.image_label, self.image_viewer, self)
            self.img_labelling_controls.setObjectName("image_annotation_overlay")
            self.img_labelling_controls.setGeometry(0, 0, self.image_viewer.image_label.width(), self.image_viewer.image_label.height())
            self.img_labelling_controls.raise_()
            self.img_labelling_controls.show()

            # References to annotation controls
            self.image_name = self.img_labelling_controls.image_name
            self.box_label_1 = self.img_labelling_controls.box_label_1
            self.box_label_2 = self.img_labelling_controls.box_label_2
            self.mouse_pos_label = self.img_labelling_controls.mouse_pos_label
            self.scroll_boxes = self.img_labelling_controls.scroll_boxes
            self.change_default_class_btn = self.img_labelling_controls.change_default_class_btn
            self.show_all_boxes_btn = self.img_labelling_controls.show_all_boxes_btn

            self.annotation_type = self.img_labelling_controls.annotation_type
            self.annotation_type_label = self.img_labelling_controls.annotation_type_label
            self.change_annotation_type = self.img_labelling_controls.change_annotation_type

            right_layout = QVBoxLayout()
            main_layout.addLayout(right_layout, 1)

            right_layout.addWidget(self.image_name, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.box_label_2, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.mouse_pos_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.scroll_boxes, stretch=1)
            right_layout.addWidget(self.change_default_class_btn)
            right_layout.addWidget(self.show_all_boxes_btn, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter))
            right_layout.addWidget(self.annotation_type_label, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight))
            right_layout.addWidget(self.change_annotation_type, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight))

    def view_image(self, img, prj, img_list):

        self.current_image = Path(img)
        self.images = img_list

        self.img_index = img_list.index(
            Path(self.current_image)
        )

        self.project = prj

        self.image_name.setText(
            f"{self.current_image.parent.name}/"
            f"{self.current_image.name}"
        )

        if self.annotating:

            self.species = self.controller.home.project_classes
            self.img_labelling_controls.species = self.species
            self.img_labelling_controls.project = self.project

            label_folder = prj / "image_labels"
            if img.parent.name != "image_uploads":
                label_folder /= img.parent.name

            self.image_label_file = label_folder / f"{img.stem}.txt"
            self.image_label_file.parent.mkdir(parents=True, exist_ok=True)
            self.image_label_file.touch()

        self.img_index_lbl.setText(
            f"Image: {self.img_index + 1}/{len(self.images)}"
        )

        self.image_viewer.load_file(
            str(self.current_image)
        )

        if self.annotating:
            self.img_labelling_controls.load_saved_boxes(
                self.image_label_file
            )

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

        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

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

        self.ctrls.setWindowTitle(
            "How to do a First Pass"
        )

        self.ctrls.setText(
            f"""
            After uploading a video, it converts itself to individual frames. It is useful to run a 'First Pass' by quickly going through all frames and selecting frames for deletion(e.g. if the frame has no objects in it).

            The controls are as follows:
            {self.controls_dialog.text()}

            Press the Escape Key for exit options, or press "Enter" when there are 0 unmarked frames remaining.
            """
        )

        self.ctrls.setStyleSheet(
            "QLabel { min-width: 750px; min-height: 150px; }"
        )

        self.menu_dialog = QWidget(
            self,
            Qt.WindowType.Dialog
        )

        screen = QApplication.primaryScreen().availableGeometry()

        self.menu_dialog.resize(
            int(screen.width() * 0.5),
            int(screen.height() * 0.5)
        )

        self.menu_dialog.move(
            screen.center() -
            self.menu_dialog.rect().center()
        )

        self.menu_layout = QVBoxLayout()

        self.menu_dialog.setLayout(
            self.menu_layout
        )

        self.menu_text = QLabel(
            "First Pass Menu"
        )

        self.menu_text.setFont(
            self.pt32b
        )

        self.cancel_vid_btn = QPushButton(
            "Remove Video From Project"
        )

        self.cancel_vid_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.discard_quit_btn = QPushButton(
            "Discard choices and Exit"
        )

        self.discard_quit_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.save_later_btn = QPushButton(
            "Delete selected and Exit"
        )

        self.save_later_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.cancel_vid_btn.clicked.connect(
            lambda _: self.cancel_this_video()
        )

        self.save_later_btn.clicked.connect(
            lambda _: self.save_and_quit()
        )

        self.discard_quit_btn.clicked.connect(
            lambda _: self.discard_and_quit()
        )

        self.menu_layout.addWidget(
            self.menu_text,
            alignment=(
                Qt.AlignmentFlag.AlignTop |
                Qt.AlignmentFlag.AlignHCenter
            )
        )

        self.menu_layout.addWidget(
            self.cancel_vid_btn,
            alignment=(
                Qt.AlignmentFlag.AlignTop |
                Qt.AlignmentFlag.AlignHCenter
            )
        )

        self.menu_layout.addWidget(
            self.save_later_btn,
            alignment=(
                Qt.AlignmentFlag.AlignTop |
                Qt.AlignmentFlag.AlignHCenter
            )
        )

        self.menu_layout.addWidget(
            self.discard_quit_btn,
            alignment=(
                Qt.AlignmentFlag.AlignTop |
                Qt.AlignmentFlag.AlignHCenter
            )
        )

        self.menu_dialog.hide()

        self.image_view = ImageContainer(
            False,
            self,
            self.controller
        )

        self.main_layout = QVBoxLayout(self)

        self.main_layout.addWidget(
            self.image_view,
            stretch=1
        )

        self.imgs_remaining_lbl = QLabel(
            "Unmarked frames: 0"
        )

        self.main_layout.addWidget(
            self.imgs_remaining_lbl,
            alignment=(
                Qt.AlignmentFlag.AlignRight |
                Qt.AlignmentFlag.AlignBottom
            )
        )

        self.current_project = Path(
            INSTALL_LOCATION
        )

        self.current_video = Path(
            INSTALL_LOCATION
        )

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
                unmarked_str = "\n".join( [ str(frame.name) for frame in self.unmarked_imgs ] )

                msg = QMessageBox(self)
                msg.setWindowTitle("Notice")
                msg.setText("The following frames have not been marked yet.")
                msg.setInformativeText("Please go back and mark them or choose from one of the following other options:")
                msg.setDetailedText(unmarked_str)
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)

                delete_button = msg.addButton("Mark frames for Deletion", QMessageBox.ButtonRole.ActionRole)

                save_button = msg.addButton(
                    "Mark frames for Saving",
                    QMessageBox.ButtonRole.ActionRole
                )

                msg.setDefaultButton(
                    QMessageBox.StandardButton.Ok
                )

                msg.exec()

                if msg.clickedButton() == delete_button:

                    self.mark_all(
                        self.unmarked_imgs,
                        "delete"
                    )

                elif msg.clickedButton() == save_button:

                    self.mark_all(
                        self.unmarked_imgs,
                        "save"
                    )

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

        if (len(self.unmarked_imgs) > 0 and self.auto_skip and self.current_img_index < (len(self.all_input_imgs) - 1)):
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

        if (len(self.unmarked_imgs) > 0 and self.auto_skip and self.current_img_index < (len(self.all_input_imgs) - 1)):
            self.show_img(self.current_img_index + 1)

        else:
            self.show_img(self.current_img_index)

        self.update_ui()

    def show_img(self, index):

        self.current_img_index = index

        img = self.all_input_imgs[index]

        if img in self.marked_del:

            self.image_view.set_mark_status(
                "delete"
            )

        elif img in self.marked_save:

            self.image_view.set_mark_status(
                "save"
            )

        else:

            self.image_view.set_mark_status(
                None
            )

        self.image_view.view_image(
            img,
            self.current_project,
            self.all_input_imgs
        )

    def next_img(self):

        if self.current_img_index < (
            len(self.all_input_imgs) - 1
        ):

            self.show_img(
                self.current_img_index + 1
            )

        self.update_ui()

    def prev_img(self):

        if self.current_img_index >= 1:

            self.show_img(
                self.current_img_index - 1
            )

        self.update_ui()

    def cancel_this_video(self):

        reply = QMessageBox.question(
            self,
            "Remove Video from Project",
            f"Are you sure you want to remove video "
            f"'{self.current_video.name}' from the project, "
            f"which will also remove all of its image frames? "
            f"Any labels existing for any of these frames will be lost!",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:

            video_imgs = [
                img
                for img in self.all_input_imgs
                if img.parent == self.current_video
            ]

            self.delete_video(
                video_imgs
            )

        self.update_ui()

    def discard_and_quit(self):

        reply = QMessageBox.question(
            self,
            "Discard Changes and Quit",
            "Are you sure you want to exit without deleting? "
            "Your choices will be reset!",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:

            self.return_to_project()

    def update_ui(self):

        if not self.all_input_imgs:
            return

        self.current_video = (
            self.all_input_imgs[
                self.current_img_index
            ].parent
        )

        if len(self.unmarked_imgs) > 0:

            self.imgs_remaining_lbl.setText(
                f"Unmarked frames: {len(self.unmarked_imgs)}"
            )

        else:

            self.imgs_remaining_lbl.setText(
                "All frames marked! Press Enter to confirm selection."
            )

    def save_and_quit(self):

        reply = QMessageBox.question(
            self,
            "Delete and Quit",
            "Are you sure you want to remove these frames from the project? They will be gone forever unless the whole video is reuploaded. Frames marked for saving will be saved as well.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.delete_frames()
            self.return_to_project()

    def finish_and_delete(self):

        for_deletion_str = "\n".join( [str(img) for img in self.marked_del] )

        msg = QMessageBox(self)
        msg.setWindowTitle("Delete and Finish")
        msg.setText("Are you sure you want to remove the marked for deletion frames from the project?")
        msg.setInformativeText("These images will be gone unless the video is reuploaded.")
        msg.setDetailedText(for_deletion_str)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_frames()
            self.return_to_project()

    def delete_video(self, video_frames):

        lines = (self.needs_fp_file.read_text().strip().splitlines())

        video_paths = { Path(img).resolve().relative_to(self.current_project.resolve()).as_posix() for img in video_frames }

        lines = [
            line for line in lines if Path(line).as_posix() not in video_paths
        ]

        try:
            shutil.rmtree(self.current_video)
        except OSError:
            pass


    def delete_frames(self):
        lines = (self.needs_fp_file.read_text().strip().splitlines())
        marked = (self.marked_del + self.marked_save)
        marked_paths = { Path(img).resolve().relative_to(self.current_project.resolve()).as_posix() for img in marked }

        lines = [
            line for line in lines if Path(line).as_posix() not in marked_paths
        ]

        self.needs_fp_file.write_text("\n".join(lines))

        image_uploads = self.current_project / "image_uploads"
        image_labels = self.current_project / "image_labels"

        for img in self.marked_del:
            img = Path(img)
            try:
                relative_img = img.resolve().relative_to(image_uploads.resolve())
                label_file = image_labels / relative_img.parent / f"{relative_img.stem}.txt"
                label_file.unlink(missing_ok=True)
            except ValueError:
                pass

            img.unlink(missing_ok=True)
            if img in self.all_input_imgs:
                self.all_input_imgs.remove(img)
            if img in self.unmarked_imgs:
                self.unmarked_imgs.remove(img)

        self.marked_del.clear()

    def return_to_project(self):

        self.all_input_imgs.clear()
        self.unmarked_imgs.clear()
        self.marked_del.clear()
        self.marked_save.clear()

        self.controller.switch_page(2)

        self.controller.home.load_saved_images(self.current_project, self.current_user, self.current_uuid)

    def closeEvent(self, event):
        self.needs_fp_file.write_text("\n".join( [str(img) for img in self.all_input_imgs] ))

        if len(self.marked_del) > 0 or len(self.marked_save) > 0:
            reply = QMessageBox.question(
                self,
                "Exit First Pass",
                "You have marked frames for deletion or saving. Are you sure you want to exit? Your choices will be lost.",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.hide()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

class ImageLabellingControls(QWidget):

    def __init__(self, parent_label, image_viewer, parents):
        super().__init__(parent_label)

        self.image_viewer = image_viewer
        self.parent_label = parent_label
        self.parents = parents

        # Image info
        self.image_label_file = ""
        self.species = []
        self.project = ""

        # Crosshair colors
        self.colors = [Qt.GlobalColor.white,Qt.GlobalColor.red,Qt.GlobalColor.darkRed,Qt.GlobalColor.green,Qt.GlobalColor.darkGreen,Qt.GlobalColor.blue,Qt.GlobalColor.darkBlue,Qt.GlobalColor.cyan,Qt.GlobalColor.darkCyan,Qt.GlobalColor.magenta,Qt.GlobalColor.darkMagenta,Qt.GlobalColor.yellow,Qt.GlobalColor.darkYellow,Qt.GlobalColor.lightGray,Qt.GlobalColor.gray,Qt.GlobalColor.darkGray,Qt.GlobalColor.black,]
        self.color_index = 0

        # Boxes
        self.boxes_lines = []
        self.current_box = [ (-1, -1), (-1, -1) ]
        self.sam_points = [] # At least 3 points are required
        self.default_class = "none"
        self.hovered_box_label = None
        self.showing_all_boxes = False

        # Mouse
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mouse_pos = QPoint(-1, -1)

        # UI
        self.image_name = QLabel()
        self.box_label_1 = QLabel("Point 1: (0, 0)")
        self.box_label_2 = QLabel("Point 2: (0, 0)")
        self.mouse_pos_label = QLabel("Mouse: (0, 0)")

        self.sam_points_label = QLabel(f"Points: {len(self.sam_points)}")
        self.ready_sam = False # first enter key hit -> preview sam label, second enter key hit -> write data

        # Box scroll area
        self.scroll_boxes_content = QWidget()
        self.scroll_boxes_layout = QGridLayout(self.scroll_boxes_content)
        self.scroll_boxes_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_boxes_layout.setSpacing(5)

        self.scroll_boxes = QScrollArea()
        self.scroll_boxes.setWidgetResizable(True)
        self.scroll_boxes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_boxes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_boxes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_boxes.setWidget(self.scroll_boxes_content)

        # Buttons
        self.change_default_class_btn = QPushButton("Change default class")
        self.change_default_class_btn.clicked.connect(self.change_default_class)
        self.show_all_boxes_btn = QPushButton("Show all boxes")
        self.show_all_boxes_btn.clicked.connect(self._draw_all_boxes)

        # Change annotation type: YOLO or SAM
        self.annotation_type = "YOLO"
        self.annotation_type_label = QLabel(f"Label Type: {self.annotation_type}")
        self.change_annotation_type = QPushButton("Switch to SAM Labelling")
        self.change_annotation_type.clicked.connect(self.switch_annot_type)

        # Files
        self.sam_labels_json = Path(INSTALL_LOCATION)

        # Actions
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) # Ctrl + Z
        self.undo_action.triggered.connect(self.undo_label) # Ctrl + Y

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo_label)

        self.tmp_boxes = [] # saved undo boxes, can redo while still on the same image
        self.tmp_sam_points = [] # saved undo points, can redo while that label still being drawn

        self._sync_geometry()

    def switch_annot_type(self):
        self.ready_sam = False
        self.change_annotation_type.setText(f"Switch to {self.annotation_type} Labelling")

        if self.annotation_type == "YOLO":
            self.annotation_type = "SAM"
            self.box_label_1.hide()
            self.box_label_2.hide()
            self.reset_box()

        elif self.annotation_type == "SAM":
            self.annotation_type = "YOLO"
            self.box_label_1.show()
            self.box_label_2.show()
            self.reset_box()

    def _sync_geometry(self):
        if not self.parent_label.isVisible():
            return
        self.setGeometry(0, 0, self.parent_label.width(), self.parent_label.height())
        self.raise_()
        self.update()

    def wheelEvent(self, event):
        if self.image_viewer._panning:
            return
        
        delta = event.angleDelta().y()
        if delta > 0:
            self.image_viewer.zoom_in()
        elif delta < 0:
            self.image_viewer.zoom_out()

        event.accept()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def _get_display_image_rect(self):
        width = self.parent_label.width()
        height = self.parent_label.height()

        if width <= 0 or height <= 0:
            return None

        return (0, 0, width, height)

    def widget_to_image_coords(self, wx, wy):
        """
        Convert coordinates from the annotation overlay to
        original image pixel coordinates.
        """
        image = self.image_viewer.image()
        if image is None or image.isNull():
            return wx, wy

        draw_w = self.parent_label.width()
        draw_h = self.parent_label.height()

        if draw_w <= 0 or draw_h <= 0:
            return wx, wy

        orig_w = image.width()
        orig_h = image.height()

        if orig_w <= 0 or orig_h <= 0:
            return wx, wy

        img_x = int( (wx / draw_w) * orig_w )
        img_y = int( (wy / draw_h) * orig_h )
        img_x = max(0, min(img_x, orig_w - 1))
        img_y = max(0, min(img_y, orig_h - 1))

        return img_x, img_y

    def image_to_widget_coords(self, ix, iy):
        """
        Convert original image pixel coordinates to
        annotation overlay coordinates.
        """
        image = self.image_viewer.image()
        if image is None or image.isNull():
            return ix, iy

        draw_w = self.parent_label.width()
        draw_h = self.parent_label.height()

        orig_w = image.width()
        orig_h = image.height()

        if (draw_w <= 0 or draw_h <= 0 or orig_w <= 0 or orig_h <= 0):
            return ix, iy

        wx = (ix / orig_w) * draw_w
        wy = (iy / orig_h) * draw_h

        return wx, wy

    def keyPressEvent(self, event: QKeyEvent):

        if event.key() == Qt.Key.Key_Escape:
            self.reset_box()
            self.update()

        elif event.key() == Qt.Key.Key_Right:
            self.reset_box()
            try:
                self.parents.controller.home.inspect_img(
                    self.parents.images[
                        self.parents.img_index + 1
                    ]
                )
            except IndexError:
                pass

        elif event.key() == Qt.Key.Key_Left:
            self.reset_box()
            if self.parents.img_index >= 1:
                self.parents.controller.home.inspect_img(
                    self.parents.images[
                        self.parents.img_index - 1
                    ]
                )

        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        current_pos = event.position().toPoint()

        if self.image_viewer._panning:
            self.image_viewer._update_pan(current_pos)
            event.accept()
            return

        self.mouse_pos = current_pos

        img_x, img_y = (
            self.widget_to_image_coords(
                current_pos.x(),
                current_pos.y()
            )
        )

        self.mouse_pos_label.setText(f"Mouse: ({img_x}, {img_y})")

        self.update()
        event.accept()

    def mousePressEvent(self, event):
        pos = event.position().toPoint()

        x = pos.x()
        y = pos.y()

        self.setFocus()

        if event.button() == Qt.MouseButton.MiddleButton:
            self.image_viewer._start_pan(pos)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.color_index = (self.color_index + 1) % len(self.colors)
            self.update()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            img_x, img_y = self.widget_to_image_coords(x, y)
            if self.annotation_type == "YOLO":
                if self.current_box[0] == (-1, -1):
                    self.current_box[0] = (img_x, img_y)

                    self.box_label_1.setText(f"Point 1: ({img_x}, {img_y})")
                    self.box_label_2.setText("Point 2: (0, 0)")

                else:
                    def_class = self.default_class if self.default_class != "none" else self.species[0] if self.species else "none"

                    self.current_box[1] = (img_x, img_y)
                    self.box_label_2.setText(f"Point 2: ({img_x}, {img_y})")

                    self.write_box_data(self.current_box, def_class)
                    self.current_box = [(-1, -1), (-1, -1)]

            elif self.annotation_type == "SAM":
                self.sam_points.append((img_x, img_y))
                self.sam_points_label.setText(f"Points: {len(self.sam_points)}")
                        
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.image_viewer._end_pan()

        event.accept()

    def undo_label(self):
        print("[ImageLabellingControls] Ctrl+Z Received, undoing last action.")

        # remove last sam point
        if self.annotation_type == "SAM":
            self.tmp_sam_points.append(self.sam_points.pop())

        # remove last box drawn
        elif self.annotation_type == "YOLO":
            self.tmp_boxes.append(self.boxes_lines.pop())
            self.delete_label(self.tmp_boxes[-1])

    def redo_label(self):
        print("[ImageLabellingControls] Ctrl+Y(or Ctrl+Shift+Z) Received, redoing last action")

        # replace from tmp_sam_points
        if self.annotation_type == "SAM" and len(self.tmp_sam_points) > 0:
            self.sam_points.append(self.tmp_sam_points.pop())

        # replace from tmp_boxes
        elif self.annotation_type == "YOLO":
            self.boxes_lines.append(self.tmp_boxes.pop())

            def_class = self.default_class if self.default_class != "none" else self.species[0] if self.species else "none"

            self.write_box_data(self.boxes_lines[-1], def_class)

    def clear_tmps(self):
        self.tmp_sam_points.clear()
        self.tmp_boxes.clear()

    def paintEvent(self, event):
        pixmap = self.parent_label.pixmap()
        if not pixmap or pixmap.isNull():
            return

        image_rect = self._get_display_image_rect()
        if image_rect is None:
            return

        x_offset, y_offset, draw_w, draw_h = image_rect

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        mx = self.mouse_pos.x()
        my = self.mouse_pos.y()

        if mx != -1 and my != -1:
            pen = QPen(self.colors[self.color_index], 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            clamped_x = min( max(mx, x_offset), x_offset + draw_w )
            clamped_y = min( max(my, y_offset), y_offset + draw_h )

            painter.drawLine(x_offset, clamped_y, x_offset + draw_w, clamped_y)
            painter.drawLine(clamped_x, y_offset, clamped_x, y_offset + draw_h)

            if self.annotation_type == "YOLO":
                pen.setWidth(2)
                if self.current_box[0] != (-1, -1):

                    p1x_img, p1y_img = self.current_box[0]

                    p1x, p1y = self.image_to_widget_coords(p1x_img, p1y_img)
                    
                    rect_x = min(clamped_x, p1x)
                    rect_y = min(clamped_y, p1y)

                    rect_w = abs(p1x - clamped_x)
                    rect_h = abs(p1y - clamped_y)

                    painter.drawRect(QRectF(rect_x, rect_y, rect_w, rect_h))
            elif self.annotation_type == "SAM":
                pen.setWidth(8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                for point in self.sam_points:
                    px, py = point
                    wx, wy = self.image_to_widget_coords(px, py)
                    painter.drawPoint(wx, wy)
                print(f"Drawing points at {self.sam_points}")

        if self.hovered_box_label is not None:
            if self.annotation_type == "YOLO":
                self._draw_box_from_label(painter, self.hovered_box_label, QColor("#ffd93d"), 3)

        if self.showing_all_boxes:
            if self.annotation_type == "YOLO":
                for box_label in self.boxes_lines:
                    self._draw_box_from_label(painter, box_label, QColor("#00ff00"), 2)

    def _draw_box_from_label(self, painter, label, color, width=2):
        try:
            parts = label.split()
            if len(parts) < 5:
                return

            class_name = parts[0]

            cx = float(parts[1])
            cy = float(parts[2])
            bw = float(parts[3])
            bh = float(parts[4])
        except ValueError:
            return

        pixmap = self.parent_label.pixmap()
        if not pixmap or pixmap.isNull():
            return

        image_rect = self._get_display_image_rect()
        if image_rect is None:
            return

        x_offset, y_offset, draw_w, draw_h = image_rect

        x1 = x_offset + (cx - bw / 2) * draw_w
        y1 = y_offset + (cy - bh / 2) * draw_h
        x2 = x_offset + (cx + bw / 2) * draw_w
        y2 = y_offset + (cy + bh / 2) * draw_h

        rect = QRectF( min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1) )

        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine))
        painter.drawRect(rect)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(int(min(x1, x2)) + 2, int(min(y1, y2)) - 3, class_name)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def _draw_all_boxes(self):
        self.showing_all_boxes = (not self.showing_all_boxes)
        self.update()

    def reset_box(self):
        if self.annotation_type == "YOLO":
            self.current_box = [ (-1, -1), (-1, -1) ]
            self.box_label_1.setText("Point 1: (0, 0)")
            self.box_label_2.setText("Point 2: (0, 0)")
        if self.annotation_type == "SAM":
            self.sam_points.clear()
            self.sam_points_label.setText("Points: 0")
            self.tmp_sam_points.clear()

    def write_box_data(self, label, label_class):
        if self.annotation_type == "YOLO":
            if label[0] == (-1, -1) or label[1] == (-1, -1):
                return

            image = self.image_viewer.image()
            if image is None or image.isNull():
                return

            orig_w = image.width()
            orig_h = image.height()

            x1, y1 = label[0]
            x2, y2 = label[1]

            x1_img = min(x1, x2)
            y1_img = min(y1, y2)

            x2_img = max(x1, x2)
            y2_img = max(y1, y2)

            center_x = (x1_img + x2_img) / 2
            center_y = (y1_img + y2_img) / 2

            width = abs(x2_img - x1_img)
            height = abs(y2_img - y1_img)

            norm_x = center_x / orig_w
            norm_y = center_y / orig_h
            norm_w = width / orig_w
            norm_h = height / orig_h

            with open(self.image_label_file, "a") as f:
                f.write(
                    f"{label_class} "
                    f"{norm_x} "
                    f"{norm_y} "
                    f"{norm_w} "
                    f"{norm_h}\n"
                )

        self.reset_box()
        self.load_saved_boxes(self.image_label_file)

    def load_saved_boxes(self, file):
        self.image_label_file = file
        with open(file, "r") as f:
            self.boxes_lines = [
                line for line in f.read().splitlines() if line
            ]

        self.update_visible_boxes(self.boxes_lines)
        self.update()

    def update_visible_boxes(self, boxes_labels):
        self.boxes_lines = boxes_labels

        while self.scroll_boxes_layout.count():
            item = self.scroll_boxes_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        self.scroll_boxes_layout.setColumnStretch(0, 1)
        self.scroll_boxes_layout.setColumnStretch(1, 1)
        self.scroll_boxes_layout.setHorizontalSpacing(8)
        self.scroll_boxes_layout.setVerticalSpacing(8)

        for idx, box in enumerate(boxes_labels):
            parts = box.split()
            if len(parts) < 5:
                continue

            row = idx // 2
            col = idx % 2

            box_container = QWidget()
            box_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            box_container.setMinimumWidth(160)
            box_container_base_style = (
                "QWidget {"
                "  border: 1px solid #7a7a7a;"
                "  border-radius: 6px;"
                "  background-color: rgba(255, 255, 255, 12);"
                "  padding: 6px;"
                "}"
            )

            box_container.setStyleSheet(box_container_base_style)
            boxinfo_layout = QVBoxLayout(box_container)

            boxinfo_layout.setContentsMargins(4, 4, 4, 4)
            boxinfo_layout.setSpacing(5)

            image = self.image_viewer.image()
            if image is not None and not image.isNull():
                orig_w = image.width()
                orig_h = image.height()

                center_x = float(parts[1]) * orig_w
                center_y = float(parts[2]) * orig_h

                width = float(parts[3]) * orig_w
                height = float(parts[4]) * orig_h

                box_info_text = (
                    f"Box {idx + 1} "
                    f"Class: {parts[0]}\n"
                    f"Center: "
                    f"({round(center_x, 1)}, "
                    f"{round(center_y, 1)})\n"
                    f"Width: {round(width, 1)}\n"
                    f"Height: {round(height, 1)}"
                )

            else:
                box_info_text = (
                    f"Box {idx + 1}\n"
                    f"Class: {parts[0]}"
                )
            box_info = QLabel(box_info_text)

            buttons_layout = QHBoxLayout()
            buttons_layout.setContentsMargins(0, 0, 0, 0)
            buttons_layout.setSpacing(5)

            delete_box_btn = QPushButton("Delete")
            delete_box_btn.setFixedSize(60, 30)
            delete_box_btn.clicked.connect(lambda checked=False, box=box: self.delete_label(box))

            species_list_dropdown = QComboBox()
            species_list_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            species_list_dropdown.addItems(self.species)
            species_list_dropdown.setCurrentText(parts[0])
            species_list_dropdown.currentTextChanged.connect(lambda new_class, box=box: self.change_species_label(box, new_class))

            buttons_layout.addWidget(delete_box_btn)
            buttons_layout.addWidget(species_list_dropdown)
            boxinfo_layout.addWidget(box_info, alignment=Qt.AlignmentFlag.AlignTop)
            boxinfo_layout.addLayout(buttons_layout)

            self.scroll_boxes_layout.addWidget(box_container, row, col, 1, 1, (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft))

            box_container.setProperty("box_label", box)

            box_container.installEventFilter(self)

    def change_default_class(self):

        choice, ok = QInputDialog.getItem(
            self,
            "Choose default class",
            "Select a class new boxes will be assigned from the following:",
            self.species
        )

        if ok and choice:

            self.default_class = choice

    def change_species_label(
        self,
        label,
        new_class
    ):

        if label not in self.boxes_lines:
            return

        parts = label.split()

        parts[0] = new_class

        new_label = " ".join(parts)

        index = self.boxes_lines.index(
            label
        )

        self.boxes_lines[index] = new_label

        with open(
            self.image_label_file,
            "w"
        ) as f:

            for box in self.boxes_lines:

                f.write(
                    f"{box}\n"
                )

        self.load_saved_boxes(
            self.image_label_file
        )

    def delete_label(self, label):
        if self.annotation_type == "YOLO":
            if label in self.boxes_lines:
                self.boxes_lines.remove(label)

            with open(self.image_label_file, "w") as f:
                for box in self.boxes_lines:
                    f.write(f"{box}\n")

            self.load_saved_boxes(self.image_label_file)
        elif self.annotation_type == "SAM":
            return # WIP

    def eventFilter(self, watched, event):

        if watched == self.parent_label:
            if event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Move,
                QEvent.Type.Show,
                QEvent.Type.Paint
            ):

                self._sync_geometry()
                self.update()

        else:
            if isinstance(watched, QWidget):
                box_label = watched.property(
                    "box_label"
                )

                if box_label is not None:

                    if event.type() == QEvent.Type.Enter:

                        self.hovered_box_label = (
                            box_label
                        )

                        watched.setStyleSheet(
                            "QWidget {"
                            "  border: 2px solid #ffd93d;"
                            "  border-radius: 6px;"
                            "  background-color: rgba(255, 217, 61, 24);"
                            "  padding: 6px;"
                            "}"
                        )

                        self.update()

                    elif event.type() == QEvent.Type.Leave:

                        if (
                            self.hovered_box_label
                            == box_label
                        ):

                            self.hovered_box_label = None

                            watched.setStyleSheet(
                                "QWidget {"
                                "  border: 1px solid #7a7a7a;"
                                "  border-radius: 6px;"
                                "  background-color: rgba(255, 255, 255, 12);"
                                "  padding: 6px;"
                                "}"
                            )

                            self.update()

        return super().eventFilter(
            watched,
            event
        )


class ImageViewer(QWidget):

    def __init__(self, parent=None):

        super().__init__(parent)

        self._scale_factor = 1.0
        self._first_file_dialog = True
        self._image = None

        self._image_label = QLabel()

        self._image_label.setBackgroundRole(
            QPalette.ColorRole.Base
        )

        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
        )

        self._image_label.setScaledContents(
            True
        )

        self._image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._image_label.setMouseTracking(
            True
        )

        self._scroll_area = QScrollArea()

        self._scroll_area.setBackgroundRole(
            QPalette.ColorRole.Dark
        )

        self._scroll_area.setWidget(
            self._image_label
        )

        self._scroll_area.setWidgetResizable(
            False
        )

        self._scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.addWidget(
            self._scroll_area
        )

        self._panning = False

        self._pan_start = QPoint()

        self._horizontal_start = 0
        self._vertical_start = 0

        self._create_actions()

    @property
    def image_label(self):
        return self._image_label

    @property
    def scroll_area(self):
        return self._scroll_area

    def image(self):
        """
        Return the currently loaded QImage.

        This fixes the previous:
            AttributeError:
            'ImageViewer' object has no attribute 'image'
        """

        return self._image

    def display_rect(self):

        return self._image_label.geometry()

    def load_file(
        self,
        fileName
    ):

        reader = QImageReader(
            str(fileName)
        )

        reader.setAutoTransform(
            True
        )

        new_image = reader.read()

        native_filename = (
            QDir.toNativeSeparators(
                str(fileName)
            )
        )

        if new_image.isNull():

            error = reader.errorString()

            QMessageBox.information(
                self,
                QGuiApplication.applicationDisplayName(),
                f"Cannot load {native_filename}: {error}"
            )

            return False

        self._set_image(
            new_image
        )

        return True

    def _set_image(
        self,
        new_image
    ):

        self._image = new_image

        if self._image.colorSpace().isValid():

            color_space = QColorSpace(
                QColorSpace.NamedColorSpace.SRgb
            )

            self._image.convertToColorSpace(
                color_space
            )

        pixmap = QPixmap.fromImage(
            self._image
        )

        self._image_label.setPixmap(
            pixmap
        )

        self._scale_factor = 1.0

        self._image_label.setFixedSize(
            pixmap.size()
        )

        self._update_overlay_geometry()

        self._update_actions()

    def _update_overlay_geometry(self):

        overlay = self._image_label.findChild(
            QWidget,
            "image_annotation_overlay"
        )

        if overlay is None:
            return

        overlay.setGeometry(
            0,
            0,
            self._image_label.width(),
            self._image_label.height()
        )

        overlay.raise_()

        overlay.update()

    @Slot()
    def zoom_in(self):

        self._scale_image(
            1.25
        )

    @Slot()
    def zoom_out(self):

        self._scale_image(
            0.8
        )

    _zoom_in = zoom_in
    _zoom_out = zoom_out

    @Slot()
    def _normal_size(self):

        if self._image is None:
            return

        self._scale_factor = 1.0

        pixmap = QPixmap.fromImage(
            self._image
        )

        self._image_label.setFixedSize(
            pixmap.size()
        )

        self._update_overlay_geometry()

        self._update_actions()

    @Slot()
    def _fit_to_window(self):

        if self._image is None:
            return

        fit_to_window = (
            self._fit_to_window_act.isChecked()
        )

        if fit_to_window:

            self._scroll_area.setWidgetResizable(
                True
            )

            self._image_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Ignored
            )

        else:

            self._scroll_area.setWidgetResizable(
                False
            )

            self._image_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Ignored
            )

            self._normal_size()

        self._update_actions()

    def _scale_image(
        self,
        factor
    ):

        if self._image is None:
            return

        old_scale = (
            self._scale_factor
        )

        self._scale_factor *= factor

        self._scale_factor = max(
            0.333,
            min(
                3.0,
                self._scale_factor
            )
        )

        actual_factor = (
            self._scale_factor /
            old_scale
        )

        new_width = int(
            self._image.width() *
            self._scale_factor
        )

        new_height = int(
            self._image.height() *
            self._scale_factor
        )

        hbar = (
            self._scroll_area.horizontalScrollBar()
        )

        vbar = (
            self._scroll_area.verticalScrollBar()
        )

        old_h = hbar.value()
        old_v = vbar.value()

        viewport_center_x = (
            self._scroll_area.viewport().width()
            / 2
        )

        viewport_center_y = (
            self._scroll_area.viewport().height()
            / 2
        )

        image_x = (
            old_h +
            viewport_center_x
        )

        image_y = (
            old_v +
            viewport_center_y
        )

        self._image_label.setFixedSize(
            new_width,
            new_height
        )

        self._update_overlay_geometry()

        new_h = int(
            image_x *
            actual_factor -
            viewport_center_x
        )

        new_v = int(
            image_y *
            actual_factor -
            viewport_center_y
        )

        hbar.setValue(
            new_h
        )

        vbar.setValue(
            new_v
        )

        self._update_actions()

    def _start_pan(
        self,
        position
    ):

        self._panning = True

        self._pan_start = position

        self._horizontal_start = (
            self._scroll_area
            .horizontalScrollBar()
            .value()
        )

        self._vertical_start = (
            self._scroll_area
            .verticalScrollBar()
            .value()
        )

        self._image_label.setCursor(
            Qt.CursorShape.ClosedHandCursor
        )

    def _update_pan(
        self,
        position
    ):

        if not self._panning:
            return

        delta = (
            position -
            self._pan_start
        )

        self._scroll_area.horizontalScrollBar().setValue(
            self._horizontal_start -
            delta.x()
        )

        self._scroll_area.verticalScrollBar().setValue(
            self._vertical_start -
            delta.y()
        )

    def _end_pan(self):

        self._panning = False

        self._image_label.setCursor(
            Qt.CursorShape.ArrowCursor
        )

    def eventFilter(self, watched, event):
        return super().eventFilter(watched, event)

    def _create_actions(self):
        self._save_as_act = QAction(
            "&Save As...",
            self
        )

        self._print_act = QAction(
            "&Print...",
            self
        )

        self._copy_act = QAction(
            "&Copy",
            self
        )

        self._paste_act = QAction(
            "&Paste",
            self
        )

        self._zoom_in_act = QAction(
            "Zoom &In (25%)",
            self
        )

        self._zoom_out_act = QAction(
            "Zoom &Out (25%)",
            self
        )

        self._normal_size_act = QAction(
            "&Normal Size",
            self
        )

        self._fit_to_window_act = QAction(
            "&Fit to Window",
            self
        )

        self._fit_to_window_act.setCheckable(
            True
        )

        self._update_actions()

    def _update_actions(self):

        has_image = (
            self._image is not None
        )

        self._save_as_act.setEnabled(
            has_image
        )

        self._copy_act.setEnabled(
            has_image
        )

        self._print_act.setEnabled(
            has_image
        )

        enable_zoom = (
            has_image
            and not self._fit_to_window_act.isChecked()
        )

        self._zoom_in_act.setEnabled(
            enable_zoom
            and self._scale_factor < 3.0
        )

        self._zoom_out_act.setEnabled(
            enable_zoom
            and self._scale_factor > 0.333
        )

        self._normal_size_act.setEnabled(
            enable_zoom
        )

    def _save_file(self, fileName):
        if self._image is None:
            return False

        writer = QImageWriter(str(fileName))

        native_filename = (QDir.toNativeSeparators(str(fileName)))

        if not writer.write(self._image):
            QMessageBox.information(
                self,
                QGuiApplication.applicationDisplayName(),
                f"Cannot write {native_filename}: "
                f"{writer.errorString()}"
            )

            return False

        return True

    @Slot()
    def _copy(self):

        if self._image is not None:

            QGuiApplication.clipboard().setImage(
                self._image
            )

    @Slot()
    def _paste(self):

        new_image = (
            QGuiApplication
            .clipboard()
            .image()
        )

        if new_image.isNull():
            return

        self._set_image(
            new_image
        )

    @Slot()
    def _print_(self):

        if self._image is None:
            return

        printer = QPrinter()

        dialog = QPrintDialog(
            printer,
            self
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):

            with QPainter(printer) as painter:

                pixmap = QPixmap.fromImage(
                    self._image
                )

                rect = painter.viewport()

                size = pixmap.size()

                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)

                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(pixmap.rect())
                painter.drawPixmap(0, 0, pixmap)