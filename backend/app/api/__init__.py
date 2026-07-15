"""API package: aggregates all resource blueprints under /api."""
from .bom_lists import bp as bom_lists_bp
from .comments import bp as comments_bp
from .documents import bp as documents_bp
from .inventory import bp as inventory_bp
from .lookups import bp as lookups_bp
from .projects import bp as projects_bp
from .ptemplate import bp as ptemplate_bp
from .records import bp as records_bp
from .sheets import bp as sheets_bp
from .stats import bp as stats_bp
from .tasks import bp as tasks_bp
from .users import bp as users_bp

blueprints = [
    projects_bp,
    tasks_bp,
    comments_bp,
    stats_bp,
    users_bp,
    sheets_bp,
    records_bp,
    ptemplate_bp,
    bom_lists_bp,
    documents_bp,
    lookups_bp,
    inventory_bp,
]
