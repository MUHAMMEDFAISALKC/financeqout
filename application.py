import os
from datetime import datetime
import pytz
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, dusd

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
dbs = SQL("sqlite:///purchases.db")

def DATE():
    timeZ_K1 = pytz.timezone('Asia/Kolkata')
    x = datetime.now(timeZ_K1)
    return x.strftime("%d-%m-%Y %H:%M:%S")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session["user_id"]
    nam = db.execute("SELECT * FROM users WHERE id = ?", id)
    name = nam[0]["username"]
    cash = round((nam[0]["cash"]),2)
    rows = db.execute("SELECT * FROM mystock WHERE user_id =? AND shares >0", id)
    stot = db.execute("SELECT SUM(total) FROM mystock WHERE user_id=?",id)
    if stot[0]["SUM(total)"] == None:
        return render_template("indexfirst.html", name=name, cash= cash, bcash=cash)
    stotal = round((stot[0]["SUM(total)"]),2)
    bcash = round((cash + stotal),2)
    return render_template("index.html", rows=rows, name=name, stotal= stotal, cash=cash, bcash=bcash )
    return apology("something wrong happened", 403)

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]
    nam = db.execute("SELECT username FROM users WHERE id=?", id)
    name = nam[0]["username"]
    rows = db.execute("SELECT timestamp, symbol,company, shares, price, total, 'purchase' AS type FROM purchases UNION ALL SELECT timestamp, symbol, company, shares, price, total, 'sale' FROM sales WHERE user_id = ? ORDER BY timestamp", id)

    return render_template("history.html", rows=rows, name=name )
    return apology("something wrong happen")


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
    if request.form.get("symbol"):
        symbo = db.execute("SELECT symbol FROM symbols WHERE name = ?",request.form.get("symbol"))
        symbol = symbo[0]["symbol"]
        rows = lookup(symbol)
        if  rows == None:
            return apology("No Detail available for this company", 403)
        return render_template("quoted.html", rows=rows, usd=usd)

    rows = db.execute("SELECT * FROM symbols")
    return render_template("quote.html", rows=rows)
    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        row = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))
        if not request.form.get("username"):
            return apology("Must provide username", 403)
        elif len(row) == 1:
            return apology("Username already exists", 403)
        elif not request.form.get("password"):
            return apology("Must provide password", 403)
        elif not request.form.get("confirmation"):
            return apology("Must confirm password", 403)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords are not matching", 403)
        else:
            psw = generate_password_hash(request.form.get("password"))
            name = request.form.get("username")

            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", name, psw)
            rows = db.execute("SELECT * FROM users WHERE username = ?", name)
            session["user_id"] = rows[0]["id"]
            return redirect("/")


    else:
        return render_template("register.html")
        return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if int(request.form.get("fid")) == 1:
            if not request.form.get("symbol"):
                return apology("Must provide company name", 403)
            elif not request.form.get("shares"):
                return apology("Must provide shares", 403)
            elif not int(request.form.get("shares")) >0:
                return apology("Must provide positive numbers")
            elif request.form.get("symbol"):

                userid = request.form.get("user")
                time = DATE()
                sell = db.execute("SELECT * FROM users WHERE id =?", userid)
                seller = sell[0]["username"]
                cashi = float(sell[0]["cash"])
                company = request.form.get("symbol")
                symbo = db.execute("SELECT symbol FROM symbols WHERE name =?", company)
                symbol = symbo[0]["symbol"]
                dtshares = db.execute("SELECT shares FROM mystock WHERE user_id = ? AND symbol = ?", userid,symbol)
                tshares = dtshares[0]["shares"]
                shares = int(request.form.get("shares"))
                bshares = tshares - shares

                if bshares <0:
                    return apology("You don't have sufficient shares")

                pri = lookup(symbol)
                if pri == None:
                    return apology("No Detail available for this company", 403)
                pric = float(pri["price"])
                price = usd(pri["price"])
                tota = round((shares * pric),2)
                total = usd(shares * pric)
                bcashi = round((cashi + (shares * pric)),2)
                bcash = usd(bcashi)
                cash = usd(cashi)

                return f"{tota}& {bcashi}"

                db.execute("INSERT INTO sale (user_id, timestamp, seller, company, symbol, shares, price, total) VALUES (?,?,?,?,?,?,?,?)", userid, time, seller, company,symbol, shares, pric, tota)
                return render_template("tosell.html", company=company, symbol=symbol, shares=shares, price=price, total=total, cash=cash, bcash=bcash)
                return apology("Something wrong heappened")

        elif int(request.form.get("fid")) == 2:
            id = session["user_id"]
            tcash = dusd(request.form.get("tcash"))
            rcash = db.execute("SELECT cash FROM users WHERE id = ?", id)
            cash =  float(rcash[0]["cash"])
            bacash = cash+tcash
            time = DATE()
            db.execute("UPDATE sale SET timestamp = ? WHERE user_id = ?", time, id)
            db.execute("INSERT INTO sales (user_id, timestamp, seller, company, symbol, shares, price, total) SELECT user_id, timestamp, seller, company, symbol, shares, price, total FROM sale WHERE user_id = ?",id)

            symb = db.execute("SELECT symbol FROM sale WHERE user_id =?", id)
            symbol = symb[0]["symbol"]
            ava = db.execute("SELECT symbol, CASE WHEN symbol = ? THEN 'YES' ELSE 'NO' END AS result FROM mystock WHERE user_id = ? AND symbol = ?", symbol, id, symbol)
            if not ava == []:
                ashare = db.execute("SELECT shares FROM mystock WHERE user_id = ? AND symbol= ?", id , symbol)
                nshare = db.execute("SELECT * FROM sale WHERE user_id = ? AND symbol= ?", id , symbol)
                avashare = ashare[0]["shares"]
                avaprice = nshare[0]["price"]
                nowshare = nshare[0]["shares"]
                tshare = avashare - nowshare
                tota = tshare * avaprice
                db.execute("UPDATE mystock SET shares = ?, price = ?, total =?  WHERE user_id= ? AND symbol = ?", tshare, avaprice, tota, id, symbol)
            else:
                db.execute("INSERT INTO mystock (user_id,company,symbol,shares,pprice, price, total) SELECT user_id,company,symbol,shares,total,price,total FROM purchase WHERE user_id = ?", id)
            db.execute("DELETE FROM sale WHERE user_id = ?", id)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", bacash,id)
            return redirect("/")
            return apology("Something wrong heappened")

        elif int(request.form.get("fid")) == 3:
            id = session["user_id"]
            db.execute("DELETE FROM sale WHERE user_id = ?", id)
            return redirect("/")

        else:
            return apology("Something wrong heappened")



    rows = db.execute("SELECT *FROM symbols")
    return render_template("sell.html", rows=rows)
    return apology("Something wrong heappened")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":
        if int(request.form.get("fid")) == 1:
            if not request.form.get("symbol"):
                return apology("Must provide company name", 403)
            elif not request.form.get("shares"):
                return apology("Must provide shares", 403)
            elif not int(request.form.get("shares")) >0:
                return apology("Must provide positive numbers")
            elif request.form.get("symbol"):
                userid = request.form.get("user")
                time = DATE()
                buy = db.execute("SELECT * FROM users WHERE id =?", userid)
                buyer = buy[0]["username"]
                cashi = float(buy[0]["cash"])
                company = request.form.get("symbol")
                symbo = db.execute("SELECT symbol FROM symbols WHERE name =?", company)
                symbol = symbo[0]["symbol"]
                shares = int(request.form.get("shares"))
                pri = lookup(symbol)
                if pri == None:
                    return apology("No Detail available for this company", 403)
                pric = float(pri["price"])
                price = usd(pri["price"])
                tota = round((shares * pric),2)
                total = usd(shares * pric)
                bcashi = cashi - (shares * pric)
                bcash = usd(bcashi)
                cash = usd(cashi)

                db.execute("INSERT INTO purchase (user_id, timestamp, buyer, company, symbol, shares, price, total) VALUES (?,?,?,?,?,?,?,?)", userid, time, buyer, company,symbol, shares, pric, tota)
                return render_template("buy.html", company=company, symbol=symbol, shares=shares, price=price, total=total, cash=cash, bcash=bcash)
                return apology("Something wrong heappened")

        elif int(request.form.get("fid")) == 2:
            id = session["user_id"]
            tcash = dusd(request.form.get("tcash"))
            rcash = db.execute("SELECT cash FROM users WHERE id = ?", id)
            cash =  float(rcash[0]["cash"])
            bacash = cash-tcash
            time = DATE()
            db.execute("UPDATE purchase SET timestamp = ? WHERE user_id = ?", time, id)
            db.execute("INSERT INTO purchases (user_id, timestamp, buyer, company, symbol, shares, price, total) SELECT user_id, timestamp, buyer, company, symbol, shares, price, total FROM purchase WHERE user_id = ?",id)
            symb = db.execute("SELECT symbol FROM purchase WHERE user_id =?", id)
            symbol = symb[0]["symbol"]
            ava = db.execute("SELECT symbol, CASE WHEN symbol = ? THEN 'YES' ELSE 'NO' END AS result FROM mystock WHERE user_id = ? AND symbol = ?", symbol, id, symbol)
            if not ava == []:
                ashare = db.execute("SELECT shares FROM mystock WHERE user_id = ? AND symbol= ?", id , symbol)
                nshare = db.execute("SELECT * FROM purchase WHERE user_id = ? AND symbol= ?", id , symbol)
                avashare = ashare[0]["shares"]
                avaprice = nshare[0]["price"]
                nowshare = nshare[0]["shares"]
                tshare = avashare + nowshare
                tota = tshare * avaprice
                db.execute("UPDATE mystock SET shares = ?, price = ?, total =?  WHERE user_id= ? AND symbol = ?", tshare, avaprice, tota, id, symbol)
            else:
                db.execute("INSERT INTO mystock (user_id,company,symbol,shares,pprice, price, total) SELECT user_id,company,symbol,shares,total,price,total FROM purchase WHERE user_id = ?", id)
            db.execute("DELETE FROM purchase WHERE user_id = ?", id)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", bacash,id)
            return redirect("/")
            return apology("Something wrong heappened")

        elif int(request.form.get("fid")) == 3:
            id = session["user_id"]
            db.execute("DELETE FROM purchase WHERE user_id = ?", id)
            return redirect("/")

        else:
            return apology("Something wrong heappened")
    else:
        rows = db.execute("SELECT *FROM symbols")
        return render_template("purchase.html", rows=rows)
        return apology("Something wrong heappened")



