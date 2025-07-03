import threading
import time
from datetime import datetime
from collections import defaultdict
from pyexpat.errors import messages
from telebot import TeleBot
from telebot import types
# Импорт файлов проекта
import keyboards_exam
import cfg
from auth import auth, users  # Импортируем auth и users
from tabulate import tabulate
import logging


# Инициализация бота с токеном из cfg
bot = TeleBot(cfg.BOT_TOKEN_EXAM, parse_mode='HTML')
url = cfg.URL


# Обработчик всех текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.chat.id)

    # Проверяем авторизацию пользователя
    if user_id not in users or users[user_id]['status'] == 'offline':
        ask_for_tabel_number(message)
        return

    # Определяем роль пользователя
    user_role = users[user_id].get('role', 'user')

    # Генерация клавиатуры в зависимости от роли
    if user_role == 'admin':
        reply_markup = keyboards_exam.kb_admin_mainmenu()  # Клавиатура для админов
    else:
        reply_markup = keyboards_exam.kb_user_mainmenu()  # Клавиатура для пользователей

     # Ответ на сообщение
    if message.text == 'Не прошедшие аттестацию ❗':
        show_overdue(message)
    elif message.text == 'Подлежащие аттестации в этом месяце ⏳':
        show_submit_list(message)
    else:
        bot.send_message(message.chat.id, "Что Вас интересует:", reply_markup=reply_markup)

# Функция для запроса табельного номера
def ask_for_tabel_number(message):
    # Отправляем сообщение и ждем ввода табельного номера
    mesg = bot.send_message(message.chat.id, text="Введите табельный номер:")

    # Регистрируем шаг для ввода табельного номера
    bot.register_next_step_handler(mesg, handle_tabel_number)


# Обработчик ввода табельного номера
def handle_tabel_number(message):
    # Обрабатываем табельный номер и возвращаем результат из функции auth()
    result = auth(message)  # Вызов функции auth, которая возвращает сообщение для отправки

    # Если в result есть сообщение, то отправляем его обратно пользователю
    if 'info' in result:
        bot.send_message(message.chat.id, result['info'], reply_markup=keyboards_exam.kb_user_mainmenu(), parse_mode='HTML')

# Обработка кнопки "Показать просрочки"
def show_overdue(message):
    bot.send_message(message.chat.id, 'Выбор экзамена', reply_markup=keyboards_exam.kb_select_exam(), parse_mode='HTML')


# Обработка кнопки "Кому необходимо сдать"
def show_submit_list(message):
    bot.send_message(message.chat.id, "Вот список тех, кому необходимо сдать...")



# Получение пользователей с проблемой по экзаменам
def check_user_exam():
    query = f'''SELECT 
    peoples.id AS people_id,
    COALESCE(org_structure_groups.group_name, 'Не указано') AS group_name,
    COALESCE(org_structure_positions.position_name, 'Не указана') AS position_name,
    COALESCE(org_structure_positions.id, 0) AS position_id,
    COALESCE(elect_group, 0) AS elect_group,
    COALESCE(log_auth_var.chat_id, 0) AS chat_id,
    COALESCE(Exam_date.Protocol_num, 'Не указан') AS Protocol_num,
    COALESCE(peoples.first_name, 'Без имени') AS first_name,
    COALESCE(peoples.last_name, 'Без фамилии') AS last_name,
    COALESCE(peoples.second_name, '-') AS second_name,
    Exam_typeQuest.Type_quest_text AS Type_quest_text,
    COALESCE(Exam_date.type_quest_id, 0) AS type_quest_id,
    COALESCE(Exam_date.success_quest_percent, 0) AS success_quest_percent,
    COALESCE(Exam_date.last_date, '1900-01-01') AS last_date,
    Exam_date.time_exam,
    peoples.TabNumberSap,
    CASE
        WHEN Exam_date.success_quest_percent < 70 THEN 'Не сдал экзамен'
        WHEN CURDATE() > DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR) THEN 'Просрочено'
        WHEN CURDATE() BETWEEN 
            DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR) - INTERVAL 14 DAY
            AND DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR)
        THEN 'Осталось менее двух недель'
        WHEN CURDATE() BETWEEN 
            DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR) - INTERVAL 1 MONTH
            AND DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR)
        THEN 'Остался месяц или меньше'
        ELSE 'Успешно'
    END AS exam_status,
    COALESCE(org_structure.id, 0) AS structure_id,
    COALESCE(org_structure.org_structure_id, 0) AS org_structure_id
FROM 
    Exam_date
JOIN 
    peoples ON peoples.id = Exam_date.people_id
JOIN 
    Exam_typeQuest ON Exam_typeQuest.id = Exam_date.type_quest_id
LEFT JOIN 
    org_structure ON org_structure.id = peoples.str_org_structure
LEFT JOIN 
    org_structure_positions ON org_structure_positions.id = org_structure.str_pos_id
LEFT JOIN 
    org_structure_groups ON org_structure_groups.id = org_structure.str_group_id
LEFT JOIN 
    log_auth_var ON log_auth_var.id_people = peoples.id
WHERE 
    Exam_date.last_date = (
        SELECT MAX(Exam_date2.last_date)
        FROM Exam_date AS Exam_date2
        WHERE Exam_date2.people_id = peoples.id
        AND Exam_date2.type_quest_id = Exam_date.type_quest_id
    )
    AND peoples.status_id = 0
    AND Exam_date.notify_check = 1
    AND (
        Exam_date.success_quest_percent < 70
        OR CURDATE() > DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR)
        OR CURDATE() BETWEEN 
            DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR) - INTERVAL 1 MONTH
            AND DATE_ADD(Exam_date.last_date, INTERVAL Exam_typeQuest.years_for_exam YEAR)
    )
ORDER BY 
    org_structure.org_structure_id ASC;
'''
    try:
        users_exam = cfg.execute_query(url + query, 19)
        print("Результат выполнения запроса:")
        if not users_exam:
            print("Данные отсутствуют.")
        return users_exam if users_exam else []
    except Exception as e:
        print("Ошибка при выполнении запроса:", e)
        return []



# Получение пользователей с просроченными защитными средствами
def check_sredstva():
    query = f'''SELECT 
    boss.id AS boss_id,
    log_auth_var_boss.chat_id AS boss_chat_id,
    
    sredstva_date.id AS sredstva_date_id,
    sredstva_date.people_id,
    sredstva_date.expire_date,
    
    all_sredstva.sredstvo_name,
    
    peoples.first_name,
    peoples.second_name,
    peoples.last_name,
    peoples.str_org_structure,
    
    log_auth_var.chat_id AS user_chat_id
    
FROM sredstva_date
JOIN peoples ON sredstva_date.people_id = peoples.id
JOIN all_sredstva ON sredstva_date.sredstvo_id = all_sredstva.id
LEFT JOIN log_auth_var ON log_auth_var.id_people = peoples.id
LEFT JOIN org_structure ON org_structure.id = peoples.str_org_structure
LEFT JOIN peoples AS boss ON boss.str_org_structure = org_structure.org_structure_id
LEFT JOIN log_auth_var AS log_auth_var_boss ON log_auth_var_boss.id_people = boss.id
WHERE sredstva_date.expire_date <= NOW()
  AND log_auth_var_boss.chat_id IS NOT NULL
ORDER BY boss.id;
'''
    try:
        users_exam = cfg.execute_query(url + query, 19)
        print("Результат выполнения запроса:")
        if not users_exam:
            print("Данные отсутствуют.")
        return users_exam if users_exam else []
    except Exception as e:
        print("Ошибка при выполнении запроса:", e)
        return []
    


def format_date(date_str,fail):
    from datetime import datetime

    # Преобразование строки в объект datetime
    date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    date_obj_plus_one_year = date_obj
    if fail !=True:
        try:
            # Добавляем 1 год
            date_obj_plus_one_year = date_obj.replace(year=date_obj.year + 1)
        except ValueError:
            # Если дата 29 февраля (високосный год), переместить на 28 февраля
            date_obj_plus_one_year = date_obj.replace(year=date_obj.year + 1, day=28)

    # Форматирование новой даты (день.месяц.год)
    return date_obj_plus_one_year.strftime("%d.%m.%Y")  # Пример: "13.12.2025"


# ОПОВЕЩЕНИЕ ПОЛЬЗОВАТЕЛЯ О СДАЧИ ЭКЗАМЕНА
sent_messages = {}
def notify_auto_check():
    global sent_messages
    while True:
        user_list = check_user_exam()
        for user in user_list:
            try:
                user_id = user[0]
                chat_id = user[5]
                exam_name = user[4]
                type_quest_id = user[6]
                
                #bot.send_message(chat_id, text=f'''Напоминание: В этом месяце необходимо пройти аттестацию по "{exam_name}"!''', parse_mode="HTML")
                print(f'Отправил сообщение пользователю {user[1]} {user[2]} об экзамене {exam_name}')
            except Exception as e:
                print(
                    f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                    f"ERROR: Пользователь {user[1]} {user[2]} не оповещён. Ошибка: {e}")
                continue

        user_list2 = cfg.notify_exam_2weeks()
        for user in user_list2:
            try:
                user_id = user[0]
                chat_id = user[5]
                exam_name = user[4]
                type_quest_id = user[6]
                
                # Сообщение для отправки
                message_text = f'''Напоминание: Вам необходимо сдать экзамен "{exam_name}"! До просрочки осталось менее двух недель!'''

                # Если экзамен относится к ОРОП (id 8 или 9) или в СПЦ
                if type_quest_id in [8, 9]:
                    keyboard = keyboards_exam.exam_done_bt(user_id, type_quest_id)
                else:
                    keyboard = keyboards_exam.exam_answer_OK(user_id, type_quest_id)

                # Отправляем сообщение
                #message = bot.send_message(chat_id, text=message_text, reply_markup=keyboard)

                # Сохраняем в словарь с message_id, чтобы связать его с chat_id
                if message.message_id not in sent_messages:
                    sent_messages[message.message_id] = []  # Если такого message_id нет в словаре, создаём новый список
                sent_messages[message.message_id].append(chat_id)  # Добавляем chat_id в список для данного message_id

                print(f'Отправил сообщение пользователю {user[1]} {user[2]} об экзамене {exam_name}')                                                               
            except Exception as e:
                print(  
                    f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                    f"ERROR: Пользователь {user[1]} {user[2]} не оповещён. Ошибка: {e}")
                continue
        
        sredstva_list = check_sredstva()
        grouped = defaultdict(list)

        # Группируем по начальнику (boss_chat_id)
        for user in sredstva_list:
            boss_chat_id = user[1]
            grouped[boss_chat_id].append(user)

        # Для каждого начальника создаём таблицу и отправляем
        for boss_chat_id, users in grouped.items():
            message = "⚠️ *Уведомление о просроченных средствах*\n\n"
            message += "| Фамилия |   Имя   | Отчество |       Средство       |  Дата  |\n"
            message += "|---------|---------|----------|----------------------|--------|\n"

            for row in users:
                message += f"| {row[8]} | {row[6]} | {row[7]} | {row[5]} | {row[4]} |\n"

            # Заменим "|" на символы таблички, если хочешь красиво, но пока оставим Markdown

            try:
                print(message)
                #bot.send_message(boss_chat_id, message, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка отправки начальнику {boss_chat_id}: {e}")

            #send_notifications(check_user_exam(), cfg.get_hierarchy())
            send_notifications(check_sredstva(),...)

            time.sleep(60)


# Уровень логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

# ============================ ПАРСИНГ ДАННЫХ ============================

def parse_exam_rows(rows):
    logging.info(f"Парсинг строк экзаменов: получено {len(rows)} строк.")
    return [
        {
            'people_id': row[0],
            'group_name': row[1],
            'position_name': row[2],
            'position_id': row[3],
            'elect_group': row[4],
            'chat_id': row[5],
            'protocol_num': row[6],
            'first_name': row[7],
            'last_name': row[8],
            'second_name': row[9],
            'type_quest_text': row[10],
            'type_quest_id': row[11],
            'success_quest_percent': row[12],
            'last_date': row[13],
            'time_exam': row[14],
            'TabNumberSap': row[15],
            'exam_status': row[16],
            'structure_id': int(row[17]),
            'org_structure_id': int(row[18])
        }
        for row in rows
    ]

# ============================ ЧАТЫ НАЧАЛЬНИКОВ ============================

def get_structure_chat_ids_full():
    query = "SELECT str_org_structure, chat_id FROM log_auth_var INNER JOIN peoples ON peoples.id = log_auth_var.id_people WHERE peoples.status_id = 0 AND chat_id IS NOT NULL"
    raw_data = cfg.execute_query(url + query, 2)

    chat_map = {}
    for structure_id, chat_id in raw_data:
        try:
            structure_id = int(structure_id)
            chat_map[structure_id] = chat_id
        except:
            continue
    return chat_map

# ============================ ИЕРАРХИЯ ============================

def get_direct_boss(structure_id, hierarchy):
    for boss_id, subordinates in hierarchy.items():
        if structure_id in subordinates:
            return boss_id
        result = get_direct_boss(structure_id, subordinates)
        if result:
            return result
    return None

# ============================ ПОСТРОЕНИЕ УВЕДОМЛЕНИЙ ============================

def build_boss_map(parsed_rows, hierarchy):
    structure_to_rows = defaultdict(list)
    for row in parsed_rows:
        structure_to_rows[row['structure_id']].append(row)

    boss_map = defaultdict(list)

    for structure_id, data in structure_to_rows.items():
        boss_id = get_direct_boss(structure_id, hierarchy)
        logging.info(f"structure_id: {structure_id} → boss_id: {boss_id}")
        if boss_id is not None:
            boss_map[boss_id].extend(data)
        else:
            logging.warning(f"Не найден прямой начальник для структуры {structure_id}")

    logging.info(f"Будет отправлено {len(boss_map)} уведомлений прямым начальникам.")
    return boss_map

# ============================ ФОРМАТИРОВАНИЕ ТАБЛИЦЫ ============================

def format_table(rows):
    header = "*📋 Список сотрудников, которым нужно сдать экзамен:*\n\n"
    table = "| ФИО              | Экзамен         | Дата        | Статус        |\n"
    table += "|------------------|------------------|-------------|----------------|\n"

    def shorten(name, surname, patronymic):
        return f"{surname} {name[0]}. {patronymic[0]}."

    for row in rows:
        first, last, second = row['first_name'], row['last_name'], row['second_name']
        fio = shorten(first, last, second)
        exam = row['type_quest_text'][:15]
        date = row['last_date'].split(' ')[0]
        status = row['exam_status']

        if "менее двух недель" in status.lower():
            status_text = "⏳ < 2 недель"
        elif "не сдал" in status.lower():
            status_text = "❌ Не сдан"
        else:
            status_text = status

        table += f"| {fio:<16} | {exam:<16} | {date:<11} | {status_text:<14} |\n"

    return header + f"\n{table}\n"

# ============================ ОТПРАВКА УВЕДОМЛЕНИЙ ============================

def send_notifications(exam_rows, hierarchy):
    if not exam_rows or not isinstance(exam_rows, list):
        logging.warning("Нет данных для обработки экзаменов. Уведомления не будут отправлены.")
        return
    parsed = parse_exam_rows(exam_rows)
    logging.info(f"Парсинг строк экзаменов: получено {len(parsed)} строк.")
    print(cfg.get_hierarchy())  # Можно убрать после отладки

    chat_ids = get_structure_chat_ids_full()
    logging.info(f"Получено {len(chat_ids)} chat_id для структур.")

    boss_map = build_boss_map(parsed, hierarchy)

    for boss_id, rows in boss_map.items():
        message = format_table(rows)

        for row in rows:
            if int(row['chat_id']) == 0:
                message_no_chat_id = f"❗ Внимание! У вашего подчиненного {row['first_name']} {row['last_name']} нет chat_id в Telegram. Он не получит уведомление."
                if boss_id in chat_ids:
                    try:
                        logging.info(f"Отправка уведомления начальнику структуры {boss_id} — chat_id: {chat_ids[boss_id]}")
                        print(message_no_chat_id)
                        print("---")
                        # bot.send_message(chat_ids[boss_id], message_no_chat_id, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке уведомления начальнику структуры {boss_id}: {e}")
                else:
                    logging.warning(f"Нет chat_id у начальника структуры {boss_id} для уведомления об отсутствии chat_id у сотрудника.")

        if boss_id in chat_ids:
            try:
                logging.info(f"Отправка уведомления в структуру {boss_id} — chat_id: {chat_ids[boss_id]}")
                print(message)
                print("---")
                # bot.send_message(chat_ids[boss_id], message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Ошибка при отправке в структуру {boss_id}: {e}")
        else:
            logging.warning(f"Нет chat_id для структуры {boss_id}, пропускаем.")


# ОБРАБОТЧИК НАЖАТИЙ КНОПОК
@bot.callback_query_handler(func=lambda call: True)
# ОБРАБОТКА ВСЕХ КНОПОК ЭКЗАМЕНОВ "ОРОП"
def exam_done_bt(call):
    global sent_messages
    if call.data.startswith('exam_done'):   
        _, people_id, type_quest_id = call.data.split('|')
        people_id = str(people_id)
        type_quest_id = str(type_quest_id)
        try:
            if cfg.check_for_new_exam(people_id) != []: # Упрощённо: Если кнопка 'я сдал' нажимается впервые
                cfg.off_notify_exam(people_id, type_quest_id)  # Отключение уведомления
                cfg.new_notify_exam(people_id, type_quest_id)  # Создание новой записи (только для экзаменов ОРОП)
                empty_markup = types.InlineKeyboardMarkup()  # Пустая клавиатура
                bot.edit_message_text(f"{call.message.text}", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=empty_markup)
                bot.send_message(call.message.chat.id, text="Вы сдали экзамен!")

                # Удаляем сообщение из sent_messages
                if call.message.message_id in sent_messages:
                    # Найдем все chat_id, связанные с данным message_id
                    for chat_id in sent_messages[call.message.message_id]:
                        # Делаем дополнительные действия, если нужно (например, логирование)
                        print(f"Удаляем сообщение с ID {call.message.message_id} для пользователя с chat_id {chat_id}")
                    # Удаляем записи по message_id
                    del sent_messages[call.message.message_id]
                
                print('---------------\nВызывается словарь с коллбека кнопки\n---------------')
                print(sent_messages)
                print('---------------')
        except Exception as e:
            print(
                f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                f"ERROR: Обработка кнопки безуспешна. Проверьте доступ к БД Ошибка: {e}")
        

# ОБРАБОТКА ВСЕХ КНОПОК ЭКЗАМЕНОВ В СПЦ
def exam_OK_bt(call):
    if call.data.startswith('exam_OK'):     
        _, people_id, type_quest_id = call.data.split('|')
        people_id = str(people_id)
        type_quest_id = str(type_quest_id)
        try:
            cfg.off_notify_exam(people_id, type_quest_id)
            empty_markup = types.InlineKeyboardMarkup()  # Пустая клавиатура
            bot.edit_message_text(f"{call.message.text}", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=empty_markup)
            bot.send_message(call.message.chat.id, text="Уведомления по текущему экзамену отключены. Не забудьте его сдать, если ещё этого не сделали!")
        except Exception as e:
            print(
                f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                f"ERROR: Обработка кнопки безуспешна. Проверьте доступ к БД Ошибка: {e}")



# Запуск бота
def run_bot():
    print("БОТ ЭКЗАМЕН НАЧАЛ РАБОТУ.....")
    try:
        _thread_notify_check = threading.Thread(target=notify_auto_check)
        _thread_notify_check.start()
        bot.infinity_polling()  # Запуск бесконечного опроса без потоков
        _thread_notify_check.join()
    except KeyboardInterrupt:
        print("БОТ ЭКЗАМЕН ОСТАНОВЛЕН")

# Запуск бота при выполнении файла
if __name__ == '__main__':
    run_bot()