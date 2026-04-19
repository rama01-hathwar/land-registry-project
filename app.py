# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 03:26:05 2025

@author: RAMA
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

#from helpers import (
    #load_data,
    3get_ohlc_table_html,
    #make_price_plot,
    #make_comparison_plot,
    #make_moving_average_plot,
    #make_rsi_plot,
    #make_bollinger_plot,
    #make_macd_plot,
    #predict_next_10_days,
    #make_random_forest_prediction,
    #make_prediction_plot,
    #plot_correlation_heatmap,
    #compute_risk_metrics_html,
    #compute_volatility_plot,
    #compute_beta_and_riskscore,
    #sentiment_analyze
#)

app = Flask(__name__, static_folder="static")
app.secret_key = "super_secret_key"
DB_FILE = "users.db"


# ---------------- DATABASE ----------------
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()


# ---------------- HELPERS ----------------
def get_saved():
    return {
        "tickers": session.get("saved_tickers", ""),
        "start_date": session.get("saved_start_date", ""),
        "end_date": session.get("saved_end_date", ""),
        # default empty — only include benchmark when user sets it
        "benchmark": session.get("saved_benchmark", "")
    }

# ---------------- AUTH ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("All fields are required!", "warning")
            return redirect(url_for("register"))

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                      (username, generate_password_hash(password)))
            conn.commit()
            flash("Registered successfully. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
        finally:
            conn.close()

    return render_template("register.html", title="Register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            flash("Welcome, " + username, "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html", title="Login")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/", methods=["GET", "POST"])
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    common_tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "SPY", "RELIANCE.NS", "INFY.NS"]
    saved = get_saved()

    if request.method == "POST":
        ticker_box = request.form.get("ticker_box", "").strip()
        ticker_dropdown = request.form.get("ticker_dropdown") or ""
        tickers = []

        if ticker_dropdown:
            tickers.append(ticker_dropdown)
        if ticker_box:
            tickers.extend([t.strip().upper() for t in ticker_box.split(",") if t.strip()])

        ticker = ",".join(sorted(set(tickers)))
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        benchmark = request.form.get("benchmark") or saved["benchmark"]

        if not ticker or not start_date or not end_date:
            flash("Please fill in all fields.", "warning")
        else:
            session["saved_tickers"] = ticker
            session["saved_start_date"] = start_date
            session["saved_end_date"] = end_date
            session["saved_benchmark"] = benchmark
            flash("Data saved successfully! Use navigation bar to analyze.", "success")
            return redirect(url_for("dashboard"))

    return render_template("dashboard.html", common_tickers=common_tickers, saved=saved, title="Dashboard")


# ---------------- HISTORICAL ----------------
@app.route("/historical", methods=["GET", "POST"])
def historical():
    if "user_id" not in session:
        return redirect(url_for("login"))

    saved = get_saved()
    tickers = [t.strip() for t in saved["tickers"].split(",") if t.strip()]
    start_date, end_date = saved["start_date"], saved["end_date"]
    data_dict = load_data(tickers, start_date, end_date)

    # ✅ Generate OHLC tables for all tickers
    ohlc_tables = {}
    for t in tickers:
        try:
            ohlc_tables[t] = get_ohlc_table_html(data_dict.get(t))
        except Exception as e:
            ohlc_tables[t] = f"<p class='text-danger'>Error loading data for {t}: {e}</p>"

    results = {}

    if request.method == "POST":
        if "do_sma" in request.form:
            results["sma_ema"] = make_moving_average_plot(data_dict)
        if "do_boll" in request.form:
            results["bollinger"] = make_bollinger_plot(data_dict)
        if "do_rsi" in request.form:
            results["rsi"] = make_rsi_plot(data_dict)
        if "do_macd" in request.form:
            results["macd"] = make_macd_plot(data_dict)

    # ✅ Send ohlc_tables to the template
    return render_template(
        "historical.html",
        ohlc_tables=ohlc_tables,
        results=results,
        title="Historical Analysis"
    )

# ---------------- PREDICTION ----------------
@app.route("/prediction", methods=["GET", "POST"])
def prediction():
    if "user_id" not in session:
        return redirect(url_for("login"))

    saved = get_saved()
    tickers = [t.strip() for t in saved["tickers"].split(",") if t.strip()]
    start_date, end_date = saved["start_date"], saved["end_date"]
    arima_results, rf_results = {}, {}

    if request.method == "POST":
        data = load_data(tickers, start_date, end_date)
        for t in tickers:
            df = data.get(t)
            if "do_arima" in request.form:
                pred_df, method = predict_next_10_days(df)
                arima_results[t] = {
                    "table": pred_df.to_html(classes="table table-sm table-bordered", index=False) if pred_df is not None else "<p>No data</p>",
                    "plot": make_prediction_plot(pred_df, f"{t} - {method.upper()}") if pred_df is not None else None
                }
            if "do_rf" in request.form:
                rf_df = make_random_forest_prediction(df)
                rf_results[t] = {
                    "table": rf_df.to_html(classes="table table-sm table-bordered", index=False) if rf_df is not None else "<p>No data</p>",
                    "plot": make_prediction_plot(rf_df, f"{t} - Random Forest") if rf_df is not None else None
                }

    return render_template("prediction.html", arima_results=arima_results, rf_results=rf_results, title="Prediction")


# ---------------- RISK ----------------
@app.route("/risk", methods=["GET", "POST"])
def risk():
    if "user_id" not in session:
        return redirect(url_for("login"))

    saved = get_saved()
    # saved["tickers"] may be "AAPL,AMZN"
    tickers = [t.strip() for t in saved["tickers"].split(",") if t.strip()]
    start_date = saved["start_date"]
    end_date = saved["end_date"]
    saved_benchmark = saved.get("benchmark", "").strip()

    # Results to render
    metrics_html = None
    vol_plot = None
    beta_info = None
    include_benchmark = False

    if request.method == "POST":

      include_benchmark = True if request.form.get("include_benchmark") else False

    # Always enforce benchmark if beta is required
    benchmark_to_use = saved_benchmark if saved_benchmark else "SPY"

    to_fetch = list(tickers)
    if benchmark_to_use not in to_fetch:
        to_fetch.append(benchmark_to_use)

    data = load_data(to_fetch, start_date, end_date)

    metrics_input = {t: data.get(t) for t in tickers}
    metrics_html = compute_risk_metrics_html(metrics_input)

    vol_input = {t: data.get(t) for t in to_fetch}
    vol_plot = compute_volatility_plot(vol_input)

    beta_info = []

    benchmark_df = data.get(benchmark_to_use)

    if benchmark_df is None or benchmark_df.empty:
        beta_info.append({
            "error": f"Benchmark data ({benchmark_to_use}) not available"
        })
    else:
        for t in tickers:
            stock_df = data.get(t)
            try:
                beta, cov, var_m = compute_beta_and_riskscore(stock_df, benchmark_df)

                beta_info.append({
                    "ticker": t,
                    "benchmark": benchmark_to_use,
                    "beta": round(beta, 3),
                    "covariance": round(cov, 6),
                    "market_variance": round(var_m, 6)
                })
            except Exception as e:
                beta_info.append({
                    "ticker": t,
                    "benchmark": benchmark_to_use,
                    "error": str(e)
                })


    return render_template("risk.html",
                           metrics_html=metrics_html,
                           vol_plot=vol_plot,
                           beta_info=beta_info,
                           saved={"tickers": ",".join(tickers), "start_date": start_date, "end_date": end_date, "benchmark": saved_benchmark},
                           title="Risk & Volatility")


# ---------------- COMPARISON ----------------
@app.route("/comparison", methods=["GET", "POST"])
def comparison():
    if "user_id" not in session:
        return redirect(url_for("login"))

    saved = get_saved()
    tickers = [t.strip() for t in saved["tickers"].split(",") if t.strip()]
    start_date, end_date = saved["start_date"], saved["end_date"]

    price_html = pct_html = heatmap_html = None

    if request.method == "POST":
        data_dict = load_data(tickers, start_date, end_date)
        price_html = make_price_plot(data_dict)
        pct_html = make_comparison_plot(data_dict)
        if "show_heatmap" in request.form:
            heatmap_html = plot_correlation_heatmap(data_dict)

    return render_template("comparison.html", price_html=price_html, pct_html=pct_html, heatmap_html=heatmap_html, title="Comparison")


# ---------------- SENTIMENT ----------------
@app.route("/sentiment", methods=["GET", "POST"])
def sentiment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    label, chart = None, None
    if request.method == "POST":
        text = request.form.get("text")
        label, chart = sentiment_analyze(text)

    return render_template("sentiment.html", result_label=label, chart=chart, title="Sentiment")

#------------------performance------------------
@app.route("/performance", methods=["GET", "POST"])
def performance():
    if "user_id" not in session:
        return redirect(url_for("login"))

    saved_tickers = session.get("saved_tickers") or ""
    start_date = session.get("saved_start_date") or ""
    end_date = session.get("saved_end_date") or ""
    tickers = [t.strip() for t in saved_tickers.split(",") if t.strip()]

    if not tickers or not start_date or not end_date:
        flash("Please select a valid ticker and date range in Dashboard.", "warning")
        return redirect(url_for("dashboard"))

    from helpers import (
        load_data, predict_next_10_days, make_random_forest_prediction, compute_detailed_performance
    )

    ticker = tickers[0]
    data = load_data([ticker], start_date, end_date)
    df = data.get(ticker)

    if df is None or df.empty:
        flash("No valid data for performance analysis.", "danger")
        return redirect(url_for("dashboard"))

    # --- HISTORICAL MODELS ---
    sma_df = df.copy(); sma_df["Predicted"] = df["Close"].rolling(5).mean().fillna(method="bfill")
    boll_df = df.copy(); boll_df["Predicted"] = df["Close"].rolling(10).mean().fillna(method="bfill")
    rsi_df = df.copy(); rsi_df["Predicted"] = df["Close"].shift(1).fillna(method="bfill")
    macd_df = df.copy(); macd_df["Predicted"] = (
        df["Close"].ewm(span=12, adjust=False).mean() - df["Close"].ewm(span=26, adjust=False).mean()
    ).fillna(method="bfill")

    historical_models = {
        "Simple Moving Average": sma_df,
        "Bollinger Bands": boll_df,
        "RSI": rsi_df,
        "MACD": macd_df
    }

    hist_table, hist_plot, hist_best = compute_detailed_performance(df, historical_models, "Historical")

    # --- PREDICTION MODELS ---
    arima_df, _ = predict_next_10_days(df)
    rf_df = make_random_forest_prediction(df)
    predictive_models = {"ARIMA": arima_df, "Random Forest": rf_df}
    pred_table, pred_plot, pred_best = compute_detailed_performance(df, predictive_models, "Prediction")

    return render_template(
        "performance.html",
        hist_table=hist_table, hist_plot=hist_plot, hist_best=hist_best,
        pred_table=pred_table, pred_plot=pred_plot, pred_best=pred_best,
        title="Performance Metrics"
    )



if __name__ == "__main__":
    init_db()
    app.run(debug=True)
