# project/src/app.py
from flask import Flask
from src.config.config import Config
from src.auth_module.auth_controller import auth_blueprint
from src.league_module.league_controller import league_blueprint
from src.invite_module.invite_controller import invite_blueprint
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "https://racing-league-app.web.app", "https://racing-league-app.firebaseapp.com", "http://localhost:3000"])
app.config.from_object(Config)

# Initialize Firebase
Config.init_firebase()

# Register blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(league_blueprint)
app.register_blueprint(invite_blueprint)

if __name__ == '__main__':
    app.run(debug=True)
