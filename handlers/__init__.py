from . import user, admin, superadmin, group

routers = (
    user.router,
    admin.router,
    superadmin.router,
    group.router,
)
