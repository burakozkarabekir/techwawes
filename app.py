"""
Memory Agent Web Interface
A Flask-based web server for interacting with mem-agent
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
from datetime import datetime
import uuid

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# In-memory storage for conversations (replace with database in production)
conversations = {}

class MemoryAgent:
    """Simple memory-augmented agent interface"""
    
    def __init__(self):
        self.memory_bank = {}
        self.conversation_history = []
        
    def add_to_memory(self, key, value):
        """Store information in memory"""
        self.memory_bank[key] = {
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'access_count': 0
        }
        
    def retrieve_from_memory(self, key):
        """Retrieve information from memory"""
        if key in self.memory_bank:
            self.memory_bank[key]['access_count'] += 1
            return self.memory_bank[key]['value']
        return None
    
    def get_relevant_memories(self, query):
        """Get memories relevant to the query"""
        relevant = []
        query_lower = query.lower()
        for key, data in self.memory_bank.items():
            if key.lower() in query_lower or query_lower in str(data['value']).lower():
                relevant.append({
                    'key': key,
                    'value': data['value'],
                    'timestamp': data['timestamp']
                })
        return relevant
    
    def process_query(self, query, use_memory=True):
        """Process a query with memory context"""
        # Add to conversation history
        self.conversation_history.append({
            'role': 'user',
            'content': query,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get relevant memories
        memories = self.get_relevant_memories(query) if use_memory else []
        
        # Simulate agent response (in production, integrate with actual LLM)
        response = self._generate_response(query, memories)
        
        # Store response in history
        self.conversation_history.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat(),
            'memories_used': len(memories)
        })
        
        return {
            'response': response,
            'memories_used': memories,
            'memory_count': len(self.memory_bank)
        }
    
    def _generate_response(self, query, memories):
        """Generate response based on query and memories"""
        context = ""
        if memories:
            context = "\n[Using memories: " + ", ".join([m['key'] for m in memories]) + "]"
        
        # Placeholder response - integrate with actual mem-agent here
        return f"Memory Agent Response to: '{query}'{context}\n\nThis is a demonstration response. To integrate the actual mem-agent, connect to the trained model using the OpenRouter or vLLM API as configured in the mem-agent repository."
    
    def clear_memory(self):
        """Clear all stored memories"""
        self.memory_bank = {}
        
    def get_stats(self):
        """Get memory statistics"""
        return {
            'total_memories': len(self.memory_bank),
            'conversation_length': len(self.conversation_history),
            'memory_items': [
                {
                    'key': k,
                    'timestamp': v['timestamp'],
                    'access_count': v['access_count']
                }
                for k, v in self.memory_bank.items()
            ]
        }

@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests"""
    data = request.json
    query = data.get('query', '')
    session_id = data.get('session_id', str(uuid.uuid4()))
    use_memory = data.get('use_memory', True)
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Get or create agent for this session
    if session_id not in conversations:
        conversations[session_id] = MemoryAgent()
    
    agent = conversations[session_id]
    
    try:
        result = agent.process_query(query, use_memory)
        return jsonify({
            'success': True,
            'session_id': session_id,
            **result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/memory/add', methods=['POST'])
def add_memory():
    """Add a memory to the agent"""
    data = request.json
    session_id = data.get('session_id')
    key = data.get('key')
    value = data.get('value')
    
    if not all([session_id, key, value]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if session_id not in conversations:
        conversations[session_id] = MemoryAgent()
    
    agent = conversations[session_id]
    agent.add_to_memory(key, value)
    
    return jsonify({
        'success': True,
        'message': f'Memory "{key}" added successfully'
    })

@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    """Get memory statistics"""
    session_id = request.args.get('session_id')
    
    if not session_id or session_id not in conversations:
        return jsonify({'error': 'Invalid session'}), 400
    
    agent = conversations[session_id]
    stats = agent.get_stats()
    
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/api/memory/clear', methods=['POST'])
def clear_memory():
    """Clear all memories for a session"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in conversations:
        return jsonify({'error': 'Invalid session'}), 400
    
    agent = conversations[session_id]
    agent.clear_memory()
    
    return jsonify({
        'success': True,
        'message': 'Memory cleared successfully'
    })

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(conversations),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)