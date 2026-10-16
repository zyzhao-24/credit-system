"""
数据模型定义

定义了系统中使用的所有数据模型类：
- Student: 学生模型
- Category: 类别模型
- Activity: 活动模型
- Record: 记录模型
- Entry: 学分条目模型
"""

class Student:
    """
    学生模型
    
    Attributes:
        student_id (str): 学号（只能包含数字）
        name (str): 姓名
        password (str): 密码（明文存储，登录时客户端哈希传输）
        password_reset_required (bool): 是否需要重置密码
    """
    def __init__(self, student_id, name, password, password_reset_required=False):
        self.student_id = student_id
        self.name = name
        self.password = password
        self.password_reset_required = password_reset_required

class Admin:
    """
    管理员模型
    
    Attributes:
        admin_id (str): 管理员账号
        password (str): 密码（明文存储，登录时客户端哈希传输）
        role (str): 角色类型 ('admin' 或 'system_admin')
        department (str): 所属部门（仅普通管理员）
    """
    def __init__(self, admin_id, password, role='admin', department=''):
        self.admin_id = admin_id
        self.password = password
        self.role = role  # 'admin' 或 'system_admin'
        self.department = department

class Category:
    """
    类别模型
    
    Attributes:
        name (str): 类别名称
        required_credits (float): 该类别合格所需学分
    """
    def __init__(self, name, required_credits):
        self.name = name
        self.required_credits = required_credits

class Activity:
    """
    活动模型
    
    Attributes:
        activity_id (str): 活动唯一标识符（UUID）
        name (str): 活动名称
        categories (list): 活动所属类别列表
        department (str): 负责部门
        created_by (str): 创建者管理员ID
        allowed_editors (list): 允许编辑的管理员ID列表
        records (list): 该活动下的记录列表
        has_questionnaire (bool): 是否开启报名问卷
        questionnaire_start (str): 报名开始时间
        questionnaire_end (str): 报名截止时间
        max_participants (int): 最大报名人数（0表示不限制）
    """
    def __init__(self, activity_id, name, categories, department='', created_by='', allowed_editors=None,
                 has_questionnaire=False, questionnaire_start='', questionnaire_end='', max_participants=0):
        self.activity_id = activity_id
        self.name = name
        self.categories = categories
        self.department = department
        self.created_by = created_by
        self.allowed_editors = allowed_editors if allowed_editors is not None else []
        self.records = []
        self.has_questionnaire = has_questionnaire
        self.questionnaire_start = questionnaire_start
        self.questionnaire_end = questionnaire_end
        self.max_participants = max_participants

class Record:
    """
    记录模型
    
    一个活动可以有多条记录，每条记录包含多个学分条目。
    
    Attributes:
        record_id (str): 记录唯一标识符（UUID）
        activity_id (str): 所属活动ID
        record_name (str): 记录名称
        entries (list): 该记录下的学分条目列表
    """
    def __init__(self, record_id, activity_id, record_name):
        self.record_id = record_id
        self.activity_id = activity_id
        self.record_name = record_name
        self.entries = []

class Entry:
    """
    学分条目模型
    
    记录学生在某个活动记录中获得的学分。
    
    Attributes:
        student_id (str): 学生学号
        credits (float): 获得的学分
        categories (list): 可选类别列表（活动类别的子集）
    
    Note:
        学分会通过智能算法分配到最优类别，以最大化合格的类别数量。
    """
    def __init__(self, student_id, credits, categories):
        self.student_id = student_id
        self.credits = credits
        self.categories = categories

class RegistrationQuestionnaire:
    """
    注册问卷模型
    
    记录学生的注册信息（独立于Student模型）。
    用于初级团校报名，包含详细的联系方式和建议。
    
    Attributes:
        questionnaire_id (str): 问卷ID（UUID）
        student_id (str): 学生学号
        name (str): 学生姓名
        phone (str): 手机号
        wechat (str): 微信号
        suggestion (str): 对团校活动的建议
        submit_time (str): 提交时间
    """
    def __init__(self, questionnaire_id, student_id, name, phone, wechat, suggestion, submit_time):
        self.questionnaire_id = questionnaire_id
        self.student_id = student_id
        self.name = name
        self.phone = phone
        self.wechat = wechat
        self.suggestion = suggestion
        self.submit_time = submit_time

class ActivityQuestionnaire:
    """
    活动问卷模板
    
    管理员创建的问卷模板，学生可以填写。
    
    Attributes:
        questionnaire_id (str): 问卷ID（UUID）
        activity_id (str): 关联的活动ID
        title (str): 问卷标题
        start_time (str): 开始时间
        end_time (str): 截止时间
        max_participants (int): 最大人数（0=不限）
        has_category_question (bool): 是否包含意向类别题
        custom_questions (list): 自定义题目列表
        created_time (str): 创建时间
        status (str): 状态（active/closed）
    """
    def __init__(self, questionnaire_id, activity_id, title, start_time, end_time, 
                 max_participants=0, has_category_question=True, custom_questions=None,
                 created_time='', status='active'):
        self.questionnaire_id = questionnaire_id
        self.activity_id = activity_id
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.max_participants = max_participants
        self.has_category_question = has_category_question
        self.custom_questions = custom_questions if custom_questions is not None else []
        self.created_time = created_time
        self.status = status

class QuestionnaireResponse:
    """
    问卷填写记录
    
    学生填写问卷后的提交记录。
    
    Attributes:
        response_id (str): 记录ID（UUID）
        questionnaire_id (str): 问卷ID
        student_id (str): 学生学号
        student_name (str): 学生姓名
        phone (str): 手机号
        wechat (str): 微信号
        intended_category (str): 意向学分类别
        custom_answers (dict): 自定义题目答案
        submit_time (str): 提交时间
        status (str): 状态（active/cancelled）
    """
    def __init__(self, response_id, questionnaire_id, student_id, student_name, 
                 phone, wechat, intended_category, submit_time, status='active', custom_answers=None):
        self.response_id = response_id
        self.questionnaire_id = questionnaire_id
        self.student_id = student_id
        self.student_name = student_name
        self.phone = phone
        self.wechat = wechat
        self.intended_category = intended_category
        self.custom_answers = custom_answers if custom_answers is not None else {}
        self.submit_time = submit_time
        self.status = status
