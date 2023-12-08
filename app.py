from flask import Flask,render_template,request,redirect,url_for,session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from flask_mail import Mail, Message
import secrets


app = Flask(__name__)

app.secret_key = 'super_tajni_kljuc'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'e-poslovanje'

app.config['MAIL_SERVER'] = 'smtp.yandex.com'
app.config['MAIL_PORT'] = 587  # Yandex obično koristi port 587 za TLS
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False


mail = Mail(app)


mysql = MySQL(app)

@app.route('/')
def home():
    ulogovan = False
    if 'loggedin' in session and session['loggedin']:
        ulogovan = True
        return render_template('index.html',ulogovan=ulogovan)
    else:
        return render_template('index.html',ulogovan=ulogovan)


@app.route('/login',methods = ['GET','POST'])
def login():
    if 'loggedin' in session and session['loggedin']:
        return redirect(url_for('home'))   
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = % s AND password = % s',(username,password))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['tip'] = account['tip']
            msg = 'Logged in successfully!'
            return redirect(url_for('home'))
            #return render_template('index.html',msg=msg)
        else:
            msg = 'Incorrect username/password'
    return render_template('login.html',msg=msg)

@app.route('/logout')
def logout():
    session.pop('loggedin',None)
    session.pop('id',None)
    session.pop('username',None)
    return redirect(url_for('login'))

@app.route('/register',methods=['GET','POST'])
def register():
    if 'loggedin' in session and session['loggedin']:
        return redirect(url_for('home'))   
    reg = False   
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form and 'ime' in request.form and 'prezime' in request.form and 'telefon' in request.form and 'tip' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        ime = request.form['ime']
        prezime = request.form['prezime']
        telefon = request.form['telefon']
        tip = request.form['tip']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s',(username, ))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email adress'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
        elif not username or not password or not email or not ime or not prezime or not telefon or not tip:
            msg = 'Please fill out the form! '
        else:
            cursor.execute('INSERT INTO accounts VALUES (NULL, % s, % s, % s, % s, % s, % s , % s)',(username,password,email,ime,prezime,telefon,tip, ))
            mysql.connection.commit()
            msg = 'You have successfully registered'
            verification_token = secrets.token_urlsafe(16) 
            verification_link = url_for('verify_email', token=verification_token, _external=True)
            mejlporuka = Message('Dobrodošlica na TerminiSrbija!', sender = 'terminisrbija@yandex.com', recipients = [str(email)])
            mejlporuka.body = 'Zdravo ' + ime + ', ' +  f'Dobrodošao na TerminiSrbija! Verifikuj svoju email adresu: {verification_link}'
            #mejlporuka.body = 'Zdravo ' + str(ime) + ' ! Dobrodošao na TerminiSrbija!'
            mail.send(mejlporuka)
            reg = True
    elif request.method == 'POST':
        msg = 'Please fill out the form!'
    return render_template('register.html',msg=msg,reg=reg)


@app.route('/verify_email/<token>')
def verify_email(token):
    return redirect(url_for('success_page'))

@app.route('/success_page')
def success_page():
    return render_template('success.html')

@app.route('/dodavanje_sale',methods=['GET','POST'])
def dodavanjesale():
    if 'loggedin' not in session or not session['loggedin'] or session['tip'] == 2 :
        return redirect(url_for('home'))
    msg = ''
    if request.method == "POST":
        id_vlasnika = session['id']
        naziv_sale = request.form.get('naziv_sale')
        cena_po_satu = request.form.get('cena_po_satu')
        opis = request.form.get('opis')
        grad = request.form.get('grad')
        adresa = request.form.get('adresa')
        print(naziv_sale, cena_po_satu, opis, grad, adresa)
        
        if not all([naziv_sale, cena_po_satu, opis, grad, adresa]):
            msg = 'Molimo vas da popunite sva polja!'
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('INSERT INTO balon_sale VALUES (NULL, %s, %s, %s, %s, %s, %s)', (id_vlasnika, naziv_sale, cena_po_satu, opis, grad, adresa))
            mysql.connection.commit()
            msg = 'Uspešno ste dodali salu!'
    return render_template('dodavanje_sale.html',msg=msg)

if __name__ == '__main__':
    app.run(debug=True)

