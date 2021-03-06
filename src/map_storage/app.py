# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Expose the main application."""

import logging
import logging.config

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from raven.contrib.flask import Sentry
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from . import errorhandlers, jwt, resources


app = Flask(__name__)


def init_app(application):
    """Initialize the main app with config information and routes."""
    from map_storage.settings import current_config

    application.config.from_object(current_config())

    # Configure logging
    logging.config.dictConfig(application.config["LOGGING"])

    # Configure Sentry
    if application.config["SENTRY_DSN"]:
        sentry = Sentry(
            dsn=application.config["SENTRY_DSN"],
            logging=True,
            level=logging.ERROR,
        )
        sentry.init_app(application)

    # Initialize the database
    from .models import db

    Migrate(application, db)
    db.init_app(application)

    # Add JWT handling middleware
    jwt.init_app(application)

    # Register error handlers
    errorhandlers.init_app(application)

    # Add routes and resources.
    resources.init_app(application)

    # Add CORS information for all resources.
    CORS(application)

    # Add an error handler for webargs parser error, ensuring a JSON response
    # including all error messages produced from the parser.
    @application.errorhandler(422)
    def handle_webargs_error(error):
        response = jsonify(error.data["messages"])
        response.status_code = error.code
        return response

    # Handle werkzeug HTTPExceptions (typically raised through `flask.abort`) by
    # returning a JSON response including the error description.
    @application.errorhandler(HTTPException)
    def handle_error(error):
        response = jsonify({"message": error.description})
        response.status_code = error.code
        return response

    # Please keep in mind that it is a security issue to use such a middleware
    # in a non-proxy setup because it will blindly trust the incoming headers
    # which might be forged by malicious clients.
    # We require this in order to serve the HTML version of the OpenAPI docs
    # via https.
    application.wsgi_app = ProxyFix(application.wsgi_app)
