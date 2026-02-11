from flask import Blueprint, jsonify

example_bp = Blueprint('example', __name__)


@example_bp.route('/api/hello')
def hello_world():
    return jsonify({"message": "Hello World!"})