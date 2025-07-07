#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wii Game Parser and Browser
Парсер и браузер игр Wii для сайта vimm.net
"""

import os
import re
import json
import logging
import ssl
import urllib3
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
import requests

# Отключаем предупреждения SSL для проблемных сайтов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WiiGame:
    """Структура данных для хранения информации об игре Wii"""
    title: str = ""
    region: str = ""
    version: str = ""
    languages: str = ""
    rating: str = ""
    detail_url: str = ""

    # Дополнительные поля с детальной страницы
    serial: str = ""
    players: str = ""
    year: str = ""
    graphics: str = ""
    sound: str = ""
    gameplay: str = ""
    overall: str = ""
    crc: str = ""
    verified: str = ""
    file_size: str = ""
    download_url: str = "" # Primary direct download link if available
    download_urls: List[str] = None # Could be multiple mirrors or alternative links

    box_art: str = ""
    disc_art: str = ""

    # Поля для отслеживания состояния
    status: str = "new"  # Возможные значения: 'new', 'queued', 'downloading', 'downloaded', 'error', 'on_drive'
    local_path: str = "" # Path to downloaded file
    description: Optional[str] = None # For GameCard
    cover_path: Optional[str] = None # For GameCard if using local images


    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.download_urls is None:
            self.download_urls = []

    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return asdict(self)

    def __str__(self) -> str:
        """Строковое представление игры"""
        return f"{self.title} ({self.region}) - {self.rating}"


class WiiGameParser:
    """Парсер для извлечения информации об играх Wii"""

    def __init__(self, base_url: str = "https://vimm.net"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # Настройка для обхода проблем с SSL
        self.session.verify = False
        # self.session.trust_env = False # This might be too aggressive, usually verify=False is enough.

    def parse_game_details(self, detail_url: str) -> Optional[WiiGame]:
        """Парсинг детальной страницы игры для получения полной информации (старый метод, может быть не нужен)"""
        # This method seems less complete than parse_game_details_from_url, keeping for reference if needed
        # but parse_game_details_from_url is likely the one to use.
        logger.warning("parse_game_details is an older method, consider using parse_game_details_from_url")
        return self.parse_game_details_from_url(detail_url) # Delegate to the more complete one

    def parse_search_results_from_file(self, file_path: str) -> List[WiiGame]:
        """Парсинг результатов поиска из локального HTML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            soup = BeautifulSoup(content, 'html.parser')
            games = []

            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                # Try another common table structure from Vimm's
                table = soup.find('table', id='list')

            if not table:
                logger.warning(f"Таблица результатов не найдена в файле: {file_path}")
                return games

            rows = table.find_all('tr')
            if not rows or len(rows) < 2 : # Check if there's at least one data row besides header
                 logger.warning(f"Не найдено строк с данными в таблице файла: {file_path}")
                 return games

            # Skip header row(s) - Vimm's can have one or two header rows
            data_row_start_index = 0
            for i, row in enumerate(rows):
                if row.find('td'): # First row with <td> is likely data
                    data_row_start_index = i
                    break
            if data_row_start_index == 0 and rows[0].find('th'): # If still 0 and first has <th>, it's a header
                 data_row_start_index = 1


            for row in rows[data_row_start_index:]:
                cells = row.find_all('td')
                if len(cells) >= 5: # Ensure enough cells
                    game = WiiGame()

                    title_cell = cells[0]
                    title_link = title_cell.find('a')
                    if title_link:
                        game.title = title_link.get_text(strip=True)
                        game.detail_url = title_link.get('href', '')
                        if game.detail_url.startswith('/'):
                            game.detail_url = self.base_url + game.detail_url
                    else: # If no link, try to get text directly (less ideal)
                        game.title = title_cell.get_text(strip=True)

                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)

                    game.version = cells[2].get_text(strip=True)
                    # Languages often in cell 3, Rating in cell 4 (0-indexed)
                    # This can vary, so be careful
                    if len(cells) > 3: game.languages = cells[3].get_text(strip=True)
                    if len(cells) > 4: game.rating = cells[4].get_text(strip=True) # Or a sub-element for rating

                    if game.title:
                        games.append(game)

            logger.info(f"Найдено {len(games)} игр в файле {file_path}")
            return games

        except Exception as e:
            logger.error(f"Ошибка при парсинге файла {file_path}: {e}")
            return []

    def parse_game_details_from_file(self, file_path: str) -> Optional[WiiGame]:
        """Парсинг детальной информации об игре из локального HTML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            soup = BeautifulSoup(content, 'html.parser')
            # This assumes the file content is similar to what parse_game_details_from_url expects
            return self._extract_details_from_soup(soup, "file://"+file_path)

        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной информации из файла {file_path}: {e}")
            return None

    def _extract_details_from_soup(self, soup: BeautifulSoup, page_url: str) -> Optional[WiiGame]:
        game = WiiGame(detail_url=page_url)

        # Title from <title> tag or a prominent <h1>
        title_tag = soup.find('title')
        if title_tag:
            game.title = title_tag.text.split(' - ')[0].split('(')[0].strip() # More robust title cleaning

        h1_title = soup.find('h1') # Often contains the title as well
        if not game.title and h1_title:
             game.title = h1_title.get_text(strip=True)


        # Details table: Vimm.net uses a table inside a div with id="romdetails"
        details_section = soup.find('div', id='romdetails')
        if details_section:
            details_table = details_section.find('table')
            if details_table:
                rows = details_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].text.strip().lower().replace(':', '')
                        value = cells[1].text.strip()
                        if 'serial' in key: game.serial = value
                        elif 'version' in key: game.version = value
                        elif 'languages' in key: game.languages = value
                        elif 'players' in key: game.players = value
                        elif 'release date' in key: game.year = value.split(',')[-1].strip()
                        elif 'file size' in key: game.file_size = value
                        elif 'crc32' in key: game.crc = value
                        elif 'verified' in key: game.verified = value
                        elif 'region' in key and not game.region: game.region = value # If not already set

        # Ratings from div id="ratings"
        ratings_section = soup.find('div', id='ratings')
        if ratings_section:
            ratings_table = ratings_section.find('table')
            if ratings_table:
                rows = ratings_table.find_all('tr')
                for row in rows:
                    header = row.find('th')
                    value_cell = row.find('td')
                    if header and value_cell:
                        rating_name = header.text.strip().lower()
                        # Rating often represented by number of star_full.png images
                        rating_value = str(len(value_cell.find_all('img', src=re.compile(r'star_full\.png'))))
                        if 'graphics' in rating_name: game.graphics = rating_value
                        elif 'sound' in rating_name: game.sound = rating_value
                        elif 'gameplay' in rating_name: game.gameplay = rating_value
                        elif 'overall' in rating_name: game.overall = rating_value


        # Art from div id="romart"
        # Box art usually has alt text containing "Box Art" or is the first image
        # Disc art alt text contains "Disc Art" or is the second/third image
        art_section = soup.find('div', id='romart')
        if art_section:
            images = art_section.find_all('img')
            if images:
                # Try to find by alt text first
                box_art_img = art_section.find('img', alt=re.compile(r'Box Art', re.I))
                if box_art_img and box_art_img.has_attr('src'):
                    game.box_art = box_art_img['src']
                elif len(images) > 0 and images[0].has_attr('src'): # Fallback to first image
                    game.box_art = images[0]['src']

                disc_art_img = art_section.find('img', alt=re.compile(r'Disc Art', re.I))
                if disc_art_img and disc_art_img.has_attr('src'):
                    game.disc_art = disc_art_img['src']
                elif len(images) > 1 and images[1].has_attr('src') and 'cart' in images[1]['src'].lower(): # Vimm uses 'cart' for disc
                     game.disc_art = images[1]['src']
                elif len(images) > 2 and images[2].has_attr('src') and 'cart' in images[2]['src'].lower(): # Sometimes it's 3rd
                     game.disc_art = images[2]['src']


            # Ensure URLs are absolute
            if game.box_art and game.box_art.startswith('/'): game.box_art = self.base_url + game.box_art
            if game.disc_art and game.disc_art.startswith('/'): game.disc_art = self.base_url + game.disc_art

        # Download URL: Often a form with action="/dl/..." or a direct link
        download_form = soup.find('form', action=re.compile(r'/dl/\?mediaId=\d+'))
        if download_form and download_form.has_attr('action'):
            game.download_url = self.base_url + download_form['action']
        else: # Fallback: look for a prominent download button/link
            dl_button = soup.find(['button', 'a'], string=re.compile(r'Download', re.I))
            if dl_button and dl_button.has_attr('href'):
                 game.download_url = dl_button['href']
                 if game.download_url.startswith('/'): game.download_url = self.base_url + game.download_url
            elif dl_button and dl_button.has_attr('onclick'): # Sometimes it's JS
                onclick_val = dl_button['onclick']
                match = re.search(r"location\.href='(/dl/\?mediaId=\d+)'", onclick_val)
                if match:
                    game.download_url = self.base_url + match.group(1)


        if not game.title: # If title is still missing, it's not a valid game page
            logger.warning(f"Не удалось извлечь название игры со страницы: {page_url}")
            return None

        logger.info(f"Получена детальная информация для игры: {game.title if game.title else 'Unknown Title'}")
        return game

    def parse_game_details_from_url(self, url: str) -> Optional[WiiGame]:
        """Парсинг детальной информации об игре по URL"""
        try:
            # Ensure full URL
            full_url = url if url.startswith('http') else self.base_url + url

            response = self.session.get(full_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            return self._extract_details_from_soup(soup, full_url)

        except requests.RequestException as e:
            logger.error(f"Ошибка сети при загрузке деталей игры {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге деталей игры {url}: {e}")
            return None

    def search_games_online(self, query: str, console: str = "Wii") -> List[WiiGame]:
        """Поиск игр онлайн на сайте vimm.net"""
        try:
            search_url = f"{self.base_url}/vault/"
            params = {
                'p': 'list',
                'system': console,
                'q': query
            }

            logger.info(f"Поиск игр онлайн: {search_url} с параметрами {params}")

            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            games = []

            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                table = soup.find('table', id='list') # Alternative table ID

            if not table:
                logger.warning(f"Таблица результатов не найдена для запроса: {query}")
                return games

            data_row_start_index = 0
            all_rows = table.find_all('tr')
            if not all_rows: return games # No rows at all

            for i, row_check in enumerate(all_rows):
                if row_check.find('td'):
                    data_row_start_index = i
                    break
            if data_row_start_index == 0 and all_rows[0].find('th'):
                 data_row_start_index = 1


            for row in all_rows[data_row_start_index:]:
                cells = row.find_all('td')
                if len(cells) >= 5: # Expect at least 5 columns: Title, Region, Version, Languages, Rating
                    game = WiiGame()

                    title_cell = cells[0]
                    title_link = title_cell.find('a')
                    if title_link:
                        game.title = title_link.get_text(strip=True)
                        game.detail_url = title_link.get('href', '')
                        if game.detail_url.startswith('/'):
                            game.detail_url = self.base_url + game.detail_url
                    else:
                         game.title = title_cell.get_text(strip=True) # Fallback if no link

                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)

                    game.version = cells[2].get_text(strip=True)
                    if len(cells) > 3: game.languages = cells[3].get_text(strip=True) # Languages
                    if len(cells) > 4: game.rating = cells[4].get_text(strip=True) # Rating

                    if game.title:
                        games.append(game)

            logger.info(f"Найдено {len(games)} игр онлайн по запросу: {query}")
            return games

        except requests.exceptions.SSLError as e:
            logger.error(f"Ошибка SSL при онлайн поиске: {e}. Попробуйте обновить certifi: pip install --upgrade certifi")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при онлайн поиске: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при онлайн поиске: {e}")
            return []


class WiiGameDatabase:
    """Класс для работы с базой данных игр"""

    def __init__(self, db_path: str = "wii_games.json"):
        self.db_path = db_path
        self.games: List[WiiGame] = [] # This will store WiiGame objects
        self.load_database()

    def load_database(self):
        """Загрузка базы данных из файла"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    # Ensure data is a list of dicts before creating WiiGame objects
                    if isinstance(data, list):
                        self.games = [WiiGame(**game_data) for game_data in data if isinstance(game_data, dict)]
                    else:
                        self.games = [] # Or handle error for malformed DB file
                        logger.error("База данных повреждена: ожидался список объектов.")
                logger.info(f"Загружено {len(self.games)} игр из базы данных: {self.db_path}")
            else:
                logger.info(f"База данных не найдена ({self.db_path}), создается новая при первом сохранении.")
                self.games = [] # Ensure games list is empty if DB file doesn't exist
        except json.JSONDecodeError:
            logger.error(f"Ошибка декодирования JSON в файле базы данных: {self.db_path}. Будет создана новая база.")
            self.games = []
        except Exception as e:
            logger.error(f"Ошибка при загрузке базы данных {self.db_path}: {e}")
            self.games = [] # Reset to empty list on any other load error

    def save_database(self):
        """Сохранение базы данных в файл"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as file:
                json.dump([game.to_dict() for game in self.games], file,
                         indent=2, ensure_ascii=False)
            logger.info(f"База данных сохранена ({len(self.games)} игр) в: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении базы данных {self.db_path}: {e}")

    def add_games(self, new_games: List[WiiGame]):
        """
        Добавление или обновление игр в базе данных.
        Игры идентифицируются по detail_url или по title+region если detail_url нет.
        """
        updated_count = 0
        added_count = 0
        for new_game in new_games:
            found_existing = False
            for i, existing_game in enumerate(self.games):
                # Primary key: detail_url if available
                if new_game.detail_url and existing_game.detail_url == new_game.detail_url:
                    # Update existing game with new details, preferring non-empty new values
                    for attr, value in asdict(new_game).items():
                        if value or getattr(existing_game, attr) is None : # Update if new value is not empty or old was None
                             setattr(self.games[i], attr, value)
                    updated_count +=1
                    found_existing = True
                    break
                # Fallback key: title and region (less reliable)
                elif not new_game.detail_url and existing_game.title == new_game.title and existing_game.region == new_game.region:
                    for attr, value in asdict(new_game).items():
                         if value or getattr(existing_game, attr) is None:
                             setattr(self.games[i], attr, value)
                    updated_count +=1
                    found_existing = True
                    break

            if not found_existing:
                self.games.append(new_game)
                added_count += 1

        if added_count > 0:
            logger.info(f"Добавлено {added_count} новых игр в базу данных (ожидает сохранения).")
        if updated_count > 0:
            logger.info(f"Обновлено {updated_count} существующих игр в базе данных (ожидает сохранения).")
        # Removed: self.save_database() - Main application should control when to save.

    def get_all_games(self) -> List[WiiGame]:
        """Возвращает все игры из базы."""
        return self.games

    def find_game_by_title(self, title: str) -> Optional[WiiGame]:
        """Поиск игры по названию (первое совпадение)"""
        title_lower = title.lower()
        for game in self.games:
            if game.title.lower() == title_lower:
                return game
        return None

    def search_games(self, query: str) -> List[WiiGame]:
        """Поиск игр по запросу в названии, регионе или языках."""
        if not query:
            return self.games # Return all if query is empty

        query_lower = query.lower()
        results = []

        for game in self.games:
            match = False
            if query_lower in game.title.lower():
                match = True
            elif game.region and query_lower in game.region.lower():
                match = True
            elif game.languages and query_lower in game.languages.lower():
                match = True
            elif game.serial and query_lower in game.serial.lower(): # Search by serial too
                match = True

            if match:
                results.append(game)

        return results

    def filter_games(self, region: str = None, rating: str = None,
                     min_rating: float = None) -> List[WiiGame]:
        """Фильтрация игр по критериям"""
        results = list(self.games) # Start with a copy

        if region:
            results = [game for game in results if game.region and region.lower() in game.region.lower()]

        if rating: # Assuming rating is a string like "4 stars" or just "4"
            results = [game for game in results if game.rating and rating in game.rating]

        if min_rating is not None:
            results = [game for game in results
                      if self._extract_rating_value(game.overall or game.rating) >= min_rating] # Check overall or general rating

        return results

    def _extract_rating_value(self, rating_str: str) -> float:
        """Извлечение числового значения рейтинга (e.g., from '4.5/5 stars' or '4')"""
        if not rating_str: return 0.0
        try:
            # Try to find a number, possibly float, at the start of the string or after '/'
            match = re.search(r'(\d+(?:\.\d+)?)', rating_str)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0 # Default if no number found

    def get_statistics(self) -> Dict:
        """Получение статистики по играм"""
        stats = {
            'total_games': len(self.games),
            'regions': {},
            'ratings': {}, # Could be more complex if ratings are parsed numerically
            'years': {}
        }

        for game in self.games:
            region = game.region or 'Unknown'
            stats['regions'][region] = stats['regions'].get(region, 0) + 1

            # For ratings, let's count distinct string values
            rating_str = game.overall or game.rating or 'Unknown'
            stats['ratings'][rating_str] = stats['ratings'].get(rating_str, 0) + 1

            year = game.year or 'Unknown'
            stats['years'][year] = stats['years'].get(year, 0) + 1

        return stats


def main():
    """Главная функция для тестирования парсера"""
    parser = WiiGameParser()
    database = WiiGameDatabase("test_db.json") # Use a test DB

    # Example: Search online
    print("Тестирование онлайн поиска...")
    online_games = parser.search_games_online("Mario Kart")
    if online_games:
        print(f"Найдено онлайн: {len(online_games)} игр.")
        database.add_games(online_games)
        database.save_database() # Explicit save for testing this part

        # Example: Get details for the first found game
        if online_games[0].detail_url:
            print(f"\nТестирование получения деталей для: {online_games[0].title}")
            detailed_game = parser.parse_game_details_from_url(online_games[0].detail_url)
            if detailed_game:
                print(f"  Серийный номер: {detailed_game.serial}")
                print(f"  Размер файла: {detailed_game.file_size}")
                print(f"  Арт обложки: {detailed_game.box_art}")
                database.add_games([detailed_game]) # Update with details
                database.save_database()
    else:
        print("Онлайн поиск не дал результатов.")

    # Test loading from DB
    print("\nТестирование загрузки из БД...")
    db_loaded = WiiGameDatabase("test_db.json")
    print(f"Загружено из test_db.json: {len(db_loaded.games)} игр.")
    if db_loaded.games:
        print(f"Первая игра из БД: {db_loaded.games[0].title}, Серийный: {db_loaded.games[0].serial}")

    # Clean up test DB
    if os.path.exists("test_db.json"):
        os.remove("test_db.json")

if __name__ == "__main__":
    main()
