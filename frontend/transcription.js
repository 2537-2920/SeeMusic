// 选中音符
function selectNote(el) {
    document.querySelectorAll('.note-head').forEach(n => {
        n.style.boxShadow = 'none';
    });
    const head = el.querySelector('.note-head') || el;
    head.style.boxShadow = '0 0 10px #457b9d';
    document.getElementById('selected-pitch').innerText = 'D4'; 
}

let isRecording = false;
function toggleRecording() {
    const btn = event.currentTarget;
    isRecording = !isRecording;
    if (isRecording) {
        btn.classList.add('recording-pulse', 'text-red-500');
        btn.querySelector('span').innerText = '停止录制...';
    } else {
        btn.classList.remove('recording-pulse', 'text-red-500');
        btn.querySelector('span').innerText = '麦克风录音';
    }
}

// 动态点击生成音符逻辑（已加入时值判断）
document.getElementById('sheet-paper').addEventListener('click', function(e) {
    if (e.target.id === 'sheet-paper' || e.target.classList.contains('staff-line-group') || e.target.classList.contains('staff-line')) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // 获取当前选择的时值
        const durationSelect = document.getElementById('note-duration');
        const duration = durationSelect ? durationSelect.value : '四分音符';
        
        // 创建外部容器
        const wrapper = document.createElement('div');
        wrapper.className = 'note-wrapper';
        wrapper.style.left = (x - 7) + 'px';
        wrapper.style.top = (y - 5) + 'px';
        wrapper.onclick = function(ev) { 
            ev.stopPropagation(); 
            selectNote(this); 
        };
        
        // 创建符头
        const head = document.createElement('div');
        head.className = 'note-head';
        if (duration === '二分音符') {
            head.classList.add('half'); // 加载空心样式
        }
        
        // 创建符干
        const stem = document.createElement('div');
        stem.className = 'note-stem';
        
        wrapper.appendChild(head);
        wrapper.appendChild(stem);
        
        // 如果是八分音符，添加符尾
        if (duration === '八分音符') {
            const tail = document.createElement('div');
            tail.className = 'note-tail';
            wrapper.appendChild(tail);
        }
        
        this.appendChild(wrapper);
    }
});