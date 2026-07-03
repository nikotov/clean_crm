from clean-crm.main import c
print('\n'.join(f'{r.path} {r.methods}' for r in app.router.routes))