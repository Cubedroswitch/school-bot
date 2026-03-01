import os
import json
import logging
import requests  # Добавляем requests
import hashlib
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Загружаем переменные из .env файла
from dotenv import load_dotenv
load_dotenv()

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters
)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not BOT_TOKEN:
    print("❌ ОШИБКА: Не найден BOT_TOKEN в .env файле")
    exit(1)
    
if not MISTRAL_API_KEY:
    print("❌ ОШИБКА: Не найден MISTRAL_API_KEY в .env файле")
    print("💡 Получите ключ на console.mistral.ai")
    exit(1)

print("✅ Токены успешно загружены из .env файла")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING_SUBJECT, CHOOSING_TOPIC, ANSWERING_QUESTION = range(3)
# Состояния для ConversationHandler
CHOOSING_SUBJECT, CHOOSING_TOPIC, ANSWERING_QUESTION = range(3)
# ========== МОДЕЛИ ДАННЫХ ==========
@dataclass
class Question:
    id: int
    text: str
    correct_answer: str
    subject: str
    topic: str
    difficulty: str

class UserProgress:
    """Отслеживание прогресса пользователя"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_question: Optional[Question] = None
        self.score: int = 0
        self.total_questions: int = 0
        self.start_time: datetime = datetime.now()
        self.attempts: Dict[int, int] = {}  # question_id -> attempts
        
    def add_correct(self):
        self.score += 1
        self.total_questions += 1
        
    def add_incorrect(self):
        self.total_questions += 1
        
    def get_accuracy(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return (self.score / self.total_questions) * 100

# ========== БАЗА ДАННЫХ ВОПРОСОВ ==========
class QuestionDatabase:
    """Простая база вопросов в памяти"""
    def __init__(self):
        self.questions: List[Question] = []
        self.load_sample_questions()
    def load_sample_questions(self):
        """Загружаем примерные вопросы по предметам"""
        sample_data = [
        # ========== МАТЕМАТИКА (8 вопросов) ==========
            Question(
                id=1,
                text="Что такое производная функции?",
                correct_answer="Производная функции - это предел отношения приращения функции к приращению аргумента при стремлении приращения аргумента к нулю. Она показывает скорость изменения функции.",
                subject="математика",
                topic="производные",
                difficulty="средняя"
            ),
            Question(
                id=2,
                text="Что такое интеграл?",
                correct_answer="Интеграл - это операция, обратная дифференцированию. Определенный интеграл вычисляет площадь под кривой на заданном интервале.",
                subject="математика",
                topic="интегралы",
                difficulty="средняя"
            ),
            Question(
                id=3,
                text="Что такое теорема Пифагора?",
                correct_answer="В прямоугольном треугольнике квадрат гипотенузы равен сумме квадратов катетов: c² = a² + b².",
                subject="математика",
                topic="геометрия",
                difficulty="легкая"
            ),
            Question(
                id=4,
                text="Что такое логарифм?",
                correct_answer="Логарифм числа b по основанию a - это показатель степени, в которую нужно возвести a, чтобы получить b: logₐb = x, если aˣ = b.",
                subject="математика",
                topic="алгебра",
                difficulty="средняя"
            ),
            Question(
                id=5,
                text="Что такое факториал?",
                correct_answer="Факториал натурального числа n - это произведение всех натуральных чисел от 1 до n. Обозначается n!. Например: 5! = 1×2×3×4×5 = 120.",
                subject="математика",
                topic="комбинаторика",
                difficulty="легкая"
            ),
            Question(
                id=6,
                text="Что такое комплексные числа?",
                correct_answer="Комплексное число имеет вид a + bi, где a и b - действительные числа, i - мнимая единица (i² = -1).",
                subject="математика",
                topic="алгебра",
                difficulty="сложная"
            ),
            Question(
                id=7,
                text="Что такое вектор?",
                correct_answer="Вектор - это направленный отрезок, характеризующийся длиной (модулем) и направлением. В математике используется для представления величин, имеющих направление.",
                subject="математика",
                topic="геометрия",
                difficulty="средняя"
            ),
            Question(
                id=8,
                text="Что такое матрица?",
                correct_answer="Матрица - это прямоугольная таблица чисел, расположенных в строках и столбцах. Используется для решения систем линейных уравнений и в линейной алгебре.",
                subject="математика",
                topic="алгебра",
                difficulty="сложная"
            ),
            
            # ========== ФИЗИКА (18 вопросов) ==========
            Question(
                id=9,
                text="Сформулируйте второй закон Ньютона.",
                correct_answer="Второй закон Ньютона: сила, действующая на тело, равна произведению массы тела на его ускорение. F = ma.",
                subject="физика",
                topic="динамика",
                difficulty="легкая"
            ),
            Question(
                id=10,
                text="Что такое закон Ома?",
                correct_answer="Сила тока в проводнике прямо пропорциональна напряжению и обратно пропорциональна сопротивлению: I = U/R.",
                subject="физика",
                topic="электричество",
                difficulty="средняя"
            ),
            Question(
                id=11,
                text="Что такое кинетическая энергия?",
                correct_answer="Кинетическая энергия - это энергия движущегося тела, равная половине произведения массы тела на квадрат его скорости: Eк = mv²/2.",
                subject="физика",
                topic="энергия",
                difficulty="средняя"
            ),
            Question(
                id=12,
                text="Что такое потенциальная энергия?",
                correct_answer="Потенциальная энергия - это энергия взаимодействия тел или частей тела. Для тела, поднятого на высоту h: Eп = mgh.",
                subject="физика",
                topic="энергия",
                difficulty="средняя"
            ),
            Question(
                id=13,
                text="Что такое закон сохранения энергии?",
                correct_answer="В замкнутой системе полная механическая энергия остается постоянной: Eк + Eп = const.",
                subject="физика",
                topic="энергия",
                difficulty="средняя"
            ),
            Question(
                id=14,
                text="Что такое давление?",
                correct_answer="Давление - это физическая величина, равная отношению силы, действующей перпендикулярно поверхности, к площади этой поверхности: P = F/S.",
                subject="физика",
                topic="механика",
                difficulty="легкая"
            ),
            Question(
                id=15,
                text="Что такое удельная теплоемкость?",
                correct_answer="Удельная теплоемкость - это количество теплоты, необходимое для нагревания 1 кг вещества на 1 °C. Измеряется в Дж/(кг·°C).",
                subject="физика",
                topic="термодинамика",
                difficulty="средняя"
            ),
            Question(
                id=16,
                text="Что такое сила Архимеда?",
                correct_answer="Сила Архимеда - выталкивающая сила, действующая на тело, погруженное в жидкость или газ. Равна весу вытесненной жидкости: F = ρgV.",
                subject="физика",
                topic="гидростатика",
                difficulty="средняя"
            ),
            # НОВЫЕ ВОПРОСЫ ПО ФИЗИКЕ:
            Question(
                id=25,
                text="Что такое первая космическая скорость?",
                correct_answer="Первая космическая скорость - минимальная скорость, которую нужно сообщить телу, чтобы оно стало искусственным спутником Земли. Для Земли ≈ 7,9 км/с.",
                subject="физика",
                topic="механика",
                difficulty="средняя"
            ),
            Question(
                id=26,
                text="Что такое закон всемирного тяготения?",
                correct_answer="Закон всемирного тяготения: два тела притягиваются с силой, прямо пропорциональной произведению их масс и обратно пропорциональной квадрату расстояния между ними: F = G(m₁m₂)/r².",
                subject="физика",
                topic="гравитация",
                difficulty="средняя"
            ),
            Question(
                id=27,
                text="Что такое момент силы?",
                correct_answer="Момент силы - это физическая величина, характеризующая вращательное действие силы. Равен произведению силы на плечо: M = F·d.",
                subject="физика",
                topic="механика",
                difficulty="средняя"
            ),
            Question(
                id=28,
                text="Что такое фотоэффект?",
                correct_answer="Фотоэффект - это явление вырывания электронов из вещества под действием света. Объясняется квантовой теорией света.",
                subject="физика",
                topic="квантовая физика",
                difficulty="сложная"
            ),
            Question(
                id=29,
                text="Что такое закон Гука?",
                correct_answer="Закон Гука: сила упругости, возникающая при деформации тела, пропорциональна величине деформации: F = -kx, где k - коэффициент жесткости.",
                subject="физика",
                topic="механика",
                difficulty="средняя"
            ),
            Question(
                id=30,
                text="Что такое КПД (коэффициент полезного действия)?",
                correct_answer="КПД - это безразмерная величина, показывающая эффективность работы устройства. Равен отношению полезной работы к затраченной энергии: η = (Aполезная / Aзатраченная) × 100%.",
                subject="физика",
                topic="энергетика",
                difficulty="средняя"
            ),
            Question(
                id=31,
                text="Что такое электромагнитная индукция?",
                correct_answer="Электромагнитная индукция - явление возникновения электрического тока в замкнутом контуре при изменении магнитного потока через этот контур.",
                subject="физика",
                topic="электричество",
                difficulty="средняя"
            ),
            Question(
                id=32,
                text="Что такое период колебаний?",
                correct_answer="Период колебаний - время, за которое совершается одно полное колебание. Обозначается T, измеряется в секундах.",
                subject="физика",
                topic="колебания",
                difficulty="легкая"
            ),
            Question(
                id=33,
                text="Что такое фокусное расстояние линзы?",
                correct_answer="Фокусное расстояние линзы - расстояние от оптического центра линзы до ее фокуса. Обозначается F, определяет оптическую силу линзы.",
                subject="физика",
                topic="оптика",
                difficulty="средняя"
            ),
            Question(
                id=34,
                text="Что такое атомная масса?",
                correct_answer="Атомная масса - масса атома химического элемента, выраженная в атомных единицах массы. Примерно равна сумме масс протонов и нейтронов в ядре.",
                subject="физика",
                topic="атомная физика",
                difficulty="средняя"
            ),
            
            # ========== ИНФОРМАТИКА (8 вопросов) ==========
            Question(
                id=17,
                text="Что такое алгоритм?",
                correct_answer="Алгоритм - это конечная последовательность четких инструкций для решения конкретной задачи за конечное число шагов.",
                subject="информатика",
                topic="алгоритмы",
                difficulty="легкая"
            ),
            Question(
                id=18,
                text="Что такое бинарный поиск?",
                correct_answer="Бинарный поиск - это алгоритм поиска элемента в отсортированном массиве путем последовательного деления интервала поиска пополам.",
                subject="информатика",
                topic="алгоритмы",
                difficulty="средняя"
            ),
            Question(
                id=19,
                text="Что такое ООП (объектно-ориентированное программирование)?",
                correct_answer="ООП - это парадигма программирования, основанная на концепции объектов, которые содержат данные и методы. Основные принципы: инкапсуляция, наследование, полиморфизм.",
                subject="информатика",
                topic="программирование",
                difficulty="сложная"
            ),
            Question(
                id=20,
                text="Что такое переменная в программировании?",
                correct_answer="Переменная - это именованная область памяти для хранения данных, значение которой может изменяться в ходе выполнения программы.",
                subject="информатика",
                topic="программирование",
                difficulty="легкая"
            ),
            Question(
                id=21,
                text="Что такое рекурсия?",
                correct_answer="Рекурсия - это процесс, при котором функция вызывает саму себя непосредственно или через другие функции. Обязательно должно быть условие выхода из рекурсии.",
                subject="информатика",
                topic="алгоритмы",
                difficulty="средняя"
            ),
            Question(
                id=22,
                text="Что такое база данных?",
                correct_answer="База данных - это организованная структура для хранения, обработки и поиска информации. Состоит из таблиц, записей и полей.",
                subject="информатика",
                topic="базы данных",
                difficulty="средняя"
            ),
            Question(
                id=23,
                text="Что такое SQL?",
                correct_answer="SQL (Structured Query Language) - язык структурированных запросов для работы с реляционными базами данных. Используется для создания, модификации и управления данными.",
                subject="информатика",
                topic="базы данных",
                difficulty="средняя"
            ),
            Question(
                id=24,
                text="Что такое API?",
                correct_answer="API (Application Programming Interface) - набор определений, протоколов и инструментов для создания программного обеспечения. Позволяет программам взаимодействовать друг с другом.",
                subject="информатика",
                topic="программирование",
                difficulty="средняя"
            )
        ]
        self.questions = sample_data
        logger.info(f"Загружено {len(self.questions)} вопросов")
    def get_questions_by_subject(self, subject: str) -> List[Question]:
        return [q for q in self.questions if q.subject == subject]
    
    def get_question_by_id(self, q_id: int) -> Optional[Question]:
        for q in self.questions:
            if q.id == q_id:
                return q
        return None
    
    def get_random_question(self, subject: str = None, topic: str = None) -> Optional[Question]:
        import random
        filtered = self.questions
        if subject:
            filtered = [q for q in filtered if q.subject == subject]
        if topic:
            filtered = [q for q in filtered if q.topic == topic]
        return random.choice(filtered) if filtered else None
    
    def get_all_subjects(self) -> List[str]:
        subjects = list(set(q.subject for q in self.questions))
        return sorted(subjects)
# ========== ИИ МОДУЛЬ ПРОВЕРКИ ==========
class AnswerChecker:
    """Проверка ответов через Mistral API (через requests)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
    def _get_cache_key(self, question: str, answer: str) -> str:
        key_str = f"{question}:{answer}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def check_with_mistral(self, question, user_answer):
        """Основной метод проверки"""
        cache_key = self._get_cache_key(question.text, user_answer)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        # Промпт для Mistral
        prompt = f"""
        Ты преподаватель. Оцени ответ ученика от 0 до 100.
        
        ВОПРОС: {question.text}
        ПРАВИЛЬНЫЙ ОТВЕТ: {question.correct_answer}
        ОТВЕТ УЧЕНИКА: {user_answer}
        
        Верни только JSON:
        {{
            "score": число 0-100,
            "feedback": "короткий комментарий",
            "is_correct": true/false
        }}
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "mistral-tiny",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 150
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result_json = response.json()
                content = result_json['choices'][0]['message']['content'].strip()
                
                # Пытаемся распарсить JSON
                try:
                    # Ищем JSON в тексте
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("Не найден JSON")
                except:
                    # Если не удалось распарсить
                    result = {
                        "score": 75,
                        "feedback": "Ответ принят",
                        "is_correct": True
                    }
            else:
                # Ошибка API
                result = {
                    "score": 70,
                    "feedback": "Демо-оценка",
                    "is_correct": True
                }
                
        except Exception as e:
            # Если вообще не удалось подключиться
            print(f"⚠️ Mistral недоступен: {e}")
            result = {
                "score": min(len(user_answer) * 4, 100),
                "feedback": f"Демо: длина {len(user_answer)} символов",
                "is_correct": len(user_answer) > 10
            }
        
        # Добавляем дополнительные поля
        result["mistakes"] = []
        result["correct_elements"] = ["Понятие темы"] if result.get("is_correct", False) else []
        result["question_id"] = question.id
        result["subject"] = question.subject
        result["topic"] = question.topic
        
        # Кэшируем
        if len(self.cache) < 100:
            self.cache[cache_key] = result
            
        print(f"✅ Проверен вопрос {question.id}, оценка: {result.get('score', 0)}")
        return result
    
    def get_cache_stats(self):
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache)
        }
    def simple_similarity_check(self, correct: str, user: str) -> float:
        """
        Простая проверка схожести (резервный метод)
        """
        # Упрощенная проверка по ключевым словам
        correct_lower = correct.lower()
        user_lower = user.lower()
        
        # Считаем совпадение ключевых слов
        correct_words = set(correct_lower.split())
        user_words = set(user_lower.split())
        
        if not correct_words:
            return 0.0
            
        common_words = correct_words.intersection(user_words)
        similarity = len(common_words) / len(correct_words)
        
        return similarity
# ========== ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ==========
db = QuestionDatabase()
checker = AnswerChecker(MISTRAL_API_KEY)  # ИСПРАВЛЕНО: передаем ключ Mistral
user_sessions: Dict[int, UserProgress] = {}
# ========== КОМАНДЫ БОТА ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Создаем или получаем сессию пользователя
    if user_id not in user_sessions:
        user_sessions[user_id] = UserProgress(user_id)
        logger.info(f"Создана новая сессия для пользователя {user_id}")
    
    welcome_text = f"""
    👋 Привет, {user.first_name}!
    
    🤖 *Я — бот для повторения теории*
    
    📚 *Предметы:*
    • Математика (производные, интегралы, геометрия)
    • Физика (динамика, электричество)
    • Информатика (алгоритмы, программирование)
    
    ✨ *Особенности:*
    • ИИ проверяет твои ответы
    • Понимает разные формулировки
    • Дает подробную обратную связь
    
    🚀 *Начнем?*
    """
    
    keyboard = [
        [InlineKeyboardButton("📚 Начать тест", callback_data="start_test")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="progress")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    return CHOOSING_SUBJECT

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
    🤖 *Как работает бот:*
    
    1. Выбери предмет (математика, физика, информатика)
    2. Читай вопрос и пиши ответ *своими словами*
    3. ИИ проверит твой ответ и даст обратную связь
    4. Получай баллы и отслеживай прогресс
    
    ✨ *Особенности:*
    • ИИ понимает разные формулировки
    • Учитывает частично правильные ответы
    • Дает подробные комментарии
    
    📝 *Пример ответа:*
    *Вопрос:* Что такое производная?
    *Твой ответ:* Это скорость изменения функции
    
    Бот поймет, что это правильный, хотя и краткий ответ!
    
    ⚡ *Команды:*
    /start - начать заново
    /test - начать тестирование
    /progress - моя статистика
    /help - эта справка
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="start_test")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return CHOOSING_SUBJECT

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогресс пользователя"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        progress = user_sessions[user_id]
        learning_minutes = int((datetime.now() - progress.start_time).total_seconds() / 60)
        
        progress_text = f"""
        📊 *Твой прогресс:*
        
        ✅ Правильных ответов: {progress.score}
        📝 Всего вопросов: {progress.total_questions}
        🎯 Точность: {progress.get_accuracy():.1f}%
        ⏱ Время обучения: {learning_minutes} мин
        
        🏆 *Статистика ИИ:*
        Кэш попаданий: {checker.get_cache_stats()['hit_rate']:.1f}%
        """
    else:
        progress_text = "📭 Ты еще не начал тестирование. Нажми /start"
    
    keyboard = [
        [InlineKeyboardButton("➡️ Продолжить тест", callback_data="next_question")],
        [InlineKeyboardButton("📚 Выбрать предмет", callback_data="start_test")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(progress_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(progress_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return CHOOSING_SUBJECT
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать тестирование - выбор предмета"""
    keyboard = [
        [
            InlineKeyboardButton("📐 Математика", callback_data="subject_математика"),
            InlineKeyboardButton("⚡ Физика", callback_data="subject_физика"),
        ],
        [
            InlineKeyboardButton("💻 Информатика", callback_data="subject_информатика"),
            InlineKeyboardButton("🎲 Случайный", callback_data="subject_random"),
        ],
        [
            InlineKeyboardButton("📊 Прогресс", callback_data="progress"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "📚 *Выбери предмет для тестирования:*"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return CHOOSING_SUBJECT
async def handle_subject_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора предмета"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data  # "subject_математика" или "subject_random"
    
    subject = data.split("_")[1]
    
    # Сохраняем выбранный предмет в контексте
    context.user_data['subject'] = subject
    
    # Получаем случайный вопрос
    if subject == "random":
        question = db.get_random_question()
        subject_display = "случайный"
    else:
        question = db.get_random_question(subject=subject)
        subject_display = subject
    
    if not question:
        await query.edit_message_text("❌ Вопросы по этой теме не найдены")
        return ConversationHandler.END
    
    # Сохраняем вопрос в сессии пользователя
    if user_id in user_sessions:
        user_sessions[user_id].current_question = question
    
    # Показываем вопрос
    question_text = f"""
    📝 *Вопрос ({subject_display}, {question.topic}):*
    
    *{question.text}*
    
    💡 *Напиши ответ своими словами:*
    """
    
    keyboard = [
        [InlineKeyboardButton("🔙 Выбрать другой предмет", callback_data="start_test")],
        [InlineKeyboardButton("❌ Завершить тест", callback_data="cancel_test")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        question_text, 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ANSWERING_QUESTION

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа пользователя"""
    user_id = update.effective_user.id
    user_answer = update.message.text.strip()
    
    # Проверяем длину ответа
    if len(user_answer) < 3:
        await update.message.reply_text("❌ Ответ слишком короткий. Попробуйте ответить подробнее.")
        return ANSWERING_QUESTION
    
    # Получаем текущий вопрос из сессии
    if user_id not in user_sessions or not user_sessions[user_id].current_question:
        await update.message.reply_text("❌ Сессия устарела. Начни заново с /start")
        return ConversationHandler.END
    
    progress = user_sessions[user_id]
    question = progress.current_question
    
    # Показываем, что идет проверка
    checking_msg = await update.message.reply_text(
        "🔍 *ИИ проверяет ваш ответ...*",
        parse_mode='Markdown'
    )
    
    # Проверяем ответ с помощью ИИ
    result = checker.check_with_mistral(question, user_answer)
    
    # Обновляем прогресс
    score = result.get('score', 0)
    if result.get('is_correct', False) or score >= 70:
        progress.add_correct()
        emoji = "✅"
        result_text = "Правильно!"
    elif score >= 40:
        progress.add_incorrect()
        emoji = "⚠️"
        result_text = "Частично правильно"
    else:
        progress.add_incorrect()
        emoji = "❌"
        result_text = "Неправильно"
    # Формируем ответ
    feedback_text = f"""
    {emoji} *{result_text}*
    
    📊 *Оценка:* {score}/100
    📝 *Предмет:* {question.subject.capitalize()}
    🏷 *Тема:* {question.topic}
    
    💬 *Комментарий ИИ:*
    {result.get('feedback', 'Нет комментария')}"""
    if score<70:
        feedback_text+=f"""
    

    📘 *Правильный ответ:*
    {question.correct_answer}
    """
    
    mistakes = result.get('mistakes', [])
    if mistakes:
        feedback_text += "\n📝 *Ошибки:*\n"
        for i, mistake in enumerate(mistakes[:3], 1):
            feedback_text += f"{i}. {mistake}\n"
    
    correct_elements = result.get('correct_elements', [])
    if correct_elements:
        feedback_text += "\n✨ *Вы правильно указали:*\n"
        for i, element in enumerate(correct_elements[:3], 1):
            feedback_text += f"{i}. {element}\n"
    
    accuracy = progress.get_accuracy()
    feedback_text += f"""
    📈 *Ваша статистика:*
    Правильно: {progress.score}/{progress.total_questions} ({accuracy:.1f}%)
    
    *Что дальше?*
    """
    
    keyboard = [
        [
            InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question"),
            InlineKeyboardButton("🔁 Повторить тему", callback_data=f"repeat_{question.topic}")
        ],
        [
            InlineKeyboardButton("📊 Прогресс", callback_data="progress"),
            InlineKeyboardButton("📚 Выбрать предмет", callback_data="start_test")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await checking_msg.delete()
    await update.message.reply_text(
        feedback_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return CHOOSING_SUBJECT
async def show_correct_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать правильный ответ на вопрос"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID вопроса из callback_data
    data = query.data
    question_id = int(data.split("_")[2])  # Получаем число после "show_answer_"
    
    # Находим вопрос в базе
    question = db.get_question_by_id(question_id)
    
    if question:
        answer_text = f"""
        📘 *Правильный ответ:*
        
        *Вопрос:* {question.text}
        
        ✅ *Ответ:* {question.correct_answer}
        
        📚 *Предмет:* {question.subject}
        🏷 *Тема:* {question.topic}
        
        💡 *Пояснение:* Этот ответ считается эталонным.
        """
        
        # Кнопки для возврата
        keyboard = [
            [InlineKeyboardButton("🔙 Вернуться к тестированию", callback_data="start_test")],
            [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            answer_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "❌ Вопрос не найден",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="start_test")]])
        )
    
    return CHOOSING_SUBJECT
    
    
    # Показываем ошибки, если есть
    mistakes = result.get('mistakes', [])
    if mistakes:
        feedback_text += "\n📝 *Ошибки:*\n"
        for i, mistake in enumerate(mistakes[:3], 1):  # Показываем только первые 3
            feedback_text += f"{i}. {mistake}\n"
    
    # Показываем правильные элементы
    correct_elements = result.get('correct_elements', [])
    if correct_elements:
        feedback_text += "\n✨ *Вы правильно указали:*\n"
        for i, element in enumerate(correct_elements[:3], 1):  # Показываем только первые 3
            feedback_text += f"{i}. {element}\n"
    
    # Добавляем статистику
    accuracy = progress.get_accuracy()
    feedback_text += f"""
    📈 *Ваша статистика:*
    Правильно: {progress.score}/{progress.total_questions} ({accuracy:.1f}%)
    
    *Что дальше?*
    """
    
    # Кнопки для следующих действий
    keyboard = [
        [
            InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question"),
            InlineKeyboardButton("🔁 Повторить тему", callback_data=f"repeat_{question.topic}")
        ],
        [
            InlineKeyboardButton("📖 Показать ответ", callback_data=f"show_answer_{question.id}"),
            InlineKeyboardButton("📊 Прогресс", callback_data="progress")
        ],
        [
            InlineKeyboardButton("📚 Выбрать предмет", callback_data="start_test")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Удаляем сообщение "проверяем" и отправляем результат
    await checking_msg.delete()
    await update.message.reply_text(
        feedback_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return CHOOSING_SUBJECT
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "next_question":
        # Получаем следующий случайный вопрос
        user_id = update.effective_user.id
        if user_id in user_sessions:
            subject = user_sessions[user_id].current_question.subject if user_sessions[user_id].current_question else None
            question = db.get_random_question(subject=subject)
            if question:
                user_sessions[user_id].current_question = question
                
                question_text = f"""
                📝 *Следующий вопрос ({question.subject}, {question.topic}):*
                
                *{question.text}*
                
                💡 *Напиши ответ своими словами:*
                """
                
                keyboard = [
                    [InlineKeyboardButton("🔙 Выбрать другой предмет", callback_data="start_test")],
                    [InlineKeyboardButton("❌ Завершить тест", callback_data="cancel_test")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    question_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return ANSWERING_QUESTION
    
    elif data == "progress":
        await show_progress(update, context)
    elif data == "start_test":
        await start_test(update, context)
    elif data == "help":
        await help_command(update, context)
    elif data.startswith("repeat_"):
        topic = data.split("_")[1]
        # Получаем вопрос по этой теме
        questions = [q for q in db.questions if q.topic == topic]
        if questions:
            import random
            question = random.choice(questions)
            user_id = update.effective_user.id
            if user_id in user_sessions:
                user_sessions[user_id].current_question = question
            
            question_text = f"""
            🔁 *Повторение темы "{topic}":*
            
            *{question.text}*
            
            💡 *Напиши ответ своими словами:*
            """
            
            keyboard = [
                [InlineKeyboardButton("🔙 Выбрать другой предмет", callback_data="start_test")],
                [InlineKeyboardButton("❌ Завершить тест", callback_data="cancel_test")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                question_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return ANSWERING_QUESTION
    
    elif data == "cancel_test":
        await cancel(update, context)
    elif data.startswith("show_answer_"):
        await show_correct_answer(update, context)
    
    return CHOOSING_SUBJECT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена теста"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        progress = user_sessions[user_id]
        learning_minutes = int((datetime.now() - progress.start_time).total_seconds() / 60)
        
        # Показываем итоговую статистику
        final_text = f"""
        🏁 *Тест завершен!*
        
        📊 *Итоговая статистика:*
        ✅ Правильных ответов: {progress.score}
        📝 Всего вопросов: {progress.total_questions}
        🎯 Точность: {progress.get_accuracy():.1f}%
        ⏱ Время тестирования: {learning_minutes} мин
        
        🧠 *Статистика ИИ:*
        Использовано кэша: {checker.get_cache_stats()['hit_rate']:.1f}%
        
        Чтобы начать заново, нажми /start
        """
# Очищаем сессию
        del user_sessions[user_id]
    else:
        final_text = "Тест завершен. Чтобы начать заново, нажми /start"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(final_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(final_text, parse_mode='Markdown')
    
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=True)
    
    error_text = "❌ Произошла ошибка. Попробуйте еще раз или начните заново с /start"
    
    if update and update.effective_message:
        await update.effective_message.reply_text(error_text)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    """Запуск бота"""
    print("=" * 50)
    print("🤖 Запуск школьного бота с ИИ")
    print(f"📚 Загружено вопросов: {len(db.questions)}")
    print(f"📝 Доступные предметы: {', '.join(db.get_all_subjects())}")
    print("=" * 50)
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler для управления диалогом
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("test", start_test),
            CommandHandler("help", help_command),
            CommandHandler("progress", show_progress),
            CallbackQueryHandler(start_test, pattern="^start_test$")
        ],
        states={
            CHOOSING_SUBJECT: [
                CallbackQueryHandler(handle_subject_choice, pattern="^subject_"),
                CallbackQueryHandler(handle_callback),
                CallbackQueryHandler(show_correct_answer, pattern="^show_answer_"),  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
                CommandHandler("cancel", cancel),
                CommandHandler("help", help_command),
                CommandHandler("progress", show_progress)
            ],
            ANSWERING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer),
                CallbackQueryHandler(handle_callback),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start)
        ]
    )
    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("✅ Бот запущен! Нажми Ctrl+C для остановки.")
    print("💡 Перейдите в Telegram и найдите своего бота")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
