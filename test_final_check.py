#!/usr/bin/env python3
"""
Финальная проверка всех методов и функций
"""

import sys
from PySide6.QtWidgets import QApplication
from wii_unified_manager import WiiUnifiedManager

def test_methods():
    """Тест всех методов"""
    print("🔍 Проверка методов Wii Unified Manager...")
    
    # Создаем приложение
    app = QApplication(sys.argv)
    
    # Создаем менеджер
    manager = WiiUnifiedManager()
    
    # Проверяем ключевые методы
    methods_to_check = [
        'create_search_page',
        'create_manager_page', 
        'perform_search',
        'show_search_section',
        'show_manager_section',
        'on_game_selected',
        'show_game_card',
        'download_game',
        'refresh_downloaded_games',
        'refresh_flash_games',
        'refresh_drives',
        'toggle_flash_panel',
        'install_selected_to_flash',
        'delete_downloaded_game',
        'add_external_games',
        'remove_from_flash'
    ]
    
    missing_methods = []
    for method in methods_to_check:
        if hasattr(manager, method):
            print(f"✅ {method}")
        else:
            print(f"❌ {method}")
            missing_methods.append(method)
    
    if not missing_methods:
        print("🎉 Все методы найдены!")
        
        # Проверяем атрибуты интерфейса
        ui_elements = [
            'search_input',
            'online_games_list',
            'downloaded_games_list',
            'flash_games_list',
            'games_tabs',
            'flash_panel',
            'card_layout',
            'download_panel'
        ]
        
        missing_elements = []
        for element in ui_elements:
            if hasattr(manager, element):
                print(f"✅ UI: {element}")
            else:
                print(f"❌ UI: {element}")
                missing_elements.append(element)
        
        if not missing_elements:
            print("🎉 Все элементы интерфейса найдены!")
        else:
            print(f"⚠️  Отсутствуют элементы: {missing_elements}")
    else:
        print(f"⚠️  Отсутствуют методы: {missing_methods}")
    
    # Проверяем работу базовых функций
    print("\n🧪 Тестирование базовых функций...")
    
    try:
        # Тест поиска
        manager.search_input.setText("Super Mario")
        print("✅ Поиск: текст установлен")
        
        # Тест навигации
        manager.show_search_section()
        print("✅ Навигация: переход на поиск")
        
        manager.show_manager_section()
        print("✅ Навигация: переход на менеджер")
        
        # Тест панели флешки
        manager.toggle_flash_panel()
        print("✅ Панель флешки: переключение")
        
        print("🎉 Все тесты пройдены!")
        
    except Exception as e:
        print(f"❌ Ошибка в тестах: {e}")
    
    app.quit()

if __name__ == "__main__":
    test_methods()
