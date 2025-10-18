# 🧠 mem-agent Web Interface

A modern, interactive web interface for [mem-agent](https://github.com/firstbatchxyz/mem-agent) - a memory-enhanced LLM agent trained using Reinforcement Learning.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![MongoDB](https://img.shields.io/badge/database-MongoDB-green.svg)

> **New!** 🎉 MongoDB integration available - your data now persists forever!

## 🌟 Features

- **💬 Interactive Chat Interface**: Clean, modern UI for conversing with the memory-enhanced AI agent
- **🧠 Memory Management**: Add, view, and manage memories that the agent can utilize
- **📊 Real-time Statistics**: Track memory usage and conversation metrics
- **🎨 Responsive Design**: Works seamlessly on desktop and mobile devices
- **🔌 Multiple Backend Support**: Compatible with OpenRouter, vLLM, and LMStudio
- **⚡ Fast & Lightweight**: Minimal dependencies, quick response times
- **🍃 MongoDB Integration**: Optional persistent storage for production use (NEW!)

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- An API key from [OpenRouter](https://openrouter.ai/) (or local LLM setup)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mem-agent-web.git
   cd mem-agent-web
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   
   Create a `.env` file in the root directory:
   ```bash
   # Flask Configuration
   SECRET_KEY=your-secret-key-here
   FLASK_DEBUG=True
   PORT=5000

   # API Key (get from https://openrouter.ai/)
   OPENROUTER_API_KEY=your-api-key-here

   # Model Configuration
   MODEL_NAME=qwen/qwen-2.5-7b-instruct
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   
   Navigate to `http://localhost:5000`

## 🍃 MongoDB Integration (Optional but Recommended)

For persistent storage that survives server restarts:

### Quick Setup (5 minutes)

1. **Get MongoDB Atlas (Free)**
   - Sign up at https://www.mongodb.com/cloud/atlas/register
   - Create a free cluster
   - Get your connection string

2. **Add to .env**
   ```bash
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/memagent
   ```
   **⚠️ Replace with your actual MongoDB credentials**

3. **Install dependencies**
   ```bash
   pip install pymongo dnspython
   ```

4. **Test connection**
   ```bash
   python test_mongodb.py
   ```

5. **Run with MongoDB**
   ```bash
   python app_with_mongodb.py
   ```

**📖 Complete Guide**: See [MONGODB_QUICKSTART.md](MONGODB_QUICKSTART.md) for detailed instructions.

**Why MongoDB?**
- ✅ Data persists forever (not lost on restart)
- ✅ Scale to millions of memories
- ✅ Multiple servers can share data
- ✅ Free tier available (512MB)

## 📖 Usage

### Basic Chat

1. Type your message in the input box at the bottom
2. Press Enter or click the send button
3. The agent will respond using its memory-enhanced capabilities

### Adding Memories

1. Click the "Add Memory" button in the sidebar
2. Enter a key (e.g., "user_name", "preference")
3. Enter the value (the information to remember)
4. Click "Add Memory"

The agent will now be able to use this information in future conversations!

### Managing Memories

- View all stored memories in the sidebar
- See access counts for each memory
- Clear all memories with the "Clear All" button

## 🔧 Configuration

### Using Different Models

You can use any model supported by OpenRouter by changing the `MODEL_NAME` in your `.env` file:

```bash
# Qwen models
MODEL_NAME=qwen/qwen-2.5-7b-instruct
MODEL_NAME=qwen/qwen-2.5-72b-instruct

# Other models
MODEL_NAME=anthropic/claude-3-sonnet
MODEL_NAME=openai/gpt-4
```

### Using Local Models (vLLM)

To use a locally hosted model with vLLM:

1. Install and run vLLM:
   ```bash
   pip install vllm
   python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct
   ```

2. Update your `.env`:
   ```bash
   USE_VLLM=True
   VLLM_BASE_URL=http://localhost:8000/v1
   MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
   ```

### Using LMStudio

1. Start LMStudio with your preferred model
2. Update your `.env`:
   ```bash
   USE_LMSTUDIO=True
   LMSTUDIO_BASE_URL=http://localhost:1234/v1
   ```

## 🏗️ Architecture

```
mem-agent-web/
├── app.py                  # Flask application & API routes
├── agent_integration.py    # Integration with mem-agent models
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Styling
    └── js/
        └── app.js        # Frontend JavaScript
```

## 🔌 API Endpoints

### Chat
```http
POST /api/chat
Content-Type: application/json

{
  "query": "What's the weather like?",
  "session_id": "session_123",
  "use_memory": true
}
```

### Add Memory
```http
POST /api/memory/add
Content-Type: application/json

{
  "session_id": "session_123",
  "key": "user_name",
  "value": "Alice"
}
```

### Get Statistics
```http
GET /api/memory/stats?session_id=session_123
```

### Clear Memory
```http
POST /api/memory/clear
Content-Type: application/json

{
  "session_id": "session_123"
}
```

### Health Check
```http
GET /api/health
```

## 🤝 Integration with mem-agent

This web interface is designed to work with the [mem-agent](https://github.com/firstbatchxyz/mem-agent) project. To integrate with a trained mem-agent model:

1. Clone the mem-agent repository
2. Follow the setup instructions in the mem-agent README
3. Train your model or use a pre-trained checkpoint
4. Configure this web interface to use your trained model

For detailed information about mem-agent, see the [research paper](https://github.com/firstbatchxyz/mem-agent/blob/main/main.pdf).

## 🚀 Deployment

### Deploy to Heroku

1. Install Heroku CLI
2. Create a new app:
   ```bash
   heroku create your-app-name
   ```
3. Set environment variables:
   ```bash
   heroku config:set OPENROUTER_API_KEY=your-key-here
   heroku config:set SECRET_KEY=your-secret-key
   ```
4. Deploy:
   ```bash
   git push heroku main
   ```

### Deploy to Railway

1. Connect your GitHub repository to Railway
2. Add environment variables in the Railway dashboard
3. Deploy automatically on push

### Deploy to AWS/GCP/Azure

See the deployment guides in the `docs/` directory for cloud-specific instructions.

## 🎨 Customization

### Changing Colors

Edit the CSS variables in `static/css/style.css`:

```css
:root {
    --primary-color: #6366f1;
    --background: #0f172a;
    --surface: #1e293b;
    /* ... */
}
```

### Adding Features

The codebase is modular and easy to extend:

- **Backend**: Add new routes in `app.py`
- **Agent Logic**: Extend `agent_integration.py`
- **Frontend**: Modify `templates/index.html` and `static/js/app.js`

## 📚 Learn More

- [mem-agent GitHub Repository](https://github.com/firstbatchxyz/mem-agent)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)

## 🐛 Troubleshooting

### Common Issues

**"No module named 'flask'"**
```bash
pip install -r requirements.txt
```

**"API key not found"**
- Make sure you've created a `.env` file with your `OPENROUTER_API_KEY`

**"Connection refused"**
- If using vLLM/LMStudio, ensure the local server is running
- Check the base URL in your `.env` file

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [FirstBatch](https://github.com/firstbatchxyz) for the original mem-agent research
- The open-source community for inspiration and tools

## 📞 Support

- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/mem-agent-web/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/mem-agent-web/discussions)

---

Built with ❤️ for the AI community
