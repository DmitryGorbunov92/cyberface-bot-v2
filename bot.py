import asyncio
import os
import logging
import base64
import json
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Токены
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOTHUB_API_KEY = os.environ.get("BOTHUB_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = AsyncOpenAI(
    api_key=BOTHUB_API_KEY,
    base_url="https://openai.bothub.chat/v1"
)

user_generations = {}
user_photos = {} 
user_second_photos = {}
ADMIN_ID = 1343198511
STATS_FILE = "/data/stats.json" 

# --- СОСТОЯНИЯ ---
class UserState(StatesGroup):
    waiting_for_art_photo = State()
    waiting_for_edit_photo = State()
    waiting_for_edit_text = State()
    waiting_for_gift_photo = State()
    waiting_for_text = State()

# --- СТАТИСТИКА ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"total_users": [], "total_generations": 0, "referrals": {}}
    return {"total_users": [], "total_generations": 0, "referrals": {}}

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)

stats_data = load_stats()

# --- СТИЛИ ---
STYLES = {
    "cyber": "Киберпанк-портрет в неоновом свете, футуристичный стиль. Сохрани лица всех людей на фото.",
    "anime": "Аниме-стиль, 2D, большие глаза, яркие цвета, студия Ghibli. Сохрани лица всех людей на фото.",
    "3d": "3D-мультфильм, стиль Pixar/Disney, милый, мягкий свет, текстура кожи. Сохрани лица всех людей на фото.",
    "military": "Тактический военный стиль, камуфляж, суровый взгляд. Сохрани лица всех людей на фото.",
    "movie": "Голливудский блокбастер, кинематографичный свет, постер фильма, 8k. Сохрани лица всех людей на фото.",
    "noir": "Нуар, черно-белый, драматичный свет, стиль детектива 1940-х. Сохрани лица всех людей на фото.",
    "painting": "Живопись эпохи Возрождения, масляные краски, барочный свет. Сохрани лица всех людей на фото.",
    "fantasy": "Фэнтези, стиль D&D, средневековые доспехи, магический свет. Сохрани лица всех людей на фото.",
    "royal": "Королевская роскошь, барокко, золотые украшения, дорогой свет. Сохрани лица всех людей на фото.",
    "retro": "Ретро 1980-х, винтажная фотография, зерно пленки, неоновые вывески. Сохрани лица всех людей на фото."
}

# --- КЛАВИАТУРЫ ---
def get_start_showcase():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 Создать арт по фото", callback_data="menu_art")
    builder.button(text="🖼 Нарисовать с нуля", callback_data="menu_text_art")
    builder.button(text="📸 Изменить фото (текст)", callback_data="menu_edit")
    builder.button(text="🎁 Сделать подарок", callback_data="menu_gift")
    builder.button(text="ℹ️ Как это работает", callback_data="menu_help")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()

def get_styles_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Киберпанк", callback_data="style_cyber")
    builder.button(text="🌸 Аниме", callback_data="style_anime")
    builder.button(text="🧸 3D Мультфильм", callback_data="style_3d")
    builder.button(text="🎖 Военный", callback_data="style_military")
    builder.button(text="🎬 Голливуд", callback_data="style_movie")
    builder.button(text="🕵️ Нуар", callback_data="style_noir")
    builder.button(text="🖼 Живопись", callback_data="style_painting")
    builder.button(text="🐉 Фэнтези", callback_data="style_fantasy")
    builder.button(text="👑 Роскошь", callback_data="style_royal")
    builder.button(text="🎞 Ретро", callback_data="style_retro")
    builder.adjust(2)
    return builder.as_markup()

# ==========================================
# КОМАНДА /stats (СТОИТ САМОЙ ПЕРВОЙ, ЧТОБЫ НЕ ПЕРЕХВАТЫВАЛИ)
# ==========================================
@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = len(stats_data["total_users"])
    gens = stats_data["total_generations"]
    refs = len(stats_data["referrals"])
    await message.answer(f"📊 **Статистика:**\n👥 Юзеров: {total}\n🎨 Генераций: {gens}\n🔗 Рефералов: {refs}", parse_mode="Markdown")

# --- СТАРТ ---
@dp.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandStart, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    referrer_id = command.args
    
    if str(user_id) not in stats_data["total_users"]:
        stats_data["total_users"].append(str(user_id))
        if referrer_id and referrer_id != str(user_id):
            stats_data["referrals"][str(user_id)] = referrer_id
        save_stats(stats_data)

    await message.answer(
        "👋 **Добро пожаловать в AI Portrait!**\n\n"
        "Здесь ты можешь превратить свои фото в крутые арты, "
        "или отредактировать фото с помощью ИИ.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.\n\n"
        "👇 **Выбери, что хочешь сделать:**",
        reply_markup=get_start_showcase(),
        parse_mode="Markdown"
    )

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if str(user_id) not in stats_data["total_users"]:
        stats_data["total_users"].append(str(user_id))
        save_stats(stats_data)

    await message.answer(
        "👋 **Добро пожаловать в AI Portrait!**\n\n"
        "Здесь ты можешь превратить свои фото в крутые арты, "
        "или отредактировать фото с помощью ИИ.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.\n\n"
        "👇 **Выбери, что хочешь сделать:**",
        reply_markup=get_start_showcase(),
        parse_mode="Markdown"
    )

# --- ОБРАБОТКА КНОПОК МЕНЮ ---
@dp.callback_query(F.data.startswith("menu_"))
async def handle_menu(callback: CallbackQuery, state: FSMContext):
    action = callback.data.replace("menu_", "")
    await callback.answer()
    
    if action == "art":
        await state.set_state(UserState.waiting_for_art_photo)
        await callback.message.answer("Отправь мне своё фото, и я предложу стили! 📥")
    elif action == "text_art":
        await state.set_state(UserState.waiting_for_text)
        await callback.message.answer("Напиши, что нарисовать (например, 'Кот в космосе'). 🎨")
    elif action == "edit":
        await state.set_state(UserState.waiting_for_edit_photo)
        await callback.message.answer("Отправь первое фото. 📥")
    elif action == "gift":
        await state.set_state(UserState.waiting_for_gift_photo)
        await callback.message.answer("🎁 Отлично! Отправь фото друга или близкого, и я сделаю для него крутой арт.")
    elif action == "help":
        await callback.message.answer(
            "Я умею делать арты по фото, генерировать картинки по тексту и менять фото по описанию. "
            "В режиме 'Изменить фото' можно отправить два фото подряд, чтобы склеить лица в одной сцене."
        )

# --- ПРОВЕРКА ЛИМИТОВ ---
async def check_limit(message: Message, user_id: int):
    count = user_generations.get(user_id, 0)
    if user_id != ADMIN_ID and count >= 2:
        await message.answer("Бесплатные генерации закончились! Хочешь еще 5 штук за 50 Stars?")
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="5 генераций AI Portrait",
            description="Оплата 5 дополнительных генераций",
            payload="5_generations",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="5 генераций", amount=50)]
        )
        return False
    return True

# --- ПРИЕМ ФОТО ---
@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()

    # 1. Режим "Изменить фото" (Редактирование и склейка)
    if current_state == UserState.waiting_for_edit_photo or current_state == UserState.waiting_for_edit_text:
        
        if current_state == UserState.waiting_for_edit_photo:
            user_photos[user_id] = message.photo[-1].file_id
            await state.set_state(UserState.waiting_for_edit_text)
            await message.answer("Первое фото получено! Теперь напиши, что с ним сделать, или **отправь второе фото**, чтобы склеить двух людей.")
        elif current_state == UserState.waiting_for_edit_text and user_id in user_photos:
            user_second_photos[user_id] = message.photo[-1].file_id
            await message.answer("Второе фото получено! Теперь напиши, какую сцену сделать с этими двумя людьми (например, 'мы убегаем от призрака').")
        return

    # 2. Остальные режимы (Арт, Подарок)
    if not await check_limit(message, user_id): return

    if current_state == UserState.waiting_for_art_photo:
        user_photos[user_id] = message.photo[-1].file_id
        await message.answer("Отличное фото! Теперь выбери стиль:", reply_markup=get_styles_keyboard())
    elif current_state == UserState.waiting_for_gift_photo:
        user_photos[user_id] = message.photo[-1].file_id
        await message.answer("Фото получено! Выбери стиль для подарка:", reply_markup=get_styles_keyboard())
    else:
        await message.answer("Сначала выбери действие в меню /start 👇")

# --- ГЕНЕРАЦИЯ ПО СТИЛЮ ---
@dp.callback_query(F.data.startswith("style_"))
async def handle_style(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    style_key = callback.data.replace("style_", "")
    
    if user_id not in user_photos:
        await callback.message.answer("Фото устарело. Отправь новое фото.")
        return

    await callback.message.edit_text("Обрабатываю фото... ⏳")
    await callback.answer()
    
    try:
        file_id = user_photos[user_id]
        file = await bot.get_file(file_id)
        file_path = f"temp_{user_id}.jpg"
        await bot.download_file(file.file_path, file_path)
        
        prompt = STYLES.get(style_key, STYLES["cyber"])
        
        with open(file_path, "rb") as image_file:
            response = await client.images.edit(
                model="gemini-2.5-flash-image",
                image=image_file,
                prompt=prompt,
                response_format="b64_json"
            )
        
        if response.data:
            image_base64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)
            photo = BufferedInputFile(image_bytes, filename="art.jpg")
            
            count = user_generations.get(user_id, 0)
            user_generations[user_id] = count + 1
            stats_data["total_generations"] += 1
            save_stats(stats_data)
            
            left = 2 - user_generations[user_id] if user_id != ADMIN_ID else "∞"
            await callback.message.answer_photo(photo=photo, caption=f"Готово! ⚡️ Осталось бесплатных: {left}")
        else:
            await callback.message.answer("Не удалось сгенерировать.")
        if os.path.exists(file_path): os.remove(file_path)
        if user_id in user_photos: del user_photos[user_id]
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer(f"Ошибка: {str(e)[:150]}...")

# --- ОБРАБОТКА ТЕКСТА ---
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    if message.text.startswith('/') or message.text in ["📸 Создать фото", "ℹ️ Как это работает", "🎁 Пригласить друга"]:
        return

    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if not await check_limit(message, user_id): return

    # 1. Текст для генерации с нуля
    if current_state == UserState.waiting_for_text and user_id not in user_photos:
        await message.answer("Рисую с нуля по описанию... 🎨")
        try:
            response = await client.images.generate(
                model="gemini-2.5-flash-image",
                prompt=f"Высокодетализированное изображение: {message.text}. Стиль: реализм, 8k.",
                response_format="b64_json",
                n=1,
                size="1024x1024"
            )
            if response.data:
                image_bytes = base64.b64decode(response.data[0].b64_json)
                photo = BufferedInputFile(image_bytes, filename="art_from_text.jpg")
                count = user_generations.get(user_id, 0)
                user_generations[user_id] = count + 1
                left = 2 - user_generations[user_id] if user_id != ADMIN_ID else "∞"
                await message.answer_photo(photo=photo, caption=f"Готово! ⚡️ Осталось: {left}")
                await state.clear()
        except Exception as e:
            await message.answer("Ошибка генерации.")

    # 2. Текст для редактирования (и склейки)
    elif current_state == UserState.waiting_for_edit_text and user_id in user_photos:
        await message.answer("Применяю изменения... ⏳")
        try:
            file1 = await bot.get_file(user_photos[user_id])
            path1 = f"temp1_{user_id}.jpg"
            await bot.download_file(file1.file_path, path1)
            
            if user_id in user_second_photos:
                # СКЛЕЙКА ДВУХ ФОТО
                file2 = await bot.get_file(user_second_photos[user_id])
                path2 = f"temp2_{user_id}.jpg"
                await bot.download_file(file2.file_path, path2)
                
                combined_prompt = f"Создай единую сцену. На первом фото человек А, на втором фото человек Б. Они должны быть вместе. Сцена: {message.text}. Сохрани их лица."
                
                with open(path1, "rb") as f1, open(path2, "rb") as f2:
                    response = await client.images.edit(
                        model="gemini-2.5-flash-image",
                        image=[f1, f2],
                        prompt=combined_prompt,
                        response_format="b64_json"
                    )
                os.remove(path2)
            else:
                # Обычное редактирование
                with open(path1, "rb") as f1:
                    response = await client.images.edit(
                        model="gemini-2.5-flash-image",
                        image=f1,
                        prompt=message.text,
                        response_format="b64_json"
                    )
            
            if response.data:
                image_bytes = base64.b64decode(response.data[0].b64_json)
                photo = BufferedInputFile(image_bytes, filename="edit.jpg")
                count = user_generations.get(user_id, 0)
                user_generations[user_id] = count + 1
                left = 2 - user_generations[user_id] if user_id != ADMIN_ID else "∞"
                await message.answer_photo(photo=photo, caption=f"Готово! ⚡️ Осталось: {left}")
                await state.clear()
            
            if os.path.exists(path1): os.remove(path1)
            if user_id in user_photos: del user_photos[user_id]
            if user_id in user_second_photos: del user_second_photos[user_id]
            
        except Exception as e:
            logging.error(f"Edit Error: {e}")
            await message.answer("Ошибка редактирования.")

    else:
        await message.answer("Я не понял команду. Нажми /start и выбери действие из меню 👇")

# --- ОПЛАТА ---
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def payment_ok(message: Message, state: FSMContext):
    user_generations[message.from_user.id] = 0 
    await message.answer("Оплата прошла! 🎉 Добавлено 5 генераций.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
