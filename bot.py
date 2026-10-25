import asyncio
import os
import logging
import base64
import json
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

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

# --- СТАТИСТИКА И РЕФЕРАЛЫ ---
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
    "cyber": "Киберпанк-портрет в неоновом свете, футуристичный стиль, высокое качество. Сохрани лица всех людей на фото, не меняй их черты.",
    "anime": "Аниме-стиль, 2D, большие глаза, яркие цвета, стиль студии Ghibli, детализированный фон. Сохрани лица всех людей на фото, не меняй их черты.",
    "3d": "3D-мультфильм, стиль Pixar/Disney, милый, мягкий свет, детализированная текстура кожи. Сохрани лица всех людей на фото, не меняй их черты.",
    "military": "Тактический военный стиль, камуфляж, разгрузка, суровый взгляд, реалистичный. Сохрани лица всех людей на фото, не меняй их черты.",
    "movie": "Голливудский блокбастер, кинематографичный свет, драматичные тени, постер фильма, 8k. Сохрани лица всех людей на фото, не меняй их черты.",
    "noir": "Нуар, черно-белый, драматичный свет, стиль детектива 1940-х, дождь, плащ. Сохрани лица всех людей на фото, не меняй их черты.",
    "painting": "Живопись эпохи Возрождения, масляные краски, классическое искусство, барочный свет. Сохрани лица всех людей на фото, не меняй их черты.",
    "fantasy": "Фэнтези, стиль D&D, средневековые доспехи, эпический фон, магический свет. Сохрани лица всех людей на фото, не меняй их черты.",
    "royal": "Королевская роскошь, барокко, золотые украшения, элегантная одежда, дорогой свет. Сохрани лица всех людей на фото, не меняй их черты.",
    "retro": "Ретро 1980-х, винтажная фотография, зерно пленки, неоновые вывески, теплые тона. Сохрани лица всех людей на фото, не меняй их черты."
}

def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📸 Создать фото")
    builder.button(text="🎁 Пригласить друга")
    builder.button(text="ℹ️ Как это работает")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

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

# --- СТАРТ ---
@dp.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandStart):
    user_id = message.from_user.id
    referrer_id = command.args
    
    if str(user_id) not in stats_data["total_users"]:
        stats_data["total_users"].append(str(user_id))
        # Запоминаем, кто пригласил (если это не сам пользователь)
        if referrer_id and referrer_id != str(user_id):
            stats_data["referrals"][str(user_id)] = referrer_id
        save_stats(stats_data)

    await message.answer(
        "Привет! Я бот CyberFace. 🤖\n"
        "Пришли мне своё фото и выбери стиль, или просто напиши, что нарисовать.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    if str(user_id) not in stats_data["total_users"]:
        stats_data["total_users"].append(str(user_id))
        save_stats(stats_data)

    await message.answer(
        "Привет! Я бот CyberFace. 🤖\n"
        "Пришли мне своё фото и выбери стиль, или просто напиши, что нарисовать.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🎁 Пригласить друга")
async def invite_friend(message: Message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/CyberFace_ru_bot?start={user_id}"
    await message.answer(
        "🎁 **Партнерская программа**\n\n"
        "Пригласи друга по своей ссылке. Как только он купит пакет генераций (50 Stars), ты получишь **+2 бесплатные генерации** в подарок!\n\n"
        f"Твоя ссылка:\n`{ref_link}`",
        parse_mode="Markdown"
    )

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = len(stats_data["total_users"])
    gens = stats_data["total_generations"]
    refs = len(stats_data["referrals"])
    await message.answer(f"📊 **Статистика:**\n👥 Юзеров: {total}\n🎨 Генераций: {gens}\n🔗 Рефералов (перешли): {refs}", parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Как это работает")
async def help_cmd(message: Message):
    await message.answer(
        "Всё просто:\n"
        "1️⃣ Отправь мне своё селфи (или напиши текст).\n"
        "2️⃣ Выбери стиль из предложенных кнопок (для фото).\n"
        "3️⃣ Нейросеть обработает запрос (займет около 30 секунд).\n"
        "4️⃣ Получи крутой арт!\n\n"
        "💳 Первые 2 генерации — бесплатно.\n"
        "Дальше: 50 Telegram Stars за пакет из 5 генераций."
    )

@dp.message(F.text == "📸 Создать фото")
async def ask_photo(message: Message):
    await message.answer("Жду твоё фото! Просто отправь его в чат. 📥")

# --- ОБРАБОТКА ФОТО ---
@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    count = user_generations.get(user_id, 0)
    
    if user_id != ADMIN_ID and count >= 2:
        await message.answer("Бесплатные генерации закончились! Хочешь еще 5 штук за 50 Stars?")
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="5 генераций CyberFace",
            description="Оплата 5 дополнительных генераций",
            payload="5_generations",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="5 генераций", amount=50)]
        )
        return

    user_photos[user_id] = message.photo[-1].file_id
    await message.answer("Отличное фото! Теперь выбери стиль:", reply_markup=get_styles_keyboard())

@dp.callback_query(F.data.startswith("style_"))
async def handle_style_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    style_key = callback.data.replace("style_", "")
    
    if user_id not in user_photos:
        await callback.message.answer("Фото устарело. Отправь новое фото.")
        return

    await callback.message.edit_text(f"Выбран стиль: {style_key}. Обрабатываю фото... ⏳")
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
        
        if response.data and len(response.data) > 0:
            image_base64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)
            photo = BufferedInputFile(image_bytes, filename="cyberface.jpg")
            
            count = user_generations.get(user_id, 0)
            user_generations[user_id] = count + 1
            stats_data["total_generations"] += 1
            save_stats(stats_data)
            
            left = 2 - user_generations[user_id] if user_id != ADMIN_ID else "∞"
            await callback.message.answer_photo(photo=photo, caption=f"Готово! ⚡️ Осталось бесплатных: {left}")
        else:
            await callback.message.answer("Не удалось сгенерировать фото.")
            
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer(f"Ошибка: {str(e)[:150]}...")

# --- ОБРАБОТКА ТЕКСТА ---
@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith('/') or message.text in ["📸 Создать фото", "ℹ️ Как это работает", "🎁 Пригласить друга"]:
        return

    user_id = message.from_user.id
    count = user_generations.get(user_id, 0)
    
    if user_id != ADMIN_ID and count >= 2:
        await message.answer("Бесплатные генерации закончились! Хочешь еще 5 штук за 50 Stars?")
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="5 генераций CyberFace",
            description="Оплата 5 дополнительных генераций",
            payload="5_generations",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="5 генераций", amount=50)]
        )
        return

    await message.answer("Рисую по твоему описанию, подожди около 30 секунд... 🎨")
    
    try:
        response = await client.images.generate(
            model="gemini-2.5-flash-image",
            prompt=f"Высокодетализированное изображение: {message.text}. Стиль: реализм, 8k, качество.",
            response_format="b64_json",
            n=1,
            size="1024x1024"
        )
        
        if response.data and len(response.data) > 0:
            image_base64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)
            photo = BufferedInputFile(image_bytes, filename="cyberface_art.jpg")
            
            count = user_generations.get(user_id, 0)
            user_generations[user_id] = count + 1
            stats_data["total_generations"] += 1
            save_stats(stats_data)
            
            left = 2 - user_generations[user_id] if user_id != ADMIN_ID else "∞"
            await message.answer_photo(photo=photo, caption=f"Готово! ⚡️ Осталось бесплатных: {left}")
        else:
            await message.answer("Не удалось нарисовать.")
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"Ошибка: {str(e)[:150]}...")

# --- ОПЛАТА И НАЧИСЛЕНИЕ БОНУСОВ ---
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    user_generations[user_id] = 0 
    
    # Проверяем, есть ли пригласивший у этого пользователя
    referrer_id = stats_data["referrals"].get(str(user_id))
    
    if referrer_id:
        # Начисляем бонус пригласившему (+2 генерации)
        current_ref_count = user_generations.get(int(referrer_id), 0)
        user_generations[int(referrer_id)] = current_ref_count - 2 # Сдвигаем лимит назад
        try:
            await bot.send_message(int(referrer_id), "🎉 Твой друг купил пакет! Тебе начислено +2 бесплатные генерации.")
        except:
            pass
            
    await message.answer("Оплата прошла успешно! 🎉 Тебе добавлено 5 новых генераций.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
