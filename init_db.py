# -*- coding: utf-8 -*-
# init_db.py - 初始化数据库表结构和默认管理员用户
#
# 前置条件:
#   1. PostgreSQL 已安装并运行
#   2. 已创建 UTF-8 编码的数据库（在 psql/pgAdmin 中执行）:
#        CREATE DATABASE webapp_db ENCODING 'UTF8';
#   3. config.py 中的数据库连接参数正确
#
# 运行:
#   python init_db.py

from app import create_app
from models import db, User
from config import DEFAULT_ADMIN


def init_database():
    app = create_app()
    with app.app_context():
        print("checking database connection ...")
        try:
            db.engine.connect().close()
            print("database connection OK")
        except Exception as e:
            print("ERROR: cannot connect to database")
            print("  -> " + str(e))
            print()
            print("Please make sure:")
            print("  1. PostgreSQL is running")
            print("  2. Database 'webapp_db' exists with UTF-8 encoding:")
            print("       CREATE DATABASE webapp_db ENCODING 'UTF8';")
            print("  3. config.py has correct DB_CONFIG")
            return

        print("creating tables ...")
        db.create_all()
        print("tables created")

        admin = User.query.filter_by(username=DEFAULT_ADMIN["username"]).first()
        if admin is None:
            admin = User(username=DEFAULT_ADMIN["username"], is_admin=True)
            admin.set_password(DEFAULT_ADMIN["password"])
            db.session.add(admin)
            db.session.commit()
            print("admin account created: " + DEFAULT_ADMIN["username"] + " / " + DEFAULT_ADMIN["password"])
        else:
            print("admin account already exists, skipping")

        print()
        print("Done. Run: python app.py")


if __name__ == "__main__":
    init_database()