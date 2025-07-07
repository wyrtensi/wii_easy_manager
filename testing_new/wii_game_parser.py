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
    download_url: str = "" # Primary download URL if determined
    download_urls: List[str] = None # All found download-related URLs
    box_art: str = ""
    disc_art: str = ""
    description: Optional[str] = None # For game card in new UI
    cover_path: Optional[str] = None # For local cover image path
    id: Optional[str] = None # Game ID from Vimm's, if available from URL

    # Поля для отслеживания состояния
    status: str = "new"  # Возможные значения: 'new', 'queued', 'downloading', 'downloaded', 'on_drive'
    local_path: str = ""

    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.download_urls is None:
            self.download_urls = []
        if self.detail_url and not self.id: # Try to extract ID from detail_url
            match = re.search(r'/vault/(\d+)', self.detail_url)
            if match:
                self.id = match.group(1)

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        # Настройка для обхода проблем с SSL (используется только при необходимости)
        self.session.verify = False # Vimm.net might have SSL issues sometimes, but generally it's fine.
                                    # Consider making this configurable or dynamically adjusting.
        # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # Already global, but good to note.

    def parse_game_details(self, detail_url: str) -> Optional[WiiGame]:
        """Парсинг детальной страницы игры для получения полной информации (старый метод, может быть неточным)"""
        # This method seems to be the older version of parsing details.
        # parse_game_details_from_url is likely more up-to-date.
        # For safety, keeping it but prefer using parse_game_details_from_url for new calls.
        logger.warning("Вызван устаревший метод parse_game_details. Рекомендуется использовать parse_game_details_from_url.")
        return self.parse_game_details_from_url(detail_url) # Delegate to the newer one

    def parse_search_results_from_file(self, file_path: str) -> List[WiiGame]:
        """Парсинг результатов поиска из локального HTML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            soup = BeautifulSoup(content, 'html.parser')
            games = []

            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                logger.warning(f"Таблица результатов не найдена в файле {file_path}")
                return games

            rows = table.find_all('tr')[1:]

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    game = WiiGame()

                    title_cell = cells[0]
                    title_link = title_cell.find('a')
                    if title_link:
                        game.title = title_link.get_text(strip=True)
                        game.detail_url = title_link.get('href', '')
                        if game.detail_url.startswith('/'):
                            game.detail_url = self.base_url + game.detail_url
                        # Extract ID from detail_url
                        id_match = re.search(r'/vault/(\d+)', game.detail_url)
                        if id_match:
                            game.id = id_match.group(1)

                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)

                    game.version = cells[2].get_text(strip=True)
                    game.languages = cells[3].get_text(strip=True) # Assuming this is languages
                    game.rating = cells[4].get_text(strip=True) # Assuming this is rating

                    if game.title:
                        games.append(game)

            logger.info(f"Найдено {len(games)} игр в файле {file_path}")
            return games

        except Exception as e:
            logger.error(f"Ошибка при парсинге файла {file_path}: {e}", exc_info=True)
            return []

    def parse_game_details_from_file(self, file_path: str) -> Optional[WiiGame]:
        """Парсинг детальной информации об игре из локального HTML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            soup = BeautifulSoup(content, 'html.parser')
            # Assuming the detail_url would be known if this file was saved from a specific game page
            # For now, we'll try to find game ID from typical page structure if possible

            game = WiiGame()

            title_element = soup.find('h1') # Often game title is in H1
            if title_element:
                game.title = title_element.text.strip()
            else: # Fallback to title tag
                title_tag = soup.find('title')
                if title_tag:
                    game.title = title_tag.text.split('-')[0].strip() # Vimm's often has "Game Title - Vimm's Lair"

            # Try to find game ID from a download form action or canonical link
            dl_form_action = soup.find("form", {"id": "dl_form"})
            if dl_form_action and dl_form_action.has_attr("action"):
                id_match = re.search(r'/dl/(\d+)/', dl_form_action['action'])
                if id_match:
                    game.id = id_match.group(1)
            if not game.id:
                canonical_link = soup.find("link", {"rel": "canonical"})
                if canonical_link and canonical_link.has_attr("href"):
                     id_match = re.search(r'/vault/(\d+)', canonical_link['href'])
                     if id_match:
                         game.id = id_match.group(1)
                         game.detail_url = canonical_link['href']


            details_map = {}
            # Find the main details table (often has 'Section - Content' rows)
            # This selector might need adjustment based on actual Vimm's Lair structure
            details_table = soup.select_one("div#romdetails table, table.tabletype1, table.tabletype0")
            if details_table:
                rows = details_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td']) # header and data cells
                    if len(cells) == 2:
                        key = cells[0].text.strip().replace(':', '')
                        value_cell = cells[1]
                        # Extract text, handling nested tags like <a> or <span> if any
                        value_parts = [elem.strip() for elem in value_cell.find_all(string=True, recursive=True) if elem.strip()]
                        value = " ".join(value_parts)
                        details_map[key] = value

            game.serial = details_map.get('Serial')
            game.version = details_map.get('Version')
            game.languages = details_map.get('Languages', details_map.get('Language(s)'))
            game.players = details_map.get('Players')
            game.year = details_map.get('Release Date', '').split(',')[-1].strip() # Get year
            game.file_size = details_map.get('Size', details_map.get('File Size'))
            game.crc = details_map.get('CRC32', details_map.get('CRC'))
            game.verified = details_map.get('Verified') # Often 'Good Dump' or similar
            game.region = details_map.get('Region')
            game.rating = details_map.get('User Rating') # Or some other rating field

            # Description often in a div with class 'main zwölfpalmensans greytext' or similar
            desc_div = soup.select_one("div.main.zwölfpalmensans.greytext, div#romdetails > p")
            if desc_div:
                game.description = desc_div.text.strip()

            # Ratings (stars)
            ratings_section = soup.find('div', id='ratings') # Common ID for ratings section
            if ratings_section:
                ratings_map = {}
                rating_rows = ratings_section.find_all('tr')
                for r_row in rating_rows:
                    r_header = r_row.find('th')
                    r_value_cell = r_row.find('td')
                    if r_header and r_value_cell:
                        r_name = r_header.text.strip().lower().replace(":", "")
                        # Count full stars, Vimm's uses images like star_full.png
                        r_val = len(r_value_cell.find_all('img', src=lambda s: s and 'star_full.png' in s))
                        # Could also count half stars: len(r_value_cell.find_all('img', src=lambda s: s and 'star_half.png' in s)) * 0.5
                        ratings_map[r_name] = str(r_val)

                game.graphics = ratings_map.get('graphics')
                game.sound = ratings_map.get('sound')
                game.gameplay = ratings_map.get('gameplay')
                if 'overall' in ratings_map : game.overall = ratings_map['overall']
                elif 'average' in ratings_map: game.overall = ratings_map['average']


            # Images (box art, disc art)
            if game.id: # If we have game ID, construct image URLs
                game.box_art = f"https://dl.vimm.net/image.php?type=box&id={game.id}"
                game.disc_art = f"https://dl.vimm.net/image.php?type=cart&id={game.id}" # 'cart' is often used for disc on Vimm's
            else: # Fallback to finding images on page
                box_art_img = soup.select_one("div#romart img[alt*='Box'], div#romart img[src*='type=box']")
                if box_art_img and box_art_img.has_attr('src'):
                    game.box_art = self.base_url + box_art_img['src'] if box_art_img['src'].startswith('/') else box_art_img['src']

                disc_art_img = soup.select_one("div#romart img[alt*='Disc'], div#romart img[alt*='Cartridge'], div#romart img[src*='type=cart']")
                if disc_art_img and disc_art_img.has_attr('src'):
                    game.disc_art = self.base_url + disc_art_img['src'] if disc_art_img['src'].startswith('/') else disc_art_img['src']

            # Download URL
            download_form = soup.find('form', id='dl_form')
            if download_form and download_form.has_attr('action'):
                 game.download_url = self.base_url + download_form['action'] if download_form['action'].startswith('/') else download_form['action']

            if game.title:
                 logger.info(f"Извлечена детальная информация для игры: {game.title} из файла {file_path}")
                 return game
            else:
                logger.warning(f"Не удалось извлечь достаточно информации из файла {file_path}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной информации из файла {file_path}: {e}", exc_info=True)
            return None

    def download_image_from_page(self, image_url: str, referer_url: str) -> Optional[bytes]:
        """Загрузка изображения со страницы с правильными заголовками"""
        try:
            # Ensure URL is absolute
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = self.base_url + image_url

            headers = {
                'User-Agent': self.session.headers['User-Agent'], # Use session's UA
                'Referer': referer_url, # Crucial for Vimm's image server
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                # Add other headers if Vimm's becomes stricter
            }

            response = self.session.get(image_url, headers=headers, timeout=15) # Use session for consistency
            response.raise_for_status() # Check for HTTP errors

            if 'image' in response.headers.get('content-type', '').lower():
                return response.content
            else:
                logger.warning(f"Загруженный контент не является изображением: {image_url}, тип: {response.headers.get('content-type')}")
                return None

        except requests.RequestException as e:
            logger.error(f"Ошибка сети при загрузке изображения {image_url}: {e}")
            return None
        except Exception as e: # Catch any other error
            logger.error(f"Неожиданная ошибка при загрузке изображения {image_url}: {e}", exc_info=True)
            return None

    def parse_game_details_from_url(self, url: str) -> Optional[WiiGame]:
        """Парсинг детальной информации об игре по URL (более новый метод)"""
        try:
            logger.info(f"Запрос деталей игры по URL: {url}")
            response = self.session.get(url, timeout=20) # Increased timeout
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            game = WiiGame(detail_url=url) # Initialize with detail_url

            # Extract Game ID from URL
            id_match = re.search(r'/vault/(\d+)', url)
            if id_match:
                game.id = id_match.group(1)

            # Title (try H1 first, then title tag)
            title_h1 = soup.select_one('div.mainContent > h1, h1#romTitle') # More specific selectors
            if title_h1:
                game.title = title_h1.text.strip()
            else:
                title_tag = soup.find('title')
                if title_tag:
                    game.title = title_tag.text.split('-')[0].strip() # "Game Title - Vimm's Lair"

            # Details Table
            details_map = {}
            details_table = soup.select_one("div#romdetails table, table.tabletype1, table.tabletype0") # Common tables for details
            if details_table:
                rows = details_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) == 2:
                        key = cells[0].text.strip().replace(':', '')
                        value_cell = cells[1]
                        value_parts = [elem.strip() for elem in value_cell.find_all(string=True, recursive=True) if elem.strip()]
                        value = " ".join(value_parts)
                        details_map[key.lower()] = value # Use lower keys for easier access

            game.serial = details_map.get('serial')
            game.version = details_map.get('version')
            game.languages = details_map.get('languages', details_map.get('language(s)'))
            game.players = details_map.get('players')
            game.year = details_map.get('release date', '').split(',')[-1].strip()
            game.file_size = details_map.get('size', details_map.get('file size'))
            game.crc = details_map.get('crc32', details_map.get('crc'))
            game.verified = details_map.get('verified', details_map.get('dump status')) # e.g., "Good Dump"
            game.region = details_map.get('region')
            game.rating = details_map.get('user rating', details_map.get('rating')) # User Rating or Metacritic

            # Description
            desc_el = soup.select_one("div#romdetails > p:not(:has(table)), div.gameDescription") # Paragraph in romdetails or specific class
            if desc_el:
                game.description = "\n".join([p.text.strip() for p in desc_el.find_all('p')]) if desc_el.find('p') else desc_el.text.strip()


            # Ratings (stars)
            ratings_section = soup.find('div', id='ratings')
            if ratings_section:
                ratings_map = {}
                rating_rows = ratings_section.find_all('tr')
                for r_row in rating_rows:
                    r_header = r_row.find('th')
                    r_value_cell = r_row.find('td')
                    if r_header and r_value_cell:
                        r_name = r_header.text.strip().lower().replace(":", "")
                        r_val = len(r_value_cell.find_all('img', src=lambda s: s and 'star_full.png' in s))
                        half_stars = len(r_value_cell.find_all('img', src=lambda s: s and 'star_half.png' in s))) * 0.5
                        ratings_map[r_name] = str(r_val + half_stars)

                game.graphics = ratings_map.get('graphics')
                game.sound = ratings_map.get('sound')
                game.gameplay = ratings_map.get('gameplay')
                if 'overall' in ratings_map : game.overall = ratings_map['overall']
                elif 'average' in ratings_map: game.overall = ratings_map['average']

            # Images (Box Art, Disc Art)
            # Using game.id is more reliable if available
            if game.id:
                # Construct direct image URLs. These might change, so parsing page is a fallback.
                game.box_art = f"https://dl.vimm.net/img/{game.id}_box.jpg" # Guessed common pattern
                game.disc_art = f"https://dl.vimm.net/img/{game.id}_cart.png" # Guessed common pattern for disc/cart
                # Fallback to image.php if direct links fail during actual display
                # game.box_art_php = f"https://dl.vimm.net/image.php?type=box&id={game.id}"
                # game.disc_art_php = f"https://dl.vimm.net/image.php?type=cart&id={game.id}"
            else: # Fallback: try to find images on the page if ID method fails or ID not found
                art_section = soup.find('div', id='romart')
                if art_section:
                    box_art_img = art_section.find('img', alt=re.compile(r'Box Art', re.I))
                    if box_art_img and box_art_img.has_attr('src'):
                        src = box_art_img['src']
                        game.box_art = self.base_url + src if src.startswith('/') else src

                    disc_art_img = art_section.find('img', alt=re.compile(r'Disc Art|Cartridge', re.I))
                    if disc_art_img and disc_art_img.has_attr('src'):
                        src = disc_art_img['src']
                        game.disc_art = self.base_url + src if src.startswith('/') else src

            # Download URL (from the main download button/form)
            download_form = soup.find('form', id='dl_form')
            if download_form and download_form.has_attr('action'):
                action_url = download_form['action']
                game.download_url = self.base_url + action_url if action_url.startswith('/') else action_url

            if game.title:
                logger.info(f"Успешно извлечены детали для игры: {game.title} (ID: {game.id})")
            else:
                logger.warning(f"Не удалось извлечь название игры из URL: {url}")
            return game

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка при парсинге деталей из URL {url}: {e.response.status_code} - {e.response.reason}")
            return None
        except requests.RequestException as e:
            logger.error(f"Ошибка сети при парсинге деталей из URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге деталей из URL {url}: {e}", exc_info=True)
            return None

    def search_games_online(self, query: str, console: str = "Wii") -> List[WiiGame]:
        """Поиск игр онлайн на сайте vimm.net"""
        try:
            if not query or len(query) < 1: # Adjusted minimum query length if necessary
                logger.warning("Поисковый запрос слишком короткий.")
                return []

            search_url = f"{self.base_url}/vault/"
            params = {
                'p': 'list',
                'system': console,
                'q': query
            }

            logger.info(f"Поиск игр онлайн: {search_url} с параметрами {params}")

            response = self.session.get(search_url, params=params, timeout=20) # Increased timeout
            response.raise_for_status() # Will raise HTTPError for 4xx/5xx

            soup = BeautifulSoup(response.text, 'html.parser')
            games: List[WiiGame] = []

            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                logger.warning(f"Таблица результатов не найдена для запроса '{query}'.")
                # Check for messages like "No results found"
                no_results_msg = soup.find(string=re.compile(r"no results found", re.I))
                if no_results_msg:
                    logger.info(f"На сайте Vimm's Lair нет результатов для запроса: '{query}'")
                return games # Return empty list if no table

            rows = table.find_all('tr')[1:]

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5: # Expect at least 5 columns: Title, Region, Version, Languages, Rating
                    game = WiiGame()

                    title_cell = cells[0]
                    title_link = title_cell.find('a')
                    if title_link:
                        game.title = title_link.get_text(strip=True)
                        href = title_link.get('href', '')
                        game.detail_url = self.base_url + href if href.startswith('/') else href
                        # Extract ID from detail_url
                        id_match = re.search(r'/vault/(\d+)', game.detail_url)
                        if id_match:
                            game.id = id_match.group(1)
                    else:
                        game.title = title_cell.get_text(strip=True) # Fallback if no link

                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)

                    game.version = cells[2].get_text(strip=True)
                    # Assuming column 4 is Languages and 5 is Rating based on typical Vimm's layout
                    # This might need adjustment if the table structure changes
                    game.languages = cells[3].get_text(strip=True)
                    game.rating = cells[4].get_text(strip=True)

                    if game.title:
                        games.append(game)

            logger.info(f"Найдено {len(games)} игр онлайн по запросу: '{query}'")
            return games

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Ошибка 404 (Не найдено) при онлайн поиске '{query}'. Ресурс не найден.")
            else:
                logger.error(f"HTTP ошибка при онлайн поиске '{query}': {e.response.status_code} - {e.response.reason}")
            return []
        except requests.exceptions.SSLError as e:
            logger.error(f"Ошибка SSL при онлайн поиске '{query}': {e}")
            logger.info("Попробуйте использовать локальные HTML файлы или проверьте соединение/настройки SSL.")
            return []
        except requests.exceptions.Timeout:
            logger.error(f"Тайм-аут при онлайн поиске '{query}'. Сервер не ответил вовремя.")
            return []
        except requests.exceptions.RequestException as e: # Catch other network related errors
            logger.error(f"Ошибка сети при онлайн поиске '{query}': {e}")
            return []
        except Exception as e: # Catch any other unexpected error during parsing
            logger.error(f"Неожиданная ошибка при онлайн поиске '{query}': {e}", exc_info=True)
            return []


class WiiGameDatabase:
    """Класс для работы с базой данных игр"""

    def __init__(self, db_path: str = "wii_games.json"):
        self.db_path = Path(db_path) # Use Path object
        self.games: List[WiiGame] = []
        self.load_database()

    def load_database(self):
        """Загрузка базы данных из файла"""
        try:
            if self.db_path.exists():
                with self.db_path.open('r', encoding='utf-8') as file:
                    data = json.load(file)
                    self.games = [WiiGame(**game_data) for game_data in data]
                logger.info(f"Загружено {len(self.games)} игр из базы данных: {self.db_path}")
            else:
                logger.info(f"Файл базы данных {self.db_path} не найден, будет создан новый при сохранении.")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON из файла {self.db_path}: {e}. Файл может быть поврежден.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке базы данных {self.db_path}: {e}", exc_info=True)

    def save_database(self):
        """Сохранение базы данных в файл"""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.db_path.open('w', encoding='utf-8') as file:
                json.dump([game.to_dict() for game in self.games], file,
                         indent=2, ensure_ascii=False)
            logger.info(f"База данных сохранена ({len(self.games)} игр) в: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении базы данных в {self.db_path}: {e}", exc_info=True)

    def update_game(self, updated_game: WiiGame) -> bool:
        """Обновление информации о существующей игре в базе данных или добавление новой, если не найдена."""
        # Идентифицируем игру по ID, если есть, иначе по detail_url или названию
        lookup_succeeded = False
        if updated_game.id:
            for i, game in enumerate(self.games):
                if game.id == updated_game.id:
                    self.games[i] = updated_game
                    lookup_succeeded = True
                    break
        elif updated_game.detail_url:
            for i, game in enumerate(self.games):
                if game.detail_url == updated_game.detail_url:
                    self.games[i] = updated_game
                    lookup_succeeded = True
                    break

        if not lookup_succeeded: # Fallback to title if other identifiers failed or not present
             for i, game in enumerate(self.games):
                if game.title.lower() == updated_game.title.lower() and \
                   (not game.region or not updated_game.region or game.region == updated_game.region): # Optional region match
                    self.games[i] = updated_game
                    lookup_succeeded = True
                    break

        if lookup_succeeded:
            logger.info(f"Информация об игре '{updated_game.title}' обновлена в базе.")
        else:
            self.games.append(updated_game) # Add as new game if not found
            logger.info(f"Игра '{updated_game.title}' добавлена как новая в базу.")

        self.save_database()
        return True


    def add_games(self, new_games: List[WiiGame], update_existing: bool = True):
        """Добавление списка игр в базу данных. Обновляет существующие, если update_existing=True."""
        added_count = 0
        updated_count = 0
        for new_game in new_games:
            existing_game = None
            if new_game.id:
                existing_game = next((g for g in self.games if g.id == new_game.id), None)
            elif new_game.detail_url:
                 existing_game = next((g for g in self.games if g.detail_url == new_game.detail_url), None)

            if existing_game:
                if update_existing:
                    # Update existing game fields from new_game if new_game has more info
                    for field, value in asdict(new_game).items():
                        if value or isinstance(value, bool): # Update if new value is not empty/None
                             setattr(existing_game, field, value)
                    updated_count +=1
            else: # Game not found by ID or detail_url, try by title as a weaker match
                title_match = self.find_game_by_title(new_game.title)
                if title_match and update_existing:
                     for field, value in asdict(new_game).items():
                        if value or isinstance(value, bool):
                             setattr(title_match, field, value)
                     updated_count += 1
                elif not title_match : # If no match by title either, add as new
                    self.games.append(new_game)
                    added_count += 1

        if added_count > 0 or updated_count > 0:
            self.save_database()
            logger.info(f"Добавлено {added_count} новых игр, обновлено {updated_count} существующих игр в базе данных.")

    def find_game_by_title(self, title: str) -> Optional[WiiGame]:
        """Поиск игры по названию (точное совпадение, без учета регистра)"""
        title_lower = title.lower()
        for game in self.games:
            if game.title.lower() == title_lower:
                return game
        return None

    def search_games(self, query: str) -> List[WiiGame]:
        """Поиск игр по запросу в названии, регионе или языках (частичное совпадение, без учета регистра)"""
        if not query:
            return list(self.games) # Return a copy

        query_lower = query.lower()
        results = [
            game for game in self.games
            if query_lower in game.title.lower() or \
               (game.region and query_lower in game.region.lower()) or \
               (game.languages and query_lower in game.languages.lower()) or \
               (game.serial and query_lower in game.serial.lower())
        ]
        return results

    def filter_games(self, region: Optional[str] = None, rating: Optional[str] = None,
                     min_rating_overall: Optional[float] = None) -> List[WiiGame]:
        """Фильтрация игр по критериям"""
        results = list(self.games) # Start with a copy

        if region:
            results = [game for game in results if game.region and region.lower() in game.region.lower()]

        if rating: # This might be string like "E for Everyone" or numerical "4.5/5"
            results = [game for game in results if game.rating and rating.lower() in game.rating.lower()]

        if min_rating_overall is not None:
            results = [game for game in results
                      if self._extract_rating_value(game.overall) >= min_rating_overall]

        return results

    def _extract_rating_value(self, rating_str: Optional[str]) -> float:
        """Извлечение числового значения рейтинга из строки (e.g., "4.5/5 stars", "85/100")"""
        if not rating_str:
            return 0.0
        try:
            # Try to find patterns like "X/Y" or "X out of Y" or just a number
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:/|out of)\s*(\d+)', rating_str)
            if match:
                value = float(match.group(1))
                base = float(match.group(2))
                return (value / base) * 5.0 if base != 5.0 else value # Normalize to 5-star scale if different
            else: # Try to find a standalone number (assuming it's out of 5 or needs context)
                match_single = re.search(r'(\d+(?:\.\d+)?)', rating_str)
                if match_single:
                    return float(match_single.group(1)) # Could be ambiguous
        except ValueError: # Handle cases where conversion to float fails
            pass
        except Exception: # Catch any other regex or conversion error
            pass
        return 0.0 # Default if no parsable rating found

    def get_statistics(self) -> Dict:
        """Получение статистики по играм"""
        stats = {
            'total_games': len(self.games),
            'regions': {},
            'ratings_text': {}, # To store textual ratings like "E", "T", "M"
            'years': {}
        }

        for game in self.games:
            region_key = game.region or 'Unknown'
            stats['regions'][region_key] = stats['regions'].get(region_key, 0) + 1

            rating_key = game.rating or 'Unknown' # This is likely ESRB or similar
            stats['ratings_text'][rating_key] = stats['ratings_text'].get(rating_key, 0) + 1

            year_key = game.year or 'Unknown'
            stats['years'][year_key] = stats['years'].get(year_key, 0) + 1

        return stats


def main():
    """Главная функция для тестирования парсера"""
    parser = WiiGameParser()
    database = WiiGameDatabase(db_path="test_wii_games.json") # Use a test DB path

    # Test online search
    print("\n--- Тест онлайн поиска ---")
    # mario_games = parser.search_games_online("mario")
    # if mario_games:
    #     print(f"Найдено {len(mario_games)} игр 'Mario':")
    #     for g in mario_games[:2]: print(f"  {g.title} (ID: {g.id}, URL: {g.detail_url})")
    #     database.add_games(mario_games, update_existing=True)
    # else:
    #     print("Игры 'Mario' не найдены онлайн.")

    # Test search for 'a' (should trigger 404 or specific handling)
    a_games = parser.search_games_online("a")
    if not a_games:
        print("Поиск по 'a' не дал результатов или была ошибка (ожидаемо).")

    # Test detail parsing from URL (if a game was found)
    # if mario_games and mario_games[0].detail_url:
    #     print(f"\n--- Тест парсинга деталей для {mario_games[0].title} ---")
    #     detailed_game = parser.parse_game_details_from_url(mario_games[0].detail_url)
    #     if detailed_game:
    #         print(f"  Заголовок: {detailed_game.title}")
    #         print(f"  Размер: {detailed_game.file_size}")
    #         print(f"  Год: {detailed_game.year}")
    #         print(f"  Описание: {detailed_game.description[:100] if detailed_game.description else 'N/A'}...")
    #         print(f"  Box Art: {detailed_game.box_art}")
    #         print(f"  Download URL: {detailed_game.download_url}")
    #         database.update_game(detailed_game) # Update this game in DB
    #     else:
    #         print(f"Не удалось получить детали для {mario_games[0].title}")

    # Test with a known problematic URL or ID if available for 404 on details page
    # print("\n--- Тест парсинга деталей с неверного URL ---")
    # non_existent_game = parser.parse_game_details_from_url(f"{parser.base_url}/vault/00000") # Non-existent ID
    # if not non_existent_game:
    #     print("Парсинг деталей с неверного URL обработан корректно (нет игры).")

    # Show some DB stats
    print("\n--- Статистика базы данных (test_wii_games.json) ---")
    stats = database.get_statistics()
    print(f"  Всего игр в базе: {stats['total_games']}")
    if stats['regions']: print(f"  Регионы (пример): {list(stats['regions'].items())[:3]}")
    if stats['ratings_text']: print(f"  Рейтинги (пример): {list(stats['ratings_text'].items())[:3]}")

    # Clean up test database file
    # if Path("test_wii_games.json").exists():
    #     Path("test_wii_games.json").unlink()
    #     print("\nТестовая база данных test_wii_games.json удалена.")

if __name__ == "__main__":
    main()
