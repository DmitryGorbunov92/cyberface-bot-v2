import asyncio
import os
import logging
import base64
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, BufferedInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Токены берутся из переменных окружения (Secrets)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOTHUB_API_KEY = os.environ.get("BOTHUB_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Клиент BotHub (OpenAI-совместимый)
client = AsyncOpenAI(
    api_key=BOTHUB_API_KEY,
    base_url="https://openai.bothub.chat/v1"
)

user_generations = {}

def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📸 Создать фото")
    builder.button(text="ℹ️ Как это работает")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "Привет! Я бот CyberFace. 🤖\n"
        "Пришли мне своё фото, и я сделаю из него крутой киберпанк-портрет.\n\n"
        "🎁 Тебе доступно 2 бесплатные генерации.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "ℹ️ Как это работает")
async def help_cmd(message: Message):
    await message.answer(
        "Всё просто:\n"
        "1️⃣ Отправь мне своё селфи или любое фото.\n"
        "2️⃣ Нейросеть обработает его (займет около 30 секунд).\n"
        "3️⃣ Получи крутой киберпанк-портрет!\n\n"
        "💳 Первые 2 генерации — бесплатно.\n"
        "Дальше: 50 Telegram Stars за пакет из 5 фото."
    )

@dp.message(F.text == "📸 Создать фото")
async def ask_photo(message: Message):
    await message.answer("Жду твоё фото! Просто отправь его в чат. 📥")

@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    count = user_generations.get(user_id, 0)
    
    if count >= 2:
        await message.answer("Бесплатные генерации закончились! Хочешь еще 5 штук за 50 Stars?")
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="5 генераций CyberFace",
            description="Оплата 5 дополнительных киберпанк-фото",
            payload="5_generations",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="5 генераций", amount=50)]
        )
        return

    await message.answer("Обрабатываю фото, подожди около 30 секунд... ⏳")
    
    try:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        file_path = f"temp_{user_id}.jpg"
        await bot.download_file(file.file_path, file_path)
        
        with open(file_path, "rb") as f:
            image_data = f.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Запрос к нейросети через BotHub
        response = await client.chat.completions.create(
            model="gemini-3.1-flash-image-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Переделай это фото в стиле киберпанк, неоновый свет, футуристичный портрет, высокое качество. Сохрани лицо человека."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            extra_body={"bothub": {"return_base64": True}}
        )
        
        message_dict = response.choices[0].message.model_dump()
        images = message_dict.get("images", [])
        
        if images:
            image_base64 = images[0]["image_url"]["url"]
            image_bytes = base64.b64decode(image_base64)
            photo = BufferedInputFile(image_bytes, filename="cyberface.jpg")
            await message.answer_photo(photo=photo, caption="Готово! ⚡️ Не забудь поделиться с друзьями!")
            user_generations[user_id] = count + 1
        else:
            await message.answer("Не удалось сгенерировать фото. Попробуй позже.")
            
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"Произошла ошибка: {str(e)[:100]}... Попробуй позже.")

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
