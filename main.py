from config import TOKEN,MONGODB,DATABASE,COLLECTION,COLLECTION2,admin_id
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command,CommandObject
from aiogram.fsm.state import State,StatesGroup
from pymongo.mongo_client import MongoClient
from pymongo import MongoClient,DESCENDING
from aiogram.fsm.context import FSMContext
from aiogram import Bot,types,Dispatcher
import string
import logging
import asyncio
import random
import time
import sys

bot = Bot(token=TOKEN,parse_mode="HTML")
dp = Dispatcher()
client = MongoClient(MONGODB)
database = client[DATABASE]
collection = database[COLLECTION]
collection2 = database[COLLECTION2]
MAX_ACTIVATIONS = 5
COINS = 1000

class rasilka(StatesGroup):
    message = State()

@dp.message(Command("send_all"))
async def send_all(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if str(user_id) == str(admin_id):
        await message.answer('Write a message for mailing')
        await state.set_state(rasilka.message)

@dp.message(rasilka.message)
async def handle_message_for_broadcast(message: types.Message, state: FSMContext):
    state_message = message.text
    user_id = message.from_user.id
    if user_id == admin_id:
        ids = [user['id'] for user in collection.find({}, {'id': 1, '_id': 0})]
        for user_id in ids:
            await bot.send_message(user_id, state_message)
        await state.clear()

@dp.message(Command("start"))
async def start(message: types.Message):
    await bot.send_message(message.from_user.id,"Hey, i'm casino bot in telegram use Games for check avalible games, send /help to see commands")
    user_id = message.from_user.id
    user_name = message.from_user.username
    user = {
        "id" : user_id,
        "Name" : user_name,
        "Balance" : 1000
    }
    if collection.find_one({"id": user_id}) is None:
        collection.insert_one(user)

@dp.message(Command('gpromo'))
async def generate_code(message: types.Message):
    user_id = message.from_user.id
    if user_id == admin_id:
        code = generate_random_code()
        try:
            collection2.insert_one({'code': code, 'max_activations': MAX_ACTIVATIONS, 'activations': 0, 'users': [], 'coins': COINS})
        except Exception as e:
            print(f"Error while inserting into DB: {e}")
            return
        await message.answer(f"New promo code generated: {code}")
    else:
        await bot.send_message(user_id,"You cant use this")

def generate_random_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

@dp.message(Command('promo'))
async def use_code(message: types.Message):
    if len(message.text.split()) < 2:
        await message.answer("You did not specify a promotional code.")
        return
    code_to_check = message.text.split()[1]
    try:
        code_info = collection2.find_one({'code': code_to_check})
    except Exception as e:
        print(f"Error while fetching from DB: {e}")
        return
    if not code_info:
        await message.answer("Promo code is invalid.")
        return
    max_activations = code_info.get('max_activations', 1)
    activations = code_info.get('activations', 0)
    if activations >= max_activations:
        await message.answer("The promotional code has already been used the maximum number of times.")
        return
    user_id = message.from_user.id
    if user_id in code_info.get('users', []):
        await message.answer("You have already used this promo code.")
        return
    try:
        collection2.update_one(
            {'code': code_to_check},
            {'$inc': {'activations': 1}, '$push': {'users': user_id}}
        )
    except Exception as e:
        print(f"Error while updating DB: {e}")
        return
    
    coins = code_info.get('coins', 0)
    add_coins(user_id, coins)
    
    await message.answer(f"Promo code successfully activated! You received {coins} coins!")

def add_coins(user_id: int, coins: int):
    user = collection.find_one({'id': user_id})
    if user:
        try:
            collection.update_one(
                {'id': user_id},
                {'$inc': {'Balance': coins}}
            )
        except Exception as e:
            print(f"Error while updating DB: {e}")
            return
    else:
        try:
            collection.insert_one(
                {'id': user_id, 'Name': 'New User', 'Balance': coins}
            )
        except Exception as e:
            print(f"Error while inserting into DB: {e}")
            return

@dp.message(Command("help"))
async def help(message: types.Message):
    await bot.send_message(message.from_user.id,"/roll {bet}\n/leaderboards\n/balance\n")

@dp.message(Command("leaderboards"))
async def leaderboards(message: types.Message):
    top_users = collection.find().sort("Balance", DESCENDING).limit(10)
    leaderboard = "Top 10 users:\n\n"

    for i, user in enumerate(top_users, start=1):
        username = user["Name"]
        balance = user["Balance"]
        leaderboard += f"{i}. {username}: {balance}\n"

    await bot.send_message(message.from_user.id, leaderboard)

@dp.message(Command("balance"))
async def balance(message: types.Message):
    user_id = message.from_user.id
    user = collection.find_one({"id": user_id})

    if user is not None:
        balance = user["Balance"]
        if balance == 0:
            balance += 1000
            collection.update_one({"id": user_id}, {"$set": {"Balance": balance}})
            await bot.send_message(message.from_user.id, f"Your balance was 0, so we added 1000 coins to you. Now your balance is {balance} coins.")
        else:
            await bot.send_message(message.from_user.id, f"🤑Your balance is {balance}💰")
    else:
        await bot.send_message(message.from_user.id, "Error, try /start.")

@dp.message(Command("roll"))
async def handler_game(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    last_roll = {}
    if user_id in last_roll and time.time() - last_roll[user_id] < 10:
        await bot.send_message(user_id, "Please, wait 10 seconds before using the command /roll.")
        return

    last_roll[user_id] = time.time()
    if command.args is None:
        await bot.send_message(message.from_user.id, "Error, try: /roll 1")
        return

    try:
        bet = int(command.args)
    except ValueError:
        await bot.send_message(message.from_user.id, "Error, try: /roll 1")
        return
    user_id = message.from_user.id
    user = collection.find_one({"id": user_id})

    if user is None:
        await bot.send_message(message.from_user.id, "Error,try /start.")
        return

    balance = user["Balance"]

    if bet > balance:
        await bot.send_message(message.from_user.id, "You don't have enough money to bet.")
        return

    if bet > 0:
        msg = await bot.send_message(message.from_user.id, "Dealer points: ")
        await asyncio.sleep(0.1)
        msg1 = await bot.send_dice(message.from_user.id)
        value = msg1.dice.value
        await asyncio.sleep(4)
        await msg.edit_text(f"Dealer points: {value}")

        msg = await bot.send_message(message.from_user.id, "Player points: ")
        await asyncio.sleep(0.1)
        msg1 = await bot.send_dice(message.from_user.id)
        value2 = msg1.dice.value
        await asyncio.sleep(4)
        await msg.edit_text(f"Player points: {value2}")

        if value > value2:
            balance -= bet
            await bot.send_message(message.from_user.id, "You lose! But 99,99% gamblers leave befor BIG WIN!")
            await bot.send_message(message.from_user.id,f"Your Balance {balance}")
        elif value < value2:
            balance += bet
            await bot.send_message(message.from_user.id, "You win!")
            await bot.send_message(message.from_user.id,f"Your Balance: {balance}")
        else:
            await bot.send_message(message.from_user.id, "Draw!")
            await bot.send_message(message.from_user.id,f"Your Balance: {balance}")

        collection.update_one({"id": user_id}, {"$set": {"Balance": balance}})
    else:
        await bot.send_message(message.from_user.id, "Error, try: /roll 1")

async def main() -> None:
    bot = Bot(TOKEN)
    await bot.set_my_commands([
        types.BotCommand(command="/leaderboards", description="Show Leaderboards"),
        types.BotCommand(command="/roll", description="Roll dice")
    ])
    await dp.start_polling(bot)


# async def main() -> None:
#     bot = Bot(TOKEN)
#     await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
