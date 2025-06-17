from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Gmail SMTP config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = '' 
app.config['MAIL_PASSWORD'] = ''      

mail = Mail(app)

@app.route("/")
def send_test_mail():
    try:
        msg = Message(
            subject="✅ Flask Mail Test",
            sender=app.config['MAIL_USERNAME'],
            recipients=["testreceiver@example.com"],  
            body="Hi! This is a test email from Flask-Mail."
        )
        mail.send(msg)
        return "✅ Email sent successfully!"
    except Exception as e:
        return f"❌ Failed to send email: {e}"

if __name__ == "__main__":
    app.run(debug=True)
