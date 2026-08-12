from PySide6.QtGui import QCursor, QMouseEvent, QPainter, QPen, QKeyEvent
from PySide6.QtCore import QPoint, Qt, QEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy
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
        self.boxes = []
        self.current_box = [(-1, -1), (-1, -1)]

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mouse_pos = QPoint(-1, -1)

        self.parent_label.installEventFilter(self)
        self.resize(self.parent_label.size())

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape and self.current_box[0] != (-1, -1):
            self.reset_box()
            self.update()

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
                self.parents.box_label_1.setText(f"Point 1: {x, y}")
                self.parents.box_label_2.setText(f"Point 2: (0, 0)")
            else:
                self.current_box[1] = (x, y)
                self.parents.box_label_2.setText(f"Point 2: {x, y}")
                self.write_box_data(self.current_box)
                self.current_box = [(-1, -1), (-1, -1)]
                
            self.update()

    # Crosshair lines
    def paintEvent(self, event):
        if not self.parent_label.pixmap() or self.parent_label.pixmap().isNull():
            return
        
        label_w = self.parent_label.width()
        label_h = self.parent_label.height()
        pix_w = self.parent_label.pixmap().width()
        pix_h = self.parent_label.pixmap().height()

        x_offset = 0 if (self.parent_label.alignment() & Qt.AlignmentFlag.AlignLeft) else (label_w - pix_w) // 2
        y_offset = (label_h - pix_h) // 2 if (self.parent_label.alignment() & Qt.AlignmentFlag.AlignVCenter) else 0

        # Account for the image label's position within the parent widget
        label_pos = self.parent_label.mapTo(self.parents, QPoint(0, 0))
        x_offset += label_pos.x()
        y_offset += label_pos.y()

        mx = self.mouse_pos.x()
        my = self.mouse_pos.y()

        painter = QPainter(self)

        if mx != -1 and my != -1:
            pen = QPen(self.colors[self.color_index], 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            painter.drawLine(mx, y_offset, mx, y_offset + pix_h)
            painter.drawLine(x_offset, my, x_offset + pix_w, my)

            if self.current_box[0] != (-1, -1):
                p1x, p1y = self.current_box[0]
                painter.drawRect(mx, my, (p1x - mx), (p1y - my))

    def reset_box(self):
        self.current_box = [(-1, -1), (-1, -1)]

    def write_box_data(self, box):
        if box[0] != (-1, -1) and box[1] != (-1, -1):
            x1, y1 = box[0]
            x2, y2 = box[1]
            box_center = ((x1 + x2) / 2, (y1 + y2) / 2)
            with open(self.image_label_file, "a") as f:
                # Yolo normalized format: class_id center_x center_y width height
                # Instead of class_id, use the name of the class itself so that imported labels can be used for training without needing to map class IDs to names
                # When ready for pipeline training, the class names can be mapped to IDs in a separate step
                f.write(f"{self.parents.species_list_dropdown.currentText()} {box_center[0] / self.parents.width()} {box_center[1] / self.parents.height()} {abs(x2 - x1) / self.parents.width()} {abs(y2 - y1) / self.parents.height()}\n")
        self.load_saved_boxes(self.image_label_file)

    def load_saved_boxes(self, file):
        self.image_label_file = file
        with open(file, "r") as f:
            self.boxes = [line for line in f.read().splitlines() if line]
        self.update_visible_boxes(self.boxes)

    def update_visible_boxes(self, boxes):
        self.boxes = boxes
        # Clear existing boxes from the layout
        while self.parents.scroll_boxes_layout.count():
            item = self.parents.scroll_boxes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.parents.scroll_boxes_layout.setColumnStretch(0, 1)
        self.parents.scroll_boxes_layout.setColumnStretch(1, 1)
        self.parents.scroll_boxes_layout.setHorizontalSpacing(8)
        self.parents.scroll_boxes_layout.setVerticalSpacing(8)

        for idx, box in enumerate(boxes):
            row = idx // 2
            col = idx % 2

            box_container = QWidget()
            box_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            box_container.setMinimumWidth(160)
            box_container.setStyleSheet(
                "QWidget {"
                "  border: 1px solid #7a7a7a;"
                "  border-radius: 6px;"
                "  background-color: rgba(255, 255, 255, 12);"
                "  padding: 6px;"
                "}"
            )
            boxinfo_layout = QVBoxLayout(box_container)
            boxinfo_layout.setContentsMargins(4, 4, 4, 4)
            boxinfo_layout.setSpacing(5)

            # Show all yolo info from the box in its container with text wrapping
            box_info = QLabel(f"""
                Box {idx + 1} Class: {box.split(' ')[0]}
                Center: ({round(float(box.split(' ')[1]) * self.parent_label.width(), 1)}, {round(float(box.split(' ')[2]) * self.parent_label.height(), 1)})
                Width: {round(float(box.split(' ')[3]) * self.parent_label.width())}
                Height: {round(float(box.split(' ')[4]) * self.parent_label.height())}
                """
            )
            box_info.setWordWrap(True)

            buttons_layout = QHBoxLayout()
            buttons_layout.setContentsMargins(0, 0, 0, 0)
            buttons_layout.setSpacing(5)

            delete_box_btn = QPushButton("Delete")
            change_box_class_btn = QPushButton("Class")
            delete_box_btn.setFixedSize(60, 30)
            change_box_class_btn.setFixedSize(60, 30)
            delete_box_btn.clicked.connect(lambda: self.delete_label(box))

            buttons_layout.addWidget(delete_box_btn)
            buttons_layout.addWidget(change_box_class_btn)

            boxinfo_layout.addWidget(box_info, alignment=Qt.AlignmentFlag.AlignTop)
            boxinfo_layout.addLayout(buttons_layout)

            self.parents.scroll_boxes_layout.addWidget(
                box_container,
                row,
                col,
                1,
                1,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )

    def delete_label(self, label):
        if label in self.boxes:
            self.boxes.remove(label)
        
        with open(self.image_label_file, "w") as f:
            for box in self.boxes:
                f.write(f"{box}\n")
        
        self.load_saved_boxes(self.image_label_file)


    def eventFilter(self, watched, event):
        if watched == self.parent_label:
            if event.type() == QEvent.Type.Resize:
                self.resize(self.parent_label.size())
                self.move(self.parent_label.pos())
                self.raise_()
                self.show()
            elif event.type() == QEvent.Type.Move:
                self.move(self.parent_label.pos())

        return super().eventFilter(watched, event)