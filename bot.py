import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '7814014008:AAHXEAuNW5RP7AUbS2CUdgdNglXJKE82aCw'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def convert_pdf_to_images(pdf_file):
    """
    Конвертирует PDF в изображения.
    """
    try:
        doc = fitz.open(pdf_file)
        images = []
        for page_num in range(len(doc)):
            pix = doc[page_num].get_pixmap(dpi=150)
            img_path = f"temp_page_{os.path.basename(pdf_file)}_{page_num}.png"
            pix.save(img_path)
            images.append(img_path)
        return images
    except Exception as e:
        logger.error(f"Ошибка при конвертации PDF в изображения: {e}")
        return []

def arrange_pdfs_on_one_page(pdf_files, output_file="merged_one_page.pdf", columns=2):
    """
    Размещает страницы из всех PDF на одной странице, сохраняя пропорции изображений.
    """
    page_width, page_height = A4  # Размер страницы A4
    images = []

    # Конвертируем страницы всех PDF в изображения
    for pdf_file in pdf_files:
        images.extend(convert_pdf_to_images(pdf_file))

    if not images:
        raise ValueError("Не удалось обработать файлы PDF")

    c = canvas.Canvas(output_file, pagesize=A4)

    x_offset = 0
    y_offset = page_height
    max_cell_height = 0

    for i, img_path in enumerate(images):
        # Загружаем изображение для определения его размеров
        with fitz.open(img_path) as img_doc:
            img_width, img_height = img_doc[0].rect.width, img_doc[0].rect.height

        # Масштабируем изображение, чтобы оно вписалось в колонку
        scale = min(page_width / columns / img_width, page_height / img_height)
        new_width = img_width * scale
        new_height = img_height * scale

        # Проверяем необходимость переноса на следующую строку
        if x_offset + new_width > page_width:
            x_offset = 0
            y_offset -= max_cell_height
            max_cell_height = 0

        # Если следующая строка выходит за границы страницы, создаём новую страницу
        if y_offset - new_height < 0:
            c.showPage()
            y_offset = page_height
            max_cell_height = 0

        # Рисуем изображение на текущей позиции
        c.drawImage(img_path, x_offset, y_offset - new_height, width=new_width, height=new_height)

        # Обновляем позиции
        x_offset += new_width
        max_cell_height = max(max_cell_height, new_height)

    c.save()

    # Удаляем временные изображения
    for img_path in images:
        if os.path.exists(img_path):
            os.remove(img_path)

    return output_file

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Добро пожаловать! Отправьте два PDF файла, и я размещу их на одной странице.")

@dp.message(lambda message: message.document is not None)
async def document_handler(message: Message, state: FSMContext):
    document = message.document
    file_name = document.file_name
    if not file_name.lower().endswith('.pdf'):
        await message.answer("Пожалуйста, отправьте только PDF файлы.")
        return

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{file_name}"
    await bot.download(document, file_path)
    logger.info(f"Файл {file_name} скачан в {file_path}")

    data = await state.get_data()
    pdf_files = data.get("pdf_files", [])
    pdf_files.append(file_path)
    await state.update_data(pdf_files=pdf_files)

    if len(pdf_files) == 2:
        await message.answer("Два файла получены. Обрабатываю...")
        try:
            merged_file = arrange_pdfs_on_one_page(pdf_files)
            await message.answer_document(FSInputFile(merged_file), caption="Ваш PDF файл готов.")
        except Exception as e:
            logger.error(f"Ошибка при обработке файлов: {e}")
            await message.answer("Произошла ошибка при обработке файлов.")
        finally:
            # Очищаем временные данные и файлы
            cleanup_files(pdf_files)
            if 'merged_file' in locals():
                cleanup_files([merged_file])
            await state.clear()
    else:
        await message.answer(f"Файл {file_name} получен. Всего файлов: {len(pdf_files)}.")

def cleanup_files(files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)
            logger.info(f"Удален временный файл: {file}")

async def main():
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())