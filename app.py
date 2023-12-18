from flask import Flask,render_template,request,redirect,url_for,session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from flask_mail import Mail, Message
import secrets
import uuid,os
from werkzeug.utils import secure_filename
from mapa import generate_embed_code_from_address

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

app.config['UPLOAD_FOLDER'] = 'static/slike_sala'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}



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
            #mejlporuka.body = 'Zdravo ' + ime + ', ' +  f'Dobrodošao na TerminiSrbija! Verifikuj svoju email adresu: {verification_link}'
            mejlporuka.html = render_template('email.html',ime=ime,verlink=verification_link)
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
        
        #print(naziv_sale, cena_po_satu, opis, grad, adresa)
        
        if not all([naziv_sale, cena_po_satu, opis, grad, adresa]):
            msg = 'Molimo vas da popunite sva polja!'
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('INSERT INTO balon_sale VALUES (NULL, %s, %s, %s, %s, %s, %s)', (id_vlasnika, naziv_sale, cena_po_satu, opis, grad, adresa))
            mysql.connection.commit()
            msg = 'Uspešno ste dodali salu!'

            fajlovi = request.files.getlist('file')  # Ispravljeno pozivanje metode getlist()
            if fajlovi:
                for index, fajl in enumerate(fajlovi):
                    if fajl and allowed_file(fajl.filename) and file_size_allowed(fajl):
                        file_extension = fajl.filename.rsplit('.', 1)[1].lower()
                        unique_filename = str(uuid.uuid4()) + '.' + file_extension
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(unique_filename))
                        cursor.execute('SELECT MAX(id_sale) FROM balon_sale')
                        id_ubacene_sale = cursor.fetchone()['MAX(id_sale)'] or 0
                        fajl.save(file_path)
                        cursor.execute('INSERT INTO slike_sala (id_sale, putanja) VALUES (%s, %s)', (id_ubacene_sale, file_path))
                        mysql.connection.commit()

    return render_template('dodavanje_sale.html',msg=msg)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def file_size_allowed(file):
    return file.content_length <= app.config['MAX_CONTENT_LENGTH']

@app.route('/sale',methods=['GET','POST'])
def sale():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT balon_sale.*, MIN(slike_sala.putanja) AS putanja_slike FROM balon_sale LEFT JOIN slike_sala ON balon_sale.id_sale = slike_sala.id_sale GROUP BY balon_sale.id_sale')
    sve_sale = cursor.fetchall()
    return render_template('sale.html',sve_sale=sve_sale) 

@app.route('/sale/<int:sala_id>',methods=['GET','POST'])
def prikazivanje_sale(sala_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM balon_sale WHERE id_sale = %s', (sala_id,))
    sala = cursor.fetchone()
    if sala:
        cursor.execute('SELECT putanja FROM slike_sala WHERE id_sale = %s', (sala_id,))
        slike = cursor.fetchall()
        kod_mape = generate_embed_code_from_address(sala['adresa'] + ',' + sala['grad'])
        return render_template('detalji_sale.html', sala=sala, slike=slike,kod_mape=kod_mape)
    else:
        return 'Sala nije pronađena', 404  

@app.route('/zatrazi_termin/<int:sala_id>',methods=['GET', 'POST'])
def zatrazi_termin(sala_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM balon_sale WHERE id_sale = %s', (sala_id,))
    sala = cursor.fetchone()
    return render_template('termin.html',sala=sala)


if __name__ == '__main__':
    app.run(debug=True)