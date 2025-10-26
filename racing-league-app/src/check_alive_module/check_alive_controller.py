from flask import Blueprint, request, jsonify

check_alive_blue_print = Blueprint('check_alive', __name__, url_prefix='/api/v1/check')

@check_alive_blue_print.route('', methods=['GET'])
def check_alive():
    return jsonify({"message": "Service is alive!"}), 200