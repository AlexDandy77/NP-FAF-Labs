import os
from flask import Flask, request, jsonify
from threading import Lock
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory key-value store
data_store = {}
store_lock = Lock()

# Configuration from environment variables
PORT = int(os.getenv('PORT', 5000))
FOLLOWER_ID = os.getenv('FOLLOWER_ID', 'unknown')

logger.info(f"Follower {FOLLOWER_ID} starting on port {PORT}")


@app.route('/replicate', methods=['POST'])
def replicate():
    """Receive a replication request from the leader."""
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    
    if key is None or value is None:
        return jsonify({"error": "key and value are required"}), 400
    
    # Write to a follower's store
    with store_lock:
        data_store[key] = value
    
    logger.debug(f"Replicated key={key}, value={value}")
    return jsonify({"status": "success"}), 200


@app.route('/read', methods=['GET'])
def read():
    """Read endpoint - returns the value for a given key."""
    key = request.args.get('key')
    
    if key is None:
        return jsonify({"error": "key parameter is required"}), 400
    
    with store_lock:
        value = data_store.get(key)
    
    if value is None:
        return jsonify({"error": "key not found"}), 404
    
    return jsonify({"key": key, "value": value}), 200


@app.route('/data', methods=['GET'])
def get_all_data():
    """Return all data in the store (for testing/verification)."""
    with store_lock:
        return jsonify(data_store.copy()), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "role": "follower", "id": FOLLOWER_ID}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, threaded=True)
