"""
认证相关路由
包括登录、登出等功能
"""
from flask import request, jsonify, session, render_template
import hashlib


def register_auth_routes(app, db, admin_username, admin_password, admin_login_path):
    """
    注册认证相关路由
    
    Args:
        app: Flask应用实例
        db: 数据库实例
        admin_username: 管理员用户名
        admin_password: 管理员密码哈希
        admin_login_path: 管理员登录路径
    """
    
    @app.route('/')
    def index():
        """学生登录页面"""
        return render_template('login.html')
    
    @app.route(f'/{admin_login_path}')
    def admin_login_page():
        """管理员登录页面"""
        return render_template('admin_login.html')
    
    @app.route('/admin')
    def admin_page():
        """管理员主页"""
        if session.get('user_type') != 'admin':
            return render_template('login.html')
        return render_template('admin.html')
    
    @app.route('/student')
    def student_page():
        """学生主页"""
        if session.get('user_type') != 'student':
            return render_template('login.html')
        return render_template('student.html')
    
    @app.route('/api/login', methods=['POST'])
    def login():
        """
        用户登录API
        
        接收JSON数据:
            username: 用户名（学号或admin）
            password_hash: SHA-256哈希后的密码
        
        返回JSON:
            success: 是否成功
            user_type: 用户类型（admin/student）
            message: 错误信息（如果失败）
        """
        data = request.json
        username = data.get('username')
        password_hash = data.get('password_hash')
        
        # 检查是否是管理员
        if username == admin_username and password_hash == admin_password:
            session['user_type'] = 'admin'
            session['username'] = username
            return jsonify({'success': True, 'user_type': 'admin'})
        
        # 检查是否是学生
        if username in db.students:
            student = db.students[username]
            # 对服务器存储的明文密码进行哈希，与客户端发送的哈希比较
            server_password_hash = hashlib.sha256(student.password.encode('utf-8')).hexdigest()
            if server_password_hash == password_hash:
                session['user_type'] = 'student'
                session['student_id'] = username
                session['student_name'] = student.name
                return jsonify({'success': True, 'user_type': 'student'})
        
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        """
        用户登出API
        
        返回JSON:
            success: 是否成功
        """
        session.clear()
        return jsonify({'success': True})
