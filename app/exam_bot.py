import threading
import time
import keyboards_exam
from datetime import datetime

from datetime import datetime


import cfg
from pyexpat.errors import messages
from telebot import TeleBot
from telebot import types

from auth import auth, users  # Импортируем auth и users

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

# Обработка кнопки "Показать просрочки"
def show_overdue(message):
    bot.send_message(message.chat.id, 'Выбор экзамена', reply_markup=keyboards_exam.kb_select_exam(), parse_mode='HTML')

# Обработка кнопки "Кому необходимо сдать"
def show_submit_list(message):
    bot.send_message(message.chat.id, "Вот список тех, кому необходимо сдать...")



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

def check_user_exam(id_1, id_2):
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
        WHEN CURDATE() > DATE_ADD(Exam_date.last_date, INTERVAL 1 YEAR) THEN 'Просрочено'
        WHEN CURDATE() BETWEEN DATE_ADD(DATE(last_date), INTERVAL 1 YEAR) - INTERVAL 14 DAY AND DATE_ADD(DATE(last_date), INTERVAL 1 YEAR) THEN 'Осталось менее двух недель'
        WHEN DATE(last_date) < CURDATE() - INTERVAL 11 MONTH THEN 'Остался месяц или меньше'
        ELSE 'Успешно'
    END AS exam_status,
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
    AND (org_structure.org_structure_id = {id_1} OR org_structure.org_structure_id = {id_2})
    AND Exam_date.notify_check = 1
    
    AND (
        Exam_date.success_quest_percent < 70
        OR CURDATE() > DATE_ADD(Exam_date.last_date, INTERVAL 1 YEAR)
        OR DATE(last_date) < CURDATE() - INTERVAL 11 MONTH
    )
ORDER BY 
    Exam_date.last_date DESC;
'''

    try:
        users_exam = cfg.execute_query(url+query, 18)
        print("Результат выполнения запроса:")
        #print(users_exam)
        if not users_exam:
            print("Данные отсутствуют.")
        return users_exam
    except Exception as e:
        print("Ошибка при выполнении запроса:", e)
        return ''

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


def get_fails_message(id_1, id_2):
    exam_fails = check_user_exam(id_1, id_2)
    if exam_fails:  # Проверяем, что результат не пустой
        # Заголовок сообщения
        header = "📋 Список пользователей на сдачу экзаменов:\n\n"

        # Инициализируем таблицы
        overdue_table = "<b>❗ Не прошедшие аттестацию:</b>\n<pre>"
        overdue_table += f"{'ФИО':<15} | {'Дата':<10} | {'Экзамен':<20}\n"
        overdue_table += f"{'-' * 15} | {'-' * 10} | {'-' * 20}\n"

        soon_expire_table = "<b>⚠️ Подлежащие аттестации в этом месяце:</b>\n<pre>"
        soon_expire_table += f"{'ФИО':<15} | {'Дата':<10} | {'Экзамен':<20}\n"
        soon_expire_table += f"{'-' * 15} | {'-' * 10} | {'-' * 20}\n"

        for fail in exam_fails:
            # Формат ФИО: "Фамилия И.О."
            fio = f"{fail[8]} {fail[7][0]}.{fail[9][0]}."
            if len(fio) > 20:  # Урезаем ФИО, если слишком длинное
                fio = fio[:17] + "..."

            success_percent = float(fail[12])

            if success_percent >= 70:
                date = format_date(fail[13], False)  # Форматируем дату
            else:
                date = format_date(fail[13], True)  # Форматируем дату и прибавляем 1 год

            exam_name = fail[10]  # Извлекаем название экзамена из fail[10]

            # Добавляем в нужную таблицу в зависимости от статуса
            if fail[16] == 'Просрочено':
                overdue_table += f"{fio:<15} | {date:<10} | {exam_name:<20}\n"
            elif fail[16] == 'Остался месяц или меньше':
                soon_expire_table += f"{fio:<15} | {date:<10} | {exam_name:<20}\n"
            elif fail[16] == 'Осталось менее двух недель':
                soon_expire_table += f"{fio:<15} | {date:<10} | {exam_name:<20}\n"

        overdue_table += "</pre>\n\n" if "ФИО" not in overdue_table else "</pre>"
        soon_expire_table += "</pre>" if "ФИО" not in soon_expire_table else "</pre>"

        # Объединяем сообщение
        return header + overdue_table + soon_expire_table
    else:
        return None



# ОПОВЕЩЕНИЕ ПОЛЬЗОВАТЕЛЯ О СДАЧИ ЭКЗАМЕНА
def notify_auto_check():
    sent_messages = {}
    while True:
        user_list = cfg.notify_exam()
        print(user_list)
        for user in user_list:
            try:
                user_id = user[0]
                chat_id = user[5]
                exam_name = user[4]
                type_quest_id = user[6]
                bot.send_message(chat_id, text=f'''Напоминание: До просрочки по экзамену "{exam_name}" остался 1 месяц!''', parse_mode="HTML") # Сообщение без вывода кнопки "Я сдал" -> Она ниже...
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
                if type_quest_id in [8,9]:  # Только для экзаменов ОРОП
                    if chat_id in sent_messages:  # Если сообщение уже отправлялось, удаляем старое
                        bot.delete_message(chat_id, sent_messages[chat_id])
                    bot.send_message(chat_id, text=f'''Напоминание: Вам необходимо сдать экзамен "{exam_name}"! До просрочки осталось менее двух недель!''', reply_markup = keyboards_exam.exam_done_bt(user_id, type_quest_id)) # Сообщение с выводом кнопки "Я сдал"
                    sent_messages[chat_id] = bot.message.message_id  # Сохраняем ID нового сообщения
                    print(f'Отправил сообщение пользователю {user[1]} {user[2]} об экзамене {exam_name}')
                else:
                    if chat_id in sent_messages:  # Если сообщение уже отправлялось, удаляем старое
                        bot.delete_message(chat_id, sent_messages[chat_id])
                    bot.send_message(chat_id, text=f'''Напоминание: Вам необходимо сдать экзамен "{exam_name}"! До просрочки осталось менее двух недель!''', reply_markup = keyboards_exam.exam_answer_OK(user_id, type_quest_id))
                    sent_messages[chat_id] = bot.message.message_id  # Сохраняем ID нового сообщения
                print(f'Отправил сообщение пользователю {user[1]} {user[2]} об экзамене {exam_name}')                                                               
            except Exception as e:
                print(  
                    f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                    f"ERROR: Пользователь {user[1]} {user[2]} не оповещён. Ошибка: {e}")
                continue

# ОПОВЕЩЕНИЕ МАСТЕРОВ ЭЛЕКТРОСЛУЖБЫ
        admin_list = cfg.get_auto_master() + cfg.get_elec_master()
        for admin in admin_list:
            try:
                msg = get_fails_message(admin[3], admin[3]) # Отправляем org_structure_id мастера автоматики и электриков
                if msg: # Проверка на отсутствие данных
                    bot.send_message(admin[2], text=msg, parse_mode="HTML")
                    print(f"Уведомомил в TG админа {admin[0]} {admin[1]}")
                elif msg == None: 
                    print('✅ Все экзамены сданы вовремя!')
            except Exception as e:
                    print(
                        f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                        f"ERROR: Администратор {admin[0]} {admin[1]} не оповещён. Ошибка: {e}")
                    continue

# ОПОВЕЩЕНИЕ НАЧАЛЬНИКА УЧАСТКА ЭЛЕКТРОСЛУЖБЫ
        boss = cfg.get_electro_boss()  # ID начальника
        id_1 = admin_list[0][3]  # id первого мастера
        id_2 = admin_list[1][3]  # id второго мастера
        msg = get_fails_message(id_1, id_2) # Отправляем org_structure_id мастеров
        try:
            if msg: # Проверка на отсутствие данных
                bot.send_message(boss[0][2], text=msg, parse_mode="HTML")
                print(f"Уведомомил в TG админа {boss[0][0]} {boss[0][1]}")
            elif msg == None: 
                print('✅ Все экзамены сданы вовремя!')
        except Exception as e:
                print(
                    f"{datetime.now().date()} | {datetime.now().strftime('%H:%M:%S')} "
                    f"ERROR: Администратор {admin[0]} {admin[1]} не оповещён. Ошибка: {e}")
                continue

        time.sleep(60)

# ОБРАБОТЧИК НАЖАТИЙ КНОПОК
@bot.callback_query_handler(func=lambda call: True)
# ОБРАБОТКА ВСЕХ КНОПОК ЭКЗАМЕНОВ "ОРОП"
def exam_done_bt(call):
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