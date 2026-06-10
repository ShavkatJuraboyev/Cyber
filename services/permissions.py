from handlers.common import (
    PANEL_MODULES, CRUD_ACTIONS, PANEL_PERMISSIONS, module_has_any, can_perm,
    can_read, can_create, can_update, can_delete, can_action, is_super_admin,
    has_panel_access, demote_panel_admin_if_empty, deny_if_no_permission, is_group_admin,
)
