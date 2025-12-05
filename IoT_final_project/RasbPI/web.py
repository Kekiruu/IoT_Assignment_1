from flask import Flask, render_template, request, send_file , redirect, url_for, flash
import csv
import io
import sqlite3
import plotly.graph_objs as go
import plotly.offline as pyo
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import requests
import signal
import paho.mqtt.client as mqtt

looking_at_dashboard = True
MQTT_BROKER = "localhost"  # Or your broker's IP/hostname
MQTT_PORT = 1883
TOPIC = "web/button/message"

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# Monitoring files
CONTROLLER_PID = "/tmp/iot_controller.pid"
CONTROLLER_HEARTBEAT = "/tmp/iot_controller.heartbeat"
HISTORIAN_HEARTBEAT = "/tmp/historian.heartbeat"

def check_service_health(service_name, heartbeat_file):
    """Check if a service is healthy by reading heartbeat"""
    try:
        with open(heartbeat_file, 'r') as f:
            last_beat = f.read().strip()
            last_time = datetime.fromisoformat(last_beat)
            age = (datetime.now() - last_time).seconds
            
            if age < 10:
                return {'status': 'healthy', 'age': age}
            elif age < 30:
                return {'status': 'warning', 'age': age}
            else:
                return {'status': 'dead', 'age': age}
    except FileNotFoundError:
        return {'status': 'missing', 'age': None}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_system_status():
    """Get health status of all services"""
    return {
        'historian': check_service_health('historian', HISTORIAN_HEARTBEAT),
        'controller': check_service_health('controller', CONTROLLER_HEARTBEAT)
    }


users = {
    "admin":'scrypt:32768:8:1$5Mfd7sHtNITC1SSE$934f44eda3d3ec843d33c1d2cfee96cc3108c1d9af0eb0a7e79a0172870d3526a66763d3257c5ff5d13e22ddc783ea388fc77588864d63215a3bc8bb973d5b01',
    "test":'scrypt:32768:8:1$NsI3nazIXsdolIUX$44f0702d6b042dbdc78c667446d9b714ab4b1b6296e7fae5ebcfc8a9e9d8fb518e80bc43e7dec83bd5dedf649a2bf6d85d44c2a839bcd2995eef87a2fba4620b'
}

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret"  # Required for session security

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

RULES_FILE = 'rules.json'

def load_rules():
    """Load rules from the JSON file"""
    if not os.path.exists(RULES_FILE):
        return []
    try:
        with open(RULES_FILE, 'r') as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"Error loading rules: {e}")
        return []

def save_rules(rules):
    """Save rules to the JSON file"""
    try:
        with open(RULES_FILE, 'w') as file:
            json.dump(rules, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving rules: {e}")
        return False

def convert_value(value_string):
    """Convert a string to a number if possible, otherwise keep as string"""
    try:
        # Try to convert to float first
        value = float(value_string)
        # If it's a whole number, convert to int
        if value.is_integer():
            return int(value)
        return value
    except ValueError:
        # It's not a number, return as string
        return value_string
@app.route('/rules')
@login_required
def list_rules():
    """Display all automation rules"""
    rules = load_rules()
    return render_template('rules_list.html', rules=rules)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':  # Form submission
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and check_password_hash(users[username], password):
            user = User(username)
            login_user(user)
            flash("Logged in successfully.", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('plot_data'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')

@app.route('/manual')
def manual():
    return render_template('manual.html')

@app.route('/publish/<msg>', methods=['POST'])
def publish_message(msg):
    mqtt_client.publish("robot/manual-movement", msg)
    return ("", 204)


@app.route('/rules/new', methods=['GET', 'POST'])
@login_required
def create_rule():
    """Create a new automation rule"""
    if request.method == 'POST':
        # Get condition data from form arrays
        topics = request.form.getlist('condition_topic[]')
        comparisons = request.form.getlist('condition_comparison[]')
        values = request.form.getlist('condition_value[]')
        
        # Build conditions list
        conditions = []
        for topic, comparison, value in zip(topics, comparisons, values):
            conditions.append({
                'topic': topic.strip(),
                'comparison': comparison,
                'value': convert_value(value.strip())
            })
        
        # Get action data
        action = {
            'message': request.form['action_message'].strip(),
            'topic': request.form['action_topic'].strip(),
            'value': request.form['action_value'].strip()
        }
        
        # Create the new rule
        new_rule = {
            'conditions': conditions,
            'action': action
        }
        
        # Add to rules and save
        rules = load_rules()
        rules.append(new_rule)
        
        if save_rules(rules):
            flash('Rule created successfully!', 'success')
        else:
            flash('Error saving rule.', 'danger')
        
        return redirect(url_for('list_rules'))
    
    # GET request - show the form
    return render_template('rule_form.html', edit_mode=False, rule=None)

@app.route('/rules/edit/<int:rule_id>', methods=['GET', 'POST'])
@login_required
def edit_rule(rule_id):
    """Edit an existing rule"""
    rules = load_rules()
    
    # Check if rule_id is valid
    if rule_id < 0 or rule_id >= len(rules):
        flash('Rule not found!', 'danger')
        return redirect(url_for('list_rules'))
    
    if request.method == 'POST':
        # Get form data (same as create)
        topics = request.form.getlist('condition_topic[]')
        comparisons = request.form.getlist('condition_comparison[]')
        values = request.form.getlist('condition_value[]')
        
        conditions = []
        for topic, comparison, value in zip(topics, comparisons, values):
            conditions.append({
                'topic': topic.strip(),
                'comparison': comparison,
                'value': convert_value(value.strip())
            })
        
        action = {
            'message': request.form['action_message'].strip(),
            'topic': request.form['action_topic'].strip(),
            'value': request.form['action_value'].strip()
        }
        
        # Update the specific rule
        rules[rule_id] = {
            'conditions': conditions,
            'action': action
        }
        
        if save_rules(rules):
            flash('Rule updated successfully!', 'success')
        else:
            flash('Error updating rule.', 'danger')
        
        return redirect(url_for('list_rules'))
    
    # GET request - show form pre-filled with existing rule
    return render_template('rule_form.html', edit_mode=True, rule=rules[rule_id], rule_id=rule_id)

@app.route('/rules/delete/<int:rule_id>', methods=['GET', 'POST'])
@login_required
def delete_rule(rule_id):
    """Delete a rule after confirmation"""
    rules = load_rules()
    
    # Check if rule_id is valid
    if rule_id < 0 or rule_id >= len(rules):
        flash('Rule not found!', 'danger')
        return redirect(url_for('list_rules'))
    
    if request.method == 'POST':
        # User confirmed deletion
        deleted_rule = rules.pop(rule_id)
        
        if save_rules(rules):
            flash(f'Rule deleted: {deleted_rule["action"]["message"]}', 'success')
        else:
            flash('Error deleting rule.', 'danger')
        
        return redirect(url_for('list_rules'))
    
    # GET request - show confirmation page
    return render_template('rule_delete.html', rule=rules[rule_id], rule_id=rule_id)

@app.route('/system/status')
@login_required
def system_status():
    """Display system health dashboard"""
    status = get_system_status()
    return render_template('system_status.html', status=status)

@app.route('/rules/reload', methods=['POST'])
@login_required
def reload_controller():
    """Send reload signal to IoT Controller"""
    # Try HTTP method first (preferred)
    try:
        response = requests.post('http://localhost:5001/reload', timeout=5)
        if response.status_code == 200:
            flash('IoT Controller rules reloaded successfully!', 'success')
            return redirect(url_for('list_rules'))
    except requests.exceptions.ConnectionError:
        pass  # Fall through to signal method
    except requests.exceptions.Timeout:
        pass  # Fall through to signal method
    
    # Fallback to Unix signal method
    try:
        with open(CONTROLLER_PID, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        flash('Reload signal sent to IoT Controller!', 'success')
    except FileNotFoundError:
        flash('Error: IoT Controller PID file not found. Is controller running?', 'danger')
    except Exception as e:
        flash(f'Error sending reload signal: {e}', 'danger')
    
    return redirect(url_for('list_rules'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))



def get_topics():
    conn = sqlite3.connect('historian_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM historian_data")
    topics = [row[0] for row in cursor.fetchall()]
    conn.close()
    return topics

def get_data_for_topic(topic):
    conn = sqlite3.connect('historian_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, message FROM historian_data WHERE topic = ? ORDER BY timestamp", (topic,))
    data = cursor.fetchall()
    conn.close()
    
    timestamps = []
    values = []
    
    for timestamp, message in data:
        timestamps.append(datetime.fromisoformat(timestamp))
        try:
            values.append(float(message))
        except ValueError:
            values.append(None)
    
    return timestamps, values

@app.route('/')
@app.route('/plot/<start_date>/<end_date>')
@login_required
def plot_data(start_date=None, end_date=None):
    looking_at_dashboard = True
    topics = get_topics()
    traces = []
    
    # Add WHERE clause to SQL query
    if start_date and end_date:
        SQL = """SELECT timestamp, message FROM historian_data 
                 WHERE topic = ? AND timestamp BETWEEN ? AND ? 
                 ORDER BY timestamp"""
        cursor.execute(SQL, (topic, start_date, end_date))
    
    for topic in topics:
        timestamps, values = get_data_for_topic(topic)
        if timestamps:
            
            
                        # In your route
            chart_type = request.args.get('type', 'line')

            if chart_type == 'bar':
                trace = go.Bar(x=timestamps, y=values, name=topic)
            elif chart_type == 'scatter':
                trace = go.Scatter(x=timestamps, y=values, mode='markers', name=topic)
            else:
                trace = go.Scatter(x=timestamps, y=values, mode='lines+markers', name=topic)
            traces.append(trace)
            
    layout = go.Layout(
        title='MQTT Historian Data',
        xaxis=dict(title='Timestamp'),
        yaxis=dict(title='Value'),
        hovermode='closest'
    )
    
    
    
    fig = go.Figure(data=traces, layout=layout)
    graph_html = pyo.plot(fig, output_type='div', include_plotlyjs='cdn')
    
    return render_template('plot.html', graph=graph_html, looking_at_dashboard=looking_at_dashboard)

@app.route('/topic/<topic_name>')
@login_required
def plot_single_topic(topic_name):
    looking_at_dashboard = False
    timestamps, values = get_data_for_topic(topic_name)
    trace = go.Scatter(x=timestamps, y=values, mode='lines+markers')
    layout = go.Layout(title=f'Data for {topic_name}')
    fig = go.Figure(data=[trace], layout=layout)
    graph_html = pyo.plot(fig, output_type='div', include_plotlyjs='cdn')
    
    return render_template('plot.html', graph=graph_html, looking_at_dashboard=looking_at_dashboard)

def get_statistics(topic):
    conn = sqlite3.connect('historian_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT AVG(CAST(message AS REAL)), 
               MIN(CAST(message AS REAL)), 
               MAX(CAST(message AS REAL))
        FROM historian_data 
        WHERE topic = ?
    """, (topic,))
    avg, min_val, max_val = cursor.fetchone()
    conn.close()
    return {'average': avg, 'minimum': min_val, 'maximum': max_val}

@app.route('/export/<topic>')
@login_required
def export_csv(topic):
    timestamps, values = get_data_for_topic(topic)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'Value'])
    
    for ts, val in zip(timestamps, values):
        writer.writerow([ts, val])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{topic.replace("/", "_")}.csv'
    )


if __name__ == '__main__':
    app.run(debug=True)

