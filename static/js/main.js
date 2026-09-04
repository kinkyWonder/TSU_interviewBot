let specialty = "";
let difficulty = "standard";
let questions = [];
let currentQ = 0;
let userAnswers = [];
let evaluations = [];
let generatedMentorPrompt = "";

const loadingPhrases = ["Анализ данных...", "Структурирование...", "Сверка с базой знаний...", "Оценка компетенций..."];
let loadingInterval;

// Проверяем наличие незавершенной сессии при загрузке страницы
window.onload = () => {
    if (localStorage.getItem('interviewState')) {
        document.getElementById('resumeContainer').style.display = 'block';
        document.getElementById('newInterviewForm').style.display = 'none';
    }
};

function saveSession() {
    const state = { specialty, difficulty, questions, currentQ, userAnswers };
    localStorage.setItem('interviewState', JSON.stringify(state));
}

function clearSession() {
    localStorage.removeItem('interviewState');
    document.getElementById('resumeContainer').style.display = 'none';
    document.getElementById('newInterviewForm').style.display = 'block';
}

function resumeInterview() {
    const saved = localStorage.getItem('interviewState');
    if (saved) {
        const state = JSON.parse(saved);
        specialty = state.specialty;
        difficulty = state.difficulty;
        questions = state.questions;
        currentQ = state.currentQ;
        userAnswers = state.userAnswers;
        
        showScreen('screen-interview');
        updateQuestionUI();
    }
}

function startDynamicText() {
    let idx = 0;
    const el = document.getElementById('dynamicLoadingText');
    el.innerText = loadingPhrases[idx];
    loadingInterval = setInterval(() => {
        idx = (idx + 1) % loadingPhrases.length;
        el.style.opacity = 0;
        setTimeout(() => { el.innerText = loadingPhrases[idx]; el.style.opacity = 1; }, 300);
    }, 2500);
}

function stopDynamicText() { clearInterval(loadingInterval); }

function showScreen(id) { 
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active')); 
    document.getElementById(id).classList.add('active'); 
}

async function startInterview() {
    const inp = document.getElementById('specialtyInput').value.trim();
    specialty = inp || "Искусственный интеллект и большие данные";
    difficulty = document.getElementById('difficultyInput').value;
    
    document.getElementById('loadingStatus').innerText = "Генерация вопросов...";
    showScreen('screen-loading');
    startDynamicText();
    
    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ specialty, difficulty })
        });
        const data = await res.json();
        questions = data.questions;
        
        stopDynamicText();
        if (!questions || questions.length === 0) throw new Error("Вопросы не сгенерированы");
        
        userAnswers = new Array(questions.length).fill(""); 
        
        saveSession(); // Сохраняем сессию сразу после генерации
        showScreen('screen-interview');
        updateQuestionUI();
    } catch (e) {
        stopDynamicText();
        alert("Произошла ошибка при обращении к серверу. Попробуйте еще раз.");
        showScreen('screen-start');
    }
}

function updateQuestionUI() {
    document.getElementById('questionCounter').innerText = `Вопрос ${currentQ + 1} из ${questions.length}`;
    document.getElementById('questionText').innerText = questions[currentQ];
    document.getElementById('answerInput').value = userAnswers[currentQ];
    document.getElementById('progressFill').style.width = `${(currentQ / questions.length) * 100}%`;
    
    document.getElementById('prevBtn').style.display = currentQ > 0 ? 'block' : 'none';
    document.getElementById('nextBtn').innerText = currentQ === questions.length - 1 ? 'Завершить' : 'Далее';
}

function nextQuestion() {
    userAnswers[currentQ] = document.getElementById('answerInput').value.trim(); 
    saveSession(); // Сохраняем прогресс пользователя
    
    if (currentQ < questions.length - 1) {
        currentQ++;
        updateQuestionUI();
    } else {
        document.getElementById('progressFill').style.width = '100%';
        startEvaluation();
    }
}

function prevQuestion() {
    userAnswers[currentQ] = document.getElementById('answerInput').value.trim();
    saveSession(); // Сохраняем прогресс пользователя
    
    if (currentQ > 0) {
        currentQ--;
        updateQuestionUI();
    }
}

function abortInterview() {
    if(confirm("Завершить собеседование досрочно? На все оставшиеся вопросы будет поставлен 0 баллов.")) {
        userAnswers[currentQ] = document.getElementById('answerInput').value.trim();
        startEvaluation(); // Автоматически уходим на проверку того, что успели
    }
}

async function startEvaluation() {
    // Пользователь дошел до конца или прервал тест — стираем локальную сессию
    localStorage.removeItem('interviewState'); 
    
    showScreen('screen-loading');
    startDynamicText();
    
    for (let i = 0; i < questions.length; i++) {
        document.getElementById('loadingStatus').innerText = `Проверка ответа ${i + 1}/${questions.length}`;
        
        // Защита от undefined, если тест был прерван
        const ans = userAnswers[i] || ""; 
        
        const res = await fetch('/api/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: questions[i], answer: ans })
        });
        const data = await res.json();
        evaluations.push({ q: questions[i], a: ans, feedback: data.feedback, score: data.score });
    }
    
    stopDynamicText();
    showScreen('screen-results');
    renderDetailedResults();
    fetchSummary(); 
}

function renderDetailedResults() {
    const container = document.getElementById('detailedResults');
    container.innerHTML = "";
    
    evaluations.forEach((item, index) => {
        const displayAnswer = item.a === "" || item.a === "-" ? "Ответ не предоставлен" : item.a;
        
        let badgeClass = 'score-low';
        if (item.score >= 8) badgeClass = 'score-high';
        else if (item.score >= 5) badgeClass = 'score-med';
        
        const card = document.createElement('div');
        card.className = 'result-card';
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div class="q-title">${index + 1}. ${item.q}</div>
                <span class="score-badge ${badgeClass}">Оценка: ${item.score}/10</span>
            </div>
            <p style="color: var(--text-muted); background: #f9fafb; padding: 10px; border-radius: 6px; border: 1px solid var(--border);"><strong>Ваш ответ:</strong> ${displayAnswer}</p>
            <p style="margin: 16px 0 0 0; white-space: pre-wrap;">${item.feedback}</p>
        `;
        container.appendChild(card);
    });
}

async function fetchSummary() {
    const scores = evaluations.map(e => e.score);
    const res = await fetch('/api/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scores: scores, specialty: specialty })
    });
    const data = await res.json();
    
    document.getElementById('chanceValue').innerText = data.chance + "%";
    document.getElementById('summaryText').innerHTML = data.summary;
    
    generatedMentorPrompt = data.mentor_prompt;
    if (generatedMentorPrompt) {
        document.getElementById('mentorPromptContainer').style.display = 'block';
    }
}

function copyMentorPrompt() {
    navigator.clipboard.writeText(generatedMentorPrompt).then(() => {
        const btn = document.getElementById('copyPromptBtn');
        const originalText = btn.innerHTML;
        
        btn.innerText = "✓ Промпт скопирован!";
        btn.style.backgroundColor = "#dcfce7";
        btn.style.borderColor = "#166534";
        btn.style.color = "#166534";
        
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style = "";
        }, 3000);
    }).catch(err => {
        alert("Не удалось скопировать текст.");
    });
}