from flask import Blueprint, jsonify
from src.league_module.point_system_preset import PointSystemPreset

point_system_blueprint = Blueprint('point_system', __name__, url_prefix='/api/v1/point-systems')


@point_system_blueprint.route('', methods=['GET'])
def get_presets():
    """Get all active point system presets"""
    presets = PointSystemPreset.get_active()
    return jsonify([p.serialize() for p in presets]), 200
