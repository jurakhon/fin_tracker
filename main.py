
import telebot
import psycopg2
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from secret import API_TOKEN, DATABASE_PASSWORD


def open_connection():
    conn = psycopg2.connect(
        database="financemanager",
        host="localhost",
        user="postgres",
        password=DATABASE_PASSWORD,
        port=5432
    )
    return conn


def close_connection(conn, cur):
    cur.close()
    conn.close()


def create_database():
    conn = open_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        create table if not exists Users(
            user_id bigint primary key,
            username varchar(200),
            created_at timestamp
        );

        create table if not exists Income(
            id serial primary key,
            user_id bigint references Users(user_id),
            amount bigint,
            category varchar(150),
            description text,
            created_at timestamp
        );

        create table if not exists Expense(
            id serial primary key,
            user_id bigint references Users(user_id),
            amount bigint,
            category varchar(150),
            description text,
            created_at timestamp
        );
        """
    )
    conn.commit()
    close_connection(conn, cur)


create_database()

bot = telebot.TeleBot(API_TOKEN, parse_mode=None)



def register_user(user_id, username):
    conn = open_connection()
    cur = conn.cursor()
    cur.execute(
        f"insert into Users (user_id, username, created_at) values ({user_id}, '{username}', '{datetime.now()}') on conflict (user_id) do nothing")
    conn.commit()
    close_connection(conn, cur)


def get_category_keyboard(transaction_type):
    categories = ["Salary", "Investments", "Gifts"] if transaction_type == "income" else ["Food", "Transport",
                                                                                          "Entertainment", "Bills",
                                                                                          "Other"]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*[KeyboardButton(category) for category in categories])
    return keyboard



@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    register_user(user_id, username)
    bot.reply_to(message, f"Welcome, {username}! You've been registered. Use /help to see available commands.")


@bot.message_handler(commands=['help'])
def help(message):
    help_text = """
    Available commands:
    /add_income - Add a new income
    /add_expense - Add a new expense
    /delete_income - Delete an income
    /delete_expense - Delete an expense
    /summary_income - View total income
    /summary_expense - View total expenses
    /summary - View overall financial summary
    """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['add_income', 'add_expense'])
def add_transaction(message):
    transaction_type = 'income' if message.text == '/add_income' else 'expense'
    bot.reply_to(message, f"Enter the {transaction_type} amount:")
    bot.register_next_step_handler(message, process_amount, transaction_type)


def process_amount(message, transaction_type):
    try:
        amount = float(message.text)
        bot.reply_to(message, f"Select a category for this {transaction_type}:",
                     reply_markup=get_category_keyboard(transaction_type))
        bot.register_next_step_handler(message, process_category, transaction_type, amount)
    except ValueError:
        bot.reply_to(message, "Invalid amount. Please enter a number.")
        bot.register_next_step_handler(message, process_amount, transaction_type)


def process_category(message, transaction_type, amount):
    category = message.text
    bot.reply_to(message, "Enter a description (optional):")
    bot.register_next_step_handler(message, save_transaction, transaction_type, amount, category)


def save_transaction(message, transaction_type, amount, category):
    description = message.text
    user_id = message.from_user.id
    conn = open_connection()
    cur = conn.cursor()

    table = "Income" if transaction_type == "income" else "Expense"
    cur.execute(
        f"insert into {table} (user_id, amount, category, description, created_at) values ({user_id}, {amount}, '{category}', '{description}', '{datetime.now()}')")

    conn.commit()
    close_connection(conn, cur)
    bot.reply_to(message, f"{transaction_type.capitalize()} added successfully!")


@bot.message_handler(commands=['summary_income', 'summary_expense'])
def summary(message):
    transaction_type = 'Income' if message.text == '/summary_income' else 'Expense'
    user_id = message.from_user.id
    conn = open_connection()
    cur = conn.cursor()

    cur.execute(f"select sum(amount) from {transaction_type} where user_id = {user_id}")
    total = cur.fetchone()[0] or 0

    close_connection(conn, cur)
    bot.reply_to(message, f"Total {transaction_type.lower()}: {total}")


@bot.message_handler(commands=['summary'])
def overall_summary(message):
    user_id = message.from_user.id
    conn = open_connection()
    cur = conn.cursor()

    cur.execute(f"select sum(amount) from Income where user_id = {user_id}")
    total_income = cur.fetchone()[0] or 0

    cur.execute(f"select sum(amount) from Expense where user_id = {user_id}")
    total_expense = cur.fetchone()[0] or 0

    balance = total_income - total_expense

    close_connection(conn, cur)
    summary_text = f"Total Income: {total_income}\nTotal Expenses: {total_expense}\nBalance: {balance}"
    bot.reply_to(message, summary_text)



bot.infinity_polling()