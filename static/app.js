window.profDataMap = {};

function getTargets() {
    return JSON.parse(localStorage.getItem('faculty_targets') || '[]');
}

function saveTargets(data) {
    localStorage.setItem('faculty_targets', JSON.stringify(data));
}

function getProfile() {
    return JSON.parse(localStorage.getItem('applicant_profile') || '{}');
}

function saveProfile(data) {
    localStorage.setItem('applicant_profile', JSON.stringify(data));
}

function showToast(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

function addToTargets(idHash, event) {
    if (event) event.stopPropagation();
    const prof = window.profDataMap[idHash];
    if (!prof) return console.error("Data missing");

    const targets = getTargets();
    if (targets.some(t => t.id_hash === prof.id_hash)) {
        showToast("⚠️ 已在收藏列表中");
        return;
    }
    targets.push(prof);
    saveTargets(targets);
    showToast("⭐ 已添加");

    const btn = document.getElementById('btn-add-' + idHash);
    if (btn) {
        btn.innerHTML = '<i class="fas fa-check"></i> 已收藏';
        btn.classList.add('btn-secondary');
    }
}

function removeFromTargets(idHash, event) {
    if (event) event.stopPropagation();
    let targets = getTargets();
    targets = targets.filter(t => t.id_hash !== idHash);
    saveTargets(targets);
    showToast("🗑️ 已移除");

    if (document.getElementById('targets-grid')) {
        renderTargets();
    } else {
        const btn = document.getElementById('btn-add-' + idHash);
        if (btn) {
            btn.innerHTML = '<i class="fas fa-star"></i> 收藏';
            btn.classList.remove('btn-secondary');
        }
    }
}

async function openEmailModal(idHash, event) {
    if (event) event.stopPropagation();

    const profile = getProfile();
    if (!profile.name && !profile.university) {
        if (confirm("⚠️ 您的个人档案为空。是否现在去填写？")) {
            window.location.href = "/profile";
            return;
        }
    }

    const prof = window.profDataMap[idHash];
    const modal = document.getElementById('emailModal');
    const loading = document.getElementById('modalLoading');
    const content = document.getElementById('modalContent');
    const errorDiv = document.getElementById('modalError');
    const copyBtn = document.getElementById('copyBtn');
    const textArea = document.getElementById('emailResult');

    modal.style.display = 'flex';
    loading.style.display = 'block';
    content.style.display = 'none';
    errorDiv.style.display = 'none';
    copyBtn.style.display = 'none';
    textArea.value = '';

    try {
        const response = await fetch('/api/generate-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                applicant: profile,
                professor: prof
            })
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error("Server Error: " + response.status + " " + errText);
        }

        const data = await response.json();
        loading.style.display = 'none';
        content.style.display = 'block';
        textArea.value = data.content;
        copyBtn.style.display = 'inline-flex';

    } catch (e) {
        loading.style.display = 'none';
        errorDiv.style.display = 'block';
        errorDiv.innerText = "❌ " + e.message;
    }
}

function closeModal() {
    document.getElementById('emailModal').style.display = 'none';
}

function copyEmail() {
    const copyText = document.getElementById("emailResult");
    copyText.select();
    document.execCommand("copy");
    showToast("📋 已复制");
}

function submitProfile(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const profile = Object.fromEntries(formData.entries());
    saveProfile(profile);
    showToast("✅ 档案已保存");
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('profileForm')) {
        const profile = getProfile();
        const inputs = document.querySelectorAll('#profileForm input, #profileForm textarea, #profileForm select');
        inputs.forEach(input => {
            if (profile[input.name]) input.value = profile[input.name];
        });
    }
    if (document.getElementById('targets-grid')) {
        renderTargets();
    }
});

function renderTargets() {
    const container = document.getElementById('targets-grid');
    const targets = getTargets();

    targets.forEach(p => { window.profDataMap[p.id_hash] = p; });

    if (targets.length === 0) {
        container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:50px;color:#94a3b8;"><h3>📭 暂无收藏</h3></div>';
        return;
    }

    container.innerHTML = targets.map(prof => {
        let areas = prof.research_areas;
        if (Array.isArray(areas)) areas = areas.join(", ");

        let nameHtml = prof.name;
        if (prof.link && prof.link !== '未提供' && prof.link.startsWith('http')) {
            nameHtml = `<a href="${prof.link}" target="_blank" style="color:inherit; text-decoration:none; border-bottom: 1px dotted currentColor;">${prof.name} <i class="fas fa-external-link-alt" style="font-size:0.7em;"></i></a>`;
        }

        return `
        <div class="card">
            <div class="card-header">
                <div style="display:flex; justify-content:space-between;">
                    <h3 class="card-title">${nameHtml}</h3>
                    <span class="badge">${prof.uni_name}</span>
                </div>
                <span class="card-subtitle">${prof.title}</span>
            </div>
            <div style="flex:1; margin-bottom:15px; font-size:0.9rem; color:#475569;">
                <p><i class="fas fa-envelope"></i> ${prof.email}</p>
                <p><i class="fas fa-microscope"></i> ${areas}</p>
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn" onclick="openEmailModal('${prof.id_hash}', event)" style="flex:1;">
                    <i class="fas fa-magic"></i> 写信
                </button>
                <button class="btn btn-secondary btn-danger" onclick="removeFromTargets('${prof.id_hash}', event)">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>`;
    }).join('');
}
