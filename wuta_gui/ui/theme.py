"""共享主题配置 - Apple 风格配色、字体、通用样式"""

from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

# === Apple 风格配色 ===
COLORS = {
    'bg_primary': '#f5f5f7',      # 主背景（macOS 窗口背景）
    'bg_secondary': '#ffffff',     # 卡片背景
    'bg_sidebar': '#fbfbfd',       # 侧边栏背景
    'bg_elevated': '#ffffff',      # 浮起元素
    'text_primary': '#1d1d1f',     # 主文字（近黑）
    'text_secondary': '#86868b',   # 次文字（灰）
    'text_tertiary': '#aeaeb2',    # 三级文字（浅灰）
    'accent': '#0071e3',           # Apple Blue
    'accent_hover': '#0077ed',
    'accent_pressed': '#006edb',
    'success': '#34c759',          # Apple Green
    'success_hover': '#2db84d',
    'warning': '#ff9f0a',          # Apple Orange
    'warning_hover': '#e68f09',
    'danger': '#ff3b30',           # Apple Red
    'danger_hover': '#e6352b',
    'emergency': '#ff0000',        # 急停红色
    'border': '#d2d2d7',           # 边框
    'separator': '#e8e8ed',        # 分隔线
    'top_bar': '#fbfbfd',          # 顶栏背景
    'card_bg': '#ffffff',          # 卡片背景
    'card_shadow': '#3b3b3f',      # 阴影颜色
    'hover_bg': '#f0f0f2',         # hover 背景
}

# === 字体大小（Apple 风格层级）===
FONT_DISPLAY = 22   # 大标题
FONT_TITLE = 18     # 页面标题
FONT_LARGE = 15     # 区域标题
FONT_NORMAL = 13    # 正文
FONT_SMALL = 11     # 辅助文字
FONT_CAPTION = 10   # 最小文字

# === 系统字体 ===
SYSTEM_FONT = "SF Pro Display, -apple-system, Noto Sans CJK SC, WenQuanYi Micro Hei, Sans Serif"
MONO_FONT = "SF Mono, Menlo, Noto Mono, DejaVu Sans Mono, Monospace"


def section_title_style() -> str:
    """页面标题样式"""
    return f"""
        color: {COLORS['text_primary']};
        font-size: {FONT_DISPLAY}px;
        font-weight: 600;
        padding: 8px 0;
    """


def font(size: int = FONT_NORMAL, bold: bool = False, family: str = SYSTEM_FONT) -> QFont:
    """创建字体对象"""
    return QFont(family, size, QFont.Bold if bold else QFont.Normal)


def mono_font(size: int = FONT_NORMAL, bold: bool = False) -> QFont:
    """创建等宽字体对象"""
    return font(size, bold, MONO_FONT)


def card_shadow(blur: int = 20, y: int = 4, alpha: float = 0.08) -> QGraphicsDropShadowEffect:
    """创建卡片阴影效果（Apple 风格柔和阴影）"""
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    color = QColor(COLORS['card_shadow'])
    color.setAlphaF(alpha)
    effect.setColor(color)
    return effect


# === 通用样式表 ===
def groupbox_style() -> str:
    """GroupBox 样式 - Apple 风格卡片"""
    return f"""
        QGroupBox {{
            font-size: {FONT_LARGE}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 12px;
            margin-top: 14px;
            padding: 20px 16px 12px 16px;
            background-color: {COLORS['bg_secondary']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 16px;
            padding: 0 6px;
            color: {COLORS['text_primary']};
        }}
    """


def radio_check_style() -> str:
    """单选/复选按钮样式 - Apple Toggle 风格"""
    return f"""
        QRadioButton, QCheckBox {{
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
            spacing: 8px;
            background: transparent;
        }}
        QRadioButton:hover, QCheckBox:hover {{
            color: {COLORS['accent']};
        }}
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {COLORS['border']};
            border-radius: 4px;
            background-color: {COLORS['bg_secondary']};
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QRadioButton::indicator:checked {{
            border-color: {COLORS['accent']};
            background-color: {COLORS['accent']};
        }}
        QCheckBox::indicator:checked {{
            border-color: {COLORS['accent']};
            background-color: {COLORS['accent']};
            image: none;
        }}
    """


def button_style(variant: str = 'default') -> str:
    """按钮样式 - Apple 风格
    Variants: default, primary, success, danger, warning
    """
    styles = {
        'default': {
            'bg': COLORS['bg_secondary'],
            'fg': COLORS['text_primary'],
            'hover': COLORS['hover_bg'],
            'pressed': COLORS['separator'],
            'border': COLORS['border'],
        },
        'primary': {
            'bg': COLORS['accent'],
            'fg': 'white',
            'hover': COLORS['accent_hover'],
            'pressed': COLORS['accent_pressed'],
            'border': COLORS['accent'],
        },
        'success': {
            'bg': COLORS['success'],
            'fg': 'white',
            'hover': COLORS['success_hover'],
            'pressed': '#24963e',
            'border': COLORS['success'],
        },
        'danger': {
            'bg': COLORS['danger'],
            'fg': 'white',
            'hover': COLORS['danger_hover'],
            'pressed': '#cc2f27',
            'border': COLORS['danger'],
        },
        'warning': {
            'bg': COLORS['warning'],
            'fg': 'white',
            'hover': COLORS['warning_hover'],
            'pressed': '#cc7f08',
            'border': COLORS['warning'],
        },
    }
    s = styles.get(variant, styles['default'])
    return f"""
        QPushButton {{
            background-color: {s['bg']};
            color: {s['fg']};
            border: 1px solid {s['border']};
            border-radius: 10px;
            padding: 9px 18px;
            font-size: {FONT_NORMAL}px;
            font-weight: 500;
        }}
        QPushButton:hover {{ background-color: {s['hover']}; }}
        QPushButton:pressed {{ background-color: {s['pressed']}; }}
        QPushButton:disabled {{
            background-color: {COLORS['separator']};
            color: {COLORS['text_tertiary']};
            border-color: {COLORS['separator']};
        }}
    """


def combo_style() -> str:
    """下拉框样式 - Apple 风格"""
    return f"""
        QComboBox {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 7px 12px;
            font-size: {FONT_NORMAL}px;
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            min-height: 20px;
        }}
        QComboBox:hover {{ border-color: {COLORS['accent']}; }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            width: 10px;
            height: 10px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {COLORS['separator']};
            border-radius: 8px;
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            selection-background-color: {COLORS['accent']};
            selection-color: white;
            padding: 4px;
            outline: none;
        }}
    """


def spinbox_style() -> str:
    """数值输入框样式 - Apple 风格"""
    return f"""
        QDoubleSpinBox, QSpinBox {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 6px 8px;
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
            selection-background-color: {COLORS['accent']};
            selection-color: white;
        }}
        QDoubleSpinBox:hover, QSpinBox:hover {{
            border-color: {COLORS['accent']};
        }}
        QDoubleSpinBox:focus, QSpinBox:focus {{
            border-color: {COLORS['accent']};
        }}
        QDoubleSpinBox::up-button, QSpinBox::up-button,
        QDoubleSpinBox::down-button, QSpinBox::down-button {{
            width: 18px;
            border: none;
            background: transparent;
        }}
    """


def lineedit_style() -> str:
    """文本输入框样式"""
    return f"""
        QLineEdit {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 7px 10px;
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
            selection-background-color: {COLORS['accent']};
            selection-color: white;
        }}
        QLineEdit:hover {{ border-color: {COLORS['accent']}; }}
        QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
    """


def scroll_style() -> str:
    """滚动区域样式 - Apple 风格细腻滚动条"""
    return f"""
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollBar:vertical {{
            background-color: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {COLORS['border']};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {COLORS['text_tertiary']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background-color: transparent;
            height: 8px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {COLORS['border']};
            border-radius: 4px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {COLORS['text_tertiary']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
    """


def card_style(bg: str = None, radius: int = 12) -> str:
    """卡片样式 - Apple 风格白色卡片"""
    bg = bg or COLORS['bg_secondary']
    return f"""
        background-color: {bg};
        border: 1px solid {COLORS['separator']};
        border-radius: {radius}px;
    """


def messagebox_style() -> str:
    """QMessageBox 统一样式 - Apple 风格"""
    return f"""
        QMessageBox {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
        }}
        QMessageBox QLabel {{
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
        }}
        QMessageBox QPushButton {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 8px 20px;
            font-size: {FONT_NORMAL}px;
            font-weight: 500;
            min-width: 70px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {COLORS['hover_bg']};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {COLORS['separator']};
        }}
        QMessageBox QPushButton[default="true"] {{
            background-color: {COLORS['accent']};
            color: white;
            border-color: {COLORS['accent']};
        }}
        QMessageBox QPushButton[default="true"]:hover {{
            background-color: {COLORS['accent_hover']};
        }}
    """


def textedit_style() -> str:
    """只读文本框样式（日志/构建输出）"""
    return f"""
        QTextEdit {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
            padding: 12px;
        }}
    """


def toggle_style() -> str:
    """可切换按钮样式 - 选中态高亮"""
    return f"""
        QPushButton {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
            padding: 8px 16px;
            font-size: {FONT_NORMAL}px;
        }}
        QPushButton:hover {{ background-color: {COLORS['hover_bg']}; }}
        QPushButton:checked {{
            background-color: {COLORS['accent']};
            color: white;
            border-color: {COLORS['accent']};
        }}
    """


def dialog_style() -> str:
    """QDialog / QInputDialog 统一样式 - Apple 风格（与 QMessageBox 一致）"""
    return f"""
        QDialog, QInputDialog {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
        }}
        QDialog QLabel, QInputDialog QLabel {{
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
        }}
        QDialog QLineEdit, QInputDialog QLineEdit {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 7px 10px;
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
            selection-background-color: {COLORS['accent']};
            selection-color: white;
        }}
        QDialog QLineEdit:hover, QInputDialog QLineEdit:hover {{
            border-color: {COLORS['accent']};
        }}
        QDialog QLineEdit:focus, QInputDialog QLineEdit:focus {{
            border-color: {COLORS['accent']};
        }}
        QDialog QPushButton, QInputDialog QPushButton {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 8px 20px;
            font-size: {FONT_NORMAL}px;
            font-weight: 500;
            min-width: 70px;
        }}
        QDialog QPushButton:hover, QInputDialog QPushButton:hover {{
            background-color: {COLORS['hover_bg']};
        }}
        QDialog QPushButton:pressed, QInputDialog QPushButton:pressed {{
            background-color: {COLORS['separator']};
        }}
        QDialog QPushButton[default="true"], QInputDialog QPushButton[default="true"] {{
            background-color: {COLORS['accent']};
            color: white;
            border-color: {COLORS['accent']};
        }}
        QDialog QPushButton[default="true"]:hover, QInputDialog QPushButton[default="true"]:hover {{
            background-color: {COLORS['accent_hover']};
        }}
    """


def global_style() -> str:
    """应用级全局样式 - 兜底默认控件样式（Apple 风格）

    页面内控件已通过本模块函数显式设置样式；
    这里兜底对话框等未显式样式的控件，保证整体风格统一。
    """
    return f"""
        QMainWindow {{ background-color: {COLORS['bg_primary']}; }}
        QLabel {{ color: {COLORS['text_primary']}; }}
        QPushButton {{
            background-color: {COLORS['accent']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: {FONT_NORMAL}px;
        }}
        QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
        QPushButton:pressed {{ background-color: {COLORS['accent_pressed']}; }}
        QPushButton:disabled {{
            background-color: {COLORS['border']};
            color: {COLORS['text_tertiary']};
        }}
        QComboBox, QLineEdit {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 6px 12px;
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            font-size: {FONT_NORMAL}px;
        }}
        QComboBox:hover, QLineEdit:hover {{ border-color: {COLORS['accent']}; }}
        QCheckBox, QRadioButton {{
            font-size: {FONT_NORMAL}px;
            color: {COLORS['text_primary']};
            spacing: 8px;
        }}
        {messagebox_style()}
        {dialog_style()}
    """


def sidebar_button_style() -> str:
    """侧边栏按钮样式 - Apple 风格导航按钮"""
    return f"""
        QPushButton {{
            text-align: left;
            padding: 10px 14px;
            border: none;
            border-radius: 8px;
            background-color: transparent;
            color: {COLORS['text_secondary']};
            font-size: {FONT_LARGE}px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {COLORS['hover_bg']};
            color: {COLORS['text_primary']};
        }}
        QPushButton:checked {{
            background-color: {COLORS['accent']};
            color: white;
        }}
        QPushButton:disabled {{
            color: {COLORS['text_tertiary']};
        }}
    """
