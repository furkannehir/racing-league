# project/src/app.py
from flask import Flask, jsonify
from src.auth_module.auth_controller import auth_blueprint
from src.check_alive_module.check_alive_controller import check_alive_blue_print
from src.league_module.league_controller import league_blueprint
from src.league_module.point_system_controller import point_system_blueprint
from src.invite_module.invite_controller import invite_blueprint
from src.user_module.user_controller import user_blueprint
from flask_cors import CORS
from src.config.config import Config
from src.config.mongo import assert_schema_ready, ensure_indexes
from src.league_module.point_system_preset import PointSystemPreset
from src.auth_module.account_limits import configure_proxy

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=Config.ORIGINS)
app.config.from_object(Config)
configure_proxy(app)


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"message": "Request must be 13 MiB or smaller", "code": "request_too_large"}), 413

# Initialize Firebase
Config.init_firebase()

# Ensure MongoDB indexes exist
assert_schema_ready()
ensure_indexes()

# Seed default point system presets
PointSystemPreset.seed_defaults()

# Register blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(league_blueprint)
app.register_blueprint(point_system_blueprint)
app.register_blueprint(invite_blueprint)
app.register_blueprint(user_blueprint)
app.register_blueprint(check_alive_blue_print)

@app.before_request
def ensure_email_workers():
    # Start in the serving process, including when Gunicorn preloads the app.
    # Database leases coordinate delivery across each process's memory scheduler.
    if Config.INVITATION_EMAIL_WORKER_ENABLED:
        from src.invite_module.invitation_notifications import start_delivery_worker
        start_delivery_worker()
    if Config.ACCOUNT_EMAIL_WORKER_ENABLED:
        from src.email_module.account_notifications import start_delivery_worker
        start_delivery_worker()


if __name__ == '__main__':
    app.run(debug=True)
