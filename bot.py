import asyncio
import os
import logging
import base64
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Токены из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOTHUB_API_KEY = os.environ.get("BOTHUB_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Клиент BotHub
client = AsyncOpenAI(
    api_key=BOTHUB_API_KEY,
    base_url="https://openai.bothub.chat/v1"
)

user_generations = {}
user_photos = {} # Временное хранилище фото для выбора стиля

# Словарь стилей (Название: Промпт)
STYLES = {
    "cyber": "Киберпанк-портрет в неоновом свете, футуристичный стиль, высокое качество. Сохрани лицо человека.",
    "anime": "Аниме-стиль, 2D, большие глаза, яркие цвета, стиль студии Ghibli, детализированный фон. Сохрани лицо человека.",
    "3d": "3D-мультфильм, стиль Pixar/Disney, милый, мягкий свет, детализированная текстура кожи. Сохрани лицо человека.",
    "military": "Тактический военный стиль, камуфляж, разгрузка, суровый взгляд, реалистичный. Сохрани лицо человека.",
    "movie": "Голливудский блокбастер, кинематографичный свет, драматичные тени, постер фильма, 8k. Сохрани лицо человека.",
    "noir": "Нуар, черно-белый, драматичный свет, стиль детектива 1940-х, дождь, плащ. Сохрани лицо человека.",
    "painting": "Живопись эпохи Возрождения, масляные краски, классическое искусство, барочный свет. Сохрани лицо человека.",
    "fantasy": "Фэнтези, стиль D&D, средневековые доспехи, эпический фон, магический свет. Сохрани лицо человека.",
    "royal": "Королевская роскошь, барокко, золотые украшения, элегантная одежда, дорогой свет. Сохрани лицо человека.",
    "retro": "Ретро 1980-х, винтажная фотография, зерно пленки, неоновые вывески, теплые тона. Сохрани лицо человека."
}

def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📸 Создать фото")
    builder.button(text="ℹ️ Как это работает")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# Функция для создания кнопок стилей
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
    builder.adjust(2) # По 2 кнопки в ряд
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "Привет! Я бот CyberFace. 🤖\n"
        "Пришли мне своё фото, выбери стиль, и я сделаю из него крутой арт.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "ℹ️ Как это работает")
async def help_cmd(message: Message):
    await message.answer(
        "Всё просто:\n"
        "1️⃣ Отправь мне своё селфи или любое фото.\n"
        "2️⃣ Выбери стиль из предложенных кнопок.\n"
        "3️⃣ Нейросеть обработает фото (займет около 30 секунд).\n"
        "4️⃣ Получи крутой арт!\n\n"
        "💳 Первые 2 генерации — бесплатно.\n"
        "Дальше: 50 Telegram Stars за пакет из 5 фото."
    )

@dp.message(F.text == "📸 Создать фото")
async def ask_photo(message: Message):
    await message.answer("Жду твоё фото! Просто отправь его в чат. 📥")

# 1. Пользователь присылает фото -> предлагаем стили
@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    count = user_generations.get(user_id, 0)
    
    if count >= 2:
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

    # Сохраняем ID фото, чтобы использовать его после выбора стиля
    user_photos[user_id] = message.photo[-1].file_id
    await message.answer("Отличное фото! Теперь выбери стиль, в котором я его обработаю:", reply_markup=get_styles_keyboard())

# 2. Пользователь нажимает на кнопку стиля -> генерируем
@dp.callback_query(F.data.startswith("style_"))
async def handle_style_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    style_key = callback.data.replace("style_", "")
    
    if user_id not in user_photos:
        await callback.message.answer("Ошибка: фото не найдено. Пожалуйста, отправь фото заново.")
        return

    await callback.message.edit_text(f"Выбран стиль: {style_key}. Обрабатываю фото, подожди около 30 секунд... ⏳")
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
            await callback.message.answer_photo(photo=photo, caption="Готово! ⚡️ Не забудь поделиться с друзьями!")
            
            # Обновляем счетчик
            count = user_generations.get(user_id, 0)
            user_generations[user_id] = count + 1
            
        else:
            await callback.message.answer("Не удалось сгенерировать фото. Попробуй позже.")
            
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer(f"Произошла ошибка: {str(e)[:150]}... Попробуй позже.")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    user_generations[user_id] = 0 
    await message.answer("Оплата прошла успешно! 🎉 Тебе добавлено 5 новых генераций.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
