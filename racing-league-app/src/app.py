# project/src/app.py
from flask import Flask
from src.auth_module.auth_controller import auth_blueprint
from src.check_alive_module.check_alive_controller import check_alive_blue_print
from src.league_module.league_controller import league_blueprint
from src.invite_module.invite_controller import invite_blueprint
from src.user_module.user_controller import user_blueprint
from flask_cors import CORS
from src.config.config import Config
# from src.check_alive_module.ping import start_scheduler

# start_scheduler()
app = Flask(__name__)
CORS(app, supports_credentials=True, origins=Config.ORIGINS)
app.config.from_object(Config)

# Initialize Firebase
Config.init_firebase()

# Register blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(league_blueprint)
app.register_blueprint(invite_blueprint)
app.register_blueprint(user_blueprint)
app.register_blueprint(check_alive_blue_print)


if __name__ == '__main__':
    app.run(debug=True)
