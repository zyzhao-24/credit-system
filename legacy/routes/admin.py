"""
管理员相关路由
包括学生管理、类别管理、活动管理等
"""
from flask import request, jsonify, session, send_file
import hashlib
import csv
import io
from models import Student, Category, Activity, Record, Entry
import uuid


def register_admin_routes(app, db):
    """
    注册管理员相关路由
    
    Args:
        app: Flask应用实例
        db: 数据库实例
    """
    
    def require_admin():
        """检查管理员权限"""
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'message': '无权限'}), 403
        return None
    
    # ========== 学生管理 ==========
    
    @app.route('/api/admin/students', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def manage_students():
        """
        学生管理API
        
        GET: 获取所有学生列表
        POST: 添加新学生
        PUT: 更新学生信息
        DELETE: 删除学生
        """
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        if request.method == 'GET':
            # 按学号排序
            students_list = sorted(
                [{'student_id': sid, 'name': s.name, 'password': s.password} 
                 for sid, s in db.students.items()],
                key=lambda x: x['student_id']
            )
            return jsonify({'success': True, 'students': students_list})
        
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
            
            db.students[student_id] = Student(student_id, name, password)
            db.save_data()
            return jsonify({'success': True})
        
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
                del db.students[student_id]
                db.save_data()
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': '学生不存在'})
    
    @app.route('/api/admin/students/batch', methods=['POST'])
    def batch_students():
        """
        批量导入学生
        
        格式：学号,姓名,密码（无表头）
        密码可省略，默认123456
        """
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
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
                    db.students[student_id].name = name
                    db.students[student_id].password = password
                    updated += 1
                else:
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
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['学号', '姓名', '密码'])
        
        # 按学号排序
        sorted_students = sorted(db.students.items(), key=lambda x: x[0])
        for student_id, student in sorted_students:
            writer.writerow([student_id, student.name, ''])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='学生名单.csv'
        )
    
    @app.route('/api/admin/change_student_password', methods=['POST'])
    def admin_change_student_password():
        """管理员修改学生密码"""
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        data = request.json
        student_id = data.get('student_id')
        new_password = data.get('new_password')
        
        if student_id not in db.students:
            return jsonify({'success': False, 'message': '学生不存在'})
        
        db.students[student_id].password = new_password
        db.save_data()
        
        return jsonify({'success': True, 'message': '密码修改成功'})
    
    # ========== 类别管理 ==========
    
    @app.route('/api/admin/categories', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def manage_categories():
        """类别管理API"""
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        if request.method == 'GET':
            categories_list = [{'name': cname, 'required_credits': c.required_credits} 
                              for cname, c in db.categories.items()]
            return jsonify({'success': True, 'categories': categories_list})
        
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
        """总学分设置API"""
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        if request.method == 'GET':
            return jsonify({'success': True, 'total_required_credits': db.total_required_credits})
        
        elif request.method == 'POST':
            data = request.json
            db.total_required_credits = data.get('total_required_credits', 0)
            db.save_data()
            return jsonify({'success': True})
    
    # ========== 部门管理 ==========
    
    @app.route('/api/admin/departments', methods=['GET', 'POST', 'DELETE'])
    def manage_departments():
        """
        部门管理API（仅系统管理员）
        
        GET: 获取所有部门列表
        POST: 添加新部门
        DELETE: 删除部门
        """
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
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
    
    # ========== 管理员账号管理 ==========
    
    @app.route('/api/admin/admins', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def manage_admins():
        """
        管理员账号管理API（仅系统管理员）
        
        GET: 获取所有管理员列表
        POST: 添加新管理员
        PUT: 修改管理员信息
        DELETE: 删除管理员
        """
        auth_error = require_admin()
        if auth_error:
            return auth_error
        
        # 检查是否是系统管理员
        if session.get('admin_role') != 'system_admin':
            return jsonify({'success': False, 'message': '仅系统管理员可以管理管理员账号'}), 403
        
        if request.method == 'GET':
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
            
            if admin_id not in db.admins:
                return jsonify({'success': False, 'message': '管理员不存在'})
            
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
            
            if admin_id in db.admins:
                del db.admins[admin_id]
                db.save_data()
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': '管理员不存在'})
