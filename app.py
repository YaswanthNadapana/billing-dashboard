from flask import Flask, render_template, request, redirect, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from datetime import datetime
import io
import qrcode
import random
import time
import os

app = Flask(__name__)
app.secret_key = "secret123"

login_manager = LoginManager(app)
login_manager.login_view = "login"

users = []
bills = []
payments = []


# PUBLIC HOME PAGE (FOR RAZORPAY VERIFICATION)
@app.route("/")
def home():
    return """
    <h1>Billing Dashboard</h1>
    <p>This is a demo billing dashboard project used for invoice management.</p>
    <a href="/login">Login</a>
    """


# USER CLASS
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


@login_manager.user_loader
def load_user(user_id):
    return next((u for u in users if u.id == int(user_id)), None)


# REGISTER
@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        users.append(User(len(users), username, password))

        flash("Account created!", "success")
        return redirect('/login')

    return render_template("register.html")


# LOGIN
@app.route('/login', methods=['GET','POST'])
def login():

    error = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        user = next((u for u in users if u.username == username), None)

        if user and check_password_hash(user.password, password):

            login_user(user)
            return redirect('/dashboard')

        else:
            error = "Invalid credentials"

    return render_template("login.html", error=error)


# LOGOUT
@app.route('/logout')
@login_required
def logout():

    logout_user()
    return redirect('/login')


# DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():

    query = request.args.get("q","").lower()

    user_bills = [b for b in bills if b['user'] == current_user.id]

    if query:
        user_bills = [b for b in user_bills if query in b['category'].lower()]

    total = sum(b['amount'] for b in user_bills)
    paid = sum(b['amount'] for b in user_bills if b['status']=="Paid")
    pending = total - paid

    today = datetime.today().date()

    return render_template(
        "dashboard.html",
        bills=user_bills,
        total=total,
        paid=paid,
        pending=pending,
        today=today,
        username=current_user.username
    )


# ADD BILL
@app.route('/add', methods=['GET','POST'])
@login_required
def add_bill():

    if request.method == 'POST':

        category = request.form['category']
        amount = float(request.form['amount'])
        due_date = request.form['due_date']

        invoice_no = f"INV-{len(bills)+1:03d}"

        bills.append({
            "invoice": invoice_no,
            "user": current_user.id,
            "category": category,
            "amount": amount,
            "due_date": due_date,
            "status": "Pending"
        })

        flash("Bill added!", "success")
        return redirect('/dashboard')

    return render_template("add.html")


# PAYMENT PAGE
@app.route('/pay/<int:id>')
@login_required
def pay_bill(id):

    user_bills = [b for b in bills if b['user']==current_user.id]
    bill = user_bills[id]

    return render_template("pay.html", bill=bill, bill_id=id)


# QR CODE GENERATOR
@app.route('/qr/<int:id>')
@login_required
def generate_qr(id):

    user_bills=[b for b in bills if b['user']==current_user.id]
    bill=user_bills[id]

    upi_id="yashnaidu1192-2@okicici"
    name="Yaswanth Billing"

    upi_link=f"upi://pay?pa={upi_id}&pn={name}&am={bill['amount']}&cu=INR"

    img=qrcode.make(upi_link)

    buffer=io.BytesIO()
    img.save(buffer)
    buffer.seek(0)

    return send_file(buffer,mimetype="image/png")


# PROCESS PAYMENT (SIMULATION)
@app.route('/process_payment/<int:id>')
@login_required
def process_payment(id):

    user_bills=[b for b in bills if b['user']==current_user.id]
    bill=user_bills[id]

    time.sleep(2)

    txn_id="TXN"+str(random.randint(100000,999999))

    bill['status']="Paid"
    bill['transaction']=txn_id

    payments.append({
        "invoice":bill['invoice'],
        "amount":bill['amount'],
        "date":datetime.now().strftime("%d-%m-%Y %H:%M"),
        "transaction":txn_id
    })

    flash("Payment successful","success")

    return redirect('/dashboard')


# DELETE BILL
@app.route('/delete/<int:id>')
@login_required
def delete_bill(id):

    user_bills=[b for b in bills if b['user']==current_user.id]
    bills.remove(user_bills[id])

    flash("Bill deleted","danger")

    return redirect('/dashboard')


# PAYMENT HISTORY
@app.route('/history')
@login_required
def history():

    return render_template("history.html", payments=payments)


# PDF INVOICE
@app.route('/invoice/<int:id>')
@login_required
def invoice(id):

    user_bills=[b for b in bills if b['user']==current_user.id]
    bill=user_bills[id]

    buffer=io.BytesIO()

    pdf=canvas.Canvas(buffer)

    pdf.setFont("Helvetica-Bold",18)
    pdf.drawString(200,800,"INVOICE")

    pdf.setFont("Helvetica",12)

    pdf.drawString(50,750,f"Invoice: {bill['invoice']}")
    pdf.drawString(50,720,f"Category: {bill['category']}")
    pdf.drawString(50,690,f"Amount: ₹{bill['amount']}")
    pdf.drawString(50,660,f"Due Date: {bill['due_date']}")
    pdf.drawString(50,630,f"Status: {bill['status']}")

    txn=bill.get("transaction","N/A")
    pdf.drawString(50,600,f"Transaction ID: {txn}")

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="invoice.pdf",
        mimetype='application/pdf'
    )


# RENDER DEPLOYMENT PORT
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)