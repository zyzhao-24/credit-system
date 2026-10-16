// 全局变量
let categories = [];
let students = [];
let activities = [];
let departments = [];
let currentAdminRole = '';
let currentAdminId = '';

// 页面加载
window.onload = async function() {
    // 从 session 获取管理员角色（必须先获取）
    try {
        const res = await fetch('/api/admin/session_info');
        const data = await res.json();
        if (data.success) {
            currentAdminRole = data.role;
            currentAdminId = data.admin_id;
            updateUIByRole();
        }
    } catch (error) {
        console.error('获取管理员信息失败:', error);
    }
    
    // 然后加载其他数据
    // 普通管理员可以查看学生列表（不含密码）
    loadStudents();
    
    // 只有系统管理员才加载其他系统设置
    if (currentAdminRole === 'system_admin') {
        loadCategories();
        loadTotalCredits();
        loadEmailConfig();
        loadDepartments();
        loadAdmins();
    }
};

// 根据角色更新界面
function updateUIByRole() {
    if (currentAdminRole === 'system_admin') {
        // 系统管理员：显示所有功能
        const systemAdminSection = document.getElementById('systemAdminSection');
        const systemAdminContent = document.getElementById('systemAdminContent');
        if (systemAdminSection) systemAdminSection.style.display = 'block';
        if (systemAdminContent) systemAdminContent.style.display = 'block';
        
        // 显示系统设置内容
        const systemSettingsContent = document.getElementById('systemSettingsContent');
        if (systemSettingsContent) systemSettingsContent.style.display = 'block';
        
        // 显示查询、报表、导出内容
        const queryContent = document.getElementById('queryContent');
        const reportContentWrapper = document.getElementById('reportContentWrapper');
        const exportContentWrapper = document.getElementById('exportContentWrapper');
        if (queryContent) queryContent.style.display = 'block';
        if (reportContentWrapper) reportContentWrapper.style.display = 'block';
        if (exportContentWrapper) exportContentWrapper.style.display = 'block';
    } else {
        // 普通管理员：可以查看学生列表和报表，但不能编辑
        const systemSettingsContent = document.getElementById('systemSettingsContent');
        const normalAdminMessage = document.getElementById('normalAdminMessage');
        if (systemSettingsContent) systemSettingsContent.style.display = 'block';
        if (normalAdminMessage) normalAdminMessage.style.display = 'none';
        
        // 隐藏查询功能
        const queryContent = document.getElementById('queryContent');
        const queryNoPermission = document.getElementById('queryNoPermission');
        if (queryContent) queryContent.style.display = 'none';
        if (queryNoPermission) queryNoPermission.style.display = 'block';
        
        // 显示报表功能（仅总体统计）
        const reportContentWrapper = document.getElementById('reportContentWrapper');
        const reportNoPermission = document.getElementById('reportNoPermission');
        if (reportContentWrapper) reportContentWrapper.style.display = 'block';
        if (reportNoPermission) reportNoPermission.style.display = 'none';
        
        // 隐藏导出功能
        const exportContentWrapper = document.getElementById('exportContentWrapper');
        const exportNoPermission = document.getElementById('exportNoPermission');
        if (exportContentWrapper) exportContentWrapper.style.display = 'none';
        if (exportNoPermission) exportNoPermission.style.display = 'block';
    }
}

// 标签切换
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(tabName).classList.add('active');
    
    if (tabName === 'activities') {
        loadActivities();
    } else if (tabName === 'report') {
        // 普通管理员也可以查看报表（仅总体统计）
        loadReport();
    } else if (tabName === 'export') {
        if (currentAdminRole === 'system_admin') {
            loadAllStudentsCredits();
        }
    }
}

// 模态框
function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// ========== 学生管理 ==========
async function loadStudents() {
    const response = await fetch('/api/admin/students');
    const data = await response.json();
    
    if (data.success) {
        students = data.students;
        const canEdit = data.can_edit;
        renderStudentsTable(students, canEdit);
    }
}

function renderStudentsTable(studentsToRender, canEdit = true) {
    const tbody = document.querySelector('#studentsTable tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    studentsToRender.forEach(student => {
        const tr = document.createElement('tr');
        
        // 系统管理员可以查看密码
        const passwordCell = student.password ? `
            <td>
                <span class="password-hidden" id="pwd-${student.student_id}">******</span>
                <button onclick="togglePassword('${student.student_id}', '${student.password}')">显示</button>
            </td>
        ` : '<td>-</td>';
        
        // 系统管理员可以编辑
        const actionCell = canEdit ? `
            <td>
                <button onclick="showChangePasswordModal('${student.student_id}')">修改密码</button>
                <button class="danger" onclick="deleteStudent('${student.student_id}')">删除</button>
            </td>
        ` : '<td>-</td>';
        
        tr.innerHTML = `
            <td>${student.student_id}</td>
            <td>${student.name}</td>
            ${passwordCell}
            ${actionCell}
        `;
        tbody.appendChild(tr);
    });
}

function filterStudents() {
    const query = document.getElementById('studentSearchInput').value.toLowerCase().trim();
    const canEdit = currentAdminRole === 'system_admin';
    
    if (!query) {
        renderStudentsTable(students, canEdit);
        return;
    }
    
    const filtered = students.filter(student => 
        student.student_id.toLowerCase().includes(query) || 
        student.name.toLowerCase().includes(query)
    );
    
    renderStudentsTable(filtered, canEdit);
}

function showChangePasswordModal(student_id) {
    document.getElementById('changePasswordStudentId').value = student_id;
    document.getElementById('changePasswordStudentIdDisplay').value = student_id;
    document.getElementById('newPassword').value = '';
    showModal('changePasswordModal');
}

async function changeStudentPassword() {
    const student_id = document.getElementById('changePasswordStudentId').value;
    const new_password = document.getElementById('newPassword').value;
    
    if (!new_password) {
        alert('请输入新密码');
        return;
    }
    
    const response = await fetch('/api/admin/change_student_password', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({student_id, new_password})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('密码修改成功');
        closeModal('changePasswordModal');
        loadStudents();
    } else {
        alert(data.message);
    }
}

function togglePassword(student_id, password_hash) {
    const elem = document.getElementById(`pwd-${student_id}`);
    if (elem.classList.contains('password-hidden')) {
        elem.textContent = password_hash;
        elem.classList.remove('password-hidden');
        event.target.textContent = '隐藏';
    } else {
        elem.textContent = '******';
        elem.classList.add('password-hidden');
        event.target.textContent = '显示';
    }
}

function showAddStudentModal() {
    document.getElementById('newStudentId').value = '';
    document.getElementById('newStudentName').value = '';
    document.getElementById('newStudentPassword').value = '123456';
    showModal('addStudentModal');
}

async function addStudent() {
    const student_id = document.getElementById('newStudentId').value;
    const name = document.getElementById('newStudentName').value;
    const password = document.getElementById('newStudentPassword').value;
    
    const response = await fetch('/api/admin/students', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({student_id, name, password})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addStudentModal');
        loadStudents();
    } else {
        alert(data.message);
    }
}

async function deleteStudent(student_id) {
    if (!confirm('确定删除该学生？学生的学分记录将被保留。')) return;
    
    const response = await fetch('/api/admin/students', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({student_id})
    });
    
    const data = await response.json();
    if (data.success) {
        loadStudents();
    }
}

function showBatchStudentModal() {
    document.getElementById('batchStudentCSV').value = '';
    document.getElementById('batchStudentCSV').placeholder = '学号,姓名,密码\n2021001,张三,123456\n2021002,李四,123456';
    showModal('batchStudentModal');
}

async function batchImportStudents() {
    const csv_data = document.getElementById('batchStudentCSV').value;
    
    const response = await fetch('/api/admin/students/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({csv_data})
    });
    
    const data = await response.json();
    if (data.success) {
        alert(`导入成功！新增: ${data.added}, 更新: ${data.updated}${data.errors.length > 0 ? '\n错误: ' + data.errors.join(', ') : ''}`);
        closeModal('batchStudentModal');
        loadStudents();
    } else {
        alert(data.message);
    }
}

function exportStudentsCSV() {
    window.location.href = '/api/admin/students/export_csv';
}

// ========== 类别管理 ==========
async function loadCategories() {
    const response = await fetch('/api/admin/categories');
    const data = await response.json();
    
    if (data.success) {
        categories = data.categories;
        const tbody = document.querySelector('#categoriesTable tbody');
        tbody.innerHTML = '';
        
        data.categories.forEach(category => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${category.name}</td>
                <td>${category.required_credits}</td>
                <td>
                    <button class="danger" onclick="deleteCategory('${category.name}')">删除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

function showAddCategoryModal() {
    document.getElementById('newCategoryName').value = '';
    document.getElementById('newCategoryCredits').value = '';
    showModal('addCategoryModal');
}

async function addCategory() {
    const name = document.getElementById('newCategoryName').value;
    const required_credits = parseFloat(document.getElementById('newCategoryCredits').value);
    
    const response = await fetch('/api/admin/categories', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, required_credits})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addCategoryModal');
        loadCategories();
    } else {
        alert(data.message);
    }
}

async function deleteCategory(name) {
    if (!confirm('确定删除该类别？')) return;
    
    const response = await fetch('/api/admin/categories', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
    });
    
    const data = await response.json();
    if (data.success) {
        loadCategories();
    }
}

// ========== 总学分设置 ==========
async function loadTotalCredits() {
    const response = await fetch('/api/admin/total_credits');
    const data = await response.json();
    
    if (data.success) {
        document.getElementById('totalCredits').value = data.total_required_credits;
    }
}

async function saveTotalCredits() {
    const total_required_credits = parseFloat(document.getElementById('totalCredits').value);
    
    const response = await fetch('/api/admin/total_credits', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({total_required_credits})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('保存成功');
    }
}

// ========== 邮箱配置 ==========
async function loadEmailConfig() {
    const response = await fetch('/api/admin/email_config');
    const data = await response.json();
    
    if (data.success) {
        document.getElementById('serviceEmail').value = data.email_config.service_email || '';
        document.getElementById('serviceEmailPassword').value = data.email_config.service_email_password || '';
        document.getElementById('studentEmailSuffix').value = data.email_config.student_email_suffix || '';
    }
}

async function saveEmailConfig() {
    const service_email = document.getElementById('serviceEmail').value.trim();
    const service_email_password = document.getElementById('serviceEmailPassword').value;
    const student_email_suffix = document.getElementById('studentEmailSuffix').value.trim();
    
    // 验证邮箱格式
    if (service_email && !service_email.includes('@')) {
        alert('请输入有效的服务邮箱地址');
        return;
    }
    
    // 验证后缀格式
    if (student_email_suffix && !student_email_suffix.startsWith('@')) {
        alert('学生邮箱后缀应以@开头，如：@example.com');
        return;
    }
    
    const response = await fetch('/api/admin/email_config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            service_email,
            service_email_password,
            student_email_suffix
        })
    });
    
    const data = await response.json();
    if (data.success) {
        alert('邮箱配置保存成功');
    } else {
        alert(data.message || '保存失败');
    }
}

function showTestEmailModal() {
    document.getElementById('testEmailAddress').value = '';
    showModal('testEmailModal');
}

async function sendTestEmail() {
    const test_email = document.getElementById('testEmailAddress').value.trim();
    const debug = document.getElementById('debugMode').checked;
    
    if (!test_email) {
        alert('请输入测试邮箱地址');
        return;
    }
    
    if (!test_email.includes('@')) {
        alert('请输入有效的邮箱地址');
        return;
    }
    
    // 清空之前的调试信息
    const debugInfoDiv = document.getElementById('debugInfo');
    debugInfoDiv.style.display = 'none';
    debugInfoDiv.innerHTML = '';
    
    // 显示加载提示
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = '发送中...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/admin/test_email', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({test_email, debug})
        });
        
        const data = await response.json();
        
        // 显示调试信息
        if (debug && data.debug_info) {
            debugInfoDiv.innerHTML = data.debug_info.map(info => `<div>${info}</div>`).join('');
            debugInfoDiv.style.display = 'block';
        }
        
        if (data.success) {
            alert(data.message);
            if (!debug) {
                closeModal('testEmailModal');
            }
        } else {
            alert(data.message || '测试失败');
        }
    } catch (error) {
        alert('测试失败：' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ========== 部门管理 ==========
async function loadDepartments() {
    const response = await fetch('/api/admin/departments');
    const data = await response.json();
    
    if (data.success) {
        departments = data.departments;
        const tbody = document.querySelector('#departmentsTable tbody');
        tbody.innerHTML = '';
        
        data.departments.forEach(department => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${department}</td>
                <td>
                    <button class="danger" onclick="deleteDepartment('${department}')" ${currentAdminRole !== 'system_admin' ? 'disabled' : ''}>删除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

function showAddDepartmentModal() {
    if (currentAdminRole !== 'system_admin') {
        alert('仅系统管理员可以添加部门');
        return;
    }
    document.getElementById('newDepartmentName').value = '';
    showModal('addDepartmentModal');
}

async function addDepartment() {
    const department = document.getElementById('newDepartmentName').value.trim();
    
    if (!department) {
        alert('请输入部门名称');
        return;
    }
    
    const response = await fetch('/api/admin/departments', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({department})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addDepartmentModal');
        loadDepartments();
    } else {
        alert(data.message);
    }
}

async function deleteDepartment(department) {
    if (currentAdminRole !== 'system_admin') {
        alert('仅系统管理员可以删除部门');
        return;
    }
    
    if (!confirm(`确定删除部门"${department}"？`)) return;
    
    const response = await fetch('/api/admin/departments', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({department})
    });
    
    const data = await response.json();
    if (data.success) {
        loadDepartments();
    }
}

// ========== 管理员账号管理 ==========
async function loadAdmins() {
    const response = await fetch('/api/admin/admins');
    const data = await response.json();
    
    if (data.success) {
        const tbody = document.querySelector('#adminsTable tbody');
        tbody.innerHTML = '';
        
        data.admins.forEach(admin => {
            const roleName = admin.role === 'system_admin' ? '系统管理员' : '管理员';
            const tr = document.createElement('tr');
            
            // 判断是否是当前登录的管理员
            const isCurrentAdmin = admin.admin_id === currentAdminId;
            // 判断是否是系统管理员
            const isSystemAdmin = admin.role === 'system_admin';
            
            tr.innerHTML = `
                <td>${admin.admin_id}</td>
                <td>${roleName}</td>
                <td>${admin.department || '-'}</td>
                <td>
                    <button onclick="showChangeAdminPasswordModal('${admin.admin_id}')">修改密码</button>
                    ${!isCurrentAdmin ? `<button onclick="showChangeAdminDepartmentModal('${admin.admin_id}', '${admin.department || ''}')">修改部门</button>` : ''}
                    ${!isSystemAdmin ? `<button class="danger" onclick="deleteAdmin('${admin.admin_id}')">删除</button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

function showAddAdminModal() {
    if (currentAdminRole !== 'system_admin') {
        alert('仅系统管理员可以添加管理员');
        return;
    }
    
    document.getElementById('newAdminId').value = '';
    document.getElementById('newAdminPassword').value = 'admin123';
    document.getElementById('newAdminRole').value = 'admin';
    
    // 填充部门下拉框
    const deptSelect = document.getElementById('newAdminDepartment');
    deptSelect.innerHTML = '<option value="">无</option>';
    departments.forEach(dept => {
        const option = document.createElement('option');
        option.value = dept;
        option.textContent = dept;
        deptSelect.appendChild(option);
    });
    
    showModal('addAdminModal');
}

async function addAdmin() {
    const admin_id = document.getElementById('newAdminId').value.trim();
    const password = document.getElementById('newAdminPassword').value;
    const role = document.getElementById('newAdminRole').value;
    const department = document.getElementById('newAdminDepartment').value;
    
    if (!admin_id) {
        alert('请输入账号');
        return;
    }
    
    const response = await fetch('/api/admin/admins', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({admin_id, password, role, department})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addAdminModal');
        loadAdmins();
    } else {
        alert(data.message);
    }
}

function showChangeAdminPasswordModal(admin_id) {
    document.getElementById('changeAdminPasswordId').value = admin_id;
    document.getElementById('changeAdminPasswordIdDisplay').value = admin_id;
    document.getElementById('newAdminPasswordInput').value = '';
    showModal('changeAdminPasswordModal');
}

async function changeAdminPassword() {
    const admin_id = document.getElementById('changeAdminPasswordId').value;
    const password = document.getElementById('newAdminPasswordInput').value;
    
    if (!password) {
        alert('请输入新密码');
        return;
    }
    
    const response = await fetch('/api/admin/admins', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({admin_id, password})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('密码修改成功');
        closeModal('changeAdminPasswordModal');
        loadAdmins();
    } else {
        alert(data.message);
    }
}

function showChangeAdminDepartmentModal(admin_id, current_department) {
    document.getElementById('changeAdminDepartmentId').value = admin_id;
    document.getElementById('changeAdminDepartmentIdDisplay').value = admin_id;
    
    // 填充部门下拉框
    const deptSelect = document.getElementById('changeAdminDepartmentSelect');
    deptSelect.innerHTML = '<option value="">无</option>';
    departments.forEach(dept => {
        const option = document.createElement('option');
        option.value = dept;
        option.textContent = dept;
        if (dept === current_department) {
            option.selected = true;
        }
        deptSelect.appendChild(option);
    });
    
    showModal('changeAdminDepartmentModal');
}

async function changeAdminDepartment() {
    const admin_id = document.getElementById('changeAdminDepartmentId').value;
    const department = document.getElementById('changeAdminDepartmentSelect').value;
    
    const response = await fetch('/api/admin/admins', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({admin_id, department})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('部门修改成功');
        closeModal('changeAdminDepartmentModal');
        loadAdmins();
    } else {
        alert(data.message);
    }
}

async function deleteAdmin(admin_id) {
    if (!confirm(`确定删除管理员"${admin_id}"？`)) return;
    
    const response = await fetch('/api/admin/admins', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({admin_id})
    });
    
    const data = await response.json();
    if (data.success) {
        loadAdmins();
    } else {
        alert(data.message);
    }
}

// ========== 活动权限管理 ==========
async function showActivityPermissionModal(activity_id) {
    const activity = activities.find(a => a.activity_id === activity_id);
    if (!activity) return;
    
    document.getElementById('permissionActivityId').value = activity_id;
    document.getElementById('permissionActivityName').value = activity.name;
    
    // 生成部门复选框
    const deptContainer = document.getElementById('permissionDepartmentsCheckbox');
    deptContainer.innerHTML = '';
    
    const currentDepts = activity.department ? activity.department.split(', ') : [];
    departments.forEach(dept => {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        const checked = currentDepts.includes(dept) ? 'checked' : '';
        div.innerHTML = `
            <input type="checkbox" id="perm-dept-${dept}" value="${dept}" ${checked}>
            <label for="perm-dept-${dept}">${dept}</label>
        `;
        deptContainer.appendChild(div);
    });
    
    // 获取所有管理员列表
    const adminsResponse = await fetch('/api/admin/admins');
    const adminsData = await adminsResponse.json();
    
    if (adminsData.success) {
        const adminsContainer = document.getElementById('permissionAdminsCheckbox');
        adminsContainer.innerHTML = '';
        
        adminsData.admins.forEach(admin => {
            // 跳过系统管理员
            if (admin.role === 'system_admin') return;
            
            const div = document.createElement('div');
            div.className = 'checkbox-item';
            const checked = activity.allowed_editors.includes(admin.admin_id) ? 'checked' : '';
            const deptInfo = admin.department ? ` (${admin.department})` : '';
            div.innerHTML = `
                <input type="checkbox" id="perm-admin-${admin.admin_id}" value="${admin.admin_id}" ${checked}>
                <label for="perm-admin-${admin.admin_id}">${admin.admin_id}${deptInfo}</label>
            `;
            adminsContainer.appendChild(div);
        });
    }
    
    showModal('activityPermissionModal');
}

async function saveActivityPermission() {
    const activity_id = document.getElementById('permissionActivityId').value;
    
    // 获取选中的部门
    const selectedDepts = [];
    departments.forEach(dept => {
        const checkbox = document.getElementById(`perm-dept-${dept}`);
        if (checkbox && checkbox.checked) {
            selectedDepts.push(dept);
        }
    });
    
    // 获取选中的管理员
    const selectedAdmins = [];
    document.querySelectorAll('#permissionAdminsCheckbox input:checked').forEach(cb => {
        selectedAdmins.push(cb.value);
    });
    
    const department = selectedDepts.join(', ');
    
    const response = await fetch('/api/admin/activities', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            activity_id,
            department,
            allowed_editors: selectedAdmins
        })
    });
    
    const data = await response.json();
    if (data.success) {
        alert('权限设置成功');
        closeModal('activityPermissionModal');
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

// ========== 活动管理 ==========
async function loadActivities() {
    const response = await fetch('/api/admin/activities');
    const data = await response.json();
    
    if (data.success) {
        activities = data.activities;
        const container = document.getElementById('activitiesList');
        container.innerHTML = '';
        
        for (const activity of data.activities) {
            const activityDiv = document.createElement('div');
            activityDiv.className = 'info-card';
            
            // 部门信息（仅管理员可见）
            const deptInfo = activity.department ? `<p><strong>负责部门：</strong>${activity.department}</p>` : '';
            
            // 权限管理按钮（仅系统管理员可见）
            const permissionBtn = currentAdminRole === 'system_admin' ? 
                `<button class="secondary" onclick="showActivityPermissionModal('${activity.activity_id}')">权限管理</button>` : '';
            
            // 根据权限显示按钮
            const canEdit = activity.can_edit;
            const editCategoryBtn = canEdit ? `<button class="secondary" onclick="showEditActivityCategoriesModal('${activity.activity_id}')">修改类别</button>` : '';
            const editButtons = canEdit ? `
                <button class="add-btn" onclick="showAddRecordModal('${activity.activity_id}')">添加记录</button>
                <button class="danger" onclick="deleteActivity('${activity.activity_id}')">删除活动</button>
            ` : '<p style="color: #999; font-size: 14px;">无编辑权限</p>';
            
            activityDiv.innerHTML = `
                <h3>${activity.name}</h3>
                <p><strong>类别：</strong>${activity.categories.join(', ')}</p>
                ${deptInfo}
                <div style="margin-top: 12px;">
                    ${editButtons}
                    ${editCategoryBtn}
                    ${permissionBtn}
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
        loadActivities();  // 刷新活动列表
    }
}

function showAddActivityModal() {
    document.getElementById('newActivityName').value = '';
    
    // 生成部门复选框
    const deptContainer = document.getElementById('activityDepartmentsCheckbox');
    deptContainer.innerHTML = '';
    
    departments.forEach(department => {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        div.innerHTML = `
            <input type="checkbox" id="act-dept-${department}" value="${department}">
            <label for="act-dept-${department}">${department}</label>
        `;
        deptContainer.appendChild(div);
    });
    
    // 生成类别复选框
    const container = document.getElementById('activityCategoriesCheckbox');
    container.innerHTML = '';
    
    categories.forEach(category => {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        div.innerHTML = `
            <input type="checkbox" id="act-cat-${category.name}" value="${category.name}">
            <label for="act-cat-${category.name}">${category.name}</label>
        `;
        container.appendChild(div);
    });
    
    showModal('addActivityModal');
}

async function addActivity() {
    const name = document.getElementById('newActivityName').value;
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
    
    const department = selectedDepartments.join(', ');
    
    const response = await fetch('/api/admin/activities', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, categories: selectedCategories, department})
    });
    
    const data = await response.json();
    if (data.success) {
        closeModal('addActivityModal');
        loadActivities();
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
        // 显示记录详情，可以添加条目
        showRecordDetail(data.record_id);
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

function showAddEntryModal(record_id) {
    document.getElementById('entryRecordId').value = record_id;
    document.getElementById('newEntryStudentId').value = '';
    document.getElementById('newEntryCredits').value = '';
    
    // 生成类别复选框
    const container = document.getElementById('entryCategoriesCheckbox');
    container.innerHTML = '';
    
    categories.forEach(category => {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        div.innerHTML = `
            <input type="checkbox" id="entry-cat-${category.name}" value="${category.name}">
            <label for="entry-cat-${category.name}">${category.name}</label>
        `;
        container.appendChild(div);
    });
    
    showModal('addEntryModal');
}

async function addEntry() {
    const record_id = document.getElementById('entryRecordId').value;
    const student_id = document.getElementById('newEntryStudentId').value;
    const credits = parseFloat(document.getElementById('newEntryCredits').value);
    const selectedCategories = [];
    
    categories.forEach(category => {
        const checkbox = document.getElementById(`entry-cat-${category.name}`);
        if (checkbox && checkbox.checked) {
            selectedCategories.push(category.name);
        }
    });
    
    const response = await fetch('/api/admin/entries', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({record_id, student_id, credits, categories: selectedCategories})
    });
    
    const data = await response.json();
    if (data.success) {
        alert('添加成功');
        // 可以继续添加更多条目
        document.getElementById('newEntryStudentId').value = '';
        document.getElementById('newEntryCredits').value = '';
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
    // 获取活动类别
    const response = await fetch(`/api/admin/records/${record_id}`);
    const data = await response.json();
    
    if (data.success) {
        const activityCategories = data.record.activity_categories;
        
        // 设置隐藏字段
        document.getElementById('editEntryRecordId').value = record_id;
        document.getElementById('editEntryStudentId').value = student_id;
        document.getElementById('editEntryStudentIdDisplay').value = student_id;
        document.getElementById('editEntryCredits').value = credits;
        
        // 生成类别复选框
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
    
    // 获取选中的类别
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
    }
}

async function showBatchEntryModal() {
    const record_id = document.getElementById('detailRecordId').value;
    
    // 获取活动类别
    const response = await fetch(`/api/admin/records/${record_id}`);
    const data = await response.json();
    
    if (data.success) {
        const activityCategories = data.record.activity_categories;
        
        // 生成类别复选框
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
    
    // 获取选中的类别
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
    }
}

// ========== 批量修改条目 ==========
function showBatchUpdateModal() {
    const record_id = document.getElementById('detailRecordId').value;
    document.getElementById('batchUpdateRecordId').value = record_id;
    document.getElementById('batchUpdateCredits').value = '';
    
    // 获取活动类别
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
    
    // 获取选中的类别
    const selectedCategories = [];
    document.querySelectorAll('#batchUpdateCategoriesCheckbox input:checked').forEach(cb => {
        selectedCategories.push(cb.value);
    });
    
    const new_categories = selectedCategories.length > 0 ? selectedCategories : null;
    
    if (new_credits === null && new_categories === null) {
        alert('请至少修改学分或类别');
        return;
    }
    
    // 获取选中的学生
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
    
    // 4. 学生列表（可排序，默认按学号）
    html += '<div class="info-card"><h3>学生列表</h3>';
    html += '<div style="margin-bottom: 10px;">排序：';
    html += '<button onclick="sortStudents(\'student_id\')">按学号</button>';
    html += '<button onclick="sortStudents(\'student_name\')">按姓名</button>';
    html += '<button onclick="sortStudents(\'total_credits\')">按总学分</button>';
    html += '<button onclick="sortStudents(\'final_qualified\')">按合格状态</button>';
    html += '</div>';
    html += '<table id="studentsReportTable"><thead><tr><th>学号</th><th>姓名</th><th>总学分</th><th>最终合格</th></tr></thead><tbody>';
    
    // 默认按学号排序
    const sortedStudents = [...data.students].sort((a, b) => a.student_id.localeCompare(b.student_id));
    sortedStudents.forEach(student => {
        html += `<tr>
            <td>${student.student_id}</td>
            <td>${student.student_name}</td>
            <td>${student.total_credits}</td>
            <td><span class="status-badge ${student.final_qualified ? 'status-qualified' : 'status-unqualified'}">
                ${student.final_qualified ? '✓ 已合格' : '✗ 未合格'}
            </span></td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    
    document.getElementById('reportContent').innerHTML = html;
    
    // 保存数据供排序使用
    window.reportStudents = data.students;
}

function sortStudents(key) {
    if (!window.reportStudents) return;
    
    const students = [...window.reportStudents];
    students.sort((a, b) => {
        if (key === 'student_id' || key === 'student_name') {
            return a[key].localeCompare(b[key]);
        } else if (key === 'total_credits') {
            return b[key] - a[key];
        } else if (key === 'final_qualified') {
            return (b[key] ? 1 : 0) - (a[key] ? 1 : 0);
        }
        return 0;
    });
    
    const tbody = document.querySelector('#studentsReportTable tbody');
    tbody.innerHTML = '';
    students.forEach(student => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${student.student_id}</td>
            <td>${student.student_name}</td>
            <td>${student.total_credits}</td>
            <td><span class="status-badge ${student.final_qualified ? 'status-qualified' : 'status-unqualified'}">
                ${student.final_qualified ? '✓ 已合格' : '✗ 未合格'}
            </span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ========== 查询功能 ==========
let currentQueryData = null;

async function queryStudent() {
    const query = document.getElementById('queryInput').value;
    
    const response = await fetch('/api/query/student', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query})
    });
    
    const data = await response.json();
    
    if (data.success) {
        currentQueryData = data;
        displayQueryResult(data);
        document.getElementById('exportQueryBtn').style.display = 'block';
    } else {
        alert(data.message);
        document.getElementById('exportQueryBtn').style.display = 'none';
    }
}

function displayQueryResult(data) {
    let html = `
        <div class="info-card">
            <h3>学生信息</h3>
            <p><strong>学号：</strong>${data.student_id}</p>
            <p><strong>姓名：</strong>${data.student_name}</p>
        </div>

        <div class="info-card">
            <h3>总学分情况</h3>
            <p><strong>已获得学分：</strong>${data.total_credits}</p>
            <p><strong>合格学分：</strong>${data.total_required}</p>
            <p><strong>总学分状态：</strong>
                <span class="status-badge ${data.total_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${data.total_qualified ? '已合格' : '未合格'}
                </span>
            </p>
            <p><strong>所有类别状态：</strong>
                <span class="status-badge ${data.all_categories_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${data.all_categories_qualified ? '已合格' : '未合格'}
                </span>
            </p>
            <p style="margin-top: 10px; padding-top: 10px; border-top: 2px solid #ddd;"><strong>最终合格情况：</strong>
                <span class="status-badge ${data.final_qualified ? 'status-qualified' : 'status-unqualified'}" style="font-size: 16px;">
                    ${data.final_qualified ? '✓ 已合格' : '✗ 未合格'}
                </span>
            </p>
        </div>

        <div class="info-card">
            <h3>各类别学分情况</h3>
            <table>
                <thead>
                    <tr>
                        <th>类别</th>
                        <th>已获得学分</th>
                        <th>合格学分</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
    `;

    for (const [category, status] of Object.entries(data.category_status)) {
        html += `
            <tr>
                <td>${category}</td>
                <td>${status.credits}</td>
                <td>${status.required}</td>
                <td>
                    <span class="status-badge ${status.qualified ? 'status-qualified' : 'status-unqualified'}">
                        ${status.qualified ? '已合格' : '未合格'}
                    </span>
                </td>
            </tr>
        `;
    }

    html += `
                </tbody>
            </table>
        </div>

        <div class="info-card">
            <h3>活动参与记录</h3>
            <table>
                <thead>
                    <tr>
                        <th>活动名称</th>
                        <th>记录名称</th>
                        <th>学分</th>
                        <th>可选类别</th>
                        <th>计入类别</th>
                    </tr>
                </thead>
                <tbody>
    `;

    data.activities.forEach(activity => {
        html += `
            <tr>
                <td>${activity.activity_name}</td>
                <td>${activity.record_name}</td>
                <td>${activity.credits}</td>
                <td>${activity.categories.join(', ')}</td>
                <td>${activity.assigned_category || '-'}</td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    document.getElementById('queryResult').innerHTML = html;
}

// ========== 数据导出 ==========
let allStudentsData = [];

async function loadAllStudentsCredits() {
    const response = await fetch('/api/admin/all_students_credits');
    const data = await response.json();
    
    if (data.success) {
        // 按学号排序并保存
        allStudentsData = [...data.students].sort((a, b) => a.student_id.localeCompare(b.student_id));
        renderAllStudentsTable(allStudentsData);
    }
}

function renderAllStudentsTable(studentsToRender) {
    const tbody = document.querySelector('#allStudentsTable tbody');
    tbody.innerHTML = '';
    
    studentsToRender.forEach(student => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${student.student_id}</td>
            <td>${student.student_name}</td>
            <td>${student.total_credits}</td>
            <td>
                <span class="status-badge ${student.total_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${student.total_qualified ? '已合格' : '未合格'}
                </span>
            </td>
            <td>
                <span class="status-badge ${student.all_categories_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${student.all_categories_qualified ? '已合格' : '未合格'}
                </span>
            </td>
            <td>
                <span class="status-badge ${student.final_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${student.final_qualified ? '✓ 已合格' : '✗ 未合格'}
                </span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterAllStudents() {
    const query = document.getElementById('allStudentsSearchInput').value.toLowerCase().trim();
    
    if (!query) {
        renderAllStudentsTable(allStudentsData);
        return;
    }
    
    const filtered = allStudentsData.filter(student => 
        student.student_id.toLowerCase().includes(query) || 
        student.student_name.toLowerCase().includes(query)
    );
    
    renderAllStudentsTable(filtered);
}

function exportData() {
    window.location.href = '/api/admin/export';
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

// ========== PDF导出功能 ==========
function exportQueryToPDF() {
    if (!currentQueryData) {
        alert('没有可导出的数据');
        return;
    }
    
    // 创建打印样式
    const printStyle = document.createElement('style');
    printStyle.textContent = `
        @media print {
            @page {
                margin: 10mm;
                size: A4;
            }
            * {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }
            html, body {
                margin: 0;
                padding: 0;
                height: auto;
                background: white !important;
            }
            body * { 
                visibility: hidden; 
            }
            .print-area, .print-area * { 
                visibility: visible; 
            }
            .print-area {
                position: absolute;
                left: 0;
                top: 0;
                width: 100%;
                background: white !important;
                font-family: 'Microsoft YaHei', sans-serif;
            }
            .print-title {
                text-align: center;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 12px;
                border-bottom: 2px solid #E53935;
                padding-bottom: 6px;
                color: #C62828;
            }
            .print-info {
                margin-bottom: 10px;
                padding: 8px;
                border: 1px solid #EF5350;
                border-radius: 4px;
                background: #FFEBEE !important;
            }
            .info-card {
                margin-bottom: 10px;
                padding: 8px;
                border: 1px solid #EF5350;
                border-radius: 4px;
                background: #FFCDD2 !important;
                page-break-inside: avoid;
            }
            .info-card h3 {
                margin: 0 0 6px 0;
                font-size: 15px;
                color: #C62828;
            }
            .info-card p {
                margin: 3px 0;
                font-size: 13px;
            }
            .status-badge {
                display: inline-block;
                padding: 2px 8px;
                font-size: 12px;
                border-radius: 3px;
            }
            .status-qualified { 
                background: #d4edda !important;
                color: #155724 !important;
            }
            .status-unqualified { 
                background: #f8d7da !important;
                color: #721c24 !important;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 6px 0;
                font-size: 12px;
                border: 1px solid #EF5350;
            }
            th, td {
                border: 1px solid #FFCDD2;
                padding: 5px 6px;
                text-align: left;
            }
            th { 
                font-weight: bold;
                background: #FFEBEE !important;
                color: #C62828;
            }
        }
    `;
    document.head.appendChild(printStyle);
    
    // 创建打印内容
    const printContent = createQueryPrintContent(currentQueryData);
    
    // 创建打印区域
    const printArea = document.createElement('div');
    printArea.className = 'print-area';
    printArea.innerHTML = printContent;
    document.body.appendChild(printArea);
    
    // 打印
    window.print();
    
    // 清理
    setTimeout(() => {
        document.body.removeChild(printArea);
        document.head.removeChild(printStyle);
    }, 100);
}

function createQueryPrintContent(data) {
    const now = new Date().toLocaleString('zh-CN');
    
    let html = `
        <div class="print-title">团校积分系统 - 学分报告</div>
        
        <div class="print-info">
            <strong>学号：</strong>${data.student_id} &nbsp;&nbsp;&nbsp;
            <strong>姓名：</strong>${data.student_name} &nbsp;&nbsp;&nbsp;
            <strong>导出时间：</strong>${now}
        </div>
        
        <div class="info-card">
            <h3>总学分情况</h3>
            <p><strong>已获得学分：</strong>${data.total_credits}</p>
            <p><strong>合格学分：</strong>${data.total_required}</p>
            <p><strong>总学分状态：</strong>
                <span class="status-badge ${data.total_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${data.total_qualified ? '✓ 已合格' : '✗ 未合格'}
                </span>
            </p>
            <p><strong>所有类别状态：</strong>
                <span class="status-badge ${data.all_categories_qualified ? 'status-qualified' : 'status-unqualified'}">
                    ${data.all_categories_qualified ? '✓ 已合格' : '✗ 未合格'}
                </span>
            </p>
        </div>
        
        <div class="info-card">
            <h3>各类别学分情况</h3>
            <table>
                <thead>
                    <tr>
                        <th>类别名称</th>
                        <th>已获学分</th>
                        <th>合格学分</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    for (const [category, status] of Object.entries(data.category_status)) {
        html += `
            <tr>
                <td>${category}</td>
                <td>${status.credits}</td>
                <td>${status.required}</td>
                <td>
                    <span class="status-badge ${status.qualified ? 'status-qualified' : 'status-unqualified'}">
                        ${status.qualified ? '✓ 已合格' : '✗ 未合格'}
                    </span>
                </td>
            </tr>
        `;
    }
    
    html += `
                </tbody>
            </table>
        </div>
        
        <div class="info-card">
            <h3>参与活动详情</h3>
            <table>
                <thead>
                    <tr>
                        <th>活动名称</th>
                        <th>记录名称</th>
                        <th>学分</th>
                        <th>可选类别</th>
                        <th>计入类别</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.activities.forEach(activity => {
        html += `
            <tr>
                <td>${activity.activity_name}</td>
                <td>${activity.record_name}</td>
                <td>${activity.credits}</td>
                <td>${activity.categories.join(', ')}</td>
                <td>${activity.assigned_category || '-'}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
        
        <div class="info-card" style="text-align: center; font-size: 18px; font-weight: bold;">
            最终合格状态：
            <span class="status-badge ${data.final_qualified ? 'status-qualified' : 'status-unqualified'}">
                ${data.final_qualified ? '✓ 已合格' : '✗ 未合格'}
            </span>
        </div>
    `;
    
    return html;
}


