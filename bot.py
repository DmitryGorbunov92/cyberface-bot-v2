import asyncio
import os
import logging
import base64
import json
import aiohttp
import re
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
ADMIN_ID = 1343198511
STATS_FILE = "/data/stats.json" 

# --- СОСТОЯНИЯ (FSM) ---
class UserState(StatesGroup):
    waiting_for_art_photo = State()
    waiting_for_edit_photo = State()
    waiting_for_gift_photo = State()
    waiting_for_text = State()
    waiting_for_music_prompt = State()

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
    builder.button(text="🎵 Создать песню", callback_data="menu_music")
    builder.button(text="🖼 Нарисовать с нуля", callback_data="menu_text_art")
    builder.button(text="📸 Изменить фото (текст)", callback_data="menu_edit")
    builder.button(text="🎁 Сделать подарок", callback_data="menu_gift")
    builder.button(text="ℹ️ Как это работает", callback_data="menu_help")
    builder.adjust(1, 1, 1, 1, 1, 1)
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

def get_gender_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской голос", callback_data="music_male")
    builder.button(text="👩 Женский голос", callback_data="music_female")
    builder.adjust(2)
    return builder.as_markup()

def get_genre_keyboard(gender):
    builder = InlineKeyboardBuilder()
    builder.button(text="🎸 Рок", callback_data=f"genre_rock_{gender}")
    builder.button(text="🎤 Рэп", callback_data=f"genre_rap_{gender}")
    builder.button(text="🎧 Поп", callback_data=f"genre_pop_{gender}")
    builder.button(text="🎹 Электроника", callback_data=f"genre_electro_{gender}")
    builder.adjust(2)
    return builder.as_markup()

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
        "создать уникальную песню или отредактировать фото.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации (для фото).\n\n"
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
        "создать уникальную песню или отредактировать фото.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации (для фото).\n\n"
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
        await callback.message.answer("Отправь фото, а затем напиши, что с ним сделать (например, 'сделай закат').")
    elif action == "gift":
        await state.set_state(UserState.waiting_for_gift_photo)
        await callback.message.answer("🎁 Отлично! Отправь фото друга или близкого, и я сделаю для него крутой арт.")
    elif action == "music":
        await state.set_state(UserState.waiting_for_music_prompt)
        await callback.message.answer("🎵 Напиши, о чем будет песня (например: 'Песня про моего кота, который любит спать').")
    elif action == "help":
        await callback.message.answer(
            "Я умею делать арты по фото, генерировать картинки по тексту и менять фото по описанию. "
            "А еще я могу создавать песни (50 Stars за 2 варианта трека)."
        )

# --- ПРОВЕРКА ЛИМИТОВ (ДЛЯ ФОТО) ---
async def check_limit(message: Message, user_id: int):
    count = user_generations.get(user_id, 0)
    if user_id != ADMIN_ID and count >= 2:
        await message.answer("Бесплатные генерации картинок закончились! Хочешь еще 5 штук за 50 Stars?")
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="5 генераций AI Portrait",
            description="Оплата 5 дополнительных генераций картинок",
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
    if not await check_limit(message, user_id): return

    current_state = await state.get_state()
    
    if current_state == UserState.waiting_for_art_photo:
        user_photos[user_id] = message.photo[-1].file_id
        await message.answer("Отличное фото! Теперь выбери стиль:", reply_markup=get_styles_keyboard())
    elif current_state == UserState.waiting_for_edit_photo:
        user_photos[user_id] = message.photo[-1].file_id
        await state.set_state(UserState.waiting_for_text)
        await message.answer("Фото получено! Теперь напиши текстом, что с ним сделать (например, 'замени фон на пляж').")
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
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer(f"Ошибка: {str(e)[:150]}...")

# --- ТЕКСТ (С УЧЕТОМ СОСТОЯНИЙ) ---
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    if message.text.startswith('/') or message.text in ["📸 Создать фото", "ℹ️ Как это работает", "🎁 Пригласить друга"]:
        return

    user_id = message.from_user.id
    current_state = await state.get_state()
    
    # 1. Текст для музыки
    if current_state == UserState.waiting_for_music_prompt:
        await state.update_data(music_prompt=message.text)
        await message.answer("Отлично! Теперь выбери, какой голос будет петь:", reply_markup=get_gender_keyboard())
        return

    if not await check_limit(message, user_id): return

    # 2. Если ждем текст для рисования с нуля
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

    # 3. Если ждем текст для изменения фото
    elif current_state == UserState.waiting_for_text and user_id in user_photos:
        await message.answer("Применяю изменения к фото... ⏳")
        try:
            file_id = user_photos[user_id]
            file = await bot.get_file(file_id)
            file_path = f"temp_{user_id}.jpg"
            await bot.download_file(file.file_path, file_path)
            
            with open(file_path, "rb") as image_file:
                response = await client.images.edit(
                    model="gemini-2.5-flash-image",
                    image=image_file,
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
            if os.path.exists(file_path): os.remove(file_path)
        except Exception as e:
            await message.answer("Ошибка редактирования.")

    else:
        await message.answer("Я не понял команду. Нажми /start и выбери действие из меню 👇")

# --- ВЫБОР ГОЛОСА И ЖАНРА ДЛЯ МУЗЫКИ ---
@dp.callback_query(F.data.startswith("music_"))
async def handle_music_gender(callback: CallbackQuery, state: FSMContext):
    gender = "male" if callback.data == "music_male" else "female"
    await state.update_data(music_gender=gender)
    await callback.message.edit_text("Отлично! Теперь выбери жанр песни:", reply_markup=get_genre_keyboard(gender))
    await callback.answer()

@dp.callback_query(F.data.startswith("genre_"))
async def handle_music_genre(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    genre = parts[1]
    gender = parts[2]
    
    data = await state.get_data()
    prompt_text = data.get("music_prompt", "Песня про жизнь")
    user_id = callback.from_user.id
    
    await state.clear()
    
    if user_id == ADMIN_ID:
        await callback.message.edit_text(f"🎵 Тема: {prompt_text}\n🎸 Жанр: {genre}\n\n[Админ-режим] Генерирую песню бесплатно... 🎶")
        await generate_music(callback.message, prompt_text, genre, gender)
        return

    await callback.message.edit_text(f"🎵 Тема: {prompt_text}\n🎸 Жанр: {genre}\n\nГенерация песни стоит 50 Stars. После оплаты ты получишь сразу 2 варианта трека. Выставить счет?")
    
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Генерация песни",
        description="2 варианта трека на выбор",
        payload=f"music_pay_{genre}_{gender}_{prompt_text[:50]}", 
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Генерация песни", amount=50)]
    )
    await callback.answer()

# --- ФУНКЦИЯ ГЕНЕРАЦИИ МУЗЫКИ ---
async def generate_music(message: Message, prompt_text: str, genre: str, gender: str):
    try:
        response = await client.chat.completions.create(
            model="suno-v6",
            messages=[
                {"role": "user", "content": f"Создай песню на русском. Жанр: {genre}. Голос: {gender}. Тема: {prompt_text}. Чистый вокал без акцента."}
            ]
        )
        
        content = response.choices[0].message.content
        
        # Ищем ссылку на mp3 в ответе
        audio_url_match = re.search(r'https://[^\s\)]+\.mp3', content)
        
        if audio_url_match:
            audio_url = audio_url_match.group(0)
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as resp:
                    if resp.status == 200:
                        audio_bytes = await resp.read()
                        audio_file = BufferedInputFile(audio_bytes, filename="song.mp3")
                        await message.answer_audio(audio=audio_file, caption="🎶 Твоя песня готова! Наслаждайся!")
                    else:
                        await message.answer(f"Не удалось скачать песню (Код: {resp.status})")
        else:
            await message.answer(f"Песня сгенерирована, но ссылка не найдена. Ответ BotHub:\n\n{content[:500]}...")
            
    except Exception as e:
        logging.error(f"Music Error: {e}")
        await message.answer(f"Ошибка при генерации музыки: {str(e)[:150]}...")

# --- ОПЛАТА (ФОТО И МУЗЫКА) ---
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def payment_ok(message: Message, state: FSMContext):
    payload = message.successful_payment.invoice_payload
    
    if payload.startswith("music_pay_"):
        parts = payload.split("_")
        genre = parts[2]
        gender = parts[3]
        prompt_text = "_".join(parts[4:]) 
        
        await message.answer("✅ Оплата получена! Генерирую песню (это займет около 2-3 минут)... 🎶")
        await generate_music(message, prompt_text, gender)
            
    else:
        user_generations[message.from_user.id] = 0 
        await message.answer("Оплата прошла! 🎉 Добавлено 5 генераций картинок.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
