# -*- coding: utf-8 -*-
# app.py - 主应用入口

import os
import sys
from flask import Flask, render_template
from flask_login import LoginManager

from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, UPLOAD_FOLDER, DEFAULT_ADMIN
from models import db, User


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_AS_ASCII"] = False

    for subdir in ["images", "videos"]:
        os.makedirs(os.path.join(UPLOAD_FOLDER, subdir), exist_ok=True)

    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
            # 自动创建默认管理员账户
            admin = User.query.filter_by(username=DEFAULT_ADMIN["username"]).first()
            if admin is None:
                admin = User(
                    username=DEFAULT_ADMIN["username"],
                    is_admin=True,
                )
                admin.set_password(DEFAULT_ADMIN["password"])
                db.session.add(admin)
                db.session.commit()
                print("[INIT] 默认管理员已创建: " + DEFAULT_ADMIN["username"])
        except Exception as e:
            print("[WARNING] DB init failed: " + str(e), file=sys.stderr)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from auth import auth_bp
    from excel_routes import excel_bp
    from media_routes import media_bp
    from chart_routes import chart_bp
    from param_query import param_bp
    from print_routes import print_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(excel_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(chart_bp)
    app.register_blueprint(param_bp)
    app.register_blueprint(print_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(404)
    def not_found(e):
        return render_template("base.html", content="<h3>404</h3>"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("base.html", content="<h3>500</h3>"), 500

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, debug=True)
