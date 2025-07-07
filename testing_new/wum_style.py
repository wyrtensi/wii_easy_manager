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
        color: {WII_DARK_GRAY}; /* Changed from black for consistency */
    }}

    QLabel {{ /* Default QLabel style */
        color: {WII_DARK_GRAY};
        padding: 2px; /* Add some default padding */
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
        color: {WII_DARK_GRAY}; /* Changed from black */
    }}
    QListWidget::item {{
        border-radius: 12px;
        margin: 4px;
        padding: 10px;
        color: {WII_DARK_GRAY}; /* Ensure item text is dark */
    }}
    QListWidget::item:selected {{ background: {WII_LIGHT_BLUE}; color: {WII_DARK_GRAY}; }} /* Ensure selected item text is dark */

    QSplitter::handle {{
        background: {WII_GRAY};
        width: 2px;
    }}
    QSplitter::handle:hover {{ background: {WII_BLUE}; }}

    QStatusBar {{
        background: {WII_WHITE};
        color: {WII_DARK_GRAY}; /* Changed from black */
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
    """
