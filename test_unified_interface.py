#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the unified interface design
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from wii_unified_manager import WiiUnifiedManager

def main():
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = WiiUnifiedManager()
    window.show()
    
    # Add some test data
    from wii_game_parser import WiiGame
    
    test_games = [
        WiiGame(
            title="Super Mario Galaxy",
            region="USA",
            rating="E",
            version="1.0",
            languages="EN",
            box_art="https://vimm.net/image/boxart/3109.jpg",
            disc_art="https://vimm.net/image/discart/3109.jpg",
            detail_url="https://vimm.net/vault/3109"
        ),
        WiiGame(
            title="Mario Kart Wii",
            region="USA", 
            rating="E",
            version="1.0",
            languages="EN",
            box_art="https://vimm.net/image/boxart/3110.jpg",
            disc_art="https://vimm.net/image/discart/3110.jpg",
            detail_url="https://vimm.net/vault/3110"
        ),
        WiiGame(
            title="Super Smash Bros. Brawl",
            region="USA",
            rating="T",
            version="1.0", 
            languages="EN",
            box_art="https://vimm.net/image/boxart/3111.jpg",
            disc_art="https://vimm.net/image/discart/3111.jpg",
            detail_url="https://vimm.net/vault/3111"
        )
    ]
    
    # Display test games
    window.online_games = test_games
    window.display_online_games(test_games)
    
    print("✅ Unified interface test launched successfully!")
    print("🎮 Test games loaded in search tab")
    print("🔍 Try selecting different games to see the improved card")
    print("💾 Toggle flash management to see the new panels")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
