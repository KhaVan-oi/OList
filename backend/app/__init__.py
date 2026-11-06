"""Lắp ráp Flask. Mỗi màn là một feature, không nhét route vào file này."""

from flask import Flask
from flask_cors import CORS

from app.common.query_gateway import QueryGateway
from app.features.customer_payment.routes import create_customer_payment_blueprint
from app.features.overview.routes import create_overview_blueprint
from app.features.product_geo.routes import create_product_geo_blueprint
from app.features.sales_time.routes import create_sales_time_blueprint
from app.health import health_bp


def create_app():
    app = Flask(__name__)
    CORS(app)
    gateway = QueryGateway()
    app.register_blueprint(health_bp)
    app.register_blueprint(create_sales_time_blueprint(gateway))
    app.register_blueprint(create_overview_blueprint(gateway))
    app.register_blueprint(create_product_geo_blueprint(gateway))
    app.register_blueprint(create_customer_payment_blueprint(gateway))
    return app
