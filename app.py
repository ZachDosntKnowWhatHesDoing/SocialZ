from flask import Flask, render_template, redirect

app = Flask(__name__)

# Optional: Temporary redirect all traffic
@app.before_request
def redirect_to_maintenance():
    # Allow admin or certain paths if needed
    return render_template("maintenance.html")
