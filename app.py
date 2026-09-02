import requests
import json
import uuid
import urllib3
import re
import time

# Отключаем предупреждения об отсутствии SSL сертификатов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Твои данные для авторизации
AUTH_KEY = "MDFhMDYwZWYtYjI1Yi03NTRjLWIyMTYtZTk0YmIyZWUyOWJjOjZmNzI5ZDNiLWZkYjYtNDkyNC04NzA3LTk1ZjdkN2U5NDRiYg=="

# Распределение моделей по твоей логике
SMART_MODEL = "GigaChat-3-Ultra" # Для вопросов и оценки
DUMB_MODEL = "GigaChat-Pro"    # Для финального резюме

def get_access_token(auth_key):
    """Получает токен доступа для GigaChat API"""
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    payload = {'scope': 'GIGACHAT_API_PERS'}
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {auth_key}'
    }
    
    response = requests.post(url, headers=headers, data=payload, verify=False)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"Ошибка авторизации: {response.status_code}")
        print(response.text)
        return None

def ask_gigachat(token, system_prompt, user_text, model):
    """Отправляет запрос в конкретную модель GigaChat"""
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.7,
        "top_p": 0.1,
        "n": 1,
        "stream": False,
        "max_tokens": 1024,
        "repetition_penalty": 1
    })
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.post(url, headers=headers, data=payload, verify=False)
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        print(f"Ошибка API (Модель: {model}): {response.status_code}")
        print(response.text)
        return ""

def extract_questions(text):
    """Парсит текст нейросети и вытаскивает только нумерованные вопросы"""
    # Поддерживает форматы "1. Вопрос", "**1.** Вопрос", " 1. Вопрос"
    questions = re.findall(r'^\s*(?:\*\*)?\d+\.(?:\*\*)?\s*(.+)', text, flags=re.MULTILINE)
    return questions[:8] 

def extract_score(text):
    """Пытается найти оценку от 0 до 10 в ответе нейросети"""
    match = re.search(r'(?:Оценка|оценка|Балл|балл).*?(\d+)(?:\s*/\s*10)?', text)
    if match:
        return int(match.group(1))
    return 0 

def main():
    print("Подключение к серверам GigaChat...")
    token = get_access_token(AUTH_KEY)
    if not token:
        return
        
    print("\n=======================================================")
    print("🤖 Здравствуйте! Это ИИ-интервьюер.")
    print("Я помогу вам подготовиться к техническому собеседованию.")
    specialty = input("Напишите мне свое направление и специальность (например: Python Backend Developer): ")
    
    if not specialty.strip():
        specialty = "IT специалист"

    print(f"\nГенерирую вопросы (Модель: {SMART_MODEL})... Пожалуйста, подождите.\n")
    
    # 1. ГЕНЕРАЦИЯ ВОПРОСОВ (Умная модель - Ultra)
    gen_prompt_sys = "Ты Senior IT-специалист, составляющий план технического собеседования."
    gen_prompt_user = (
        f"Выведи ТОЛЬКО пронумерованный список из 8 вопросов для собеседования на позицию: {specialty}. "
        "Вопросы должны идти строго в порядке возрастания по важности и сложности (от базовых к архитектурным). "
        "Не пиши никаких вступлений и заключений, только сами вопросы."
    )
    
    questions_raw = ask_gigachat(token, gen_prompt_sys, gen_prompt_user, SMART_MODEL)
    questions = extract_questions(questions_raw)
    
    if not questions:
        print("Произошла ошибка при парсинге вопросов. Ответ сети:")
        print(questions_raw)
        return
        
    interview_results = {}
    scores_list = []
    
    # 2. ЦИКЛ СОБЕСЕДОВАНИЯ
    print("=======================================================")
    print(f"Собеседование начинается. Всего вопросов: {len(questions)}")
    print("Отвечайте максимально полно. Если не знаете — так и пишите.")
    print("=======================================================\n")
    
    for i, q in enumerate(questions):
        print(f"Вопрос {i+1}/{len(questions)}:")
        print(f"🔹 {q}")
        user_answer = input("\nВаш ответ:\n> ")
        print("-" * 50)
        
        interview_results[q] = user_answer
        
    print("\nСобеседование завершено! Анализирую ваши ответы...\n")
    time.sleep(1)
    
    # 3. ОЦЕНКА ОТВЕТОВ (Умная модель - Ultra)
    eval_prompt_sys = "Ты честный, вежливый и абсолютно профессиональный IT-интервьюер. Твоя задача — объективно оценить технический ответ кандидата."
    
    print("================ РЕЗУЛЬТАТЫ ПО ВОПРОСАМ ================")
    for q, a in interview_results.items():
        eval_prompt_user = (
            f"Вопрос с собеседования: '{q}'.\n"
            f"Ответ кандидата: '{a}'.\n\n"
            "Дай честную и профессиональную оценку ответу. Если ответ откровенно глупый, неверный или неполный — прямо, но вежливо укажи на это и объясни, как нужно было ответить. "
            "Если ответ хороший — подтверди правильность, но без излишних восторгов. "
            "В самом конце обязательно с новой строки напиши 'Оценка: X/10' (где X — балл от 0 до 10, оценивай строго)."
        )
        
        feedback = ask_gigachat(token, eval_prompt_sys, eval_prompt_user, SMART_MODEL)
        score = extract_score(feedback)
        scores_list.append(score)
        
        print(f"\nВопрос: {q}")
        print(f"Ваш ответ: {a}")
        print(f"Комментарий ИИ:\n{feedback}")
        print("-" * 50)

    # 4. ФИНАЛЬНОЕ РЕЗЮМЕ (Младшая модель - Pro)
    print(f"\nФормирую итоговое заключение (Модель: {DUMB_MODEL})...\n")
    
    avg_score = sum(scores_list) / len(scores_list) if scores_list else 0
    
    summary_sys = "Ты IT-лид, который дает неформальный фидбек после технического интервью."
    summary_user = (
        f"Кандидат проходил собеседование на '{specialty}'. Его средний балл: {avg_score:.1f}/10.\n"
        f"Вот его оценки за вопросы по порядку: {scores_list}.\n\n"
        "Напиши короткое резюме по всему собеседованию. "
        "Опирайся на средний балл. Если балл 6.5 и выше, начни со слов 'Красава, ты бы сдал', если ниже, начни со слов 'Не красава, ты бы не сдал'. "
        "Далее укажи, что было хорошо (исходя из высоких оценок), а что нужно обязательно подтянуть (исходя из низких оценок). "
        "Сделай это в виде связного текста, не перечисляя сами вопросы."
    )
    
    final_summary = ask_gigachat(token, summary_sys, summary_user, DUMB_MODEL)
    
    print("================ ИТОГОВОЕ РЕЗЮМЕ ================")
    print(final_summary)
    print("=================================================")

if __name__ == "__main__":
    main()