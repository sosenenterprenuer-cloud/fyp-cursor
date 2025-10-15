(function(){
  let currentAttemptId = null;
  let currentAnswers = [];

  async function fetchQuiz(){
    const res = await fetch('/api/quiz_progressive');
    if(res.redirected){ 
      window.location = res.url; 
      return; 
    }
    if(!res.ok){ 
      throw new Error('Failed to load quiz'); 
    }
    return await res.json();
  }

  function createEl(tag, attrs, ...children){
    const el = document.createElement(tag);
    if(attrs){ 
      Object.entries(attrs).forEach(([k,v])=>{
        if(k==='class') el.className = v; 
        else el.setAttribute(k,v);
      }); 
    }
    for(const child of children){
      if(typeof child === 'string') el.appendChild(document.createTextNode(child));
      else if(child) el.appendChild(child);
    }
    return el;
  }

  function renderQuiz(root, payload){
    const { attempt_id, questions } = payload;
    currentAttemptId = attempt_id;
    currentAnswers = [];
    
    let idx = 0;
    let started = performance.now();

    function showQuestion(){
      root.innerHTML='';
      
      // Progress indicator
      const progress = createEl('div', {class: 'quiz-progress'});
      const progressBar = createEl('div', {class: 'progress-bar'});
      const progressFill = createEl('div', {class: 'progress-fill', style: `width: ${((idx + 1) / questions.length) * 100}%`});
      progressBar.appendChild(progressFill);
      progress.appendChild(progressBar);
      
      const q = questions[idx];
      const title = createEl('h3', {class: 'question-title'}, `Question ${idx+1} of ${questions.length}`);
      const text = createEl('p', {class: 'question-text'}, q.question);
      const form = createEl('div', {class:'quiz-form'});
      const opts = q.options || [];
      const list = createEl('div', {class: 'options-list'});
      
      opts.forEach((opt,i)=>{
        const id = `opt_${idx}_${i}`;
        const optionDiv = createEl('div', {class: 'option-item'});
        const input = createEl('input', {type:'radio', name:'answer', id});
        input.value = opt;
        const label = createEl('label', {for:id, class: 'option-label'}, opt);
        optionDiv.appendChild(input);
        optionDiv.appendChild(label);
        list.appendChild(optionDiv);
      });
      
      const nextBtn = createEl('button', {
        class:'btn btn-primary quiz-btn', 
        type:'button'
      }, idx===questions.length-1?'Submit Quiz':'Next Question');
      
      nextBtn.addEventListener('click', ()=>{
        const chosen = root.querySelector('input[name="answer"]:checked');
        if(!chosen){ 
          alert('Please select an answer'); 
          return; 
        }
        const elapsed = (performance.now()-started)/1000.0;
        currentAnswers.push({ 
          quiz_id: q.quiz_id, 
          answer: chosen.value, 
          time_sec: elapsed 
        });
        idx++;
        if(idx < questions.length){
          started = performance.now();
          showQuestion();
        } else {
          submitAll();
        }
      });
      
      form.appendChild(list);
      form.appendChild(nextBtn);
      
      root.appendChild(progress);
      root.appendChild(title);
      root.appendChild(text);
      root.appendChild(form);
    }

    async function submitAll(){
      root.innerHTML = '<div class="quiz-loading"><h2>Submitting Quiz...</h2><p>Please wait while we grade your answers.</p></div>';
      
      try {
        const res = await fetch('/submit', { 
          method:'POST', 
          headers:{'Content-Type':'application/json'}, 
          body: JSON.stringify({ 
            attempt_id: currentAttemptId, 
            answers: currentAnswers 
          }) 
        });
        
        if(res.redirected){ 
          window.location = res.url; 
          return; 
        }
        if(!res.ok){ 
          root.innerHTML = '<div class="quiz-error"><p>Submission failed. Please try again.</p></div>'; 
          return; 
        }
        
        const data = await res.json();
        showResult(data);
        
      } catch (error) {
        root.innerHTML = '<div class="quiz-error"><p>Network error. Please try again.</p></div>';
      }
    }

    function showResult(data) {
      const modal = document.getElementById('result-modal');
      const percentage = document.getElementById('result-percentage');
      const message = document.getElementById('result-message');
      const retakeBtn = document.getElementById('retake-btn');
      const nextTopicBtn = document.getElementById('next-topic-btn');
      const feedbackList = document.getElementById('feedback-list');
      
      // Update score display
      percentage.textContent = `${Math.round(data.score_pct)}%`;
      
      // Update message and show appropriate buttons
      if (data.passed) {
        message.textContent = 'Congratulations! You passed the quiz.';
        nextTopicBtn.style.display = 'inline-block';
        retakeBtn.style.display = 'none';
      } else {
        message.textContent = 'Keep practicing! You\'ll get it next time.';
        retakeBtn.style.display = 'inline-block';
        nextTopicBtn.style.display = 'none';
      }
      
      // Build feedback list
      feedbackList.innerHTML = '';
      data.details.forEach((detail, index) => {
        const feedbackItem = createEl('div', {class: 'feedback-item'});
        
        const question = createEl('div', {class: 'feedback-question'}, 
          `${index + 1}. ${detail.question}`);
        
        const answers = createEl('div', {class: 'feedback-answers'});
        const yourAnswer = createEl('div', {class: 'feedback-answer feedback-your-answer'}, 
          `Your answer: ${detail.answer}`);
        const correctAnswer = createEl('div', {class: 'feedback-answer feedback-correct-answer'}, 
          `Correct answer: ${detail.correct_answer}`);
        
        answers.appendChild(yourAnswer);
        answers.appendChild(correctAnswer);
        
        const explanation = createEl('div', {class: 'feedback-explanation'}, 
          detail.explanation || 'No explanation available.');
        
        feedbackItem.appendChild(question);
        feedbackItem.appendChild(answers);
        feedbackItem.appendChild(explanation);
        
        feedbackList.appendChild(feedbackItem);
      });
      
      // Show modal
      modal.style.display = 'flex';
      
      // Button event listeners
      retakeBtn.onclick = () => {
        modal.style.display = 'none';
        window.location.href = '/reattempt';
      };
      
      nextTopicBtn.onclick = () => {
        modal.style.display = 'none';
        if (data.next_step) {
          // Find the module for the next step concept
          window.location.href = '/modules';
        } else {
          window.location.href = '/modules';
        }
      };
      
      document.getElementById('close-result').onclick = () => {
        modal.style.display = 'none';
        window.location.href = `/student/${data.student_id}`;
      };
    }

    showQuestion();
  }

  async function init(){
    const root = document.getElementById('quiz-root');
    if(!root) return;
    
    try{
      const payload = await fetchQuiz();
      renderQuiz(root, payload);
    }catch(e){
      root.innerHTML = '<div class="quiz-error"><p>Failed to load quiz. Please refresh the page.</p></div>';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();