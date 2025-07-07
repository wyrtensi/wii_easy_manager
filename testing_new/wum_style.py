#!/usr/bin/env python3
"""Palette and QSS style builder for Wii Unified Manager."""

# 🎨 Palette
WII_BLUE = "#5C6BC0"
WII_LIGHT_BLUE = "#C5CAE9"
WII_WHITE = "#FFFFFF"
WII_LIGHT_GRAY = "#FAFAFA"
WII_GRAY = "#E0E0E0"
WII_DARK_GRAY = "#555555"
WII_GREEN = "#66BB6A"
WII_ORANGE = "#FFB74D"

# ---------------------------------------------------------------------------
# QSS builder
# ---------------------------------------------------------------------------

def build_style() -> str:
    """Return global QSS string for the application."""
    return f"""
    *:focus {{ outline: none; }}

    QMainWindow {{
        background: {WII_LIGHT_GRAY};
        font-family: 'Segoe UI', 'Comic Sans MS', sans-serif;
        font-size: 12pt;
        color: black;
    }}

    QLabel[headerTitle="true"] {{
        background: {WII_BLUE};
        color: white;
        border-radius: 24px;
        padding: 20px;
        font-size: 24pt;
        font-weight: bold;
        min-height: 80px;
    }}

    QPushButton[nav="true"] {{
        background: {WII_BLUE};
        color: white;
        border: none;
        border-radius: 20px;
        padding: 14px 28px;
        font-size: 18pt;
    }}
    QPushButton[nav="true"]:checked {{ background: {WII_GREEN}; }}

    QPushButton {{
        background: {WII_BLUE};
        color: white;
        border-radius: 16px;
        padding: 12px 24px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background: {WII_ORANGE}; }}
    QPushButton:disabled {{ background: {WII_GRAY}; color: {WII_DARK_GRAY}; }}

    QLineEdit {{
        background: {WII_WHITE};
        color: black;
        border: 2px solid {WII_GRAY};
        border-radius: 12px;
        padding: 10px 16px;
    }}
    QLineEdit:focus {{ border-color: {WII_BLUE}; }}
    QLineEdit::placeholder {{ color: {WII_DARK_GRAY}; }}

    QListWidget {{
        background: {WII_WHITE};
        border: 2px solid {WII_GRAY};
        border-radius: 12px;
        padding: 8px;
        color: black;
    }}
    QListWidget::item {{
        border-radius: 12px;
        margin: 4px;
        padding: 10px;
    }}
    QListWidget::item:selected {{ background: {WII_LIGHT_BLUE}; color: black; }}

    QSplitter::handle {{
        background: {WII_GRAY};
        width: 2px;
    }}
    QSplitter::handle:hover {{ background: {WII_BLUE}; }}

    QStatusBar {{
        background: {WII_WHITE};
        color: black;
    }}

    QProgressBar {{
        border: 2px solid {WII_GRAY};
        border-radius: 10px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {WII_BLUE};
        border-radius: 8px;
    }}

    /* Scroll Area */
    QScrollArea {{
        border: 1px solid {WII_GRAY};
        border-radius: 12px;
        background-color: {WII_WHITE};
    }}
    QScrollBar:vertical {{
        border: none;
        background: {WII_LIGHT_GRAY};
        width: 14px;
        margin: 15px 0 15px 0;
        border-radius: 0px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {WII_BLUE};
        min-height: 30px;
        border-radius: 7px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {WII_GREEN};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        border: none;
        background: none;
        height: 0px;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}

    /* Tab Widget */
    QTabWidget::pane {{
        border: 1px solid {WII_GRAY};
        border-radius: 12px; /* Rounded corners for the pane */
        background-color: {WII_WHITE};
        padding: 5px;
    }}
    QTabBar::tab {{
        background-color: {WII_LIGHT_GRAY};
        color: {WII_BLUE};
        border: 1px solid {WII_GRAY};
        border-bottom: none;
        padding: 10px 20px; /* Increased padding for larger tabs */
        margin-right: 2px;
        border-top-left-radius: 12px; /* More rounded tabs */
        border-top-right-radius: 12px;
        font-weight: bold;
        font-size: 13pt; /* Slightly larger font for tabs */
    }}
    QTabBar::tab:selected {{
        background-color: {WII_BLUE};
        color: white;
        border-color: {WII_BLUE};
    }}
    QTabBar::tab:hover {{
        background-color: {WII_LIGHT_BLUE};
        color: {WII_DARK_GRAY};
    }}
    QTabBar::tab:disabled {{
        background-color: {WII_GRAY};
        color: {WII_DARK_GRAY};
    }}
    QTabWidget::tab-bar {{
        alignment: center;
        left: 10px; /* Add some space from the left edge */
    }}

    /* ComboBox */
    QComboBox {{
        border: 2px solid {WII_GRAY};
        border-radius: 10px;
        padding: 5px 10px;
        background-color: {WII_WHITE};
        color: {WII_DARK_GRAY};
        font-size: 12pt;
        min-height: 28px; /* Ensure decent height */
    }}
    QComboBox:focus {{
        border-color: {WII_BLUE};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: {WII_GRAY};
        border-left-style: solid;
        border-top-right-radius: 10px;
        border-bottom-right-radius: 10px;
        background: {WII_LIGHT_BLUE};
    }}
    QComboBox::down-arrow {{
        /* Using a unicode character as a placeholder for an image */
        /* image: url(./testing_new/down_arrow.png); */
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{ /* Style for the dropdown list */
        border: 2px solid {WII_BLUE};
        border-radius: 8px;
        background-color: {WII_WHITE};
        color: {WII_DARK_GRAY};
        selection-background-color: {WII_LIGHT_BLUE};
        padding: 5px;
    }}

    /* Danger Button Style */
    QPushButton[danger="true"] {{
        background-color: #EF5350; /* WII_RED */
    }}
    QPushButton[danger="true"]:hover {{
        background-color: #D32F2F; /* Darker Red */
    }}
    QPushButton[danger="true"]:pressed {{
        background-color: #B71C1C; /* Even Darker Red */
    }}

    /* Success Button Style (alternative to default blue for some actions) */
    QPushButton[success="true"] {{
        background-color: {WII_GREEN};
    }}
    QPushButton[success="true"]:hover {{
        background-color: #4CAF50; /* Darker Green */
    }}
    QPushButton[success="true"]:pressed {{
        background-color: #388E3C; /* Even Darker Green */
    }}

    """
