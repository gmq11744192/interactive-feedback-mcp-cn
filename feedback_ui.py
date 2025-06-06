# 交互式反馈界面
# 原作者: Fábio Ferreira (https://x.com/fabiomlferreira)
# 灵感来源: dotcursorrules.com (https://dotcursorrules.com/)
# 由Pau Oliva (https://x.com/pof)增强，基于 https://github.com/ttommyth/interactive-mcp 的创意
import os
import sys
import json
import argparse
import base64
import uuid
from pathlib import Path
from typing import Optional, TypedDict, List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QGroupBox,
    QFrame, QScrollArea, QGraphicsDropShadowEffect, QSizePolicy,
    QFileDialog, QListWidget, QListWidgetItem, QMenu, QToolButton
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings, QPoint, QRect, QEvent, QMimeData, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QTextCursor, QIcon, QKeyEvent, QPalette, QColor, QFont, QFontDatabase, QPainter, QPen, QPainterPath, QMouseEvent, QPixmap, QImage, QClipboard, QDrag

class FeedbackResult(TypedDict):
    interactive_feedback: str
    attachments: Optional[List[Dict[str, Any]]]

def get_dark_mode_palette(app: QApplication):
    darkPalette = app.palette()
    # 使用更现代的深色主题颜色方案
    darkPalette.setColor(QPalette.Window, QColor(45, 45, 48))
    darkPalette.setColor(QPalette.WindowText, QColor(225, 225, 225))
    darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.Base, QColor(36, 36, 39))
    darkPalette.setColor(QPalette.AlternateBase, QColor(56, 56, 59))
    darkPalette.setColor(QPalette.ToolTipBase, QColor(45, 45, 48))
    darkPalette.setColor(QPalette.ToolTipText, QColor(225, 225, 225))
    darkPalette.setColor(QPalette.Text, QColor(225, 225, 225))
    darkPalette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.Dark, QColor(30, 30, 33))
    darkPalette.setColor(QPalette.Shadow, QColor(18, 18, 20))
    darkPalette.setColor(QPalette.Button, QColor(45, 45, 48))
    darkPalette.setColor(QPalette.ButtonText, QColor(225, 225, 225))
    darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.BrightText, QColor(255, 100, 100))
    darkPalette.setColor(QPalette.Link, QColor(42, 140, 218))
    darkPalette.setColor(QPalette.Highlight, QColor(42, 140, 218))
    darkPalette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(75, 75, 78))
    darkPalette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    darkPalette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.PlaceholderText, QColor(150, 150, 150))
    return darkPalette

class FeedbackTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                background-color: #2d2d30;
                color: #e1e1e1;
            }
        """)
        self.setAcceptDrops(True)
        # 跟踪附件
        self.attachments = []
        # 获取剪贴板实例
        self.clipboard = QApplication.clipboard()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # 找到父级 FeedbackUI 实例并调用提交
            parent = self.parent()
            while parent and not isinstance(parent, FeedbackUI):
                parent = parent.parent()
            if parent:
                parent._submit_feedback()
        elif event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            # 拦截Ctrl+V粘贴事件
            self.handlePaste()
        else:
            super().keyPressEvent(event)
    
    def handlePaste(self):
        # 检查剪贴板内容
        mime_data = self.clipboard.mimeData()
        
        # 如果有图片，优先处理图片
        if mime_data.hasImage():
            image = QImage(mime_data.imageData())
            if not image.isNull():
                # 找到父级FeedbackUI实例
                parent = self.parent()
                while parent and not isinstance(parent, FeedbackUI):
                    parent = parent.parent()
                
                if parent and hasattr(parent, "attachments_manager"):
                    # 将图片添加到附件管理器
                    parent.attachments_manager.add_image_from_clipboard(image)
                    return
        
        # 如果有文件，处理文件
        if mime_data.hasUrls():
            urls = mime_data.urls()
            file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            
            if file_paths:
                # 找到父级FeedbackUI实例
                parent = self.parent()
                while parent and not isinstance(parent, FeedbackUI):
                    parent = parent.parent()
                
                if parent and hasattr(parent, "attachments_manager"):
                    # 添加文件到附件管理器
                    for file_path in file_paths:
                        parent.attachments_manager.add_file(file_path)
                    return
        
        # 如果没有图片或文件，使用默认粘贴行为
        super().paste()
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dropEvent(self, event):
        mime_data = event.mimeData()
        
        # 处理图片拖放
        if mime_data.hasImage():
            image = QImage(mime_data.imageData())
            if not image.isNull():
                # 找到父级FeedbackUI实例
                parent = self.parent()
                while parent and not isinstance(parent, FeedbackUI):
                    parent = parent.parent()
                
                if parent and hasattr(parent, "attachments_manager"):
                    # 将图片添加到附件管理器
                    parent.attachments_manager.add_image_from_clipboard(image)
                    event.acceptProposedAction()
                    return
        
        # 处理文件拖放
        if mime_data.hasUrls():
            urls = mime_data.urls()
            file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            
            if file_paths:
                # 找到父级FeedbackUI实例
                parent = self.parent()
                while parent and not isinstance(parent, FeedbackUI):
                    parent = parent.parent()
                
                if parent and hasattr(parent, "attachments_manager"):
                    # 添加文件到附件管理器
                    for file_path in file_paths:
                        parent.attachments_manager.add_file(file_path)
                    event.acceptProposedAction()
                    return
        
        super().dropEvent(event)

class AttachmentsManager(QWidget):
    """附件管理器组件，显示和管理上传的文件和图片"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.attachments = []  # 存储附件数据
        self._setup_ui()
    
    def _setup_ui(self):
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 顶部标题和按钮区域
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel("附件")
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch(1)
        
        # 上传按钮
        self.upload_button = QToolButton()
        self.upload_button.setText("添加")
        self.upload_button.setPopupMode(QToolButton.InstantPopup)
        self.upload_button.setStyleSheet("""
            QToolButton {
                background-color: #2d2d30;
                color: #e1e1e1;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px 10px;
            }
            QToolButton:hover {
                background-color: #3e3e42;
            }
            QToolButton::menu-indicator {
                image: none;
            }
        """)
        
        # 创建上下文菜单
        upload_menu = QMenu(self)
        upload_menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #e1e1e1;
                border: 1px solid #555;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3e3e42;
            }
        """)
        
        # 添加文件选项
        action_file = upload_menu.addAction("选择文件")
        action_file.triggered.connect(self.open_file_dialog)
        
        # 添加图片选项
        action_image = upload_menu.addAction("选择图片")
        action_image.triggered.connect(self.open_image_dialog)
        
        # 从剪贴板粘贴选项
        action_paste = upload_menu.addAction("从剪贴板粘贴")
        action_paste.triggered.connect(self.paste_from_clipboard)
        
        self.upload_button.setMenu(upload_menu)
        header_layout.addWidget(self.upload_button)
        
        layout.addLayout(header_layout)
        
        # 创建附件列表
        self.attachments_list = QListWidget()
        self.attachments_list.setMinimumHeight(100)
        self.attachments_list.setMaximumHeight(200)
        self.attachments_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
            }
        """)
        
        # 右键菜单
        self.attachments_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.attachments_list.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.attachments_list)
        
        # 如果没有附件，隐藏整个组件
        self.setVisible(False)
    
    def open_file_dialog(self):
        """打开文件选择对话框"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", "所有文件 (*.*)"
        )
        
        for file_path in file_paths:
            self.add_file(file_path)
    
    def open_image_dialog(self):
        """打开图片选择对话框"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        
        for file_path in file_paths:
            self.add_file(file_path, is_image=True)
    
    def paste_from_clipboard(self):
        """从剪贴板粘贴图片或文件"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        # 处理图片
        if mime_data.hasImage():
            image = QImage(mime_data.imageData())
            if not image.isNull():
                self.add_image_from_clipboard(image)
                return
        
        # 处理文件
        if mime_data.hasUrls():
            urls = mime_data.urls()
            file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            
            for file_path in file_paths:
                self.add_file(file_path)
            
            if file_paths:
                return
        
        # 如果没有可用内容
        print("剪贴板中没有找到图片或文件")
    
    def add_file(self, file_path, is_image=None):
        """添加文件到附件列表"""
        file_path = os.path.normpath(file_path)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        # 确定文件类型
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # 如果未指定是否为图片，则根据扩展名判断
        if is_image is None:
            is_image = file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
        
        # 创建唯一ID
        attachment_id = str(uuid.uuid4())
        
        # 准备附件数据
        attachment_data = {
            'id': attachment_id,
            'name': file_name,
            'path': file_path,
            'type': 'image' if is_image else 'file',
            'size': os.path.getsize(file_path)
        }
        
        # 为图片创建预览
        preview = None
        if is_image:
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    # 图片缩放处理
                    pixmap = pixmap.scaledToWidth(100, Qt.SmoothTransformation)
                    preview = pixmap
                    
                    # 生成base64数据
                    byte_array = QByteArray()
                    buffer = QBuffer(byte_array)
                    buffer.open(QIODevice.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    attachment_data['data'] = f"data:image/png;base64,{base64.b64encode(byte_array.data()).decode('utf-8')}"
            except Exception as e:
                print(f"图片预览生成失败: {e}")
        
        # 添加到附件列表
        self.attachments.append(attachment_data)
        
        # 创建列表项
        item = QListWidgetItem()
        self.attachments_list.addItem(item)
        
        # 创建附件项UI
        attachment_widget = self._create_attachment_item_widget(attachment_data, preview)
        item.setSizeHint(attachment_widget.sizeHint())
        self.attachments_list.setItemWidget(item, attachment_widget)
        
        # 确保附件管理器可见
        self.setVisible(True)
    
    def add_image_from_clipboard(self, image):
        """从剪贴板添加图片"""
        if image.isNull():
            return
        
        # 创建唯一ID和临时文件名
        attachment_id = str(uuid.uuid4())
        file_name = f"clipboard_image_{attachment_id[:8]}.png"
        
        # 创建临时目录以保存剪贴板图片
        temp_dir = os.path.join(os.path.expanduser("~"), ".interactive_feedback_temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存图片到临时文件
        file_path = os.path.join(temp_dir, file_name)
        image.save(file_path, "PNG")
        
        # 创建QPixmap用于预览
        pixmap = QPixmap.fromImage(image)
        pixmap = pixmap.scaledToWidth(100, Qt.SmoothTransformation)
        
        # 生成base64数据
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        
        # 准备附件数据
        attachment_data = {
            'id': attachment_id,
            'name': file_name,
            'path': file_path,
            'type': 'image',
            'size': os.path.getsize(file_path),
            'data': f"data:image/png;base64,{base64.b64encode(byte_array.data()).decode('utf-8')}"
        }
        
        # 添加到附件列表
        self.attachments.append(attachment_data)
        
        # 创建列表项
        item = QListWidgetItem()
        self.attachments_list.addItem(item)
        
        # 创建附件项UI
        attachment_widget = self._create_attachment_item_widget(attachment_data, pixmap)
        item.setSizeHint(attachment_widget.sizeHint())
        self.attachments_list.setItemWidget(item, attachment_widget)
        
        # 确保附件管理器可见
        self.setVisible(True)
    
    def _create_attachment_item_widget(self, attachment_data, preview=None):
        """创建附件项UI组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 显示预览或图标
        if preview and not preview.isNull():
            # 图片预览
            preview_label = QLabel()
            preview_label.setPixmap(preview)
            preview_label.setFixedSize(100, 100)
            preview_label.setScaledContents(True)
            layout.addWidget(preview_label)
        else:
            # 文件图标
            icon_label = QLabel()
            icon_label.setText("📄")
            icon_label.setStyleSheet("font-size: 24px;")
            icon_label.setFixedWidth(30)
            layout.addWidget(icon_label)
        
        # 文件信息
        info_layout = QVBoxLayout()
        
        # 文件名
        name_label = QLabel(attachment_data['name'])
        name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(name_label)
        
        # 文件大小
        size_str = self._format_size(attachment_data['size'])
        size_label = QLabel(f"大小: {size_str}")
        info_layout.addWidget(size_label)
        
        info_layout.addStretch(1)
        layout.addLayout(info_layout, stretch=1)
        
        # 删除按钮
        delete_button = QPushButton("×")
        delete_button.setFixedSize(24, 24)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #e1e1e1;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c42b1c;
            }
        """)
        delete_button.clicked.connect(lambda: self.remove_attachment(attachment_data['id']))
        layout.addWidget(delete_button)
        
        return widget
    
    def _format_size(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def remove_attachment(self, attachment_id):
        """删除指定的附件"""
        # 查找附件索引
        index_to_remove = None
        for i, attachment in enumerate(self.attachments):
            if attachment['id'] == attachment_id:
                index_to_remove = i
                break
        
        if index_to_remove is not None:
            # 从数据列表中删除
            removed_attachment = self.attachments.pop(index_to_remove)
            
            # 从UI列表中删除
            self.attachments_list.takeItem(index_to_remove)
            
            # 如果是剪贴板图片，删除临时文件
            if 'clipboard_image_' in removed_attachment['name']:
                try:
                    os.remove(removed_attachment['path'])
                except Exception as e:
                    print(f"删除临时文件失败: {e}")
            
            # 如果没有附件了，隐藏附件管理器
            if not self.attachments:
                self.setVisible(False)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        if self.attachments_list.count() == 0:
            return
        
        item = self.attachments_list.itemAt(position)
        if not item:
            return
        
        index = self.attachments_list.row(item)
        attachment = self.attachments[index]
        
        # 创建上下文菜单
        context_menu = QMenu(self)
        context_menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #e1e1e1;
                border: 1px solid #555;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3e3e42;
            }
        """)
        
        # 预览选项（仅适用于图片）
        if attachment['type'] == 'image':
            preview_action = context_menu.addAction("预览")
            preview_action.triggered.connect(lambda: self.preview_image(attachment))
        
        # 删除选项
        delete_action = context_menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.remove_attachment(attachment['id']))
        
        # 显示菜单
        context_menu.exec_(self.attachments_list.mapToGlobal(position))
    
    def preview_image(self, attachment):
        """预览图片"""
        # 这里可以实现一个简单的图片预览对话框
        # 为简化代码，我们只打开系统默认程序查看图片
        try:
            import platform
            system = platform.system()
            
            if system == 'Windows':
                os.startfile(attachment['path'])
            elif system == 'Darwin':  # macOS
                os.system(f'open "{attachment["path"]}"')
            else:  # Linux
                os.system(f'xdg-open "{attachment["path"]}"')
        except Exception as e:
            print(f"打开预览失败: {e}")
    
    def get_attachments_data(self):
        """获取所有附件数据用于提交"""
        return self.attachments

# 移除了标题栏类

class FeedbackUI(QMainWindow):
    def __init__(self, prompt: str, predefined_options: Optional[List[str]] = None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.prompt = prompt
        self.predefined_options = predefined_options or []

        self.feedback_result = None
        self.border_radius = 8  # 窗口圆角半径
        self.old_pos = None  # 用于实现窗口拖动
        
        # 设置透明背景以便应用圆角
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "images", "feedback.png")
        self.setWindowIcon(QIcon(icon_path))
        
        self.settings = QSettings("InteractiveFeedbackMCP", "InteractiveFeedbackMCP")
        
        # 设置窗口初始大小（宽度设置稍大一些，高度设置合理值但会在显示后自动调整）
        self.resize(650, 750)
        self.setMinimumSize(500, 400)  # 设置最小尺寸以确保UI元素可见
        
        # 仅恢复窗口大小而非位置
        self.settings.beginGroup("MainWindow_General")
        geometry = self.settings.value("geometry")
        if geometry:
            # 仅恢复尺寸，不恢复位置
            self.restoreGeometry(geometry)
            # 重新定位到屏幕中心
            self.center_on_screen()
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        self.settings.endGroup() # 结束 "MainWindow_General" 组

        # 设置全局样式
        self.setup_fonts()
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 12px;
                font-weight: bold;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #e1e1e1;
            }
            QLabel {
                color: #e1e1e1;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a88e1;
            }
            QPushButton:pressed {
                background-color: #0067b8;
            }
            QCheckBox {
                color: #e1e1e1;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #777; /* Slightly lighter border for contrast */
                background-color: #3a3a3e; /* Background for the checkbox indicator */
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3a3a3e;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d7; /* Highlight color for checked state */
                /* Optionally, you can add a check mark image here if needed */
                /* image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); */
            }
            QCheckBox::indicator:hover {
                border: 1px solid #999;
            }
            QFrame[frameShape="4"] { /* HLine */
                color: #555;
                margin: 5px 0;
            }
            QScrollArea, QWidget#centralWidget {
                border: none;
                background-color: transparent;
            }
        """)

        self._create_ui()
        # 添加窗口阴影
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.shadow.setOffset(0, 2)
        self.centralWidget().setGraphicsEffect(self.shadow)
        
        # 安装事件过滤器以处理鼠标拖动
        self.installEventFilter(self)

    def setup_fonts(self):
        # 设置中文友好的字体
        font_id = QFontDatabase.addApplicationFont("Microsoft YaHei")
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            # 回退使用系统默认字体
            font_family = "微软雅黑, Microsoft YaHei, 宋体, SimSun, sans-serif"
        
        font = QFont(font_family, 10)
        QApplication.setFont(font)

    def _create_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(10)
        
        # 标题部分
        title_label = QLabel("请提供您的反馈")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 0px;
        """)
        title_container_layout = QHBoxLayout()
        title_container_layout.setContentsMargins(0, 0, 0, 0)
        title_container_layout.addStretch(1)
        title_container_layout.addWidget(title_label)
        title_container_layout.addStretch(1)
        
        main_layout.addLayout(title_container_layout)

        # 添加标题与内容之间的分界线
        header_separator = QFrame()
        header_separator.setFrameShape(QFrame.HLine)
        header_separator.setFrameShadow(QFrame.Sunken)
        header_separator.setStyleSheet("""
            QFrame[frameShape="4"] {
                color: #3a3a3a;
                background-color: #3a3a3a;
                border: none;
                height: 1px;
                margin: 0px 0;
            }
        """)
        main_layout.addWidget(header_separator)

        # 创建反馈主内容容器（非滚动区域）
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet("background-color: transparent;")
        content_wrapper_layout = QVBoxLayout(content_wrapper)
        content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        content_wrapper_layout.setSpacing(15)
        
        # 创建可滚动区域（只有在需要时才会滚动）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2d2d30;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建内容容器小部件
        content_widget = QWidget()
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_widget.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)

        # 反馈部分
        self.feedback_group = QGroupBox("反馈内容")
        self.feedback_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        feedback_layout = QVBoxLayout(self.feedback_group)
        feedback_layout.setSpacing(15)

        # 描述标签 (来自 self.prompt) - 支持多行
        self.description_label = QLabel(self.prompt)
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("padding: 5px 0;")
        feedback_layout.addWidget(self.description_label)

        # 添加预定义选项（如果有）
        self.option_checkboxes = []
        if self.predefined_options and len(self.predefined_options) > 0:
            options_frame = QFrame()
            options_layout = QVBoxLayout(options_frame)
            options_layout.setContentsMargins(0, 10, 0, 10)
            options_layout.setSpacing(8)
            
            for option in self.predefined_options:
                checkbox = QCheckBox(option)
                self.option_checkboxes.append(checkbox)
                options_layout.addWidget(checkbox)
            
            feedback_layout.addWidget(options_frame)
            
            # 添加分隔线
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            feedback_layout.addWidget(separator)

        # 自由文本反馈
        feedback_label = QLabel("详细反馈:")
        feedback_layout.addWidget(feedback_label)
        
        self.feedback_text = FeedbackTextEdit()
        font_metrics = self.feedback_text.fontMetrics()
        row_height = font_metrics.height()
        # 设置一个更大的默认高度（大约8-10行文本）
        self.feedback_text.setMinimumHeight(8 * row_height)
        # 尝试固定高度而非使用弹性策略
        self.feedback_text.setFixedHeight(10 * row_height)

        self.feedback_text.setPlaceholderText("请在此输入您的反馈（按Ctrl+Enter提交）")
        
        feedback_layout.addWidget(self.feedback_text)
        
        # 添加附件管理器组件
        self.attachments_manager = AttachmentsManager()
        feedback_layout.addWidget(self.attachments_manager)
        
        # 将反馈组添加到内容布局中
        content_layout.addWidget(self.feedback_group)
        
        # 添加一个弹性空间，帮助内容自然扩展
        content_layout.addStretch(1)
        
        # 将内容容器设置为滚动区域的内容
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主容器
        content_wrapper_layout.addWidget(scroll_area)
        
        # 添加分界线，区分滚动内容和按钮区域
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("""
            QFrame[frameShape="4"] {
                color: #3a3a3a;
                background-color: #3a3a3a;
                border: none;
                height: 1px;
                margin: 0px 0;
            }
        """)
        content_wrapper_layout.addWidget(separator)
        
        # 按钮部分（放在主容器中，不在滚动区域内）
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch(1)
        
        # 添加"无需反馈已解决了"按钮
        resolved_button = QPushButton("已解决！")
        resolved_button.clicked.connect(self._submit_resolved)
        resolved_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #34b754;
            }
            QPushButton:pressed {
                background-color: #218838;
            }
        """)
        
        # 提交按钮
        submit_button = QPushButton("发送反馈")
        submit_button.clicked.connect(self._submit_feedback)
        submit_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a88e1;
            }
            QPushButton:pressed {
                background-color: #0067b8;
            }
        """)
        
        button_layout.addWidget(resolved_button)
        button_layout.addWidget(submit_button)
        button_layout.addStretch(1)
        
        # 将按钮布局添加到主容器中
        content_wrapper_layout.addLayout(button_layout)
        
        # 将内容包装器添加到主布局
        main_layout.addWidget(content_wrapper)
        
        # 设置内容包装器的大小策略，允许它根据需要伸展
        content_wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置一个合理的初始尺寸
        self.setMinimumWidth(500)

    def _submit_feedback(self):
        feedback_text = self.feedback_text.toPlainText().strip()
        selected_options = []
        
        # 获取选中的预定义选项（如果有）
        if self.option_checkboxes:
            for i, checkbox in enumerate(self.option_checkboxes):
                if checkbox.isChecked():
                    selected_options.append(self.predefined_options[i])
        
        # 组合选中的选项和反馈文本
        final_feedback_parts = []
        
        # 添加选中的选项
        if selected_options:
            final_feedback_parts.append("选中选项: " + "; ".join(selected_options))
        
        # 添加用户的文本反馈
        if feedback_text:
            final_feedback_parts.append(feedback_text)
            
        # 如果两部分都存在，用换行符连接
        final_feedback = "\n\n".join(final_feedback_parts)
        
        # 获取附件数据
        attachments = []
        if hasattr(self, 'attachments_manager'):
            attachments = self.attachments_manager.get_attachments_data()
            
        self.feedback_result = FeedbackResult(
            interactive_feedback=final_feedback,
            attachments=attachments,
        )
        self.close()

    def _submit_resolved(self):
        """提交'问题已解决'的反馈"""
        self.feedback_result = FeedbackResult(
            interactive_feedback="问题已解决",
            attachments=[],
        )
        self.close()

    def closeEvent(self, event):
        # 保存主窗口的通用UI设置(几何尺寸、状态)
        try:
            self.settings.beginGroup("MainWindow_General")
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            self.settings.endGroup()
            self.settings.sync()  # 确保设置立即保存
        except Exception as e:
            print(f"保存窗口设置时出错: {str(e)}")

        super().closeEvent(event)

    def center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def run(self) -> FeedbackResult:
        # 先调用limitMaxHeight计算适当的窗口大小
        self.limitMaxHeight()
        
        # 显示窗口前确保它居中
        self.center_on_screen()
        
        # 显示窗口
        self.show()
        
        # 再次调整窗口大小和位置，确保UI元素完全加载后的尺寸正确
        QTimer.singleShot(100, lambda: (self.limitMaxHeight(), self.center_on_screen()))
        
        QApplication.instance().exec()

        if not self.feedback_result:
            return FeedbackResult(
                interactive_feedback="",
                attachments=[]
            )

        return self.feedback_result

    def limitMaxHeight(self):
        """根据内容调整窗口大小，最大高度为900像素"""
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        # 定义窗口最大高度（900像素或屏幕高度的80%，取较小值）
        max_allowed_height = min(700, int(screen.height() * 0.7))
        
        # 直接设置一个固定的高度，确保所有元素都可见
        # 此高度应该足够显示标题、反馈组和按钮，但不超过最大允许高度
        base_height = 700  # 基础高度，根据实际内容调整
        
        # 添加预定义选项的额外高度
        option_height = len(self.option_checkboxes) * 30 if self.option_checkboxes else 0
        
        # 根据提示文本长度估计额外高度
        prompt_lines = len(self.prompt.split('\n'))
        prompt_height = prompt_lines * 20  # 每行约20像素
        
        # 计算目标高度
        target_height = base_height + option_height + prompt_height
        
        # 确保不超过最大允许高度
        if target_height > max_allowed_height:
            target_height = max_allowed_height
        
        # 确保至少有最小高度
        min_height = 500
        target_height = max(target_height, min_height)
        
        # 保持窗口宽度不变，只调整高度
        self.resize(self.width(), target_height)
        
        # 打印调试信息
        print(f"窗口调整高度: {target_height}px (基础:{base_height}, 选项:{option_height}, 提示:{prompt_height})")

    def paintEvent(self, event):
        """绘制自定义边框和圆角"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 定义绘制区域
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(rect, self.border_radius, self.border_radius)
        
        # 设置画笔（边框）
        border_pen = QPen(QColor('#555555'))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        
        # 填充背景
        painter.fillPath(path, QColor('#2d2d30'))
        
        # 绘制边框
        painter.drawPath(path)
        
    def eventFilter(self, obj, event):
        """处理鼠标事件以实现窗口拖动"""
        if obj is self:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.old_pos = event.globalPosition().toPoint()
                    return True
            elif event.type() == QEvent.MouseMove:
                if self.old_pos:
                    delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
                    self.move(self.pos() + delta)
                    self.old_pos = event.globalPosition().toPoint()
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    self.old_pos = None
                    return True
        return super().eventFilter(obj, event)

def feedback_ui(prompt: str, predefined_options: Optional[List[str]] = None, output_file: Optional[str] = None) -> Optional[FeedbackResult]:
    app = QApplication.instance() or QApplication()
    app.setPalette(get_dark_mode_palette(app))
    app.setStyle("Fusion")
    ui = FeedbackUI(prompt, predefined_options)
    result = ui.run()

    if output_file and result:
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        # 将结果保存到输出文件
        with open(output_file, "w") as f:
            json.dump(result, f)
        return None

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行反馈界面")
    parser.add_argument("--prompt", default="我已实现您请求的更改。", help="向用户展示的提示信息")
    parser.add_argument("--predefined-options", default="", help="预定义选项的管道分隔列表 (|||)")
    parser.add_argument("--output-file", help="保存反馈结果为JSON的路径")
    args = parser.parse_args()

    predefined_options = [opt for opt in args.predefined_options.split("|||") if opt] if args.predefined_options else None
    
    result = feedback_ui(args.prompt, predefined_options, args.output_file)
    if result:
        print(f"\n收到反馈:\n{result['interactive_feedback']}")
        if result.get('attachments') and len(result['attachments']) > 0:
            print(f"附件数量: {len(result['attachments'])}")
    sys.exit(0)