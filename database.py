"""
数据库操作层

提供数据的持久化存储和读取功能，使用JSON文件作为存储介质。
包含并发控制机制，确保数据一致性。

Features:
- 文件锁机制防止并发写入冲突
- 原子性文件替换保证数据完整性
- 自动加载和保存数据
"""
import json
import os
from models import Student, Category, Activity, Record, Entry, Admin, RegistrationQuestionnaire, ActivityQuestionnaire, QuestionnaireResponse

# 获取项目根目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Database:
    def __init__(self, data_file='data.json'):
        # 确保使用绝对路径，避免工作目录问题
        if not os.path.isabs(data_file):
            # 获取当前文件所在目录
            self.data_file = os.path.join(BASE_DIR, data_file)
        else:
            self.data_file = data_file
        
        self.students = {}
        self.categories = {}
        self.activities = {}
        self.records = {}
        self.admins = {}
        self.departments = []
        self.total_required_credits = 0
        self.registration_questionnaires = {}  # 注册问卷
        self.activity_questionnaires = {}      # 活动问卷模板
        self.questionnaire_responses = {}      # 问卷填写记录
        # 邮箱配置
        self.email_config = {
            'service_email': '',           # 服务邮箱
            'service_email_password': '',  # 服务邮箱密码（SMTP）
            'student_email_suffix': '',    # 学生邮箱后缀（如：@example.com）
        }
        self.load_data()
    
    def load_data(self):
        """
        从JSON文件加载数据到内存
        
        加载内容包括：
        - 学生信息
        - 管理员信息
        - 类别设置
        - 活动、记录和条目数据
        - 总学分要求
        
        如果文件不存在，则初始化为空数据。
        """
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 加载学生（密码明文存储）
                for sid, sdata in data.get('students', {}).items():
                    password_reset_required = sdata.get('password_reset_required', False)
                    self.students[sid] = Student(sid, sdata['name'], sdata['password'], password_reset_required)
                
                # 加载管理员
                for aid, adata in data.get('admins', {}).items():
                    self.admins[aid] = Admin(
                        aid, 
                        adata['password'], 
                        adata.get('role', 'admin'),
                        adata.get('department', '')
                    )
                
                # 加载类别
                for cname, cdata in data.get('categories', {}).items():
                    self.categories[cname] = Category(cname, cdata['required_credits'])
                
                # 加载部门
                self.departments = data.get('departments', [])
                
                self.total_required_credits = data.get('total_required_credits', 0)
                
                # 加载邮箱配置
                default_config = {
                    'service_email': '',
                    'service_email_password': '',
                    'student_email_suffix': '',
                }
                loaded_config = data.get('email_config', {})
                self.email_config = {**default_config, **loaded_config}
                
                # 加载活动、记录和条目
                for aid, adata in data.get('activities', {}).items():
                    activity = Activity(
                        aid, 
                        adata['name'], 
                        adata['categories'],
                        adata.get('department', ''),
                        adata.get('created_by', ''),
                        adata.get('allowed_editors', []),
                        adata.get('has_questionnaire', False),
                        adata.get('questionnaire_start', ''),
                        adata.get('questionnaire_end', ''),
                        adata.get('max_participants', 0)
                    )
                    self.activities[aid] = activity
                    
                    for rdata in adata.get('records', []):
                        record = Record(rdata['record_id'], aid, rdata['record_name'])
                        self.records[rdata['record_id']] = record
                        activity.records.append(record)
                        
                        for edata in rdata.get('entries', []):
                            entry = Entry(edata['student_id'], edata['credits'], edata['categories'])
                            record.entries.append(entry)
                
                # 加载注册问卷
                for qid, qdata in data.get('registration_questionnaires', {}).items():
                    questionnaire = RegistrationQuestionnaire(
                        qid,
                        qdata['student_id'],
                        qdata['name'],
                        qdata['phone'],
                        qdata['wechat'],
                        qdata.get('suggestion', ''),
                        qdata['submit_time']
                    )
                    self.registration_questionnaires[qid] = questionnaire
                
                # 加载活动问卷模板
                for qid, qdata in data.get('activity_questionnaires', {}).items():
                    questionnaire = ActivityQuestionnaire(
                        qid,
                        qdata['activity_id'],
                        qdata['title'],
                        qdata['start_time'],
                        qdata['end_time'],
                        qdata.get('max_participants', 0),
                        qdata.get('has_category_question', True),
                        qdata.get('custom_questions', []),
                        qdata.get('created_time', ''),
                        qdata.get('status', 'active')
                    )
                    self.activity_questionnaires[qid] = questionnaire
                
                # 加载问卷填写记录
                for rid, rdata in data.get('questionnaire_responses', {}).items():
                    response = QuestionnaireResponse(
                        rid,
                        rdata['questionnaire_id'],
                        rdata['student_id'],
                        rdata['student_name'],
                        rdata['phone'],
                        rdata['wechat'],
                        rdata.get('intended_category', ''),
                        rdata['submit_time'],
                        rdata.get('status', 'active'),
                        rdata.get('custom_answers', {})
                    )
                    self.questionnaire_responses[rid] = response
    
    def save_data(self):
        """
        保存数据到JSON文件
        
        使用文件锁和原子性操作确保数据安全：
        1. 创建锁文件防止并发写入
        2. 先写入临时文件
        3. 原子性替换目标文件
        4. 删除锁文件
        
        并发控制：
        - 最多等待5秒获取锁
        - 超时后强制删除锁文件
        - 使用进程ID标识锁的所有者
        """
        import threading
        import time
        
        # 使用文件锁防止并发写入
        lock_file = self.data_file + '.lock'
        max_wait = 5  # 最多等待5秒
        start_time = time.time()
        
        while os.path.exists(lock_file):
            if time.time() - start_time > max_wait:
                # 超时，强制删除锁文件
                try:
                    os.remove(lock_file)
                except:
                    pass
                break
            time.sleep(0.1)
        
        try:
            # 创建锁文件
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # 按学号排序学生
            sorted_students = sorted(self.students.items(), key=lambda x: x[0])
            
            data = {
                'students': {sid: {
                    'name': s.name, 
                    'password': s.password,
                    'password_reset_required': s.password_reset_required
                } for sid, s in sorted_students},
                'admins': {aid: {
                    'password': a.password, 
                    'role': a.role,
                    'department': a.department
                } for aid, a in self.admins.items()},
                'categories': {cname: {'required_credits': c.required_credits} 
                              for cname, c in self.categories.items()},
                'departments': self.departments,
                'total_required_credits': self.total_required_credits,
                'email_config': self.email_config,
                'activities': {}
            }
            
            # 保存注册问卷
            data['registration_questionnaires'] = {
                qid: {
                    'student_id': q.student_id,
                    'name': q.name,
                    'phone': q.phone,
                    'wechat': q.wechat,
                    'suggestion': q.suggestion,
                    'submit_time': q.submit_time
                } for qid, q in self.registration_questionnaires.items()
            }
            
            # 保存活动问卷模板
            data['activity_questionnaires'] = {
                qid: {
                    'activity_id': q.activity_id,
                    'title': q.title,
                    'start_time': q.start_time,
                    'end_time': q.end_time,
                    'max_participants': q.max_participants,
                    'has_category_question': q.has_category_question,
                    'custom_questions': q.custom_questions,
                    'created_time': q.created_time,
                    'status': q.status
                } for qid, q in self.activity_questionnaires.items()
            }
            
            # 保存问卷填写记录
            data['questionnaire_responses'] = {
                rid: {
                    'questionnaire_id': r.questionnaire_id,
                    'student_id': r.student_id,
                    'student_name': r.student_name,
                    'phone': r.phone,
                    'wechat': r.wechat,
                    'intended_category': r.intended_category,
                    'custom_answers': r.custom_answers,
                    'submit_time': r.submit_time,
                    'status': r.status
                } for rid, r in self.questionnaire_responses.items()
            }
            
            for aid, activity in self.activities.items():
                data['activities'][aid] = {
                    'name': activity.name,
                    'categories': activity.categories,
                    'department': activity.department,
                    'created_by': activity.created_by,
                    'allowed_editors': activity.allowed_editors,
                    'has_questionnaire': activity.has_questionnaire,
                    'questionnaire_start': activity.questionnaire_start,
                    'questionnaire_end': activity.questionnaire_end,
                    'max_participants': activity.max_participants,
                    'records': []
                }
                
                for record in activity.records:
                    record_data = {
                        'record_id': record.record_id,
                        'record_name': record.record_name,
                        'entries': []
                    }
                    
                    for entry in record.entries:
                        record_data['entries'].append({
                            'student_id': entry.student_id,
                            'credits': entry.credits,
                            'categories': entry.categories
                        })
                    
                    data['activities'][aid]['records'].append(record_data)
            
            # 先写入临时文件，再重命名（原子操作）
            temp_file = self.data_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子性替换
            if os.path.exists(self.data_file):
                os.replace(temp_file, self.data_file)
            else:
                os.rename(temp_file, self.data_file)
        finally:
            # 删除锁文件
            try:
                os.remove(lock_file)
            except:
                pass
