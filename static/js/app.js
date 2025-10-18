// TechWawes AI - Modern Interface JavaScript

// Global state
let sessionId = generateSessionId();
let isLoading = false;
let memoryPanelOpen = false;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    setupNavigation();
    loadMemoryStats();
    checkHealth();
}

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Setup event listeners
function setupEventListeners() {
    const input = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    
    if (input) {
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
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });
    }
    
    // Modal close on background click
    const modal = document.getElementById('add-memory-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeAddMemoryModal();
            }
        });
    }
}

// Navigation functions
function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const navToggle = document.querySelector('.nav-toggle');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            scrollToSection(targetId);
            
            // Update active link
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
        });
    });
    
    if (navToggle) {
        navToggle.addEventListener('click', toggleMobileMenu);
    }
}

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

function toggleMobileMenu() {
    const navLinks = document.querySelector('.nav-links');
    navLinks.classList.toggle('active');
}

// Hero section functions
function startChat() {
    scrollToSection('demo');
    setTimeout(() => {
        const input = document.getElementById('user-input');
        if (input) input.focus();
    }, 500);
}

function scrollToDemo() {
    scrollToSection('demo');
}

// Chat functions
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

function sendSuggestion(text) {
    const input = document.getElementById('user-input');
    if (input) {
        input.value = text;
        sendMessage();
    }
}

// Message display functions
function addMessage(role, text, memories = []) {
    const messagesContainer = document.getElementById('chat-messages');
    if (!messagesContainer) return;
    
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

function showTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');
    if (!messagesContainer) return;
    
    const indicator = document.createElement('div');
    indicator.className = 'message assistant';
    indicator.id = 'typing-indicator';
    
    indicator.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function updateSendButton() {
    const sendButton = document.getElementById('send-button');
    if (sendButton) {
        sendButton.disabled = isLoading;
    }
}

// Memory management functions
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

function updateMemoryStats(count) {
    const countEl = document.getElementById('memory-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

function updateConversationCount(count) {
    const countEl = document.getElementById('conversation-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

function displayMemoryList(memories) {
    const listEl = document.getElementById('memory-list');
    if (!listEl) return;
    
    if (!memories || memories.length === 0) {
        listEl.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>No memories stored yet</p>
            </div>
        `;
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

// Memory panel functions
function toggleMemoryPanel() {
    const panel = document.getElementById('memory-panel');
    if (panel) {
        memoryPanelOpen = !memoryPanelOpen;
        panel.classList.toggle('active', memoryPanelOpen);
    }
}

function toggleMemory() {
    toggleMemoryPanel();
}

// Memory modal functions
function showAddMemoryModal() {
    const modal = document.getElementById('add-memory-modal');
    if (modal) {
        modal.classList.add('active');
        const keyInput = document.getElementById('memory-key');
        if (keyInput) keyInput.focus();
    }
}

function closeAddMemoryModal() {
    const modal = document.getElementById('add-memory-modal');
    if (modal) {
        modal.classList.remove('active');
        const keyInput = document.getElementById('memory-key');
        const valueInput = document.getElementById('memory-value');
        if (keyInput) keyInput.value = '';
        if (valueInput) valueInput.value = '';
    }
}

async function addMemory() {
    const keyInput = document.getElementById('memory-key');
    const valueInput = document.getElementById('memory-value');
    
    if (!keyInput || !valueInput) return;
    
    const key = keyInput.value.trim();
    const value = valueInput.value.trim();
    
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

async function clearAllMemories() {
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

function clearChat() {
    const messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) {
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-content">
                    <i class="fas fa-sparkles"></i>
                    <h3>Welcome to TechWawes AI!</h3>
                    <p>I'm your memory-enhanced AI assistant. I can remember our conversations and learn from them. Try asking me about yourself or any topic!</p>
                    <div class="suggestions">
                        <button class="suggestion-btn" onclick="sendSuggestion('Tell me about yourself')">Tell me about yourself</button>
                        <button class="suggestion-btn" onclick="sendSuggestion('What can you remember?')">What can you remember?</button>
                        <button class="suggestion-btn" onclick="sendSuggestion('Help me with a task')">Help me with a task</button>
                    </div>
                </div>
            </div>
        `;
    }
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        console.log('Server health:', data);
    } catch (error) {
        console.error('Server health check failed:', error);
    }
}

// Smooth scrolling for navigation
function smoothScrollTo(target) {
    const element = document.querySelector(target);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Intersection Observer for navigation highlighting
const observerOptions = {
    root: null,
    rootMargin: '-50% 0px -50% 0px',
    threshold: 0
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.id;
            const navLink = document.querySelector(`.nav-link[href="#${id}"]`);
            if (navLink) {
                document.querySelectorAll('.nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                navLink.classList.add('active');
            }
        }
    });
}, observerOptions);

// Observe sections when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('section[id]');
    sections.forEach(section => {
        observer.observe(section);
    });
});

// Add some interactive animations
document.addEventListener('DOMContentLoaded', () => {
    // Animate feature cards on scroll
    const featureCards = document.querySelectorAll('.feature-card');
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 100);
            }
        });
    }, { threshold: 0.1 });

    featureCards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        cardObserver.observe(card);
    });
});

// Add keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus chat input
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const input = document.getElementById('user-input');
        if (input) {
            input.focus();
            scrollToSection('demo');
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        closeAddMemoryModal();
        if (memoryPanelOpen) {
            toggleMemoryPanel();
        }
    }
});

// Add loading states and error handling
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#6366f1'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        z-index: 3000;
        animation: slideInRight 0.3s ease-out;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);
