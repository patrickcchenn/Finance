import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows=db.execute("SELECT symbol, SUM(transactions) as amount FROM record WHERE userID=? GROUP BY symbol HAVING transactions",session["user_id"])
    cash=db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
    cash_=cash[0]["cash"]

    #store all the data into a dict so its easier to pass in to html
    display=[]
    total_share=0
    for row in rows:
        symbol=str(row["symbol"])
        print(symbol)
        name=lookup(symbol)["name"]
        shares=int(row["amount"])
        price=float(lookup(symbol)["price"])
        total=float(shares) *price
        total_share+=total
        display.append({'symbol':symbol, 'name':name, 'shares':shares, 'price':price, 'total':total})

    total_money=total_share+cash[0]["cash"]
    return render_template("index.html",display=display,total_money=total_money,cash=cash_)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)

        if not request.form.get("shares").isdigit():
            return apology("must be integer",400)

        elif int(request.form.get("shares"))<1   :
            return apology("must be positive integer", 400)

        elif lookup(request.form.get("symbol"))==None:
            return apology("Must be a valid symbol",400)

        #ensure money>price
        quote=lookup(request.form.get("symbol"))
        shares=request.form.get("shares")
        cash=db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
        if cash[0]["cash"]<int(quote["price"])*int(shares):
            return apology("You can't affort this/these",400)

        #BUY, STORE DATA IN REPOSITORY AND RECORD

        #record this transaction
        db.execute("INSERT INTO record(userID,transactions,symbol,price,t1) VALUES(?,?,?,?,strftime('%Y-%m-%d %H:%M:%S','now'))",session["user_id"],int(shares),quote["symbol"],float(quote["price"]))

        #deduct the cash
        total=int(quote["price"])*int(shares)
        db.execute("UPDATE users SET cash=cash- (?) WHERE id=?",total,session["user_id"])

        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows=db.execute("SELECT * FROM record ORDER BY t1")
    return render_template("history.html",rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="POST":
        quote=lookup(request.form.get("symbol"))
        if quote==None:
            return apology("Invalid symbol",400)
        price=usd(quote["price"])
        return render_template("quoted.html",quote=quote,price=price)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure comfirm password was submitted
        elif not request.form.get("confirmation"):
            return apology("must comfirm password", 400)

        # Ensure  password matches
        elif  request.form.get("confirmation") != request.form.get("password"):
            return apology("Password not matches",400)

        # Ensure username is new(unique)
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("username used", 400)

        db.execute("INSERT INTO users (username,hash) VALUES (?,?)",request.form.get("username"),generate_password_hash(request.form.get("password")))


        # Redirect user to home page
        return redirect("/")


    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method=='POST':
        #parameter is not filled
        if not request.form.get("shares"):
            return apology("Please enter how much u want to sell",400)
        #check if shares(amount) that are going to be sell less than owner's share.
        sell=request.form.get("sell")
        shares=request.form.get("shares")
        amount=db.execute("SELECT SUM(transactions) as amount FROM record WHERE userID=? AND symbol=? GROUP BY symbol HAVING transactions",session["user_id"],sell)
        if amount[0]["amount"]<int(shares):
            return apology("You dont own that much shares",400)

        #record sell and add cash amount
        quote=lookup(sell)
        price=quote["price"]
        total=int(price)*int(shares)

        db.execute("INSERT INTO record(userID,transactions,symbol,price,t1) VALUES(?,?,?,?,strftime('%s','now'))",session["user_id"],(int(shares)*-1),quote["symbol"],price)
        db.execute("UPDATE users SET cash=cash- (?) WHERE id=?",total,session["user_id"])

        return redirect("/")

    else:
        rows=db.execute("SELECT symbol, SUM(transactions) as amount FROM record WHERE userID=? GROUP BY symbol HAVING transactions",session["user_id"])

        return render_template("sell.html",rows=rows)



@app.route("/HAX", methods=["GET", "POST"])
@login_required
def HAX():
    #add free monei boiiii
    if request.method=="POST":
        total=request.form.get("HAX")
        db.execute("UPDATE users SET cash=cash+ (?) WHERE id=?",total,session["user_id"])
        flash(u'HAX SUCCESSFULLY ACTIVATED!!!')

        return redirect("/")

    else:
        return render_template("HAX.html")





def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
