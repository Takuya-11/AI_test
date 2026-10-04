import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

ACCOUNT_ID    = os.getenv('ZOOM_ACCOUNT_ID')
CLIENT_ID     = os.getenv('ZOOM_CLIENT_ID')
CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')


def get_access_token():
    url = f'https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}'
    res = requests.post(url, auth=(CLIENT_ID, CLIENT_SECRET))
    res.raise_for_status()
    return res.json()['access_token']


@app.route('/api/create-meeting', methods=['POST'])
def create_meeting():
    try:
        data = request.get_json()
        topic    = data.get('topic', 'APIテストミーティング')
        duration = int(data.get('duration', 60))
        start    = data.get('start_time', (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S'))

        token = get_access_token()

        payload = {
            'topic': topic,
            'type': 2,
            'start_time': start,
            'duration': duration,
            'timezone': 'Asia/Tokyo',
            'settings': {'waiting_room': False},
        }
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        res = requests.post('https://api.zoom.us/v2/users/me/meetings', json=payload, headers=headers)
        res.raise_for_status()
        meeting = res.json()

        return jsonify({
            'topic':    meeting['topic'],
            'id':       meeting['id'],
            'password': meeting.get('password', ''),
            'join_url': meeting['join_url'],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)
