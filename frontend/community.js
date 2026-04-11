// 乐谱卡片点击交互：显示右侧面板
function showDetail(title, author, price, cover) {
    document.getElementById('detail-empty').classList.add('hidden');
    document.getElementById('detail-content').classList.remove('hidden');
    
    document.getElementById('d-title').innerText = title;
    document.getElementById('d-author').innerText = author;
    document.getElementById('d-cover').src = cover;
}

// 上传模态框显示与隐藏
function toggleModal(id, show) {
    const modal = document.getElementById(id);
    if (show) {
        modal.classList.add('modal-active');
    } else {
        modal.classList.remove('modal-active');
    }
}