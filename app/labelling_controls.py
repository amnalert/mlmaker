from PySide6.QtGui import QCursor, QMouseEvent, QPainter, QPen, QKeyEvent, QColor, QFont
from PySide6.QtCore import QPoint, Qt, QEvent, QRectF
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy, QComboBox, QInputDialog, QGridLayout, QScrollArea
from pathlib import Path
import math

class ImageLabellingControls(QWidget):
    def __init__(self, parents, parent_label):
        super().__init__(parents, Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.parent_label = parent_label
        self.parents = parents

        # Crosshair vars
        self.colors = [
            Qt.GlobalColor.white,
            Qt.GlobalColor.red,
            Qt.GlobalColor.darkRed,
            Qt.GlobalColor.green,
            Qt.GlobalColor.darkGreen,
            Qt.GlobalColor.blue,
            Qt.GlobalColor.darkBlue,
            Qt.GlobalColor.cyan,
            Qt.GlobalColor.darkCyan,
            Qt.GlobalColor.magenta,
            Qt.GlobalColor.darkMagenta,
            Qt.GlobalColor.yellow,
            Qt.GlobalColor.darkYellow,
            Qt.GlobalColor.lightGray,
            Qt.GlobalColor.gray,
            Qt.GlobalColor.darkGray,
            Qt.GlobalColor.black
        ]
        self.color_index = 0
        self.image_label_file = ""

        # Box vars
        self.boxes_lines = []
        self.current_box = [(-1, -1), (-1, -1)]
        self.default_class = "none"
        self.hovered_box_label = None
        self.showing_all_boxes = False

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mouse_pos = QPoint(-1, -1)

        # Labelling UI widgets
        self.image_name = QLabel()
        self.box_label_1 = QLabel("Point 1: (0, 0)")
        self.box_label_2 = QLabel("Point 2: (0, 0)")
        self.mouse_pos_label = QLabel("Mouse: (0, 0)")
        
        # Placed boxes scroll area
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
        self.show_all_boxes_btn.clicked.connect(lambda: self._draw_all_boxes())
        
        # Species and project info
        self.species = []
        self.project = ""

        self.parent_label.installEventFilter(self)
        self.resize(self.parent_label.size())

    def change_default_class(self):
        choice, ok = QInputDialog.getItem(
            self,
            "Choose default class",
            "Select a class new boxes will be assigned from the following:",
            self.species
        )
        if ok and choice:
            self.default_class = choice

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.reset_box()
            self.update()
        elif event.key() == Qt.Key.Key_Right:
            self.reset_box()
            try:
                self.parents.controller.home.inspect_img(self.parents.images[self.parents.img_index + 1])
            except IndexError:
                pass
        elif event.key() == Qt.Key.Key_Left:
            self.reset_box()
            if self.parents.img_index >= 1:
                self.parents.controller.home.inspect_img(self.parents.images[self.parents.img_index - 1])

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.position().toPoint()
        self.update()

    def leaveEvent(self, event):
        self.mouse_pos = QPoint(-1, -1)
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        x = int(pos.x())
        y = int(pos.y())
        
        self.setFocus()

        if event.button() == Qt.MouseButton.RightButton:
            self.color_index = (self.color_index + 1) % len(self.colors)
            self.update()
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.current_box[0] == (-1, -1):
                self.current_box[0] = (x, y)
                self.box_label_1.setText(f"Point 1: {x, y}")
                self.box_label_2.setText(f"Point 2: (0, 0)")
            else:
                def_class = ""
                if self.default_class != "none":
                    def_class = self.default_class
                else:
                    def_class = self.species[0]

                self.current_box[1] = (x, y)
                self.box_label_2.setText(f"Point 2: {x, y}")
                self.write_box_data(self.current_box, def_class)
                self.current_box = [(-1, -1), (-1, -1)]
                
            self.update()    

    # Crosshair lines
    def _get_display_image_rect(self):
        pixmap = self.parent_label.pixmap()
        if not pixmap or pixmap.isNull():
            return None

        label_w = self.width()
        label_h = self.height()
        pix_w = pixmap.width()
        pix_h = pixmap.height()

        if label_w <= 0 or label_h <= 0:
            return None

        scale = min(label_w / pix_w, label_h / pix_h)
        draw_w = max(1, int(pix_w * scale))
        draw_h = max(1, int(pix_h * scale))
        x_offset = (label_w - draw_w) // 2
        y_offset = (label_h - draw_h) // 2

        return x_offset, y_offset, draw_w, draw_h

    def _draw_box_from_label(self, painter, label, color, width=2):
        try:
            parts = label.split()
            if len(parts) < 5:
                return
            # coordinates are normalized to the original image dimensions
            cx = float(parts[1])
            cy = float(parts[2])
            bw = float(parts[3])
            bh = float(parts[4])
        except ValueError:
            return

        pixmap = self.parent_label.pixmap()
        if not pixmap or pixmap.isNull():
            return

        orig_w = pixmap.width()
        orig_h = pixmap.height()

        image_rect = self._get_display_image_rect()
        if image_rect is None:
            return

        x_offset, y_offset, draw_w, draw_h = image_rect

        # Convert normalized coords back to the displayed image rectangle.
        x1 = x_offset + (cx - bw / 2) * orig_w * (draw_w / orig_w)
        y1 = y_offset + (cy - bh / 2) * orig_h * (draw_h / orig_h)
        x2 = x_offset + (cx + bw / 2) * orig_w * (draw_w / orig_w)
        y2 = y_offset + (cy + bh / 2) * orig_h * (draw_h / orig_h)

        rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        pen = QPen(color, width, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawRect(rect)

        # Draw class label
        class_name = parts[0]
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(int(min(x1, x2)) + 2, int(min(y1, y2)) - 3, class_name)

    def _draw_all_boxes(self):
        self.showing_all_boxes = not self.showing_all_boxes
        self.update()

    def paintEvent(self, event):
        pixmap = self.parent_label.pixmap()
        if not pixmap or pixmap.isNull():
            return

        image_rect = self._get_display_image_rect()
        if image_rect is None:
            return

        x_offset, y_offset, draw_w, draw_h = image_rect
        mx = self.mouse_pos.x()
        my = self.mouse_pos.y()

        painter = QPainter(self)

        if mx != -1 and my != -1:
            pen = QPen(self.colors[self.color_index], 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            self.mouse_pos_label.setText(f"Mouse: ({mx}, {my})")

            clamped_x = min(max(mx, x_offset), x_offset + draw_w)
            clamped_y = min(max(my, y_offset), y_offset + draw_h)

            painter.drawLine(x_offset, clamped_y, x_offset + draw_w, clamped_y)
            painter.drawLine(clamped_x, y_offset, clamped_x, y_offset + draw_h)

            if self.current_box[0] != (-1, -1):
                p1x, p1y = self.current_box[0]
                rect_x = min(clamped_x, p1x)
                rect_y = min(clamped_y, p1y)
                rect_w = abs(p1x - clamped_x)
                rect_h = abs(p1y - clamped_y)
                painter.drawRect(rect_x, rect_y, rect_w, rect_h)

        if self.hovered_box_label is not None:
            self._draw_box_from_label(painter, self.hovered_box_label, QColor('#ffd93d'), 3)

        if self.showing_all_boxes:
            for box_label in self.boxes_lines:
                self._draw_box_from_label(painter, box_label, QColor('#00ff00'), 2)

    def reset_box(self):
        if self.current_box[0] != (-1, -1):
            self.current_box = [(-1, -1), (-1, -1)]
            self.box_label_1.setText(f"Point 1: (0, 0)")
            self.box_label_2.setText(f"Point 2: (0, 0)")

    def write_box_data(self, box, boxclass):
        if box[0] != (-1, -1) and box[1] != (-1, -1):
            x1_display, y1_display = box[0]
            x2_display, y2_display = box[1]

            if not hasattr(self.parents, "orig_pixmap") or self.parents.orig_pixmap.isNull():
                self.load_saved_boxes(self.image_label_file)
                return

            image_rect = self._get_display_image_rect()
            if image_rect is None:
                self.load_saved_boxes(self.image_label_file)
                return

            x_offset, y_offset, draw_w, draw_h = image_rect
            orig_w = self.parents.orig_pixmap.width()
            orig_h = self.parents.orig_pixmap.height()

            x1_img = (min(x1_display, x2_display) - x_offset) / draw_w * orig_w
            y1_img = (min(y1_display, y2_display) - y_offset) / draw_h * orig_h
            x2_img = (max(x1_display, x2_display) - x_offset) / draw_w * orig_w
            y2_img = (max(y1_display, y2_display) - y_offset) / draw_h * orig_h

            center_x = (x1_img + x2_img) / 2
            center_y = (y1_img + y2_img) / 2
            width = abs(x2_img - x1_img)
            height = abs(y2_img - y1_img)

            with open(self.image_label_file, "a") as f:
                # Yolo normalized format: class_id center_x center_y width height
                # Store relative to the original image dimensions so the box still matches after resizing.
                f.write(
                    f"{boxclass} {center_x / orig_w} {center_y / orig_h} {width / orig_w} {height / orig_h}\n"
                )
        self.load_saved_boxes(self.image_label_file)

    def load_saved_boxes(self, file):
        self.image_label_file = file
        with open(file, "r") as f:
            self.boxes_lines = [line for line in f.read().splitlines() if line]
        self.update_visible_boxes(self.boxes_lines)

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

            box_info = QLabel(f"""
                Box {idx + 1} Class: {box.split(' ')[0]}
                Center: ({round(float(box.split(' ')[1]) * self.parent_label.width(), 1)}, {round(float(box.split(' ')[2]) * self.parent_label.height(), 1)})
                Width: {round(float(box.split(' ')[3]) * self.parent_label.width())}
                Height: {round(float(box.split(' ')[4]) * self.parent_label.height())}
                """
            )

            buttons_layout = QHBoxLayout()
            buttons_layout.setContentsMargins(0, 0, 0, 0)
            buttons_layout.setSpacing(5)

            delete_box_btn = QPushButton("Delete")
            delete_box_btn.setFixedSize(60, 30)
            delete_box_btn.clicked.connect(lambda: self.delete_label(box))

            species_list_dropdown = QComboBox()
            species_list_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            species_list_dropdown.addItems(self.species)
            species_list_dropdown.setCurrentText(box.split(' ')[0])
            species_list_dropdown.currentTextChanged.connect(lambda: self.change_species_label(box, species_list_dropdown.currentText()))

            buttons_layout.addWidget(delete_box_btn)
            buttons_layout.addWidget(species_list_dropdown)

            boxinfo_layout.addWidget(box_info, alignment=Qt.AlignmentFlag.AlignTop)
            boxinfo_layout.addLayout(buttons_layout)

            self.scroll_boxes_layout.addWidget(
                box_container,
                row,
                col,
                1,
                1,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
            box_container.setProperty("box_label", box)

            # Show box on hover over the box_container
            box_container.installEventFilter(self)


    def change_species_label(self, label, new_class):
        if label in self.boxes_lines:
            parts = label.split(' ')
            parts[0] = new_class
            new_label = ' '.join(parts)
            index = self.boxes_lines.index(label)
            self.boxes_lines[index] = new_label

            with open(self.image_label_file, "w") as f:
                for box in self.boxes_lines:
                    f.write(f"{box}\n")

            self.load_saved_boxes(self.image_label_file)

    def delete_label(self, label):
        if label in self.boxes_lines:
            self.boxes_lines.remove(label)
        
        with open(self.image_label_file, "w") as f:
            for box in self.boxes_lines:
                f.write(f"{box}\n")
        
        self.load_saved_boxes(self.image_label_file)

    def eventFilter(self, watched, event):
        if watched == self.parent_label:
            if event.type() == QEvent.Type.Resize:
                self.resize(self.parent_label.size())
                self.move(self.parent_label.mapTo(self.parents, QPoint(0, 0)))
                self.raise_()
                self.show()
            elif event.type() == QEvent.Type.Move:
                self.move(self.parent_label.mapTo(self.parents, QPoint(0, 0)))
        elif isinstance(watched, QWidget):
            box_label = watched.property("box_label")
            if box_label is not None:
                if event.type() == QEvent.Type.Enter:
                    self.hovered_box_label = box_label
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
                    if self.hovered_box_label == box_label:
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

        return super().eventFilter(watched, event)