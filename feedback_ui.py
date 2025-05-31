# 交互式反馈界面
# 原作者: Fábio Ferreira (https://x.com/fabiomlferreira)
# 灵感来源: dotcursorrules.com (https://dotcursorrules.com/)
# 由Pau Oliva (https://x.com/pof)增强，基于 https://github.com/ttommyth/interactive-mcp 的创意
import os
import sys
import json
import argparse
from typing import Optional, TypedDict, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QGroupBox,
    QFrame, QScrollArea, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings, QPoint, QRect, QEvent
from PySide6.QtGui import QTextCursor, QIcon, QKeyEvent, QPalette, QColor, QFont, QFontDatabase, QPainter, QPen, QPainterPath, QMouseEvent

class FeedbackResult(TypedDict):
    interactive_feedback: str

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

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # 找到父级 FeedbackUI 实例并调用提交
            parent = self.parent()
            while parent and not isinstance(parent, FeedbackUI):
                parent = parent.parent()
            if parent:
                parent._submit_feedback()
        else:
            super().keyPressEvent(event)

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
        
        # 设置窗口初始大小为较小的值，以便后续自动调整
        self.resize(600, 400)
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 600) // 2
        y = (screen.height() - 400) // 2
        self.move(x, y)
        
        # 尝试恢复保存的窗口状态
        self.settings.beginGroup("MainWindow_General")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
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
            margin-bottom: 10px;
        """)
        title_container_layout = QHBoxLayout()
        title_container_layout.setContentsMargins(0, 0, 0, 0)
        title_container_layout.addWidget(title_label)
        title_container_layout.addStretch()
        
        main_layout.addLayout(title_container_layout)

        # 创建反馈内容容器（不使用滚动区域）
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)

        # 反馈部分
        self.feedback_group = QGroupBox("反馈内容")
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
        # 计算2-3行文本的高度 + 一些内边距，减少默认高度
        padding = self.feedback_text.contentsMargins().top() + self.feedback_text.contentsMargins().bottom() + 5
        self.feedback_text.setMinimumHeight(2.5 * row_height + padding)

        self.feedback_text.setPlaceholderText("请在此输入您的反馈（按Ctrl+Enter提交）")
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

        feedback_layout.addWidget(self.feedback_text)
        
        # 按钮容器，添加右对齐
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(resolved_button)
        button_layout.addWidget(submit_button)
        
        feedback_layout.addLayout(button_layout)

        # 为feedback_group设置最小高度
        self.feedback_group.setMinimumHeight(
            self.description_label.sizeHint().height() + 
            self.feedback_text.minimumHeight() + 
            submit_button.sizeHint().height() + 
            feedback_layout.spacing() * 3 + 
            feedback_layout.contentsMargins().top() + 
            feedback_layout.contentsMargins().bottom() + 
            40  # 额外空间
        )

        # 添加组件到内容布局
        content_layout.addWidget(self.feedback_group)
        
        # 将内容添加到主布局
        main_layout.addWidget(content_widget)
        
        # 窗口显示后自动调整大小以适应内容
        QTimer.singleShot(0, self.adjustSize)

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
            
        self.feedback_result = FeedbackResult(
            interactive_feedback=final_feedback,
        )
        self.close()

    def _submit_resolved(self):
        """提交'问题已解决'的反馈"""
        self.feedback_result = FeedbackResult(
            interactive_feedback="问题已解决",
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

    def run(self) -> FeedbackResult:
        # 显示窗口
        self.show()
        
        # 延迟调整窗口大小以适应内容
        QTimer.singleShot(10, self.adjustSize)
        
        QApplication.instance().exec()

        if not self.feedback_result:
            return FeedbackResult(interactive_feedback="")

        return self.feedback_result

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
    sys.exit(0)
