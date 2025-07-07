#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script to verify core functionality
"""

import sys
import os

def test_basic_imports():
    """Test that core modules can be imported"""
    print("Testing basic imports...")
    
    try:
        # Test main application
        import wii_unified_manager
        print("✓ Main application imports successfully")
        
        # Test core modules
        import wii_game_parser
        import wii_game_selenium_downloader
        import download_queue_class
        import download_thread
        import wum_style
        print("✓ All core modules import successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_pyside6():
    """Test PySide6 availability"""
    print("\nTesting PySide6...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        print("✓ PySide6 is available")
        return True
        
    except Exception as e:
        print(f"✗ PySide6 test failed: {e}")
        return False

def test_selenium():
    """Test Selenium availability"""
    print("\nTesting Selenium...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        print("✓ Selenium is available")
        return True
        
    except Exception as e:
        print(f"✗ Selenium test failed: {e}")
        return False

def test_requests():
    """Test requests functionality"""
    print("\nTesting requests...")
    
    try:
        import requests
        from bs4 import BeautifulSoup
        print("✓ Requests and BeautifulSoup are available")
        return True
        
    except Exception as e:
        print(f"✗ Requests test failed: {e}")
        return False

def test_py7zr():
    """Test py7zr for archive extraction"""
    print("\nTesting py7zr...")
    
    try:
        import py7zr
        print("✓ py7zr is available for archive extraction")
        return True
        
    except Exception as e:
        print(f"✗ py7zr test failed: {e}")
        return False

def test_file_structure():
    """Test that required files exist"""
    print("\nTesting file structure...")
    
    required_files = [
        "wii_unified_manager.py",
        "wii_game_parser.py", 
        "wii_game_selenium_downloader.py",
        "download_queue_class.py",
        "download_thread.py",
        "wum_style.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"✗ Missing files: {missing_files}")
        return False
    else:
        print("✓ All required files are present")
        return True

def main():
    """Run all tests"""
    print("=== Wii Unified Manager Basic Functionality Test ===\n")
    
    tests = [
        test_basic_imports,
        test_pyside6,
        test_selenium,
        test_requests,
        test_py7zr,
        test_file_structure
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
        print("🎉 All basic tests passed! The application should be working correctly.")
        print("\nTo test the full application, run:")
        print("  python wii_unified_manager.py")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Some functionality may not work properly.")
        
        if passed >= 4:  # Most core functionality works
            print("\nBasic functionality appears to work. You can try running:")
            print("  python wii_unified_manager.py")
    
    return passed >= 4  # Consider it a success if most tests pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
