// Global state
let sessionId = generateSessionId();
let isLoading = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadMemoryStats();
});

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Setup event listeners
function setupEventListeners() {
    const input = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    
    // Handle Enter key (Shift+Enter for new line)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    });
    
    // Modal close on background click
    const modal = document.getElementById('add-memory-modal');
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeAddMemoryModal();
        }
    });
}

// Send message
async function sendMessage() {
    const input = document.getElementById('user-input');
    const query = input.value.trim();
    
    if (!query || isLoading) return;
    
    const useMemory = document.getElementById('use-memory').checked;
    
    // Clear input and reset height
    input.value = '';
    input.style.height = 'auto';
    
    // Remove welcome message if it exists
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    // Add user message
    addMessage('user', query);
    
    // Show typing indicator
    showTypingIndicator();
    
    isLoading = true;
    updateSendButton();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                session_id: sessionId,
                use_memory: useMemory
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remove typing indicator
            removeTypingIndicator();
            
            // Add assistant response
            addMessage('assistant', data.response, data.memories_used);
            
            // Update stats
            updateMemoryStats(data.memory_count);
            loadMemoryStats();
        } else {
            throw new Error(data.error || 'Failed to get response');
        }
    } catch (error) {
        removeTypingIndicator();
        addMessage('assistant', '❌ Error: ' + error.message);
        console.error('Error sending message:', error);
    } finally {
        isLoading = false;
        updateSendButton();
    }
}

// Add message to chat
function addMessage(role, text, memories = []) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'A';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const textEl = document.createElement('div');
    textEl.className = 'message-text';
    textEl.textContent = text;
    
    bubble.appendChild(textEl);
    
    // Add memories if any
    if (memories && memories.length > 0) {
        const memoriesDiv = document.createElement('div');
        memoriesDiv.className = 'memories-used';
        
        memories.forEach(memory => {
            const badge = document.createElement('span');
            badge.className = 'memory-badge';
            badge.textContent = `📚 ${memory.key}`;
            badge.title = memory.value;
            memoriesDiv.appendChild(badge);
        });
        
        bubble.appendChild(memoriesDiv);
    }
    
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    meta.innerHTML = `<span>${new Date().toLocaleTimeString()}</span>`;
    if (memories && memories.length > 0) {
        meta.innerHTML += `<span>Used ${memories.length} memor${memories.length === 1 ? 'y' : 'ies'}</span>`;
    }
    
    content.appendChild(bubble);
    content.appendChild(meta);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.className = 'message assistant';
    indicator.id = 'typing-indicator';
    
    indicator.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Update send button state
function updateSendButton() {
    const sendButton = document.getElementById('send-button');
    sendButton.disabled = isLoading;
}

// Load memory statistics
async function loadMemoryStats() {
    try {
        const response = await fetch(`/api/memory/stats?session_id=${sessionId}`);
        const data = await response.json();
        
        if (data.success) {
            updateMemoryStats(data.stats.total_memories);
            updateConversationCount(Math.floor(data.stats.conversation_length / 2));
            displayMemoryList(data.stats.memory_items);
        }
    } catch (error) {
        console.error('Error loading memory stats:', error);
    }
}

// Update memory statistics
function updateMemoryStats(count) {
    const countEl = document.getElementById('memory-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

// Update conversation count
function updateConversationCount(count) {
    const countEl = document.getElementById('conversation-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

// Display memory list
function displayMemoryList(memories) {
    const listEl = document.getElementById('memory-list');
    
    if (!memories || memories.length === 0) {
        listEl.innerHTML = '<p class="empty-state">No memories stored yet</p>';
        return;
    }
    
    listEl.innerHTML = memories.map(memory => `
        <div class="memory-item">
            <span class="memory-key">${escapeHtml(memory.key)}</span>
            <div class="memory-meta">
                <span>Accessed: ${memory.access_count}x</span>
            </div>
        </div>
    `).join('');
}

// Show add memory modal
function showAddMemoryModal() {
    const modal = document.getElementById('add-memory-modal');
    modal.classList.add('active');
    document.getElementById('memory-key').focus();
}

// Close add memory modal
function closeAddMemoryModal() {
    const modal = document.getElementById('add-memory-modal');
    modal.classList.remove('active');
    document.getElementById('memory-key').value = '';
    document.getElementById('memory-value').value = '';
}

// Add memory
async function addMemory() {
    const key = document.getElementById('memory-key').value.trim();
    const value = document.getElementById('memory-value').value.trim();
    
    if (!key || !value) {
        alert('Please fill in both key and value');
        return;
    }
    
    try {
        const response = await fetch('/api/memory/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                key: key,
                value: value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeAddMemoryModal();
            loadMemoryStats();
            
            // Show success message in chat
            const messagesContainer = document.getElementById('chat-messages');
            const welcomeMessage = messagesContainer.querySelector('.welcome-message');
            if (welcomeMessage) {
                welcomeMessage.remove();
            }
            
            addMessage('assistant', `✅ Memory "${key}" has been added successfully.`);
        } else {
            throw new Error(data.error || 'Failed to add memory');
        }
    } catch (error) {
        alert('Error adding memory: ' + error.message);
        console.error('Error adding memory:', error);
    }
}

// Clear memory
async function clearMemory() {
    if (!confirm('Are you sure you want to clear all memories? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/memory/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadMemoryStats();
            addMessage('assistant', '🗑️ All memories have been cleared.');
        } else {
            throw new Error(data.error || 'Failed to clear memory');
        }
    } catch (error) {
        alert('Error clearing memory: ' + error.message);
        console.error('Error clearing memory:', error);
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Health check on load
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        console.log('Server health:', data);
    } catch (error) {
        console.error('Server health check failed:', error);
    }
}

// Run health check
checkHealth();
