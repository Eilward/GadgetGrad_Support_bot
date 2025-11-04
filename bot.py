import asyncio
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Загружаем переменные из .env (только при локальной разработке)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная BOT_TOKEN не задана! Проверьте файл .env или настройки хостинга.")

bot = Bot(token=BOT_TOKEN)

class SupportStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_question = State()
    waiting_for_phone_type = State()
    waiting_for_screen_phone = State()

dp = Dispatcher(storage=MemoryStorage())

# === Настройки времени для отзыва ===
REVIEW_DELAY = timedelta(minutes=40)
last_interaction = {}  # user_id → datetime
review_sent = set()    # user_id, которым уже отправлен запрос

def update_last_interaction(user_id: int):
    """Обновляет время последнего взаимодействия и сбрасывает флаг отзыва при новом обращении."""
    last_interaction[user_id] = datetime.now()
    if user_id in review_sent:
        review_sent.discard(user_id)

# === КЛАВИАТУРЫ ===

def get_product_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Carlinkit 5.0", callback_data="product:cl5")],
        [InlineKeyboardButton(text="Carlinkit 5.0 mini pro", callback_data="product:cl5_mini")],
        [InlineKeyboardButton(text="Экран с CarPlay/AA", callback_data="product:screen")]
    ])

def get_cl5_questions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Инструкция по подключению", callback_data="q:connect")],
        [InlineKeyboardButton(text="Обновление прошивки", callback_data="q:firmware")],
        [InlineKeyboardButton(text="Частые вопросы", callback_data="q:faq")],
        [InlineKeyboardButton(text="Нестабильное соединение с адаптером", callback_data="q:unstable")],
        [InlineKeyboardButton(text="Другое", callback_data="q:other")],
        [InlineKeyboardButton(text="🔙 Назад к выбору товара", callback_data="back_to_products")]
    ])

def get_screen_questions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Инструкция по подключению", callback_data="q:screen_connect")],
        [InlineKeyboardButton(text="Частые вопросы", callback_data="q:screen_faq")],
        [InlineKeyboardButton(text="Другое", callback_data="q:screen_other")],
        [InlineKeyboardButton(text="🔙 Назад к выбору товара", callback_data="back_to_products")]
    ])

def get_screen_faq_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_screen_menu")],
        [InlineKeyboardButton(text="❓ Другой вопрос", callback_data="q:screen_other_from_faq")],
        [InlineKeyboardButton(text="📦 Возврат товара", url="https://t.me/GadgetGrad_Official")]
    ])

def get_screen_phone_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 iPhone", callback_data="screen_phone:iphone")],
        [InlineKeyboardButton(text="🤖 Android", callback_data="screen_phone:android")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_screen_menu")]
    ])

def get_back_to_screen_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_screen_menu")]
    ])

def get_faq_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_cl5_menu")],
        [InlineKeyboardButton(text="❓ Другой вопрос", callback_data="q:other_from_faq")]
    ])

def get_back_to_cl5_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_cl5_menu")],
        [InlineKeyboardButton(text="📦 Возврат товара", url="https://t.me/GadgetGrad_Official")]
    ])

def get_firmware_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_cl5_menu")]
    ])

def get_phone_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 iPhone", callback_data="phone:iphone")],
        [InlineKeyboardButton(text="🤖 Android", callback_data="phone:android")],
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_cl5_menu")]
    ])

def get_os_response_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="back_to_cl5_menu")]
    ])

def get_other_questions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Написать в поддержку", url="https://t.me/GadgetGrad_Official")],
        [InlineKeyboardButton(text="🔙 Назад к выбору товара", callback_data="back_to_products")]
    ])


# === ОБРАБОТЧИКИ ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    update_last_interaction(message.from_user.id)
    await message.answer(
        "👋 Здравствуйте! Это техническая поддержка GadgetGrad.\n\n"
        "Пожалуйста, выберите товар, по которому у вас возник вопрос:",
        reply_markup=get_product_keyboard()
    )
    await state.set_state(SupportStates.waiting_for_product)


@dp.callback_query(lambda c: c.data.startswith("product:"), SupportStates.waiting_for_product)
async def product_chosen(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    product_code = callback.data.split(":")[1]
    product_names = {
        "cl5": "Carlinkit 5.0",
        "cl5_mini": "Carlinkit 5.0 mini pro",
        "screen": "Экран с CarPlay/AA"
    }
    product_name = product_names.get(product_code, "Неизвестный товар")
    await state.update_data(chosen_product=product_name, product_code=product_code)

    if product_code in ("cl5", "cl5_mini"):
        kb = get_cl5_questions_kb()
        await state.set_state(SupportStates.waiting_for_question)
    elif product_code == "screen":
        kb = get_screen_questions_kb()
        await state.set_state(SupportStates.waiting_for_question)
    else:
        kb = get_other_questions_kb()

    await callback.message.edit_text(
        f"Вы выбрали: *{product_name}*\n\nВыберите ваш вопрос:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


# === ОБРАБОТЧИКИ ДЛЯ ЭКРАНА ===

@dp.callback_query(lambda c: c.data == "q:screen_connect", SupportStates.waiting_for_question)
async def screen_connect(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    await callback.message.edit_text(
        "📱 *Какой у вас смартфон?*",
        reply_markup=get_screen_phone_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(SupportStates.waiting_for_screen_phone)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "q:screen_other", SupportStates.waiting_for_question)
async def screen_other(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    data = await state.get_data()
    product = data.get("chosen_product", "Экран с CarPlay/AA")
    await callback.message.edit_text(
        f"📩 Пожалуйста, напишите нам напрямую: [GadgetGrad Support](https://t.me/GadgetGrad_Official)\n\n"
        f"🔹 Укажите, что ваш вопрос по товару: **{product} → Другое**",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(lambda c: c.data == "q:screen_faq", SupportStates.waiting_for_question)
async def screen_faq(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    text = (
        "❓ *Частые вопросы*\n\n"
        "1. *Вы недовольны доставкой?*\n"
        "Мы отправляем товар в новой упаковке, но повреждения при транспортировке — вне нашего контроля (доставкой управляет маркетплейс).\n"
        "❗ Не оставляйте негативный отзыв — напишите в поддержку маркетплейса: *Профиль → Чаты → Поддержка*.\n\n"
        "2. *Почему не появляется изображение на экране?*\n"
        "– Убедитесь, что выбран правильный режим: **CarPlay** для iPhone, **Android Auto** для Android.\n\n"
        "3. *Можно ли скачать дополнительные приложения?*\n"
        "– Нет, дополнительные приложения скачать нельзя.\n\n"
        "4. *Яндекс Навигатор требует подписку?*\n"
        "– Да, для работы в CarPlay/Android Auto требуется **Яндекс Плюс**.\n"
        "Подробнее: [yandex.ru/project/maps/auto/android-auto_non-plus](https://yandex.ru/project/maps/auto/android-auto_non-plus/)\n"
        "Альтернатива: Google Карты или 2ГИС.\n\n"
        "5. *Есть ли на экране русский язык?*\n"
        "– Да. Зайдите в настройки (шестерёнка внизу слева) → **Language** → выберите **Русский**.\n"
        "⚠️ Перевод пока не идеален, но мы работаем над улучшением.\n\n"
        "6. *Есть ли GPS?*\n"
        "– Нет. Навигация работает **только через CarPlay и Android Auto**.\n"
        "Подробнее:\n"
        "• [CarPlay](https://www.apple.com/ios/carplay/)\n"
        "• [Android Auto](https://www.android.com/intl/ru_ru/auto/)\n\n"
        "7. *Можно ли скачать карты на Экран?*\n"
        "– Нет, это не классический навигатор. Навигация — только через CarPlay/Android Auto.\n"
        "Подробнее:\n"
        "• [CarPlay](https://www.apple.com/ios/carplay/)\n"
        "• [Android Auto](https://www.android.com/intl/ru_ru/auto/)\n\n"
        "8. *Можно ли использовать без AUX-кабеля?*\n"
        "– Да, если ваше головное устройство поддерживает **Bluetooth-аудио**. Подключите телефон к экрану (для CarPlay/AA) и к ГУ (для звука)."
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=False,
        reply_markup=get_screen_faq_kb()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "q:screen_other_from_faq")
async def screen_other_from_faq(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    data = await state.get_data()
    product = data.get("chosen_product", "Экран с CarPlay/AA")
    await callback.message.edit_text(
        f"📩 Пожалуйста, напишите нам напрямую: [GadgetGrad Support](https://t.me/GadgetGrad_Official)\n\n"
        f"🔹 Укажите, что ваш вопрос по товару: **{product} → Частые вопросы → Другой вопрос**",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(
    SupportStates.waiting_for_screen_phone,
    lambda c: c.data in ("screen_phone:iphone", "screen_phone:android")
)
async def screen_phone_chosen(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    phone = callback.data
    if phone == "screen_phone:iphone":
        text = (
            "📄 *Инструкция по подключению к Экрану iPhone*\n\n"
            "1. Подключите питание экрана в прикуриватель;\n"
            "2. Подключите экран по AUX к вашему головному устройству (мультимедийной системе);\n"
            "3. На экране выберите **CarPlay**;\n"
            "4. Включите на вашем iPhone Bluetooth и подключите к экрану `CAR-XTD-BT_****`;\n"
            "5. При необходимости дайте необходимые разрешения на вашем iPhone (это необходимо при первом использовании CarPlay);\n"
            "6. Дождитесь подключения.\n\n"
            "💡 *Лайфхак!*\n"
            "Если в головном устройстве на вашем авто есть Bluetooth, вы можете **не подключать AUX-кабель**. Просто подключите телефон к экрану (для CarPlay) и к головному устройству (для звука) — сможете воспроизводить музыку через штатные колонки, а управлять треками — с экрана."
        )
    elif phone == "screen_phone:android":
        text = (
            "📄 *Инструкция по подключению к Экрану Android смартфона*\n\n"
            "1. Подключите питание экрана в прикуриватель;\n"
            "2. Подключите экран по AUX к вашему головному устройству (мультимедийной системе);\n"
            "3. На экране выберите **Android Auto**;\n"
            "4. Включите на вашем смартфоне Bluetooth и подключите к экрану `CAR-XTD-BT_****`;\n"
            "5. При необходимости дайте необходимые разрешения на вашем смартфоне (это необходимо при первом использовании Android Auto);\n"
            "6. Дождитесь подключения.\n\n"
            "💡 *Лайфхак!*\n"
            "Если в головном устройстве на вашем авто есть Bluetooth, вы можете **не подключать AUX-кабель**. Просто подключите телефон к экрану (для Android Auto) и к головному устройству (для звука) — сможете воспроизводить музыку через штатные колонки, а управлять треками — с экрана."
        )
    else:
        text = "Неизвестный тип устройства."

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_back_to_screen_kb())
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back_to_screen_menu")
async def back_to_screen_menu(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    product_data = await state.get_data()
    product_code = product_data.get("product_code", "screen")
    product_name = "Экран с CarPlay/AA"
    await state.update_data(chosen_product=product_name, product_code=product_code)
    await callback.message.edit_text(
        f"Вы выбрали: *{product_name}*\n\nВыберите ваш вопрос:",
        reply_markup=get_screen_questions_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(SupportStates.waiting_for_question)
    await callback.answer()


# === СТАРЫЕ ОБРАБОТЧИКИ (CL5 / CL5 Mini) ===

@dp.callback_query(lambda c: c.data == "q:other_from_faq")
async def other_from_faq(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    data = await state.get_data()
    product = data.get("chosen_product", "неизвестный товар")
    await callback.message.edit_text(
        f"📩 Пожалуйста, напишите нам напрямую: [GadgetGrad Support](https://t.me/GadgetGrad_Official)\n\n"
        f"🔹 Укажите, что ваш вопрос по товару: **{product} → Частые вопросы → Другой вопрос**",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(
    SupportStates.waiting_for_question,
    lambda c: not c.data.startswith("back_to_") and c.data not in ("q:other_from_faq", "q:screen_connect", "q:screen_faq", "q:screen_other", "q:screen_other_from_faq")
)
async def question_chosen(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    data = callback.data
    product_data = await state.get_data()
    product_code = product_data.get("product_code")
    chosen_product = product_data.get("chosen_product", "Carlinkit")

    if data == "q:other":
        await callback.message.edit_text(
            f"📩 Пожалуйста, напишите нам напрямую: [GadgetGrad Support](https://t.me/GadgetGrad_Official)\n\n"
            f"🔹 Укажите, что ваш вопрос по товару: **{chosen_product} → Другое**",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await state.clear()
        await callback.answer()
        return

    if product_code in ("cl5", "cl5_mini"):
        if data == "q:connect":
            if product_code == "cl5":
                text = (
                    "📄 *Инструкция по подключению Carlinkit 5.0*\n\n"
                    "1. Подключите адаптер через USB-порт к вашему автомобилю;\n"
                    "2. Подключитесь к Wi-Fi адаптера (имя – `AutoKit_***`), пароль `12345678`;\n"
                    "3. Подключитесь по Bluetooth к адаптеру (имя – `AutoKit_***`);\n"
                    "4. Дождитесь подключения и наслаждайтесь CarPlay (если у вас iPhone) и Android Auto (если у вас Android смартфон).\n\n"
                    "💡 *Индикация адаптера:*\n"
                    "• Адаптер горит красным – смартфон не подключен;\n"
                    "• Адаптер горит зелёным или синим – смартфон подключён.\n\n"
                    "⚠️ *Если подключить не удалось, необходимо проверить следующее:*\n"
                    "• Если у вас iPhone — версия операционной системы должна быть **iOS 10.0 и выше**;\n"
                    "• Если у вас Android — версия операционной системы должна быть **Android 11.0 и выше**;\n"
                    "• Совместимость с авто: подключите телефон **проводом к автомобилю**. Если у вас активировался интерфейс Android Auto или CarPlay — значит, адаптер вам подходит. Если нет — адаптер вам не подходит.\n\n"
                    "📦 *Возврат*\n"
                    "Согласно Закону РФ от 07.02.1992 № 2300-1 (ред. от 07.07.2025) «О защите прав потребителей»:\n"
                    "1. Вы вправе оформить возврат товара надлежащего качества в течение **четырнадцати дней**, не считая дня его покупки;\n"
                    "2. Возврат возможен, если сохранены **товарный вид** и **потребительские свойства**.\n\n"
                    "Таким образом, если товар вам не подходит и у вас сохранилась упаковка в целости и сохранности (не порвана), а также не утеряна комплектация товара, вы можете аккуратно сложить всё в коробку и согласовать возврат с сотрудником магазина. Для создания заявки на возврат выберите пункт «Возврат товара», опишите причину возврата и пришлите фото полной комплектации — дальше сотрудник вас проконсультирует."
                )
            else:  # cl5_mini
                text = (
                    "📄 *Инструкция по подключению Carlinkit 5.0 mini pro*\n\n"
                    "1. Подключите адаптер через USB-порт к вашему автомобилю;\n"
                    "2. Подключитесь к Wi-Fi адаптера (имя – `VehiConn_***`), пароль `12345678`;\n"
                    "3. Подключитесь по Bluetooth к адаптеру (имя – `VehiConn_***`);\n"
                    "4. Дождитесь подключения и наслаждайтесь CarPlay (если у вас iPhone) и Android Auto (если у вас Android смартфон).\n\n"
                    "⚠️ *Если подключить не удалось, необходимо проверить следующее:*\n"
                    "• Если у вас iPhone — версия операционной системы должна быть **iOS 10.0 и выше**;\n"
                    "• Если у вас Android — версия операционной системы должна быть **Android 11.0 и выше**;\n"
                    "• Совместимость с авто: подключите телефон **проводом к автомобилю**. Если активировался интерфейс Android Auto или CarPlay — значит, адаптер вам подходит. Если нет — адаптер вам не подходит.\n\n"
                    "📦 *Возврат*\n"
                    "Согласно Закону РФ от 07.02.1992 № 2300-1 (ред. от 07.07.2025) «О защите прав потребителей»:\n"
                    "1. Вы вправе оформить возврат товара надлежащего качества в течение **четырнадцати дней**, не считая дня его покупки;\n"
                    "2. Возврат товара надлежащего качества возможен, если сохранены его **товарный вид** и **потребительские свойства**.\n\n"
                    "Таким образом, если товар вам не подходит и прошло меньше 14 дней с момента покупки, вы можете аккуратно сложить всё в коробку и согласовать возврат с сотрудником магазина. Для создания заявки на возврат выберите пункт «Возврат товара», опишите причину возврата и пришлите фото полной комплектации — дальше сотрудник вас проконсультирует."
                )

            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_back_to_cl5_kb())

        elif data == "q:firmware":
            if product_code == "cl5":
                text = ("🔄 *Инструкция по обновлению Carlinkit 5.0*\n\n"
                        "1. Подключите смартфон к адаптеру;\n"
                        "2. Зайдите в браузер и в адресной строке наберите IP-адрес: `192.168.0.50`;\n"
                        "3. Нажмите «Help» и пролистайте вниз;\n"
                        "4. Нажмите «Check update»;\n"
                        "5. Дождитесь установки обновления.")
            else:  # cl5_mini
                text = ("🔄 *Инструкция по обновлению Carlinkit 5.0 mini pro*\n\n"
                        "1. Подключите смартфон к адаптеру;\n"
                        "2. Зайдите в браузер и в адресной строке наберите IP-адрес: `192.168.50.100`;\n"
                        "3. Пролистайте вниз;\n"
                        "4. Выберите версию «CP and AA two in one» и нажмите **Обновить**;\n"
                        "5. Дождитесь установки обновления.")

            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_firmware_kb())

        elif data == "q:faq":
            text = (
                "❓ *Частые вопросы*\n\n"
                
                "*1. Недовольны доставкой?*\n"
                "Мы отправляем товар в новой упаковке, но повреждения при транспортировке — вне нашего контроля (доставкой управляет маркетплейс).\n"
                "❗ Не оставляйте негативный отзыв — напишите в поддержку маркетплейса: *Профиль → Чаты → Поддержка*.\n\n"
                
                "*2. Можно ли смотреть видео через Carlinkit?*\n"
                "Нет. Доступны только стандартные функции CarPlay и Android Auto.\n"
                "• [Android Auto](https://www.android.com/intl/ru_ru/auto/)\n"
                "• [CarPlay](https://www.apple.com/ios/carplay/)\n\n"
                
                "*3. Можно ли установить дополнительные приложения?*\n"
                "Нет, установка сторонних приложений невозможна.\n\n"
                
                "*4. Почему Яндекс Навигатор требует подписку?*\n"
                "Это требование Яндекса: для работы в CarPlay/Android Auto нужна подписка *Яндекс Плюс*.\n"
                "Подробнее: [yandex.ru/project/maps/auto/android-auto_non-plus](https://yandex.ru/project/maps/auto/android-auto_non-plus/)\n"
                "Альтернатива: Google Карты или 2ГИС — работают без подписки.\n\n"
                
                "*5. Работает ли адаптер, если в ГУ установить AutoKit.apk?*\n"
                "Нет. Адаптер работает **только** с автомобилями, где CarPlay/Android Auto предустановлены с завода.\n\n"
                
                "*6. У меня Android, а в авто только CarPlay (или наоборот). Подключится ли адаптер?*\n"
                "Нет. Carlinkit не конвертирует протоколы:\n"
                "• iPhone → только CarPlay\n"
                "• Android → только Android Auto\n\n"
                
                "*7. Звук отстаёт от видео при воспроизведении?*\n"
                "Да, это особенность всех беспроводных адаптеров. На данный момент проблема не решена, но разработчики работают над улучшениями.\n\n"
                
                "*8. Что означает индикация на адаптере?*\n"
                "• 🔴 Красный — смартфон не подключён\n"
                "• 🟢 Зелёный / синий — смартфон подключён"
            )
            await callback.message.edit_text(
                text,
                parse_mode="Markdown",
                disable_web_page_preview=False,
                reply_markup=get_faq_kb()
            )

        elif data == "q:unstable":
            await callback.message.edit_text(
                "📱 *Какой у вас смартфон?*",
                reply_markup=get_phone_type_kb(),
                parse_mode="Markdown"
            )
            await state.set_state(SupportStates.waiting_for_phone_type)

    else:
        await callback.message.edit_text(
            "Спасибо! Наш специалист скоро свяжется с вами.",
            reply_markup=get_product_keyboard()
        )
    await callback.answer()


@dp.callback_query(
    SupportStates.waiting_for_phone_type,
    lambda c: c.data in ("phone:iphone", "phone:android")
)
async def phone_type_chosen(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    phone = callback.data
    product_data = await state.get_data()
    product_code = product_data.get("product_code")

    if product_code == "cl5_mini":
        if phone == "phone:iphone":
            text = ("📱 *Для iPhone (Carlinkit 5.0 mini pro):*\n\n"
                    "1. Проверьте VPN: если включен — может мешать работе;\n"
                    "2. Забудьте Bluetooth-соединение с автомобилем — тоже может некорректно активировать интерфейс CarPlay;\n"
                    "3. Удалите в Bluetooth и Wi-Fi подключение к адаптеру Carlinkit;\n"
                    "4. Зайдите в настройки, в поиске наберите *CarPlay*, удалите все существующие подключения CarPlay;\n"
                    "5. Подключите адаптер заново (по Wi-Fi и Bluetooth). После этих манипуляций интерфейс CarPlay должен отобразиться на ГУ. После этого сможете подключаться без провода.")
        elif phone == "phone:android":
            text = ("🤖 *Для Android (Carlinkit 5.0 mini pro):*\n\n"
                    "1. Проверьте VPN: если включен — может мешать работе;\n"
                    "2. Забудьте Bluetooth-соединение с автомобилем — тоже может некорректно активировать интерфейс Android Auto;\n"
                    "3. Удалите в Bluetooth и Wi-Fi подключение к экрану;\n"
                    "4. Зайдите в настройки, в поиске наберите *Android Auto*, удалите все существующие подключения Android Auto;\n"
                    "5. Зайдите в Wi-Fi — создайте новое подключение по Wi-Fi с адаптером;\n"
                    "6. Зайдите в Bluetooth — создайте новое подключение с адаптером. После этих манипуляций интерфейс Android Auto должен отобразиться на ГУ. После этого сможете подключаться без провода и сбоев.")
        else:
            text = "Неизвестный тип устройства."
    else:
        if phone == "phone:iphone":
            text = ("📱 *Для iPhone:*\n\n"
                    "1. Проверьте VPN: если включен — может мешать работе;\n"
                    "2. Забудьте Bluetooth-соединение с автомобилем — тоже может некорректно активировать интерфейс CarPlay;\n"
                    "3. Удалите в Bluetooth и Wi-Fi подключение к адаптеру Carlinkit;\n"
                    "4. Зайдите в настройки, в поиске наберите *CarPlay*, удалите все существующие подключения CarPlay;\n"
                    "5. Подключите адаптер проводом к автомобилю, затем телефон проводом к адаптеру (через 2-е гнездо).\n\n"
                    "После этих манипуляций интерфейс CarPlay должен отобразиться на ГУ. После этого сможете подключаться без провода.")
        elif phone == "phone:android":
            text = ("🤖 *Для Android:*\n\n"
                    "1. Проверьте VPN: если включен — может мешать работе;\n"
                    "2. Забудьте Bluetooth-соединение с автомобилем — тоже может некорректно активировать интерфейс Android Auto;\n"
                    "3. Удалите в Bluetooth и Wi-Fi подключение к экрану;\n"
                    "4. Зайдите в настройки, в поиске наберите *Android Auto*, удалите все существующие подключения Android Auto;\n"
                    "5. Зайдите в Wi-Fi — создайте новое подключение по Wi-Fi с адаптером;\n"
                    "6. Зайдите в Bluetooth — создайте новое подключение с адаптером.\n\n"
                    "После этих манипуляций интерфейс Android Auto должен отобразиться на ГУ. После этого сможете подключаться без провода и сбоев.")
        else:
            text = "Неизвестный тип устройства."

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_os_response_kb())
    await state.set_state(SupportStates.waiting_for_question)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back_to_products")
async def back_to_products(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(
        "👋 Здравствуйте! Это техническая поддержка GadgetGrad.\n\n"
        "Пожалуйста, выберите товар, по которому у вас возник вопрос:",
        reply_markup=get_product_keyboard()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back_to_cl5_menu")
async def back_to_cl5_menu(callback: types.CallbackQuery, state: FSMContext):
    update_last_interaction(callback.from_user.id)
    product_data = await state.get_data()
    product_code = product_data.get("product_code", "cl5")
    product_name = "Carlinkit 5.0" if product_code == "cl5" else "Carlinkit 5.0 mini pro"
    await state.update_data(chosen_product=product_name, product_code=product_code)
    await callback.message.edit_text(
        f"Вы выбрали: *{product_name}*\n\nВыберите ваш вопрос:",
        reply_markup=get_cl5_questions_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(SupportStates.waiting_for_question)
    await callback.answer()


@dp.message()
async def unknown_message(message: types.Message, state: FSMContext):
    update_last_interaction(message.from_user.id)
    current_state = await state.get_state()
    if current_state == SupportStates.waiting_for_product:
        await message.answer(
            "Пожалуйста, выберите товар, используя кнопки ниже.",
            reply_markup=get_product_keyboard()
        )
    elif current_state == SupportStates.waiting_for_question:
        product_data = await state.get_data()
        product_code = product_data.get("product_code")
        if product_code == "screen":
            kb = get_screen_questions_kb()
        else:
            kb = get_cl5_questions_kb() if product_code in ("cl5", "cl5_mini") else get_other_questions_kb()
        await message.answer(
            "Пожалуйста, выберите вопрос из меню.",
            reply_markup=kb
        )
    elif current_state == SupportStates.waiting_for_phone_type:
        await message.answer(
            "Пожалуйста, укажите тип вашего смартфона, используя кнопки ниже.",
            reply_markup=get_phone_type_kb()
        )
    elif current_state == SupportStates.waiting_for_screen_phone:
        await message.answer(
            "Пожалуйста, укажите тип вашего смартфона, используя кнопки ниже.",
            reply_markup=get_screen_phone_kb()
        )
    else:
        await message.answer(
            "Я бот технической поддержки GadgetGrad 🛠️\n"
            "Чтобы начать, отправьте команду /start."
        )


# === ФОНОВЫЕ ЗАДАЧИ ===

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # читаем из .env

async def heartbeat_monitor(bot: Bot):
    """Отправляет сообщение раз в час, чтобы подтвердить, что бот работает."""
    while True:
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Техподдержка работает!")
        except Exception as e:
            logging.warning(f"[HEARTBEAT ERROR] Не удалось отправить сообщение: {e}")
        await asyncio.sleep(3600)  # 1 час


async def review_scheduler(bot: Bot):
    """Проверяет пользователей и отправляет запрос на отзыв через 40 минут бездействия."""
    while True:
        now = datetime.now()
        to_remove = []
        for user_id, last_time in list(last_interaction.items()):
            if user_id not in review_sent and now - last_time >= REVIEW_DELAY:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            "🙏 Спасибо, что обратились в поддержку **GadgetGrad**!\n"
                            "Мы очень старались помочь вам — и очень надеемся, что у нас это получилось.\n\n"
                            "Если вы остались довольны — не могли бы вы уделить пару минут и [оставить 5 звёзд на Wildberries](https://www.wildberries.ru/lk/myorders/archive)?\n"
                            "Ваш отзыв помогает другим покупателям уверенно выбирать технику, а нам — продолжать стараться ещё лучше 🌟🌟🌟🌟🌟\n\n"
                            "С благодарностью,\n"
                            "Команда **GadgetGrad**"
                        ),
                        parse_mode="Markdown"
                    )
                    review_sent.add(user_id)
                except Exception as e:
                    logging.warning(f"Не удалось отправить запрос на отзыв пользователю {user_id}: {e}")
                to_remove.append(user_id)
        for uid in to_remove:
            last_interaction.pop(uid, None)
        await asyncio.sleep(60)  # проверка раз в минуту


# === ЗАПУСК ===

async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Бот запущен!")
    asyncio.create_task(heartbeat_monitor(bot))
    asyncio.create_task(review_scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())