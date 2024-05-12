from config import TOKEN,MONGODB,DATABASE,COLLECTION
from aiogram.filters import Command,CommandObject
from pymongo.mongo_client import MongoClient
from pymongo import MongoClient, DESCENDING
from aiogram import Bot,types,Dispatcher
import logging
import asyncio
import time
import sys

bot = Bot(token=TOKEN,parse_mode="HTML")
dp = Dispatcher()
balance = 1000
last_roll ={}

@dp.message(Command("start"))
async def start(message: types.Message):
    await bot.send_message(message.from_user.id,"Hey, i'm casino bot in telegram use Games for check avalible games, send /help to see commands")
    try:
        client = MongoClient(MONGODB)
        database = client[DATABASE]
        collection = database[COLLECTION]
    except Exception as e:
        raise Exception("The following error occurred: ", e)
    
    user_id = message.from_user.id
    user_name = message.from_user.username
    user = {
        "id" : user_id,
        "Name" : user_name,
        "Balance" : 1000
    }
    
    if collection.find_one({"id": user_id}) is None:
        result = collection.insert_one(user)

@dp.message(Command("help"))
async def help(message: types.Message):
    await bot.send_message(message.from_user.id,"/roll {bet}\n/leaderboards\n/balance\n")

@dp.message(Command("leaderboards"))
async def leaderboards(message: types.Message):
    client = MongoClient(MONGODB)
    database = client[DATABASE]
    collection = database[COLLECTION]
    top_users = collection.find().sort("Balance", DESCENDING).limit(10)
    leaderboard = "Top 10 users:\n\n"

    for i, user in enumerate(top_users, start=1):
        username = user["Name"]
        balance = user["Balance"]
        leaderboard += f"{i}. {username}: {balance}\n"

    await bot.send_message(message.from_user.id, leaderboard)

@dp.message(Command("balance"))
async def balance(message: types.Message):
    client = MongoClient(MONGODB)
    database = client[DATABASE]
    collection = database[COLLECTION]

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

    client = MongoClient(MONGODB)
    database = client[DATABASE]
    collection = database[COLLECTION]

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
            await bot.send_message(message.from_user.id, "You lose! But 99,99% players leave befor BIG WIN!")
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())