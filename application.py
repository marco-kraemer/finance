import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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
    #Create lists
    shares = []
    prices = []
    totals = []
    stocksymbols = []
    stocknames = []
    cashtotal_ = 0

    #get number of rows
    row = db.execute("SELECT * FROM stockindex WHERE userid = :id", id=session["user_id"])
    rows = len(row)

    #Get stock symbol from database(stockindex)
    symbol = db.execute("SELECT symbol FROM stockindex WHERE userid = :id", id=session["user_id"])

    #get user CASH(use in last row) from database(users)
    usercash = db.execute("SELECT cash FROM users WHERE id= :id", id=session["user_id"])
    cash = usd(usercash[0]["cash"])
    cashfloat = float(usercash[0]["cash"])

    for i in range(len(row)):
        #get number of shares bought from database(stockindex)
        shares_ = db.execute("SELECT shares FROM stockindex WHERE userid = :id", id=session["user_id"])
        share = int(shares_[i]["shares"])
        shares.append(share)

        #Get stocks data(name and price) using lookup function
        stock = lookup(symbol[i]["symbol"])

        #get stock price from lookup
        price_ = stock["price"]
        price = usd(price_)
        prices.append(price)

        #Get stock symbols
        stocksymbol = stock["symbol"]
        stocksymbols.append(stocksymbol)

        #Get stock names
        stockname = stock["name"]
        stocknames.append(stockname)

        #Get TOTAL
        pricefloat = float(stock["price"])
        totalfloat = pricefloat * share
        total = usd(totalfloat)
        totals.append(total)

        #Get sum of TOTALS
        cashtotal_ = cashtotal_ + totalfloat

    #Add cash to sum of TOTALS
    cashtotalfloat = cashtotal_ + cashfloat
    cashtotal = usd(cashtotalfloat)

    #return template
    return render_template("index.html", rows = rows, stocksymbols=stocksymbols, stocknames=stocknames,shares=shares, prices=prices, cash=cash, totals=totals, cashtotal=cashtotal)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "POST":

        #Ensure user type cash amount
        if not request.form.get("cash"):
            return apology("Must select amount")

        #Update cash from users
        updatecash = int(request.form.get("cash"))
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        usercash=float(cash[0]["cash"])
        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=usercash + updatecash, id=session["user_id"])
        db.execute("INSERT INTO history (userid, symbol, name, shares, price) VALUES (:userid ,:symbol, :name, :shares, :price)", userid=session["user_id"], symbol=" ", name="Add Cash", shares=" ", price= usd(updatecash))

        return redirect("/")

    else:
        return render_template("addcash.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    #user submitted the form
    if request.method == "POST":

        #Get stocks data
        stock = lookup(request.form.get("symbol"))

        #Get user's money
        usercash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        cash = float(usercash[0]["cash"])

        #Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("Must provide a valid stock symbol", 403)

        elif stock == None:
            return apology("Must provide a valid stock symbol", 403)

        #Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("Must provide a valid number of stocks", 403)

        #Get number of shares
        stockshares = float(request.form.get("shares"))
        stockshares2 = request.form.get("shares")

        #Check user's cash
        if cash < stock["price"] * stockshares:
            return apology("Not enough money")

        #If not first time: Update number of stocks
        symbolbefore = request.form.get("symbol")
        symbolupper = symbolbefore.upper()
        rows = db.execute("SELECT * FROM stockindex WHERE userid = :id AND symbol = :symbol", id=session["user_id"], symbol = symbolupper)
        if len(rows) != 0:
            numshares_ =  db.execute("SELECT shares FROM stockindex WHERE userid = :id AND symbol = :symbol", id=session["user_id"], symbol = symbolupper)
            numshares = int(numshares_[0]["shares"])
            db.execute("UPDATE stockindex SET shares = :shares WHERE userid = :id AND symbol = :symbol", shares=numshares + stockshares, id=session["user_id"], symbol = symbolupper)
            db.execute("INSERT INTO history (userid, symbol, name, shares, price) VALUES (:userid ,:symbol, :name, :shares, :price)", userid=session["user_id"], symbol=stock["symbol"], name=stock["name"], shares=stockshares2, price=stock["price"])

        #If first time: Insert stock data in stockindex
        else:
            db.execute("INSERT INTO stockindex (userid, symbol, name, shares, price) VALUES (:userid ,:symbol, :name, :shares, :price)", userid=session["user_id"], symbol=stock["symbol"], name=stock["name"], shares=stockshares, price=stock["price"])
            db.execute("INSERT INTO history (userid, symbol, name, shares, price) VALUES (:userid ,:symbol, :name, :shares, :price)", userid=session["user_id"], symbol=stock["symbol"], name=stock["name"], shares=stockshares2, price=stock["price"])
        #Subtract user's money from cash
        aftercash = cash - (stockshares * stock["price"])

        #Update cash column in user
        db.execute("UPDATE users SET cash = :aftercash WHERE id = :id", aftercash=aftercash, id=session["user_id"])

        #redirect user to index
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    #Create lists
    names = []
    symbols = []
    shares = []
    prices = []
    dates = []
    times = []

    #Get rows from history.db
    row = db.execute("SELECT symbol FROM history WHERE userid = :id", id=session["user_id"])
    rows = len(row)

    #Get name from history.db
    namedict = db.execute("SELECT name FROM history WHERE userid = :id", id=session["user_id"])

    #Get symbol from history.db
    symboldict = db.execute("SELECT symbol FROM history WHERE userid = :id", id=session["user_id"])

    #Get shares from history db
    sharedict = db.execute("SELECT shares FROM history WHERE userid = :id", id=session["user_id"])

    #Get price from history.db
    pricedict = db.execute("SELECT price FROM history WHERE userid = :id", id=session["user_id"])

    #Get date from history.db
    datedict = db.execute("SELECT date FROM history WHERE userid = :id", id=session["user_id"])

    #Get time from history.db
    timedict = db.execute("SELECT time FROM history WHERE userid = :id", id=session["user_id"])

    for i in range(rows):

        name = namedict[i]["name"]
        names.append(name)

        symbol = symboldict[i]["symbol"]
        symbols.append(symbol)

        share = sharedict[i]["shares"]
        shares.append(share)

        price = pricedict[i]["price"]
        prices.append(price)

        date = datedict[i]["date"]
        dates.append(date)

        time = timedict[i]["time"]
        times.append(time)

    return render_template("history.html", rows=rows, names=names, symbols=symbols, shares=shares, prices=prices, dates=dates, times=times)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    #Display form to request a stock quote
    if request.method == "POST":

        #Get stocks data
        stock = lookup(request.form.get("symbol"))

        #ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("Must provide a valid stock symbol", 403)

        #if stock symbol is invalid
        elif stock == None:
            return apology("Must provide a valid stock symbol", 403)

        return render_template("quoted.html", stock=stock)

    #Lookup the stock symbol by calling lookuo function and display the result
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #User reaches submitting the form
    if request.method == "POST":

        #ensure name was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 403)

        #ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 403)

        #ensure passwords are the same
        elif request.form.get("password") != request.form.get("confirm_password"):
            return apology("Passwords aren't the same", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        #Check if user already exist
        if len(rows) != 0:
            return apology("Username already exist", 403)

        #Get user informations
        username = request.form.get("username")
        password_before = request.form.get("password")

        #Hash password
        password = generate_password_hash(password_before)

        #Insert data into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username=username, password=password)
        return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        #Check if share != None
        if not request.form.get("shares"):
            return apology("Invalid number of shares", 403)

        #Check if user has enough shares
        usershare = db.execute("SELECT shares FROM stockindex WHERE userid = :id AND symbol = :symbol", id = session["user_id"], symbol = request.form.get("symbol"))
        numbshares = int(usershare[0]["shares"])
        userinput = int(request.form.get("shares"))
        if numbshares < userinput:
            return  apology("Invalid number of shares", 403)

        #Get stock price using lookup
        stock = lookup(request.form.get("symbol"))
        price = float(stock["price"])

        #Multiply price and shares
        ordertotal = userinput * price

        #Add amount to users'cash in database(users)
        usercash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        aftercash = (usercash[0]["cash"] + ordertotal)
        db.execute("UPDATE users SET cash = :aftercash WHERE id = :id", aftercash=aftercash, id=session["user_id"])

        #Subtract number of shares from database(stockindex)
        stockshares = db.execute("SELECT shares FROM stockindex WHERE userid = :id AND symbol = :symbol", id = session["user_id"], symbol = request.form.get("symbol"))
        aftershare = (stockshares[0]["shares"] - userinput)
        db.execute("UPDATE stockindex SET shares = :aftershare WHERE userid = :id AND symbol = :symbol", aftershare=aftershare, id=session["user_id"], symbol = request.form.get("symbol"))

        #Insert order into history.db
        db.execute("INSERT INTO history (userid, symbol, name, shares, price) VALUES (:userid ,:symbol, :name, :shares, :price)", userid=session["user_id"], symbol=stock["symbol"], name=stock["name"], shares= -(userinput), price=stock["price"])

        #Remove row from database(stockindex) if shares = 0
        db.execute("DELETE FROM stockindex WHERE shares = 0;")

        return redirect("/")

    else:
        stocksymbols=[]
        stocksymbol_ = db.execute("SELECT symbol FROM stockindex WHERE userid = :id ORDER BY symbol", id = session["user_id"])
        for i in range(len(stocksymbol_)):
            stocksymbol = stocksymbol_[i]["symbol"]
            stocksymbols.append(stocksymbol)
        return render_template("sell.html", stocksymbols=stocksymbols)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
