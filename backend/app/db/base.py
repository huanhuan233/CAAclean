# SQLAlchemy 声明式表模型的共同基类，所有业务表共享同一份 metadata。
from sqlalchemy.orm import DeclarativeBase


# 集中注册 ORM 表定义，供会话初始化与迁移工具使用。
class Base(DeclarativeBase):
    pass
