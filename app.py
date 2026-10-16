"""
团校积分系统 - Flask 主应用

这是一个完整的学分管理系统，包含以下功能：
- 学生管理和认证
- 活动和学分记录管理
- 智能学分分配算法（DFS + 剪枝）
- 数据报表和统计
- 批量操作支持

技术栈：
- Flask 3.0.0
- 原生 HTML/CSS/JavaScript
- JSON 文件存储（含并发控制）
- SHA-256 密码哈希

作者：团校积分系统开发组
版本：v2.4
"""
from flask import Flask, render_template, request, jsonify, session, send_file, send_from_directory, redirect, url_for, Response
from flask_cors import CORS
from database import Database
from models import Activity, Record, Entry, Student, Category
import openpyxl
from openpyxl.styles import Font, Alignment
import io
import os
import uuid
import csv
import hashlib
import time

app = Flask(__name__)
app.secret_key = 'cjtxjfxtweb'

# Session 配置（确保在所有环境下都能正常工作）
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_DOMAIN=None,  # 允许在任何域名（包括 IP）下工作
    PERMANENT_SESSION_LIFETIME=3600,
    SESSION_REFRESH_EACH_REQUEST=True,
)

CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # 允许所有来源（开发环境）
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": True  # 支持 Cookie
    }
})

db = Database()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

# 生成混淆的管理员登录路径
import secrets
ADMIN_LOGIN_PATH = secrets.token_urlsafe(16)

@app.route(f'/{ADMIN_LOGIN_PATH}')
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/api/login/student', methods=['POST'])
def student_login():
    """学生登录（仅限学生）"""
    data = request.json
    username = data.get('username')
    password_hash = data.get('password_hash')  # 客户端已经哈希过的密码
    
    # 只检查学生
    if username in db.students:
        student = db.students[username]
        # 对服务器存储的明文密码进行哈希，与客户端发送的哈希比较
        server_password_hash = hashlib.sha256(student.password.encode('utf-8')).hexdigest()
        if server_password_hash == password_hash:
            session['user_type'] = 'student'
            session['student_id'] = username
            session['student_name'] = student.name
            
            # 检查是否有注册问卷，没有则自动创建
            has_questionnaire = any(q.student_id == username for q in db.registration_questionnaires.values())
            if not has_questionnaire:
                from datetime import datetime
                from models import RegistrationQuestionnaire
                questionnaire_id = str(uuid.uuid4())
                submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                questionnaire = RegistrationQuestionnaire(
                    questionnaire_id=questionnaire_id,
                    student_id=username,
                    name=student.name,
                    phone='',
                    wechat='',
                    suggestion='',
                    submit_time=submit_time
                )
                db.registration_questionnaires[questionnaire_id] = questionnaire
                db.save_data()
            
            return jsonify({'success': True, 'user_type': 'student'})
    
    return jsonify({'success': False, 'message': '学号或密码错误'})

@app.route('/api/student/register', methods=['POST'])
def student_register():
    """学生注册 - 创建学生账号和注册问卷"""
    data = request.json
    name = data.get('name', '').strip()
    student_id = data.get('student_id', '').strip()
    phone = data.get('phone', '').strip()
    wechat = data.get('wechat', '').strip()
    password = data.get('password', '')
    suggestion = data.get('suggestion', '').strip()
    
    # 验证必填字段
    if not all([name, student_id, phone, wechat, password]):
        return jsonify({'success': False, 'message': '请填写所有必填项'})
    
    # 验证学号格式（只能包含数字）
    if not student_id.isdigit():
        return jsonify({'success': False, 'message': '学号只能包含数字'})
    
    # 验证学号是否已存在
    if student_id in db.students:
        return jsonify({'success': False, 'message': '该学号已注册，请直接登录'})
    
    # 验证手机号格式
    import re
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({'success': False, 'message': '请输入正确的手机号码'})
    
    # 验证密码长度
    if len(password) < 6:
        return jsonify({'success': False, 'message': '密码至少需要6位字符'})
    
    # 创建学生账号（只包含基本信息）
    student = Student(
        student_id=student_id,
        name=name,
        password=password,
        password_reset_required=False
    )
    db.students[student_id] = student
    
    # 创建注册问卷记录
    from datetime import datetime
    import uuid
    from models import RegistrationQuestionnaire
    
    questionnaire_id = str(uuid.uuid4())
    submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    questionnaire = RegistrationQuestionnaire(
        questionnaire_id=questionnaire_id,
        student_id=student_id,
        name=name,
        phone=phone,
        wechat=wechat,
        suggestion=suggestion,
        submit_time=submit_time
    )
    
    db.registration_questionnaires[questionnaire_id] = questionnaire
    db.save_data()
    
    return jsonify({'success': True, 'message': '注册成功！请使用学号和密码登录'})

@app.route('/api/login/admin', methods=['POST'])
def admin_login():
    """管理员登录（仅限管理员）"""
    data = request.json
    username = data.get('username')
    password_hash = data.get('password_hash')  # 客户端已经哈希过的密码
    
    # 只检查管理员
    if username in db.admins:
        admin = db.admins[username]
        # 对服务器存储的明文密码进行哈希，与客户端发送的哈希比较
        server_password_hash = hashlib.sha256(admin.password.encode('utf-8')).hexdigest()
        if server_password_hash == password_hash:
            session['user_type'] = 'admin'
            session['admin_id'] = username
            session['admin_role'] = admin.role
            session['admin_department'] = admin.department
            
            # 系统管理员登录时，检查所有学生是否都有注册问卷
            if admin.role == 'system_admin':
                from datetime import datetime
                from models import RegistrationQuestionnaire
                created_count = 0
                
                for student_id, student in db.students.items():
                    has_questionnaire = any(q.student_id == student_id for q in db.registration_questionnaires.values())
                    if not has_questionnaire:
                        questionnaire_id = str(uuid.uuid4())
                        submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        questionnaire = RegistrationQuestionnaire(
                            questionnaire_id=questionnaire_id,
                            student_id=student_id,
                            name=student.name,
                            phone='',
                            wechat='',
                            suggestion='',
                            submit_time=submit_time
                        )
                        db.registration_questionnaires[questionnaire_id] = questionnaire
                        created_count += 1
                
                if created_count > 0:
                    db.save_data()
            
            return jsonify({
                'success': True, 
                'user_type': 'admin',
                'role': admin.role,
                'department': admin.department
            })
    
    return jsonify({'success': False, 'message': '账号或密码错误'})

@app.route('/api/logout', methods=['POST'])
def logout():
    user_type = session.get('user_type')
    session.clear()
    
    # 如果是管理员，返回管理员登录路径
    if user_type == 'admin':
        return jsonify({'success': True, 'admin_login_path': ADMIN_LOGIN_PATH})
    else:
        return jsonify({'success': True})

@app.route('/api/admin/session_info', methods=['GET'])
def get_session_info():
    """获取当前管理员的 session 信息"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    return jsonify({
        'success': True,
        'admin_id': session.get('admin_id', ''),
        'role': session.get('admin_role', 'admin'),
        'department': session.get('admin_department', '')
    })

@app.route('/admin')
def admin_page():
    if session.get('user_type') != 'admin':
        return redirect('/')
    
    # 根据角色路由到不同的页面
    if session.get('admin_role') == 'system_admin':
        return render_template('admin.html')
    else:
        return render_template('normal_admin.html')

@app.route('/admin/registration_questionnaires')
def registration_questionnaires_page():
    """注册问卷管理页面（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return redirect('/')
    
    if session.get('admin_role') != 'system_admin':
        return redirect('/admin')
    
    return render_template('registration_questionnaires.html')

@app.route('/student')
def student_page():
    if session.get('user_type') != 'student':
        return redirect('/')
    return render_template('student.html')

@app.route('/student/activity_registration')
def student_activity_registration():
    if session.get('user_type') != 'student':
        return redirect('/')
    return render_template('activity_registration.html')

@app.route('/student/registration_questionnaire')
def student_registration_questionnaire():
    if session.get('user_type') != 'student':
        return redirect('/')
    return render_template('student_registration_questionnaire.html')

# ========== 系统设置 API ==========

@app.route('/api/admin/students', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_students():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'GET':
        # 普通管理员可以查看学生列表（不含密码）
        is_system_admin = session.get('admin_role') == 'system_admin'
        
        # 按学号排序
        sorted_students = sorted(db.students.items(), key=lambda x: x[0])
        
        if is_system_admin:
            # 系统管理员可以看到密码
            students_list = [{'student_id': sid, 'name': s.name, 'password': s.password} 
                            for sid, s in sorted_students]
        else:
            # 普通管理员只能看到学号和姓名
            students_list = [{'student_id': sid, 'name': s.name} 
                            for sid, s in sorted_students]
        
        return jsonify({'success': True, 'students': students_list, 'can_edit': is_system_admin})
    
    # 其他操作只有系统管理员可以执行
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以管理学生'}), 403
    
    elif request.method == 'POST':
        data = request.json
        student_id = data.get('student_id', '').strip()
        name = data.get('name', '').strip()
        password = data.get('password', '123456')
        
        # 验证学号只能是数字
        if not student_id.isdigit():
            return jsonify({'success': False, 'message': '学号只能包含数字'})
        
        if not name:
            return jsonify({'success': False, 'message': '姓名不能为空'})
        
        if student_id in db.students:
            return jsonify({'success': False, 'message': '学号已存在'})
        
        # 创建学生账号
        db.students[student_id] = Student(student_id, name, password)
        
        # 自动创建空白注册问卷
        from datetime import datetime
        questionnaire_id = str(uuid.uuid4())
        submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        from models import RegistrationQuestionnaire
        questionnaire = RegistrationQuestionnaire(
            questionnaire_id=questionnaire_id,
            student_id=student_id,
            name=name,
            phone='',  # 空白
            wechat='',  # 空白
            suggestion='',  # 空白
            submit_time=submit_time
        )
        db.registration_questionnaires[questionnaire_id] = questionnaire
        
        db.save_data()
        return jsonify({'success': True, 'message': '已添加学生并创建空白问卷'})
    
    elif request.method == 'PUT':
        data = request.json
        student_id = data.get('student_id')
        
        if student_id not in db.students:
            return jsonify({'success': False, 'message': '学生不存在'})
        
        if 'name' in data:
            db.students[student_id].name = data['name']
        if 'password' in data:
            db.students[student_id].password = data['password']
        
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        student_id = request.json.get('student_id')
        if student_id in db.students:
            # 删除学生
            del db.students[student_id]
            
            # 自动删除该学生的所有问卷
            # 删除注册问卷
            reg_questionnaires_to_delete = [qid for qid, q in db.registration_questionnaires.items() 
                                           if q.student_id == student_id]
            for qid in reg_questionnaires_to_delete:
                del db.registration_questionnaires[qid]
            
            # 删除活动问卷
            act_questionnaires_to_delete = [qid for qid, q in db.activity_questionnaires.items() 
                                           if q.student_id == student_id]
            for qid in act_questionnaires_to_delete:
                del db.activity_questionnaires[qid]
            
            db.save_data()
            return jsonify({'success': True, 'message': f'已删除学生及其{len(reg_questionnaires_to_delete) + len(act_questionnaires_to_delete)}条问卷记录'})
        return jsonify({'success': False, 'message': '学生不存在'})

@app.route('/api/admin/categories', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_categories():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'GET':
        # 所有管理员都可以查看类别
        categories_list = [{'name': cname, 'required_credits': c.required_credits} 
                          for cname, c in db.categories.items()]
        return jsonify({'success': True, 'categories': categories_list})
    
    # 其他操作只有系统管理员可以执行
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以管理类别'}), 403
    
    elif request.method == 'POST':
        data = request.json
        name = data.get('name')
        required_credits = data.get('required_credits', 0)
        
        if name in db.categories:
            return jsonify({'success': False, 'message': '类别已存在'})
        
        db.categories[name] = Category(name, required_credits)
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        data = request.json
        name = data.get('name')
        
        if name not in db.categories:
            return jsonify({'success': False, 'message': '类别不存在'})
        
        if 'required_credits' in data:
            db.categories[name].required_credits = data['required_credits']
        
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        name = request.json.get('name')
        if name in db.categories:
            del db.categories[name]
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '类别不存在'})

@app.route('/api/admin/total_credits', methods=['GET', 'POST'])
def manage_total_credits():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 只有系统管理员可以管理总学分
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以管理总学分'}), 403
    
    if request.method == 'GET':
        return jsonify({'success': True, 'total_required_credits': db.total_required_credits})
    
    elif request.method == 'POST':
        data = request.json
        db.total_required_credits = data.get('total_required_credits', 0)
        db.save_data()
        return jsonify({'success': True})

# ========== 邮箱配置 API ==========

@app.route('/api/admin/email_config', methods=['GET', 'POST'])
def manage_email_config():
    """邮箱配置管理API（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 只有系统管理员可以管理邮箱配置
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以管理邮箱配置'}), 403
    
    if request.method == 'GET':
        # 返回配置（不包含密码）
        safe_config = {
            'service_email': db.email_config.get('service_email', ''),
            'student_email_suffix': db.email_config.get('student_email_suffix', ''),
            'has_password': bool(db.email_config.get('service_email_password', ''))
        }
        return jsonify({
            'success': True,
            'email_config': safe_config
        })
    
    elif request.method == 'POST':
        data = request.json
        db.email_config['service_email'] = data.get('service_email', '')
        db.email_config['student_email_suffix'] = data.get('student_email_suffix', '')
        
        # 只有提供了新密码才更新
        if data.get('service_email_password'):
            db.email_config['service_email_password'] = data['service_email_password']
        
        db.save_data()
        return jsonify({'success': True})

@app.route('/api/admin/test_email', methods=['POST'])
def test_email_config():
    """测试邮箱配置（仅系统管理员）"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以测试邮箱配置'}), 403
    
    data = request.json
    test_email = data.get('test_email', '')
    debug_mode = data.get('debug', False)
    
    if not test_email:
        return jsonify({'success': False, 'message': '请输入测试邮箱地址'})
    
    debug_info = []
    
    # 检查邮箱配置
    service_email = db.email_config.get('service_email', '')
    service_password = db.email_config.get('service_email_password', '')
    
    if not service_email or not service_password:
        return jsonify({'success': False, 'message': '请先配置服务邮箱'})
    
    if debug_mode:
        debug_info.append(f'服务邮箱: {service_email}')
        debug_info.append(f'密码长度: {len(service_password)} 字符')
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = service_email
        msg['To'] = test_email
        msg['Subject'] = '团校积分系统 - 邮箱配置测试'
        
        body = """这是一封测试邮件。

如果您收到这封邮件，说明邮箱配置成功！

---
团校积分系统"""
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 根据邮箱类型选择SMTP服务器
        if 'qq.com' in service_email:
            smtp_server = 'smtp.qq.com'
            smtp_port = 587
            use_ssl = False
            email_type = 'QQ邮箱'
        elif '163.com' in service_email:
            smtp_server = 'smtp.163.com'
            smtp_port = 465
            use_ssl = True
            email_type = '163邮箱'
        elif '126.com' in service_email:
            smtp_server = 'smtp.126.com'
            smtp_port = 465
            use_ssl = True
            email_type = '126邮箱'
        elif 'gmail.com' in service_email:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
            use_ssl = False
            email_type = 'Gmail'
        elif 'outlook.com' in service_email or 'hotmail.com' in service_email or 'live.com' in service_email:
            smtp_server = 'smtp-mail.outlook.com'
            smtp_port = 587
            use_ssl = False
            email_type = 'Outlook'
        else:
            smtp_server = 'smtp.' + service_email.split('@')[1]
            smtp_port = 587
            use_ssl = False
            email_type = '自动检测'
        
        if debug_mode:
            debug_info.append(f'邮箱类型: {email_type}')
            debug_info.append(f'SMTP服务器: {smtp_server}')
            debug_info.append(f'端口: {smtp_port}')
            debug_info.append(f'连接方式: {"SSL" if use_ssl else "TLS"}')
            debug_info.append('正在连接服务器...')
        
        # 连接并发送
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
        
        if debug_mode:
            debug_info.append('正在登录...')
        
        server.login(service_email, service_password)
        
        if debug_mode:
            debug_info.append('正在发送邮件...')
        
        server.send_message(msg)
        server.quit()
        
        if debug_mode:
            debug_info.append('✓ 邮件发送成功！')
        
        return jsonify({
            'success': True,
            'message': f'测试邮件已发送至 {test_email}，请查收',
            'debug_info': debug_info if debug_mode else None
        })
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        if debug_mode:
            debug_info.append(f'✗ 认证失败: {error_msg}')
        
        if 'qq.com' in service_email:
            msg = '认证失败：请确认使用QQ邮箱授权码（不是QQ密码）'
        elif '163.com' in service_email or '126.com' in service_email:
            msg = '认证失败：请确认已开启SMTP服务并使用授权密码'
        elif 'gmail.com' in service_email:
            msg = '认证失败：请确认使用应用专用密码并已开启两步验证'
        else:
            msg = f'认证失败：{error_msg}'
        
        return jsonify({
            'success': False,
            'message': msg,
            'debug_info': debug_info if debug_mode else None
        })
        
    except Exception as e:
        if debug_mode:
            debug_info.append(f'✗ 错误: {str(e)}')
        
        return jsonify({
            'success': False,
            'message': f'发送失败：{str(e)}',
            'debug_info': debug_info if debug_mode else None
        })

# ========== 部门管理 API ==========

@app.route('/api/admin/departments', methods=['GET', 'POST', 'DELETE'])
def manage_departments():
    """部门管理API（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'GET':
        return jsonify({'success': True, 'departments': db.departments})
    
    elif request.method == 'POST':
        # 检查是否是系统管理员
        if session.get('admin_role') != 'system_admin':
            return jsonify({'success': False, 'message': '仅系统管理员可以添加部门'}), 403
        
        data = request.json
        department = data.get('department', '').strip()
        
        if not department:
            return jsonify({'success': False, 'message': '部门名称不能为空'})
        
        if department in db.departments:
            return jsonify({'success': False, 'message': '部门已存在'})
        
        db.departments.append(department)
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        # 检查是否是系统管理员
        if session.get('admin_role') != 'system_admin':
            return jsonify({'success': False, 'message': '仅系统管理员可以删除部门'}), 403
        
        department = request.json.get('department')
        if department in db.departments:
            db.departments.remove(department)
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '部门不存在'})

# ========== 管理员账号管理 API ==========

@app.route('/api/admin/admins', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_admins():
    """管理员账号管理API（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 检查是否是系统管理员
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以管理管理员账号'}), 403
    
    if request.method == 'GET':
        from models import Admin
        admins_list = []
        for aid, admin in db.admins.items():
            admins_list.append({
                'admin_id': aid,
                'role': admin.role,
                'department': admin.department
            })
        return jsonify({'success': True, 'admins': admins_list})
    
    elif request.method == 'POST':
        from models import Admin
        data = request.json
        admin_id = data.get('admin_id', '').strip()
        password = data.get('password', 'admin123')
        role = data.get('role', 'admin')
        department = data.get('department', '')
        
        if not admin_id:
            return jsonify({'success': False, 'message': '账号不能为空'})
        
        if admin_id in db.admins:
            return jsonify({'success': False, 'message': '账号已存在'})
        
        db.admins[admin_id] = Admin(admin_id, password, role, department)
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        data = request.json
        admin_id = data.get('admin_id')
        current_admin_id = session.get('admin_id')
        
        if admin_id not in db.admins:
            return jsonify({'success': False, 'message': '管理员不存在'})
        
        # 不能修改自己的部门
        if admin_id == current_admin_id and 'department' in data:
            return jsonify({'success': False, 'message': '不能修改自己的部门'})
        
        if 'password' in data:
            db.admins[admin_id].password = data['password']
        if 'role' in data:
            db.admins[admin_id].role = data['role']
        if 'department' in data:
            db.admins[admin_id].department = data['department']
        
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        admin_id = request.json.get('admin_id')
        current_admin_id = session.get('admin_id')
        
        # 不能删除自己
        if admin_id == current_admin_id:
            return jsonify({'success': False, 'message': '不能删除自己的账号'})
        
        # 不能删除系统管理员
        if admin_id in db.admins and db.admins[admin_id].role == 'system_admin':
            return jsonify({'success': False, 'message': '不能删除系统管理员'})
        
        if admin_id in db.admins:
            del db.admins[admin_id]
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '管理员不存在'})

# ========== 活动和学分录入 API ==========

@app.route('/api/admin/activities', methods=['GET', 'POST', 'DELETE', 'PUT'])
def manage_activities():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'GET':
        activities_list = []
        current_admin_id = session.get('admin_id', '')
        is_system_admin = session.get('admin_role') == 'system_admin'
        
        for aid, activity in db.activities.items():
            activity_data = {
                'activity_id': aid,
                'name': activity.name,
                'categories': activity.categories,
                'records_count': len(activity.records)
            }
            # 部门信息仅对管理员可见
            activity_data['department'] = activity.department
            activity_data['created_by'] = activity.created_by
            activity_data['allowed_editors'] = activity.allowed_editors
            
            # 问卷信息
            activity_data['has_questionnaire'] = activity.has_questionnaire
            activity_data['questionnaire_start'] = activity.questionnaire_start
            activity_data['questionnaire_end'] = activity.questionnaire_end
            activity_data['max_participants'] = activity.max_participants
            
            # 计算当前报名人数（仅统计active状态）
            if activity.has_questionnaire:
                current_participants = sum(1 for q in db.activity_questionnaires.values() 
                                         if q.activity_id == aid and q.status == 'active')
                activity_data['current_participants'] = current_participants
            
            # 判断当前管理员是否可以编辑
            can_edit = (is_system_admin or current_admin_id in activity.allowed_editors)
            activity_data['can_edit'] = can_edit
            
            activities_list.append(activity_data)
        return jsonify({'success': True, 'activities': activities_list})
    
    elif request.method == 'POST':
        data = request.json
        activity_id = str(uuid.uuid4())
        name = data.get('name', '').strip()
        categories = data.get('categories', [])
        department = data.get('department', '')
        
        # 验证活动名称
        if not name:
            return jsonify({'success': False, 'message': '活动名称不能为空'})
        
        # 检查是否重名
        for existing_activity in db.activities.values():
            if existing_activity.name == name:
                return jsonify({'success': False, 'message': '活动名称已存在'})
        
        # 验证类别
        if not categories:
            return jsonify({'success': False, 'message': '请至少选择一个类别'})
        
        # 记录创建者，并直接将创建者加入允许编辑列表
        created_by = session.get('admin_id', '')
        allowed_editors = [created_by] if created_by else []
        
        activity = Activity(activity_id, name, categories, department, created_by, allowed_editors)
        db.activities[activity_id] = activity
        db.save_data()
        return jsonify({'success': True, 'activity_id': activity_id})
    
    elif request.method == 'PUT':
        # 修改活动信息（部门、权限、类别等）
        data = request.json
        activity_id = data.get('activity_id')
        
        if activity_id not in db.activities:
            return jsonify({'success': False, 'message': '活动不存在'})
        
        activity = db.activities[activity_id]
        
        # 检查权限：系统管理员可以修改所有，有编辑权限的管理员可以修改类别
        is_system_admin = session.get('admin_role') == 'system_admin'
        has_edit_permission = check_activity_edit_permission(activity_id)
        
        # 修改类别：有编辑权限即可
        if 'categories' in data:
            if not has_edit_permission:
                return jsonify({'success': False, 'message': '无权限修改此活动'}), 403
            
            categories = data['categories']
            if not categories:
                return jsonify({'success': False, 'message': '请至少选择一个类别'})
            activity.categories = categories
        
        # 修改部门和权限：仅系统管理员
        if 'department' in data or 'allowed_editors' in data:
            if not is_system_admin:
                return jsonify({'success': False, 'message': '仅系统管理员可以修改活动权限'}), 403
            
            if 'department' in data:
                activity.department = data['department']
            if 'allowed_editors' in data:
                activity.allowed_editors = data['allowed_editors']
        
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        activity_id = request.json.get('activity_id')
        if activity_id in db.activities:
            # 删除相关记录
            for record in db.activities[activity_id].records:
                if record.record_id in db.records:
                    del db.records[record.record_id]
            del db.activities[activity_id]
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '活动不存在'})

def check_activity_edit_permission(activity_id):
    """检查是否有编辑活动的权限"""
    if activity_id not in db.activities:
        return False
    
    activity = db.activities[activity_id]
    current_admin_id = session.get('admin_id', '')
    is_system_admin = session.get('admin_role') == 'system_admin'
    
    # 系统管理员或在允许编辑列表中
    return (is_system_admin or current_admin_id in activity.allowed_editors)

@app.route('/api/admin/records', methods=['POST', 'DELETE', 'PUT'])
def manage_records():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'POST':
        data = request.json
        activity_id = data.get('activity_id')
        record_name = data.get('record_name')
        
        if activity_id not in db.activities:
            return jsonify({'success': False, 'message': '活动不存在'})
        
        # 检查编辑权限
        if not check_activity_edit_permission(activity_id):
            return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
        
        record_id = str(uuid.uuid4())
        record = Record(record_id, activity_id, record_name)
        db.records[record_id] = record
        db.activities[activity_id].records.append(record)
        db.save_data()
        return jsonify({'success': True, 'record_id': record_id})
    
    elif request.method == 'PUT':
        data = request.json
        record_id = data.get('record_id')
        new_name = data.get('record_name')
        
        if record_id not in db.records:
            return jsonify({'success': False, 'message': '记录不存在'})
        
        record = db.records[record_id]
        
        # 检查编辑权限
        if not check_activity_edit_permission(record.activity_id):
            return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
        
        if not new_name or not new_name.strip():
            return jsonify({'success': False, 'message': '记录名称不能为空'})
        
        record.record_name = new_name.strip()
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        record_id = request.json.get('record_id')
        if record_id in db.records:
            record = db.records[record_id]
            
            # 检查编辑权限
            if not check_activity_edit_permission(record.activity_id):
                return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
            
            activity = db.activities.get(record.activity_id)
            if activity:
                activity.records = [r for r in activity.records if r.record_id != record_id]
            del db.records[record_id]
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '记录不存在'})

@app.route('/api/admin/entries', methods=['POST', 'DELETE', 'PUT'])
def manage_entries():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if request.method == 'POST':
        data = request.json
        record_id = data.get('record_id')
        student_id = data.get('student_id', '').strip()
        credits = data.get('credits')
        categories = data.get('categories', [])
        
        if record_id not in db.records:
            return jsonify({'success': False, 'message': '记录不存在'})
        
        # 检查编辑权限
        record = db.records[record_id]
        if not check_activity_edit_permission(record.activity_id):
            return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
        
        # 验证学号格式（如果提供）
        if student_id and not student_id.isdigit():
            return jsonify({'success': False, 'message': '学号只能包含数字'})
        
        # 允许为不存在的学生添加记录（学号为纯数字即可）
        entry = Entry(student_id, credits, categories)
        db.records[record_id].entries.append(entry)
        db.save_data()
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        data = request.json
        record_id = data.get('record_id')
        student_id = data.get('student_id')
        
        if record_id not in db.records:
            return jsonify({'success': False, 'message': '记录不存在'})
        
        record = db.records[record_id]
        for entry in record.entries:
            if entry.student_id == student_id:
                if 'credits' in data:
                    entry.credits = data['credits']
                if 'categories' in data:
                    entry.categories = data['categories']
                db.save_data()
                return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': '条目不存在'})
    
    elif request.method == 'DELETE':
        data = request.json
        record_id = data.get('record_id')
        student_id = data.get('student_id')
        
        if record_id in db.records:
            record = db.records[record_id]
            record.entries = [e for e in record.entries if e.student_id != student_id]
            db.save_data()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '记录不存在'})

# ========== 查询 API ==========

def calculate_student_credits(student_id):
    """
    计算学生的学分情况 - 使用DFS找到最优分配方案
    
    该函数使用深度优先搜索算法，智能分配学分到各个类别，
    目标是最大化合格的类别数量。
    
    Args:
        student_id (str): 学生学号
    
    Returns:
        dict: 包含以下键的字典：
            - activities (list): 活动参与详情列表
            - category_status (dict): 各类别学分状态
            - total_credits (float): 总学分
            - total_required (float): 总学分要求
            - total_qualified (bool): 总学分是否合格
            - all_categories_qualified (bool): 所有类别是否合格
            - final_qualified (bool): 最终是否合格（总学分合格 AND 所有类别合格）
    
    算法说明：
        1. 收集学生的所有学分条目
        2. 使用DFS遍历所有可能的类别分配方案
        3. 使用剪枝优化搜索效率
        4. 选择能让最多类别合格的分配方案
    """
    
    # 收集该学生的所有学分条目
    entries_data = []
    for record_id, record in db.records.items():
        activity = db.activities.get(record.activity_id)
        if not activity:
            continue
        
        for entry in record.entries:
            if entry.student_id == student_id:
                # 过滤出有效的类别（在系统中存在的类别）
                valid_categories = [cat for cat in entry.categories if cat in db.categories]
                if valid_categories:
                    entries_data.append({
                        'activity_name': activity.name,
                        'record_name': record.record_name,
                        'credits': entry.credits,
                        'categories': valid_categories
                    })
    
    # 如果没有条目，返回空结果
    if not entries_data:
        category_status = {}
        for cname in db.categories.keys():
            category_status[cname] = {
                'credits': 0,
                'required': db.categories[cname].required_credits,
                'qualified': False
            }
        return {
            'activities': [],
            'category_status': category_status,
            'total_credits': 0,
            'total_required': db.total_required_credits,
            'total_qualified': False,
            'all_categories_qualified': False,
            'final_qualified': False
        }
    
    # 使用DFS找到最优分配方案
    best_assignment = find_best_category_assignment(entries_data, db.categories)
    
    # 计算总学分
    total_credits = sum(entry['credits'] for entry in entries_data)
    
    # 根据最优分配计算每个类别的学分
    category_credits = {cname: 0 for cname in db.categories.keys()}
    for i, entry in enumerate(entries_data):
        assigned_cat = best_assignment[i]
        if assigned_cat:
            category_credits[assigned_cat] += entry['credits']
    
    # 构建活动详情列表
    activities_detail = []
    for i, entry in enumerate(entries_data):
        activities_detail.append({
            'activity_name': entry['activity_name'],
            'record_name': entry['record_name'],
            'credits': entry['credits'],
            'categories': entry['categories'],
            'assigned_category': best_assignment[i]
        })
    
    # 计算合格情况
    category_status = {}
    all_categories_qualified = True
    
    for cname, credits in category_credits.items():
        required = db.categories[cname].required_credits
        qualified = credits >= required
        category_status[cname] = {
            'credits': credits,
            'required': required,
            'qualified': qualified
        }
        if not qualified:
            all_categories_qualified = False
    
    # 最终合格条件：总学分合格 AND 所有类别都合格
    total_credits_qualified = total_credits >= db.total_required_credits
    final_qualified = total_credits_qualified and all_categories_qualified
    
    return {
        'activities': activities_detail,
        'category_status': category_status,
        'total_credits': total_credits,
        'total_required': db.total_required_credits,
        'total_qualified': total_credits_qualified,
        'all_categories_qualified': all_categories_qualified,
        'final_qualified': final_qualified
    }


def find_best_category_assignment(entries, categories):
    """
    使用DFS找到最优的类别分配方案
    
    该函数实现了带剪枝的深度优先搜索算法，用于找到能让最多类别合格的学分分配方案。
    
    Args:
        entries (list): 学分条目列表，每个条目包含：
            - credits (float): 学分值
            - categories (list): 可选类别列表
        categories (dict): 类别字典，键为类别名，值为Category对象，包含：
            - required_credits (float): 该类别的合格学分要求
    
    Returns:
        list: 最优分配方案列表，长度与entries相同，
              每个元素是分配给对应条目的类别名称
    
    算法复杂度：
        - 时间复杂度：O(K^N)，其中K是平均可选类别数，N是条目数
        - 实际复杂度：由于剪枝优化，远小于理论值
        - 空间复杂度：O(N + M)，其中M是类别数
    
    优化策略：
        1. 剪枝：如果当前合格数+剩余条目数 <= 最优解，则剪枝
        2. 排序：优先尝试未合格的类别
        3. 提前终止：如果所有类别都合格，立即返回
    """
    n = len(entries)
    best_assignment = [None] * n
    best_qualified_count = -1
    
    def count_qualified(category_credits):
        """计算有多少个类别合格"""
        count = 0
        for cname, credits in category_credits.items():
            if credits >= categories[cname].required_credits:
                count += 1
        return count
    
    def dfs(index, current_assignment, category_credits, current_qualified):
        """深度优先搜索所有可能的分配方案"""
        nonlocal best_assignment, best_qualified_count
        
        # 剪枝：如果当前已合格数量加上剩余条目数量都无法超过最优解，则剪枝
        remaining = n - index
        if current_qualified + remaining <= best_qualified_count:
            return
        
        # 到达叶子节点，检查是否是更优解
        if index == n:
            qualified_count = count_qualified(category_credits)
            if qualified_count > best_qualified_count:
                best_qualified_count = qualified_count
                best_assignment = current_assignment[:]
            return
        
        # 尝试将当前条目分配到每个可能的类别
        entry = entries[index]
        
        # 按照优先级排序：优先尝试未合格的类别
        sorted_categories = sorted(
            entry['categories'],
            key=lambda cat: (
                category_credits[cat] >= categories[cat].required_credits,  # 未合格的优先
                -category_credits[cat]  # 学分少的优先
            )
        )
        
        for cat in sorted_categories:
            # 分配到这个类别
            current_assignment[index] = cat
            category_credits[cat] += entry['credits']
            
            # 计算分配后的合格数量（用于剪枝）
            new_qualified = count_qualified(category_credits)
            
            # 递归搜索
            dfs(index + 1, current_assignment, category_credits, new_qualified)
            
            # 回溯
            category_credits[cat] -= entry['credits']
            current_assignment[index] = None
    
    # 初始化类别学分
    category_credits = {cname: 0 for cname in categories.keys()}
    current_assignment = [None] * n
    
    # 开始DFS搜索
    dfs(0, current_assignment, category_credits, 0)
    
    return best_assignment

@app.route('/api/query/student', methods=['POST'])
def query_student():
    # 只有系统管理员可以查询学生
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以查询学生学分'}), 403
    
    data = request.json
    query = data.get('query')  # 可以是姓名或学号
    
    # 查找学生
    student = None
    student_id = None
    
    if query in db.students:
        student_id = query
        student = db.students[query]
    else:
        for sid, s in db.students.items():
            if s.name == query:
                student_id = sid
                student = s
                break
    
    if not student:
        return jsonify({'success': False, 'message': '未找到该学生'})
    
    result = calculate_student_credits(student_id)
    result['student_id'] = student_id
    result['student_name'] = student.name
    result['success'] = True
    
    return jsonify(result)

@app.route('/api/student/my_credits', methods=['GET'])
def my_credits():
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    result = calculate_student_credits(student_id)
    result['student_id'] = student_id
    result['student_name'] = session.get('student_name')
    result['success'] = True
    
    return jsonify(result)

@app.route('/api/student/change_password', methods=['POST'])
def student_change_password():
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    old_password_hash = data.get('old_password_hash')
    new_password = data.get('new_password')
    
    student_id = session.get('student_id')
    if student_id not in db.students:
        return jsonify({'success': False, 'message': '学生不存在'})
    
    student = db.students[student_id]
    # 验证旧密码
    server_password_hash = hashlib.sha256(student.password.encode('utf-8')).hexdigest()
    if server_password_hash != old_password_hash:
        return jsonify({'success': False, 'message': '原密码错误'})
    
    # 更新密码并清除重置标记
    student.password = new_password
    student.password_reset_required = False
    db.save_data()
    
    return jsonify({'success': True, 'message': '密码修改成功'})

def send_email_with_config(to_email: str, subject: str, body: str) -> tuple:
    """
    使用SMTP发送邮件
    
    Returns:
        (success: bool, message: str)
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        service_email = db.email_config.get('service_email', '')
        service_password = db.email_config.get('service_email_password', '')
        
        if not service_email or not service_password:
            return False, '邮箱配置不完整，请在系统设置中配置服务邮箱'
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = service_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 根据邮箱类型选择SMTP服务器配置
        if 'qq.com' in service_email:
            smtp_server = 'smtp.qq.com'
            smtp_port = 587
            use_ssl = False
        elif '163.com' in service_email:
            smtp_server = 'smtp.163.com'
            smtp_port = 465
            use_ssl = True
        elif '126.com' in service_email:
            smtp_server = 'smtp.126.com'
            smtp_port = 465
            use_ssl = True
        elif 'gmail.com' in service_email:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
            use_ssl = False
        elif 'outlook.com' in service_email or 'hotmail.com' in service_email or 'live.com' in service_email:
            smtp_server = 'smtp-mail.outlook.com'
            smtp_port = 587
            use_ssl = False
        else:
            # 默认配置（适用于大多数邮箱）
            smtp_server = 'smtp.' + service_email.split('@')[1]
            smtp_port = 587
            use_ssl = False
        
        # 连接并发送
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
        
        server.login(service_email, service_password)
        server.send_message(msg)
        server.quit()
        
        return True, '邮件发送成功'
        
    except smtplib.SMTPAuthenticationError as e:
        if 'qq.com' in service_email:
            return False, '认证失败：请确认使用QQ邮箱授权码（不是QQ密码）'
        elif '163.com' in service_email or '126.com' in service_email:
            return False, '认证失败：请确认已开启SMTP服务并使用授权密码'
        elif 'gmail.com' in service_email:
            return False, '认证失败：请确认使用应用专用密码并已开启两步验证'
        else:
            return False, f'认证失败：{str(e)}'
    except smtplib.SMTPConnectError as e:
        return False, f'连接失败：无法连接到邮件服务器，请检查网络连接'
    except Exception as e:
        return False, f'发送失败：{str(e)}'

@app.route('/api/student/forgot_password', methods=['POST'])
def forgot_password():
    """学生忘记密码 - 发送重置密码邮件"""
    import secrets
    
    data = request.json
    student_id = data.get('student_id', '').strip()
    
    # 验证学号是否存在
    if not student_id or student_id not in db.students:
        return jsonify({'success': False, 'message': '学号不存在'})
    
    student = db.students[student_id]
    
    # 检查是否已经申请过密码重置（还未修改密码）
    if student.password_reset_required:
        return jsonify({
            'success': False, 
            'message': '您已申请过密码重置，新密码已发送到您的邮箱。\n请查收邮件并使用新密码登录。\n如未收到邮件，请联系管理员。',
            'already_requested': True
        })
    
    # 检查邮箱配置
    if not db.email_config.get('service_email'):
        return jsonify({'success': False, 'message': '系统邮箱未配置，请联系管理员'})
    
    if not db.email_config.get('student_email_suffix'):
        return jsonify({'success': False, 'message': '学生邮箱后缀未配置，请联系管理员'})
    
    student_email = student_id + db.email_config['student_email_suffix']
    
    # 生成随机密码（8位字母数字组合）
    new_password = secrets.token_urlsafe(8)[:8]
    
    # 邮件内容
    subject = '团校积分系统 - 密码重置'
    body = f"""
您好，{student.name} 同学：

您的团校积分系统密码已重置。

学号：{student_id}
新密码：{new_password}

请使用新密码登录系统，并及时修改密码。

如非本人操作，请立即联系管理员。

---
团校积分系统
    """
    
    # 发送邮件
    success, message = send_email_with_config(student_email, subject, body)
    
    if success:
        # 更新密码并标记为需要重置
        student.password = new_password
        student.password_reset_required = True
        db.save_data()
        
        return jsonify({
            'success': True,
            'message': f'新密码已发送至 {student_email}，请查收邮件'
        })
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/api/admin/change_student_password', methods=['POST'])
def admin_change_student_password():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    student_id = data.get('student_id')
    new_password = data.get('new_password')
    
    if student_id not in db.students:
        return jsonify({'success': False, 'message': '学生不存在'})
    
    student = db.students[student_id]
    student.password = new_password
    # 管理员修改密码后，清除重置标记
    student.password_reset_required = False
    db.save_data()
    
    return jsonify({'success': True, 'message': '密码修改成功'})

@app.route('/api/admin/all_students_credits', methods=['GET'])
def all_students_credits():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 只有系统管理员可以查看所有学生学分
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以查看所有学生学分'}), 403
    
    results = []
    for student_id, student in db.students.items():
        result = calculate_student_credits(student_id)
        results.append({
            'student_id': student_id,
            'student_name': student.name,
            'total_credits': result['total_credits'],
            'total_qualified': result['total_qualified'],
            'all_categories_qualified': result['all_categories_qualified'],
            'final_qualified': result['final_qualified'],
            'category_status': result['category_status']
        })
    
    return jsonify({'success': True, 'students': results})

@app.route('/api/admin/students/batch', methods=['POST'])
def batch_students():
    """批量导入学生（无表头CSV格式：学号,姓名,密码）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    csv_data = data.get('csv_data', '')
    
    try:
        added = 0
        updated = 0
        errors = []
        
        lines = csv_data.strip().split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) < 2:
                errors.append(f'第{line_num}行格式错误: {line}')
                continue
            
            student_id = parts[0].strip()
            name = parts[1].strip()
            password = parts[2].strip() if len(parts) > 2 else '123456'
            
            # 验证学号只能是数字
            if not student_id.isdigit():
                errors.append(f'第{line_num}行学号必须是数字: {student_id}')
                continue
            
            if not name:
                errors.append(f'第{line_num}行姓名为空')
                continue
            
            if student_id in db.students:
                # 更新现有学生
                db.students[student_id].name = name
                db.students[student_id].password = password
                updated += 1
            else:
                # 添加新学生
                db.students[student_id] = Student(student_id, name, password)
                added += 1
        
        db.save_data()
        return jsonify({
            'success': True,
            'added': added,
            'updated': updated,
            'errors': errors
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'解析失败: {str(e)}'})

@app.route('/api/admin/students/export_csv', methods=['GET'])
def export_students_csv():
    """导出学生CSV模板"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['学号', '姓名', '密码'])
    
    for student_id, student in db.students.items():
        writer.writerow([student_id, student.name, student.password])  # 不导出密码哈希
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='学生名单.csv'
    )

@app.route('/api/admin/activities/<activity_id>/records', methods=['GET'])
def get_activity_records(activity_id):
    """获取活动的所有记录"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if activity_id not in db.activities:
        return jsonify({'success': False, 'message': '活动不存在'})
    
    activity = db.activities[activity_id]
    records_list = []
    
    for record in activity.records:
        records_list.append({
            'record_id': record.record_id,
            'record_name': record.record_name,
            'entries_count': len(record.entries)
        })
    
    return jsonify({
        'success': True,
        'records': records_list
    })

@app.route('/api/admin/records/<record_id>', methods=['GET'])
def get_record_detail(record_id):
    """获取记录详情"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if record_id not in db.records:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    record = db.records[record_id]
    activity = db.activities.get(record.activity_id)
    
    entries_list = []
    for entry in record.entries:
        # 获取学生信息
        student = db.students.get(entry.student_id)
        student_name = student.name if student else '(学生不存在)'
        
        entries_list.append({
            'student_id': entry.student_id,
            'student_name': student_name,
            'credits': entry.credits,
            'categories': entry.categories,
            'student_exists': student is not None
        })
    
    return jsonify({
        'success': True,
        'record': {
            'record_id': record.record_id,
            'record_name': record.record_name,
            'activity_id': record.activity_id,
            'activity_name': activity.name if activity else '未知',
            'activity_categories': activity.categories if activity else [],
            'entries': entries_list
        }
    })

@app.route('/api/admin/entries/batch', methods=['POST'])
def batch_entries():
    """批量添加/更新条目（格式：姓名或学号 或 姓名或学号,学分）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    record_id = data.get('record_id')
    entries_text = data.get('entries_text', '')
    categories = data.get('categories', [])  # 统一的类别选择
    default_credits = data.get('default_credits', 0)  # 默认学分
    
    if record_id not in db.records:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    # 检查编辑权限
    record = db.records[record_id]
    if not check_activity_edit_permission(record.activity_id):
        return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
    
    record = db.records[record_id]
    added = 0
    updated = 0
    ignored = 0
    errors = []
    
    lines = entries_text.strip().split('\n')
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        # 解析：可能是 "姓名或学号" 或 "姓名或学号,学分"
        parts = line.split(',')
        identifier = parts[0].strip()  # 姓名或学号
        
        # 确定学分
        if len(parts) >= 2:
            try:
                credits = float(parts[1].strip())
            except ValueError:
                errors.append(f'第{line_num}行学分格式错误: {parts[1]}')
                continue
        else:
            # 没有学分，使用默认学分
            credits = default_credits
        
        # 判断是学号还是姓名
        student_ids = []
        if identifier.isdigit():
            # 纯数字，作为学号，无论学生是否存在都保留
            student_ids = [identifier]
        else:
            # 非数字，作为姓名，匹配系统中的学生
            for sid, student in db.students.items():
                if student.name == identifier:
                    student_ids.append(sid)
            
            if not student_ids:
                ignored += 1
                continue  # 无对应学生则忽略
        
        # 为所有匹配的学生添加/更新记录
        for student_id in student_ids:
            existing_entry = None
            for entry in record.entries:
                if entry.student_id == student_id:
                    existing_entry = entry
                    break
            
            if existing_entry:
                existing_entry.credits = credits
                existing_entry.categories = categories
                updated += 1
            else:
                entry = Entry(student_id, credits, categories)
                record.entries.append(entry)
                added += 1
    
    db.save_data()
    return jsonify({
        'success': True,
        'added': added,
        'updated': updated,
        'ignored': ignored,
        'errors': errors
    })

@app.route('/api/admin/entries/batch_update', methods=['POST'])
def batch_update_entries():
    """批量修改条目的学分和类别"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    record_id = data.get('record_id')
    student_ids = data.get('student_ids', [])
    new_credits = data.get('credits')
    new_categories = data.get('categories')
    
    if record_id not in db.records:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    # 检查编辑权限
    record = db.records[record_id]
    if not check_activity_edit_permission(record.activity_id):
        return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
    
    record = db.records[record_id]
    updated = 0
    
    for entry in record.entries:
        if entry.student_id in student_ids:
            if new_credits is not None:
                entry.credits = new_credits
            if new_categories is not None:
                entry.categories = new_categories
            updated += 1
    
    db.save_data()
    return jsonify({'success': True, 'updated': updated})

@app.route('/api/admin/entries/batch_delete', methods=['POST'])
def batch_delete_entries():
    """批量删除条目"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    data = request.json
    record_id = data.get('record_id')
    student_ids = data.get('student_ids', [])
    
    if record_id not in db.records:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    # 检查编辑权限
    record = db.records[record_id]
    if not check_activity_edit_permission(record.activity_id):
        return jsonify({'success': False, 'message': '无权限编辑此活动'}), 403
    
    record = db.records[record_id]
    record.entries = [e for e in record.entries if e.student_id not in student_ids]
    db.save_data()
    
    return jsonify({'success': True, 'deleted': len(student_ids)})

@app.route('/api/admin/report', methods=['GET'])
def admin_report():
    """管理员报表"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    is_system_admin = session.get('admin_role') == 'system_admin'
    
    # 1. 按类别统计活动
    category_activities = {}
    no_category_activities = []
    
    for aid, activity in db.activities.items():
        if not activity.categories:
            no_category_activities.append({
                'activity_id': aid,
                'activity_name': activity.name
            })
        else:
            for cat in activity.categories:
                if cat not in category_activities:
                    category_activities[cat] = []
                category_activities[cat].append({
                    'activity_id': aid,
                    'activity_name': activity.name
                })
    
    # 2. 统计各类别和总学分合格情况
    category_stats = {}
    total_stats = {'qualified': 0, 'unqualified': 0}
    final_stats = {'qualified': 0, 'unqualified': 0}
    
    for cname in db.categories.keys():
        category_stats[cname] = {'qualified': 0, 'unqualified': 0}
    
    all_students_data = []
    for student_id, student in db.students.items():
        result = calculate_student_credits(student_id)
        
        # 统计各类别
        for cname, status in result['category_status'].items():
            if status['qualified']:
                category_stats[cname]['qualified'] += 1
            else:
                category_stats[cname]['unqualified'] += 1
        
        # 统计总学分
        if result['total_qualified']:
            total_stats['qualified'] += 1
        else:
            total_stats['unqualified'] += 1
        
        # 统计最终合格
        if result['final_qualified']:
            final_stats['qualified'] += 1
        else:
            final_stats['unqualified'] += 1
        
        all_students_data.append({
            'student_id': student_id,
            'student_name': student.name,
            'total_credits': result['total_credits'],
            'category_status': result['category_status'],
            'total_qualified': result['total_qualified'],
            'final_qualified': result['final_qualified']
        })
    
    # 计算比例
    total_students = len(db.students)
    for cname in category_stats:
        q = category_stats[cname]['qualified']
        category_stats[cname]['percentage'] = round(q / total_students * 100, 1) if total_students > 0 else 0
    
    total_stats['percentage'] = round(total_stats['qualified'] / total_students * 100, 1) if total_students > 0 else 0
    final_stats['percentage'] = round(final_stats['qualified'] / total_students * 100, 1) if total_students > 0 else 0
    
    # 3. 分数段统计
    score_ranges = {
        '0-10': 0,
        '11-20': 0,
        '21-30': 0,
        '31-40': 0,
        '41-50': 0,
        '50+': 0
    }
    
    for data in all_students_data:
        score = data['total_credits']
        if score <= 10:
            score_ranges['0-10'] += 1
        elif score <= 20:
            score_ranges['11-20'] += 1
        elif score <= 30:
            score_ranges['21-30'] += 1
        elif score <= 40:
            score_ranges['31-40'] += 1
        elif score <= 50:
            score_ranges['41-50'] += 1
        else:
            score_ranges['50+'] += 1
    
    # 根据角色返回不同的数据
    response_data = {
        'success': True,
        'category_activities': category_activities,
        'no_category_activities': no_category_activities,
        'category_stats': category_stats,
        'total_stats': total_stats,
        'final_stats': final_stats,
        'score_ranges': score_ranges,
        'total_students': total_students,
        'is_system_admin': is_system_admin
    }
    
    # 只有系统管理员可以看到学生详细列表
    if is_system_admin:
        response_data['students'] = all_students_data
    
    return jsonify(response_data)

@app.route('/api/student/activities', methods=['GET'])
def student_activities():
    """学生查看活动列表"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 按类别统计活动
    category_activities = {}
    no_category_activities = []
    
    for aid, activity in db.activities.items():
        if not activity.categories:
            no_category_activities.append({
                'activity_id': aid,
                'activity_name': activity.name
            })
        else:
            for cat in activity.categories:
                if cat not in category_activities:
                    category_activities[cat] = []
                category_activities[cat].append({
                    'activity_id': aid,
                    'activity_name': activity.name
                })
    
    return jsonify({
        'success': True,
        'category_activities': category_activities,
        'no_category_activities': no_category_activities
    })

@app.route('/api/student/categories', methods=['GET'])
def get_student_categories():
    """学生获取学分类别列表"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    categories = []
    for cid, category in db.categories.items():
        categories.append({
            'category_id': cid,
            'name': category.name,
            'required_credits': category.required_credits
        })
    
    return jsonify({'success': True, 'categories': categories})

@app.route('/api/student/registration_questionnaire', methods=['GET'])
def get_student_registration_questionnaire():
    """学生获取自己的注册问卷"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    
    # 查找学生的注册问卷
    for qid, q in db.registration_questionnaires.items():
        if q.student_id == student_id:
            return jsonify({
                'success': True,
                'questionnaire': {
                    'questionnaire_id': qid,
                    'student_id': q.student_id,
                    'name': q.name,
                    'phone': q.phone,
                    'wechat': q.wechat,
                    'suggestion': q.suggestion,
                    'submit_time': q.submit_time
                }
            })
    
    return jsonify({'success': False, 'message': '未找到注册问卷'})

@app.route('/api/student/registration_questionnaire', methods=['PUT'])
def update_student_registration_questionnaire():
    """学生更新自己的注册问卷"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    data = request.json
    
    phone = data.get('phone', '').strip()
    wechat = data.get('wechat', '').strip()
    suggestion = data.get('suggestion', '').strip()
    
    # 验证手机号
    if phone:
        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})
    
    # 查找并更新学生的注册问卷
    for qid, q in db.registration_questionnaires.items():
        if q.student_id == student_id:
            q.phone = phone
            q.wechat = wechat
            q.suggestion = suggestion
            db.save_data()
            return jsonify({'success': True, 'message': '更新成功'})
    
    return jsonify({'success': False, 'message': '未找到注册问卷'})

@app.route('/api/student/activity/<activity_id>/categories', methods=['GET'])
def get_activity_categories(activity_id):
    """获取活动的类别列表（学生和管理员都可访问）"""
    user_type = session.get('user_type')
    if user_type not in ['student', 'admin']:
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if activity_id not in db.activities:
        return jsonify({'success': False, 'message': '活动不存在'})
    
    activity = db.activities[activity_id]
    return jsonify({'success': True, 'categories': activity.categories})

@app.route('/api/student/questionnaires/available', methods=['GET'])
def get_available_questionnaires():
    """获取可报名的问卷列表"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    from datetime import datetime
    now = datetime.now()
    
    questionnaires = []
    for qid, q in db.activity_questionnaires.items():
        if q.status != 'active':
            continue
        
        # 检查时间范围
        try:
            start_time = datetime.strptime(q.start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.strptime(q.end_time, '%Y-%m-%d %H:%M:%S')
            if now < start_time or now > end_time:
                continue
        except:
            continue
        
        # 统计报名人数
        response_count = sum(1 for r in db.questionnaire_responses.values() 
                           if r.questionnaire_id == qid and r.status == 'active')
        
        # 检查是否已报名，并计算排名和候补状态
        is_registered = False
        my_rank = 0
        is_waitlist = False
        
        for rid, r in db.questionnaire_responses.items():
            if r.questionnaire_id == qid and r.student_id == student_id and r.status == 'active':
                is_registered = True
                
                # 计算排名
                all_responses = [(resp_id, resp) for resp_id, resp in db.questionnaire_responses.items() 
                               if resp.questionnaire_id == qid and resp.status == 'active']
                all_responses.sort(key=lambda x: x[1].submit_time)
                
                for idx, (resp_id, resp) in enumerate(all_responses, 1):
                    if resp_id == rid:
                        my_rank = idx
                        break
                
                # 判断是否候补
                if q.max_participants > 0 and my_rank > q.max_participants:
                    is_waitlist = True
                
                break
        
        activity_name = db.activities.get(q.activity_id).name if q.activity_id in db.activities else '未知活动'
        
        questionnaires.append({
            'questionnaire_id': qid,
            'activity_id': q.activity_id,
            'title': q.title,
            'activity_name': activity_name,
            'start_time': q.start_time,
            'end_time': q.end_time,
            'max_participants': q.max_participants,
            'response_count': response_count,
            'is_registered': is_registered,
            'my_rank': my_rank,
            'is_waitlist': is_waitlist,
            'custom_questions': q.custom_questions
        })
    
    # 按创建时间排序
    questionnaires.sort(key=lambda x: x['start_time'], reverse=True)
    
    return jsonify({'success': True, 'questionnaires': questionnaires})

@app.route('/api/student/questionnaires/my_registrations', methods=['GET'])
def get_my_registrations():
    """获取我的报名记录"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    from datetime import datetime
    now = datetime.now()
    
    registrations = []
    for rid, r in db.questionnaire_responses.items():
        if r.student_id == student_id:
            q = db.activity_questionnaires.get(r.questionnaire_id)
            if not q:
                continue
            
            activity_name = db.activities.get(q.activity_id).name if q.activity_id in db.activities else '未知活动'
            
            # 计算排名和状态
            rank = 0
            is_waitlist = False
            is_selected = False
            is_ended = False
            
            if r.status == 'active':
                # 获取该问卷的所有active记录，按时间排序
                all_responses = [(resp_id, resp) for resp_id, resp in db.questionnaire_responses.items() 
                               if resp.questionnaire_id == r.questionnaire_id and resp.status == 'active']
                all_responses.sort(key=lambda x: x[1].submit_time)
                
                # 找到当前记录的排名
                for idx, (resp_id, resp) in enumerate(all_responses, 1):
                    if resp_id == rid:
                        rank = idx
                        break
                
                # 判断是否在名额内
                if q.max_participants > 0:
                    if rank <= q.max_participants:
                        is_selected = True
                    else:
                        is_waitlist = True
                else:
                    is_selected = True
                
                # 判断是否已截止
                try:
                    end_time = datetime.strptime(q.end_time, '%Y-%m-%d %H:%M:%S')
                    is_ended = now > end_time
                except:
                    pass
            
            registrations.append({
                'response_id': rid,
                'questionnaire_id': r.questionnaire_id,
                'questionnaire_title': q.title,
                'activity_name': activity_name,
                'phone': r.phone,
                'wechat': r.wechat,
                'intended_category': r.intended_category,
                'custom_answers': r.custom_answers if hasattr(r, 'custom_answers') else {},
                'submit_time': r.submit_time,
                'status': r.status,
                'rank': rank,
                'is_waitlist': is_waitlist,
                'is_selected': is_selected,
                'is_ended': is_ended,
                'max_participants': q.max_participants
            })
    
    # 按提交时间排序
    registrations.sort(key=lambda x: x['submit_time'], reverse=True)
    
    return jsonify({'success': True, 'registrations': registrations})

@app.route('/api/student/questionnaire/submit', methods=['POST'])
def submit_questionnaire():
    """提交问卷"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    if not student_id:
        return jsonify({'success': False, 'message': '会话已过期，请重新登录'}), 401
    
    student = db.students.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': '学生不存在，请联系管理员'})
    
    data = request.json
    questionnaire_id = data.get('questionnaire_id', '').strip()
    intended_category = data.get('intended_category', '').strip()
    custom_answers = data.get('custom_answers', {})
    
    # 从注册问卷中获取手机号和微信号
    phone = ''
    wechat = ''
    for q in db.registration_questionnaires.values():
        if q.student_id == student_id:
            phone = q.phone or ''
            wechat = q.wechat or ''
            break
    
    # 验证
    if not questionnaire_id or questionnaire_id not in db.activity_questionnaires:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    questionnaire = db.activity_questionnaires[questionnaire_id]
    
    if questionnaire.status != 'active':
        return jsonify({'success': False, 'message': '问卷已关闭'})
    
    # 检查时间范围
    from datetime import datetime
    now = datetime.now()
    try:
        start_time = datetime.strptime(questionnaire.start_time, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(questionnaire.end_time, '%Y-%m-%d %H:%M:%S')
        if now < start_time:
            return jsonify({'success': False, 'message': '问卷尚未开始'})
        if now > end_time:
            return jsonify({'success': False, 'message': '问卷已截止'})
    except:
        return jsonify({'success': False, 'message': '时间格式错误'})
    
    # 检查是否已有记录（包括已取消的）
    existing_response = None
    existing_response_id = None
    for rid, r in db.questionnaire_responses.items():
        if r.questionnaire_id == questionnaire_id and r.student_id == student_id:
            existing_response = r
            existing_response_id = rid
            break
    
    # 如果已有active状态的记录，提示已报名
    if existing_response and existing_response.status == 'active':
        return jsonify({'success': False, 'message': '您已报名此问卷'})
    
    # 注意：不再限制人数，允许候补报名
    # 超出名额的报名将在排名计算时标记为候补
    
    # 验证手机号和微信号（从注册问卷获取）
    if not phone or not wechat:
        return jsonify({'success': False, 'message': '请先在注册问卷中填写手机号和微信号'})
    
    # 验证意向类别
    if not intended_category:
        return jsonify({'success': False, 'message': '请选择意向学分类别'})
    
    from datetime import datetime
    submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 如果已有记录（已取消的），重新激活并更新
    if existing_response:
        existing_response.phone = phone
        existing_response.wechat = wechat
        existing_response.intended_category = intended_category
        existing_response.custom_answers = custom_answers
        existing_response.submit_time = submit_time
        existing_response.status = 'active'
        db.save_data()
        return jsonify({'success': True, 'message': '报名成功'})
    
    # 否则创建新记录
    from models import QuestionnaireResponse
    
    response_id = str(uuid.uuid4())
    
    response = QuestionnaireResponse(
        response_id=response_id,
        questionnaire_id=questionnaire_id,
        student_id=student_id,
        student_name=student.name,
        phone=phone,
        wechat=wechat,
        intended_category=intended_category,
        submit_time=submit_time,
        status='active',
        custom_answers=custom_answers
    )
    
    db.questionnaire_responses[response_id] = response
    db.save_data()
    
    return jsonify({'success': True, 'message': '报名成功'})

@app.route('/api/student/questionnaire/update/<response_id>', methods=['PUT'])
def student_update_questionnaire_response(response_id):
    """学生更新报名信息"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    
    if response_id not in db.questionnaire_responses:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    response = db.questionnaire_responses[response_id]
    
    if response.student_id != student_id:
        return jsonify({'success': False, 'message': '无权限'})
    
    if response.status != 'active':
        return jsonify({'success': False, 'message': '已取消的报名无法修改'})
    
    data = request.json
    intended_category = data.get('intended_category', '').strip()
    custom_answers = data.get('custom_answers', {})
    
    # 验证意向类别
    if not intended_category:
        return jsonify({'success': False, 'message': '请选择意向学分类别'})
    
    # 更新信息
    response.intended_category = intended_category
    response.custom_answers = custom_answers
    db.save_data()
    
    return jsonify({'success': True, 'message': '修改成功'})

@app.route('/api/student/questionnaire/cancel/<response_id>', methods=['POST'])
def cancel_questionnaire(response_id):
    """取消报名"""
    if session.get('user_type') != 'student':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    student_id = session.get('student_id')
    
    if response_id not in db.questionnaire_responses:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    response = db.questionnaire_responses[response_id]
    
    if response.student_id != student_id:
        return jsonify({'success': False, 'message': '无权限'})
    
    if response.status != 'active':
        return jsonify({'success': False, 'message': '已取消，无需重复操作'})
    
    response.status = 'cancelled'
    db.save_data()
    
    return jsonify({'success': True, 'message': '取消成功'})

@app.route('/api/admin/export', methods=['GET'])
def export_data():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    # 只有系统管理员可以导出数据
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以导出数据'}), 403
    
    # 创建Excel工作簿
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "学生学分统计"
    
    # 设置表头
    headers = ['学号', '姓名', '总学分', '总学分合格']
    for cname in db.categories.keys():
        headers.extend([f'{cname}学分', f'{cname}合格'])
    headers.append('最终合格')
    
    ws.append(headers)
    
    # 设置表头样式
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # 填充数据
    for student_id, student in db.students.items():
        result = calculate_student_credits(student_id)
        row = [
            student_id,
            student.name,
            result['total_credits'],
            '是' if result['total_qualified'] else '否'
        ]
        
        for cname in db.categories.keys():
            status = result['category_status'][cname]
            row.extend([
                status['credits'],
                '是' if status['qualified'] else '否'
            ])
        
        row.append('是' if result['final_qualified'] else '否')
        ws.append(row)
    
    # 保存到内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='学生学分统计.xlsx'
    )

# ========== 统一问卷管理 API ==========

@app.route('/api/admin/questionnaires/all', methods=['GET'])
def get_all_questionnaires():
    """获取所有问卷（注册+活动）（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以查看问卷'}), 403
    
    questionnaires = []
    
    # 添加注册问卷
    for qid, q in db.registration_questionnaires.items():
        questionnaires.append({
            'questionnaire_id': qid,
            'questionnaire_type': 'registration',
            'student_id': q.student_id,
            'name': q.name,
            'phone': q.phone,
            'wechat': q.wechat,
            'suggestion': q.suggestion,
            'submit_time': q.submit_time
        })
    
    # 添加活动问卷模板（显示为问卷而非记录）
    from datetime import datetime
    now = datetime.now()
    
    for qid, q in db.activity_questionnaires.items():
        activity_name = db.activities.get(q.activity_id).name if q.activity_id in db.activities else '未知活动'
        # 统计报名人数
        response_count = sum(1 for r in db.questionnaire_responses.values() 
                           if r.questionnaire_id == qid and r.status == 'active')
        
        # 判断是否已截止
        is_ended = False
        try:
            end_time = datetime.strptime(q.end_time, '%Y-%m-%d %H:%M:%S')
            is_ended = now > end_time
        except:
            pass
        
        questionnaires.append({
            'questionnaire_id': qid,
            'questionnaire_type': 'activity_template',
            'title': q.title,
            'activity_name': activity_name,
            'activity_id': q.activity_id,
            'start_time': q.start_time,
            'end_time': q.end_time,
            'max_participants': q.max_participants,
            'response_count': response_count,
            'status': q.status,
            'created_time': q.created_time,
            'is_ended': is_ended,
            'custom_questions': q.custom_questions
        })
    
    # 按时间倒序排序（注册问卷用submit_time，活动问卷用created_time）
    questionnaires.sort(key=lambda x: x.get('submit_time') or x.get('created_time', ''), reverse=True)
    
    return jsonify({
        'success': True,
        'questionnaires': questionnaires,
        'total': len(questionnaires)
    })

@app.route('/api/admin/questionnaire/update', methods=['PUT'])
def admin_update_questionnaire():
    """管理员更新问卷信息"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以编辑问卷'}), 403
    
    data = request.json
    questionnaire_id = data.get('questionnaire_id')
    phone = data.get('phone', '').strip()
    wechat = data.get('wechat', '').strip()
    
    # 验证手机号格式
    if phone:
        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})
    
    # 查找问卷（先查注册问卷，再查活动问卷）
    if questionnaire_id in db.registration_questionnaires:
        q = db.registration_questionnaires[questionnaire_id]
        q.phone = phone
        q.wechat = wechat
        q.suggestion = data.get('suggestion', '').strip()
    elif questionnaire_id in db.activity_questionnaires:
        q = db.activity_questionnaires[questionnaire_id]
        q.phone = phone
        q.wechat = wechat
        q.status = data.get('status', 'active')
    else:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    db.save_data()
    return jsonify({'success': True, 'message': '更新成功'})

@app.route('/api/admin/questionnaire/<questionnaire_id>', methods=['DELETE'])
def delete_questionnaire(questionnaire_id):
    """删除问卷"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以删除问卷'}), 403
    
    # 查找并删除问卷
    if questionnaire_id in db.registration_questionnaires:
        del db.registration_questionnaires[questionnaire_id]
        db.save_data()
        return jsonify({'success': True, 'message': '删除成功'})
    elif questionnaire_id in db.activity_questionnaires:
        del db.activity_questionnaires[questionnaire_id]
        db.save_data()
        return jsonify({'success': True, 'message': '删除成功'})
    else:
        return jsonify({'success': False, 'message': '问卷不存在'})

@app.route('/api/admin/questionnaire/create_activity', methods=['POST'])
def create_activity_questionnaire():
    """创建活动问卷"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以创建问卷'}), 403
    
    data = request.json
    student_id = data.get('student_id', '').strip()
    activity_id = data.get('activity_id', '').strip()
    phone = data.get('phone', '').strip()
    wechat = data.get('wechat', '').strip()
    
    # 验证
    if not student_id or student_id not in db.students:
        return jsonify({'success': False, 'message': '学生不存在'})
    
    if not activity_id or activity_id not in db.activities:
        return jsonify({'success': False, 'message': '活动不存在'})
    
    # 检查是否已经报名
    for q in db.activity_questionnaires.values():
        if q.student_id == student_id and q.activity_id == activity_id and q.status == 'active':
            return jsonify({'success': False, 'message': '该学生已报名此活动'})
    
    # 验证手机号
    if phone:
        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})
    
    # 创建活动问卷
    from datetime import datetime
    from models import ActivityQuestionnaire
    
    questionnaire_id = str(uuid.uuid4())
    submit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    student = db.students[student_id]
    
    questionnaire = ActivityQuestionnaire(
        questionnaire_id=questionnaire_id,
        activity_id=activity_id,
        student_id=student_id,
        student_name=student.name,
        phone=phone,
        wechat=wechat,
        submit_time=submit_time,
        status='active'
    )
    
    db.activity_questionnaires[questionnaire_id] = questionnaire
    db.save_data()
    
    return jsonify({'success': True, 'message': '创建成功'})

@app.route('/api/admin/questionnaire/create_template', methods=['POST'])
def create_activity_questionnaire_template():
    """创建活动问卷模板"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以创建问卷'}), 403
    
    data = request.json
    activity_id = data.get('activity_id', '').strip()
    title = data.get('title', '').strip()
    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    max_participants = int(data.get('max_participants', 0))
    custom_questions = data.get('custom_questions', [])
    
    # 验证
    if not activity_id or activity_id not in db.activities:
        return jsonify({'success': False, 'message': '活动不存在'})
    
    if not title:
        return jsonify({'success': False, 'message': '请输入问卷标题'})
    
    if not start_time or not end_time:
        return jsonify({'success': False, 'message': '请设置问卷时间'})
    
    # 验证时间
    from datetime import datetime
    try:
        start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
        if start_dt >= end_dt:
            return jsonify({'success': False, 'message': '开始时间必须早于结束时间'})
    except ValueError:
        return jsonify({'success': False, 'message': '时间格式不正确'})
    
    # 检查是否已存在该活动的问卷
    for q in db.activity_questionnaires.values():
        if q.activity_id == activity_id and q.status == 'active':
            return jsonify({'success': False, 'message': '该活动已存在问卷'})
    
    # 验证自定义题目
    for idx, q in enumerate(custom_questions):
        q['question_id'] = str(uuid.uuid4())
        q['order'] = idx + 1
        if q.get('question_type') not in ['description', 'single_choice', 'multiple_choice', 'text', 'textarea']:
            return jsonify({'success': False, 'message': f'题目{idx+1}类型无效'})
        if not q.get('question_text'):
            return jsonify({'success': False, 'message': f'题目{idx+1}文本不能为空'})
    
    # 创建问卷模板
    from models import ActivityQuestionnaire
    
    questionnaire_id = str(uuid.uuid4())
    created_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 转换时间格式
    start_time_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    questionnaire = ActivityQuestionnaire(
        questionnaire_id=questionnaire_id,
        activity_id=activity_id,
        title=title,
        start_time=start_time_str,
        end_time=end_time_str,
        max_participants=max_participants,
        has_category_question=True,
        custom_questions=custom_questions,
        created_time=created_time,
        status='active'
    )
    
    db.activity_questionnaires[questionnaire_id] = questionnaire
    db.save_data()
    
    return jsonify({'success': True, 'message': '创建成功'})

@app.route('/api/admin/questionnaire/template/<questionnaire_id>', methods=['PUT'])
def update_questionnaire_template(questionnaire_id):
    """编辑问卷模板"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以编辑问卷'}), 403
    
    if questionnaire_id not in db.activity_questionnaires:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    data = request.json
    title = data.get('title', '').strip()
    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    max_participants = int(data.get('max_participants', 0))
    custom_questions = data.get('custom_questions', [])
    
    # 验证
    if not title:
        return jsonify({'success': False, 'message': '请输入问卷标题'})
    
    if not start_time or not end_time:
        return jsonify({'success': False, 'message': '请设置问卷时间'})
    
    # 验证时间
    from datetime import datetime
    try:
        start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
        if start_dt >= end_dt:
            return jsonify({'success': False, 'message': '开始时间必须早于结束时间'})
    except ValueError:
        return jsonify({'success': False, 'message': '时间格式不正确'})
    
    # 验证自定义题目
    for idx, q in enumerate(custom_questions):
        if 'question_id' not in q or not q['question_id']:
            q['question_id'] = str(uuid.uuid4())
        q['order'] = idx + 1
        if q.get('question_type') not in ['description', 'single_choice', 'multiple_choice', 'text', 'textarea']:
            return jsonify({'success': False, 'message': f'题目{idx+1}类型无效'})
        if not q.get('question_text'):
            return jsonify({'success': False, 'message': f'题目{idx+1}文本不能为空'})
    
    # 更新问卷
    questionnaire = db.activity_questionnaires[questionnaire_id]
    questionnaire.title = title
    questionnaire.start_time = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    questionnaire.end_time = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    questionnaire.max_participants = max_participants
    questionnaire.custom_questions = custom_questions
    
    db.save_data()
    
    return jsonify({'success': True, 'message': '更新成功'})

@app.route('/api/admin/questionnaire/template/<questionnaire_id>', methods=['DELETE'])
def delete_questionnaire_template(questionnaire_id):
    """删除问卷模板"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以删除问卷'}), 403
    
    if questionnaire_id not in db.activity_questionnaires:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    del db.activity_questionnaires[questionnaire_id]
    db.save_data()
    
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/admin/questionnaire/responses/<questionnaire_id>', methods=['GET'])
def get_questionnaire_responses(questionnaire_id):
    """获取问卷填写记录"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if questionnaire_id not in db.activity_questionnaires:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    questionnaire = db.activity_questionnaires[questionnaire_id]
    
    # 获取所有active记录并按时间排序（用于计算排名）
    all_active_responses = [(rid, r) for rid, r in db.questionnaire_responses.items() 
                           if r.questionnaire_id == questionnaire_id and r.status == 'active']
    all_active_responses.sort(key=lambda x: x[1].submit_time)
    
    # 判断是否已截止
    from datetime import datetime
    now = datetime.now()
    is_ended = False
    try:
        end_time = datetime.strptime(questionnaire.end_time, '%Y-%m-%d %H:%M:%S')
        is_ended = now > end_time
    except:
        pass
    
    responses = []
    for rid, r in db.questionnaire_responses.items():
        if r.questionnaire_id == questionnaire_id:
            # 计算排名和状态
            rank = 0
            is_waitlist = False
            is_selected = False
            
            if r.status == 'active':
                # 找到排名
                for idx, (resp_id, resp) in enumerate(all_active_responses, 1):
                    if resp_id == rid:
                        rank = idx
                        break
                
                # 判断是否在名额内
                if questionnaire.max_participants > 0:
                    if rank <= questionnaire.max_participants:
                        is_selected = True
                    else:
                        is_waitlist = True
                else:
                    is_selected = True
            
            responses.append({
                'response_id': rid,
                'student_id': r.student_id,
                'student_name': r.student_name,
                'phone': r.phone,
                'wechat': r.wechat,
                'intended_category': r.intended_category,
                'custom_answers': r.custom_answers if hasattr(r, 'custom_answers') else {},
                'submit_time': r.submit_time,
                'status': r.status,
                'rank': rank,
                'is_waitlist': is_waitlist,
                'is_selected': is_selected,
                'is_ended': is_ended
            })
    
    # 按提交时间排序（active在前，按时间升序；cancelled在后）
    responses.sort(key=lambda x: (x['status'] != 'active', x['submit_time']))
    
    return jsonify({'success': True, 'responses': responses})

@app.route('/api/admin/questionnaire/responses/<questionnaire_id>/export', methods=['GET'])
def export_questionnaire_responses(questionnaire_id):
    """导出问卷填写记录"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if questionnaire_id not in db.activity_questionnaires:
        return jsonify({'success': False, 'message': '问卷不存在'})
    
    questionnaire = db.activity_questionnaires[questionnaire_id]
    
    # 获取所有active记录并按时间排序（用于计算排名）
    all_active_responses = [(rid, r) for rid, r in db.questionnaire_responses.items() 
                           if r.questionnaire_id == questionnaire_id and r.status == 'active']
    all_active_responses.sort(key=lambda x: x[1].submit_time)
    
    # 判断是否已截止
    from datetime import datetime
    now = datetime.now()
    is_ended = False
    try:
        end_time = datetime.strptime(questionnaire.end_time, '%Y-%m-%d %H:%M:%S')
        is_ended = now > end_time
    except:
        pass
    
    # 准备CSV数据
    import io
    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM
    output.write('排名,学号,姓名,手机号,微信号,意向学分类别,提交时间,状态\n')
    
    # 收集所有记录并计算排名
    all_responses = []
    for rid, r in db.questionnaire_responses.items():
        if r.questionnaire_id == questionnaire_id:
            # 计算排名和状态
            rank = 0
            is_waitlist = False
            is_selected = False
            
            if r.status == 'active':
                # 找到排名
                for idx, (resp_id, resp) in enumerate(all_active_responses, 1):
                    if resp_id == rid:
                        rank = idx
                        break
                
                # 判断是否在名额内
                if questionnaire.max_participants > 0:
                    if rank <= questionnaire.max_participants:
                        is_selected = True
                    else:
                        is_waitlist = True
                else:
                    is_selected = True
            
            # 状态文本
            if r.status == 'cancelled':
                status_text = '已取消'
            elif is_ended:
                status_text = '已入选' if is_selected else '未入选'
            else:
                status_text = '候补' if is_waitlist else '已报名'
            
            all_responses.append({
                'rank': rank if rank > 0 else '-',
                'student_id': r.student_id,
                'student_name': r.student_name,
                'phone': r.phone,
                'wechat': r.wechat,
                'intended_category': r.intended_category,
                'submit_time': r.submit_time,
                'status': status_text
            })
    
    # 按提交时间排序（active在前，按时间升序；cancelled在后）
    all_responses.sort(key=lambda x: (x['status'] == '已取消', x['submit_time']))
    
    # 写入CSV
    for resp in all_responses:
        output.write(f'{resp["rank"]},{resp["student_id"]},{resp["student_name"]},{resp["phone"]},{resp["wechat"]},{resp["intended_category"]},{resp["submit_time"]},{resp["status"]}\n')
    
    # 返回CSV文件
    from flask import make_response
    from urllib.parse import quote
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    # 使用URL编码的文件名以支持中文
    safe_filename = questionnaire.title.replace(',', '_').replace('\n', '_').replace('\r', '_')
    encoded_filename = quote(f'{safe_filename}_填写记录.csv')
    response.headers['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{encoded_filename}'
    
    return response

@app.route('/api/admin/questionnaire/response/<response_id>', methods=['PUT'])
def update_response(response_id):
    """管理员编辑问卷填写记录"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以编辑'}), 403
    
    if response_id not in db.questionnaire_responses:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    response = db.questionnaire_responses[response_id]
    data = request.json
    
    phone = data.get('phone', '').strip()
    wechat = data.get('wechat', '').strip()
    intended_category = data.get('intended_category', '').strip()
    
    if phone:
        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})
        response.phone = phone
    
    if wechat:
        response.wechat = wechat
    
    if intended_category:
        response.intended_category = intended_category
    
    db.save_data()
    return jsonify({'success': True, 'message': '修改成功'})

@app.route('/api/admin/questionnaire/response/<response_id>', methods=['DELETE'])
def delete_response(response_id):
    """管理员删除问卷填写记录"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以删除'}), 403
    
    if response_id not in db.questionnaire_responses:
        return jsonify({'success': False, 'message': '记录不存在'})
    
    del db.questionnaire_responses[response_id]
    db.save_data()
    
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/admin/questionnaires/export', methods=['GET'])
def export_all_questionnaires():
    """导出所有问卷为CSV"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以导出'}), 403
    
    from io import BytesIO
    from datetime import datetime
    
    type_filter = request.args.get('type', '')
    
    output = BytesIO()
    output.write('\ufeff'.encode('utf-8'))
    
    csv_lines = []
    csv_lines.append('类型,学号,姓名,手机号,微信号,备注,提交时间')
    
    # 收集所有问卷
    all_questionnaires = []
    
    if not type_filter or type_filter == 'registration':
        for q in db.registration_questionnaires.values():
            all_questionnaires.append({
                'type': '注册问卷',
                'student_id': q.student_id,
                'name': q.name,
                'phone': q.phone,
                'wechat': q.wechat,
                'remark': q.suggestion or '',
                'submit_time': q.submit_time
            })
    
    if not type_filter or type_filter == 'activity':
        # 导出问卷填写记录，而不是问卷模板
        for r in db.questionnaire_responses.values():
            q = db.activity_questionnaires.get(r.questionnaire_id)
            if q:
                activity_name = db.activities.get(q.activity_id).name if q.activity_id in db.activities else '未知活动'
                status_text = '已报名' if r.status == 'active' else '已取消'
                all_questionnaires.append({
                    'type': '活动问卷',
                    'student_id': r.student_id,
                    'name': r.student_name,
                    'phone': r.phone,
                    'wechat': r.wechat,
                    'remark': f'{activity_name} - {q.title} ({status_text}) - 意向类别：{r.intended_category}',
                    'submit_time': r.submit_time
                })
    
    # 排序
    all_questionnaires.sort(key=lambda x: x.get('submit_time', ''), reverse=True)
    
    # 写入数据
    for q in all_questionnaires:
        remark = q['remark'].replace(',', '，').replace('\n', ' ').replace('\r', '')
        csv_lines.append(f"{q['type']},{q['student_id']},{q['name']},{q['phone']},{q['wechat']},{remark},{q['submit_time']}")
    
    csv_content = '\n'.join(csv_lines)
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    filename = f'questionnaires_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )

# ========== 注册问卷管理 API（保留兼容性）==========

@app.route('/api/admin/registration_questionnaires', methods=['GET'])
def get_registration_questionnaires():
    """获取所有注册问卷（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以查看注册问卷'}), 403
    
    questionnaires = []
    for qid, q in db.registration_questionnaires.items():
        questionnaires.append({
            'questionnaire_id': qid,
            'student_id': q.student_id,
            'name': q.name,
            'phone': q.phone,
            'wechat': q.wechat,
            'suggestion': q.suggestion,
            'submit_time': q.submit_time
        })
    
    # 按提交时间倒序排序
    questionnaires.sort(key=lambda x: x['submit_time'], reverse=True)
    
    return jsonify({
        'success': True,
        'questionnaires': questionnaires,
        'total': len(questionnaires)
    })

@app.route('/api/admin/registration_questionnaires/export', methods=['GET'])
def export_registration_questionnaires():
    """导出注册问卷为CSV（仅系统管理员）"""
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    
    if session.get('admin_role') != 'system_admin':
        return jsonify({'success': False, 'message': '仅系统管理员可以导出'}), 403
    
    import csv
    from io import BytesIO
    
    # 使用BytesIO以便添加BOM
    output = BytesIO()
    
    # 写入UTF-8 BOM，让Excel正确识别中文
    output.write('\ufeff'.encode('utf-8'))
    
    # 按提交时间排序
    questionnaires = sorted(
        db.registration_questionnaires.values(),
        key=lambda x: x.submit_time,
        reverse=True
    )
    
    # 构建CSV内容
    csv_lines = []
    csv_lines.append('学号,姓名,手机号,微信号,建议,提交时间')
    
    for q in questionnaires:
        # 处理建议字段中的逗号和换行符
        suggestion = q.suggestion.replace(',', '，').replace('\n', ' ').replace('\r', '') if q.suggestion else ''
        csv_lines.append(f'{q.student_id},{q.name},{q.phone},{q.wechat},{suggestion},{q.submit_time}')
    
    csv_content = '\n'.join(csv_lines)
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    from datetime import datetime
    filename = f'registration_questionnaires_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Credit System Started")
    print("="*60)
    print(f"\nStudent Login: http://localhost:5000")
    print(f"Admin Login: http://localhost:5000/{ADMIN_LOGIN_PATH}")
    print("\n" + "="*60 + "\n")
    print(flush=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
