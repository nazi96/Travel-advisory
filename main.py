"""
Google App Engine: Current World Travel Advisory
Main entry point for the Flask application.

Project Group 2 - Final Project
Members: Nazanin Amini, Lorie Blount, Michael Hawkins
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Cloud Run / App Engine sets PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
