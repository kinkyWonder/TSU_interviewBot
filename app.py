import os
import re
import json
import logging
import urllib3
from flask import Flask, render_template, request, jsonify
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Настройка логирования
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/gigachat.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ==========================================
# КОНФИГУРАЦИЯ GIGACHAT
# ==========================================
AUTH_KEY = "apikey"
MODEL_NAME = "GigaChat-3-Ultra"  # Единая модель для всех задач

gc_client = GigaChat(
    credentials=AUTH_KEY,
    scope="GIGACHAT_API_PERS",
    verify_ssl_certs=False
)

def ask_gigachat(sys_prompt: str, user_text: str, model_name: str) -> str:
    """Отправка запроса в GigaChat."""
    logging.info(f"--- ЗАПРОС К {model_name} ---")
    
    try:
        chat = Chat(
            model=model_name,
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=sys_prompt),
                Messages(role=MessagesRole.USER, content=user_text)
            ]
        )
        response = gc_client.chat(chat)
        result = response.choices[0].message.content
        logging.info(f"--- ОТВЕТ ОТ {model_name} ---\n{result}\n")
        return result
    except Exception as e:
        logging.error(f"[ОШИБКА API]: {e}\n")
        return ""

def process_evaluation_text(text: str) -> tuple[int, str]:
    match = re.search(r'(?:Оценка|оценка|Балл|балл).*?(\d+)(?:\s*/\s*10)?', text)
    score = int(match.group(1)) if match else 0
    
    lines = text.split('\n')
    clean_lines = [line for line in lines if not re.search(r'(?:Оценка|оценка|Балл|балл).*?\d+', line)]
    return score, '\n'.join(clean_lines).strip()

def format_markdown_to_html(text: str) -> str:
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

# ==========================================
# МАРШРУТЫ API
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    specialty = data.get('specialty', 'Искусственный интеллект и большие данные')
    difficulty = data.get('difficulty', 'standard')
    
    diff_text = "Продвинутый уровень (6-9 вопросов). Упор на глубокое понимание архитектуры и оптимизацию." if difficulty == 'advanced' else "Стандартный уровень (7-9 вопросов). От базовых понятий к рабочим задачам."

    sys_prompt = "Ты Senior IT-специалист, составляющий вопросы для технического собеседования."
    user_prompt = (
        f"Напиши вопросы для собеседования на позицию: {specialty}. Уровень: {diff_text}\n"
        "Вопросы должны усложняться от первого к последнему. "
        "Верни ответ СТРОГО в формате JSON: {\"questions\": [\"вопрос 1\", \"вопрос 2\"]} без лишнего текста и форматирования."
    )
    
    raw_text = ask_gigachat(sys_prompt, user_prompt, MODEL_NAME)
    
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group(0)).get("questions", [])
            if not questions: raise ValueError("Пустой список вопросов")
        else:
            raise ValueError("JSON блок не найден")
    except Exception as e:
        logging.warning(f"Ошибка парсинга JSON: {e}. Используем fallback regex.")
        questions = re.findall(r'^\s*(?:\*\*)?\d+\.(?:\*\*)?\s*(.+)', raw_text, flags=re.MULTILINE)
    
    return jsonify({"questions": questions[:9]})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    data = request.json
    q = data.get('question')
    a = data.get('answer', '').strip()
    
    if not a or a == '-':
        return jsonify({"feedback": "Ответ не предоставлен.", "score": 0})
    
    sys_prompt = (
        "Ты строгий, но объективный технический интервьюер. Оценивай ответ кандидата сухо и по факту. "
        "Если кандидат использует альтернативный, но рабочий подход, засчитай это как плюс. "
        "Не будь излишне мягким и не хвали просто за попытку ответить."
    )
    user_prompt = (
        f"Вопрос: '{q}'\nОтвет: '{a}'\n\n"
        "Краткая оценка. Структура:\n"
        "1. Что верно.\n"
        "2. Что неверно.\n"
        "3. Чего не хватает.\n"
        "Строго запрещено объяснять теорию или писать развернутые лекции.\n"
        "В самом конце с новой строки напиши 'Оценка: X/10' (где X — балл от 0 до 10)."
    )
    
    raw_feedback = ask_gigachat(sys_prompt, user_prompt, MODEL_NAME)
    score, clean_feedback = process_evaluation_text(raw_feedback)
    
    return jsonify({
        "feedback": format_markdown_to_html(clean_feedback), 
        "score": score
    })

@app.route('/api/summary', methods=['POST'])
def summary():
    data = request.json
    scores = data.get('scores', [])
    specialty = data.get('specialty', '')
    
    # ПРОВЕРКА НА ОТСУТСТВИЕ ОТВЕТОВ:
    # Если массив пустой или сумма всех баллов равна нулю
    if not scores or sum(scores) == 0:
        return jsonify({
            "chance": "0",
            "summary": "Вы не предоставили ни одного ответа.",
            "mentor_prompt": "" # Возвращаем пустую строку, чтобы скрыть кнопку на клиенте
        })

    max_possible = len(scores) * 10
    total_score = sum(scores)
    chance_calculated = int((total_score / max_possible) * 100) if max_possible > 0 else 0
    
    sys_prompt = "Ты IT-лид, предоставляющий официальный фидбек после собеседования. Тон: профессиональный."
    user_prompt = (
        f"Кандидат ('{specialty}') набрал {total_score} из {max_possible} возможных баллов. Оценки по каждому ответу: {scores}.\n\n"
        "1. Напиши общее резюме собеседования. Сначала немного похвали кандидата, а затем укажи минусы и зоны для роста.\n"
        "2. Составь готовый промпт от лица кандидата для AI-ментора, чтобы кандидат мог скопировать его и попросить ментора помочь закрыть пробелы. Промпт должен начинаться с 'Действуй как Senior-разработчик...' и учитывать конкретные слабые стороны.\n"
        "Формат ответа СТРОГО такой:\n"
        "Резюме: [твое резюме]\n"
        "Промпт: [сгенерированный промпт]"
    )
    
    raw_summary = ask_gigachat(sys_prompt, user_prompt, MODEL_NAME)
    
    resume_match = re.search(r'Резюме:\s*(.*?)(?=Промпт:|$)', raw_summary, flags=re.IGNORECASE | re.DOTALL)
    prompt_match = re.search(r'Промпт:\s*(.+)', raw_summary, flags=re.IGNORECASE | re.DOTALL)
    
    resume_text = resume_match.group(1).strip() if resume_match else raw_summary
    mentor_prompt = prompt_match.group(1).strip() if prompt_match else "Привет! Помоги мне составить план подготовки к собеседованию."
    
    return jsonify({
        "chance": str(chance_calculated),
        "summary": format_markdown_to_html(resume_text),
        "mentor_prompt": mentor_prompt
    })

if __name__ == '__main__':
    app.run(debug=True)