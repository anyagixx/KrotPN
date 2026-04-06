# FILE: backend/app/tasks/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Barrel exports for background task scheduler
#   SCOPE: Re-exports TaskScheduler class and singleton instance for app lifespan wiring
#   DEPENDS: M-008 (tasks scheduler module)
#   LINKS: M-008 (background-tasks)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   TaskScheduler - APScheduler wrapper managing recurring maintenance jobs
#   task_scheduler - Global singleton scheduler instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Tasks module exports.

MODULE_CONTRACT
- PURPOSE: Barrel exports for background task scheduler.
- SCOPE: Re-exports TaskScheduler class and singleton instance for app lifespan wiring.
- DEPENDS: M-012 scheduler (scheduler module).
- LINKS: M-012 background-tasks.

MODULE_MAP
- TaskScheduler: APScheduler wrapper managing recurring maintenance jobs.
- task_scheduler: Global singleton scheduler instance.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite barrel markup for tasks module.
"""
# <!-- GRACE: role="BARREL" module="M-012" MAP_MODE="SUMMARY" -->

from app.tasks.scheduler import TaskScheduler, task_scheduler

# <!-- START_BLOCK: __all__ -->
__all__ = [
    "TaskScheduler",
    "task_scheduler",
]
# <!-- END_BLOCK: __all__ -->
