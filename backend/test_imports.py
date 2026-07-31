import sys
sys.path.insert(0, 'backend')
from app.component_builds.service import ComponentBuildService
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
print('All imports OK')
print('Service methods:', [m for m in dir(ComponentBuildService) if not m.startswith('_')])
print('Repo methods:', [m for m in dir(SqlAlchemyComponentBuildRepository) if not m.startswith('_')])
