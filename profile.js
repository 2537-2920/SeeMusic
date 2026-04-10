// 模拟清理缓存交互
function clearCache(btn) {
    const textSpan = btn.querySelector('.cache-text');
    if(textSpan.innerText.includes('0KB')) return;
    
    textSpan.innerText = '正在清理缓存中...';
    btn.classList.replace('text-red-400', 'text-yellow-500');
    
    setTimeout(() => {
        textSpan.innerText = '清除系统缓存 (0KB)';
        btn.classList.replace('text-yellow-500', 'text-gray-400');
        alert('成功释放 1.2GB 系统缓存空间！');
    }, 1200);
}