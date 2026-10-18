import re
import json
import urllib3
from flask import Flask, render_template, request, jsonify
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Подавление предупреждений SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
AUTH_KEY = "key"
SMART_MODEL = "GigaChat-3-Ultra"
DUMB_MODEL = "GigaChat-Pro"

gc_client = GigaChat(
    credentials=AUTH_KEY,
    scope="GIGACHAT_API_PERS",
    verify_ssl_certs=False
)

def ask_gigachat(sys_prompt: str, user_text: str, model_name: str) -> str:
    try:
        chat = Chat(
            model=model_name,
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=sys_prompt),
                Messages(role=MessagesRole.USER, content=user_text)
            ]
        )
        response = gc_client.chat(chat)
        return response.choices[0].message.content
    except Exception as e:
        print(f"\n[ОШИБКА API]: {e}\n")
        return ""

def process_evaluation_text(text: str) -> tuple[int, str]:
    match = re.search(r'(?:Оценка|оценка|Балл|балл).*?(\d+)(?:\s*/\s*10)?', text)
    score = int(match.group(1)) if match else 0
    
    lines = text.split('\n')
    clean_lines = [line for line in lines if not re.search(r'(?:Оценка|оценка|Балл|балл).*?\d+', line)]
    clean_text = '\n'.join(clean_lines).strip()
    
    return score, clean_text

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
    
    # Настройка параметров сложности
    if difficulty == 'advanced':
        diff_text = "Продвинутый уровень (6-9 вопросов). Упор на глубокое понимание архитектуры, неочевидные кейсы и оптимизацию."
    else:
        diff_text = "Стандартный уровень (7-9 вопросов). От базовых понятий к рабочим задачам."

    sys_prompt = "Ты Senior IT-специалист, составляющий вопросы для технического собеседования."
    user_prompt = (
        f"Напиши вопросы для собеседования на позицию: {specialty}. "
        f"Уровень: {diff_text}\n"
        "Вопросы должны усложняться от первого к последнему. "
        "Верни ответ СТРОГО в формате JSON: {\"questions\": [\"вопрос 1\", \"вопрос 2\"]} без лишнего текста и форматирования."
    )
    
    raw_text = ask_gigachat(sys_prompt, user_prompt, SMART_MODEL)
    
    # Безопасный парсинг JSON с фолбэком на случай галлюцинаций модели
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            questions_data = json.loads(json_match.group(0))
            questions = questions_data.get("questions", [])
        else:
            raise ValueError("JSON блок не найден")
    except Exception as e:
        print(f"Ошибка парсинга JSON, использую запасной метод. Ошибка: {e}")
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
        "Ты строгий, но объективный технический интервьюер. "
        "Оценивай ответ кандидата сухо и исключительно по факту. "
        "Если кандидат использует альтернативный, но рабочий подход, засчитай это как плюс, а не как ошибку. "
        "При этом сохраняй профессиональную дистанцию, не будь излишне мягким и не хвали просто за попытку ответить."
    )
    user_prompt = (
        f"Вопрос: '{q}'\nОтвет: '{a}'\n\n"
        "Дай краткую оценку ответу. Структура:\n"
        "1. Что верно.\n"
        "2. Что неверно (или неточно).\n"
        "3. Чего не хватает.\n"
        "Строго запрещено объяснять теорию, давать правильный ответ или писать развернутые лекции.\n"
        "В самом конце с новой строки напиши 'Оценка: X/10' (где X — балл от 0 до 10)."
    )
    
    raw_feedback = ask_gigachat(sys_prompt, user_prompt, SMART_MODEL)
    score, clean_feedback = process_evaluation_text(raw_feedback)
    feedback_html = format_markdown_to_html(clean_feedback)
    
    return jsonify({"feedback": feedback_html, "score": score})

@app.route('/api/summary', methods=['POST'])
def summary():
    data = request.json
    scores = data.get('scores', [])
    specialty = data.get('specialty', '')
    
    # Строгий математический подсчет шанса (полностью на Python)
    max_possible = len(scores) * 10
    total_score = sum(scores)
    chance_calculated = int((total_score / max_possible) * 100) if max_possible > 0 else 0
    
    sys_prompt = (
        "Ты IT-лид, предоставляющий официальный фидбек после собеседования. "
        "Тон: профессиональный, официальный, объективный. Хвали чуть больше, чем критикуешь, но не скатывайся в 'няньку'."
    )
    user_prompt = (
        f"Кандидат ('{specialty}') набрал {total_score} из {max_possible} возможных баллов. Оценки по каждому ответу: {scores}.\n\n"
        "Напиши общее резюме собеседования. Отметь сильные стороны и укажи зоны для роста. "
        "Текст должен быть сплошным (без списков). Без сленга. НЕ пиши вероятность успеха в процентах, это уже рассчитано системой."
    )
    
    raw_summary = ask_gigachat(sys_prompt, user_prompt, DUMB_MODEL)
    resume_html = format_markdown_to_html(raw_summary.strip())
    
    return jsonify({
        "chance": str(chance_calculated),
        "summary": resume_html
    })

if __name__ == '__main__':
    app.run(debug=True)
