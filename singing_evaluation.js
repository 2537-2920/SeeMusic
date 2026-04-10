// 模拟交互逻辑
document.querySelectorAll('.action-btn, .secondary-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const originalText = this.innerText;
        this.innerHTML = '<iconify-icon icon="line-md:loading-twotone-loop" class="text-xl"></iconify-icon> 处理中...';
        this.disabled = true;
        this.style.opacity = '0.7';
        
        setTimeout(() => {
            this.innerHTML = originalText;
            this.disabled = false;
            this.style.opacity = '1';
            alert('操作模拟成功！(仅为原型演示)');
        }, 1500);
    });
});