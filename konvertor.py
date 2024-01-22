from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

# Zamijenite ovo sa stvarnim šiframa iz vaše baze podataka
plain_text_passwords = ["danilo","korisnik123","korisnik2","veljko123","aki123"]

hashed_passwords = []

for password in plain_text_passwords:
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    hashed_passwords.append(hashed_password)

print(hashed_passwords)

