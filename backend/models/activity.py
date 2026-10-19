"""Activity, record, and credit-entry models.

Entry.student_id intentionally has no foreign key: the legacy system allows
credit entries for students who are not present in the student table.
"""

from backend.extensions import db


class RecordCategory(db.Model):
    """记录一级的学分类别：条目类别必须从记录类别中选择。"""

    __tablename__ = "record_categories"

    record_id = db.Column(
        db.String(36),
        db.ForeignKey("records.record_id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_name = db.Column(
        db.String(100),
        db.ForeignKey("categories.name", onupdate="CASCADE"),
        primary_key=True,
    )
    position = db.Column(db.Integer, nullable=False, default=0)

    record = db.relationship("Record", back_populates="category_links")
    category = db.relationship("Category")


class ActivityAllowedEditor(db.Model):
    __tablename__ = "activity_allowed_editors"

    activity_id = db.Column(
        db.String(36),
        db.ForeignKey("activities.activity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    admin_id = db.Column(
        db.String(100),
        db.ForeignKey("admins.admin_id"),
        primary_key=True,
    )
    position = db.Column(db.Integer, nullable=False, default=0)

    activity = db.relationship("Activity", back_populates="allowed_editor_links")
    admin = db.relationship("Admin")


class Activity(db.Model):
    __tablename__ = "activities"

    activity_id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False, default="")
    created_by = db.Column(db.String(100), db.ForeignKey("admins.admin_id"), nullable=True)
    has_questionnaire = db.Column(db.Boolean, nullable=False, default=False)
    questionnaire_start = db.Column(db.DateTime, nullable=True)
    questionnaire_end = db.Column(db.DateTime, nullable=True)
    max_participants = db.Column(db.Integer, nullable=False, default=0)
    position = db.Column(db.Integer, nullable=False, default=0)

    allowed_editor_links = db.relationship(
        "ActivityAllowedEditor",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityAllowedEditor.position",
    )
    records = db.relationship(
        "Record",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="Record.position",
    )

    @property
    def categories(self) -> list[str]:
        """活动类别是各记录类别的并集（按记录、类别的声明顺序去重）。"""
        names: list[str] = []
        for record in self.records:
            for name in record.categories:
                if name not in names:
                    names.append(name)
        return names

    @property
    def allowed_editors(self) -> list[str]:
        return [link.admin_id for link in self.allowed_editor_links]

    @allowed_editors.setter
    def allowed_editors(self, admin_ids: list[str]) -> None:
        self.allowed_editor_links = [
            ActivityAllowedEditor(admin_id=admin_id, position=index)
            for index, admin_id in enumerate(admin_ids)
        ]


class Record(db.Model):
    __tablename__ = "records"

    record_id = db.Column(db.String(36), primary_key=True)
    activity_id = db.Column(
        db.String(36),
        db.ForeignKey("activities.activity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_name = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    activity = db.relationship("Activity", back_populates="records")
    category_links = db.relationship(
        "RecordCategory",
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="RecordCategory.position",
    )
    entries = db.relationship(
        "Entry",
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="Entry.position",
    )

    @property
    def categories(self) -> list[str]:
        return [link.category_name for link in self.category_links]

    @categories.setter
    def categories(self, names: list[str]) -> None:
        self.category_links = [
            RecordCategory(category_name=name, position=index)
            for index, name in enumerate(names)
        ]


class EntryCategory(db.Model):
    __tablename__ = "entry_categories"

    entry_id = db.Column(
        db.Integer,
        db.ForeignKey("entries.entry_id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_name = db.Column(
        db.String(100),
        db.ForeignKey("categories.name", onupdate="CASCADE"),
        primary_key=True,
    )
    position = db.Column(db.Integer, nullable=False, default=0)

    entry = db.relationship("Entry", back_populates="category_links")
    category = db.relationship("Category")


class Entry(db.Model):
    __tablename__ = "entries"

    entry_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column(
        db.String(36),
        db.ForeignKey("records.record_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(db.String(32), nullable=False, index=True)
    credits = db.Column(db.Float, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    record = db.relationship("Record", back_populates="entries")
    category_links = db.relationship(
        "EntryCategory",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryCategory.position",
    )

    @property
    def categories(self) -> list[str]:
        return [link.category_name for link in self.category_links]

    @categories.setter
    def categories(self, names: list[str]) -> None:
        self.category_links = [
            EntryCategory(category_name=name, position=index)
            for index, name in enumerate(names)
        ]
