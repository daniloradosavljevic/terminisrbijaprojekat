from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from flask_mail import Mail, Message
import secrets
import uuid, os
from werkzeug.utils import secure_filename
from mapa import generate_embed_code_from_address
from datetime import datetime, timedelta

app = Flask(__name__)

app.secret_key = "super_tajni_kljuc"
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "e-poslovanje"

app.config["MAIL_SERVER"] = "smtp.yandex.com"
app.config["MAIL_PORT"] = 587  # Yandex obično koristi port 587 za TLS
#potrebno je dodati i svoj app.config["USERNAME"] i app.config["PASSWORD"]
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False

app.config["UPLOAD_FOLDER"] = "static/slike_sala"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}


mail = Mail(app)
mysql = MySQL(app)

bcrypt = Bcrypt(app)


@app.route("/")
def home():
    ulogovan = False
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        query="""
    SELECT bs.id_sale, bs.naziv_sale, bs.grad, MAX(ss.putanja) AS slika
    FROM (
        SELECT t.id_sale, COUNT(*) AS broj_termina
        FROM termini t
        GROUP BY t.id_sale
        ORDER BY broj_termina DESC
        LIMIT 3
    ) popularne_sale
    JOIN balon_sale bs ON popularne_sale.id_sale = bs.id_sale
    LEFT JOIN slike_sala ss ON bs.id_sale = ss.id_sale
    GROUP BY bs.id_sale, bs.naziv_sale, bs.grad
    ORDER BY popularne_sale.broj_termina DESC;
    """
    )
    popularne = cursor.fetchall()
    if "loggedin" in session and session["loggedin"]:
        ulogovan = True
        return render_template("index.html", ulogovan=ulogovan, popularne=popularne)
    else:
        return render_template("index.html", ulogovan=ulogovan, popularne=popularne)


bcrypt = Bcrypt(app)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "loggedin" in session and session["loggedin"]:
        return redirect(url_for("home"))

    msg = ""

    if (
        request.method == "POST"
        and "username" in request.form
        and "password" in request.form
    ):
        username = request.form["username"]
        password = request.form["password"]

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM accounts WHERE username = %s", (username,))

        account = cursor.fetchone()

        if account and bcrypt.check_password_hash(account["password"], password):
            session["loggedin"] = True
            session["id"] = account["id"]
            session["username"] = account["username"]
            session["tip"] = account["tip"]
            msg = "Logged in successfully!"
            return redirect(url_for("home"))
        else:
            msg = "Incorrect username/password"

    return render_template("login.html", msg=msg)


@app.route("/logout")
def logout():
    session.pop("loggedin", None)
    session.pop("id", None)
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "loggedin" in session and session["loggedin"]:
        return redirect(url_for("home"))
    reg = False
    msg = ""
    if (
        request.method == "POST"
        and "username" in request.form
        and "password" in request.form
        and "email" in request.form
        and "ime" in request.form
        and "prezime" in request.form
        and "telefon" in request.form
        and "tip" in request.form
    ):
        username = request.form["username"]
        password = request.form["password"]
        password_hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        email = request.form["email"]
        ime = request.form["ime"]
        prezime = request.form["prezime"]
        telefon = request.form["telefon"]
        tip = request.form["tip"]
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM accounts WHERE username = %s", (username,))
        account = cursor.fetchone()
        if account:
            msg = "Account already exists!"
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            msg = "Invalid email adress"
        elif not re.match(r"[A-Za-z0-9]+", username):
            msg = "Username must contain only characters and numbers!"
        elif (
            not username
            or not password
            or not email
            or not ime
            or not prezime
            or not telefon
            or not tip
        ):
            msg = "Please fill out the form! "
        else:
            cursor.execute(
                "INSERT INTO accounts VALUES (NULL, % s, % s, % s, % s, % s, % s , % s)",
                (
                    username,
                    password_hashed,
                    email,
                    ime,
                    prezime,
                    telefon,
                    tip,
                ),
            )
            mysql.connection.commit()
            msg = "You have successfully registered"
            verification_token = secrets.token_urlsafe(16)
            verification_link = url_for(
                "verify_email", token=verification_token, _external=True
            )
            mejlporuka = Message(
                "Dobrodošlica na TerminiSrbija!",
                sender="terminisrbija@yandex.com",
                recipients=[str(email)],
            )
            # mejlporuka.body = 'Zdravo ' + ime + ', ' +  f'Dobrodošao na TerminiSrbija! Verifikuj svoju email adresu: {verification_link}'
            mejlporuka.html = render_template(
                "email.html", ime=ime, verlink=verification_link
            )
            mail.send(mejlporuka)
            reg = True
    elif request.method == "POST":
        msg = "Please fill out the form!"
    return render_template("register.html", msg=msg, reg=reg)


@app.route("/verify_email/<token>")
def verify_email(token):
    return redirect(url_for("success_page"))


@app.route("/success_page")
def success_page():
    return render_template("success.html")


@app.route("/dodavanje_sale", methods=["GET", "POST"])
def dodavanjesale():
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))
    msg = ""
    if request.method == "POST":
        id_vlasnika = session["id"]
        naziv_sale = request.form.get("naziv_sale")
        cena_po_satu = request.form.get("cena_po_satu")
        opis = request.form.get("opis")
        grad = request.form.get("grad")
        adresa = request.form.get("adresa")

        # print(naziv_sale, cena_po_satu, opis, grad, adresa)

        if not all([naziv_sale, cena_po_satu, opis, grad, adresa]):
            msg = "Molimo vas da popunite sva polja!"
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(
                "INSERT INTO balon_sale VALUES (NULL, %s, %s, %s, %s, %s, %s)",
                (id_vlasnika, naziv_sale, cena_po_satu, opis, grad, adresa),
            )
            mysql.connection.commit()
            msg = "Uspešno ste dodali salu!"

            fajlovi = request.files.getlist("file")
            if fajlovi:
                for index, fajl in enumerate(fajlovi):
                    if fajl and allowed_file(fajl.filename) and file_size_allowed(fajl):
                        file_extension = fajl.filename.rsplit(".", 1)[1].lower()
                        unique_filename = str(uuid.uuid4()) + "." + file_extension
                        file_path = os.path.join(
                            app.config["UPLOAD_FOLDER"],
                            secure_filename(unique_filename),
                        )
                        cursor.execute("SELECT MAX(id_sale) FROM balon_sale")
                        id_ubacene_sale = cursor.fetchone()["MAX(id_sale)"] or 0
                        fajl.save(file_path)
                        cursor.execute(
                            "INSERT INTO slike_sala (id_sale, putanja) VALUES (%s, %s)",
                            (id_ubacene_sale, file_path),
                        )
                        mysql.connection.commit()

    return render_template("dodavanje_sale.html", msg=msg)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def file_size_allowed(file):
    return file.content_length <= app.config["MAX_CONTENT_LENGTH"]


@app.route("/sale", methods=["GET", "POST"])
def sale():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        pretraga = request.form.get("pretraga")
        query = """
            SELECT DISTINCT balon_sale.*, MIN(slike_sala.putanja) AS putanja_slike, ROUND(AVG(ocene_sale.ocena), 1) AS prosecna_ocena
            FROM balon_sale
            LEFT JOIN slike_sala ON balon_sale.id_sale = slike_sala.id_sale
            LEFT JOIN ocene_sale ON balon_sale.id_sale = ocene_sale.id_sale
            WHERE (slike_sala.id_slike_sale IS NOT NULL OR ocene_sale.id IS NOT NULL)
                  AND (balon_sale.grad LIKE %s OR balon_sale.naziv_sale LIKE %s)
            GROUP BY balon_sale.id_sale
            """
        cursor.execute(query, (f"%{pretraga}%", f"%{pretraga}%"))
    else:
        query = """
            SELECT DISTINCT balon_sale.*, MIN(slike_sala.putanja) AS putanja_slike, ROUND(AVG(ocene_sale.ocena), 1) AS prosecna_ocena
            FROM balon_sale
            LEFT JOIN slike_sala ON balon_sale.id_sale = slike_sala.id_sale
            LEFT JOIN ocene_sale ON balon_sale.id_sale = ocene_sale.id_sale
            WHERE slike_sala.id_slike_sale IS NOT NULL OR ocene_sale.id IS NOT NULL
            GROUP BY balon_sale.id_sale ORDER BY RAND()
            """
        cursor.execute(query)

    sve_sale = cursor.fetchall()
    return render_template("sale.html", sve_sale=sve_sale)


@app.route("/sala:<int:sala_id>", methods=["GET", "POST"])
def prikazivanje_sale(sala_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM balon_sale WHERE id_sale = %s", (sala_id,))
    sala = cursor.fetchone()
    if sala:
        cursor.execute("SELECT putanja FROM slike_sala WHERE id_sale = %s", (sala_id,))
        slike = cursor.fetchall()
        kod_mape = generate_embed_code_from_address(sala["adresa"] + "," + sala["grad"])
        return render_template(
            "detalji_sale.html", sala=sala, slike=slike, kod_mape=kod_mape
        )
    else:
        return "Sala nije pronađena", 404


@app.route("/zatrazi_termin/<int:sala_id>", methods=["GET", "POST"])
def zatrazi_termin(sala_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 1:
        return redirect(url_for("home"))
    cursor = mysql.connection.cursor(
        MySQLdb.cursors.DictCursor
    )  # Definisanje cursora i ovde
    cursor.execute("SELECT * FROM balon_sale WHERE id_sale = %s", (sala_id,))
    sala = cursor.fetchone()
    if request.method == "POST":
        vreme = request.form["vreme"]
        cursor.execute(
            "SELECT * FROM termini WHERE id_sale = %s AND vreme = %s AND status_termina = %s",
            (sala_id, vreme, "odobren"),
        )
        existing_termin = cursor.fetchone()
        if existing_termin:
            msg = "Već postoji potvrđen termin za to vreme!"
            return render_template("termin.html", sala=sala, msg=msg)
        cursor = mysql.connection.cursor(
            MySQLdb.cursors.DictCursor
        )  # Definisanje cursora ovde
        cursor.execute(
            "INSERT INTO termini (id_sale, id_igraca, status_termina, vreme) VALUES (%s, %s, %s, %s)",
            (sala_id, session["id"], "zatrazen", vreme),
        )
        mysql.connection.commit()
        msg = "Uspešno ste zatražili termin u ovoj sali!"
        return render_template("termin.html", sala=sala, msg=msg)
    return render_template("termin.html", sala=sala)


@app.route("/moji_termini")
def moji_termini():
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 1:
        return redirect(url_for("home"))

    id_igraca = session["id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT * FROM termini INNER JOIN balon_sale ON termini.id_sale = balon_sale.id_sale WHERE termini.id_igraca = %s",
        (id_igraca,),
    )
    termini = cursor.fetchall()
    return render_template("moji_termini.html", termini=termini)


@app.route("/otkazi_termin/<int:termin_id>", methods=["POST"])
def otkazi_termin(termin_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 1:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT termini.*, balon_sale.naziv_sale FROM termini LEFT JOIN balon_sale ON termini.id_sale = balon_sale.id_sale WHERE termini.id = %s",
        (termin_id,),
    )
    termin = cursor.fetchone()

    if not termin:
        return redirect(
            url_for("moji_termini", msg="Nemate dozvolu za brisanje tog termina")
        )

    if termin["status_termina"] == "zatrazen" and termin["id_igraca"] == session["id"]:
        cursor.execute("DELETE FROM termini WHERE id = %s", (termin_id,))
        mysql.connection.commit()
        return redirect(
            url_for("moji_termini", msg="Uspešno ste otkazali zahtev za termin")
        )

    return redirect(
        url_for("moji_termini", msg="Nemate dozvolu za brisanje tog termina")
    )


@app.route("/moji_zahtevi", methods=["GET"])
def moji_zahtevi():
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        """
        SELECT termini.*, balon_sale.naziv_sale, accounts.username 
        FROM termini 
        LEFT JOIN balon_sale ON termini.id_sale = balon_sale.id_sale 
        LEFT JOIN accounts ON termini.id_igraca = accounts.id 
        WHERE balon_sale.id_vlasnika = %s
    """,
        (session["id"],),
    )
    zahtevi_termina = cursor.fetchall()
    now_time = datetime.now()

    # Prolazi kroz svaki zahtev i postavi ts
    for zahtev in zahtevi_termina:
        vreme_zahteva = zahtev["vreme"]
        # Ako je trenutno vreme bar 1 dan ispred vremena iz zahteva, postavi ts na True, inače False
        zahtev["ts"] = now_time - vreme_zahteva >= timedelta(days=1)

    return render_template("moji_zahtevi.html", zahtevi=zahtevi_termina)


@app.route("/odobri_zahtev/<int:termin_id>", methods=["GET"])
def odobri_zahtev(termin_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT t.id_sale FROM termini t JOIN balon_sale s ON t.id_sale = s.id_sale WHERE t.id = %s AND s.id_vlasnika = %s",
        (termin_id, session["id"]),
    )
    sala = cursor.fetchone()

    if sala:
        cursor.execute(
            'UPDATE termini SET status_termina = "odobren" WHERE id = %s', (termin_id,)
        )
        mysql.connection.commit()

    return redirect(url_for("moji_zahtevi", sala_id=session["id"]))


@app.route("/odbij_zahtev/<int:termin_id>", methods=["GET"])
def odbij_zahtev(termin_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT t.id_sale FROM termini t JOIN balon_sale s ON t.id_sale = s.id_sale WHERE t.id = %s AND s.id_vlasnika = %s",
        (termin_id, session["id"]),
    )
    sala = cursor.fetchone()

    if sala:
        cursor.execute(
            'UPDATE termini SET status_termina = "odbijen" WHERE id = %s', (termin_id,)
        )
        mysql.connection.commit()

    return redirect(url_for("moji_zahtevi", sala_id=session["id"]))


@app.route("/profil", methods=["GET"])
def profil():
    if "loggedin" not in session or not session["loggedin"]:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM accounts WHERE id = %s", (session["id"],))
    korisnik = cursor.fetchone()

    uloga = "Vlasnik sale" if korisnik["tip"] == 1 else "Igrač"

    return render_template("moj_profil.html", korisnik=korisnik, uloga=uloga)


@app.route("/izmeni_profil", methods=["GET", "POST"])
def izmeni_profil():
    if "loggedin" not in session or not session["loggedin"]:
        return redirect(url_for("home"))

    msg = ""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        ime = request.form["ime"]
        prezime = request.form["prezime"]
        telefon = request.form["telefon"]
        email = request.form["email"]
        nova_sifra = request.form["nova_sifra"]
        potvrda_sifre = request.form["potvrda_sifre"]

        cursor.execute("SELECT * FROM accounts WHERE id = %s", (session["id"],))
        korisnik = cursor.fetchone()

        if korisnik:
            cursor.execute(
                "SELECT * FROM accounts WHERE email = %s AND id != %s",
                (email, session["id"]),
            )
            existing_email = cursor.fetchone()

            if existing_email:
                msg = "Email adresa je zauzeta!"
            else:
                if nova_sifra != potvrda_sifre:
                    msg = "Nova šifra i potvrda šifre se ne podudaraju!"
                else:
                    if nova_sifra:
                        hashed_password = bcrypt.generate_password_hash(
                            nova_sifra
                        ).decode("utf-8")
                        cursor.execute(
                            "UPDATE accounts SET ime = %s, prezime = %s, telefon = %s, email = %s, password = %s WHERE id = %s",
                            (
                                ime,
                                prezime,
                                telefon,
                                email,
                                hashed_password,
                                session["id"],
                            ),
                        )
                    else:
                        cursor.execute(
                            "UPDATE accounts SET ime = %s, prezime = %s, telefon = %s, email = %s WHERE id = %s",
                            (ime, prezime, telefon, email, session["id"]),
                        )
                    mysql.connection.commit()
                    msg = "Uspešno ste izmenili profil!"
                    return render_template(
                        "izmeni_profil.html", korisnik=korisnik, msg=msg
                    )

    cursor.execute("SELECT * FROM accounts WHERE id = %s", (session["id"],))
    korisnik = cursor.fetchone()
    return render_template("izmeni_profil.html", korisnik=korisnik, msg=msg)


@app.route("/deaktiviraj_profil", methods=["GET"])
def deaktiviraj_profil():
    if "loggedin" not in session or not session["loggedin"]:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor()
    user_id = session["id"]

    cursor.execute("SELECT id_sale FROM balon_sale WHERE id_vlasnika = %s", (user_id,))
    balon_sale_ids = [result[0] for result in cursor.fetchall()]

    cursor.execute("SELECT id FROM termini WHERE id_igraca = %s", (user_id,))
    termini_ids = [result[0] for result in cursor.fetchall()]

    for balon_sale_id in balon_sale_ids:
        cursor.execute("DELETE FROM ocene_sale WHERE id_sale = %s", (balon_sale_id,))
        cursor.execute("DELETE FROM balon_sale WHERE id_sale = %s", (balon_sale_id,))
        cursor.execute("DELETE FROM termini WHERE id_sale = %s", (balon_sale_id,))
        mysql.connection.commit()

    for termin_id in termini_ids:
        cursor.execute("DELETE FROM termini WHERE id = %s", (termin_id,))
        mysql.connection.commit()

    cursor.execute("DELETE FROM accounts WHERE id = %s", (user_id,))
    mysql.connection.commit()

    session.pop("loggedin", None)
    session.pop("id", None)

    return render_template("stranica_oprostaja.html")


@app.route("/izmeni_salu/<int:sala_id>", methods=["GET", "POST"])
def izmeni_salu(sala_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))

    msg = ""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM balon_sale WHERE id_sale = %s", (sala_id,))
    sala = cursor.fetchone()

    if request.method == "POST":
        novi_naziv = request.form["novi_naziv"]
        nova_cena = request.form["nova_cena"]
        novi_opis = request.form["novi_opis"]

        if sala and sala["id_vlasnika"] == session["id"]:
            cursor.execute(
                "UPDATE balon_sale SET naziv_sale = %s, cena_po_satu = %s, opis = %s WHERE id_sale = %s",
                (novi_naziv, nova_cena, novi_opis, sala_id),
            )
            mysql.connection.commit()
            return redirect(url_for("sale"))
        else:
            return redirect(url_for("home"))

    if sala:
        return render_template("izmeni_salu.html", sala=sala)
    else:
        return redirect(url_for("home"))


@app.route("/obrisi_salu/<int:sala_id>", methods=["GET"])
def obrisi_salu(sala_id):
    if "loggedin" not in session or not session["loggedin"]:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id_vlasnika FROM balon_sale WHERE id_sale = %s", (sala_id,))
    result = cursor.fetchone()

    if result and result[0] == session["id"]:
        cursor.execute("DELETE FROM ocene_sale WHERE id_sale = %s", (sala_id,))
        mysql.connection.commit()

        cursor.execute("DELETE FROM termini WHERE id_sale = %s", (sala_id,))
        mysql.connection.commit()

        cursor.execute("DELETE FROM balon_sale WHERE id_sale = %s", (sala_id,))
        mysql.connection.commit()

    return redirect(url_for("sale"))


@app.route("/oceni/<int:entity_id>", methods=["GET", "POST"])
def oceni(entity_id):
    if "loggedin" not in session or not session["loggedin"]:
        return redirect(url_for("home"))

    cursor = mysql.connection.cursor()

    if request.method == "POST":
        ocena = request.form["ocena"]
        komentar = request.form["komentar"]

        if session["tip"] != 1:  # Igrač ocenjuje salu
            cursor.execute(
                'SELECT * FROM termini t INNER JOIN balon_sale bs ON t.id_sale = bs.id_sale WHERE t.id_igraca = %s AND t.status_termina = "odobren" AND bs.id_sale = %s',
                (session["id"], entity_id),
            )
            termini = cursor.fetchall()
            if not termini:
                return redirect(url_for("home"))

            cursor.execute(
                "INSERT INTO ocene_sale (id_sale, id_igraca, ocena, komentar) VALUES (%s, %s, %s, %s)",
                (entity_id, session["id"], ocena, komentar),
            )
            mysql.connection.commit()

        elif session["tip"] != 2:  # Vlasnik sale ocenjuje igrača
            cursor.execute(
                'SELECT * FROM termini t INNER JOIN balon_sale bs ON t.id_sale = bs.id_sale WHERE bs.id_vlasnika = %s AND t.id_igraca = %s AND t.status_termina = "odobren"',
                (session["id"], entity_id),
            )
            termini = cursor.fetchall()
            if not termini:
                return redirect(url_for("home"))

            cursor.execute(
                "INSERT INTO ocene_igraca (id_igraca, id_vlasnika, ocena, komentar) VALUES (%s, %s, %s, %s)",
                (entity_id, session["id"], ocena, komentar),
            )
            mysql.connection.commit()

        return redirect(url_for("home"))

    # Renderovanje forme za ocenjivanje
    if session["tip"] != 1:  # Igrač ocenjuje salu
        cursor.execute("SELECT * FROM balon_sale WHERE id_sale = %s", (entity_id,))
        sala = cursor.fetchone()
        if not sala:
            return redirect(url_for("home"))
        idsal = sala[0]
        return render_template("oceni.html", entity=sala, entid=idsal)

    elif session["tip"] != 2:  # Vlasnik sale ocenjuje igrača
        cursor.execute("SELECT * FROM accounts WHERE id = %s", (entity_id,))
        igrac = cursor.fetchone()
        if not igrac:
            return redirect(url_for("home"))
        ident = igrac[0]
        return render_template("oceni.html", entity=igrac, entid=ident)


@app.route("/ocene_sala/<int:sala_id>")
def ocene_sala(sala_id):
    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT os.ocena, os.komentar, IFNULL(a.ime, 'Nedostupno') as ime, IFNULL(a.prezime, '') as prezime FROM ocene_sale os LEFT JOIN accounts a ON os.id_igraca = a.id WHERE os.id_sale = %s",
        (sala_id,),
    )
    ocene_sala = cursor.fetchall()
    return render_template("ocene_sala.html", ocene=ocene_sala)


@app.route("/ocene_igraca/<int:igrac_id>")
def ocene_igraca(igrac_id):
    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT oi.ocena, oi.komentar, IFNULL(a.ime, 'Nedostupno') as ime, IFNULL(a.prezime, '') as prezime FROM ocene_igraca oi LEFT JOIN accounts a ON oi.id_igraca = a.id WHERE oi.id_igraca = %s",
        (igrac_id,),
    )
    ocene_igraca = cursor.fetchall()

    return render_template("ocene_igraca.html", ocene=ocene_igraca)


@app.route("/moje_sale")
def moje_sale():
    if "loggedin" not in session or not session["loggedin"] or session["tip"] == 2:
        return redirect(url_for("home"))

    id_vlasnika = session["id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT * FROM balon_sale WHERE id_vlasnika = %s",
        (id_vlasnika,),
    )
    sale = cursor.fetchall()
    return render_template("moje_sale.html", sale=sale)


@app.route("/admin/dashboard")
def admin_dashboard():
    if "loggedin" not in session or not session["loggedin"] or session["tip"] != 0:
        return redirect(url_for("home"))

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM accounts")
    users = cur.fetchall()

    cur.execute("SELECT * FROM balon_sale")
    izlozene_sale = cur.fetchall()

    cur.execute("SELECT * FROM ocene_sale")
    comments = cur.fetchall()

    cur.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        izlozene_sale=izlozene_sale,
        comments=comments,
    )


@app.route("/admin/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] != 0:
        return redirect(url_for("home"))

    cur = mysql.connection.cursor()

    if request.method == "POST":
        if "delete" in request.form:
            cur.execute(
                "SELECT id_sale FROM balon_sale WHERE id_vlasnika = %s", (user_id,)
            )
            balon_sale_ids = [result[0] for result in cur.fetchall()]

            for balon_sale_id in balon_sale_ids:
                cur.execute(
                    "DELETE FROM ocene_sale WHERE id_sale = %s", (balon_sale_id,)
                )
                mysql.connection.commit()

            for balon_sale_id in balon_sale_ids:
                cur.execute("DELETE FROM termini WHERE id_sale = %s", (balon_sale_id,))
                mysql.connection.commit()

            cur.execute(
                "DELETE FROM termini WHERE id_igraca = %s",
                (user_id,),
            )

            cur.execute("DELETE FROM accounts WHERE id = %s", (user_id,))
            mysql.connection.commit()
            cur.close()

            return redirect(url_for("admin_dashboard"))

        username = request.form.get("username")
        email = request.form.get("email")
        ime = request.form.get("ime")
        prezime = request.form.get("prezime")
        telefon = request.form.get("telefon")
        account_type = request.form.get("account_type")

        cur.execute(
            "UPDATE accounts SET username=%s, email=%s, ime=%s, prezime=%s, telefon=%s, tip=%s WHERE id=%s",
            (username, email, ime, prezime, telefon, account_type, user_id),
        )
        mysql.connection.commit()
        cur.close()

        return redirect(url_for("admin_dashboard"))

    cur.execute("SELECT * FROM accounts WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()

    return render_template("admin_edit_user.html", user=user)


@app.route("/admin/edit_sale/<int:sale_id>", methods=["GET", "POST"])
def edit_sale(sale_id):
    if "loggedin" not in session or not session["loggedin"] or session["tip"] != 0:
        return redirect(url_for("home"))

    cur = mysql.connection.cursor()

    if request.method == "POST":
        if "delete" in request.form:
            cur.execute("DELETE FROM ocene_sale WHERE id_sale = %s", (sale_id,))
            mysql.connection.commit()

            cur.execute("DELETE FROM termini WHERE id_sale = %s", (sale_id,))
            mysql.connection.commit()

            cur.execute("DELETE FROM balon_sale WHERE id_sale = %s", (sale_id,))
            mysql.connection.commit()
            cur.close()

            return redirect(url_for("admin_dashboard"))

        naziv_sale = request.form.get("naziv_sale")
        cena_po_satu = request.form.get("cena_po_satu")
        opis = request.form.get("opis")
        grad = request.form.get("grad")
        adresa = request.form.get("adresa")

        cur.execute(
            "UPDATE balon_sale SET naziv_sale=%s, cena_po_satu=%s, opis=%s, grad=%s, adresa=%s WHERE id_sale=%s",
            (naziv_sale, cena_po_satu, opis, grad, adresa, sale_id),
        )
        mysql.connection.commit()
        cur.close()

        return redirect(url_for("admin_dashboard"))

    cur.execute("SELECT * FROM balon_sale WHERE id_sale = %s", (sale_id,))
    sale = cur.fetchone()
    cur.close()

    return render_template("admin_edit_sale.html", sale=sale)


@app.route("/delete_comment/<int:comment_id>", methods=["GET", "POST"])
def delete_comment(comment_id):
    if request.method == "POST" or request.form.get("_method") == "DELETE":
        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT id_sale, id_igraca FROM ocene_sale WHERE id = %s", (comment_id,)
        )
        comment_info = cursor.fetchone()

        if comment_info:
            id_sale, id_igraca = comment_info

            cursor.execute("DELETE FROM ocene_sale WHERE id = %s", (comment_id,))
            mysql.connection.commit()

            cursor.execute(
                "DELETE FROM ocene_igraca WHERE id_igraca = %s",
                (id_igraca,),
            )
            mysql.connection.commit()

            return redirect(url_for("admin_dashboard"))

    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
