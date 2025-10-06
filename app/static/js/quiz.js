(function(){
  async function fetchQuiz(){
    const res = await fetch('/api/quiz_progressive');
    if(res.redirected){ window.location = res.url; return; }
    if(!res.ok){ throw new Error('Failed to load quiz'); }
    return await res.json();
  }

  function createEl(tag, attrs, ...children){
    const el = document.createElement(tag);
    if(attrs){ Object.entries(attrs).forEach(([k,v])=>{
      if(k==='class') el.className = v; else el.setAttribute(k,v);
    }); }
    for(const child of children){
      if(typeof child === 'string') el.appendChild(document.createTextNode(child));
      else if(child) el.appendChild(child);
    }
    return el;
  }

  function renderQuiz(root, payload){
    const { attempt_id, questions } = payload;
    let idx = 0;
    const answers = [];
    let started = performance.now();

    function showQuestion(){
      root.innerHTML='';
      const q = questions[idx];
      const title = createEl('h3', null, `Question ${idx+1} of ${questions.length}`);
      const text = createEl('p', null, q.question);
      const form = createEl('div', {class:'card'});
      const opts = q.options || [];
      const list = createEl('div');
      opts.forEach((opt,i)=>{
        const id = `opt_${idx}_${i}`;
        const input = createEl('input', {type:'radio', name:'answer', id});
        input.value = opt;
        const label = createEl('label', {for:id}, opt);
        const row = createEl('div', {class:'form-row'} , input, label);
        list.appendChild(row);
      });
      const nextBtn = createEl('button', {class:'btn', type:'button'}, idx===questions.length-1?'Submit':'Next');
      nextBtn.addEventListener('click', ()=>{
        const chosen = root.querySelector('input[name="answer"]:checked');
        if(!chosen){ alert('Please select an answer'); return; }
        const elapsed = (performance.now()-started)/1000.0;
        answers.push({ quiz_id: q.quiz_id, answer: chosen.value, time_sec: elapsed });
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
      root.appendChild(title);
      root.appendChild(text);
      root.appendChild(form);
    }

    async function submitAll(){
      root.innerHTML = '<p>Submitting...</p>';
      const res = await fetch('/submit', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ attempt_id, answers }) });
      if(res.redirected){ window.location = res.url; return; }
      if(!res.ok){ root.innerHTML = '<p>Submission failed.</p>'; return; }
      const data = await res.json();
      const score = createEl('h3', null, `Score: ${Math.round(data.score_pct)}% (${data.correct}/${data.total})`);
      const back = createEl('a', {class:'btn', href:`/student/${data.student_id}`}, 'Back to Dashboard');

      const wrong = data.details.filter(d=>d.score===0);
      const list = createEl('div');
      wrong.forEach(d=>{
        const item = createEl('div', {class:'card'},
          createEl('p', null, d.question),
          createEl('p', null, `Your answer: ${d.answer}`),
          createEl('p', null, `Correct: ${d.correct_answer}`),
          createEl('p', null, `Explanation: ${d.explanation || ''}`)
        );
        list.appendChild(item);
      });
      root.innerHTML='';
      root.appendChild(score);
      root.appendChild(back);
      if(wrong.length){
        root.appendChild(createEl('h4', null, 'Review these questions:'));
        root.appendChild(list);
      }
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
      root.innerHTML = '<p>Failed to load quiz.</p>';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
