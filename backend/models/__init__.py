"""Public model imports for migrations and application setup."""

from backend.models.activity import (  # noqa: F401
    Activity,
    ActivityAllowedEditor,
    Entry,
    EntryCategory,
    Record,
    RecordCategory,
)
from backend.models.core import (  # noqa: F401
    Admin,
    Category,
    Department,
    EmailConfig,
    EmailVerification,
    Setting,
    Student,
    TrustedDevice,
)
from backend.models.feedback import Feedback  # noqa: F401
from backend.models.questionnaire import (  # noqa: F401
    ActivityQuestionnaire,
    QuestionnaireResponse,
)
