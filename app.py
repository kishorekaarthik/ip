from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import json
import pickle
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = 'your_secret_key'

__locations = None
__data_columns = None
__model = None

cred = credentials.Certificate("servicekey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

EMAIL_ADDRESS = '220701135@rajalakshmi.edu.in'
EMAIL_PASSWORD = 'rxkq omqy jork mjoe'

def send_calculated_email(email, subject, message):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
    
def get_past_searches():
    try:
        docs = db.collection('searched_houses').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error fetching past searches: {e}")
        return []


def save_search(location, sqft, bhk, bath, price):
    try:
        doc_ref = db.collection('searched_houses').document()
        doc_ref.set({
            'location': location,
            'sqft': sqft,
            'bhk': bhk,
            'bath': bath,
            'price': price,
            'timestamp': datetime.now()
        })
    except Exception as e:
        print(f"Error saving search data: {e}")

def save_mortgage(principal, rate, years, monthly_payment):
    try:
        doc_ref = db.collection('calculated_mortgages').document()
        doc_ref.set({
            'principal': principal,
            'rate': rate,
            'years': years,
            'monthly_payment': monthly_payment
        })
    except Exception as e:
        print(f"Error saving mortgage data: {e}")

def get_estimated_price(location, sqft, bhk, bath):
    try:
        loc_index = __data_columns.index(location.lower())
    except ValueError:
        loc_index = -1  

    x = np.zeros(len(__data_columns))
    x[0] = sqft
    x[1] = bath
    x[2] = bhk
    if loc_index >= 0:
        x[loc_index] = 1  

    return round(__model.predict([x])[0], 2)

def load_saved_artifacts():
    global __data_columns
    global __locations
    global __model

    try:
        with open("./artifacts/columns.json", "r") as f:
            __data_columns = json.load(f)['data_columns']
            __locations = __data_columns[3:]

        if __model is None:
            with open('./artifacts/model.pkl', 'rb') as f:
                __model = pickle.load(f)
    except Exception as e:
        print(f"Error loading artifacts: {e}")

def get_past_searches():
    try:
        docs = db.collection('searched_houses').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error fetching past searches: {e}")
        return []

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    price = None
    past_searches = get_past_searches()

    if request.method == 'POST':
        location = request.form.get('location', '')
        sqft = request.form.get('sqft', 0, type=float)
        bhk = request.form.get('bkh', 0, type=int)
        bathroom = request.form.get('bathroom', 0, type=int)
        email = request.form.get('email', '')

        if location and sqft > 0 and bhk > 0 and bathroom >= 0:
            price = get_estimated_price(location, sqft, bhk, bathroom)
            save_search(location, sqft, bhk, bathroom, price)
            
            # Send email with the predicted price
            if email:
                message = f"Estimated Price for your criteria:\nLocation: {location}\nSqft: {sqft}\nBHK: {bhk}\nBathroom: {bathroom}\nPrice: {price}"
                send_calculated_email(email, "Predicted House Price", message)
                flash('The estimated price has been sent to your email.', 'success')

    return render_template('predict.html', price=price, past_searches=past_searches)

@app.route('/get_locations')
def get_locations():
    return jsonify({
        'locations': __locations  # Ensure __locations is properly loaded with location data
    })

@app.route('/mortgage', methods=['GET', 'POST'])
def mortgage():
    mortgage = None
    if request.method == 'POST':
        principal = request.form.get('principal', 0, type=float)
        rate = request.form.get('rate', 0, type=float) / 100 / 12
        years = request.form.get('years', 0, type=int) * 12
        email = request.form.get('email', '')

        if principal > 0 and rate >= 0 and years > 0:
            mortgage = (principal * rate) / (1 - (1 + rate) ** -years)
            save_mortgage(principal, rate * 12 * 100, years // 12, mortgage)
            
            # Send email with the mortgage calculation
            if email:
                message = f"Mortgage Calculation:\nPrincipal: {principal}\nRate: {rate * 12 * 100}%\nYears: {years // 12}\nMonthly Payment: {mortgage}"
                send_calculated_email(email, "Mortgage Calculation", message)
                flash('The mortgage calculation has been sent to your email.', 'success')

    return render_template('mortgage.html', mortgage=mortgage)

@app.route('/get_trends')
def get_trends():
    past_searches = get_past_searches()
    trends = [{'timestamp': search['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'price': search['price']} for search in past_searches]
    return jsonify(trends)

@app.route('/trends')
def trends():
    past_searches = get_past_searches()
    trends_data = [{'timestamp': search['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'price': search['price']} for search in past_searches]
    return render_template('trends.html', trends=trends_data)

if __name__ == '__main__':
    load_saved_artifacts()
    app.run(debug=True)
