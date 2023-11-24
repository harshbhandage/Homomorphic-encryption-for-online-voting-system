from flask import Flask, render_template, request, redirect, session,jsonify
from flask_sqlalchemy import SQLAlchemy
from Cryptodome.Util.number import getPrime
from random import randint


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///voting.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "your_secret_key"
app.static_folder = "static"

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(10))
    voted=db.Column(db.Integer)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    sex = db.Column(db.String(10))
    area = db.Column(db.String(100))
    party = db.Column(db.String(50))
    votes=db.Column(db.Integer)
    


count=0


class Paillier:
    def __init__(self, bit_length=10):
        p = getPrime(bit_length)
        q = getPrime(bit_length)

        self.n = p * q
        self.n_square = self.n * self.n
        self.g = self.n + 1

        self.lmbda = (p - 1) * (q - 1)
        self.mu = self.mod_inverse(self.lmbda, self.n)

    def mod_inverse(self, a, m):
        def egcd(a, b):
            if a == 0:
                return b, 0, 1
            else:
                g, x, y = egcd(b % a, a)
                return g, y - (b // a) * x, x

        g, x, _ = egcd(a, m)
        if g != 1:
            raise Exception("Modular inverse does not exist.")
        else:
            return x % m

    def encrypt(self, plaintext):
        r = randint(1, self.n - 1)

        c = (
            pow(self.g, plaintext, self.n_square) * pow(r, self.n, self.n_square)
        ) % self.n_square

        return c

    def decrypt(self, ciphertext):
        numerator = pow(ciphertext, self.lmbda, self.n_square) - 1
        plaintext = (numerator // self.n * self.mu) % self.n

        return plaintext


paillier = Paillier()




@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user_id"] = user.id
            if user.role == "Admin":
                return redirect("/admin_panel")
            else:
                return redirect("/user_panel")
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        new_user = User(username=username, password=password, role=role,voted=0)
        db.session.add(new_user)
        db.session.commit()
        return redirect("/login")
    return render_template("signup.html")

@app.route("/admin_panel", methods=["GET", "POST"])
def admin_dashboard():
    if "user_id" in session:
        user_id = session["user_id"]
        user = User.query.get(user_id)
        if user.role == "Admin":
            return render_template("admin_panel.html")
    return redirect("/login")


@app.route("/add_candidate", methods=["GET","POST"])
def add_candidate():
        name=request.form["candidate_name"]
        age=request.form["age"]
        sex=request.form["sex"]
        area=request.form["area"]
        party=request.form["party"]
        new_candidate = Candidate(name=name,age=age,sex=sex,area=area,party=party,votes=paillier.encrypt(0))
        db.session.add(new_candidate)
        db.session.commit()

        return redirect("/admin_panel")


@app.route("/result")
def result():
    candidates = Candidate.query.all()
    candidate_list = []
    total=User.query.filter_by(role="Voter").count()
    for candidate in candidates:
        setv=paillier.decrypt(candidate.votes)
        setv=(setv*100)/total
        candidate_data = {
            'id': candidate.id,
            'name': candidate.name,
            'age': candidate.age,
            'sex': candidate.sex,
            'area': candidate.area,
            'party': candidate.party,
            'votes': setv
        }
        candidate_list.append(candidate_data)
    return jsonify(candidate_list)



@app.route("/display_list")
def display():
    candidates = Candidate.query.all()
    candidate_list = []
    for candidate in candidates:
        candidate_data = {
            'id': candidate.id,
            'name': candidate.name,
            'age': candidate.age,
            'sex': candidate.sex,
            'area': candidate.area,
            'party': candidate.party,
            'votes': candidate.votes
        }
        candidate_list.append(candidate_data)
    return jsonify(candidate_list)





@app.route("/user_panel")
def user_dashboard():
    if "user_id" in session:
        user_id = session["user_id"]
        user = User.query.get(user_id)
        if user.role == "Voter":
            return render_template("user_panel.html")
    return redirect("/login")


@app.route('/handle_click', methods=['POST'])
def handle_click():
      global count
      button_data = request.get_json()
      button_id = int(button_data.get('buttonId'))
      vote = Candidate.query.filter_by(id=button_id).with_entities(Candidate.votes).first()
      vote_to_update = db.session.get(Candidate, button_id)
      pvote=paillier.decrypt(vote[0])
      final=pvote+1
      vote_to_update.votes=paillier.encrypt(final)
      db.session.commit()
      print(button_id)
      if "user_id" in session:
          user_id = session["user_id"]
          user = User.query.get(user_id)
          user_to_update = db.session.get(User,user.id)
          user_to_update.voted = 1
          db.session.commit()
      return("user_panel.html")


@app.route('/handle_delete',methods=['POST'])
def handle_delete():
      button_data = request.get_json()
      button_id = button_data.get('buttonId')
      item = Candidate.query.get_or_404(button_id) 
      db.session.delete(item)  
      db.session.commit()
      return("admin_panel.html")


@app.route("/send_data",methods=['POST'])
def send_data():
    if "user_id" in session:
        user_id = session["user_id"]
        user = User.query.get(user_id)
        print("10")
        if user.voted == 1:
            data=1
        else:
            data=0
    response_data = {'vote1': data}
    return jsonify(response_data)

@app.route('/total_voters')
def total_voters():
    total_voters = User.query.filter_by(role='Voter').count()
    return jsonify({'total_voters': total_voters})

@app.route('/total_candidates')
def total_candidates():
    total_candidates = Candidate.query.count()
    return jsonify({'total_candidates': total_candidates})
    
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)