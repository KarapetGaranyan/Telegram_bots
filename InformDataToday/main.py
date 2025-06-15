import telebot
import datetime
import time
import threading
import random
import requests
import json
import os
import uuid

# Настройки бота
bot = telebot.TeleBot("8142649834:AAENOiHRChIQNdPRomnkF_iecHiVIjk0jmA")
OWM_API_KEY = 'e3b72acefafea8565fbf86b756297d0f'

# Файлы для хранения данных
TASKS_FILE = "user_tasks.json"
REMINDERS_FILE = "user_reminders.json"
RECURRING_FILE = "user_recurring.json"

# Глобальные переменные
reminder_threads = {}


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def load_json_file(filename):
    """Загружает данные из JSON файла"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_json_file(filename, data):
    """Сохраняет данные в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения {filename}: {e}")


def parse_datetime_string(date_str, time_str):
    """Парсит строки даты и времени в datetime объект"""
    try:
        now = datetime.datetime.now()

        # Обработка особых слов
        if date_str.lower() == "сегодня":
            target_date = now.date()
        elif date_str.lower() == "завтра":
            target_date = (now + datetime.timedelta(days=1)).date()
        else:
            # Форматы дат для парсинга
            date_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]
            target_date = None

            for fmt in date_formats:
                try:
                    parsed = datetime.datetime.strptime(date_str, fmt)
                    target_date = parsed.date()
                    break
                except ValueError:
                    continue

            if not target_date:
                return None

        # Парсинг времени
        try:
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            return None

        # Объединение даты и времени
        result = datetime.datetime.combine(target_date, time_obj)
        return result

    except Exception as e:
        print(f"Ошибка парсинга даты: {e}")
        return None


def safe_send_message(chat_id, text, parse_mode=None):
    """Безопасная отправка сообщений"""
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")
        return False


# === ФУНКЦИИ ДЛЯ ЗАДАЧ ===

def get_user_tasks(user_id):
    """Получает задачи пользователя"""
    all_tasks = load_json_file(TASKS_FILE)
    return all_tasks.get(str(user_id), [])


def save_user_tasks(user_id, tasks):
    """Сохраняет задачи пользователя"""
    all_tasks = load_json_file(TASKS_FILE)
    all_tasks[str(user_id)] = tasks
    save_json_file(TASKS_FILE, all_tasks)


# === ФУНКЦИИ ДЛЯ НАПОМИНАНИЙ ===

def get_user_reminders(user_id):
    """Получает напоминания пользователя"""
    all_reminders = load_json_file(REMINDERS_FILE)
    return all_reminders.get(str(user_id), [])


def save_user_reminders(user_id, reminders):
    """Сохраняет напоминания пользователя"""
    all_reminders = load_json_file(REMINDERS_FILE)
    all_reminders[str(user_id)] = reminders
    save_json_file(REMINDERS_FILE, all_reminders)


def get_user_recurring(user_id):
    """Получает регулярные напоминания пользователя"""
    all_recurring = load_json_file(RECURRING_FILE)
    return all_recurring.get(str(user_id), [])


def save_user_recurring(user_id, recurring):
    """Сохраняет регулярные напоминания пользователя"""
    all_recurring = load_json_file(RECURRING_FILE)
    all_recurring[str(user_id)] = recurring
    save_json_file(RECURRING_FILE, all_recurring)


# === СИСТЕМА НАПОМИНАНИЙ ===

def reminder_loop(user_id):
    """Основной цикл проверки напоминаний"""
    print(f"[INFO] Запущен поток напоминаний для пользователя {user_id}")
    sent_today = set()

    while True:
        try:
            now = datetime.datetime.now()
            current_datetime = now.strftime("%Y-%m-%d %H:%M")
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")
            current_weekday = now.strftime("%A").lower()

            # Проверка разовых напоминаний
            reminders = get_user_reminders(user_id)
            updated_reminders = []

            for reminder in reminders:
                if reminder.get('datetime') == current_datetime:
                    # Отправляем напоминание
                    message = f"⏰ *НАПОМИНАНИЕ*\n\n💬 {reminder['text']}"
                    if safe_send_message(user_id, message, 'Markdown'):
                        print(f"[INFO] Отправлено напоминание: {reminder['text']}")
                    # Не добавляем в updated_reminders - удаляем
                else:
                    updated_reminders.append(reminder)

            # Сохраняем обновленный список если что-то изменилось
            if len(updated_reminders) != len(reminders):
                save_user_reminders(user_id, updated_reminders)

            # Проверка регулярных напоминаний
            recurring = get_user_recurring(user_id)
            for reminder in recurring:
                if not reminder.get('active', True):
                    continue

                reminder_key = f"{reminder['id']}_{current_date}"
                if reminder_key in sent_today:
                    continue

                should_send = False

                if reminder['type'] == 'daily':
                    if current_time == reminder['time']:
                        should_send = True
                elif reminder['type'] == 'weekly':
                    if (current_weekday == reminder['day_of_week'] and
                            current_time == reminder['time']):
                        should_send = True

                if should_send:
                    message = f"🔄 *РЕГУЛЯРНОЕ НАПОМИНАНИЕ*\n\n💬 {reminder['text']}"
                    if safe_send_message(user_id, message, 'Markdown'):
                        sent_today.add(reminder_key)
                        print(f"[INFO] Отправлено регулярное напоминание: {reminder['text']}")

            # Очистка отправленных напоминаний в полночь
            if current_time == "00:00":
                sent_today.clear()

        except Exception as e:
            print(f"[ERROR] Ошибка в цикле напоминаний: {e}")

        # Пауза 30 секунд
        time.sleep(30)


def start_reminder_thread(user_id):
    """Запускает поток напоминаний для пользователя"""
    global reminder_threads

    # Проверяем, не запущен ли уже поток
    if user_id in reminder_threads:
        if reminder_threads[user_id].is_alive():
            return False

    # Создаем и запускаем новый поток
    thread = threading.Thread(target=reminder_loop, args=(user_id,), daemon=True)
    thread.start()
    reminder_threads[user_id] = thread
    return True


# === ОБРАБОТЧИКИ КОМАНД ===

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    start_reminder_thread(user_id)

    welcome_text = """👋 Добро пожаловать!

Я ваш персональный помощник для:
• Управления задачами
• Создания напоминаний  
• Получения фактов о здоровье
• Просмотра погоды

Введите /help для списка команд."""

    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """🤖 *Доступные команды:*

📝 *Задачи:*
/add\\_task [текст] - Добавить задачу
/tasks - Показать все задачи
/done [номер] - Отметить выполненной
/del\\_task [номер] - Удалить задачу

⏰ *Напоминания:*
/remind [дата] [время] [текст] - Создать напоминание
/reminders - Показать напоминания
/test - Тестовое напоминание

🔄 *Регулярные:*
/daily [время] [текст] - Ежедневное напоминание
/weekly [день] [время] [текст] - Еженедельное
/recurring - Показать регулярные

🌤️ *Другое:*
/fact - Факт о здоровье
/weather - Погода

*Примеры:*
`/remind сегодня 15:30 Встреча с врачом`
`/daily 08:00 Утренняя зарядка`
`/weekly monday 09:00 Планерка`"""

    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


# === КОМАНДЫ ЗАДАЧ ===

@bot.message_handler(commands=['add_task'])
def handle_add_task(message):
    try:
        task_text = message.text.split('/add_task', 1)[1].strip()
        if not task_text:
            bot.reply_to(message, "❌ Укажите текст задачи\nПример: /add_task Купить продукты")
            return

        user_id = message.from_user.id
        tasks = get_user_tasks(user_id)

        new_task = {
            'id': len(tasks) + 1,
            'text': task_text,
            'done': False,
            'created': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        tasks.append(new_task)
        save_user_tasks(user_id, tasks)

        bot.reply_to(message, f"✅ Задача добавлена: {task_text}")

    except IndexError:
        bot.reply_to(message, "❌ Укажите текст задачи")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при добавлении задачи")


@bot.message_handler(commands=['tasks'])
def handle_tasks(message):
    user_id = message.from_user.id
    tasks = get_user_tasks(user_id)

    if not tasks:
        bot.reply_to(message, "📝 У вас нет задач")
        return

    text = "📋 *Ваши задачи:*\n\n"
    for task in tasks:
        status = "✅" if task['done'] else "⏳"
        text += f"{task['id']}. {status} {task['text']}\n"

    bot.reply_to(message, text, parse_mode='Markdown')


@bot.message_handler(commands=['done'])
def handle_done_task(message):
    try:
        task_id = int(message.text.split()[1])
        user_id = message.from_user.id
        tasks = get_user_tasks(user_id)

        for task in tasks:
            if task['id'] == task_id:
                task['done'] = True
                save_user_tasks(user_id, tasks)
                bot.reply_to(message, f"✅ Задача выполнена: {task['text']}")
                return

        bot.reply_to(message, "❌ Задача не найдена")

    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Укажите номер задачи\nПример: /done 1")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка")


@bot.message_handler(commands=['del_task'])
def handle_delete_task(message):
    try:
        task_id = int(message.text.split()[1])
        user_id = message.from_user.id
        tasks = get_user_tasks(user_id)

        for i, task in enumerate(tasks):
            if task['id'] == task_id:
                deleted_task = tasks.pop(i)
                # Перенумеровываем оставшиеся задачи
                for j, remaining_task in enumerate(tasks):
                    remaining_task['id'] = j + 1
                save_user_tasks(user_id, tasks)
                bot.reply_to(message, f"🗑️ Задача удалена: {deleted_task['text']}")
                return

        bot.reply_to(message, "❌ Задача не найдена")

    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Укажите номер задачи\nПример: /del_task 1")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка")


# === КОМАНДЫ НАПОМИНАНИЙ ===

@bot.message_handler(commands=['remind'])
def handle_remind(message):
    try:
        parts = message.text.split(' ', 3)
        if len(parts) < 4:
            bot.reply_to(message, """❌ Неверный формат

*Примеры:*
`/remind сегодня 15:30 Встреча`
`/remind завтра 09:00 Врач`
`/remind 2025-12-31 23:59 Новый год`""", parse_mode='Markdown')
            return

        date_str = parts[1]
        time_str = parts[2]
        text = parts[3]

        # Парсим дату и время
        reminder_datetime = parse_datetime_string(date_str, time_str)
        if not reminder_datetime:
            bot.reply_to(message, "❌ Неверный формат даты или времени")
            return

        # Проверяем, что время в будущем
        if reminder_datetime <= datetime.datetime.now():
            bot.reply_to(message, "❌ Время должно быть в будущем")
            return

        user_id = message.from_user.id
        start_reminder_thread(user_id)

        # Создаем напоминание
        reminder = {
            'id': str(uuid.uuid4())[:8],
            'datetime': reminder_datetime.strftime("%Y-%m-%d %H:%M"),
            'text': text,
            'created': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        reminders = get_user_reminders(user_id)
        reminders.append(reminder)
        save_user_reminders(user_id, reminders)

        formatted_time = reminder_datetime.strftime("%d.%m.%Y в %H:%M")
        bot.reply_to(message, f"✅ Напоминание создано!\n📅 {formatted_time}\n💬 {text}")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['test'])
def handle_test_reminder(message):
    try:
        user_id = message.from_user.id
        start_reminder_thread(user_id)

        # Создаем тестовое напоминание через 1 минуту
        test_time = datetime.datetime.now() + datetime.timedelta(minutes=1)

        reminder = {
            'id': str(uuid.uuid4())[:8],
            'datetime': test_time.strftime("%Y-%m-%d %H:%M"),
            'text': "🧪 Тестовое напоминание работает!",
            'created': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        reminders = get_user_reminders(user_id)
        reminders.append(reminder)
        save_user_reminders(user_id, reminders)

        bot.reply_to(message, f"🧪 Тестовое напоминание создано!\n⏰ Сработает через 1 минуту")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['reminders'])
def handle_reminders(message):
    user_id = message.from_user.id
    reminders = get_user_reminders(user_id)

    if not reminders:
        bot.reply_to(message, "⏰ У вас нет напоминаний")
        return

    text = "⏰ *Ваши напоминания:*\n\n"
    now = datetime.datetime.now()

    # Сортируем по времени
    sorted_reminders = sorted(reminders, key=lambda x: x['datetime'])

    for reminder in sorted_reminders:
        reminder_time = datetime.datetime.strptime(reminder['datetime'], "%Y-%m-%d %H:%M")
        formatted_time = reminder_time.strftime("%d.%m в %H:%M")

        if reminder_time > now:
            status = "🟢"
        else:
            status = "🔴"

        text += f"{status} {formatted_time}\n💬 {reminder['text']}\n\n"

    bot.reply_to(message, text, parse_mode='Markdown')


# === КОМАНДЫ РЕГУЛЯРНЫХ НАПОМИНАНИЙ ===

@bot.message_handler(commands=['daily'])
def handle_daily(message):
    try:
        parts = message.text.split(' ', 2)
        if len(parts) < 3:
            bot.reply_to(message, "❌ Формат: /daily 08:00 Текст напоминания")
            return

        time_str = parts[1]
        text = parts[2]

        # Проверяем формат времени
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
        except ValueError:
            bot.reply_to(message, "❌ Неверный формат времени (ЧЧ:ММ)")
            return

        user_id = message.from_user.id
        start_reminder_thread(user_id)

        # Создаем регулярное напоминание
        recurring = {
            'id': str(uuid.uuid4())[:8],
            'type': 'daily',
            'time': time_str,
            'text': text,
            'active': True,
            'created': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        recurring_list = get_user_recurring(user_id)
        recurring_list.append(recurring)
        save_user_recurring(user_id, recurring_list)

        bot.reply_to(message, f"✅ Ежедневное напоминание создано!\n⏰ Каждый день в {time_str}\n💬 {text}")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['weekly'])
def handle_weekly(message):
    try:
        parts = message.text.split(' ', 3)
        if len(parts) < 4:
            bot.reply_to(message, "❌ Формат: /weekly monday 09:00 Текст")
            return

        day_str = parts[1].lower()
        time_str = parts[2]
        text = parts[3]

        # Проверяем день недели
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if day_str not in valid_days:
            bot.reply_to(message, f"❌ Неверный день недели\nДоступные: {', '.join(valid_days)}")
            return

        # Проверяем формат времени
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
        except ValueError:
            bot.reply_to(message, "❌ Неверный формат времени (ЧЧ:ММ)")
            return

        user_id = message.from_user.id
        start_reminder_thread(user_id)

        # Создаем еженедельное напоминание
        recurring = {
            'id': str(uuid.uuid4())[:8],
            'type': 'weekly',
            'day_of_week': day_str,
            'time': time_str,
            'text': text,
            'active': True,
            'created': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        recurring_list = get_user_recurring(user_id)
        recurring_list.append(recurring)
        save_user_recurring(user_id, recurring_list)

        days_ru = {
            'monday': 'понедельник', 'tuesday': 'вторник', 'wednesday': 'среда',
            'thursday': 'четверг', 'friday': 'пятница', 'saturday': 'суббота', 'sunday': 'воскресенье'
        }

        bot.reply_to(message,
                     f"✅ Еженедельное напоминание создано!\n📅 Каждый {days_ru[day_str]} в {time_str}\n💬 {text}")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['recurring'])
def handle_recurring(message):
    user_id = message.from_user.id
    recurring_list = get_user_recurring(user_id)

    if not recurring_list:
        bot.reply_to(message, "🔄 У вас нет регулярных напоминаний")
        return

    text = "🔄 *Регулярные напоминания:*\n\n"

    days_ru = {
        'monday': 'понедельник', 'tuesday': 'вторник', 'wednesday': 'среда',
        'thursday': 'четверг', 'friday': 'пятница', 'saturday': 'суббота', 'sunday': 'воскресенье'
    }

    for recurring in recurring_list:
        status = "🟢" if recurring.get('active', True) else "🔴"

        if recurring['type'] == 'daily':
            schedule = f"каждый день в {recurring['time']}"
        elif recurring['type'] == 'weekly':
            day_ru = days_ru.get(recurring['day_of_week'], recurring['day_of_week'])
            schedule = f"каждый {day_ru} в {recurring['time']}"

        text += f"{status} {schedule}\n💬 {recurring['text']}\n\n"

    bot.reply_to(message, text, parse_mode='Markdown')


# === ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ===

@bot.message_handler(commands=['fact'])
def handle_fact(message):
    facts = [
        "💧 Взрослому человеку нужно выпивать 1.5-2 литра воды в день",
        "🏃 30 минут физической активности в день снижают риск болезней сердца на 35%",
        "😴 Качественный сон 7-9 часов улучшает память и концентрацию",
        "🥗 5 порций овощей и фруктов в день - оптимальная норма для здоровья",
        "🧘 10 минут медитации в день снижают уровень стресса на 23%",
        "🚶 10 000 шагов в день помогают поддерживать нормальный вес",
        "🌞 15 минут на солнце обеспечивают дневную норму витамина D"
    ]

    fact = random.choice(facts)
    bot.reply_to(message, f"💡 {fact}")


@bot.message_handler(commands=['weather'])
def handle_weather(message):
    bot.reply_to(message, "🌤️ Отправьте название города для получения прогноза погоды")


def get_weather_info(city):
    """Получает информацию о погоде"""
    try:
        url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_API_KEY}&units=metric&lang=ru'
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            return "❌ Город не найден"

        data = response.json()
        temp = data['main']['temp']
        desc = data['weather'][0]['description']
        humidity = data['main']['humidity']
        wind = data['wind']['speed']

        return f"🌤️ *Погода в {city}:*\n🌡️ {temp}°C, {desc}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} м/с"

    except Exception as e:
        return "❌ Ошибка получения прогноза погоды"


# === ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ===

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text.strip()

    # Игнорируем команды
    if text.startswith('/'):
        bot.reply_to(message, "❓ Неизвестная команда. Используйте /help для списка команд")
        return

    # Если сообщение короткое, игнорируем
    if len(text) < 2:
        return

    # Обрабатываем как запрос погоды
    weather_info = get_weather_info(text)
    bot.reply_to(message, weather_info, parse_mode='Markdown')


# === ЗАПУСК БОТА ===

def main():
    print("🤖 Бот запускается...")

    while True:
        try:
            print("✅ Бот успешно запущен!")
            bot.polling(non_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            print("🔄 Переподключение через 5 секунд...")
            time.sleep(5)


if __name__ == "__main__":
    main()