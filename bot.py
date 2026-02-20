import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import random
import time
import re
from datetime import datetime, timedelta
import threading
import logging
from logging.handlers import RotatingFileHandler
import json
import os
import sys

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('bot_system.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('vk_chat_bot')

# ==================== КОНФИГУРАЦИЯ ====================
# Токен VK для чат-бота
GROUP_ID = 232134257
VK_TOKEN_CHAT = "vk1.a.rg8v6onM6zdD4DRqdsyQZlyCbt_31_hWaSi1EUxAamHmzL6Z7IPUDUXA1CI7YHCiR3QbegNi5iR7Nvkogm5NjM3gUbZ5vyN35rqBy5BqWhbaFwj0IkfUdxahdMb5dpQGAlfdBiYJU7DVLOdJKVXALJN1TadfOnSEJb0sDKUuEFZeMaWDzsvftsF-ZXsMO_g6X3Ov4qOnpZk0XuAmYlKS6g"

# Файлы для хранения данных чат-бота
ADMINS_FILE = 'admins.json'
MODERATORS_FILE = 'moderators.json'
USERS_FILE = 'users.json'
MUTED_FILE = 'muted.json'
CHATS_FILE = 'active_chats.json'
SILENCE_MODE_FILE = 'silence_mode.json'
AUTOKICK_FILE = 'autokick.json'
CHAT_CATEGORIES_FILE = 'chat_categories.json'
BLACKLIST_FILE = 'blacklist.json'
BLACKLIST_HISTORY_FILE = 'blacklist_history.json'
LOGS_DIR = 'logs'
LEADERSHIP_FILE = 'leadership.json'
LOCAL_ADMINS_FILE = 'local_admins.json'
LOCAL_MODERATORS_FILE = 'local_moderators.json'
ADMIN_LEVELS_FILE = 'admin_levels.json'
ADMIN_LEVEL_NAMES_FILE = 'admin_level_names.json'
NEWS_CHANNELS_FILE = 'news_channels.json'
NEWS_HISTORY_FILE = 'news_history.json'
SETUP_ADMINS_FILE = 'setup_admins.json'
COMMAND_ACCESS_FILE = 'command_access.json'

# Уровни администраторов (7 уровней) - 1 самый низкий, 7 самый высокий
DEFAULT_ADMIN_LEVELS = {
    1: "Модератор",
    2: "Старший Модератор", 
    3: "Администратор",
    4: "Главный Администратор",
    5: "Со-Владелец",
    6: "Владелец",
    7: "Основатель"
}

# Загружаем названия уровней из файла или используем значения по умолчанию
def load_admin_level_names():
    if os.path.exists(ADMIN_LEVEL_NAMES_FILE):
        try:
            with open(ADMIN_LEVEL_NAMES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_ADMIN_LEVELS.copy()
    return DEFAULT_ADMIN_LEVELS.copy()

def save_admin_level_names(names):
    try:
        with open(ADMIN_LEVEL_NAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(names, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения названий уровней: {e}")

ADMIN_LEVELS = load_admin_level_names()

# ==================== ОБЩИЕ ФУНКЦИИ ====================
def get_random_id():
    return random.getrandbits(63)

def get_user_mention(vk, user_id):
    """Получает упоминание пользователя"""
    try:
        user_info = vk.users.get(user_ids=user_id)
        if user_info:
            user = user_info[0]
            return f"[id{user_id}|{user['first_name']} {user['last_name']}]"
        return f"[id{user_id}|Пользователь]"
    except Exception as e:
        logger.error(f"Ошибка получения упоминания для {user_id}: {e}")
        return f"[id{user_id}|Пользователь]"

def get_user_name(vk, user_id):
    """Получает имя пользователя"""
    try:
        user_info = vk.users.get(user_ids=user_id)
        if user_info:
            user = user_info[0]
            return f"{user['first_name']} {user['last_name']}"
        return f"Пользователь (ID{user_id})"
    except Exception as e:
        logger.error(f"Ошибка получения имени для {user_id}: {e}")
        return f"Пользователь (ID{user_id})"

def extract_user_id(text, vk=None):
    """Извлекает ID пользователя из текста"""
    # Поиск упоминания [id123|Name]
    mention_match = re.search(r'\[id(\d+)\|', text)
    if mention_match:
        return int(mention_match.group(1))
    
    # Поиск ссылки vk.com/id123
    link_match = re.search(r'vk\.com/id(\d+)', text, re.IGNORECASE)
    if link_match:
        return int(link_match.group(1))
    
    # Поиск прямой ссылки с https://
    https_link_match = re.search(r'https?://vk\.com/id(\d+)', text, re.IGNORECASE)
    if https_link_match:
        return int(https_link_match.group(1))
    
    # Поиск чистого ID
    id_match = re.search(r'^(\d+)$', text.strip())
    if id_match:
        return int(id_match.group(1))
    
    # Поиск ID в тексте
    any_id_match = re.search(r'id(\d+)', text, re.IGNORECASE)
    if any_id_match:
        return int(any_id_match.group(1))
    
    return None

# ==================== КЛАСС ДЛЯ РАБОТЫ С ФАЙЛАМИ ДАННЫХ ====================
class DataManager:
    """Менеджер для работы с данными чат-бота"""
    
    @staticmethod
    def load_data(filename, default=dict):
        """Загружает данные из файла"""
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки файла {filename}: {e}")
                if callable(default):
                    return default()
                return default
        if callable(default):
            return default()
        return default
    
    @staticmethod
    def save_data(data, filename):
        """Сохраняет данные в файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения файла {filename}: {e}")
    
    @staticmethod
    def init_data_files():
        """Инициализирует файлы данных"""
        files = {
            ADMINS_FILE: {},
            MODERATORS_FILE: [],
            USERS_FILE: {},
            MUTED_FILE: {},
            CHATS_FILE: [],
            SILENCE_MODE_FILE: {},
            AUTOKICK_FILE: {},
            CHAT_CATEGORIES_FILE: {},
            BLACKLIST_FILE: {},
            BLACKLIST_HISTORY_FILE: [],
            LEADERSHIP_FILE: {},
            LOCAL_ADMINS_FILE: {},
            LOCAL_MODERATORS_FILE: {},
            ADMIN_LEVELS_FILE: {},
            ADMIN_LEVEL_NAMES_FILE: DEFAULT_ADMIN_LEVELS,
            NEWS_CHANNELS_FILE: [],
            NEWS_HISTORY_FILE: [],
            SETUP_ADMINS_FILE: [],
            COMMAND_ACCESS_FILE: {}
        }
        
        for filename, default in files.items():
            if not os.path.exists(filename):
                DataManager.save_data(default, filename)
        
        # Создаем папку для логов
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)

# ==================== КЛАСС ЧАТ-БОТА ====================
class ChatBot:
    def __init__(self, token):
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, group_id=GROUP_ID)
        
        # Инициализация файлов данных
        DataManager.init_data_files()
        
        # Кэш для предупреждений о правах
        self.permission_warnings = {}
        
        # Проверяем, нужно ли выполнить настройку администраторов
        self.check_setup_admins()
        
        # Инициализация системы доступа к командам
        self.init_command_access()
        
        # Загружаем названия уровней
        global ADMIN_LEVELS
        ADMIN_LEVELS = load_admin_level_names()
        
        logger.info("Чат-бот инициализирован")
    
    def init_command_access(self):
        """Инициализирует настройки доступа к командам"""
        command_access = DataManager.load_data(COMMAND_ACCESS_FILE, dict)
        
        # Базовые настройки доступа к командам
        default_command_access = {
            'команда': 'уровень',
            '/кик': 1,
            '/мут': 1,
            '/варн': 1,
            '/разварн': 1,
            '/удалить': 1,
            '/очистить': 1,
            '/стата': 0,
            '/яадмин': 0,
            '/помощь': 0,
            '/start': 3,
            '/stop': 3,
            '/привязать': 3,
            '/отвязать': 3,
            '/тишина': 3,
            '/автокик': 3,
            '/акик': 3,
            '/чс': 2,
            '/снятьчс': 2,
            '/инфо': 2,
            '/новости': 4,
            '/инфоновости': 3,
            '/каналыновостей': 3,
            '/добавитьканал': 4,
            '/удалитьканал': 4,
            '/падминл': 3,
            '/надминл': 3,
            '/падминг': 4,
            '/надминг': 4,
            '/настроитьадмин': 0,
            '/рук': 6,
            '/срук': 6,
            '/ктоадмин': 0,
            '/уровеньназвание': 4,
            '/доступкоманда': 4,
            '/админроли': 0,
            '/уровенькоманд': 0
        }
        
        # Обновляем только если файл пустой
        if not command_access:
            command_access = default_command_access
            DataManager.save_data(command_access, COMMAND_ACCESS_FILE)
        
        logger.info("Система доступа к командам инициализирована")
    
    def check_setup_admins(self):
        """Проверяет, нужно ли выполнить начальную настройку администраторов"""
        setup_admins = DataManager.load_data(SETUP_ADMINS_FILE, list)
        if not setup_admins:
            logger.info("Начальная настройка администраторов не выполнена. Готов к настройке через команду.")
        else:
            logger.info(f"Начальная настройка уже выполнена для {len(setup_admins)} администраторов")
    
    def setup_admin(self, user_id, level):
        """Настройка администратора при запуске бота"""
        if level < 1 or level > 7:
            return False
        
        admin_levels = self.load_admin_levels()
        admin_levels[str(user_id)] = level
        self.save_admin_levels(admin_levels)
        
        # Добавляем в список настроенных администраторов
        setup_admins = DataManager.load_data(SETUP_ADMINS_FILE, list)
        if str(user_id) not in setup_admins:
            setup_admins.append(str(user_id))
            DataManager.save_data(setup_admins, SETUP_ADMINS_FILE)
        
        logger.info(f"Установлен уровень {level} для пользователя {user_id}")
        return True
    
    # ==================== УПРОЩЕННАЯ СИСТЕМА ПРАВ ====================
    
    def load_admin_levels(self):
        """Загружает уровни администраторов"""
        return DataManager.load_data(ADMIN_LEVELS_FILE, dict)
    
    def save_admin_levels(self, admin_levels):
        """Сохраняет уровни администраторов"""
        DataManager.save_data(admin_levels, ADMIN_LEVELS_FILE)
    
    def get_admin_level(self, user_id):
        """Получает уровень администратора"""
        admin_levels = self.load_admin_levels()
        user_id_str = str(user_id)
        
        if user_id_str in admin_levels:
            return admin_levels[user_id_str]
        return 0  # 0 = не администратор
    
    def set_admin_level(self, user_id, level):
        """Устанавливает уровень администратора"""
        if level < 1 or level > 7:
            return False
        
        admin_levels = self.load_admin_levels()
        admin_levels[str(user_id)] = level
        self.save_admin_levels(admin_levels)
        return True
    
    def remove_admin_level(self, user_id):
        """Удаляет уровень администратора"""
        admin_levels = self.load_admin_levels()
        user_id_str = str(user_id)
        
        if user_id_str in admin_levels:
            del admin_levels[user_id_str]
            self.save_admin_levels(admin_levels)
            return True
        return False
    
    def get_admin_level_name(self, level):
        """Получает название уровня администратора"""
        global ADMIN_LEVELS
        return ADMIN_LEVELS.get(level, f"Уровень {level}")
    
    # ==================== ПОЛУЧЕНИЕ СПИСКА АДМИНИСТРАТОРОВ ====================
    def get_admins_in_chat(self, chat_id):
        """Получает список всех администраторов в беседе с информацией о глобальных/локальных правах"""
        admins_info = []
        
        try:
            # Получаем список участников беседы
            members = self.vk.messages.getConversationMembers(peer_id=chat_id)
            
            for member in members['items']:
                if member.get('is_admin', False):
                    user_id = member.get('member_id')
                    if user_id > 0:  # Исключаем ботов и группы
                        user_info = self.get_user_permissions_info(user_id, chat_id)
                        admins_info.append(user_info)
            
            return admins_info
        except Exception as e:
            logger.error(f"Ошибка при получении администраторов чата: {e}")
            return []
    
    # ==================== ИЗМЕНЕНИЕ НАЗВАНИЙ УРОВНЕЙ АДМИНИСТРАТОРОВ ====================
    def update_admin_level_name(self, level, new_name):
        """Обновляет название уровня администратора и сохраняет в файл"""
        if level < 1 or level > 7:
            return False
        
        global ADMIN_LEVELS
        # Обновляем название в словаре
        ADMIN_LEVELS[level] = new_name
        
        # Сохраняем изменения в файл
        save_admin_level_names(ADMIN_LEVELS)
        
        logger.info(f"Обновлено название уровня {level}: {new_name}")
        return True
    
    # ==================== УПРАВЛЕНИЕ ДОСТУПОМ К КОМАНДАМ ====================
    def load_command_access(self):
        """Загружает настройки доступа к командам"""
        return DataManager.load_data(COMMAND_ACCESS_FILE, dict)
    
    def save_command_access(self, command_access):
        """Сохраняет настройки доступа к командам"""
        DataManager.save_data(command_access, COMMAND_ACCESS_FILE)
    
    def set_command_access_level(self, command, level):
        """Устанавливает минимальный уровень для доступа к команде"""
        if level < 0 or level > 7:
            return False
        
        command_access = self.load_command_access()
        command_access[command] = level
        self.save_command_access(command_access)
        logger.info(f"Установлен уровень {level} для команды {command}")
        return True
    
    def get_command_access_level(self, command):
        """Получает минимальный уровень для доступа к команде"""
        command_access = self.load_command_access()
        return command_access.get(command, 0)
    
    def check_command_access(self, user_id, command, chat_id=None):
        """Проверяет доступ пользователя к команде"""
        required_level = self.get_command_access_level(command)
        return self.has_permission(user_id, chat_id, required_level)
    
    # ==================== ЕДИНАЯ СИСТЕМА ПРАВ ====================
    
    def has_permission(self, user_id, chat_id=None, min_level=0):
        """Проверяет, есть ли у пользователя права
        
        Единая система приоритетов:
        1. Уровень из admin_levels (1-7) - самый высокий приоритет
        2. Глобальный администратор из admins.json = уровень 3
        3. Глобальный модератор = уровень 1
        4. Локальный администратор = уровень 3 (но только в конкретном чате)
        5. Локальный модератор = уровень 1 (но только в конкретном чате)
        6. Руководство = уровень 6
        """
        # Проверяем уровень администратора (самый высокий приоритет)
        admin_level = self.get_admin_level(user_id)
        if admin_level >= min_level:
            return True
        
        # Если указан минимальный уровень выше 0, остальные проверки не нужны
        if min_level > 0:
            return False
        
        # Проверяем остальные системы (только если min_level=0)
        if self.is_leadership(user_id):
            return True
        
        # Для чат-специфичных прав нужен chat_id
        if chat_id:
            if self.is_local_admin(user_id, chat_id):
                return True
            if self.is_local_moderator(user_id, chat_id):
                return True
        
        # Проверяем глобальные права (из старых систем)
        if self.is_admin_global(user_id):
            return True
        if self.is_moderator_global(user_id):
            return True
        
        return False
    
    def check_permission(self, user_id, chat_id, command_level=0):
        """Проверяет права и отправляет сообщение об ошибке при отсутствии"""
        if not self.has_permission(user_id, chat_id, command_level):
            user_mention = get_user_mention(self.vk, user_id)
            
            if command_level > 0:
                level_name = self.get_admin_level_name(command_level)
                message = f"❌ {user_mention}, команда доступна только для {level_name} и выше!"
            else:
                message = f"❌ {user_mention}, у вас недостаточно прав для выполнения этой команды!"
            
            self.vk.messages.send(
                peer_id=chat_id,
                message=message,
                random_id=get_random_id()
            )
            return False
        return True
    
    # ==================== КОМПАТИБИЛЬНОСТЬ СО СТАРЫМИ СИСТЕМАМИ ====================
    
    def load_admins(self):
        """Загружает глобальных администраторов (старая система)"""
        admins = DataManager.load_data(ADMINS_FILE, dict)
        # Конвертируем старый формат (список) в новый (словарь)
        if isinstance(admins, list):
            new_admins = {}
            for admin_id in admins:
                new_admins[str(admin_id)] = {
                    'added_by': 'system',
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'level': 3  # По умолчанию уровень 3 (Администратор)
                }
            self.save_admins(new_admins)
            return new_admins
        return admins
    
    def save_admins(self, admins):
        """Сохраняет глобальных администраторов (старая система)"""
        DataManager.save_data(admins, ADMINS_FILE)
    
    def is_admin_global(self, user_id):
        """Проверяет, является ли пользователем глобальным администратором (старая система)"""
        return str(user_id) in self.load_admins()
    
    def load_moderators(self):
        """Загружает глобальных модераторов (старая система)"""
        moderators = DataManager.load_data(MODERATORS_FILE, list)
        return [str(moderator) for moderator in moderators]
    
    def save_moderators(self, moderators):
        """Сохраняет глобальных модераторов (старая система)"""
        DataManager.save_data(moderators, MODERATORS_FILE)
    
    def is_moderator_global(self, user_id):
        """Проверяет, является ли пользователь глобальным модератором (старая система)"""
        return str(user_id) in self.load_moderators()
    
    # ==================== РУКОВОДСТВО ====================
    def load_leadership(self):
        """Загружает список руководства"""
        return DataManager.load_data(LEADERSHIP_FILE, dict)
    
    def save_leadership(self, leadership):
        """Сохраняет список руководства"""
        DataManager.save_data(leadership, LEADERSHIP_FILE)
    
    def is_leadership(self, user_id):
        """Проверяет, является ли пользователь руководством"""
        leadership = self.load_leadership()
        return str(user_id) in leadership
    
    def add_leadership(self, user_id, admin_id):
        """Добавляет пользователя в руководство"""
        leadership = self.load_leadership()
        user_id_str = str(user_id)
        
        if user_id_str not in leadership:
            leadership[user_id_str] = {
                'added_by': str(admin_id),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save_leadership(leadership)
            
            # Устанавливаем уровень 6 (Владелец)
            self.set_admin_level(user_id, 6)
            
            self.add_action_log(
                action_type='leadership_add',
                admin_id=admin_id,
                target_id=user_id
            )
            return True
        return False
    
    def remove_leadership(self, user_id, admin_id):
        """Удаляет пользователя из руководство"""
        leadership = self.load_leadership()
        user_id_str = str(user_id)
        
        if user_id_str in leadership:
            del leadership[user_id_str]
            self.save_leadership(leadership)
            
            # Удаляем уровень администратора
            self.remove_admin_level(user_id)
            
            self.add_action_log(
                action_type='leadership_remove',
                admin_id=admin_id,
                target_id=user_id
            )
            return True
        return False
    
    # ==================== ЛОКАЛЬНЫЕ АДМИНИСТРАТОРЫ ====================
    def load_local_admins(self):
        """Загружает локальных администраторов"""
        return DataManager.load_data(LOCAL_ADMINS_FILE, dict)
    
    def save_local_admins(self, local_admins):
        """Сохраняет локальные администраторы"""
        DataManager.save_data(local_admins, LOCAL_ADMINS_FILE)
    
    def is_local_admin(self, user_id, chat_id):
        """Проверяет, является ли пользователь локальным администратором"""
        local_admins = self.load_local_admins()
        chat_id_str = str(chat_id)
        
        if chat_id_str in local_admins:
            return str(user_id) in local_admins[chat_id_str]
        return False
    
    def add_local_admin(self, user_id, chat_id, admin_id):
        """Добавляет локального администратора"""
        local_admins = self.load_local_admins()
        chat_id_str = str(chat_id)
        user_id_str = str(user_id)
        
        if chat_id_str not in local_admins:
            local_admins[chat_id_str] = []
        
        if user_id_str not in local_admins[chat_id_str]:
            local_admins[chat_id_str].append(user_id_str)
            self.save_local_admins(local_admins)
            
            self.add_action_log(
                action_type='local_admin_add',
                admin_id=admin_id,
                target_id=user_id,
                chat_id=chat_id
            )
            return True
        return False
    
    def remove_local_admin(self, user_id, chat_id, admin_id):
        """Удаляет локального администратора"""
        local_admins = self.load_local_admins()
        chat_id_str = str(chat_id)
        user_id_str = str(user_id)
        
        if chat_id_str in local_admins and user_id_str in local_admins[chat_id_str]:
            local_admins[chat_id_str].remove(user_id_str)
            self.save_local_admins(local_admins)
            
            self.add_action_log(
                action_type='local_admin_remove',
                admin_id=admin_id,
                target_id=user_id,
                chat_id=chat_id
            )
            return True
        return False
    
    # ==================== ЛОКАЛЬНЫЕ МОДЕРАТОРЫ ====================
    def load_local_moderators(self):
        """Загружает локальные модераторы"""
        return DataManager.load_data(LOCAL_MODERATORS_FILE, dict)
    
    def save_local_moderators(self, local_moderators):
        """Сохраняет локальные модераторы"""
        DataManager.save_data(local_moderators, LOCAL_MODERATORS_FILE)
    
    def is_local_moderator(self, user_id, chat_id):
        """Проверяет, является ли пользователь локальным модератором"""
        local_moderators = self.load_local_moderators()
        chat_id_str = str(chat_id)
        
        if chat_id_str in local_moderators:
            return str(user_id) in local_moderators[chat_id_str]
        return False
    
    def add_local_moderator(self, user_id, chat_id, admin_id):
        """Добавляет локального модератора"""
        local_moderators = self.load_local_moderators()
        chat_id_str = str(chat_id)
        user_id_str = str(user_id)
        
        if chat_id_str not in local_moderators:
            local_moderators[chat_id_str] = []
        
        if user_id_str not in local_moderators[chat_id_str]:
            local_moderators[chat_id_str].append(user_id_str)
            self.save_local_moderators(local_moderators)
            
            self.add_action_log(
                action_type='local_moder_add',
                admin_id=admin_id,
                target_id=user_id,
                chat_id=chat_id
            )
            return True
        return False
    
    def remove_local_moderator(self, user_id, chat_id, admin_id):
        """Удаляет локального модератора"""
        local_moderators = self.load_local_moderators()
        chat_id_str = str(chat_id)
        user_id_str = str(user_id)
        
        if chat_id_str in local_moderators and user_id_str in local_moderators[chat_id_str]:
            local_moderators[chat_id_str].remove(user_id_str)
            self.save_local_moderators(local_moderators)
            
            self.add_action_log(
                action_type='local_moder_remove',
                admin_id=admin_id,
                target_id=user_id,
                chat_id=chat_id
            )
            return True
        return False
    
    # ==================== НОВОСТИ ====================
    def load_news_channels(self):
        """Загружает каналы для новостей"""
        return DataManager.load_data(NEWS_CHANNELS_FILE, list)
    
    def save_news_channels(self, channels):
        """Сохраняет каналы для новостей"""
        DataManager.save_data(channels, NEWS_CHANNELS_FILE)
    
    def load_news_history(self):
        """Загружает историю новостей"""
        return DataManager.load_data(NEWS_HISTORY_FILE, list)
    
    def save_news_history(self, history):
        """Сохраняет историю новостей"""
        DataManager.save_data(history, NEWS_HISTORY_FILE)
    
    def add_news_channel(self, chat_id, admin_id):
        """Добавляет канал для новостей"""
        channels = self.load_news_channels()
        chat_id_str = str(chat_id)
        
        if chat_id_str not in channels:
            channels.append(chat_id_str)
            self.save_news_channels(channels)
            
            self.add_action_log(
                action_type='news_channel_add',
                admin_id=admin_id,
                chat_id=chat_id
            )
            return True
        return False
    
    def remove_news_channel(self, chat_id, admin_id):
        """Удаляет канал для новостей"""
        channels = self.load_news_channels()
        chat_id_str = str(chat_id)
        
        if chat_id_str in channels:
            channels.remove(chat_id_str)
            self.save_news_channels(channels)
            
            self.add_action_log(
                action_type='news_channel_remove',
                admin_id=admin_id,
                chat_id=chat_id
            )
            return True
        return False
    
    def send_news(self, admin_id, channel_numbers, message_text):
        """Отправляет новости в выбранные каналы по их номерам"""
        channels = self.load_news_channels()
        
        if not channels:
            self.vk.messages.send(
                peer_id=admin_id,
                message="❌ Нет добавленных каналов для новостей!",
                random_id=get_random_id()
            )
            return
        
        # Получаем информацию об администраторе
        try:
            admin_info = self.vk.users.get(user_ids=admin_id, fields='first_name,last_name')[0]
            admin_name = f"{admin_info['first_name']} {admin_info['last_name']}"
            admin_mention = f"[id{admin_id}|{admin_name}]"
        except Exception as e:
            logger.error(f"Ошибка получения информации об администраторе: {e}")
            admin_name = "Администратора"
            admin_mention = f"[id{admin_id}|Администратор]"
        
        # Выбираем только указанные каналы
        selected_channels = []
        invalid_numbers = []
        
        for num in channel_numbers:
            if 1 <= num <= len(channels):
                selected_channels.append(channels[num-1])
            else:
                invalid_numbers.append(str(num))
        
        if not selected_channels:
            self.vk.messages.send(
                peer_id=admin_id,
                message=f"❌ Неверные номера каналов: {', '.join(invalid_numbers)}\n"
                        f"Доступные номера: 1-{len(channels)}",
                random_id=get_random_id()
            )
            return
        
        self.vk.messages.send(
            peer_id=admin_id,
            message=f"🚀 Отправляю новость в {len(selected_channels)} из {len(channels)} каналов...",
            random_id=get_random_id()
        )
        
        success_count = 0
        fail_count = 0
        failed_channels = []
        
        # Форматируем сообщение
        formatted_message = f"📢 Информация от {admin_mention}\n{message_text}\n\nЭто автоматическое сообщение."
        
        for channel_id_str in selected_channels:
            try:
                self.vk.messages.send(
                    peer_id=int(channel_id_str),
                    message=formatted_message,
                    random_id=get_random_id()
                )
                success_count += 1
                time.sleep(0.1)
                
            except Exception as e:
                fail_count += 1
                failed_channels.append(channel_id_str)
                logger.error(f"Ошибка при отправке новости в канал {channel_id_str}: {e}")
        
        # Сохраняем в историю новостей
        news_history = self.load_news_history()
        news_entry = {
            'text': message_text,
            'admin_id': admin_id,
            'admin_name': admin_name,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'channels_sent': success_count,
            'channels_failed': fail_count,
            'selected_channels': selected_channels
        }
        news_history.append(news_entry)
        self.save_news_history(news_history)
        
        report = f"✅ Новости отправлены!\n\n"
        report += f"📊 Статистика:\n"
        report += f"• Успешно: {success_count}\n"
        report += f"• Не удалось: {fail_count}\n"
        report += f"• Всего выбрано каналов: {len(selected_channels)}\n"
        
        if invalid_numbers:
            report += f"\n⚠️ Пропущены неверные номера: {', '.join(invalid_numbers)}\n"
        
        if failed_channels:
            report += f"\n❌ Не удалось отправить в каналы:\n"
            for channel in failed_channels[:5]:
                # Пытаемся получить название чата
                try:
                    chat_name = self.get_chat_name(int(channel))
                    report += f"• {chat_name} (ID: {channel})\n"
                except:
                    report += f"• {channel}\n"
            if len(failed_channels) > 5:
                report += f"... и еще {len(failed_channels) - 5} каналов\n"
        
        self.vk.messages.send(
            peer_id=admin_id,
            message=report,
            random_id=get_random_id()
        )
        
        self.add_action_log(
            action_type='news_sent',
            admin_id=admin_id,
            details=f"Новость, успешно: {success_count}, неудачно: {fail_count}"
        )
    
    def get_news_info(self):
        """Получает информацию о новостях"""
        channels = self.load_news_channels()
        history = self.load_news_history()
        
        info = f"📢 ИНФОРМАЦИЯ О НОВОСТЯХ\n\n"
        info += f"📋 Количество каналов: {len(channels)}\n"
        info += f"📊 Всего отправлено новостей: {len(history)}\n\n"
        
        if channels:
            info += "📌 Активные каналы (используйте номера для выбора):\n"
            for i, channel in enumerate(channels[:10], 1):
                try:
                    chat_name = self.get_chat_name(int(channel))
                    info += f"{i}. {chat_name} (ID: {channel})\n"
                except:
                    info += f"{i}. ID: {channel}\n"
            if len(channels) > 10:
                info += f"... и еще {len(channels) - 10} каналов\n"
            
            info += f"\n📝 Для отправки новости используйте:\n"
            info += f"/новости 1,2,4 ваше сообщение\n"
            info += f"Где 1,2,4 - номера каналов из списка выше\n"
        
        if history:
            info += "\n📜 Последние 5 новостей:\n"
            for i, news in enumerate(history[-5:], 1):
                date = news.get('date', 'Неизвестно')
                admin_name = news.get('admin_name', 'Неизвестно')
                text_preview = news.get('text', '')[:50] + "..." if len(news.get('text', '')) > 50 else news.get('text', '')
                channels_count = news.get('channels_sent', 0)
                info += f"{i}. {date} от {admin_name}: {text_preview} (отправлено в {channels_count} каналов)\n"
        
        return info
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ====================
    def load_data(self, filename, default=dict):
        return DataManager.load_data(filename, default)
    
    def save_data(self, data, filename):
        DataManager.save_data(data, filename)
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ЛОГАМИ ====================
    def get_today_log_file(self):
        """Получить файл логов для текущего дня"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(LOGS_DIR, f"actions_{today}.json")
    
    def load_today_logs(self):
        """Загрузить логи текущего дня"""
        log_file = self.get_today_log_file()
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_today_logs(self, logs):
        """Сохранить логи текущего дня"""
        log_file = self.get_today_log_file()
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    
    def add_action_log(self, action_type, admin_id, target_id=None, chat_id=None, reason="", duration="", details=""):
        """Добавление записи в логи действий"""
        logs = self.load_today_logs()
        
        log_entry = {
            'id': len(logs) + 1,
            'type': action_type,
            'admin_id': str(admin_id),
            'target_id': str(target_id) if target_id else None,
            'chat_id': str(chat_id) if chat_id else None,
            'reason': reason,
            'duration': duration,
            'details': details,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logs.append(log_entry)
        self.save_today_logs(logs)
        return log_entry['id']
    
    def cleanup_old_logs(self, days_to_keep=30):
        """Удалить старые логи (старше указанного количества дней)"""
        if not os.path.exists(LOGS_DIR):
            return
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for filename in os.listdir(LOGS_DIR):
            if filename.startswith("actions_") and filename.endswith(".json"):
                try:
                    date_str = filename.replace("actions_", "").replace(".json", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff_date:
                        file_path = os.path.join(LOGS_DIR, filename)
                        os.remove(file_path)
                        logger.info(f"🗑️ Удален старый лог: {filename}")
                except ValueError:
                    continue
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ЧЕРНЫМ СПИСКОМ ====================
    def load_blacklist_history(self):
        return self.load_data(BLACKLIST_HISTORY_FILE, list)
    
    def save_blacklist_history(self, history):
        self.save_data(history, BLACKLIST_HISTORY_FILE)
    
    def add_to_blacklist_history(self, user_id, admin_id, action, reason="", categories=None, unban_date=None):
        history = self.load_blacklist_history()
        
        entry = {
            'user_id': str(user_id),
            'admin_id': str(admin_id),
            'action': action,
            'reason': reason,
            'categories': categories or ["все"],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'unban_date': unban_date
        }
        
        history.append(entry)
        self.save_blacklist_history(history)
    
    def load_blacklist(self):
        return self.load_data(BLACKLIST_FILE, dict)
    
    def save_blacklist(self, blacklist):
        self.save_data(blacklist, BLACKLIST_FILE)
    
    def add_to_blacklist(self, user_id, admin_id, reason="", duration_days=0, categories=None):
        if categories is None:
            categories = ["все"]
        
        blacklist = self.load_blacklist()
        user_id_str = str(user_id)
        
        unban_date = None
        if duration_days > 0:
            unban_date = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
        
        blacklist[user_id_str] = {
            'admin_id': str(admin_id),
            'reason': reason,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'categories': categories,
            'unban_date': unban_date
        }
        
        self.save_blacklist(blacklist)
        
        self.add_to_blacklist_history(user_id, admin_id, 'add', reason, categories, unban_date)
        
        self.add_action_log(
            action_type='blacklist_add',
            admin_id=admin_id,
            target_id=user_id,
            reason=reason,
            duration=f"{duration_days} дней" if duration_days > 0 else "бессрочно",
            details=f"Категории: {', '.join(categories)}"
        )
        
        return True
    
    def remove_from_blacklist(self, user_id, admin_id=None):
        blacklist = self.load_blacklist()
        user_id_str = str(user_id)
        
        if user_id_str in blacklist:
            if admin_id is None:
                admin_id = blacklist[user_id_str]['admin_id']
            self.add_to_blacklist_history(user_id, admin_id, 'remove')
            
            self.add_action_log(
                action_type='blacklist_remove',
                admin_id=admin_id,
                target_id=user_id
            )
            
            del blacklist[user_id_str]
            self.save_blacklist(blacklist)
            return True
        return False
    
    def is_in_blacklist(self, user_id, category=None):
        blacklist = self.load_blacklist()
        user_id_str = str(user_id)
        
        if user_id_str not in blacklist:
            return False
        
        user_data = blacklist[user_id_str]
        
        if user_data.get('unban_date'):
            unban_date = datetime.strptime(user_data['unban_date'], "%Y-%m-%d")
            if datetime.now().date() > unban_date.date():
                self.remove_from_blacklist(user_id)
                return False
        
        categories = user_data.get('categories', [])
        return "все" in categories or category in categories
    
    def get_blacklist_info(self, user_id):
        blacklist = self.load_blacklist()
        user_id_str = str(user_id)
        
        if user_id_str not in blacklist:
            return None
        
        return blacklist[user_id_str]
    
    def get_blacklist_history(self, user_id):
        history = self.load_blacklist_history()
        user_id_str = str(user_id)
        
        user_history = [entry for entry in history if entry['user_id'] == user_id_str]
        return user_history
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С КАТЕГОРИЯМИ ЧАТОВ ====================
    def load_chat_categories(self):
        return self.load_data(CHAT_CATEGORIES_FILE, dict)
    
    def save_chat_categories(self, categories):
        self.save_data(categories, CHAT_CATEGORIES_FILE)
    
    def set_chat_category(self, chat_id, category):
        categories = self.load_chat_categories()
        categories[str(chat_id)] = category
        self.save_chat_categories(categories)
    
    def get_chat_category(self, chat_id):
        categories = self.load_chat_categories()
        return categories.get(str(chat_id), "Не объединен с другими")
    
    def remove_chat_category(self, chat_id):
        categories = self.load_chat_categories()
        chat_id_str = str(chat_id)
        if chat_id_str in categories:
            del categories[chat_id_str]
            self.save_chat_categories(categories)
            return True
        return False
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С АВТОКИКОМ ====================
    def load_autokick(self):
        return self.load_data(AUTOKICK_FILE, dict)
    
    def save_autokick(self, autokick):
        self.save_data(autokick, AUTOKICK_FILE)
    
    def is_autokick_enabled(self, peer_id):
        autokick = self.load_autokick()
        peer_id_str = str(peer_id)
        return autokick.get(peer_id_str, False)
    
    def toggle_autokick(self, peer_id, admin_id=None):
        autokick = self.load_autokick()
        peer_id_str = str(peer_id)
        
        if peer_id_str in autokick:
            autokick[peer_id_str] = not autokick[peer_id_str]
        else:
            autokick[peer_id_str] = True
            
        self.save_autokick(autokick)
        
        if admin_id:
            status = "включен" if autokick[peer_id_str] else "выключен"
            self.add_action_log(
                action_type='autokick_toggle',
                admin_id=admin_id,
                chat_id=peer_id,
                details=f"Автокик {status}"
            )
        
        return autokick[peer_id_str]
    
    # ==================== ФУНКЦИЯ ДЛЯ УДАЛЕНИЯ СООБЩЕНИЙ ====================
    def delete_messages(self, peer_id, message_ids):
        """Удаляет сообщения используя правильный метод VK API"""
        if not message_ids:
            return 0, "Нет сообщений для удаления"
        
        try:
            if not isinstance(message_ids, list):
                message_ids = [message_ids]
            
            # Очищаем ID от нечисловых значений
            clean_ids = []
            for msg_id in message_ids:
                if isinstance(msg_id, int):
                    clean_ids.append(msg_id)
                elif isinstance(msg_id, str) and msg_id.isdigit():
                    clean_ids.append(int(msg_id))
            
            if not clean_ids:
                return 0, "Нет корректных ID сообщений"
            
            # Пытаемся удалить все сообщения одним запросом
            try:
                # Пробуем удалить с параметром delete_for_all=1
                result = self.vk.messages.delete(
                    message_ids=clean_ids,
                    delete_for_all=1
                )
                
                # Проверяем результат
                if isinstance(result, dict):
                    deleted_count = 0
                    for msg_id, status in result.items():
                        if status == 1:
                            deleted_count += 1
                    
                    if deleted_count > 0:
                        return deleted_count, f"Удалено {deleted_count} сообщений"
                    elif any(status == 0 for status in result.values()):
                        # Если сообщения не удалены из-за прав, но мы знаем что есть проблема
                        return -1, "Нет прав на удаление сообщений"
                elif result == 1:
                    return len(clean_ids), f"Удалено {len(clean_ids)} сообщений"
                    
            except vk_api.exceptions.ApiError as e:
                if e.code == 15 or e.code == 924:
                    # Нет прав на удаление
                    logger.warning(f"Нет прав на удаление сообщений в чате {peer_id}")
                    
                    # Пытаемся удалить по одному для более детальной информации
                    deleted_count = 0
                    failed_count = 0
                    
                    for msg_id in clean_ids:
                        try:
                            # Пробуем удалить как администратор беседы
                            self.vk.messages.delete(
                                message_ids=msg_id,
                                delete_for_all=1
                            )
                            deleted_count += 1
                            time.sleep(0.1)
                        except vk_api.exceptions.ApiError as e2:
                            if e2.code == 15 or e2.code == 924:
                                # Все равно нет прав
                                return -1, "Нет прав на удаление сообщений"
                            else:
                                failed_count += 1
                                logger.error(f"Ошибка при удалении сообщения {msg_id}: {e2.code}")
                    
                    if deleted_count > 0:
                        return deleted_count, f"Удалено {deleted_count} сообщений"
                    else:
                        return 0, "Не удалось удалить сообщения"
                        
                elif e.code == 6:
                    # Слишком много запросов, пробуем удалить по одному
                    logger.warning("Слишком много запросов, удаляю по одному")
                    deleted_count = 0
                    for msg_id in clean_ids:
                        try:
                            time.sleep(0.3)
                            self.vk.messages.delete(
                                message_ids=msg_id,
                                delete_for_all=1
                            )
                            deleted_count += 1
                        except:
                            pass
                    
                    if deleted_count > 0:
                        return deleted_count, f"Удалено {deleted_count} сообщений"
                    else:
                        return 0, "Не удалось удалить сообщения"
                else:
                    # Другая ошибка API
                    logger.error(f"Ошибка API при удалении сообщений: {e.code} - {e}")
                    return 0, f"Ошибка API: {e.code}"
            
            return 0, "Не удалось удалить сообщения"
                
        except Exception as e:
            logger.error(f"⚠️ Ошибка при удалении: {e}")
            return 0, f"Ошибка: {str(e)}"
    
    # ==================== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ МУТА ====================
    def check_mute_and_delete(self, peer_id, user_id, message_id):
        """Проверяет, находится ли пользователь в муте, и если да - удаляет сообщение"""
        if self.is_muted(user_id):
            try:
                result, message = self.delete_messages(peer_id, message_id)
                if result > 0:
                    logger.info(f"Сообщение от замьюченного пользователя {user_id} удалено")
                    return True
                elif result == -1:
                    # Если нет прав на удаление, отправляем предупреждение
                    if peer_id not in self.permission_warnings:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message="⚠️ Внимание: для работы мута боту нужны права на удаление сообщений!",
                            random_id=get_random_id()
                        )
                        self.permission_warnings[peer_id] = True
            except Exception as e:
                logger.error(f"⚠️ Не удалось удалить сообщение: {e}")
            return True
        return False
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С АКТИВНЫМИ ЧАТАМИ ====================
    def load_active_chats(self):
        return self.load_data(CHATS_FILE, list)
    
    def save_active_chats(self, chats):
        self.save_data(chats, CHATS_FILE)
    
    def add_active_chat(self, chat_id):
        chats = self.load_active_chats()
        chat_id = str(chat_id)
        
        if chat_id not in chats:
            chats.append(chat_id)
            self.save_active_chats(chats)
            return True
        return False
    
    def remove_active_chat(self, chat_id):
        chats = self.load_active_chats()
        chat_id = str(chat_id)
        
        if chat_id in chats:
            chats.remove(chat_id)
            self.save_active_chats(chats)
            return True
        return False
    
    def is_chat_active(self, chat_id):
        chats = self.load_active_chats()
        return str(chat_id) in chats
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЬСКОЙ СТАТИСТИКОЙ ====================
    def get_user_stats(self, user_id):
        users = self.load_data(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str not in users:
            users[user_id_str] = {
                'messages': 0,
                'warns': 0,
                'last_message': None,
                'first_message': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return users[user_id_str]
    
    def update_user_stats(self, user_id, add_message=False):
        users = self.load_data(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str not in users:
            users[user_id_str] = {
                'messages': 0,
                'warns': 0,
                'last_message': None,
                'first_message': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        if add_message:
            users[user_id_str]['messages'] += 1
            users[user_id_str]['last_message'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.save_data(users, USERS_FILE)
        return users[user_id_str]
    
    def add_warn(self, user_id, admin_id, reason=""):
        users = self.load_data(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str not in users:
            users[user_id_str] = {
                'messages': 0,
                'warns': 0,
                'last_message': None,
                'first_message': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'warn_history': []
            }
        
        if 'warn_history' not in users[user_id_str]:
            users[user_id_str]['warn_history'] = []
        
        warn_data = {
            'admin_id': str(admin_id),
            'reason': reason,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        users[user_id_str]['warns'] += 1
        users[user_id_str]['warn_history'].append(warn_data)
        
        self.save_data(users, USERS_FILE)
        
        self.add_action_log(
            action_type='warn',
            admin_id=admin_id,
            target_id=user_id,
            reason=reason,
            details=f"Текущее количество варнов: {users[user_id_str]['warns']}"
        )
        
        return users[user_id_str]['warns']
    
    def remove_warn(self, user_id, admin_id):
        users = self.load_data(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str in users and users[user_id_str]['warns'] > 0:
            users[user_id_str]['warns'] -= 1
            
            if 'warn_remove_history' not in users[user_id_str]:
                users[user_id_str]['warn_remove_history'] = []
            
            remove_data = {
                'admin_id': str(admin_id),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            users[user_id_str]['warn_remove_history'].append(remove_data)
            
            self.save_data(users, USERS_FILE)
            
            self.add_action_log(
                action_type='unwarn',
                admin_id=admin_id,
                target_id=user_id,
                details=f"Осталось варнов: {users[user_id_str]['warns']}"
            )
            
            return True
        return False
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С МУТАМИ ====================
    def mute_user(self, user_id, duration_minutes, admin_id, reason=""):
        muted = self.load_data(MUTED_FILE)
        user_id_str = str(user_id)
        
        unmute_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        muted[user_id_str] = {
            'admin_id': str(admin_id),
            'unmute_time': unmute_time.strftime("%Y-%m-%d %H:%M:%S"),
            'reason': reason,
            'duration_minutes': duration_minutes
        }
        
        self.save_data(muted, MUTED_FILE)
        
        self.add_action_log(
            action_type='mute',
            admin_id=admin_id,
            target_id=user_id,
            reason=reason,
            duration=f"{duration_minutes} минут",
            details=f"Мут до {unmute_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return unmute_time
    
    def unmute_user(self, user_id, admin_id=None):
        muted = self.load_data(MUTED_FILE)
        user_id_str = str(user_id)
        
        if user_id_str in muted:
            if admin_id is None:
                admin_id = muted[user_id_str]['admin_id']
            
            self.add_action_log(
                action_type='unmute',
                admin_id=admin_id,
                target_id=user_id
            )
            
            del muted[user_id_str]
            self.save_data(muted, MUTED_FILE)
            return True
        return False
    
    def is_muted(self, user_id):
        muted = self.load_data(MUTED_FILE)
        user_id_str = str(user_id)
        
        if user_id_str in muted:
            unmute_time = datetime.strptime(muted[user_id_str]['unmute_time'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < unmute_time:
                return True
            else:
                self.unmute_user(user_id)
        return False
    
    # ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЖИМОМ ТИШИНЫ ====================
    def load_silence_mode(self):
        return self.load_data(SILENCE_MODE_FILE, dict)
    
    def save_silence_mode(self, silence_mode):
        self.save_data(silence_mode, SILENCE_MODE_FILE)
    
    def set_silence_mode(self, peer_id, minutes=None, admin_id=None):
        silence_mode = self.load_silence_mode()
        peer_id_str = str(peer_id)
        
        if minutes is None:
            silence_mode[peer_id_str] = 'permanent'
            duration = "бессрочно"
        else:
            end_time = datetime.now() + timedelta(minutes=minutes)
            silence_mode[peer_id_str] = end_time.strftime("%Y-%m-%d %H:%M:%S")
            duration = f"{minutes} минут"
        
        self.save_silence_mode(silence_mode)
        
        if admin_id:
            self.add_action_log(
                action_type='silence_on',
                admin_id=admin_id,
                chat_id=peer_id,
                duration=duration
            )
        
        return silence_mode[peer_id_str]
    
    def disable_silence_mode(self, peer_id, admin_id=None):
        silence_mode = self.load_silence_mode()
        peer_id_str = str(peer_id)
        
        if peer_id_str in silence_mode:
            del silence_mode[peer_id_str]
            self.save_silence_mode(silence_mode)
            
            if admin_id:
                self.add_action_log(
                    action_type='silence_off',
                    admin_id=admin_id,
                    chat_id=peer_id
                )
            
            return True
        return False
    
    def is_silence_mode(self, peer_id):
        silence_mode = self.load_silence_mode()
        peer_id_str = str(peer_id)
        
        if peer_id_str in silence_mode:
            if silence_mode[peer_id_str] == 'permanent':
                return True
            
            try:
                end_time = datetime.strptime(silence_mode[peer_id_str], "%Y-%m-%d %H:%M:%S")
                if datetime.now() < end_time:
                    return True
                else:
                    self.disable_silence_mode(peer_id)
            except:
                return True
        return False
    
    # ==================== ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПРАВ ====================
    def is_chat_admin(self, peer_id, user_id):
        try:
            if peer_id < 2000000000:
                return False
                
            members = self.vk.messages.getConversationMembers(peer_id=peer_id)
            for member in members['items']:
                if member.get('member_id') == user_id:
                    return bool(member.get('is_admin', False))
            return False
        except Exception as e:
            logger.error(f"⚠️ Ошибка при проверке прав администратора чата: {e}")
            return False
    
    # ==================== ФУНКЦИИ ДЛЯ ФОРМАТИРОВАНИЯ СТАТИСТИКИ ====================
    def format_stats(self, stats, user_id):
        user_mention = get_user_mention(self.vk, user_id)
        muted_status = "🔇 В муте" if self.is_muted(user_id) else "✅ Не в муте"
        
        # Получаем уровень администратора
        admin_level = self.get_admin_level(user_id)
        admin_info = ""
        if admin_level > 0:
            admin_info = f"👑 Уровень администратора: {self.get_admin_level_name(admin_level)} ({admin_level})\n"
        
        return (
            f"📊 Статистика пользователя {user_mention}:\n"
            f"{admin_info}"
            f"✉️ Сообщений: {stats['messages']}\n"
            f"⚠️ Варнов: {stats['warns']}/3\n"
            f"{muted_status}\n"
            f"📅 Первое сообщение: {stats['first_message']}\n"
            f"🕒 Последнее сообщение: {stats['last_message'] or 'еще не писал'}"
        )
    
    # ==================== ФУНКЦИИ ДЛЯ КИКА ====================
    def kick_from_chat(self, peer_id, user_id, admin_id, reason=""):
        """Кикает пользователя из чата с детальной информацией"""
        try:
            chat_id = peer_id - 2000000000
            self.vk.messages.removeChatUser(
                chat_id=chat_id,
                member_id=user_id
            )
            
            # Получаем информацию о пользователях
            user_mention = get_user_mention(self.vk, user_id)
            admin_mention = get_user_mention(self.vk, admin_id)
            chat_info = self.get_chat_name(peer_id)
            
            self.add_action_log(
                action_type='kick',
                admin_id=admin_id,
                target_id=user_id,
                chat_id=peer_id,
                reason=reason,
                details=f"Кик из чата {peer_id} ({chat_info})"
            )
            
            # Формируем детальное сообщение для логов
            log_message = (
                f"👢 Кик выполнен:\n"
                f"• Пользователь: {user_mention}\n"
                f"• Администратор: {admin_mention}\n"
                f"• Чат: {chat_info} (ID: {peer_id})\n"
                f"• Причина: {reason if reason else 'не указана'}"
            )
            logger.info(log_message)
            
            return True, chat_info
        except vk_api.exceptions.ApiError as e:
            if e.code == 15:
                # Нет прав на кик
                logger.error(f"Нет прав на кик в чате {peer_id}: {e}")
                return False, "Нет прав на кик"
            elif e.code == 935:
                # Пользователь не в чате
                logger.error(f"Пользователь {user_id} не в чате {peer_id}: {e}")
                return False, "Пользователь не в чате"
            else:
                logger.error(f"Ошибка кика в чате {peer_id}: {e}")
                return False, f"Ошибка API: {e.code}"
        except Exception as e:
            logger.error(f"⚠️ Ошибка кика в чате {peer_id}: {e}")
            return False, str(e)
    
    def get_chat_name(self, peer_id):
        """Получает название чата"""
        try:
            if peer_id < 2000000000:
                return "личные сообщения"
            
            chat_info = self.vk.messages.getConversationsById(peer_ids=peer_id)
            if chat_info and 'items' in chat_info and chat_info['items']:
                chat = chat_info['items'][0]
                if 'chat_settings' in chat and 'title' in chat['chat_settings']:
                    return chat['chat_settings']['title']
            
            return f"Чат {peer_id}"
        except Exception as e:
            logger.error(f"Ошибка получения названия чата: {e}")
            return f"Чат {peer_id}"
    
    def kick_from_all_chats(self, user_id, admin_id, reason=""):
        """Кикает пользователя из всех активных чатов с детальным отчетом"""
        active_chats = self.load_active_chats()
        kicked_chats = []
        failed_chats = []
        chat_details = []
        failed_details = []
        
        for chat_id_str in active_chats:
            try:
                chat_id = int(chat_id_str)
                chat_name = self.get_chat_name(chat_id)
                success, message = self.kick_from_chat(chat_id, user_id, admin_id, reason)
                
                if success:
                    kicked_chats.append(str(chat_id))
                    chat_details.append(f"• {chat_name} (ID: {chat_id}) - успешно")
                else:
                    failed_chats.append(str(chat_id))
                    failed_details.append(f"• {chat_name} (ID: {chat_id}) - {message}")
                    
            except Exception as e:
                failed_chats.append(str(chat_id))
                chat_name = self.get_chat_name(chat_id)
                failed_details.append(f"• {chat_name} (ID: {chat_id}) - ошибка: {str(e)}")
                logger.error(f"⚠️ Ошибка кика в чате {chat_id}: {e}")
        
        # Формируем детальный отчет
        report = {
            'kicked_chats': kicked_chats,
            'failed_chats': failed_chats,
            'chat_details': chat_details,
            'failed_details': failed_details,
            'total_active': len(active_chats)
        }
        
        self.add_action_log(
            action_type='kick_all',
            admin_id=admin_id,
            target_id=user_id,
            reason=reason,
            details=f"Кик из {len(kicked_chats)} чатов, не удалось из {len(failed_chats)}"
        )
        
        return report
    
    # ==================== ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР ====================
    def create_category_keyboard(self):
        keyboard = {
            "inline": True,
            "buttons": [
                [{
                    "action": {
                        "type": "callback",
                        "label": "Для администрации",
                        "payload": json.dumps({"category": "администрация"})
                    },
                    "color": "primary"
                }],
                [{
                    "action": {
                        "type": "callback",
                        "label": "Для лидеров",
                        "payload": json.dumps({"category": "лидеры"})
                    },
                    "color": "primary"
                }],
                [{
                    "action": {
                        "type": "callback",
                        "label": "Для заместителей",
                        "payload": json.dumps({"category": "заместители"})
                    },
                    "color": "primary"
                }],
                [{
                    "action": {
                        "type": "callback",
                        "label": "Для ГА/ЗГА",
                        "payload": json.dumps({"category": "га"})
                    },
                    "color": "primary"
                }],
                [{
                    "action": {
                        "type": "callback",
                        "label": "Отмена",
                        "payload": json.dumps({"cancel": True})
                    },
                    "color": "negative"
                }]
            ]
        }
        return json.dumps(keyboard)
    
    # ==================== ФУНКЦИИ ДЛЯ ОЧИСТКИ ЧАТА ====================
    def clear_chat(self, peer_id, count=100, admin_id=None):
        """Очищает указанное количество последних сообщений в чате"""
        try:
            history = self.vk.messages.getHistory(
                peer_id=peer_id,
                count=min(count, 100),
                rev=1
            )
            
            message_ids = [msg['id'] for msg in history['items'] if 'id' in msg]
            
            deleted_count, message = self.delete_messages(peer_id, message_ids)
            
            if admin_id and deleted_count > 0:
                self.add_action_log(
                    action_type='clear',
                    admin_id=admin_id,
                    chat_id=peer_id,
                    details=f"Удалено {deleted_count} сообщений"
                )
            
            return deleted_count, message
        except Exception as e:
            logger.error(f"⚠️ Ошибка очистки чата: {e}")
            return 0, f"Ошибка: {str(e)}"
    
    # ==================== ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ СПИСКА КОМАНД ====================
    def get_help_message(self, user_id, chat_id):
        """Получает сообщение помощи в зависимости от прав пользователя"""
        admin_level = self.get_admin_level(user_id)
        is_moderator_user = self.is_moderator_global(user_id)
        is_local_admin = self.is_local_admin(user_id, chat_id)
        is_local_moderator = self.is_local_moderator(user_id, chat_id)
        is_leadership = self.is_leadership(user_id)
        
        if admin_level >= 6 or is_leadership:  # Владелец и выше
            return (
                "👑 Команды Владельца:\n"
                "• /start - подключить беседу к боту\n"
                "• /stop - отключить беседу от бота\n"
                "• /привязать - привязать беседу к категории\n"
                "• /отвязать - отвязать беседу от категории\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /акик @упоминание - кикнуть пользователя из всех бесед\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /тишина [время] - включить режим тишины\n"
                "• /тишина выкл - выключить режим тишины\n"
                "• /автокик - включить/выключить автокик вышедших пользователей\n"
                "• /акик @упоминание - кикнуть пользователя из всех бесед\n"
                "• /чс @пользователь категория дни причина - добавить в ЧС\n"
                "• /снятьчс @пользователь - убрать из ЧС\n"
                "• /инфо @пользователь - информация о ЧС\n"
                "• /новости - отправить новости в выбранные каналы\n"
                "• /инфоновости - информация о новостях\n"
                "• /каналыновостей - показать каналы новостей\n"
                "• /добавитьканал - добавить текущий чат в каналы новостей\n"
                "• /удалитьканал - удалить текущий чат из каналов новостей\n"
                "• /падминл @пользователь - назначить локального администратора\n"
                "• /надминл @пользователь - снять локального администратора\n"
                "• /падминг @пользователь уровень - назначить глобального администратора\n"
                "• /надминг @пользователь - снять глобального администратора\n"
                "• /настроитьадмин @пользователь уровень - настроить администратора (только при запуске)\n"
                "• /рук @пользователь - назначить руководство\n"
                "• /срук @пользователь - снять руководство\n"
                "• /яадмин - проверить свои права\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /уровеньназвание уровень новое_название - изменить название уровня администратора\n"
                "• /доступкоманда команда уровень - изменить доступ к команде\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif admin_level >= 4:  # Главный Администратор и выше
            return (
                "👑 Команды Главного Администратора:\n"
                "• /start - подключить беседу к боту\n"
                "• /stop - отключить беседу от бота\n"
                "• /привязать - привязать беседу к категории\n"
                "• /отвязать - отвязать беседу от категории\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /акик @упоминание - кикнуть пользователя из всех бесед\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /тишина [время] - включить режим тишины\n"
                "• /тишина выкл - выключить режим тишины\n"
                "• /автокик - включить/выключить автокик вышедших пользователей\n"
                "• /чс @пользователь категория дни причина - добавить в ЧС\n"
                "• /снятьчс @пользователь - убрать из ЧС\n"
                "• /инфо @пользователь - информация о ЧС\n"
                "• /новости - отправить новости в выбранные каналы\n"
                "• /инфоновости - информация о новостях\n"
                "• /каналыновостей - показать каналы новостей\n"
                "• /добавитьканал - добавить текущий чат в каналы новостей\n"
                "• /удалитьканал - удалить текущий чат из каналов новостей\n"
                "• /падминл @пользователь - назначить локального администратора\n"
                "• /надминл @пользователь - снять локального администратора\n"
                "• /падминг @пользователь уровень - назначить глобального администратора\n"
                "• /надминг @пользователь - снять глобального администратора\n"
                "• /настроитьадмин @пользователь уровень - настроить администратора (только при запуске)\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /уровеньназвание уровень новое_название - изменить название уровня администратора\n"
                "• /доступкоманда команда уровень - изменить доступ к команде\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif admin_level >= 3:  # Администратор
            return (
                "👑 Команды Администратора:\n"
                "• /start - подключить беседу к боту\n"
                "• /stop - отключить беседу от бота\n"
                "• /привязать - привязать беседу к категории\n"
                "• /отвязать - отвязать беседу от категории\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /акик @упоминание - кикнуть пользователя из всех бесед\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /тишина [время] - включить режим тишины\n"
                "• /тишина выкл - выключить режим тишины\n"
                "• /автокик - включить/выключить автокик вышедших пользователей\n"
                "• /чс @пользователь категория дни причина - добавить в ЧС\n"
                "• /снятьчс @пользователь - убрать из ЧС\n"
                "• /инфо @пользователь - информация о ЧС\n"
                "• /падминл @пользователь - назначить локального администратора\n"
                "• /надминл @пользователь - снять локального администратора\n"
                "• /настроитьадмин @пользователь уровень - настроить администратора (только при запуске)\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif admin_level >= 2:  # Старший Модератор
            return (
                "🛡️ Команды Старшего Модератора:\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /чс @пользователь категория дни причина - добавить в ЧС\n"
                "• /снятьчс @пользователь - убрать из ЧС\n"
                "• /инфо @пользователь - информация о ЧС\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif admin_level >= 1 or is_moderator_user:  # Модератор
            return (
                "🛡️ Команды Модератора:\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif is_local_admin:
            return (
                "🏘️ Команды Локального Администратора:\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /падминл @пользователь - назначить локального администратора\n"
                "• /надминл @пользователь - снять локального администратора\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        elif is_local_moderator:
            return (
                "🏘️ Команды Локального Модератора:\n"
                "• /кик @упоминание - кикнуть пользователя\n"
                "• /варн @пользователь [причина] - выдать предупреждение\n"
                "• /разварн @пользователь - снять предупреждение\n"
                "• /мут @пользователь [время] [причина] - замутить\n"
                "• /размут @пользователь - размутить\n"
                "• /стата [@пользователь] - статистика\n"
                "• /удалить (ответом) - удалить сообщение\n"
                "• /очистить [кол-во] - удалить много сообщений\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /яадмин - проверить свои права\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
        else:
            return (
                "👋 Команды для пользователя:\n"
                "• /яадмин - проверить свои права\n"
                "• /ктоадмин - показать список администраторов в беседе\n"
                "• /админроли - показать названия уровней администраторов\n"
                "• /уровенькоманд - показать уровень доступа ко всем командам\n"
                "• /стата - моя статистика\n"
                "• /помощь - показать это сообщение\n\n"
                "💬 Также я реагирую на слова 'бог' и 'бот' в сообщениях"
            )
    
    # ==================== ФУНКЦИИ ДЛЯ ФОРМАТИРОВАНИЯ ИНФОРМАЦИИ О ЧС ====================
    def format_blacklist_info(self, user_id, user_info):
        user_mention = get_user_mention(self.vk, user_id)
        admin_mention = get_user_mention(self.vk, user_info['admin_id'])
        
        info_text = f"Информация о {user_mention}.\n"
        
        if user_info.get('unban_date'):
            unban_date = datetime.strptime(user_info['unban_date'], "%Y-%m-%d")
            info_text += f"Заблокирован: {user_info['date']}\n"
            info_text += f"Будет разблокирован: {user_info['unban_date']}\n"
            
            if datetime.now().date() > unban_date.date():
                self.remove_from_blacklist(user_id)
                info_text += "\n✅ Срок блокировки истек, пользователь автоматически разблокирован."
        else:
            info_text += f"Заблокирован навсегда: {user_info['date']}\n"
        
        info_text += f"Причина: {user_info['reason']}\n\n"
        
        categories = user_info.get('categories', ['все'])
        
        admin_status = "✔" if "все" in categories or "администрация" in categories else "✖"
        leader_status = "✔" if "все" in categories or "лидеры" in categories else "✖"
        deputy_status = "✔" if "все" in categories or "заместители" in categories else "✖"
        
        info_text += f"{admin_status} ЧС Админов\n"
        info_text += f"{leader_status} ЧС Лидеров\n"
        info_text += f"{deputy_status} ЧС Замов\n"
        
        return info_text
    
    def format_blacklist_history_info(self, user_id):
        user_mention = get_user_mention(self.vk, user_id)
        history = self.get_blacklist_history(user_id)
        
        if not history:
            return f"Информация о {user_mention}.\nПользователь никогда не был в черном списке."
        
        info_text = f"История ЧС для {user_mention}:\n\n"
        
        add_entries = [entry for entry in history if entry['action'] == 'add']
        remove_entries = [entry for entry in history if entry['action'] == 'remove']
        
        if add_entries:
            info_text += "📛 Был в ЧС:\n"
            for i, entry in enumerate(add_entries[-3:], 1):
                admin_mention = get_user_mention(self.vk, entry['admin_id'])
                info_text += f"{i}. Дата: {entry['date']}\n"
                info_text += f"   Причина: {entry['reason']}\n"
                info_text += f"   Заблокировал: {admin_mention}\n"
                
                if entry.get('unban_date'):
                    info_text += f"   Срок: до {entry['unban_date']}\n"
                else:
                    info_text += "   Срок: бессрочно\n"
                    
                info_text += f"   Категории: {', '.join(entry.get('categories', ['все']))}\n\n"
        else:
            info_text += "❌ Не было записей о добавлении в ЧС\n\n"
        
        if remove_entries:
            info_text += "✅ Снятия с ЧС:\n"
            for i, entry in enumerate(remove_entries[-3:], 1):
                admin_mention = get_user_mention(self.vk, entry['admin_id'])
                info_text += f"{i}. Дата: {entry['date']}\n"
                info_text += f"   Разблокировал: {admin_mention}\n\n"
        else:
            info_text += "✅ Не было записей о снятии с ЧС\n\n"
        
        current_status = "находится" if self.is_in_blacklist(user_id) else "не находится"
        info_text += f"📋 Текущий статус: {current_status} в черном списке."
        
        return info_text
    
    # ==================== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ПРАВ С ДЕТАЛЬНОЙ ИНФОРМАЦИЕЙ ====================
    def get_user_permissions_info(self, user_id, chat_id=None):
        """Получает детальную информацию о правах пользователя"""
        admin_level = self.get_admin_level(user_id)
        user_mention = get_user_mention(self.vk, user_id)
        
        info = f"🔍 Информация о правах {user_mention}:\n\n"
        
        if admin_level >= 7:
            info += f"👑 Основатель (уровень {admin_level}) - самый высокий уровень!\n"
        elif admin_level >= 6:
            info += f"👑 Владелец (уровень {admin_level})!\n"
        elif admin_level >= 5:
            info += f"👑 Со-Владелец (уровень {admin_level})!\n"
        elif admin_level >= 4:
            info += f"👑 Главный Администратор (уровень {admin_level})!\n"
        elif admin_level >= 3:
            info += f"👑 Администратор (уровень {admin_level})!\n"
        elif admin_level >= 2:
            info += f"🛡️ Старший Модератор (уровень {admin_level})!\n"
        elif admin_level >= 1:
            info += f"🛡️ Модератор (уровень {admin_level})!\n"
        
        # Дополнительные права (старые системы)
        additional_rights = []
        
        if self.is_leadership(user_id):
            additional_rights.append("👑 Руководство")
        
        if self.is_admin_global(user_id):
            additional_rights.append("👑 Глобальный администратор (старая система)")
        
        if self.is_moderator_global(user_id):
            additional_rights.append("🛡️ Глобальный модератор (старая система)")
        
        if chat_id:
            if self.is_local_admin(user_id, chat_id):
                additional_rights.append("🏘️ Локальный администратор этого чата")
            
            if self.is_local_moderator(user_id, chat_id):
                additional_rights.append("🏘️ Локальный модератор этого чата")
        
        if additional_rights:
            info += "\n📋 Дополнительные права:\n"
            for right in additional_rights:
                info += f"• {right}\n"
        
        if admin_level == 0 and not additional_rights:
            info += "❌ Нет прав администратора или модератора"
        
        return info
    
    # ==================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О РОЛЯХ АДМИНИСТРАТОРОВ ====================
    def get_admin_roles_info(self):
        """Получает информацию о названиях ролей администраторов"""
        global ADMIN_LEVELS
        info = "👑 Названия уровней администраторов:\n\n"
        
        for level in sorted(ADMIN_LEVELS.keys()):
            level_name = self.get_admin_level_name(level)
            info += f"Уровень {level}: {level_name}\n"
        
        info += "\nℹ️ Уровень 0: Пользователь (без прав администратора)"
        
        return info
    
    # ==================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О ДОСТУПЕ К КОМАНДАМ ====================
    def get_command_access_info(self):
        """Получает информацию о минимальном уровне доступа для всех команд"""
        command_access = self.load_command_access()
        
        info = "🔐 Уровень доступа к командам:\n\n"
        
        # Сортируем команды по уровню доступа, пропуская заголовок
        commands_to_show = [(cmd, level) for cmd, level in command_access.items() if cmd != 'команда']
        sorted_commands = sorted(commands_to_show, key=lambda x: x[1])
        
        for command, level in sorted_commands:
            if level == 0:
                level_name = "всем пользователям"
            else:
                level_name = self.get_admin_level_name(level)
            
            info += f"• {command} - {level_name} (уровень {level})\n"
        
        info += "\nℹ️ Уровень 0 означает, что команда доступна всем пользователям"
        
        return info
    
    # ==================== ОСНОВНОЙ ЦИКЛ ОБРАБОТКИ ====================
    def process_message(self, event):
        msg = event.object.message
        peer_id = msg['peer_id']
        from_id = msg['from_id']
        text = msg['text']
        chat_id_str = str(peer_id)
        message_id = msg.get('id')
        
        # Проверяем, что сообщение из беседы, а не из ЛС
        if peer_id == from_id:
            logger.info(f"[CHAT] Игнорирую личное сообщение от ID{from_id}")
            return
        
        normalized_text = text.lower()
        
        # Проверяем, не в муте ли пользователь
        if self.check_mute_and_delete(peer_id, from_id, message_id):
            return
        
        # Проверяем режим тишины
        if self.is_silence_mode(peer_id) and not text.startswith('/'):
            if not self.has_permission(from_id, peer_id) and not self.is_chat_admin(peer_id, from_id):
                try:
                    if message_id:
                        result, message = self.delete_messages(peer_id, message_id)
                        if result > 0:
                            logger.info(f"Сообщение от {from_id} удалено в режиме тишины")
                        elif result == -1:
                            # Если нет прав на удаление, отправляем предупреждение
                            if peer_id not in self.permission_warnings:
                                self.vk.messages.send(
                                    peer_id=peer_id,
                                    message="⚠️ Внимание: для работы режима тишины боту нужны права на удаление сообщений!",
                                    random_id=get_random_id()
                                )
                                self.permission_warnings[peer_id] = True
                except Exception as e:
                    logger.error(f"⚠️ Не удалось удалить сообщение в режиме тишины: {e}")
                return
        
        # Обновляем статистику сообщений
        self.update_user_stats(from_id, add_message=True)
        
        logger.info(f"[CHAT] Сообщение в чате {peer_id} от ID{from_id}: {text}")
        
        # Обработка системных действий
        if 'action' in msg:
            action = msg['action']
            action_type = action.get('type')
            
            if action_type == 'chat_invite_user':
                invited_id = action.get('member_id')
                
                chat_category = self.get_chat_category(peer_id)
                if self.is_in_blacklist(invited_id, chat_category):
                    try:
                        if message_id:
                            self.delete_messages(peer_id, message_id)
                    except:
                        pass
                    
                    success, chat_name = self.kick_from_chat(peer_id, invited_id, from_id, "Нахождение в ЧС")
                    if success:
                        invited_mention = get_user_mention(self.vk, invited_id)
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"⛔ Пользователь {invited_mention} находится в ЧС и был кикнут!",
                            random_id=get_random_id()
                        )
                    else:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"⚠️ Не удалось кикнуть пользователя из ЧС: {chat_name}",
                            random_id=get_random_id()
                        )
            
            elif action_type == 'chat_invite_user_by_link':
                joined_id = from_id
                
                chat_category = self.get_chat_category(peer_id)
                if self.is_in_blacklist(joined_id, chat_category):
                    try:
                        if message_id:
                            self.delete_messages(peer_id, message_id)
                    except:
                        pass
                    
                    success, chat_name = self.kick_from_chat(peer_id, joined_id, from_id, "Нахождение в ЧС")
                    if success:
                        joined_mention = get_user_mention(self.vk, joined_id)
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"⛔ Пользователь {joined_mention} находится в ЧС и был кикнут!",
                            random_id=get_random_id()
                        )
                    else:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"⚠️ Не удалось кикнуть пользователя из ЧС: {chat_name}",
                            random_id=get_random_id()
                        )
            
            elif action_type in ['chat_kick_user', 'chat_leave']:
                left_id = action.get('member_id', from_id)
                
                if self.is_autokick_enabled(peer_id) and left_id > 0:
                    success, chat_name = self.kick_from_chat(peer_id, left_id, from_id, "Автокик за выход")
                    if success:
                        left_mention = get_user_mention(self.vk, left_id)
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"👢 Пользователь {left_mention} был кикнут (автокик)!",
                            random_id=get_random_id()
                        )
                    else:
                        logger.error(f"Не удалось выполнить автокик для {left_id}: {chat_name}")
        
        # НОВАЯ КОМАНДА: КТО АДМИН
        elif normalized_text.startswith('/ктоадмин'):
            admins_info = self.get_admins_in_chat(peer_id)
            
            if not admins_info:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ В этой беседе нет администраторов с правами бота.",
                    random_id=get_random_id()
                )
            else:
                message = "👑 Администраторы в беседе:\n\n"
                for i, admin_info in enumerate(admins_info, 1):
                    # Извлекаем упоминание из информации
                    lines = admin_info.split('\n')
                    mention = lines[0].replace("🔍 Информация о правах ", "").replace(":", "")
                    
                    # Определяем тип администратора
                    admin_type = "Локальный"
                    if "Глобальный администратор" in admin_info or "Уровень администратора" in admin_info:
                        admin_type = "Глобальный"
                    
                    message += f"{i}. {mention} - {admin_type}\n"
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    random_id=get_random_id()
                )
        
        # НОВАЯ КОМАНДА: АДМИНРОЛИ
        elif normalized_text.startswith('/админроли'):
            roles_info = self.get_admin_roles_info()
            self.vk.messages.send(
                peer_id=peer_id,
                message=roles_info,
                random_id=get_random_id()
            )
        
        # НОВАЯ КОМАНДА: УРОВЕНЬКОМАНД
        elif normalized_text.startswith('/уровенькоманд'):
            access_info = self.get_command_access_info()
            self.vk.messages.send(
                peer_id=peer_id,
                message=access_info,
                random_id=get_random_id()
            )
        
        # НОВАЯ КОМАНДА: ИЗМЕНЕНИЕ НАЗВАНИЯ УРОВНЯ АДМИНИСТРАТОРА
        elif normalized_text.startswith('/уровеньназвание'):
            if not self.check_permission(from_id, peer_id, 4):  # Только Главный Админ и выше
                return
            
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Используйте: /уровеньназвание уровень новое_название\n"
                            "Пример: /уровеньназвание 1 Младший Модератор",
                    random_id=get_random_id()
                )
                return
            
            try:
                level = int(parts[1])
                if level < 1 or level > 7:
                    raise ValueError
            except ValueError:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Уровень должен быть числом от 1 до 7!",
                    random_id=get_random_id()
                )
                return
            
            new_name = parts[2]
            old_name = self.get_admin_level_name(level)
            
            if self.update_admin_level_name(level, new_name):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ Название уровня {level} изменено:\n"
                            f"Старое: {old_name}\n"
                            f"Новое: {new_name}",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Не удалось изменить название уровня!",
                    random_id=get_random_id()
                )
        
        # НОВАЯ КОМАНДА: ИЗМЕНЕНИЕ ДОСТУПА К КОМАНДЕ
        elif normalized_text.startswith('/доступкоманда'):
            if not self.check_permission(from_id, peer_id, 4):  # Только Главный Админ и выше
                return
            
            parts = text.split()
            if len(parts) < 3:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Используйте: /доступкоманда команда уровень\n"
                            "Пример: /доступкоманда /кик 1\n"
                            "Пример: /доступкоманда /новости 4\n"
                            "Уровень 0 - доступно всем пользователям",
                    random_id=get_random_id()
                )
                return
            
            command = parts[1]
            try:
                level = int(parts[2])
                if level < 0 or level > 7:
                    raise ValueError
            except ValueError:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Уровень должен быть числом от 0 до 7!",
                    random_id=get_random_id()
                )
                return
            
            old_level = self.get_command_access_level(command)
            
            if self.set_command_access_level(command, level):
                level_name = self.get_admin_level_name(level) if level > 0 else "всем пользователям"
                old_level_name = self.get_admin_level_name(old_level) if old_level > 0 else "всем пользователям"
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ Доступ к команде {command} изменен:\n"
                            f"Старый уровень: {old_level_name} ({old_level})\n"
                            f"Новый уровень: {level_name} ({level})",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Не удалось изменить доступ к команде!",
                    random_id=get_random_id()
                )
        
        # Команда помощи
        elif normalized_text == '/помощь':
            help_message = self.get_help_message(from_id, peer_id)
            self.vk.messages.send(
                peer_id=peer_id,
                message=help_message,
                random_id=get_random_id()
            )
        
        # Команда START - подключение беседы
        elif normalized_text == '/start':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/start')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.add_active_chat(peer_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="✅ Вы успешно подключили беседу. Баны, муты и прочий функционал теперь активен!",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ Беседа уже подключена!",
                    random_id=get_random_id()
                )
        
        # Команда STOP - отключение беседы
        elif normalized_text == '/stop':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/stop')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.remove_active_chat(peer_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="✅ Беседа отключена. Функционал бота больше не активен.",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ Беседа не была подключена!",
                    random_id=get_random_id()
                )
        
        # Команда ПРИВЯЗАТЬ - привязка беседы к категории
        elif normalized_text == '/привязать':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/привязать')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if not self.is_chat_active(peer_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Сначала подключите беседу командой /start!",
                    random_id=get_random_id()
                )
                return
            
            keyboard = self.create_category_keyboard()
            self.vk.messages.send(
                peer_id=peer_id,
                message="Выберите категорию для беседы:",
                keyboard=keyboard,
                random_id=get_random_id()
            )
        
        # Команда ОТВЯЗАТЬ - отвязка беседы от категории
        elif normalized_text == '/отвязать':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/отвязать')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.remove_chat_category(peer_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="✅ Беседа отвязана от категории.",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ Беседа не была привязана к категории!",
                    random_id=get_random_id()
                )
        
        # Команда удаления сообщения
        elif normalized_text == '/удалить':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/удалить')
            if not self.has_permission(from_id, peer_id, required_level):
                # Пытаемся удалить команду, если есть права
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                sent_msg = self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg and 'id' in msg['reply_message']:
                try:
                    target_msg_id = msg['reply_message']['id']
                    
                    # Сначала удаляем целевое сообщение
                    result1, message1 = self.delete_messages(peer_id, target_msg_id)
                    
                    # Затем удаляем команду
                    if message_id:
                        result2, message2 = self.delete_messages(peer_id, message_id)
                    
                    if result1 == -1:
                        # Нет прав на удаление
                        error_msg = self.vk.messages.send(
                            peer_id=peer_id,
                            message="❌ Недостаточно прав для удаления сообщений! Убедитесь, что бот является администратором беседы.",
                            random_id=get_random_id()
                        )
                    elif result1 > 0:
                        # Успешно удалили
                        success_msg = self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"🗑️ Сообщение удалено!",
                            random_id=get_random_id()
                        )
                    else:
                        # Не удалось удалить
                        fail_msg = self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"❌ Не удалось удалить сообщение",
                            random_id=get_random_id()
                        )
                except Exception as e:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"❌ Ошибка удаления: {e}",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Ответьте на сообщение, которое хотите удалить!",
                    random_id=get_random_id()
                )
        
        # Команда очистки чата
        elif normalized_text.startswith('/очистить'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/очистить')
            if not self.has_permission(from_id, peer_id, required_level):
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                sent_msg = self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            count = 100
            parts = text.split()
            if len(parts) > 1:
                try:
                    count = min(int(parts[1]), 100)
                except:
                    pass
            
            # Отправляем сообщение о начале очистки
            start_msg = self.vk.messages.send(
                peer_id=peer_id,
                message=f"🧹 Начинаю очистку {count} последних сообщений...",
                random_id=get_random_id()
            )
            
            deleted_count, message = self.clear_chat(peer_id, count, from_id)
            
            # Удаляем сообщение о начале очистки
            self.delete_messages(peer_id, start_msg)
            
            if deleted_count > 0:
                report = f"🧹 Удалено {deleted_count} сообщений!"
            else:
                report = f"❌ {message}"
            
            self.vk.messages.send(
                peer_id=peer_id,
                message=report,
                random_id=get_random_id()
            )
        
        # Команда режима тишины
        elif normalized_text.startswith('/тишина'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/тишина')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            parts = text.split()
            admin_mention = get_user_mention(self.vk, from_id)
            
            if len(parts) > 1:
                if parts[1].lower() in ['выкл', 'off', 'откл']:
                    if self.disable_silence_mode(peer_id, from_id):
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"🔊 Режим тишины выключен по запросу {admin_mention}!",
                            random_id=get_random_id()
                        )
                    else:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message="ℹ️ Режим тишины не был включен!",
                            random_id=get_random_id()
                        )
                else:
                    try:
                        minutes = int(parts[1])
                        end_time = self.set_silence_mode(peer_id, minutes, from_id)
                        # Форматируем время для вывода
                        if isinstance(end_time, str) and end_time != 'permanent':
                            time_str = end_time
                        else:
                            time_str = end_time.strftime("%Y-%m-%d %H:%M:%S") if not isinstance(end_time, str) else "бессрочно"
                        
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"🔇 Режим тишины включен на {minutes} минут!\n⏳ Завершится в {time_str}",
                            random_id=get_random_id()
                        )
                    except ValueError:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message="❌ Укажите время в минутах: /тишина [время]",
                            random_id=get_random_id()
                        )
            else:
                end_time = self.set_silence_mode(peer_id, admin_id=from_id)
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"🔇 Режим тишины включен бессрочно!\n👤 По запросу: {admin_mention}",
                    random_id=get_random_id()
                )
        
        # Команда мута
        elif normalized_text.startswith('/мут'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/мут')
            if not self.has_permission(from_id, peer_id, required_level):
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg:
                target_id = msg['reply_message']['from_id']
                duration = 60
                reason = ""
                
                parts = text.split()
                if len(parts) > 1:
                    try:
                        duration = int(parts[1])
                        if len(parts) > 2:
                            reason = ' '.join(parts[2:])
                    except ValueError:
                        reason = ' '.join(parts[1:])
                
                target_mention = get_user_mention(self.vk, target_id)
                
                unmute_time = self.mute_user(target_id, duration, from_id, reason)
                time_str = unmute_time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Удаляем команду
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"🔇 Пользователь {target_mention} замьючен до {time_str}!\n📌 Причина: {reason}",
                    random_id=get_random_id()
                )
            else:
                target_id = extract_user_id(text, self.vk)
                if target_id:
                    target_mention = get_user_mention(self.vk, target_id)
                    
                    # Парсим команду /мут @user 30 спам
                    parts = text.split()
                    duration = 60
                    reason = "без указания причины"
                    
                    # Ищем цифры для длительности
                    found_duration = False
                    for i, part in enumerate(parts):
                        if part.isdigit():
                            duration = int(part)
                            found_duration = True
                            if i + 1 < len(parts):
                                reason = ' '.join(parts[i+1:])
                            break
                    
                    # Если не нашли цифр, значит причина - весь текст после упоминания
                    if not found_duration:
                        for i, part in enumerate(parts):
                            if 'id' in part or 'vk.com' in part or 'http' in part or '[' in part:
                                if i + 1 < len(parts):
                                    reason = ' '.join(parts[i+1:])
                                break
                    
                    unmute_time = self.mute_user(target_id, duration, from_id, reason)
                    time_str = unmute_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Удаляем команду
                    if message_id:
                        self.delete_messages(peer_id, message_id)
                    
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"🔇 Пользователь {target_mention} замьючен до {time_str}!\n📌 Причина: {reason}",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Укажите пользователя (упоминание, ссылка или ID) или ответьте на его сообщение: /мут @упоминание [время] [причина]",
                        random_id=get_random_id()
                    )
        
        # Команда размута
        elif normalized_text.startswith('/размут'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/размут')
            if not self.has_permission(from_id, peer_id, required_level):
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg:
                target_id = msg['reply_message']['from_id']
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.unmute_user(target_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"🔊 Пользователь {target_mention} размучен!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} не в муте!",
                        random_id=get_random_id()
                    )
            else:
                target_id = extract_user_id(text, self.vk)
                if target_id:
                    target_mention = get_user_mention(self.vk, target_id)
                    
                    if self.unmute_user(target_id, from_id):
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"🔊 Пользователь {target_mention} размучен!",
                            random_id=get_random_id()
                        )
                    else:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"ℹ️ Пользователь {target_mention} не в муте!",
                            random_id=get_random_id()
                        )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Укажите пользователя (упоминание, ссылка или ID) или ответьте на его сообщение: /размут @упоминание",
                        random_id=get_random_id()
                    )
        
        # Команда автокика
        elif normalized_text == '/автокик':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/автокик')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            new_status = self.toggle_autokick(peer_id, from_id)
            status_text = "включен" if new_status else "выключен"
            
            self.vk.messages.send(
                peer_id=peer_id,
                message=f"👢 Автокик вышедших пользователей {status_text}!",
                random_id=get_random_id()
            )
        
        # Команда акик (кик из всех чатов)
        elif normalized_text.startswith('/акик'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/акик')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                admin_mention = get_user_mention(self.vk, from_id)
                
                parts = text.split()
                reason = ""
                for i, part in enumerate(parts):
                    if part.isdigit() or 'id' in part or 'vk.com' in part or 'http' in part:
                        if i + 1 < len(parts):
                            reason = ' '.join(parts[i+1:])
                        break
                
                # Кикаем из всех чатов
                report = self.kick_from_all_chats(target_id, from_id, reason)
                
                # Формируем детальное сообщение
                message = (
                    f"👢 МАССОВЫЙ КИК ВЫПОЛНЕН\n\n"
                    f"• Пользователь: {target_mention}\n"
                    f"• Администратор: {admin_mention}\n"
                    f"• Причина: {reason if reason else 'не указана'}\n"
                    f"• Всего активных чатов: {report['total_active']}\n\n"
                )
                
                # Список успешно кикнутых чатов
                if report['chat_details']:
                    message += f"✅ Успешно кикнут из {len(report['kicked_chats'])} чатов:\n"
                    if len(report['chat_details']) <= 10:
                        message += "\n".join(report['chat_details']) + "\n\n"
                    else:
                        message += "\n".join(report['chat_details'][:10]) + "\n"
                        message += f"... и еще {len(report['kicked_chats']) - 10} чатов\n\n"
                
                # Список чатов, где не удалось кикнуть
                if report['failed_details']:
                    message += f"❌ Не удалось кикнуть из {len(report['failed_chats'])} чатов:\n"
                    if len(report['failed_details']) <= 5:
                        message += "\n".join(report['failed_details']) + "\n"
                    else:
                        message += "\n".join(report['failed_details'][:5]) + "\n"
                        message += f"... и еще {len(report['failed_chats']) - 5} чатов\n"
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя (упоминание, ссылка или ID): /акик @упоминание [причина]",
                    random_id=get_random_id()
                )
        
        # Команда кика
        elif normalized_text.startswith('/кик'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/кик')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg:
                target_id = msg['reply_message']['from_id']
                reason = ""
                
                parts = text.split()
                if len(parts) > 1:
                    reason = ' '.join(parts[1:])
                
                target_mention = get_user_mention(self.vk, target_id)
                admin_mention = get_user_mention(self.vk, from_id)
                
                # Получаем название текущего чата
                current_chat_name = self.get_chat_name(peer_id)
                
                success, chat_name = self.kick_from_chat(peer_id, target_id, from_id, reason)
                
                if success:
                    message = (
                        f"👢 КИК ВЫПОЛНЕН\n\n"
                        f"• Пользователь: {target_mention}\n"
                        f"• Администратор: {admin_mention}\n"
                        f"• Чат: {current_chat_name}\n"
                        f"• Причина: {reason if reason else 'не указана'}\n\n"
                        f"⚠️ Пользователь удален из беседы."
                    )
                    
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=message,
                        random_id=get_random_id()
                    )
                else:
                    # Проверяем, есть ли пользователь в чате
                    try:
                        members = self.vk.messages.getConversationMembers(peer_id=peer_id)
                        user_in_chat = any(member.get('member_id') == target_id for member in members['items'])
                        
                        if not user_in_chat:
                            message = f"ℹ️ Пользователь {target_mention} уже не находится в этом чате."
                        else:
                            message = (
                                f"❌ НЕ УДАЛОСЬ КИКНУТЬ\n\n"
                                f"• Пользователь: {target_mention}\n"
                                f"• Администратор: {admin_mention}\n"
                                f"• Причина ошибки: {chat_name}\n\n"
                                f"⚠️ Убедитесь, что бот является администратором беседы!"
                            )
                        
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=message,
                            random_id=get_random_id()
                        )
                    except Exception as e:
                        logger.error(f"Ошибка проверки участника чата: {e}")
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"⚠️ Ошибка при попытке кика пользователя {target_mention}: {chat_name}",
                            random_id=get_random_id()
                        )
            else:
                target_id = extract_user_id(text, self.vk)
                if target_id:
                    parts = text.split()
                    reason = ""
                    for i, part in enumerate(parts):
                        if part.isdigit() or 'id' in part or 'vk.com' in part or 'http' in part:
                            if i + 1 < len(parts):
                                reason = ' '.join(parts[i+1:])
                            break
                    
                    target_mention = get_user_mention(self.vk, target_id)
                    admin_mention = get_user_mention(self.vk, from_id)
                    current_chat_name = self.get_chat_name(peer_id)
                    
                    success, chat_name = self.kick_from_chat(peer_id, target_id, from_id, reason)
                    
                    if success:
                        message = (
                            f"👢 КИК ВЫПОЛНЕН\n\n"
                            f"• Пользователь: {target_mention}\n"
                            f"• Администратор: {admin_mention}\n"
                            f"• Чат: {current_chat_name}\n"
                            f"• Причина: {reason if reason else 'не указана'}\n\n"
                            f"⚠️ Пользователь удален из беседы."
                        )
                        
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=message,
                            random_id=get_random_id()
                        )
                    else:
                        try:
                            members = self.vk.messages.getConversationMembers(peer_id=peer_id)
                            user_in_chat = any(member.get('member_id') == target_id for member in members['items'])
                            
                            if not user_in_chat:
                                message = f"ℹ️ Пользователь {target_mention} не находится в этом чате."
                            else:
                                message = (
                                    f"❌ НЕ УДАЛОСЬ КИКНУТЬ\n\n"
                                    f"• Пользователь: {target_mention}\n"
                                    f"• Администратор: {admin_mention}\n"
                                    f"• Причина ошибки: {chat_name}\n\n"
                                    f"⚠️ Убедитесь, что бот является администратором беседы!"
                                )
                            
                            self.vk.messages.send(
                                peer_id=peer_id,
                                message=message,
                                random_id=get_random_id()
                            )
                        except Exception as e:
                            logger.error(f"Ошибка проверки участника чата: {e}")
                            self.vk.messages.send(
                                peer_id=peer_id,
                                message=f"⚠️ Ошибка при попытке кика пользователя {target_mention}: {chat_name}",
                                random_id=get_random_id()
                            )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Укажите пользователя (упоминание, ссылка или ID) или ответьте на его сообщение: /кик @упоминание [причина]",
                        random_id=get_random_id()
                    )
        
        # Команда варна
        elif normalized_text.startswith('/варн'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/варн')
            if not self.has_permission(from_id, peer_id, required_level):
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg:
                target_id = msg['reply_message']['from_id']
                reason = ""
                
                parts = text.split()
                if len(parts) > 1:
                    reason = ' '.join(parts[1:])
                
                target_mention = get_user_mention(self.vk, target_id)
                
                warn_count = self.add_warn(target_id, from_id, reason)
                
                message = (
                    f"⚠️ Пользователю {target_mention} выдано предупреждение!\n"
                    f"📌 Причина: {reason}\n"
                    f"🔥 Всего предупреждений: {warn_count}/3"
                )
                
                if warn_count >= 3:
                    self.add_to_blacklist(target_id, from_id, "3 предупреждения", 7, ["все"])
                    success, chat_name = self.kick_from_chat(peer_id, target_id, from_id, "3 предупреждения")
                    
                    message += "\n⛔ Пользователь добавлен в ЧС на 7 дней за 3 предупреждения!"
                    if success:
                        message += "\n👢 Пользователь кикнут из беседы"
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    random_id=get_random_id()
                )
            else:
                target_id = extract_user_id(text, self.vk)
                if target_id:
                    target_mention = get_user_mention(self.vk, target_id)
                    
                    reason = "без указания причины"
                    parts = text.split()
                    for i, part in enumerate(parts):
                        if part.isdigit() or 'id' in part or 'vk.com' in part or 'http' in part:
                            if i + 1 < len(parts):
                                reason = ' '.join(parts[i+1:])
                            break
                    
                    warn_count = self.add_warn(target_id, from_id, reason)
                    
                    message = (
                        f"⚠️ Пользователю {target_mention} выдано предупреждение!\n"
                        f"📌 Причина: {reason}\n"
                        f"🔥 Всего предупреждений: {warn_count}/3"
                    )
                    
                    if warn_count >= 3:
                        self.add_to_blacklist(target_id, from_id, "3 предупреждения", 7, ["все"])
                        success, chat_name = self.kick_from_chat(peer_id, target_id, from_id, "3 предупреждения")
                        
                        message += "\n⛔ Пользователь добавлен в ЧС на 7 дней за 3 предупреждения!"
                        if success:
                            message += "\n👢 Пользователь кикнут из беседы"
                    
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=message,
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Укажите пользователя (упоминание, ссылка или ID) или ответьте на его сообщение: /варн @упоминание [причина]",
                        random_id=get_random_id()
                    )
        
        # Команда разварна
        elif normalized_text.startswith('/разварн'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/разварн')
            if not self.has_permission(from_id, peer_id, required_level):
                if message_id:
                    self.delete_messages(peer_id, message_id)
                
                error_msg = f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!"
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=error_msg,
                    random_id=get_random_id()
                )
                return
            
            if 'reply_message' in msg:
                target_id = msg['reply_message']['from_id']
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.remove_warn(target_id, from_id):
                    stats = self.get_user_stats(target_id)
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ С пользователя {target_mention} снято предупреждение!\n"
                                f"⚠️ Всего предупреждений: {stats['warns']}/3",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ У пользователя {target_mention} нет предупреждений!",
                        random_id=get_random_id()
                    )
            else:
                target_id = extract_user_id(text, self.vk)
                if target_id:
                    target_mention = get_user_mention(self.vk, target_id)
                    
                    if self.remove_warn(target_id, from_id):
                        stats = self.get_user_stats(target_id)
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"✅ С пользователя {target_mention} снято предупреждение!\n"
                                    f"⚠️ Всего предупреждений: {stats['warns']}/3",
                            random_id=get_random_id()
                        )
                    else:
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=f"ℹ️ У пользователя {target_mention} нет предупреждений!",
                            random_id=get_random_id()
                        )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Укажите пользователя (упоминание, ссылка или ID) или ответьте на его сообщение: /разварн @упоминание",
                        random_id=get_random_id()
                    )
        
        # Команда статы
        elif normalized_text.startswith('/стата'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/стата')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = from_id
            parts = text.split()
            
            if len(parts) > 1:
                target_id = extract_user_id(text, self.vk)
                if not target_id:
                    target_id = from_id
            
            stats = self.get_user_stats(target_id)
            stats_message = self.format_stats(stats, target_id)
            
            self.vk.messages.send(
                peer_id=peer_id,
                message=stats_message,
                random_id=get_random_id()
            )
        
        # Команда проверки прав
        elif normalized_text == '/яадмин':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/яадмин')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            permissions_info = self.get_user_permissions_info(from_id, peer_id)
            self.vk.messages.send(
                peer_id=peer_id,
                message=permissions_info,
                random_id=get_random_id()
            )
        
        # Команда назначения локального администратора
        elif normalized_text.startswith('/падминл'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/падминл')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.add_local_admin(target_id, peer_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Пользователь {target_mention} назначен локальным администратором этого чата!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} уже является локальным администратором!",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя: /падминл @упоминание",
                    random_id=get_random_id()
                )
        
        # Команда снятия локального администратора
        elif normalized_text.startswith('/надминл'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/надминл')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.remove_local_admin(target_id, peer_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ С пользователя {target_mention} сняты права локального администратора!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} не является локальным администратором!",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя: /надминл @упоминание",
                    random_id=get_random_id()
                )
        
        # Команда назначения глобального администратора (только уровень 4 и выше)
        elif normalized_text.startswith('/падминг'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/падминг')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            parts = text.split()
            if len(parts) < 3:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Используйте: /падминг @упоминание уровень\n"
                            "Уровни: 1-Модератор, 2-Старший Модер, 3-Админ, 4-Главный Админ, 5-Со-Владелец, 6-Владелец, 7-Основатель",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(parts[1], self.vk)
            if not target_id:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверное упоминание пользователя!",
                    random_id=get_random_id()
                )
                return
            
            try:
                level = int(parts[2])
                if level < 1 or level > 7:
                    raise ValueError
            except ValueError:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверный уровень! Используйте число от 1 до 7",
                    random_id=get_random_id()
                )
                return
            
            # Проверяем, может ли администратор назначить такой уровень
            admin_level = self.get_admin_level(from_id)
            if level >= admin_level:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Вы не можете назначить уровень равный или выше вашего!",
                    random_id=get_random_id()
                )
                return
            
            target_mention = get_user_mention(self.vk, target_id)
            
            if self.set_admin_level(target_id, level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ Пользователь {target_mention} назначен {self.get_admin_level_name(level)} (уровень {level})!",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"ℹ️ Не удалось назначить пользователя {target_mention}!",
                    random_id=get_random_id()
                )
        
        # Команда снятия глобального администратора (только уровень 4 и выше)
        elif normalized_text.startswith('/надминг'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/надминг')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if not target_id:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя: /надминг @упоминание",
                    random_id=get_random_id()
                )
                return
            
            # Проверяем, может ли администратор снять этого пользователя
            admin_level = self.get_admin_level(from_id)
            target_level = self.get_admin_level(target_id)
            
            if target_level == 0:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Этот пользователь не является глобальным администратором!",
                    random_id=get_random_id()
                )
                return
            
            if admin_level <= target_level:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Вы не можете снять администратора равного или выше вашего уровня!",
                    random_id=get_random_id()
                )
                return
            
            target_mention = get_user_mention(self.vk, target_id)
            
            if self.remove_admin_level(target_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ С пользователя {target_mention} сняты права глобального администратора!",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"ℹ️ Пользователь {target_mention} не является глобальным администратором!",
                    random_id=get_random_id()
                )
        
        # Команда настройки администратора при запуске (только для начальной настройки)
        elif normalized_text.startswith('/настроитьадмин'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/настроитьадмин')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            # Проверяем, была ли уже выполнена начальная настройка
            setup_admins = DataManager.load_data(SETUP_ADMINS_FILE, list)
            if len(setup_admins) >= 3:  # Максимум 3 администратора можно настроить
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Начальная настройка администраторов уже завершена!",
                    random_id=get_random_id()
                )
                return
            
            parts = text.split()
            if len(parts) < 3:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Используйте: /настроитьадмин @упоминание уровень\n"
                            "Уровни: 1-Модератор, 2-Старший Модер, 3-Админ, 4-Главный Админ, 5-Со-Владелец, 6-Владелец, 7-Основатель",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(parts[1], self.vk)
            if not target_id:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверное упоминание пользователя!",
                    random_id=get_random_id()
                )
                return
            
            try:
                level = int(parts[2])
                if level < 1 or level > 7:
                    raise ValueError
            except ValueError:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверный уровень! Используйте число от 1 до 7",
                    random_id=get_random_id()
                )
                return
            
            target_mention = get_user_mention(self.vk, target_id)
            
            if self.setup_admin(target_id, level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ Пользователь {target_mention} настроен как {self.get_admin_level_name(level)} (уровень {level})!\n"
                            f"📊 Настроено администраторов: {len(setup_admins) + 1}/3",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"ℹ️ Не удалось настроить пользователя {target_mention}!",
                    random_id=get_random_id()
                )
        
        # Команда назначения руководства (только уровень 6 и выше)
        elif normalized_text.startswith('/рук'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/рук')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.add_leadership(target_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Пользователь {target_mention} назначен руководством!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} уже является руководством!",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя: /рук @упоминание",
                    random_id=get_random_id()
                )
        
        # Команда снятия руководства (только уровень 6 и выше)
        elif normalized_text.startswith('/срук'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/срук')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.remove_leadership(target_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ С пользователя {target_mention} сняты права руководства!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} не является руководством!",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя: /срук @упоминание",
                    random_id=get_random_id()
                )
        
        # Команда новостей
        elif normalized_text.startswith('/новости'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/новости')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            channels = self.load_news_channels()
            if not channels:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Нет добавленных каналов для новостей!",
                    random_id=get_random_id()
                )
                return
            
            # Показываем список каналов с номерами
            channel_list = "📋 Доступные каналы:\n\n"
            for i, channel_id in enumerate(channels, 1):
                try:
                    chat_name = self.get_chat_name(int(channel_id))
                    channel_list += f"{i}. {chat_name} (ID: {channel_id})\n"
                except:
                    channel_list += f"{i}. ID: {channel_id}\n"
            
            channel_list += f"\n📝 Используйте: /новости 1,2,4 ваше сообщение\n"
            channel_list += f"Где 1,2,4 - номера каналов из списка выше"
            
            # Если сообщение содержит номера каналов и текст
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                args = parts[1].strip()
                # Ищем формат "1,2,4 текст"
                match = re.match(r'^([\d,\s]+)\s+(.+)$', args)
                if match:
                    numbers_str = match.group(1)
                    news_text = match.group(2)
                    
                    # Парсим номера каналов
                    try:
                        channel_numbers = []
                        for num in numbers_str.replace(' ', '').split(','):
                            if num.strip().isdigit():
                                channel_numbers.append(int(num.strip()))
                        
                        # Отправляем новости
                        self.send_news(from_id, channel_numbers, news_text)
                        return
                    except Exception as e:
                        logger.error(f"Ошибка парсинга номеров каналов: {e}")
                        self.vk.messages.send(
                            peer_id=peer_id,
                            message=channel_list,
                            random_id=get_random_id()
                        )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=channel_list,
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=channel_list,
                    random_id=get_random_id()
                )
        
        # Команда информации о новостях
        elif normalized_text == '/инфоновости':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/инфоновости')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            news_info = self.get_news_info()
            self.vk.messages.send(
                peer_id=peer_id,
                message=news_info,
                random_id=get_random_id()
            )
        
        # Команда добавления канала новостей
        elif normalized_text == '/добавитьканал':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/добавитьканал')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.add_news_channel(peer_id, from_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="✅ Этот чат добавлен в каналы новостей!",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ Этот чат уже в списке каналов новостей!",
                    random_id=get_random_id()
                )
        
        # Команда удаления канала новостей
        elif normalized_text == '/удалитьканал':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/удалитьканал')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.remove_news_channel(peer_id, from_id):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="✅ Этот чат удален из каналов новостей!",
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="ℹ️ Этот чат не был в списке каналов новостей!",
                    random_id=get_random_id()
                )
        
        # Команда просмотра каналов новостей
        elif normalized_text == '/каналыновостей':
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/каналыновостей')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            channels = self.load_news_channels()
            if not channels:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="📢 Нет добавленных каналов для новостей.",
                    random_id=get_random_id()
                )
                return
            
            message = f"📢 Каналы новостей ({len(channels)}):\n\n"
            for i, channel_id in enumerate(channels[:20], 1):
                try:
                    chat_name = self.get_chat_name(int(channel_id))
                    message += f"{i}. {chat_name} (ID: {channel_id})\n"
                except:
                    message += f"{i}. ID: {channel_id}\n"
            
            if len(channels) > 20:
                message += f"\n... и еще {len(channels) - 20} каналов"
            
            self.vk.messages.send(
                peer_id=peer_id,
                message=message,
                random_id=get_random_id()
            )
        
        # Команда добавления в ЧС (только для чатов категории "га")
        elif normalized_text.startswith('/чс'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/чс')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.get_chat_category(peer_id) != "га":
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Эта команда доступна только в чатах категории ГА/ЗГА!",
                    random_id=get_random_id()
                )
                return
            
            parts = text.split()
            if len(parts) < 4:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Используйте: /чс @упоминание категория дни причина\n"
                            "Категории: 1 - админка, 2 - лидерка, 3 - замки, 4 - все",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(parts[1], self.vk)
            if not target_id:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверное упоминание пользователя!",
                    random_id=get_random_id()
                )
                return
            
            category_map = {
                '1': 'администрация',
                '2': 'лидеры',
                '3': 'заместители',
                '4': 'все'
            }
            
            category_num = parts[2]
            if category_num not in category_map:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверная категория! Используйте: 1 - админка, 2 - лидерка, 3 - замки, 4 - все",
                    random_id=get_random_id()
                )
                return
            
            category = category_map[category_num]
            categories = [category]
            
            try:
                duration_days = int(parts[3])
                if duration_days < 0:
                    raise ValueError
            except ValueError:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Неверное количество дней!",
                    random_id=get_random_id()
                )
                return
            
            reason = ' '.join(parts[4:]) if len(parts) > 4 else "без указания причины"
            
            if self.add_to_blacklist(target_id, from_id, reason, duration_days, categories):
                target_mention = get_user_mention(self.vk, target_id)
                
                kicked_chats = []
                active_chats = self.load_active_chats()
                
                for chat_id_str in active_chats:
                    chat_id = int(chat_id_str)
                    chat_category = self.get_chat_category(chat_id)
                    
                    if self.is_in_blacklist(target_id, chat_category):
                        success, chat_name = self.kick_from_chat(chat_id, target_id, from_id, f"ЧС: {reason}")
                        if success:
                            kicked_chats.append(chat_id_str)
                
                message = f"⛔ Пользователь {target_mention} добавлен в ЧС!\n📌 Причина: {reason}\n"
                
                if duration_days > 0:
                    unban_date = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
                    message += f"📅 Срок блокировки: {duration_days} дней (до {unban_date})\n"
                else:
                    message += "📅 Срок блокировки: бессрочно\n"
                
                message += f"🎯 Категория: {category}\n"
                
                if kicked_chats:
                    message += f"👢 Пользователь кикнут из {len(kicked_chats)} чатов"
                else:
                    message += "ℹ️ Пользователь не был кикнут из чатов"
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    random_id=get_random_id()
                )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ Не удалось добавить пользователя в ЧС!",
                    random_id=get_random_id()
                )
        
        # Команда снятия ЧС (только для чатов категории "га")
        elif normalized_text.startswith('/снятьчс'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/снятьчс')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.get_chat_category(peer_id) != "га":
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Эта команда доступна только в чатах категории ГА/ЗГА!",
                    random_id=get_random_id()
                )
                return
            
            target_id = extract_user_id(text, self.vk)
            if target_id:
                target_mention = get_user_mention(self.vk, target_id)
                
                if self.remove_from_blacklist(target_id, from_id):
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Пользователь {target_mention} удален из ЧС!",
                        random_id=get_random_id()
                    )
                else:
                    self.vk.messages.send(
                        peer_id=peer_id,
                        message=f"ℹ️ Пользователь {target_mention} не был в ЧС!",
                        random_id=get_random_id()
                    )
            else:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Укажите пользователя (упоминание, ссылка или ID): /снятьчс @пользователь",
                    random_id=get_random_id()
                )
        
        # Команда информации о пользователе (только для чатов категории "га")
        elif normalized_text.startswith('/инфо'):
            # Проверяем доступ к команде
            required_level = self.get_command_access_level('/инфо')
            if not self.has_permission(from_id, peer_id, required_level):
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"❌ {get_user_mention(self.vk, from_id)}, команда доступна только для {self.get_admin_level_name(required_level)} и выше!",
                    random_id=get_random_id()
                )
                return
            
            if self.get_chat_category(peer_id) != "га":
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Эта команда доступна только в чатах категории ГА/ЗГА!",
                    random_id=get_random_id()
                )
                return
            
            target_id = from_id
            parts = text.split()
            
            if len(parts) > 1:
                target_id = extract_user_id(text, self.vk)
                if not target_id:
                    target_id = from_id
            
            target_mention = get_user_mention(self.vk, target_id)
            
            blacklist_info = self.get_blacklist_info(target_id)
            
            if blacklist_info:
                info_text = self.format_blacklist_info(target_id, blacklist_info)
            else:
                info_text = self.format_blacklist_history_info(target_id)
            
            if self.is_muted(target_id):
                info_text += "\n🔇 Пользователь в муте"
            
            self.vk.messages.send(
                peer_id=peer_id,
                message=info_text,
                random_id=get_random_id()
            )
        
        # Реакция на слово "бог" в любом регистре
        elif 'бог' in text.lower():
            user_mention = get_user_mention(self.vk, from_id)
            self.vk.messages.send(
                peer_id=peer_id,
                message=f"{user_mention}, всё в его руках!",
                random_id=get_random_id()
            )
        
        # Реакция на слово "бот" в любом регистре
        elif 'бот' in text.lower():
            user_mention = get_user_mention(self.vk, from_id)
            self.vk.messages.send(
                peer_id=peer_id,
                message=f"{user_mention}, я здесь! Чем могу помочь?",
                random_id=get_random_id()
            )
        
        # Реакция на неизвестные команды
        elif text.startswith(('!', '/', 'І', 'і')):
            self.vk.messages.send(
                peer_id=peer_id,
                message="❌ Неизвестная команда. Используйте /помощь для списка команд.",
                random_id=get_random_id()
            )
    
    def process_callback(self, event):
        """Обрабатывает callback-события от кнопок"""
        try:
            payload = event.object.payload
            
            if isinstance(payload, str):
                payload = json.loads(payload)
            
            user_id = event.object.user_id
            peer_id = event.object.peer_id
            
            if 'category' in payload:
                # Проверяем доступ к команде
                required_level = self.get_command_access_level('/привязать')
                if not self.has_permission(user_id, peer_id, required_level):
                    return
                
                category = payload['category']
                category_names = {
                    'администрация': 'администрации',
                    'лидеры': 'лидеров',
                    'заместители': 'заместителей',
                    'га': 'ГА/ЗГА'
                }
                
                self.set_chat_category(peer_id, category)
                admin_mention = get_user_mention(self.vk, user_id)
                
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=f"{admin_mention}, вы присоединили беседу \"{peer_id}\" к категории для {category_names.get(category, category)}.",
                    random_id=get_random_id()
                )
            
            elif 'cancel' in payload:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Привязка отменена.",
                    random_id=get_random_id()
                )
            
            self.vk.messages.sendMessageEventAnswer(
                event_id=event.object.event_id,
                user_id=user_id,
                peer_id=peer_id,
            )
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка обработки callback: {e}")
    
    def run(self):
        """Запускает чат-бота"""
        logger.info("Чат-бот запущен и готов к работе!")
        logger.info(f"📁 Логи будут сохраняться в папке: {LOGS_DIR}")
        logger.info("🔄 Чат-бот отвечает только в беседах")
        logger.info("🔄 Для остановки нажмите Ctrl+C")
        
        self.cleanup_old_logs(days_to_keep=30)
        
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                try:
                    self.process_message(event)
                except Exception as e:
                    logger.error(f"Ошибка в чат-боте: {e}")
            
            elif event.type == VkBotEventType.MESSAGE_EVENT:
                try:
                    self.process_callback(event)
                except Exception as e:
                    logger.error(f"Ошибка обработки callback: {e}")

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================
def main():
    """Запускает чат-бота"""
    logger.info("Запуск чат-бота...")
    
    try:
        # Создаем и запускаем только чат-бота
        chat_bot = ChatBot(VK_TOKEN_CHAT)
        chat_bot.run()
            
    except KeyboardInterrupt:
        logger.info("Завершение работы чат-бота...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске чат-бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
