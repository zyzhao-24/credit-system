// 普通管理员界面 JavaScript
// 全局变量
let categories = [];
let students = [];
let activities = [];
let departments = [];

// 页面加载
window.onload = async function() {
    loadStudents();
    loadCategories();
    loadDepartments();
};

// 标签切换
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(tabName).classList.add('active');
    
    if (tabName === 'activities') {
        loadActivities();
    } else if (tabName === 'report') {
        loadReport();
    }
}

// 模态框
function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// ========== 学生列表 ==========
async function loadStudents() {
    const response = await fetch('/api/admin/students');
    const data = await response.json();
    
    if (data.success) {
        students = data.students;
        renderStudentsTable(students);
    }
}

function renderStudentsTable(studentsToRender) {
    const tbody = document.querySelector('#studentsTable tbody');
    tbody.innerHTML = '';
    
    studentsToRender.forEach(student => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${student.student_id}</td>
            <td>${student.name}</td>
        `;
        tbody.appendChild(tr);
    });
}

function filterStudents() {
    const query = document.getElementById('studentSearchInput').value.toLowerCase().trim();
    
    if (!query) {
        renderStudentsTable(students);
        return;
    }
    
    const filtered = students.filter(student => 
        student.student_id.toLowerCase().includes(query) || 
        student.name.toLowerCase().includes(query)
    );
    
    renderStudentsTable(filtered);
}

// ========== 类别和部门加载 ==========
async function loadCategories() {
    const response = await fetch('/api/admin/categories');
    const data = await response.json();
    
    if (data.success) {
        categories = data.categories;
    }
}

async function loadDepartments() {
    const response = await fetch('/api/admin/departments');
    const data = await response.json();
    
    if (data.success) {
        departments = data.departments;
    }
}

// ========== 活动管理 ==========
async function loadActivities() {
    const response = await fetch('/api/admin/activities');
    const data = await response.json();
    
    if (data.success) {
        // 只保存有权限的活动
        activities = data.activities.filter(a => a.can_edit);
        const container = document.getElementById('activitiesList');
        container.innerHTML = '';
        
        if (activities.length === 0) {
            container.innerHTML = '<div class="info-card"><p style="color: #666; text-align: center;">暂无活动，点击"创建活动"开始</p></div>';
            return;
        }
        
        for (const activity of activities) {
            const activityDiv = document.createElement('div');
            activityDiv.className = 'info-card';
            
            // 部门信息
            const deptInfo = activity.department ? `<p><strong>负责部门：</strong>${activity.department}</p>` : '';
            
            activityDiv.innerHTML = `
                <h3>${activity.name}</h3>
                <p><strong>类别：</strong>${activity.categories.join(', ')}</p>
                ${deptInfo}
                <div style="margin-top: 12px;">
                    <button class="add-btn" onclick="showAddRecordModal('${activity.activity_id}')">添加记录</button>
                    <button class="secondary" onclick="showEditActivityCategoriesModal('${activity.activity_id}')">修改类别</button>
                    <button class="danger" onclick="deleteActivity('${activity.activity_id}')">删除活动</button>
                </div>
                <div id="records-${activity.activity_id}"></div>
            `;
            container.appendChild(activityDiv);
            
            await loadRecords(activity.activity_id);
        }
    }
}

async function loadRecords(activity_id) {
    const recordsDiv = document.getElementById(`records-${activity_id}`);
    
    const response = await fetch(`/api/admin/activities/${activity_id}/records`);
    const data = await response.json();
    
    let html = '<h4 style="margin-top: 15px;">记录列表</h4>';
    html += '<table style="margin-top: 10px;"><thead><tr><th>记录名称</th><th>条目数</th><th>操作</th></tr></thead><tbody>';
    
    if (data.success && data.records.length > 0) {
        data.records.forEach(record => {
            html += `
                <tr>
                    <td>${record.record_name}</td>
                    <td>${record.entries_count}</td>
                    <td>
                        <button onclick="showRecordDetail('${record.record_id}')">查看详情</button>
                        <button onclick="showEditRecordModal('${record.record_id}', '${record.record_name.replace(/'/g, "\\'")}', '${activity_id}')">修改名称</button>
                        <button class="danger" onclick="deleteRecord('${record.record_id}', '${activity_id}')">删除</button>
                    </td>
                </tr>
            `;
        });
    } else {
        html += '<tr><td colspan="3" style="text-align: center; color: #666;">暂无记录</td></tr>';
    }
    
    html += '</tbody></table>';
    recordsDiv.innerHTML = html;
}

async function showAddActivityModal() {
    // 确保类别和部门已加载
    if (categories.length === 0) {
        await loadCategories();
    }
    if (departments.length === 0) {
        await loadDepartments();
    }
    
    document.getElementById('newActivityName').value = '';
    
    // 生成部门复选框
    const deptContainer = document.getElementById('activityDepartmentsCheckbox');
    deptContainer.innerHTML = '';
    
    if (departments.length === 0) {
        deptContainer.innerHTML = '<p style="color: #999; font-size: 14px;">暂无部门</p>';
    } else {
        departments.forEach(department => {
            const div = document.createElement('div');
            div.className = 'checkbox-item';
            div.innerHTML = `
                <input type="checkbox" id="act-dept-${department}" value="${department}">
                <label for="act-dept-${department}">${department}</label>
            `;
            deptContainer.appendChild(div);
        });
    }
    
    // 生成类别复选框
    const container = document.getElementById('activityCategoriesCheckbox');
    container.innerHTML = '';
    
    if (categories.length === 0) {
        container.innerHTML = '<p style="color: #999; font-size: 14px;">暂无类别，请联系系统管理员添加</p>';
    } else {
        categories.forEach(category => {
            const div = document.createElement('div');
            div.className = 'checkbox-item';
            div.innerHTML = `
                <input type="checkbox" id="act-cat-${category.name}" value="${category.name}">
                <label for="act-cat-${category.name}">${category.name}</label>
            `;
            container.appendChild(div);
        });
    }
    
    showModal('addActivityModal');
}

async function addActivity() {
    const name = document.getElementById('newActivityName').value.trim();
    
    if (!name) {
        alert('请输入活动名称');
        return;
    }
    
    // 检查是否重名
    const existingActivity = activities.find(a => a.name === name);
    if (existingActivity) {
        alert('活动名称已存在，请使用其他名称');
        return;
    }
    
    const selectedDepartments = [];
    const selectedCategories = [];
    
    // 获取选中的部门
    departments.forEach(department => {
        const checkbox = document.getElementById(`act-dept-${department}`);
        if (checkbox && checkbox.checked) {
            selectedDepartments.push(department);
        }
    });
    
    // 获取选中的类别
    categories.forEach(category => {
        const checkbox = document.getElementById(`act-cat-${category.name}`);
        if (checkbox && checkbox.checked) {
            selectedCategories.push(category.name);
        }
    });
    
    if (selectedCategories.length === 0) {
        alert('请至少选择一个活动类别');
        return;
    }
    
    const department = selectedDepartments.join(', ');
    
    const response = await fetch('/api/admin/activities', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, categories: selectedCategories, department})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('活动创建成功！');
        closeModal('addActivityModal');
        loadActivities();
    } else {
        alert(data.message || '创建失败');
    }
}

async function deleteActivity(activity_id) {
    if (!confirm('确定删除该活动？')) return;
    
    const response = await fetch('/api/admin/activities', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({activity_id})
    });
    
    const data = await response.json();
    if (data.success) {
        loadActivities();
    } else {
        alert(data.message);
    }
}

// ========== 活动类别修改 ==========
async function showEditActivityCategoriesModal(activity_id) {
    const activity = activities.find(a => a.activity_id === activity_id);
    if (!activity) return;
    
    document.getElementById('editActivityId').value = activity_id;
    document.getElementById('editActivityName').value = activity.name;
    
    // 加载类别复选框
    const container = document.getElementById('editActivityCategoriesCheckbox');
    container.innerHTML = '';
    
    categories.forEach(category => {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `edit-cat-${category.name}`;
        checkbox.value = category.name;
        checkbox.checked = activity.categories.includes(category.name);
        
        const label = document.createElement('label');
        label.htmlFor = `edit-cat-${category.name}`;
        label.textContent = category.name;
        
        div.appendChild(checkbox);
        div.appendChild(label);
        container.appendChild(div);
    });
    
    showModal('editActivityCategoriesModal');
}

async function saveActivityCategories() {
    const activity_id = document.getElementById('editActivityId').value;
    
    // 获取选中的类别
    const selectedCategories = [];
    categories.forEach(category => {
        const checkbox = document.getElementById(`edit-cat-${category.name}`);
        if (checkbox && checkbox.checked) {
            selectedCategories.push(category.name);
        }
    });
    
    if (selectedCategories.length === 0) {
        alert('请至少选择一个类别');
        return;
    }
    
    const response = await fetch('/api/admin/activities', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            activity_id,
            categories: selectedCategories
        })
    });
    
    const data = await response.json();
    if (data.success) {
        alert('类别修改成功');
        closeModal('editActivityCategoriesModal');
        loadActivities();
    } else {
        alert(data.message);
    }
}

function showAddRecordModal(activity_id) {
    document.getElementById('recordActivityId').value = activity_id;
    document.getElementById('newRecordName').value = '';
    showModal('addRecordModal');
}

async function addRecord() {
    const activity_id = document.getElementById('recordActivityId').value;
    const record_name = document.getElementById('newRecordName').value;
    
    const response = await fetch('/api/admin/records', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({activity_id, record_name})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addRecordModal');
        loadRecords(activity_id);
        showRecordDetail(data.record_id);
    } else {
        alert(data.message);
    }
}

function showEditRecordModal(record_id, current_name, activity_id) {
    document.getElementById('editRecordId').value = record_id;
    document.getElementById('editRecordActivityId').value = activity_id;
    document.getElementById('editRecordName').value = current_name;
    showModal('editRecordModal');
}

async function updateRecordName() {
    const record_id = document.getElementById('editRecordId').value;
    const activity_id = document.getElementById('editRecordActivityId').value;
    const record_name = document.getElementById('editRecordName').value;
    
    if (!record_name.trim()) {
        alert('记录名称不能为空');
        return;
    }
    
    const response = await fetch('/api/admin/records', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id, record_name})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('editRecordModal');
        loadRecords(activity_id);
    } else {
        alert(data.message || '修改失败');
    }
}

async function deleteRecord(record_id, activity_id) {
    if (!confirm('确定删除该记录？所有学分条目也将被删除。')) return;
    
    const response = await fetch('/api/admin/records', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id})
    });
    
    const data = await response.json();
    if (data.success) {
        await loadRecords(activity_id);
        loadActivities();
    } else {
        alert(data.message);
    }
}

// ========== 记录详情 ==========
async function showRecordDetail(record_id) {
    const response = await fetch(`/api/admin/records/${record_id}`);
    const data = await response.json();
    
    if (data.success) {
        const record = data.record;
        
        // 检查是否有编辑权限（通过检查活动是否在有权限列表中）
        const activity = activities.find(a => a.activity_id === record.activity_id);
        const canEdit = activity && activity.can_edit;
        
        if (!canEdit) {
            alert('无权限查看此记录');
            return;
        }
        
        document.getElementById('detailRecordId').value = record_id;
        document.getElementById('recordDetailTitle').textContent = 
            `${record.activity_name} - ${record.record_name}`;
        
        let html = `
            <p><strong>活动类别：</strong>${record.activity_categories.join(', ')}</p>
            <table>
                <thead>
                    <tr>
                        <th><input type="checkbox" id="selectAllEntries" onchange="toggleSelectAll()"></th>
                        <th>学号</th>
                        <th>姓名</th>
                        <th>学分</th>
                        <th>类别</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        record.entries.forEach(entry => {
            const notExistTag = !entry.student_exists ? ' <span style="color: #ff8c00;">(学生不存在)</span>' : '';
            html += `
                <tr>
                    <td><input type="checkbox" class="entry-checkbox" value="${entry.student_id}"></td>
                    <td>${entry.student_id}</td>
                    <td>${entry.student_name}${notExistTag}</td>
                    <td>${entry.credits}</td>
                    <td>${entry.categories.join(', ')}</td>
                    <td>
                        <button onclick="editEntry('${record_id}', '${entry.student_id}', ${entry.credits}, ${JSON.stringify(entry.categories).replace(/"/g, '&quot;')})">编辑</button>
                        <button class="danger" onclick="deleteEntry('${record_id}', '${entry.student_id}')">删除</button>
                    </td>
                </tr>
            `;
        });
        
        html += `
                </tbody>
            </table>
        `;
        
        document.getElementById('recordDetailContent').innerHTML = html;
        showModal('recordDetailModal');
    }
}

function toggleSelectAll() {
    const checked = document.getElementById('selectAllEntries').checked;
    document.querySelectorAll('.entry-checkbox').forEach(cb => {
        cb.checked = checked;
    });
}

async function editEntry(record_id, student_id, credits, categories) {
    const response = await fetch(`/api/admin/records/${record_id}`);
    const data = await response.json();
    
    if (data.success) {
        const activityCategories = data.record.activity_categories;
        
        document.getElementById('editEntryRecordId').value = record_id;
        document.getElementById('editEntryStudentId').value = student_id;
        document.getElementById('editEntryStudentIdDisplay').value = student_id;
        document.getElementById('editEntryCredits').value = credits;
        
        const container = document.getElementById('editEntryCategoriesCheckbox');
        container.innerHTML = '';
        
        activityCategories.forEach(category => {
            const div = document.createElement('div');
            div.className = 'checkbox-item';
            const isChecked = categories.includes(category) ? 'checked' : '';
            div.innerHTML = `
                <input type="checkbox" id="edit-cat-${category}" value="${category}" ${isChecked}>
                <label for="edit-cat-${category}">${category}</label>
            `;
            container.appendChild(div);
        });
        
        showModal('editEntryModal');
    }
}

async function saveEditEntry() {
    const record_id = document.getElementById('editEntryRecordId').value;
    const student_id = document.getElementById('editEntryStudentId').value;
    const credits = parseFloat(document.getElementById('editEntryCredits').value);
    
    const selectedCategories = [];
    document.querySelectorAll('#editEntryCategoriesCheckbox input:checked').forEach(cb => {
        selectedCategories.push(cb.value);
    });
    
    if (selectedCategories.length === 0) {
        alert('请至少选择一个类别');
        return;
    }
    
    const response = await fetch('/api/admin/entries', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            record_id,
            student_id,
            credits,
            categories: selectedCategories
        })
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('editEntryModal');
        showRecordDetail(record_id);
    } else {
        alert(data.message);
    }
}

async function deleteEntry(record_id, student_id) {
    if (!confirm('确定删除该条目？')) return;
    
    const response = await fetch('/api/admin/entries', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id, student_id})
    });
    
    const data = await response.json();
    if (data.success) {
        showRecordDetail(record_id);
    } else {
        alert(data.message);
    }
}

async function showBatchEntryModal() {
    const record_id = document.getElementById('detailRecordId').value;
    
    const response = await fetch(`/api/admin/records/${record_id}`);
    const data = await response.json();
    
    if (data.success) {
        const activityCategories = data.record.activity_categories;
        
        const container = document.getElementById('batchEntryCategoriesCheckbox');
        container.innerHTML = '';
        
        activityCategories.forEach(category => {
            const div = document.createElement('div');
            div.className = 'checkbox-item';
            div.innerHTML = `
                <input type="checkbox" id="batch-cat-${category}" value="${category}" checked>
                <label for="batch-cat-${category}">${category}</label>
            `;
            container.appendChild(div);
        });
        
        document.getElementById('batchEntryData').value = '';
        showModal('batchEntryModal');
    }
}

async function batchAddEntries() {
    const record_id = document.getElementById('detailRecordId').value;
    const entries_text = document.getElementById('batchEntryData').value;
    const default_credits = parseFloat(document.getElementById('defaultCredits').value) || 0;
    
    const selectedCategories = [];
    document.querySelectorAll('#batchEntryCategoriesCheckbox input:checked').forEach(cb => {
        selectedCategories.push(cb.value);
    });
    
    if (selectedCategories.length === 0) {
        alert('请至少选择一个类别');
        return;
    }
    
    const response = await fetch('/api/admin/entries/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id, entries_text, categories: selectedCategories, default_credits})
    });
    
    const result = await response.json();
    if (result.success) {
        let msg = `批量操作成功！\n新增: ${result.added}\n更新: ${result.updated}`;
        if (result.ignored > 0) {
            msg += `\n忽略: ${result.ignored}（姓名无匹配）`;
        }
        if (result.errors.length > 0) {
            msg += '\n\n错误:\n' + result.errors.join('\n');
        }
        alert(msg);
        closeModal('batchEntryModal');
        showRecordDetail(record_id);
    } else {
        alert(result.message);
    }
}

async function batchDeleteSelectedEntries() {
    const record_id = document.getElementById('detailRecordId').value;
    const selected = [];
    
    document.querySelectorAll('.entry-checkbox:checked').forEach(cb => {
        selected.push(cb.value);
    });
    
    if (selected.length === 0) {
        alert('请选择要删除的条目');
        return;
    }
    
    if (!confirm(`确定删除选中的 ${selected.length} 个条目？`)) return;
    
    const response = await fetch('/api/admin/entries/batch_delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id, student_ids: selected})
    });
    
    const data = await response.json();
    if (data.success) {
        showRecordDetail(record_id);
    } else {
        alert(data.message);
    }
}

function showBatchUpdateModal() {
    const record_id = document.getElementById('detailRecordId').value;
    document.getElementById('batchUpdateRecordId').value = record_id;
    document.getElementById('batchUpdateCredits').value = '';
    
    fetch(`/api/admin/records/${record_id}`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const activityCategories = data.record.activity_categories;
                const container = document.getElementById('batchUpdateCategoriesCheckbox');
                container.innerHTML = '';
                
                activityCategories.forEach(category => {
                    const div = document.createElement('div');
                    div.className = 'checkbox-item';
                    div.innerHTML = `
                        <input type="checkbox" id="batch-update-cat-${category}" value="${category}">
                        <label for="batch-update-cat-${category}">${category}</label>
                    `;
                    container.appendChild(div);
                });
                
                showModal('batchUpdateModal');
            }
        });
}

async function batchUpdateEntries() {
    const record_id = document.getElementById('batchUpdateRecordId').value;
    const credits_input = document.getElementById('batchUpdateCredits').value;
    const new_credits = credits_input ? parseFloat(credits_input) : null;
    
    const selectedCategories = [];
    document.querySelectorAll('#batchUpdateCategoriesCheckbox input:checked').forEach(cb => {
        selectedCategories.push(cb.value);
    });
    
    const new_categories = selectedCategories.length > 0 ? selectedCategories : null;
    
    if (new_credits === null && new_categories === null) {
        alert('请至少修改学分或类别');
        return;
    }
    
    const selected = [];
    document.querySelectorAll('.entry-checkbox:checked').forEach(cb => {
        selected.push(cb.value);
    });
    
    if (selected.length === 0) {
        alert('请选择要修改的条目');
        return;
    }
    
    const response = await fetch('/api/admin/entries/batch_update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            record_id,
            student_ids: selected,
            credits: new_credits,
            categories: new_categories
        })
    });
    
    const data = await response.json();
    if (data.success) {
        alert(`批量修改成功！修改了 ${data.updated} 个条目`);
        closeModal('batchUpdateModal');
        showRecordDetail(record_id);
    } else {
        alert(data.message);
    }
}

// ========== 数据报表 ==========
async function loadReport() {
    const response = await fetch('/api/admin/report');
    const data = await response.json();
    
    if (data.success) {
        displayReport(data);
    }
}

function displayReport(data) {
    let html = '';
    
    // 1. 活动列表（网格布局）
    html += '<div class="info-card"><h3>活动列表（按类别）</h3>';
    html += '<div class="activities-grid">';
    
    for (const [category, activities] of Object.entries(data.category_activities)) {
        html += `<div class="activity-column">`;
        html += `<h4>${category}</h4><ul>`;
        activities.forEach(act => {
            html += `<li>${act.activity_name}</li>`;
        });
        html += '</ul></div>';
    }
    
    if (data.no_category_activities.length > 0) {
        html += `<div class="activity-column">`;
        html += '<h4>无类别活动</h4><ul>';
        data.no_category_activities.forEach(act => {
            html += `<li>${act.activity_name}</li>`;
        });
        html += '</ul></div>';
    }
    
    html += '</div></div>';
    
    // 2. 合格统计（带进度条）
    html += '<div class="info-card"><h3>合格情况统计</h3>';
    html += '<table><thead><tr><th>项目</th><th>合格人数</th><th>未合格人数</th><th>合格率</th><th>进度</th></tr></thead><tbody>';
    
    for (const [category, stats] of Object.entries(data.category_stats)) {
        html += `<tr>
            <td>${category}</td>
            <td>${stats.qualified}</td>
            <td>${stats.unqualified}</td>
            <td>${stats.percentage}%</td>
            <td>
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" style="width: ${stats.percentage}%"></div>
                    <div class="progress-bar-text">${stats.percentage}%</div>
                </div>
            </td>
        </tr>`;
    }
    
    html += `<tr>
        <td><strong>总学分</strong></td>
        <td>${data.total_stats.qualified}</td>
        <td>${data.total_stats.unqualified}</td>
        <td>${data.total_stats.percentage}%</td>
        <td>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${data.total_stats.percentage}%"></div>
                <div class="progress-bar-text">${data.total_stats.percentage}%</div>
            </div>
        </td>
    </tr>`;
    
    html += `<tr>
        <td><strong>最终合格</strong></td>
        <td>${data.final_stats.qualified}</td>
        <td>${data.final_stats.unqualified}</td>
        <td>${data.final_stats.percentage}%</td>
        <td>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${data.final_stats.percentage}%"></div>
                <div class="progress-bar-text">${data.final_stats.percentage}%</div>
            </div>
        </td>
    </tr>`;
    
    html += '</tbody></table></div>';
    
    // 3. 分数段统计
    html += '<div class="info-card"><h3>分数段统计</h3>';
    html += '<table><thead><tr><th>分数段</th><th>人数</th><th>比例</th></tr></thead><tbody>';
    for (const [range, count] of Object.entries(data.score_ranges)) {
        const percentage = data.total_students > 0 ? (count / data.total_students * 100).toFixed(1) : 0;
        html += `<tr><td>${range}</td><td>${count}</td><td>${percentage}%</td></tr>`;
    }
    html += '</tbody></table></div>';
    
    document.getElementById('reportContent').innerHTML = html;
}

// 退出登录
async function logout() {
    const response = await fetch('/api/logout', {method: 'POST'});
    const data = await response.json();
    if (data.admin_login_path) {
        window.location.href = '/' + data.admin_login_path;
    } else {
        window.location.href = '/';
    }
}
