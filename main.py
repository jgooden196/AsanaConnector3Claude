from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from repair_workflow import (
    client, 
    process_repair_request, 
    is_repair_form_task, 
    REPAIR_PROJECT_ID, 
    send_email_notification
)
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    """Landing page with info and links"""
    html_response = """
    <html>
    <head>
        <title>Property Repair Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            .container { max-width: 600px; margin: 0 auto; }
            h1 { color: #333; }
            .button { 
                display: inline-block; 
                background: #4CAF50; 
                color: white; 
                padding: 10px 20px; 
                text-decoration: none; 
                border-radius: 4px; 
                margin: 10px; 
                text-align: center;
            }
            .grid { 
                display: flex; 
                flex-wrap: wrap; 
                justify-content: center; 
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Property Repair Management</h1>
            <p>Use this page to manually trigger actions for the repair management system.</p>
            
            <div class="grid">
                <a href="/manual-trigger" class="button">Dashboard</a>
                <a href="/health" class="button">Health Check</a>
            </div>
            
            <hr>
            <p>Current time: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        </div>
    </body>
    </html>
    """
    return html_response

@app.route('/manual-trigger', methods=['GET'])
def manual_trigger():
    """User-friendly endpoint to manually trigger processing of recent tasks"""
    try:
        html_response = """
        <html>
        <head>
            <title>Property Repair Management</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                .container { max-width: 600px; margin: 0 auto; }
                h1 { color: #333; }
                .button { 
                    display: inline-block; 
                    background: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 4px; 
                    margin: 10px; 
                    text-align: center;
                }
                .grid { 
                    display: flex; 
                    flex-wrap: wrap; 
                    justify-content: center; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Property Repair Management</h1>
                <p>Use this page to manually trigger actions for the repair management system.</p>
                
                <div class="grid">
                    <a href="/process-recent" class="button">Process Recent Repair Requests</a>
                    <a href="/test-email" class="button">Send Test Email</a>
                </div>
                
                <hr>
                <p>Current time: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            </div>
        </body>
        </html>
        """
        return html_response
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/test-email', methods=['GET'])
def test_email():
    """Test the email notification system"""
    try:
        # Create a sample repair request details dictionary
        test_details = {
            'first_name': 'Test',
            'last_name': 'Tenant',
            'email': 'test@example.com',
            'phone': '(555) 123-4567',
            'address': '123 Test Street',
            'unit_number': 'Apt 4B',
            'urgency_level': 'Standard',
            'issue_category': 'Plumbing',
            'specific_issue': 'Leaky faucet',
            'description': 'This is a test description for the repair request system.'
        }
        
        # Simulate a fake task GID for testing
        test_task_gid = 'test_task_12345'
        
        # Send test email
        send_email_notification(test_details, test_task_gid)
        
        return jsonify({
            "status": "success", 
            "message": "Test email sent successfully"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Failed to send test email: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/process-task/<task_gid>', methods=['GET'])
def process_specific_task(task_gid):
    """Manually process a specific task"""
    try:
        task = client.tasks.find_by_id(task_gid)
        if is_repair_form_task(task):
            success = process_repair_request(task)
            if success:
                return jsonify({
                    "status": "success", 
                    "message": f"Task {task_gid} processed successfully"
                }), 200
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to process task {task_gid}"
                }), 500
        else:
            return jsonify({
                "status": "error", 
                "message": f"Task {task_gid} is not a repair request task"
            }), 400
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/process-recent', methods=['GET'])
def process_recent():
    """Process recent tasks from the repair project"""
    try:
        # Get tasks created in the last 24 hours
        tasks = client.tasks.find_all({
            'project': REPAIR_PROJECT_ID,
            'modified_since': (datetime.now() - timedelta(days=1)).isoformat()
        })
        
        processed_count = 0
        for task in tasks:
            if is_repair_form_task(task):
                if process_repair_request(task):
                    processed_count += 1
        
        html_response = f"""
        <html>
        <head>
            <title>Recent Tasks Processed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                .success {{ color: green; font-weight: bold; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                h1 {{ color: #333; }}
                .button {{ 
                    display: inline-block; 
                    background: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 4px; 
                    margin-top: 20px; 
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Recent Tasks Processed</h1>
                <p class="success">✅ Processed {processed_count} recent repair request tasks</p>
                <p>The system has checked for recent repair requests and processed them.</p>
                <p>Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <a href="/manual-trigger" class="button">Back to Main Menu</a>
            </div>
        </body>
        </html>
        """
        return html_response
    except Exception as e:
        return f"Error processing recent tasks: {str(e)}", 500

@app.route('/debug-simple', methods=['GET'])
def debug_simple():
    """Simple debug endpoint for tasks"""
    try:
        # Get project info
        project = client.projects.find_by_id(REPAIR_PROJECT_ID)
        
        # Get recent tasks
        tasks = list(client.tasks.find_all({
            'project': REPAIR_PROJECT_ID,
            'opt_fields': 'name,notes,created_at,custom_fields,custom_fields.name,custom_fields.type,custom_fields.enum_value'
        }))
        
        # Format HTML response
        html = f"""
        <html>
        <head>
            <title>Simple Debug</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .task {{ margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; }}
                .field {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <h1>Project and Task Debug</h1>
            
            <h2>Project Information</h2>
            <p>Project ID: {REPAIR_PROJECT_ID}</p>
            <p>Project Name: {project.get('name')}</p>
            
            <h2>Tasks ({len(tasks)})</h2>
        """
        
        # Add task information
        for task in tasks:
            html += f"""
            <div class="task">
                <h3>{task.get('name')} (ID: {task.get('gid')})</h3>
                <p>Created: {task.get('created_at')}</p>
                <p>Has notes: {"Yes" if task.get('notes') else "No"}</p>
                <h4>Custom Fields:</h4>
            """
            
            # Add custom field information
            for field in task.get('custom_fields', []):
                value = "None"
                if field.get('type') == 'enum' and field.get('enum_value'):
                    value = field.get('enum_value').get('name')
                elif field.get('type') == 'text':
                    value = field.get('text_value')
                
                html += f"""
                <div class="field">
                    <strong>{field.get('name')}</strong> ({field.get('type')}): {value}
                </div>
                """
            
            html += "</div>"
        
        html += """
            <p><a href="/manual-trigger">Back to Main Menu</a></p>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        return f"Error debugging: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
