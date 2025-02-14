from flask import Flask, render_template, send_from_directory, request, jsonify, session, send_file
import requests
import os
import pandas as pd
from io import BytesIO
import json

app = Flask(__name__)
app.secret_key = 'AIzaSyBnXe1a_-Asl9guOmEChKeEqgP3U2L1Jgw'  # Required for session handling

API_KEY = "AIzaSyBnXe1a_-Asl9guOmEChKeEqgP3U2L1Jgw"  # Replace with your actual Google API key


# Serve CSS files from /css directory
@app.route('/css/<path:style.css>')
def serve_css(filename):
    return send_from_directory('css', filename)


# Serve the index.html from the templates folder
@app.route('/')
def index():
    return render_template('index.html')


# Function to fetch businesses based on input
def fetch_businesses(location, radius, categories, website_filter):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    businesses = []
    page_token = None

    while True:
        params = {
            "location": location,
            "radius": radius,
            "key": API_KEY,
            "type": categories[0] if categories[0] != "any" else None,
            "pagetoken": page_token
        }
        response = requests.get(url, params=params).json()
        
        for place in response.get("results", []):
            # Skip if place doesn't have a phone number
            if "formatted_phone_number" not in place:
                continue

            # Skip if filtering by website and website doesn't match criteria
            if website_filter == "without" and place.get("website") and not ("facebook" in place.get("website") or "instagram" in place.get("website")):
                continue

            # Add the business information
            businesses.append({
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "phone": place.get("formatted_phone_number"),
                "website": place.get("website", "N/A"),
                "email": "N/A",  # Placeholder, as Google Places API doesn't provide email
                "category": categories[0] if categories[0] != "any" else "Uncategorized",
            })

        # Check for pagination token
        page_token = response.get("next_page_token")
        if not page_token:
            break

    return businesses


# Route to handle search request
@app.route('/search', methods=['POST'])
def search_businesses():
    location = request.form['location']
    radius = request.form['radius']
    categories = json.loads(request.form['categories'])
    website_filter = request.form['website_filter']

    # Fetch businesses
    businesses = fetch_businesses(location, radius, categories, website_filter)

    # Remove duplicates based on phone number
    unique_businesses = {b['phone']: b for b in businesses}.values()

    # Save businesses in session for pagination and Excel download
    session['businesses'] = list(unique_businesses)

    return jsonify({
        "count": len(unique_businesses),
        "businesses": list(unique_businesses)
    })


# Route to handle Excel file download
@app.route('/download', methods=['GET'])
def download_file():
    businesses = session.get('businesses', [])
    if not businesses:
        return "No businesses found for download."

    # Create a pandas DataFrame
    df = pd.DataFrame(businesses)

    # Create an Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Businesses")

    # Save Excel file to output stream
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='filtered_businesses.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# Route to handle moving a business to the "waiting list"
@app.route('/callback', methods=['POST'])
def callback_business():
    business_name = request.form.get('business_name')

    # Move business from found list to waiting list
    businesses = session.get('businesses', [])
    waiting_list = session.get('waiting_list', [])

    # Find the business to move to waiting list
    business_to_move = next((b for b in businesses if b['name'] == business_name), None)
    
    if business_to_move:
        businesses = [b for b in businesses if b['name'] != business_name]  # Remove from found list
        waiting_list.append(business_to_move)  # Add to waiting list

        # Update session data
        session['businesses'] = businesses
        session['waiting_list'] = waiting_list

        return jsonify({"status": "success", "message": f"Moved {business_name} to waiting list"})

    return jsonify({"status": "error", "message": f"Business {business_name} not found"}), 404


# Route to retrieve the waiting list
@app.route('/waiting_list', methods=['GET'])
def get_waiting_list():
    waiting_list = session.get('waiting_list', [])
    return jsonify({
        "count": len(waiting_list),
        "waiting_list": waiting_list
    })


# Route to reset session data (useful for testing and clearing stored businesses)
@app.route('/reset', methods=['POST'])
def reset_session():
    session.clear()
    return jsonify({"status": "success", "message": "Session reset."})


# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True)
