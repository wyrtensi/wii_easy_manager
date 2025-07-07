#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test for all the new Wii Unified Manager features
"""

import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from wii_unified_manager import WiiUnifiedManager
from wii_game_parser import WiiGame

def create_test_games():
    """Create a comprehensive set of test games"""
    return [
        WiiGame(
            title="Super Mario Galaxy",
            region="USA",
            rating="E",
            version="1.0",
            languages="EN",
            year="2007",
            players="1",
            serial="RMGE01",
            file_size="3.7 GB",
            graphics="9.5",
            sound="9.0", 
            gameplay="9.8",
            overall="9.4",
            crc="A1B2C3D4",
            verified="Yes",
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
            year="2008",
            players="1-4",
            serial="RMCE01",
            file_size="4.1 GB",
            graphics="8.8",
            sound="8.5",
            gameplay="9.2",
            overall="8.8",
            crc="B2C3D4E5",
            verified="Yes",
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
            year="2008",
            players="1-4",
            serial="RSBE01",
            file_size="7.4 GB",
            graphics="9.0",
            sound="9.5",
            gameplay="9.6",
            overall="9.4",
            crc="C3D4E5F6",
            verified="Yes",
            box_art="https://vimm.net/image/boxart/3111.jpg",
            disc_art="https://vimm.net/image/discart/3111.jpg",
            detail_url="https://vimm.net/vault/3111"
        ),
        WiiGame(
            title="The Legend of Zelda: Twilight Princess",
            region="USA",
            rating="T",
            version="1.0",
            languages="EN",
            year="2006",
            players="1",
            serial="RZDE01",
            file_size="4.4 GB",
            graphics="9.2",
            sound="9.3",
            gameplay="9.7",
            overall="9.4",
            crc="D4E5F6G7",
            verified="Yes",
            box_art="https://vimm.net/image/boxart/3112.jpg",
            disc_art="https://vimm.net/image/discart/3112.jpg",
            detail_url="https://vimm.net/vault/3112"
        ),
        WiiGame(
            title="Wii Sports",
            region="USA",
            rating="E",
            version="1.0",
            languages="EN",
            year="2006",
            players="1-4",
            serial="RSPE01",
            file_size="2.8 GB",
            graphics="8.0",
            sound="8.2",
            gameplay="8.8",
            overall="8.5",
            crc="E5F6G7H8",
            verified="Yes",
            box_art="https://vimm.net/image/boxart/3113.jpg",
            disc_art="https://vimm.net/image/discart/3113.jpg",
            detail_url="https://vimm.net/vault/3113"
        )
    ]

def create_test_downloaded_files():
    """Create some test downloaded files"""
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    test_files = [
        "Super Mario Galaxy [USA].wbfs",
        "Mario Kart Wii [USA].iso",
        "Wii Sports [USA].rvz"
    ]
    
    for filename in test_files:
        file_path = downloads_dir / filename
        if not file_path.exists():
            # Create a dummy file for testing
            with open(file_path, 'w') as f:
                f.write("# Test game file\n")
                f.write(f"# {filename}\n")
                f.write("# This is a test file for the Wii Unified Manager\n")

def main():
    app = QApplication(sys.argv)
    
    print("🎮 Starting Wii Unified Manager - Comprehensive Test")
    print("=" * 60)
    
    # Create test environment
    create_test_downloaded_files()
    
    # Create and show the main window
    window = WiiUnifiedManager()
    window.show()
    
    # Load test games
    test_games = create_test_games()
    
    # Display test games in search
    window.online_games = test_games
    window.display_online_games(test_games)
    
    # Switch to search section
    window.show_search_section()
    
    # Refresh downloaded games
    window.refresh_downloaded_games()
    
    print("✅ Application launched successfully!")
    print("\n🔧 New Features to Test:")
    print("1. 📱 Unified Interface Layout:")
    print("   - Search panel at top")
    print("   - Game lists in left panel (tabbed)")
    print("   - Game card details in right panel")
    print("   - Toggle flash management panel")
    
    print("\n2. 🎮 Improved Game Cards:")
    print("   - Tabbed interface (General, Ratings, Images)")
    print("   - All game information displayed properly")
    print("   - Reliable image loading (synchronous)")
    print("   - Modern Wii-style design")
    
    print("\n3. 📊 Status Indicators:")
    print("   - 🎮 = New game")
    print("   - ✅ = Downloaded game")
    print("   - 💾 = Game on flash drive")
    print("   - Cross-referenced between all lists")
    
    print("\n4. 💾 Flash Drive Management:")
    print("   - Collapsible management panel")
    print("   - Drive selection and refresh")
    print("   - Install/remove games")
    print("   - Status integration across interface")
    
    print("\n5. 📥 Integrated Downloads:")
    print("   - Download progress in main interface")
    print("   - No separate dialog windows")
    print("   - Queue management")
    print("   - Cancel functionality")
    
    print("\n6. 🎨 Modern Wii Design:")
    print("   - Consistent color scheme throughout")
    print("   - Proper spacing and typography")
    print("   - Hover effects and animations")
    print("   - Light, modern theme")
    
    print("\n🚀 How to Test:")
    print("1. Select different games from the search list")
    print("2. Switch between 'Поиск' and 'Скачанные' tabs")
    print("3. Toggle 'Управление флешкой' panel")
    print("4. Try the navigation buttons at top")
    print("5. Check the tabbed game card interface")
    print("6. Notice the status indicators (🎮 ✅ 💾)")
    
    print("\n" + "=" * 60)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
