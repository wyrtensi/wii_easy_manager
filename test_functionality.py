#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify key functionality
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        import wii_unified_manager
        print("✓ wii_unified_manager imported successfully")
        
        import wii_game_parser
        print("✓ wii_game_parser imported successfully")
        
        import wii_game_selenium_downloader
        print("✓ wii_game_selenium_downloader imported successfully")
        
        import download_queue_class
        print("✓ download_queue_class imported successfully")
        
        import download_thread
        print("✓ download_thread imported successfully")
        
        import wum_style
        print("✓ wum_style imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_parser_basic():
    """Test basic parser functionality"""
    print("\nTesting parser...")
    
    try:
        from wii_game_parser import WiiGameParser
        
        parser = WiiGameParser()
        print("✓ Parser created successfully")
        
        # Test search with a simple query
        games = parser.search_games("mario")
        print(f"✓ Search returned {len(games)} games")
        
        if games:
            game = games[0]
            print(f"✓ First game: {game.title}")
            
            # Test detail parsing
            detailed = parser.parse_game_details_from_url(game.detail_url)
            if detailed:
                print("✓ Game details parsed successfully")
                print(f"  - Title: {detailed.title}")
                print(f"  - Region: {getattr(detailed, 'region', 'Unknown')}")
                print(f"  - Size: {getattr(detailed, 'size', 'Unknown')}")
            else:
                print("✗ Failed to parse game details")
                
        return True
        
    except Exception as e:
        print(f"✗ Parser test failed: {e}")
        return False

def test_download_queue():
    """Test download queue functionality"""
    print("\nTesting download queue...")
    
    try:
        from download_queue_class import DownloadQueue
        from wii_game_parser import WiiGame
        
        queue = DownloadQueue()
        print("✓ Download queue created successfully")
        
        # Create a dummy game
        game = WiiGame()
        game.title = "Test Game"
        game.id = "TEST001"
        game.detail_url = "https://example.com"
        
        # Test adding to queue
        queue.add(game)
        print("✓ Game added to queue")
        
        print(f"✓ Queue size: {queue.size()}")
        
        return True
        
    except Exception as e:
        print(f"✗ Download queue test failed: {e}")
        return False

def test_drive_functionality():
    """Test drive/USB functionality"""
    print("\nTesting drive functionality...")
    
    try:
        from wii_download_manager.models.enhanced_drive import EnhancedDrive
        
        drives = EnhancedDrive.get_drives()
        print(f"✓ Found {len(drives)} drives")
        
        for drive in drives:
            print(f"  - Drive {drive.letter}: {drive.label} ({drive.format_size(drive.free_space)} free)")
            
        return True
        
    except Exception as e:
        print(f"✗ Drive test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Wii Unified Manager Functionality Test ===\n")
    
    tests = [
        test_imports,
        test_parser_basic,
        test_download_queue,
        test_drive_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
    
    print(f"\n=== Test Results: {passed}/{total} passed ===")
    
    if passed == total:
        print("🎉 All tests passed! The application appears to be working correctly.")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Some functionality may not work properly.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
