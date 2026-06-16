"""SQLAlchemy 声明式基类与统一命名约定。"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 统一命名约定（开发规范 3.3）：索引 ix_、唯一约束 uq_、外键 fk_、主键 pk_
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，共享命名约定。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
