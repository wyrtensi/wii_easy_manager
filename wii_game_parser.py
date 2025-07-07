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
    download_url: str = ""
    download_urls: List[str] = None
    box_art: str = ""
    disc_art: str = ""
    
    # Поля для отслеживания состояния
    status: str = "new"  # Возможные значения: 'new', 'downloaded', 'on_drive'
    local_path: str = ""

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
        self.session.trust_env = False
        
    def parse_game_details(self, detail_url: str) -> Optional[WiiGame]:
        """Парсинг детальной страницы игры для получения полной информации"""
        try:
            full_url = f"{self.base_url}{detail_url}" if not detail_url.startswith('http') else detail_url
            response = self.session.get(full_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            game = WiiGame(detail_url=detail_url)

            # Находим основную информацию
            main_section = soup.find('div', id='romdetails')
            if not main_section:
                logger.error(f"Не удалось найти секцию 'romdetails' на странице: {full_url}")
                return None

            # Извлекаем данные из таблицы
            details_table = main_section.find('table')
            if details_table:
                rows = details_table.find_all('tr')
                details_map = {}
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].text.strip().replace(':', '')
                        value = cells[1].text.strip()
                        details_map[key] = value
                
                game.serial = details_map.get('Serial')
                game.version = details_map.get('Version')
                game.languages = details_map.get('Languages')
                game.players = details_map.get('Players')
                game.year = details_map.get('Release Date', '').split(',')[-1].strip()
                game.file_size = details_map.get('File Size')
                game.crc = details_map.get('CRC32')
                game.verified = details_map.get('Verified')

            # Извлекаем оценки
            ratings_section = soup.find('div', id='ratings')
            if ratings_section:
                ratings_table = ratings_section.find('table')
                if ratings_table:
                    rows = ratings_table.find_all('tr')
                    for row in rows:
                        header = row.find('th')
                        value = row.find('td')
                        if header and value:
                            rating_name = header.text.strip()
                            rating_value = len(row.find_all('img', src=re.compile(r'star_full.png')))
                            
                            if 'Graphics' in rating_name:
                                game.graphics = str(rating_value)
                            elif 'Sound' in rating_name:
                                game.sound = str(rating_value)
                            elif 'Gameplay' in rating_name:
                                game.gameplay = str(rating_value)
                            elif 'Overall' in rating_name:
                                game.overall = str(rating_value)

            # Извлекаем изображения
            art_section = soup.find('div', id='romart')
            if art_section:
                # Обложка
                box_art_img = art_section.find('img', alt=re.compile(r'Box Art'))
                if box_art_img and box_art_img.has_attr('src'):
                    game.box_art = self.base_url + box_art_img['src']

                # Диск
                disc_art_img = art_section.find('img', alt=re.compile(r'Disc Art'))
                if disc_art_img and disc_art_img.has_attr('src'):
                    game.disc_art = self.base_url + disc_art_img['src']
            
            # Извлекаем заголовок игры
            title_tag = soup.find('title')
            if title_tag:
                game.title = title_tag.text.split('-')[0].strip()

            # Находим ссылку на загрузку (может потребовать дополнительной логики)
            download_form = soup.find('form', action=re.compile(r'/dl/'))
            if download_form:
                game.download_url = self.base_url + download_form['action']

            return game
            
        except requests.RequestException as e:
            logger.error(f"Ошибка сети при загрузке деталей игры {detail_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге деталей игры {detail_url}: {e}")
            return None
        
    def parse_search_results_from_file(self, file_path: str) -> List[WiiGame]:
        """Парсинг результатов поиска из локального HTML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            games = []
            
            # Находим таблицу с результатами по классу
            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                logger.warning("Таблица результатов не найдена")
                return games
                
            # Пропускаем заголовок таблицы
            rows = table.find_all('tr')[1:]  # Пропускаем первую строку (заголовок)
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    game = WiiGame()
                    
                    # Извлекаем название игры и ссылку
                    title_cell = cells[0]
                    title_link = title_cell.find('a')
                    if title_link:
                        game.title = title_link.get_text(strip=True)
                        game.detail_url = title_link.get('href', '')
                        if game.detail_url.startswith('/'):
                            game.detail_url = self.base_url + game.detail_url
                    
                    # Извлекаем остальные поля
                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)
                    
                    game.version = cells[2].get_text(strip=True)
                    game.languages = cells[3].get_text(strip=True)
                    game.rating = cells[4].get_text(strip=True)
                    
                    if game.title:  # Добавляем только если есть название
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
            game = WiiGame()
            
            # Извлекаем название из заголовка
            title_element = soup.find('h1')
            if title_element:
                game.title = title_element.get_text(strip=True)
            
            # Извлекаем информацию из таблицы
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    field_name = cells[0].get_text(strip=True)
                    field_value = cells[2].get_text(strip=True)
                    
                    # Сопоставляем поля
                    if field_name == "Serial":
                        game.serial = field_value
                    elif field_name == "Region":
                        game.region = field_value
                    elif field_name == "Players":
                        game.players = field_value
                    elif field_name == "Year":
                        game.year = field_value
                    elif field_name == "Graphics":
                        game.graphics = field_value
                    elif field_name == "Sound":
                        game.sound = field_value
                    elif field_name == "Gameplay":
                        game.gameplay = field_value
                    elif field_name == "Overall":
                        game.overall = field_value
                    elif field_name == "CRC":
                        game.crc = field_value
                    elif field_name == "Verified":
                        game.verified = field_value
            
            # Извлекаем размер файла
            size_element = soup.find('td', {'id': 'dl_size'})
            if size_element:
                game.file_size = size_element.get_text(strip=True)
            
            # Извлекаем изображения
            box_img = soup.find('img', {'alt': 'Box'})
            if box_img:
                game.box_art = box_img.get('src', '')
            
            disc_img = soup.find('img', {'alt': 'Disc'})
            if disc_img:
                game.disc_art = disc_img.get('src', '')
            
            logger.info(f"Извлечена детальная информация для игры: {game.title}")
            return game
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной информации из файла {file_path}: {e}")
            return None
    
    def download_image_from_page(self, image_url: str, referer_url: str) -> Optional[bytes]:
        """Загрузка изображения со страницы с правильными заголовками"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': referer_url,
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin'
            })
            session.verify = False
            
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = self.base_url + image_url
            
            response = session.get(image_url, timeout=15)
            if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
                return response.content
            else:
                logger.warning(f"Не удалось загрузить изображение: {image_url}, статус: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке изображения {image_url}: {e}")
            return None

    def parse_game_details_from_url(self, url: str) -> Optional[WiiGame]:
        """Парсинг детальной информации об игре по URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            game = WiiGame()
            
            # Извлекаем название из заголовка
            title_element = soup.find('h1')
            if title_element:
                game.title = title_element.get_text(strip=True)
            
            # Извлекаем информацию из таблицы
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    field_name = cells[0].get_text(strip=True)
                    field_value = cells[2].get_text(strip=True)
                    
                    # Сопоставляем поля
                    if field_name == "Serial":
                        game.serial = field_value
                    elif field_name == "Region":
                        game.region = field_value
                    elif field_name == "Players":
                        game.players = field_value
                    elif field_name == "Year":
                        game.year = field_value
                    elif field_name == "Graphics":
                        game.graphics = field_value
                    elif field_name == "Sound":
                        game.sound = field_value
                    elif field_name == "Gameplay":
                        game.gameplay = field_value
                    elif field_name == "Overall":
                        game.overall = field_value
                    elif field_name == "CRC":
                        game.crc = field_value
                    elif field_name == "Verified":
                        game.verified = field_value
            
            # Извлекаем размер файла из JavaScript массива allMedia
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'allMedia' in script.string:
                    script_content = script.string
                    # Ищем ZippedText в allMedia
                    try:
                        # Извлекаем JSON из JavaScript
                        start = script_content.find('allMedia=[') + 10
                        end = script_content.find('];', start)
                        if start > 9 and end > start:
                            json_str = script_content[start:end]
                            media_data = json.loads(json_str)
                            if media_data and len(media_data) > 0:
                                game.file_size = media_data[0].get('ZippedText', '')
                                break
                    except Exception:
                        pass
            
            # Если не нашли в скрипте, пытаемся найти элемент с id="dl_size"
            if not game.file_size:
                size_element = soup.find('td', {'id': 'dl_size'})
                if size_element:
                    game.file_size = size_element.get_text(strip=True)
            
            # Если все еще не нашли, ищем в тексте
            if not game.file_size:
                size_elements = soup.find_all(string=re.compile(r'\d+\.\d+\s*[MG]B'))
                if size_elements:
                    game.file_size = size_elements[0].strip()
            
            # Извлекаем изображения
            # Получаем ID игры из URL (например, из https://vimm.net/vault/17243)
            game_id = None
            id_match = re.search(r'/vault/(\d+)', url)
            if id_match:
                game_id = id_match.group(1)
            
            if game_id:
                # Формируем ссылки на изображения
                box_url = f"https://dl.vimm.net/image.php?type=box&id={game_id}"
                disc_url = f"https://dl.vimm.net/image.php?type=cart&id={game_id}"
                
                # Загружаем изображения и конвертируем в base64
                import base64
                
                box_data = self.download_image_from_page(box_url, url)
                if box_data:
                    box_b64 = base64.b64encode(box_data).decode('utf-8')
                    game.box_art = f"data:image/jpeg;base64,{box_b64}"
                
                disc_data = self.download_image_from_page(disc_url, url)
                if disc_data:
                    disc_b64 = base64.b64encode(disc_data).decode('utf-8')
                    game.disc_art = f"data:image/jpeg;base64,{disc_b64}"
            else:
                # Альтернативный способ - ищем изображения в div с display:inline-block
                image_div = soup.find('div', style=lambda x: x and 'display:inline-block' in x)
                if image_div:
                    # Обложка
                    box_img = image_div.find('img', {'alt': 'Box'})
                    if box_img:
                        src = box_img.get('src', '')
                        if src.startswith('//'):
                            game.box_art = 'https:' + src
                        elif src.startswith('/'):
                            game.box_art = self.base_url + src
                        else:
                            game.box_art = src
                    
                    # Диск
                    disc_img = image_div.find('img', src=lambda x: x and 'type=cart' in x)
                    if disc_img:
                        src = disc_img.get('src', '')
                        if src.startswith('//'):
                            game.disc_art = 'https:' + src
                        elif src.startswith('/'):
                            game.disc_art = self.base_url + src
                        else:
                            game.disc_art = src
            
            # Извлекаем ссылки на скачивание
            download_links = soup.find_all('a', href=lambda x: x and 'download' in x)
            game.download_urls = []
            for link in download_links:
                href = link.get('href', '')
                if href.startswith('/'):
                    href = self.base_url + href
                game.download_urls.append(href)
            
            logger.info(f"Получена детальная информация для игры: {game.title}")
            return game
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной информации из URL {url}: {e}")
            return None
    
    def search_games_online(self, query: str, console: str = "Wii") -> List[WiiGame]:
        """Поиск игр онлайн на сайте vimm.net"""
        try:
            # Используем правильный URL для поиска
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
            
            # Ищем таблицу с результатами (такую же как в локальных файлах)
            table = soup.find('table', {'class': 'rounded centered cellpadding1 hovertable striped'})
            if not table:
                logger.warning("Таблица результатов не найдена в онлайн поиске")
                return games
                
            rows = table.find_all('tr')[1:]  # Пропускаем заголовок
            
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
                    
                    region_cell = cells[1]
                    region_img = region_cell.find('img', class_='flag')
                    if region_img:
                        game.region = region_img.get('title', '')
                    else:
                        game.region = region_cell.get_text(strip=True)
                    
                    game.version = cells[2].get_text(strip=True)
                    game.languages = cells[3].get_text(strip=True)
                    game.rating = cells[4].get_text(strip=True)
                    
                    if game.title:
                        games.append(game)
            
            logger.info(f"Найдено {len(games)} игр онлайн по запросу: {query}")
            return games
            
        except requests.exceptions.SSLError as e:
            logger.error(f"Ошибка SSL при онлайн поиске: {e}")
            logger.info("Попробуйте использовать локальные HTML файлы вместо онлайн поиска")
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
        self.games: List[WiiGame] = []
        self.load_database()
    
    def load_database(self):
        """Загрузка базы данных из файла"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    self.games = [WiiGame(**game_data) for game_data in data]
                logger.info(f"Загружено {len(self.games)} игр из базы данных")
            else:
                logger.info("База данных не найдена, создается новая")
        except Exception as e:
            logger.error(f"Ошибка при загрузке базы данных: {e}")
    
    def save_database(self):
        """Сохранение базы данных в файл"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as file:
                json.dump([game.to_dict() for game in self.games], file, 
                         indent=2, ensure_ascii=False)
            logger.info(f"База данных сохранена ({len(self.games)} игр)")
        except Exception as e:
            logger.error(f"Ошибка при сохранении базы данных: {e}")

    def update_game(self, updated_game: WiiGame):
        """Обновление информации о существующей игре в базе данных."""
        # Идентифицируем игру по уникальному серийному номеру или URL
        lookup_key = updated_game.serial or updated_game.detail_url
        if not lookup_key:
            logger.warning(f"Невозможно обновить игру '{updated_game.title}' без уникального идентификатора.")
            return False

        for i, game in enumerate(self.games):
            current_key = game.serial or game.detail_url
            if current_key == lookup_key:
                self.games[i] = updated_game
                self.save_database()
                logger.info(f"Статус игры '{updated_game.title}' обновлен на '{updated_game.status}'.")
                return True
        
        logger.warning(f"Не удалось найти игру '{updated_game.title}' для обновления.")
        return False

    def add_games(self, games: List[WiiGame]):
        """Добавление игр в базу данных"""
        added_count = 0
        for game in games:
            if not self.find_game_by_title(game.title):
                self.games.append(game)
                added_count += 1
        
        if added_count > 0:
            self.save_database()
            logger.info(f"Добавлено {added_count} новых игр в базу данных")
    
    def find_game_by_title(self, title: str) -> Optional[WiiGame]:
        """Поиск игры по названию"""
        for game in self.games:
            if game.title.lower() == title.lower():
                return game
        return None
    
    def search_games(self, query: str) -> List[WiiGame]:
        """Поиск игр по запросу"""
        if not query:
            return self.games
        
        query_lower = query.lower()
        results = []
        
        for game in self.games:
            if (query_lower in game.title.lower() or 
                query_lower in game.region.lower() or
                query_lower in game.languages.lower()):
                results.append(game)
        
        return results
    
    def filter_games(self, region: str = None, rating: str = None, 
                     min_rating: float = None) -> List[WiiGame]:
        """Фильтрация игр по критериям"""
        results = self.games
        
        if region:
            results = [game for game in results if game.region == region]
        
        if rating:
            results = [game for game in results if game.rating == rating]
        
        if min_rating is not None:
            results = [game for game in results 
                      if self._extract_rating_value(game.overall) >= min_rating]
        
        return results
    
    def _extract_rating_value(self, rating_str: str) -> float:
        """Извлечение числового значения рейтинга"""
        try:
            # Ищем числовое значение в строке рейтинга
            match = re.search(r'(\d+(?:\.\d+)?)', rating_str)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0
    
    def get_statistics(self) -> Dict:
        """Получение статистики по играм"""
        stats = {
            'total_games': len(self.games),
            'regions': {},
            'ratings': {},
            'years': {}
        }
        
        for game in self.games:
            # Статистика по регионам
            region = game.region or 'Unknown'
            stats['regions'][region] = stats['regions'].get(region, 0) + 1
            
            # Статистика по рейтингам
            rating = game.rating or 'Unknown'
            stats['ratings'][rating] = stats['ratings'].get(rating, 0) + 1
            
            # Статистика по годам
            year = game.year or 'Unknown'
            stats['years'][year] = stats['years'].get(year, 0) + 1
        
        return stats


def main():
    """Главная функция для тестирования парсера"""
    # Создаем парсер
    parser = WiiGameParser()
    
    # Создаем базу данных
    database = WiiGameDatabase()
    
    # Проверяем наличие HTML файлов в текущей директории
    current_dir = Path.cwd()
    search_files = list(current_dir.glob("*Search Results*.html"))
    detail_files = list(current_dir.glob("*Call of Duty 3*.html"))
    
    if search_files:
        print(f"Найден файл с результатами поиска: {search_files[0]}")
        games = parser.parse_search_results_from_file(str(search_files[0]))
        print(f"Извлечено {len(games)} игр:")
        for game in games[:5]:  # Показываем первые 5 игр
            print(f"  - {game}")
        
        # Добавляем игры в базу данных
        database.add_games(games)
    
    if detail_files:
        print(f"\nНайден файл с детальной информацией: {detail_files[0]}")
        game_details = parser.parse_game_details_from_file(str(detail_files[0]))
        if game_details:
            print("Детальная информация об игре:")
            print(f"  Название: {game_details.title}")
            print(f"  Серийный номер: {game_details.serial}")
            print(f"  Регион: {game_details.region}")
            print(f"  Игроки: {game_details.players}")
            print(f"  Год: {game_details.year}")
            print(f"  Графика: {game_details.graphics}")
            print(f"  Звук: {game_details.sound}")
            print(f"  Геймплей: {game_details.gameplay}")
            print(f"  Общий рейтинг: {game_details.overall}")
            print(f"  CRC: {game_details.crc}")
            print(f"  Размер файла: {game_details.file_size}")
    
    # Показываем статистику
    stats = database.get_statistics()
    print("\nСтатистика базы данных:")
    print(f"  Всего игр: {stats['total_games']}")
    print(f"  Регионы: {dict(list(stats['regions'].items())[:3])}")
    print(f"  Рейтинги: {dict(list(stats['ratings'].items())[:3])}")


if __name__ == "__main__":
    main()
