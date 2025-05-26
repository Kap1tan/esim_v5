# handlers/questions.py

from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards.inline import get_questions_keyboard, get_qa_back_keyboard, get_feedback_keyboard
from texts import TEXTS
from texts import QA_ITEMS

router = Router()


@router.callback_query(F.data == "questions")
async def show_questions(callback: CallbackQuery):
    """Показать меню вопросов и ответов"""
    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["questions"],
                reply_markup=get_questions_keyboard()
            )
        else:
            await callback.message.edit_text(
                text=TEXTS["questions"],
                reply_markup=get_questions_keyboard()
            )
    except Exception:
        await callback.message.answer(
            text=TEXTS["questions"],
            reply_markup=get_questions_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("qa_"))
async def show_answer(callback: CallbackQuery):
    """Показать ответ на выбранный вопрос"""
    qa_key = callback.data.replace("qa_", "")

    if qa_key in QA_ITEMS:
        qa_item = QA_ITEMS[qa_key]
        answer_text = f"❓ {qa_item['text']}\n\n{qa_item['answer']}\n\n{TEXTS['feedback_question']}"

        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    text=answer_text,
                    reply_markup=get_feedback_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text=answer_text,
                    reply_markup=get_feedback_keyboard()
                )
        except Exception:
            await callback.message.answer(
                text=answer_text,
                reply_markup=get_feedback_keyboard()
            )

    await callback.answer()